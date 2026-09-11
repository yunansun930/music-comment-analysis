"""
Step7 模型预测 - 用户流失预测

定义流失：用户最近一次评论距今天数 > 90 天 → churn=1，否则 churn=0

特征工程：
  - 行为统计：评论数 / 回复数 / 获赞数 / 活跃天数 / 平均评论长度
  - 用户价值：activity_score / interaction_score / diversity_score / user_value
  - 情感特征：avg_sentiment / sentiment_type_encoded
  - 时间特征：register_days / active_period_encoded
  - RFM 分群：r_score / f_score / m_score / rfm_total / rfm_cluster（来自 step5 模块 A）

模型：LogisticRegression / RandomForest / XGBoost
处理类别不平衡：class_weight='balanced' / scale_pos_weight
"""

import os
import logging

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, average_precision_score
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler

from config import MODEL_DIR
from db_helper import read_sql, write_table, execute


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("step7.churn")

RANDOM_STATE = 42
CHURN_DAYS_THRESHOLD = 90  # 90 天未评论判定为流失


def _create_tables():
    execute("""
        CREATE TABLE IF NOT EXISTS ads_churn_predict (
            user_id             VARCHAR(32) PRIMARY KEY COMMENT '用户ID',
            recency_days        INT COMMENT '最近评论距今天数',
            actual_label        INT COMMENT '真实流失标签(0=活跃,1=流失)',
            churn_prob          DECIMAL(8,6) COMMENT '流失概率',
            is_churn_predicted  INT COMMENT '预测流失(0/1)',
            model_name          VARCHAR(64) COMMENT '预测模型',
            risk_level          VARCHAR(16) COMMENT '风险等级：低/中/高',
            update_time         DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-用户流失预测结果'
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS ads_churn_metrics (
            model_name          VARCHAR(64) PRIMARY KEY COMMENT '模型名',
            auc                 DECIMAL(8,4) COMMENT 'AUC(5-fold CV)',
            auc_std             DECIMAL(8,4) COMMENT 'AUC 标准差',
            auc_holdout         DECIMAL(8,4) COMMENT 'AUC(测试集)',
            pr_auc              DECIMAL(8,4) COMMENT 'PR-AUC',
            f1                  DECIMAL(8,4) COMMENT 'F1',
            accuracy            DECIMAL(8,4) COMMENT 'Accuracy',
            support_pos         INT COMMENT '正样本数',
            support_neg         INT COMMENT '负样本数'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-用户流失模型指标'
    """)


