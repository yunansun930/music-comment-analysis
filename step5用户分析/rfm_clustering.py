"""
Step5 用户分析 - RFM 分群

RFM 模型基于用户评论行为的三维特征：
  R (Recency)   - 最近一次评论距今天数（越小越好，反向打分）
  F (Frequency) - 评论频率（评论总数 / 活跃天数）
  M (Monetary)  - 评论质量（获赞总数，作为内容贡献价值代理）

与 K-means 8 维聚类并存：原 cluster_label/user_type 保留，新增 rfm_label。
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from config import RANDOM_STATE
from db_helper import read_table, read_sql, to_sql_replace, execute
from user_features import build_user_features


def _compute_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """计算 R/F/M 原始值。"""
    print("\n  [RFM] 计算 R/F/M 原始值...")

    # R: 最近一次评论距今天数（从 dwd_comment_detail 取最新 comment_time）
    try:
        recent = read_sql("""
            SELECT user_id, MAX(comment_time) AS last_comment_time
            FROM dwd_comment_detail
            GROUP BY user_id
        """)
        recent["last_comment_time"] = pd.to_datetime(recent["last_comment_time"])
        # 用数据中最大日期作为"今天"，避免与采集时间差导致 R 全部很大
        ref_date = recent["last_comment_time"].max()
        recent["recency_days"] = (ref_date - recent["last_comment_time"]).dt.days
        df = df.merge(recent[["user_id", "recency_days"]], on="user_id", how="left")
        df["recency_days"] = df["recency_days"].fillna(df["recency_days"].median())
    except Exception as e:
        print(f"  [Warning] R 计算失败: {e}，使用 active_days 反向近似")
        df["recency_days"] = df["active_days"].max() - df["active_days"]

    # F: 评论频率 = 评论总数 / 活跃天数
    df["frequency"] = df["total_comment_count"] / df["active_days"].clip(lower=1)

    # M: 评论质量 = 获赞总数
    df["monetary"] = df["total_like_received"]

    print(f"    R 范围: {df['recency_days'].min():.0f} ~ {df['recency_days'].max():.0f} 天")
    print(f"    F 范围: {df['frequency'].min():.2f} ~ {df['frequency'].max():.2f}")
    print(f"    M 范围: {df['monetary'].min():.0f} ~ {df['monetary'].max():.0f}")
    return df


def _score_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """五分位打分（1-5）。

    R 反向：值越小（最近评论越近）分数越高
    F/M 正向：值越大分数越高
    """
    print("\n  [RFM] 五分位打分...")

    def _qcut_reverse(s):
        """反向五分位：值越小分数越高"""
        try:
            return pd.qcut(s, 5, labels=[5, 4, 3, 2, 1], duplicates="drop").astype(int)
        except Exception:
            # 数据分布不均时降级到等距
            return pd.cut(s.rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)

    def _qcut_normal(s):
        """正向五分位：值越大分数越高"""
        try:
            return pd.qcut(s, 5, labels=[1, 2, 3, 4, 5], duplicates="drop").astype(int)
        except Exception:
            return pd.cut(s.rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)

    df["r_score"] = _qcut_reverse(df["recency_days"])
    df["f_score"] = _qcut_normal(df["frequency"])
    df["m_score"] = _qcut_normal(df["monetary"])

    df["rfm_total"] = df["r_score"] + df["f_score"] + df["m_score"]

    print(f"    R_score 分布: {dict(df['r_score'].value_counts().sort_index())}")
    print(f"    F_score 分布: {dict(df['f_score'].value_counts().sort_index())}")
    print(f"    M_score 分布: {dict(df['m_score'].value_counts().sort_index())}")
    return df


def _cluster_rfm(df: pd.DataFrame, k: int = 4) -> pd.DataFrame:
    """K-means 聚类 R/F/M 三维。"""
    print(f"\n  [RFM] K-means 聚类 (k={k})...")

    X = df[["r_score", "f_score", "m_score"]].values
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 评估 k=2..6（采样 5000 避免 silhouette O(n²) 爆炸）
    sample_size = min(5000, len(X_scaled))
    print(f"    {'k':>3s} {'silhouette':>12s} (n={sample_size})")
    print("    " + "-" * 30)
    for kk in range(2, 7):
        km = KMeans(n_clusters=kk, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels, sample_size=sample_size, random_state=RANDOM_STATE)
        print(f"    {kk:3d} {sil:12.4f}")

    km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
    df["rfm_cluster"] = km.fit_predict(X_scaled)

    sil = silhouette_score(X_scaled, df["rfm_cluster"], sample_size=sample_size, random_state=RANDOM_STATE)
    print(f"    选定 k={k}, 轮廓系数={sil:.4f} (n={sample_size})")
    return df


def _label_rfm(df: pd.DataFrame) -> pd.DataFrame:
    """根据聚类中心打标签。

    规则：按 R+F+M 加权排序
    - 高价值用户 (VIP): R 高 + F 高 + M 高
    - 成长用户: R 高 / F 中
    - 沉默用户: R 低 + F 低
    - 流失风险用户: R 低 + M 中等（曾经活跃但最近沉默）
    """
    print("\n  [RFM] 簇标签分配...")

    centers = df.groupby("rfm_cluster")[["r_score", "f_score", "m_score"]].mean()
    # 加权排序：R 0.4 + F 0.3 + M 0.3
    centers["weighted"] = 0.4 * centers["r_score"] + 0.3 * centers["f_score"] + 0.3 * centers["m_score"]
    centers = centers.sort_values("weighted", ascending=False)

    print(f"    聚类中心（按加权降序）：")
    for idx, row in centers.iterrows():
        print(f"      cluster {idx}: R={row['r_score']:.2f} F={row['f_score']:.2f} M={row['m_score']:.2f} weighted={row['weighted']:.2f}")

    # 第一名高价值，最后一名流失风险，中间按 R 高低分成长/沉默
    sorted_clusters = centers.index.tolist()
    label_map = {}
    if len(sorted_clusters) == 4:
        label_map[sorted_clusters[0]] = "高价值用户"
        # 中间两个：按 R_score 高低区分成长 vs 沉默
        mid1, mid2 = sorted_clusters[1], sorted_clusters[2]
        if centers.loc[mid1, "r_score"] >= centers.loc[mid2, "r_score"]:
            label_map[mid1] = "成长用户"
            label_map[mid2] = "沉默用户"
        else:
            label_map[mid1] = "沉默用户"
            label_map[mid2] = "成长用户"
        label_map[sorted_clusters[3]] = "流失风险用户"
    else:
        # 通用兜底
        tier_names = ["高价值用户", "成长用户", "沉默用户", "流失风险用户"]
        for i, c in enumerate(sorted_clusters):
            label_map[c] = tier_names[min(i, len(tier_names) - 1)]

    df["rfm_label"] = df["rfm_cluster"].map(label_map)

    print("\n  [RFM 分群分布]")
    dist = df["rfm_label"].value_counts()
    for label, cnt in dist.items():
        pct = cnt / len(df) * 100
        print(f"    {label:8s}: {cnt:6d} 人 ({pct:5.2f}%)")
    return df


def _create_rfm_table():
    """创建 ads_user_rfm 表（独立存放 RFM 详情，与 ads_user_portrait 解耦）。"""
    execute("""
        CREATE TABLE IF NOT EXISTS ads_user_rfm (
            user_id         VARCHAR(32) PRIMARY KEY COMMENT '用户ID',
            recency_days    INT COMMENT '最近评论距今天数',
            frequency       DECIMAL(10,4) COMMENT '评论频率（评论总数/活跃天数）',
            monetary        INT COMMENT '评论质量（获赞总数）',
            r_score         INT COMMENT 'R 五分位打分(1-5)',
            f_score         INT COMMENT 'F 五分位打分(1-5)',
            m_score         INT COMMENT 'M 五分位打分(1-5)',
            rfm_total       INT COMMENT 'R+F+M 总分(3-15)',
            rfm_cluster     INT COMMENT 'K-means 簇号',
            rfm_label       VARCHAR(32) COMMENT 'RFM 标签：高价值/成长/沉默/流失风险',
            update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-用户 RFM 分群结果'
    """)


def run():
    print("\n[Step5.4] RFM 分群...")

    features_df = build_user_features()
    df = _compute_rfm(features_df)
    df = _score_rfm(df)
    df = _cluster_rfm(df, k=4)
    df = _label_rfm(df)

    _create_rfm_table()

    out = df[["user_id", "recency_days", "frequency", "monetary",
              "r_score", "f_score", "m_score", "rfm_total",
              "rfm_cluster", "rfm_label"]].copy()
    out["frequency"] = out["frequency"].round(4)
    to_sql_replace(out, "ads_user_rfm")

    # 同时把 rfm_label 回填到 ads_user_portrait（如果存在）
    try:
        portrait = read_table("ads_user_portrait")
        if not portrait.empty and "user_id" in portrait.columns:
            if "rfm_label" in portrait.columns:
                portrait = portrait.drop(columns=["rfm_label"])
            portrait = portrait.merge(out[["user_id", "rfm_label"]], on="user_id", how="left")
            to_sql_replace(portrait, "ads_user_portrait")
            print("[OK] ads_user_portrait 已补充 rfm_label 字段")
    except Exception as e:
        print(f"  [Warning] 回填 rfm_label 到 portrait 失败: {e}")

    print("[OK] RFM 分群完成，已写入 ads_user_rfm")
    return df
