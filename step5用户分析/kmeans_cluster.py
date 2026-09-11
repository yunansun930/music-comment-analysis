"""
Step5 用户分析 - K-means 用户聚类

根据用户评论行为特征进行 K-means 聚类，并给用户打标签。
聚类维度：评论频次、互动贡献、内容多样性、情感倾向、活跃时段。

评估体系：肘部法则选 k、轮廓系数验证、ANOVA 检验簇间差异。
"""

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score, calinski_harabasz_score
from sklearn.preprocessing import StandardScaler

from config import N_CLUSTERS, RANDOM_STATE
from db_helper import read_table, to_sql_replace, execute
from user_features import build_user_features, get_cluster_features


CLUSTER_FEATURES = [
    "total_comment_count", "total_reply_count", "total_like_received",
    "active_days", "avg_daily_comment", "total_active_song_num",
    "activity_score", "interaction_score", "diversity_score", "user_value",
    "avg_sentiment", "active_period_encoded",
]


def assign_user_types(df: pd.DataFrame, cluster_centers: np.ndarray, labels: np.ndarray) -> pd.DataFrame:
    """
    根据聚类中心特征给用户打标签。
    规则：
    - 核心粉丝：互动贡献 + 多样性 + 情感投入最高
    - 内容消费者：评论量大但互动偏低
    - 轻度用户：各项指标都低
    """
    df = df.copy()
    df["cluster_label"] = labels

    centers_df = pd.DataFrame(cluster_centers, columns=CLUSTER_FEATURES)

    centers_df["rank_score"] = (
        0.3 * centers_df["interaction_score"]
        + 0.2 * centers_df["diversity_score"]
        + 0.2 * centers_df["activity_score"]
        + 0.15 * centers_df["avg_sentiment"]
        + 0.15 * np.log1p(centers_df["total_comment_count"]) / np.log1p(max(centers_df["total_comment_count"].max(), 1))
    )

    sorted_idx = centers_df["rank_score"].sort_values(ascending=False).index.tolist()
    if len(sorted_idx) == 3:
        label_map = {
            sorted_idx[0]: "核心粉丝",
            sorted_idx[1]: "内容消费者",
            sorted_idx[2]: "轻度用户",
        }
    elif len(sorted_idx) == 2:
        label_map = {
            sorted_idx[0]: "核心粉丝",
            sorted_idx[1]: "轻度用户",
        }
    else:
        tier_names = ["核心粉丝", "活跃用户", "内容消费者", "边缘用户", "沉默用户"]
        label_map = {sorted_idx[i]: tier_names[min(i, len(tier_names)-1)] for i in range(len(sorted_idx))}

    df["user_type"] = df["cluster_label"].map(label_map)

    print("\n  [聚类中心特征]")
    for idx in sorted_idx:
        row = centers_df.loc[idx]
        print(f"    {label_map[idx]:8s}: "
              f"评论={row['total_comment_count']:8.1f}, "
              f"回复={row['total_reply_count']:6.1f}, "
              f"获赞={row['total_like_received']:7.1f}, "
              f"活跃天数={row['active_days']:5.1f}, "
              f"情感={row['avg_sentiment']:.3f}, "
              f"价值分={row['user_value']:.4f}")

    return df


def evaluate_k_values(X_scaled, k_range=range(2, 9)):
    """
    肘部法则 + 轮廓系数 + Calinski-Harabasz 指数选择最优 k 值。

    注：silhouette 复杂度 O(n²)，对 15 万+ 样本会爆，强制 sample_size=5000 采样。
    """
    print("\n  [聚类评估] k 值选择...")
    n_samples = X_scaled.shape[0]
    sil_sample = min(5000, n_samples)
    print(f"  {'k':>3s} {'inertia':>12s} {'silhouette':>12s} {'CH_index':>12s}")
    print("  " + "-" * 45)

    results = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=10)
        labels = km.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels, sample_size=sil_sample, random_state=RANDOM_STATE)
        ch = calinski_harabasz_score(X_scaled, labels)
        results.append({"k": k, "inertia": km.inertia_, "silhouette": sil, "ch_index": ch})
        print(f"  {k:3d} {km.inertia_:12.2f} {sil:12.4f} {ch:12.2f}")

    best_sil_k = max(results, key=lambda r: r["silhouette"])["k"]
    best_ch_k = max(results, key=lambda r: r["ch_index"])["k"]
    print(f"\n  轮廓系数最优 k={best_sil_k}, CH 指数最优 k={best_ch_k}")

    if n_samples < 20:
        chosen_k = min(best_sil_k, N_CLUSTERS)
        print(f"  样本量较小({n_samples}), 选用 k={chosen_k}")
    else:
        chosen_k = best_sil_k
        print(f"  选用轮廓系数最优 k={chosen_k} (采样 n={sil_sample})")

    return chosen_k, results