def _load_features() -> pd.DataFrame:
    """从 dws_user_daily + ads_user_rfm + ads_user_portrait + dwd_user_info 拼特征。"""
    logger.info("\n[Step7-User Churn] 加载用户特征...")

    sql = """
        SELECT
            u.user_id,
            u.comment_count_total,
            u.reply_count_total,
            u.like_received_total,
            u.activity_score,
            u.interaction_score,
            u.diversity_score,
            u.user_value,
            u.avg_sentiment,
            u.preferred_topic_id,
            u.active_period,
            u.sentiment_type,
            u.cluster_label,
            i.register_time,
            d.active_days,
            d.avg_comment_length,
            r.recency_days,
            r.frequency,
            r.monetary,
            r.r_score,
            r.f_score,
            r.m_score,
            r.rfm_total,
            r.rfm_cluster
        FROM ads_user_portrait u
        LEFT JOIN dwd_user_info i ON u.user_id = i.user_id
        LEFT JOIN (
            SELECT user_id,
                   COUNT(DISTINCT dt) AS active_days,
                   AVG(avg_comment_length) AS avg_comment_length
            FROM dws_user_daily
            GROUP BY user_id
        ) d ON u.user_id = d.user_id
        LEFT JOIN ads_user_rfm r ON u.user_id = r.user_id
    """
    df = read_sql(sql)
    if df.empty:
        raise ValueError("ads_user_portrait 为空，请先运行 step5")

    # register_days: 用数据最新评论日期近似"今天"
    df["register_time"] = pd.to_datetime(df["register_time"], errors="coerce")
    ref_date = df["register_time"].max()
    df["register_days"] = (ref_date - df["register_time"]).dt.days
    df["register_days"] = df["register_days"].fillna(df["register_days"].median()).clip(lower=1).astype(int)

    # active_period_encoded
    period_map = {"凌晨": 0, "上午": 1, "下午": 2, "晚上": 3, "未知": 1}
    df["active_period_encoded"] = df["active_period"].map(period_map).fillna(1).astype(int)

    df["sentiment_type_encoded"] = df["sentiment_type"].map(
        {"正面": 2, "中性": 1, "负面": 0}
    ).fillna(1).astype(int)

    for col in ["recency_days", "frequency", "monetary",
                "r_score", "f_score", "m_score", "rfm_total", "rfm_cluster",
                "active_days", "avg_comment_length", "preferred_topic_id"]:
        if col in df.columns:
            df[col] = df[col].fillna(df[col].median() if df[col].notna().any() else 0)

    # ---- 交叉/比率特征（不含 recency_days，无泄露） ----
    df["comment_per_active_day"] = df["comment_count_total"] / (df["active_days"] + 1)
    df["like_per_active_day"] = df["like_received_total"] / (df["active_days"] + 1)
    df["engagement_ratio"] = (df["like_received_total"] + df["reply_count_total"]) / (df["comment_count_total"] + 1)
    df["activity_consistency"] = df["active_days"] / (df["register_days"] + 1)
    df["reply_to_comment_ratio"] = df["reply_count_total"] / (df["comment_count_total"] + 1)
    df["like_to_reply_ratio"] = df["like_received_total"] / (df["reply_count_total"] + 1)
    logger.info("  [特征工程] 新增 6 个交叉/比率特征")

    # 标签：>90 天未评论 = 流失
    df["label"] = (df["recency_days"] > CHURN_DAYS_THRESHOLD).astype(int)

    pos_count = int(df["label"].sum())
    neg_count = int(len(df) - pos_count)
    pos_pct = pos_count / len(df) * 100
    logger.info(f"  样本分布: 流失={pos_count} ({pos_pct:.1f}%), 活跃={neg_count} ({100-pos_pct:.1f}%)")
    return df


def get_feature_columns(df: pd.DataFrame) -> list:
    """特征列（严格排除标签生成链路 + 标识 + 整数标签）。"""
    exclude = {
        "user_id", "sentiment_type", "label",
        # 标签链路：recency_days → r_score → rfm_total 都参与 label 生成
        "recency_days",
        "r_score",
        "rfm_total",
        # 整数聚类标签可能与 label 强相关（如果聚类用了 R）
        "rfm_cluster",
        "cluster_label",
    }
    return [c for c in df.columns if c not in exclude and df[c].dtype in [np.float64, np.int64, int, float]]


def _tune_xgboost(X_train, y_train, cv, scale_pos):
    """RandomizedSearchCV 调优 XGBoost 超参数。"""
    param_grid = {
        "max_depth": [3, 4, 5, 6, 7, 8],
        "learning_rate": [0.01, 0.05, 0.1, 0.15, 0.2],
        "n_estimators": [50, 100, 200, 300],
        "subsample": [0.6, 0.7, 0.8, 0.9, 1.0],
        "colsample_bytree": [0.6, 0.7, 0.8, 0.9, 1.0],
        "min_child_weight": [1, 3, 5, 7],
        "gamma": [0, 0.1, 0.2, 0.3],
    }
    base = xgb.XGBClassifier(
        objective="binary:logistic",
        eval_metric="logloss",
        scale_pos_weight=scale_pos,
        random_state=RANDOM_STATE, n_jobs=-1,
    )
    search = RandomizedSearchCV(
        base, param_grid, n_iter=30, cv=cv,
        scoring="roc_auc", n_jobs=-1,
        random_state=RANDOM_STATE, verbose=0,
    )
    search.fit(X_train, y_train)
    logger.info(f"  [XGBoost 调参] 最优参数: {search.best_params_}")
    logger.info(f"  [XGBoost 调参] 调参 CV AUC={search.best_score_:.4f}")
    return search.best_estimator_, search.best_params_


