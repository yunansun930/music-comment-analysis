"""
Step7 模型预测 - 爆款歌曲特征工程（基于真实评论数据）

特征全部来自评论衍生指标：
- 歌曲评论汇总：评论数、回复数、获赞数、热度分
- 歌手评论汇总：评论数、回复数、获赞数
- 情感特征：正面/负面比例、有效评论数
- 主题特征：主题覆盖数
- 发布时间特征
- 评论比率：每条评论平均获赞、平均回复
复合热度 = 评论数×0.4 + 获赞数×0.3 + 正面情感×0.3
"""
import logging

import numpy as np
import pandas as pd

from db_helper import read_sql

logger = logging.getLogger("step7.features")

HEAT_WEIGHTS = {
    "comment": 0.40,
    "like": 0.30,
    "sentiment": 0.30,
}


def _quantile_label(series: pd.Series, top_pct: float = 0.10) -> pd.Series:
    # top_pct 表示"取前 top_pct 比例作为爆款"，阈值应使用 (1 - top_pct) 分位数
    # 例如 top_pct=0.10 表示前 10%，则阈值 = 第 90 百分位的值，>= 阈值的恰好是 10%
    threshold = series.quantile(1 - top_pct)
    return (series >= threshold).astype(int)


def build_features():
    """为每首歌构建爆款预测特征（基于真实评论数据）。"""
    songs = read_sql("""
        SELECT song_id, release_time, artist_id
        FROM dwd_song_info
    """)

    song_metrics = read_sql("""
        SELECT
            song_id,
            SUM(comment_count) AS total_comment_count,
            SUM(reply_count) AS total_reply_count,
            SUM(like_total) AS total_like_total,
            AVG(heat_score) AS avg_heat_score,
            MAX(heat_score) AS max_heat_score
        FROM dws_song_daily
        GROUP BY song_id
    """)

    artist_metrics = read_sql("""
        SELECT
            artist_id,
            SUM(comment_count) AS artist_comment_count,
            SUM(reply_count) AS artist_reply_count,
            SUM(like_total) AS artist_like_total
        FROM dws_artist_daily
        GROUP BY artist_id
    """)

    sentiment = read_sql("""
        SELECT
            song_id,
            AVG(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) AS positive_ratio,
            AVG(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) AS negative_ratio,
            COUNT(*) AS valid_comment_count
        FROM ads_comment_sentiment
        GROUP BY song_id
    """)

    topic_diversity = read_sql("""
        SELECT
            song_id,
            COUNT(DISTINCT topic_id) AS topic_count
        FROM ads_comment_topic_detail
        GROUP BY song_id
    """)

    df = songs.merge(song_metrics, on="song_id", how="left")
    df = df.merge(artist_metrics, on="artist_id", how="left")
    df = df.merge(sentiment, on="song_id", how="left")
    df = df.merge(topic_diversity, on="song_id", how="left")

    df["release_time"] = pd.to_datetime(df["release_time"])
    df["release_year"] = df["release_time"].dt.year
    df["release_month"] = df["release_time"].dt.month
    df["days_since_release"] = (pd.Timestamp.now() - df["release_time"]).dt.days

    df["like_per_comment"] = df["total_like_total"] / (df["total_comment_count"] + 1)
    df["reply_per_comment"] = df["total_reply_count"] / (df["total_comment_count"] + 1)

    # ---- 交叉特征（歌曲/歌手级别比率，不含绝对值，无泄露） ----
    df["artist_song_count"] = df.groupby("artist_id")["song_id"].transform("count")
    df["artist_avg_comment_per_song"] = df["artist_comment_count"] / (df["artist_song_count"] + 1)
    df["artist_avg_like_per_song"] = df["artist_like_total"] / (df["artist_song_count"] + 1)

    # ---- 时序窗口特征（趋势/波动/动量，不含绝对值，无泄露） ----
    daily = read_sql("""
        SELECT song_id, dt, comment_count, like_total, heat_score
        FROM dws_song_daily
        ORDER BY song_id, dt
    """)
    if not daily.empty and "dt" in daily.columns:
        daily["dt"] = pd.to_datetime(daily["dt"], errors="coerce")
        daily = daily.dropna(subset=["dt"]).sort_values(["song_id", "dt"])

        def _slope(y):
            x = np.arange(len(y), dtype=float)
            if len(y) < 2 or np.std(x) == 0:
                return 0.0
            s = np.polyfit(x, y, 1)[0]
            return float(s) if not np.isnan(s) else 0.0

        def _ts_features(g):
            n = len(g)
            last7 = g.tail(7)
            last30 = g.tail(30)
            mean_c = g["comment_count"].mean()
            std_c = g["comment_count"].std()
            mean_l = g["like_total"].mean()
            return pd.Series({
                "comment_trend_slope": _slope(g["comment_count"].values),
                "like_trend_slope": _slope(g["like_total"].values),
                "heat_trend_slope": _slope(g["heat_score"].values),
                "comment_volatility": float(std_c / (mean_c + 1)) if mean_c > 0 else 0.0,
                "comment_momentum": float(last7["comment_count"].mean() / (last30["comment_count"].mean() + 1)),
                "like_momentum": float(last7["like_total"].mean() / (last30["like_total"].mean() + 1)),
            })

        ts = daily.groupby("song_id").apply(_ts_features).reset_index()
        df = df.merge(ts, on="song_id", how="left")
        logger.info("[时序特征] 为 %d 首歌曲计算了 6 个时序特征", len(ts))
    else:
        for col in ["comment_trend_slope", "like_trend_slope", "heat_trend_slope",
                     "comment_volatility", "comment_momentum", "like_momentum"]:
            df[col] = 0.0
        logger.warning("[时序特征] dws_song_daily 无 dt 列或为空，时序特征填 0")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    for col in numeric_cols:
        df[col] = df[col].fillna(0)

    for col in ["total_comment_count", "total_like_total", "positive_ratio"]:
        col_max = df[col].max() if df[col].max() > 0 else 1
        df[f"{col}_norm"] = df[col] / col_max

    df["composite_heat"] = (
        df["total_comment_count_norm"] * HEAT_WEIGHTS["comment"]
        + df["total_like_total_norm"] * HEAT_WEIGHTS["like"]
        + df["positive_ratio_norm"] * HEAT_WEIGHTS["sentiment"]
    )

    df["label"] = _quantile_label(df["composite_heat"], top_pct=0.10)

    df["label_comment_hot"] = _quantile_label(df["total_comment_count"], top_pct=0.10)
    df["label_interact_hot"] = _quantile_label(
        df["total_comment_count"] + df["total_like_total"], top_pct=0.10
    )
    df["label_longtail_hot"] = 0
    longtail_mask = df["days_since_release"] >= 90
    if longtail_mask.any():
        df.loc[longtail_mask, "label_longtail_hot"] = _quantile_label(
            df.loc[longtail_mask, "composite_heat"], top_pct=0.30
        ).values

    logger.info("[特征工程] 共 %d 首歌曲", len(df))
    logger.info("[复合热度标签] 爆款 %d 首 (%.1f%%)", int(df["label"].sum()), df["label"].mean() * 100)

    return df
