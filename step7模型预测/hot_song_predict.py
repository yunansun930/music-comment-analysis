"""
Step7 模型预测 - 爆款歌曲预测

训练 LR / RF / XGBoost / LightGBM(可选) 模型，按 AUC 选最优。
保存 model.pkl / metrics.json / features.yaml，写入 ADS 表。
"""
import json
import logging
import os

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score, average_precision_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler

import xgboost as xgb
from config import HOT_SONG_CONFIG, MODEL_DIR
from db_helper import write_table, read_sql
from features import build_features

logger = logging.getLogger("step7.predict")


def get_feature_columns(df: pd.DataFrame) -> list:
    """获取模型输入特征列。

    严格排除参与标签生成链路的所有字段，避免特征泄露：
    - label/label_*: 直接是标签
    - composite_heat: 直接生成标签
    - *_norm: 直接构成 composite_heat
    - total_comment_count/total_like_total/positive_ratio: 是 *_norm 的原值
    - like_per_comment/reply_per_comment: 由 total_*_count 派生，可反推原值
    - avg_heat_score/max_heat_score: dws_song_daily.heat_score 与 composite_heat 同源（都由评论数+获赞数+回复数加权）
    """
    exclude = [
        "song_id", "artist_id", "release_time",
        "label", "label_comment_hot", "label_interact_hot", "label_longtail_hot",
        "composite_heat",
        # *_norm 直接参与 composite_heat 计算
        "total_comment_count_norm", "total_like_total_norm", "positive_ratio_norm",
        # 这三个原值通过 _norm 间接参与 composite_heat 计算
        "total_comment_count", "total_like_total", "positive_ratio",
        # 比率值可由原值反推，间接泄露
        "like_per_comment", "reply_per_comment",
        # heat_score 与 composite_heat 同源（都是评论衍生指标的加权），存在严重泄露
        "avg_heat_score", "max_heat_score",
    ]
    return [c for c in df.columns if c not in exclude]


def _try_lightgbm():
    try:
        import lightgbm as lgb
        return lgb
    except ImportError:
        logger.warning("  LightGBM 未安装，跳过该基线模型。可执行: pip install lightgbm")
        return None


def _calc_shap(model, X: pd.DataFrame, feature_cols: list) -> pd.DataFrame:
    try:
        import shap
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        mean_abs = np.abs(shap_values).mean(axis=0)
        return pd.DataFrame({
            "feature": feature_cols,
            "importance": mean_abs,
        }).sort_values("importance", ascending=False)
    except Exception as e:
        logger.warning("  SHAP 计算失败，回退到模型原生重要性: %s", e)
        if hasattr(model, "feature_importances_"):
            return pd.DataFrame({
                "feature": feature_cols,
                "importance": model.feature_importances_,
            }).sort_values("importance", ascending=False)
        return pd.DataFrame({"feature": feature_cols, "importance": 0.0})


def _bootstrap_ci(y_true, y_proba, metric_fn, n_boot=500, ci=0.95, seed=42):
    """Bootstrap 计算指标的置信区间。"""
    rng = np.random.RandomState(seed)
    y_true = np.array(y_true)
    y_proba = np.array(y_proba)
    n = len(y_true)
    boots = []
    for _ in range(n_boot):
        idx = rng.randint(0, n, n)
        if len(np.unique(y_true[idx])) < 2:
            continue
        boots.append(metric_fn(y_true[idx], y_proba[idx]))
    if not boots:
        return 0.0, 0.0
    alpha = (1 - ci) / 2
    lo, hi = np.percentile(boots, [alpha * 100, (1 - alpha) * 100])
    return float(lo), float(hi)


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
        eval_metric="auc",
        scale_pos_weight=scale_pos,
        random_state=HOT_SONG_CONFIG["random_state"],
        n_jobs=-1,
        use_label_encoder=False,
    )
    search = RandomizedSearchCV(
        base, param_grid, n_iter=30, cv=cv,
        scoring="roc_auc", n_jobs=-1,
        random_state=HOT_SONG_CONFIG["random_state"], verbose=0,
    )
    search.fit(X_train, y_train)
    logger.info("  [XGBoost 调参] 最优参数: %s", search.best_params_)
    logger.info("  [XGBoost 调参] 调参 CV AUC=%.4f", search.best_score_)
    return search.best_estimator_, search.best_params_, search.best_score_


