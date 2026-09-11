"""
Step4 指标体系 - 歌曲日评论指标表 dws_song_daily

基于真实评论数据计算，字段含义与名称一致：
  comment_count       → 歌曲日评论数 COUNT(comment_id)
  reply_count        → 歌曲日回复数 SUM(reply_count)
  like_total         → 歌曲日评论获赞数 SUM(like_count)
  comment_user_count → 歌曲日评论用户数 COUNT(DISTINCT user_id)
  heat_score         → 热度分数(评论数+获赞数加权)
  comment_growth_rate→ 评论数日环比增长率
  reply_growth_rate  → 回复数日环比增长率
"""

import numpy as np
import pandas as pd

from db_helper import read_table, to_sql_replace


def calc_growth_rate(series: pd.Series) -> pd.Series:
    growth = series.pct_change().replace([np.inf, -np.inf], np.nan)
    growth = growth.fillna(0)
    growth = growth.clip(lower=-1, upper=5)
    return growth


def build_dws_song_daily() -> pd.DataFrame:
    print("\n[Step4.1] 开始计算歌曲日评论指标...")

    comment_df = read_table("dwd_comment_detail")
    comment_df["dt"] = pd.to_datetime(comment_df["comment_time"]).dt.date

    agg = comment_df.groupby(["dt", "song_id"]).agg(
        comment_count=("comment_id", "count"),
        like_total=("like_count", "sum"),
        reply_count=("reply_count", "sum"),
        comment_user_count=("user_id", "nunique"),
    ).reset_index()

    agg = agg.sort_values(["song_id", "dt"])
    agg["comment_growth_rate"] = agg.groupby("song_id")["comment_count"].transform(calc_growth_rate)
    agg["reply_growth_rate"] = agg.groupby("song_id")["reply_count"].transform(calc_growth_rate)

    agg["heat_score"] = (
        0.6 * np.log1p(agg["comment_count"]) / np.log1p(max(agg["comment_count"].max(), 1)) +
        0.4 * np.log1p(agg["like_total"]) / np.log1p(max(agg["like_total"].max(), 1))
    )
    agg["heat_score"] = agg["heat_score"] + 0.05 * (
        0.5 * agg["comment_growth_rate"] + 0.5 * agg["reply_growth_rate"]
    )
    agg["heat_score"] = agg["heat_score"].round(4)

    agg["dt"] = pd.to_datetime(agg["dt"]).dt.date
    for col in ["comment_count", "reply_count", "like_total", "comment_user_count"]:
        agg[col] = agg[col].astype(int)

    output_cols = [
        "dt", "song_id", "comment_count", "reply_count", "like_total",
        "comment_user_count", "heat_score", "comment_growth_rate", "reply_growth_rate"
    ]
    df = agg[output_cols].sort_values(["dt", "song_id"]).reset_index(drop=True)

    print(f"  计算完成，共 {len(df)} 条歌曲日评论指标")
    return df


def run():
    df = build_dws_song_daily()
    to_sql_replace(df, "dws_song_daily")
    print("[OK] 歌曲日评论指标计算完成并已写入 dws_song_daily")


if __name__ == "__main__":
    run()
