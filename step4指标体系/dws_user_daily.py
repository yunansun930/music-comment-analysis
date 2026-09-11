"""
Step4 指标体系 - 用户日评论指标表 dws_user_daily

基于真实评论数据计算，字段含义与名称一致：
  comment_count      → 用户日评论数
  reply_count        → 用户日回复数
  like_received      → 用户日评论获赞数
  active_song_num    → 评论歌曲数 COUNT(DISTINCT song_id)
  avg_comment_length → 平均评论字数 AVG(CHAR_LENGTH(content))
"""

import pandas as pd

from db_helper import read_table, to_sql_replace


def build_dws_user_daily() -> pd.DataFrame:
    print("\n[Step4.2] 开始计算用户日评论指标...")

    comment_df = read_table("dwd_comment_detail")
    comment_df["dt"] = pd.to_datetime(comment_df["comment_time"]).dt.date
    comment_df["content_length"] = comment_df["content"].fillna("").str.len()

    agg = comment_df.groupby(["dt", "user_id"]).agg(
        comment_count=("comment_id", "count"),
        like_received=("like_count", "sum"),
        reply_count=("reply_count", "sum"),
        active_song_num=("song_id", "nunique"),
        avg_comment_length=("content_length", "mean"),
    ).reset_index()

    agg["dt"] = pd.to_datetime(agg["dt"]).dt.date
    for col in ["comment_count", "reply_count", "like_received", "active_song_num"]:
        agg[col] = agg[col].astype(int)
    agg["avg_comment_length"] = agg["avg_comment_length"].round(2)

    output_cols = [
        "dt", "user_id", "comment_count", "reply_count", "like_received",
        "active_song_num", "avg_comment_length"
    ]
    df = agg[output_cols].sort_values(["dt", "user_id"]).reset_index(drop=True)

    print(f"  计算完成，共 {len(df)} 条用户日评论指标")
    return df


def run():
    df = build_dws_user_daily()
    to_sql_replace(df, "dws_user_daily")
    print("[OK] 用户日评论指标计算完成并已写入 dws_user_daily")


if __name__ == "__main__":
    run()
