"""
Step4 指标体系 - 用户评论画像表 ads_user_portrait

基于真实评论数据计算用户画像基础字段：
  comment_count_total → 用户总评论数
  reply_count_total   → 用户总回复数
  like_received_total  → 用户总评论获赞数
  activity_score       → 活跃度（基于评论天数 + 日均评论数）
  interaction_score    → 互动贡献（基于回复数 + 获赞数）
  diversity_score      → 内容多样性（基于评论歌曲数）
  user_value           → 用户价值分
聚类标签、情感/主题增强字段在 Step5 中填充。
"""

import numpy as np
import pandas as pd

from config import USER_VALUE_WEIGHTS
from db_helper import read_table, to_sql_replace


def build_ads_user_portrait() -> pd.DataFrame:
    print("\n[Step4.6] 开始计算用户评论画像...")

    user_daily = read_table("dws_user_daily")

    agg = user_daily.groupby("user_id").agg({
        "comment_count": "sum",
        "reply_count": "sum",
        "like_received": "sum",
        "active_song_num": "sum",
    }).reset_index()

    agg.columns = [
        "user_id", "comment_count_total", "reply_count_total",
        "like_received_total", "total_active_song_num"
    ]

    active_days = user_daily.groupby("user_id")["dt"].nunique().reindex(agg["user_id"]).fillna(0)
    agg["active_days"] = active_days.values

    def min_max_scale(series: pd.Series) -> pd.Series:
        s_min, s_max = series.min(), series.max()
        if s_max == s_min:
            return pd.Series([0.0] * len(series), index=series.index)
        return ((series - s_min) / (s_max - s_min)).round(4)

    agg["activity_score"] = min_max_scale(
        0.5 * agg["active_days"] / agg["active_days"].clip(lower=1).max()
        + 0.5 * np.log1p(agg["comment_count_total"]) / np.log1p(max(agg["comment_count_total"].max(), 1))
    )
    agg["interaction_score"] = min_max_scale(
        agg["reply_count_total"] + agg["like_received_total"]
    )
    agg["diversity_score"] = min_max_scale(
        np.log1p(agg["total_active_song_num"])
    )

    w = USER_VALUE_WEIGHTS
    agg["user_value"] = (
        w["activity"] * agg["activity_score"]
        + w["interaction"] * agg["interaction_score"]
        + w["diversity"] * agg["diversity_score"]
    ).round(4)

    def simple_user_type(value: float) -> str:
        if value >= 0.7:
            return "核心粉丝"
        elif value >= 0.3:
            return "内容消费者"
        else:
            return "轻度用户"

    agg["user_type"] = agg["user_value"].apply(simple_user_type)
    agg["cluster_label"] = -1

    output_cols = [
        "user_id", "cluster_label", "user_type", "user_value",
        "comment_count_total", "reply_count_total", "like_received_total",
        "activity_score", "interaction_score", "diversity_score"
    ]
    df = agg[output_cols].sort_values("user_value", ascending=False).reset_index(drop=True)

    print(f"  计算完成，共 {len(df)} 条用户画像记录")
    print(f"  用户类型分布:\n{df['user_type'].value_counts().to_string()}")
    return df


def run():
    df = build_ads_user_portrait()
    to_sql_replace(df, "ads_user_portrait")
    print("[OK] 用户评论画像计算完成并已写入 ads_user_portrait")


if __name__ == "__main__":
    run()
