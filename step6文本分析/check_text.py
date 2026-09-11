"""
Step6 文本分析 - 结果检查

运行命令：
    python -u check_text.py
"""

import pandas as pd
from db_helper import read_table


def main():
    print("=" * 60)
    print("Step6 文本分析 - 结果检查")
    print("=" * 60)

    tables = [
        "ads_global_keywords",
        "ads_song_keywords",
        "ads_comment_topic",
        "ads_comment_topic_detail",
        "ads_song_topic_dist",
        "ads_comment_sentiment",
        "ads_song_sentiment",
        "ads_sentiment_summary",
    ]

    print("\n[各结果表数据量]")
    for table in tables:
        try:
            df = read_table(table)
            print(f"  {table:30s}: {len(df):6d} 条")
        except Exception as e:
            print(f"  {table:30s}: 读取失败 - {e}")

    print("\n[全局热门关键词 TOP 10]")
    try:
        keywords = read_table("ads_global_keywords")
        print(keywords.head(10).rename(columns={"keyword_rank": "rank"}).to_string(index=False))
    except Exception as e:
        print(f"  读取失败: {e}")

    print("\n[LDA 主题关键词]")
    try:
        topics = read_table("ads_comment_topic")
        for _, row in topics.iterrows():
            print(f"  {row['topic_name']}: {row['keywords']}")
    except Exception as e:
        print(f"  读取失败: {e}")

    print("\n[全局情感汇总]")
    try:
        summary = read_table("ads_sentiment_summary")
        print(summary.to_string(index=False))
    except Exception as e:
        print(f"  读取失败: {e}")

    print("\n[检查完成]")


if __name__ == "__main__":
    main()