def test_cluster_differences(df, feature_cols):
    """
    对每个特征做 Kruskal-Wallis 非参数检验，验证簇间差异显著性。
    """
    print("\n  [统计检验] 聚类簇间差异 (Kruskal-Wallis)")
    print(f"  {'特征':<28s} {'H统计量':>10s} {'p值':>10s} {'显著':>6s}")
    print("  " + "-" * 60)

    test_results = []
    for col in feature_cols:
        groups = [df[df["cluster_label"] == c][col].dropna().values for c in sorted(df["cluster_label"].unique())]
        groups = [g for g in groups if len(g) >= 2]
        if len(groups) < 2:
            continue
        h_stat, p_val = stats.kruskal(*groups)
        is_sig = p_val < 0.05
        test_results.append({
            "feature": col, "h_statistic": float(h_stat), "p_value": float(p_val),
            "is_significant": is_sig,
        })
        sig_str = "***" if p_val < 0.001 else ("**" if p_val < 0.01 else ("*" if p_val < 0.05 else ""))
        print(f"  {col:<28s} {h_stat:10.4f} {p_val:10.4f} {sig_str:>6s}")

    n_sig = sum(1 for r in test_results if r["is_significant"])
    print(f"\n  {n_sig}/{len(test_results)} 个特征簇间差异显著 (p<0.05)")
    return test_results


def visualize_clusters_pca(X_scaled, labels):
    """PCA 降维可视化聚类结果（文本摘要）。"""
    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    X_pca = pca.fit_transform(X_scaled)

    print(f"\n  [PCA 降维] 解释方差比: PC1={pca.explained_variance_ratio_[0]:.4f}, PC2={pca.explained_variance_ratio_[1]:.4f}")
    print(f"  累计解释方差: {sum(pca.explained_variance_ratio_):.4f}")

    for c in sorted(set(labels)):
        mask = labels == c
        cx, cy = X_pca[mask, 0].mean(), X_pca[mask, 1].mean()
        spread = np.sqrt(X_pca[mask, 0].var() + X_pca[mask, 1].var())
        print(f"    Cluster {c}: 中心=({cx:.2f}, {cy:.2f}), 离散度={spread:.2f}, 样本={mask.sum()}")


def run_clustering():
    print("\n[Step5.2] 开始 K-means 用户聚类...")

    features_df = build_user_features()
    cluster_input = get_cluster_features(features_df)

    feature_cols = [c for c in cluster_input.columns if c != "user_id"]
    X = cluster_input[feature_cols].values

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # 评估仅作参考（采样避免 silhouette O(n²) 爆炸）
    chosen_k, _ = evaluate_k_values(X_scaled)
    # 业务上固定 k=3（核心粉丝/内容消费者/轻度用户），与运营粒度一致
    chosen_k = N_CLUSTERS
    print(f"  [业务约束] 固定 k={chosen_k}（核心粉丝/内容消费者/轻度用户）")

    kmeans = KMeans(n_clusters=chosen_k, random_state=RANDOM_STATE, n_init=10)
    labels = kmeans.fit_predict(X_scaled)

    sil_score = silhouette_score(X_scaled, labels, sample_size=min(5000, len(X_scaled)), random_state=RANDOM_STATE)
    ch_score = calinski_harabasz_score(X_scaled, labels)
    print(f"\n  最终 k={chosen_k}: 轮廓系数={sil_score:.4f}, CH指数={ch_score:.2f}")

    visualize_clusters_pca(X_scaled, labels)

    labeled_df = assign_user_types(features_df, kmeans.cluster_centers_, labels)

    test_cluster_differences(labeled_df, CLUSTER_FEATURES)

    print("\n  [聚类结果分布]")
    dist = labeled_df["user_type"].value_counts()
    for user_type, cnt in dist.items():
        pct = cnt / len(labeled_df) * 100
        print(f"    {user_type:8s}: {cnt:6d} 人 ({pct:5.2f}%)")

    return labeled_df


def update_user_portrait(df: pd.DataFrame):
    """将聚类结果和增强字段更新到 ads_user_portrait 表。"""
    print("\n[Step5.3] 更新 ads_user_portrait 表...")

    portrait = read_table("ads_user_portrait")

    update_cols = [
        "user_id", "cluster_label", "user_type", "user_value",
        "avg_sentiment", "active_period", "sentiment_type",
    ]
    update_df = df[update_cols].copy()

    if portrait.empty:
        to_sql_replace(update_df, "ads_user_portrait")
    else:
        drop_cols = ["cluster_label", "user_type", "user_value",
                     "avg_sentiment", "active_period", "sentiment_type"]
        portrait = portrait.drop(columns=[c for c in drop_cols if c in portrait.columns], errors="ignore")
        portrait = pd.merge(portrait, update_df, on="user_id", how="outer")
        to_sql_replace(portrait, "ads_user_portrait")

    print("[OK] ads_user_portrait 更新完成")


def run():
    df = run_clustering()
    update_user_portrait(df)
