"""
Step5 用户分析 - 用户评论特征工程

从 dws_user_daily + dwd_user_info 聚合用户评论行为特征，
可选地从 ads_comment_sentiment / dwd_comment_detail 增强情感与时段画像。
"""

import logging

import numpy as np
import pandas as pd

from db_helper import read_sql, read_table

logger = logging.getLogger("step5.features")


def _try_read_sentiment() -> pd.DataFrame:
    """尝试读取情感数据，若 step6 尚未运行则返回空 DataFrame。"""
    try:
        return read_sql("""
            SELECT c.user_id, AVG(s.positive_prob) AS avg_sentiment
            FROM dwd_comment_detail c
            JOIN ads_comment_sentiment s ON c.comment_id = s.comment_id
            GROUP BY c.user_id
        """)
    except Exception:
        logger.warning("  ads_comment_sentiment 表不存在或查询失败，跳过情感增强")
        return pd.DataFrame(columns=["user_id", "avg_sentiment"])


def _try_read_active_period() -> pd.DataFrame:
    """从评论时间提取用户活跃时段（凌晨/上午/下午/晚上）。"""
    try:
        df = read_sql("SELECT user_id, comment_time FROM dwd_comment_detail")
        if df.empty:
            return pd.DataFrame(columns=["user_id", "active_period"])
        df["hour"] = pd.to_datetime(df["comment_time"]).dt.hour

        def _period(h):
            if 0 <= h < 6:
                return "凌晨"
            elif 6 <= h < 12:
                return "上午"
            elif 12 <= h < 18:
                return "下午"
            else:
                return "晚上"

        df["period"] = df["hour"].apply(_period)
        mode = df.groupby("user_id")["period"].agg(lambda x: x.mode().iloc[0] if not x.mode().empty else "未知").reset_index()
        mode.columns = ["user_id", "active_period"]
        return mode
    except Exception:
        logger.warning("  活跃时段计算失败，跳过")
        return pd.DataFrame(columns=["user_id", "active_period"])


def build_user_features() -> pd.DataFrame:
    """构建用户评论行为特征宽表。"""
    print("\n[Step5.1] 开始构建用户评论特征...")

    user_daily = read_table("dws_user_daily")
    user_info = read_table("dwd_user_info")

    if user_daily.empty:
        raise ValueError("dws_user_daily 表为空，请先运行 Step4 指标体系")

    agg = user_daily.groupby("user_id").agg(
        total_comment_count=("comment_count", "sum"),
        total_reply_count=("reply_count", "sum"),
        total_like_received=("like_received", "sum"),
        active_days=("dt", "nunique"),
        total_active_song_num=("active_song_num", "sum"),
        avg_comment_length=("avg_comment_length", "mean"),
    ).reset_index()

    agg["avg_daily_comment"] = agg["total_comment_count"] / agg["active_days"].clip(lower=1)

    df = pd.merge(agg, user_info[["user_id", "level", "gender", "register_time"]], on="user_id", how="left")

    df["register_time"] = pd.to_datetime(df["register_time"], errors="coerce")
    df["register_days"] = (pd.Timestamp.now() - df["register_time"]).dt.days
    df["register_days"] = df["register_days"].fillna(df["register_days"].median()).clip(lower=1)

    for col in ["level", "gender"]:
        df[col] = df[col].fillna(df[col].median()).astype(int)

    df["activity_score"] = (
        0.4 * df["active_days"] / df["register_days"]
        + 0.3 * np.log1p(df["total_comment_count"]) / np.log1p(max(df["total_comment_count"].max(), 1))
        + 0.3 * np.log1p(df["avg_daily_comment"]) / np.log1p(max(df["avg_daily_comment"].max(), 1))
    )

    df["interaction_score"] = (
        0.6 * np.log1p(df["total_reply_count"]) / np.log1p(max(df["total_reply_count"].max(), 1))
        + 0.4 * np.log1p(df["total_like_received"]) / np.log1p(max(df["total_like_received"].max(), 1))
    )

    df["diversity_score"] = np.log1p(df["total_active_song_num"]) / np.log1p(max(df["total_active_song_num"].max(), 1))

    df["user_value"] = (
        0.4 * df["activity_score"]
        + 0.3 * df["interaction_score"]
        + 0.3 * df["diversity_score"]
    ).round(4)

    sentiment_df = _try_read_sentiment()
    if not sentiment_df.empty:
        df = pd.merge(df, sentiment_df, on="user_id", how="left")
        df["avg_sentiment"] = df["avg_sentiment"].fillna(0.5)
    else:
        df["avg_sentiment"] = 0.5

    period_df = _try_read_active_period()
    if not period_df.empty:
        df = pd.merge(df, period_df, on="user_id", how="left")
        df["active_period"] = df["active_period"].fillna("未知")
    else:
        df["active_period"] = "未知"

    period_map = {"凌晨": 0, "上午": 1, "下午": 2, "晚上": 3, "未知": 1}
    df["active_period_encoded"] = df["active_period"].map(period_map).fillna(1).astype(int)

    def _sentiment_label(val):
        if val >= 0.6:
            return "正面"
        elif val < 0.4:
            return "负面"
        return "中性"

    df["sentiment_type"] = df["avg_sentiment"].apply(_sentiment_label)

    print(f"  特征构建完成，共 {len(df)} 个用户")
    return df


def get_cluster_features(df: pd.DataFrame) -> pd.DataFrame:
    """获取用于聚类的特征列。"""
    feature_cols = [
        "total_comment_count", "total_reply_count", "total_like_received",
        "active_days", "avg_daily_comment", "total_active_song_num",
        "activity_score", "interaction_score", "diversity_score", "user_value",
        "avg_sentiment", "active_period_encoded",
    ]
    return df[["user_id"] + feature_cols].copy()
