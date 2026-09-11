"""
Step4 指标体系 - 歌曲热度排名 & 生命周期

生成两张 ADS 表：
1. ads_song_rank：每日歌曲热度排名（基于评论指标）
2. ads_song_lifecycle：每日歌曲生命周期阶段
"""

import pandas as pd

from config import LIFECYCLE_THRESHOLDS
from db_helper import read_table, to_sql_replace


def classify_lifecycle(row: pd.Series) -> str:
    """根据日评论指标判断歌曲生命周期阶段。"""
    comment_count = row["comment_count"]
    comment_growth = row["comment_growth_rate"]
    heat_score = row["heat_score"]
    t = LIFECYCLE_THRESHOLDS

    if comment_count <= t["cold_comment"] and heat_score <= 0:
        return "冷启动"

    if comment_growth >= t["explode_growth"] or heat_score >= row.get("heat_threshold", 999):
        return "爆发期"

    if comment_growth >= t["growth_threshold"]:
        return "增长期"

    if comment_growth <= t["decline_growth"]:
        return "衰退期"

    return "稳定期"


def build_ads_song_rank() -> pd.DataFrame:
    print("\n[Step4.4] 开始计算歌曲热度排名...")

    df = read_table("dws_song_daily")
    df["dt"] = pd.to_datetime(df["dt"]).dt.date

    df["heat_rank"] = df.groupby("dt")["heat_score"].rank(ascending=False, method="min").astype(int)
    df["heat_threshold"] = df.groupby("dt")["heat_score"].transform(lambda x: x.quantile(0.8))
    df["lifecycle_stage"] = df.apply(classify_lifecycle, axis=1)

    output_cols = [
        "dt", "song_id", "heat_rank", "heat_score", "comment_count", "reply_count",
        "like_total", "lifecycle_stage"
    ]
    df = df[output_cols].sort_values(["dt", "heat_rank"]).reset_index(drop=True)

    print(f"  计算完成，共 {len(df)} 条排名记录")
    return df


def build_ads_song_lifecycle() -> pd.DataFrame:
    print("\n[Step4.5] 开始计算歌曲生命周期...")

    df = read_table("dws_song_daily")
    df["dt"] = pd.to_datetime(df["dt"]).dt.date
    df["heat_threshold"] = df.groupby("dt")["heat_score"].transform(lambda x: x.quantile(0.8))
    df["lifecycle_stage"] = df.apply(classify_lifecycle, axis=1)

    output_cols = ["dt", "song_id", "lifecycle_stage", "heat_score"]
    df = df[output_cols].sort_values(["dt", "song_id"]).reset_index(drop=True)

    print(f"  计算完成，共 {len(df)} 条生命周期记录")
    return df


def run():
    rank_df = build_ads_song_rank()
    to_sql_replace(rank_df, "ads_song_rank")

    lifecycle_df = build_ads_song_lifecycle()
    to_sql_replace(lifecycle_df, "ads_song_lifecycle")

    print("[OK] 歌曲热度排名和生命周期计算完成")


if __name__ == "__main__":
    run()
