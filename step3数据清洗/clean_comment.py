"""
Step3 数据清洗 - 评论数据清洗

处理逻辑：
1. 文本规范化（去除控制字符、合并空白、去重标点）
2. 过滤无意义评论（如：666、哈哈、好听）
3. 过滤垃圾评论（广告、刷屏、引流）
4. 按歌曲维度精确去重（相同内容在同一首歌下只保留第一条）
5. SimHash 近似去重（避免语义雷同的垃圾评论）
6. 将清洗后的结果写回 dwd_comment_detail
"""
import logging

import pandas as pd

from clean_rules import (
    is_meaningless_comment,
    is_spam_comment,
    normalize_comment,
    SimHashDedup,
)
from db_helper import read_table, to_sql_replace

logger = logging.getLogger("step3.clean_comment")


def clean_comments() -> pd.DataFrame:
    """清洗评论数据并返回清洗后的 DataFrame。"""
    logger.info("[Step3.1] 开始清洗评论数据...")

    df = read_table("dwd_comment_detail")
    original_count = len(df)
    logger.info("  原始评论数: %d", original_count)

    # 1. 基础字段清洗
    df["content"] = df["content"].fillna("").astype(str)
    df["like_count"] = df["like_count"].fillna(0).astype(int)
    df["reply_count"] = df["reply_count"].fillna(0).astype(int)

    # 2. 文本规范化
    df["content_cleaned"] = df["content"].apply(normalize_comment)

    # 3. 标记无意义评论
    df["is_meaningless"] = df["content_cleaned"].apply(is_meaningless_comment)
    meaningless_count = int(df["is_meaningless"].sum())
    logger.info("  无意义评论数: %d", meaningless_count)

    # 4. 标记垃圾评论（广告、刷屏等）
    df["is_spam"] = df["content_cleaned"].apply(is_spam_comment)
    spam_count = int(df["is_spam"].sum())
    logger.info("  垃圾评论数: %d", spam_count)

    # 5. 过滤无意义 + 垃圾评论
    df_valid = df[~df["is_meaningless"] & ~df["is_spam"]].copy()

    # 6. 按 song_id + content_cleaned 精确去重，保留时间最早的一条
    df_valid = df_valid.sort_values("comment_time")
    df_valid = df_valid.drop_duplicates(subset=["song_id", "content_cleaned"], keep="first")
    logger.info("  精确去重后剩余: %d", len(df_valid))

    # 7. SimHash 近似去重（按歌曲维度）
    dedup = SimHashDedup(threshold=3)
    keep_mask = []
    simhash_dropped = 0
    current_song = None
    for _, row in df_valid.iterrows():
        # 切歌重置去重器（避免跨歌曲误判，控制内存）
        if row["song_id"] != current_song:
            dedup = SimHashDedup(threshold=3)
            current_song = row["song_id"]
        if dedup.is_duplicate(row["content_cleaned"]):
            keep_mask.append(False)
            simhash_dropped += 1
        else:
            dedup.add(row["content_cleaned"])
            keep_mask.append(True)
    df_valid = df_valid[keep_mask].copy()
    logger.info("  SimHash 近似去重丢弃: %d", simhash_dropped)
    logger.info("  有效评论数: %d", len(df_valid))

    # 8. 用清洗后的内容替换原内容
    df_valid["content"] = df_valid["content_cleaned"]

    # 9. 只保留目标表字段
    output_cols = [
        "comment_id", "song_id", "user_id", "content",
        "like_count", "reply_count", "comment_time", "etl_time"
    ]
    df_valid = df_valid[output_cols].copy()

    # 10. 更新 etl_time
    df_valid["etl_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    return df_valid


def run():
    df_cleaned = clean_comments()
    to_sql_replace(df_cleaned, "dwd_comment_detail")
    logger.info("[OK] 评论清洗完成并已写回 dwd_comment_detail")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()
