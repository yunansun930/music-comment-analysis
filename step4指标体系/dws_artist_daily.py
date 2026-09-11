"""
Step4 指标体系 - 歌手日评论指标表 dws_artist_daily

基于真实评论数据计算，字段含义与名称一致：
  comment_count → 歌手日评论数
  reply_count   → 歌手日回复数
  like_total    → 歌手日评论获赞数
"""

import pandas as pd

from db_helper import read_sql, to_sql_replace


def build_dws_artist_daily() -> pd.DataFrame:
    print("\n[Step4.3] 开始计算歌手日评论指标...")

    sql = """
        SELECT
            c.comment_time,
            c.song_id,
            c.like_count,
            c.reply_count,
            s.artist_id
        FROM dwd_comment_detail c
        LEFT JOIN dwd_song_info s ON c.song_id = s.song_id
    """
    comment_df = read_sql(sql)
    comment_df["dt"] = pd.to_datetime(comment_df["comment_time"]).dt.date
    comment_df = comment_df[comment_df["artist_id"].notna()]

    agg = comment_df.groupby(["dt", "artist_id"]).agg(
        comment_count=("comment_time", "count"),
        like_total=("like_count", "sum"),
        reply_count=("reply_count", "sum"),
    ).reset_index()

    agg["dt"] = pd.to_datetime(agg["dt"]).dt.date
    agg["artist_id"] = agg["artist_id"].astype(int)
    for col in ["comment_count", "reply_count", "like_total"]:
        agg[col] = agg[col].astype(int)

    output_cols = ["dt", "artist_id", "comment_count", "reply_count", "like_total"]
    df = agg[output_cols].sort_values(["dt", "artist_id"]).reset_index(drop=True)

    print(f"  计算完成，共 {len(df)} 条歌手日评论指标")
    return df


def run():
    df = build_dws_artist_daily()
    to_sql_replace(df, "dws_artist_daily")
    print("[OK] 歌手日评论指标计算完成并已写入 dws_artist_daily")


if __name__ == "__main__":
    run()