def train_models(df: pd.DataFrame):
    feature_cols = get_feature_columns(df)
    X = df[feature_cols]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=HOT_SONG_CONFIG["test_size"],
        random_state=HOT_SONG_CONFIG["random_state"],
        stratify=y,
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    pos_count = int(y_train.sum())
    neg_count = int(len(y_train) - pos_count)
    scale_pos = neg_count / max(pos_count, 1)
    logger.info("  [类别不平衡] 正样本=%d, 负样本=%d, scale_pos_weight=%.2f", pos_count, neg_count, scale_pos)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=HOT_SONG_CONFIG["random_state"])

    metrics_rows = []
    models = {}

    # --- Logistic Regression ---
    lr = LogisticRegression(**HOT_SONG_CONFIG["lr_params"], class_weight="balanced")
    lr.fit(X_train_scaled, y_train)
    lr_pred = lr.predict(X_test_scaled)
    lr_proba = lr.predict_proba(X_test_scaled)[:, 1]
    lr_auc = roc_auc_score(y_test, lr_proba)
    lr_f1 = f1_score(y_test, lr_pred)
    lr_acc = accuracy_score(y_test, lr_pred)
    lr_prauc = average_precision_score(y_test, lr_proba)
    lr_cv_auc = cross_val_score(lr, X_train_scaled, y_train, cv=cv, scoring="roc_auc")
    lr_ci_lo, lr_ci_hi = _bootstrap_ci(y_test, lr_proba, roc_auc_score)
    logger.info("  [LogisticRegression] AUC=%.4f±%.4f (5-fold), PR-AUC=%.4f, 95%%CI=[%.4f,%.4f]",
                lr_cv_auc.mean(), lr_cv_auc.std(), lr_prauc, lr_ci_lo, lr_ci_hi)
    metrics_rows.append({
        "model_name": "LogisticRegression",
        "auc": float(lr_cv_auc.mean()), "auc_std": float(lr_cv_auc.std()),
        "auc_holdout": float(lr_auc), "pr_auc": float(lr_prauc),
        "f1": float(lr_f1), "accuracy": float(lr_acc),
        "auc_ci_lower": lr_ci_lo, "auc_ci_upper": lr_ci_hi,
    })
    models["LogisticRegression"] = (lr, lr_cv_auc.mean())

    # --- Random Forest ---
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=6,
        random_state=HOT_SONG_CONFIG["random_state"], n_jobs=-1,
        class_weight="balanced",
    )
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_proba = rf.predict_proba(X_test)[:, 1]
    rf_auc = roc_auc_score(y_test, rf_proba)
    rf_f1 = f1_score(y_test, rf_pred)
    rf_acc = accuracy_score(y_test, rf_pred)
    rf_prauc = average_precision_score(y_test, rf_proba)
    rf_cv_auc = cross_val_score(rf, X_train, y_train, cv=cv, scoring="roc_auc")
    rf_ci_lo, rf_ci_hi = _bootstrap_ci(y_test, rf_proba, roc_auc_score)
    logger.info("  [RandomForest]        AUC=%.4f±%.4f (5-fold), PR-AUC=%.4f, 95%%CI=[%.4f,%.4f]",
                rf_cv_auc.mean(), rf_cv_auc.std(), rf_prauc, rf_ci_lo, rf_ci_hi)
    metrics_rows.append({
        "model_name": "RandomForest",
        "auc": float(rf_cv_auc.mean()), "auc_std": float(rf_cv_auc.std()),
        "auc_holdout": float(rf_auc), "pr_auc": float(rf_prauc),
        "f1": float(rf_f1), "accuracy": float(rf_acc),
        "auc_ci_lower": rf_ci_lo, "auc_ci_upper": rf_ci_hi,
    })
    models["RandomForest"] = (rf, rf_cv_auc.mean())

    # --- XGBoost (默认参数, 作为调参前基线) ---
    xgb_default = xgb.XGBClassifier(
        **HOT_SONG_CONFIG["xgb_params"], scale_pos_weight=scale_pos
    )
    xgb_default_cv = cross_val_score(xgb_default, X_train, y_train, cv=cv, scoring="roc_auc")
    logger.info("  [XGBoost 默认参数]     CV AUC=%.4f±%.4f", xgb_default_cv.mean(), xgb_default_cv.std())

    # --- XGBoost (RandomizedSearchCV 调参后) ---
    xgb_model, xgb_best_params, xgb_tuned_cv = _tune_xgboost(X_train, y_train, cv, scale_pos)
    xgb_pred = xgb_model.predict(X_test)
    xgb_proba = xgb_model.predict_proba(X_test)[:, 1]
    xgb_auc = roc_auc_score(y_test, xgb_proba)
    xgb_f1 = f1_score(y_test, xgb_pred)
    xgb_acc = accuracy_score(y_test, xgb_pred)
    xgb_prauc = average_precision_score(y_test, xgb_proba)
    xgb_cv_auc = cross_val_score(xgb_model, X_train, y_train, cv=cv, scoring="roc_auc")
    xgb_ci_lo, xgb_ci_hi = _bootstrap_ci(y_test, xgb_proba, roc_auc_score)
    logger.info("  [XGBoost 调参后]       AUC=%.4f±%.4f (5-fold), PR-AUC=%.4f, 95%%CI=[%.4f,%.4f]",
                xgb_cv_auc.mean(), xgb_cv_auc.std(), xgb_prauc, xgb_ci_lo, xgb_ci_hi)
    logger.info("  [XGBoost 提升]         %.4f → %.4f (+%.4f)",
                xgb_default_cv.mean(), xgb_cv_auc.mean(), xgb_cv_auc.mean() - xgb_default_cv.mean())
    metrics_rows.append({
        "model_name": "XGBoost",
        "auc": float(xgb_cv_auc.mean()), "auc_std": float(xgb_cv_auc.std()),
        "auc_holdout": float(xgb_auc), "pr_auc": float(xgb_prauc),
        "f1": float(xgb_f1), "accuracy": float(xgb_acc),
        "auc_ci_lower": xgb_ci_lo, "auc_ci_upper": xgb_ci_hi,
    })
    models["XGBoost"] = (xgb_model, xgb_cv_auc.mean())

    # --- LightGBM (可选) ---
    lgb = _try_lightgbm()
    if lgb is not None:
        lgb_model = lgb.LGBMClassifier(
            n_estimators=200, max_depth=6, learning_rate=0.1,
            random_state=HOT_SONG_CONFIG["random_state"], n_jobs=-1, verbose=-1,
            class_weight="balanced",
        )
        lgb_model.fit(X_train, y_train)
        lgb_pred = lgb_model.predict(X_test)
        lgb_proba = lgb_model.predict_proba(X_test)[:, 1]
        lgb_auc = roc_auc_score(y_test, lgb_proba)
        lgb_f1 = f1_score(y_test, lgb_pred)
        lgb_acc = accuracy_score(y_test, lgb_pred)
        lgb_prauc = average_precision_score(y_test, lgb_proba)
        lgb_cv_auc = cross_val_score(lgb_model, X_train, y_train, cv=cv, scoring="roc_auc")
        lgb_ci_lo, lgb_ci_hi = _bootstrap_ci(y_test, lgb_proba, roc_auc_score)
        logger.info("  [LightGBM]           AUC=%.4f±%.4f (5-fold), PR-AUC=%.4f, 95%%CI=[%.4f,%.4f]",
                    lgb_cv_auc.mean(), lgb_cv_auc.std(), lgb_prauc, lgb_ci_lo, lgb_ci_hi)
        metrics_rows.append({
            "model_name": "LightGBM",
            "auc": float(lgb_cv_auc.mean()), "auc_std": float(lgb_cv_auc.std()),
            "auc_holdout": float(lgb_auc), "pr_auc": float(lgb_prauc),
            "f1": float(lgb_f1), "accuracy": float(lgb_acc),
            "auc_ci_lower": lgb_ci_lo, "auc_ci_upper": lgb_ci_hi,
        })
        models["LightGBM"] = (lgb_model, lgb_cv_auc.mean())

    best_name, (best_model, best_auc) = max(models.items(), key=lambda kv: kv[1][1])
    logger.info("  [OK] 最优模型: %s (5-fold CV AUC=%.4f)", best_name, best_auc)

    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(lr, os.path.join(MODEL_DIR, "logistic_regression_hot_song_model.pkl"))
    joblib.dump(rf, os.path.join(MODEL_DIR, "random_forest_hot_song_model.pkl"))
    joblib.dump(xgb_model, os.path.join(MODEL_DIR, "xgboost_hot_song_model.pkl"))
    joblib.dump(scaler, os.path.join(MODEL_DIR, "scaler.pkl"))
    joblib.dump(feature_cols, os.path.join(MODEL_DIR, "feature_cols.pkl"))
    joblib.dump(best_model, os.path.join(MODEL_DIR, "best_hot_song_model.pkl"))

    _save_model_artifacts(
        feature_cols=feature_cols,
        best_name=best_name,
        best_auc=best_auc,
        metrics_rows=metrics_rows,
        xgb_params=xgb_best_params,
    )

    logger.info("  [OK] 模型产物已保存到 %s/", MODEL_DIR)

    if best_name == "LogisticRegression":
        df["hot_prob"] = best_model.predict_proba(scaler.transform(X))[:, 1]
    else:
        df["hot_prob"] = best_model.predict_proba(X)[:, 1]
    df["is_hot_predicted"] = (df["hot_prob"] >= 0.5).astype(int)

    metrics = pd.DataFrame(metrics_rows)

    shap_model = best_model if best_name in {"XGBoost", "RandomForest", "LightGBM"} else xgb_model
    importance = _calc_shap(shap_model, X_test, feature_cols)

    return df, metrics, importance


