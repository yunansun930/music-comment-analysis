"""
Step1 数据采集 - 评论数据采集

负责：
1. 根据歌曲表中的 song_id 列表
2. 调用网易云评论接口获取评论
3. 输出 fact_comment.csv
"""

import time
from typing import List

import pandas as pd

from config import API, LIMITS, OUTPUT
from utils import fetch_json, ms_to_datetime, save_csv, safe_get


def get_comments(song_id: int, limit: int = LIMITS["comments_per_song"]) -> List[dict]:
    """
    获取指定歌曲的热门评论。
    接口：https://music.163.com/api/v1/resource/comments/R_SO_4_{song_id}
    """
    url = API["comment"].format(song_id=song_id)
    all_comments = []
    offset = 0
    page_limit = LIMITS["comment_offset_step"]

    while len(all_comments) < limit:
        params = {
            "limit": page_limit,
            "offset": offset,
        }
        data = fetch_json(url, params=params)
        if data is None:
            break

        # 热门评论 + 最新评论
        hot_comments = safe_get(data, "hotComments", default=[])
        new_comments = safe_get(data, "comments", default=[])
        comments = hot_comments + new_comments

        if not comments:
            break

        all_comments.extend(comments)
        offset += page_limit

        # 如果已经拿到足够的热门评论，提前结束
        if len(all_comments) >= limit:
            break
        time.sleep(LIMITS["request_delay"])

    return all_comments[:limit]


def parse_comment(raw: dict, song_id: int) -> dict:
    """将原始评论数据解析为 fact_comment 字段格式。"""
    user = raw.get("user", {})
    return {
        "comment_id": raw.get("commentId"),
        "song_id": song_id,
        "user_id": user.get("userId"),
        "user_nickname": user.get("nickname"),  # 用于后续构建 dim_user
        "content": raw.get("content", "").strip(),
        "like_count": raw.get("likedCount", 0),
        "reply_count": raw.get("replyCount", 0),
        "comment_time": ms_to_datetime(raw.get("time")),
    }


def run_comment_spider(song_df: pd.DataFrame) -> pd.DataFrame:
    """
    执行评论数据采集。

    参数：
        song_df: dim_song DataFrame，用于提取 song_id
    """
    print("\n[Step1.3] 开始采集评论数据...")
    song_ids = song_df["song_id"].dropna().unique().tolist()
    print(f"  -> 共 {len(song_ids)} 首歌曲需要采集评论")

    all_comments = []
    for idx, song_id in enumerate(song_ids, 1):
        comments = get_comments(int(song_id))
        parsed = [parse_comment(c, song_id) for c in comments if c.get("content")]
        all_comments.extend(parsed)
        print(f"     [{idx}/{len(song_ids)}] song_id={song_id} 获取评论 {len(parsed)} 条")
        time.sleep(LIMITS["request_delay"])

    df = pd.DataFrame(all_comments)
    save_csv(df, OUTPUT["fact_comment"])
    return df


if __name__ == "__main__":
    song_df = pd.read_csv(OUTPUT["dim_song"])
    run_comment_spider(song_df)