def _train_models(df: pd.DataFrame):
    feature_cols = get_feature_columns(df)
    logger.info(f"  使用 {len(feature_cols)} 个特征: {feature_cols}")

    X = df[feature_cols]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.3, random_state=RANDOM_STATE, stratify=y
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    pos_count = int(y_train.sum())
    neg_count = int(len(y_train) - pos_count)
    scale_pos = neg_count / max(pos_count, 1)
    logger.info(f"  训练集类别: 正={pos_count}, 负={neg_count}, scale_pos_weight={scale_pos:.2f}")

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)
    metrics_rows = []
    models = {}

    # Logistic Regression
    lr = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE)
    lr.fit(X_train_scaled, y_train)
    lr_pred = lr.predict(X_test_scaled)
    lr_proba = lr.predict_proba(X_test_scaled)[:, 1]
    lr_auc_holdout = roc_auc_score(y_test, lr_proba)
    lr_f1 = f1_score(y_test, lr_pred)
    lr_acc = accuracy_score(y_test, lr_pred)
    lr_prauc = average_precision_score(y_test, lr_proba)
    lr_cv_auc = cross_val_score(lr, X_train_scaled, y_train, cv=cv, scoring="roc_auc")
    logger.info(f"  [LogisticRegression] AUC={lr_cv_auc.mean():.4f}±{lr_cv_auc.std():.4f} (5-fold), "
                f"holdout={lr_auc_holdout:.4f}, F1={lr_f1:.4f}, Acc={lr_acc:.4f}")
    metrics_rows.append({
        "model_name": "LogisticRegression",
        "auc": float(lr_cv_auc.mean()), "auc_std": float(lr_cv_auc.std()),
        "auc_holdout": float(lr_auc_holdout), "pr_auc": float(lr_prauc),
        "f1": float(lr_f1), "accuracy": float(lr_acc),
        "support_pos": int(y_test.sum()), "support_neg": int(len(y_test) - y_test.sum()),
    })
    models["LogisticRegression"] = (lr, lr_cv_auc.mean(), lr_proba, scaler)

    # Random Forest
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=6, n_jobs=-1,
        class_weight="balanced", random_state=RANDOM_STATE
    )
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_proba = rf.predict_proba(X_test)[:, 1]
    rf_auc_holdout = roc_auc_score(y_test, rf_proba)
    rf_f1 = f1_score(y_test, rf_pred)
    rf_acc = accuracy_score(y_test, rf_pred)
    rf_prauc = average_precision_score(y_test, rf_proba)
    rf_cv_auc = cross_val_score(rf, X_train, y_train, cv=cv, scoring="roc_auc")
    logger.info(f"  [RandomForest]        AUC={rf_cv_auc.mean():.4f}±{rf_cv_auc.std():.4f} (5-fold), "
                f"holdout={rf_auc_holdout:.4f}, F1={rf_f1:.4f}, Acc={rf_acc:.4f}")
    metrics_rows.append({
        "model_name": "RandomForest",
        "auc": float(rf_cv_auc.mean()), "auc_std": float(rf_cv_auc.std()),
        "auc_holdout": float(rf_auc_holdout), "pr_auc": float(rf_prauc),
        "f1": float(rf_f1), "accuracy": float(rf_acc),
        "support_pos": int(y_test.sum()), "support_neg": int(len(y_test) - y_test.sum()),
    })
    models["RandomForest"] = (rf, rf_cv_auc.mean(), rf_proba, None)

    # XGBoost (默认参数, 作为调参前基线)
    xgb_default = xgb.XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        scale_pos_weight=scale_pos,
        random_state=RANDOM_STATE, n_jobs=-1, eval_metric="logloss"
    )
    xgb_default_cv = cross_val_score(xgb_default, X_train, y_train, cv=cv, scoring="roc_auc")
    logger.info(f"  [XGBoost 默认参数]     CV AUC={xgb_default_cv.mean():.4f}±{xgb_default_cv.std():.4f}")

    # XGBoost (RandomizedSearchCV 调参后)
    xgb_model, xgb_best_params = _tune_xgboost(X_train, y_train, cv, scale_pos)
    xgb_pred = xgb_model.predict(X_test)
    xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
    xgb_auc_holdout = roc_auc_score(y_test, xgb_proba)
    xgb_f1 = f1_score(y_test, xgb_pred)
    xgb_acc = accuracy_score(y_test, xgb_pred)
    xgb_prauc = average_precision_score(y_test, xgb_proba)
    xgb_cv_auc = cross_val_score(xgb_model, X_train, y_train, cv=cv, scoring="roc_auc")
    logger.info(f"  [XGBoost 调参后]       AUC={xgb_cv_auc.mean():.4f}±{xgb_cv_auc.std():.4f} (5-fold), "
                f"holdout={xgb_auc_holdout:.4f}, F1={xgb_f1:.4f}, Acc={xgb_acc:.4f}")
    logger.info(f"  [XGBoost 提升]         {xgb_default_cv.mean():.4f} → {xgb_cv_auc.mean():.4f} "
                f"(+{xgb_cv_auc.mean() - xgb_default_cv.mean():.4f})")
    metrics_rows.append({
        "model_name": "XGBoost",
        "auc": float(xgb_cv_auc.mean()), "auc_std": float(xgb_cv_auc.std()),
        "auc_holdout": float(xgb_auc_holdout), "pr_auc": float(xgb_prauc),
        "f1": float(xgb_f1), "accuracy": float(xgb_acc),
        "support_pos": int(y_test.sum()), "support_neg": int(len(y_test) - y_test.sum()),
    })
    models["XGBoost"] = (xgb_model, xgb_cv_auc.mean(), xgb_proba, None)

    best_name = max(models, key=lambda k: models[k][1])
    logger.info(f"  [最优模型] {best_name} (5-fold CV AUC={models[best_name][1]:.4f})")

    return df, pd.DataFrame(metrics_rows), best_name, models, feature_cols