def _save_model_artifacts(feature_cols, best_name, best_auc, metrics_rows, xgb_params):
    yaml_path = os.path.join(MODEL_DIR, "features.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write("# 爆款预测模型特征清单（基于真实评论数据）\n")
        f.write(f"# 共 {len(feature_cols)} 个特征\n\n")
        for i, c in enumerate(feature_cols, 1):
            f.write(f"{i}. {c}\n")

    metrics_path = os.path.join(MODEL_DIR, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({
            "best_model": best_name,
            "best_auc": float(best_auc),
            "all_metrics": metrics_rows,
            "xgb_params": xgb_params,
        }, f, ensure_ascii=False, indent=2)

    card_path = os.path.join(MODEL_DIR, "model_card.json")
    best_metrics = next((m for m in metrics_rows if m["model_name"] == best_name), {})
    with open(card_path, "w", encoding="utf-8") as f:
        json.dump({
            "task": "爆款歌曲二分类预测（基于真实评论数据）",
            "label_definition": "复合热度(评论数+获赞数+正面情感加权) Top 10%",
            "best_model": best_name,
            "best_auc_cv_mean": float(best_auc),
            "best_auc_cv_std": float(best_metrics.get("auc_std", 0)),
            "best_auc_holdout": float(best_metrics.get("auc_holdout", 0)),
            "best_pr_auc": float(best_metrics.get("pr_auc", 0)),
            "auc_ci_95": [float(best_metrics.get("auc_ci_lower", 0)), float(best_metrics.get("auc_ci_upper", 0))],
            "cv_method": "StratifiedKFold(n_splits=5, shuffle=True)",
            "ci_method": "Bootstrap(n=500)",
            "imbalance_handling": "class_weight=balanced / scale_pos_weight",
            "hyperparameter_tuning": "RandomizedSearchCV(n_iter=30, 7 params, scoring=roc_auc)",
            "feature_count": len(feature_cols),
            "metrics_file": "metrics.json",
            "features_file": "features.yaml",
            "model_file": "best_hot_song_model.pkl",
            "scaler_file": "scaler.pkl",
            "note": "基于真实评论指标：评论数、回复数、获赞数、热度分、情感、主题等",
        }, f, ensure_ascii=False, indent=2)


def save_hot_predict_results(df: pd.DataFrame, metrics: pd.DataFrame, importance: pd.DataFrame):
    """保存爆款预测结果到 ADS 层。"""
    result = df[[
        "song_id", "total_comment_count", "label",
        "hot_prob", "is_hot_predicted",
    ]].copy()
    result.columns = [
        "song_id", "actual_comment_count", "actual_label",
        "hot_prob", "is_hot_predicted",
    ]
    result["update_time"] = pd.Timestamp.now()

    write_table(result, "ads_hot_predict", if_exists="replace")
    write_table(metrics, "ads_model_metrics", if_exists="replace")
    write_table(importance, "ads_feature_importance", if_exists="replace")
    logger.info("  [OK] ads_hot_predict / ads_model_metrics / ads_feature_importance 已写入")