def _save_results(df: pd.DataFrame, metrics: pd.DataFrame, best_name: str, models: dict, feature_cols: list):
    """保存预测结果到 ADS 层。"""
    best_model, best_auc, best_proba, best_scaler = models[best_name]
    test_idx = df.index  # 完整数据集

    # 用最优模型对全量用户预测（基于全数据）
    feature_cols_local = feature_cols
    X_full = df[feature_cols_local]

    if best_name == "LogisticRegression":
        # LR 需要 scaler
        scaler = best_scaler
        proba_full = best_model.predict_proba(scaler.transform(X_full))[:, 1]
        pred_full = best_model.predict(scaler.transform(X_full))
    else:
        proba_full = best_model.predict_proba(X_full)[:, 1]
        pred_full = best_model.predict(X_full)

    result = pd.DataFrame({
        "user_id": df["user_id"].values,
        "recency_days": df["recency_days"].astype(int).values,
        "actual_label": df["label"].astype(int).values,
        "churn_prob": np.round(proba_full, 6),
        "is_churn_predicted": pred_full.astype(int),
        "model_name": best_name,
    })

    # 风险等级：低(<0.3) / 中(0.3-0.7) / 高(>0.7)
    def _risk(p):
        if p < 0.3:
            return "低"
        elif p < 0.7:
            return "中"
        return "高"
    result["risk_level"] = result["churn_prob"].apply(_risk)

    write_table(result, "ads_churn_predict", if_exists="replace")
    write_table(metrics, "ads_churn_metrics", if_exists="replace")
    logger.info(f"  [OK] ads_churn_predict ({len(result)} 行) / ads_churn_metrics 已写入")

    # 模型文件
    import pickle
    os.makedirs(MODEL_DIR, exist_ok=True)
    with open(os.path.join(MODEL_DIR, "best_churn_model.pkl"), "wb") as f:
        pickle.dump(best_model, f)
    with open(os.path.join(MODEL_DIR, "churn_features.yaml"), "w", encoding="utf-8") as f:
        f.write(f"# 用户流失预测特征清单（共 {len(feature_cols_local)} 个）\n\n")
        for i, c in enumerate(feature_cols_local, 1):
            f.write(f"{i}. {c}\n")

    # 汇总
    logger.info("\n  ═══ 流失预测结果汇总 ═══")
    risk_dist = result["risk_level"].value_counts()
    for level in ["低", "中", "高"]:
        cnt = risk_dist.get(level, 0)
        pct = cnt / len(result) * 100
        logger.info(f"  {level}风险用户: {cnt:6d} ({pct:5.1f}%)")


def run():
    print("\n" + "=" * 60)
    print("Step7 用户流失预测")
    print("=" * 60)

    _create_tables()
    df = _load_features()
    df, metrics, best_name, models, feature_cols = _train_models(df)
    _save_results(df, metrics, best_name, models, feature_cols)

    print("\n" + "=" * 60)
    print("用户流失预测完成")
    print("=" * 60)


if __name__ == "__main__":
    run()
