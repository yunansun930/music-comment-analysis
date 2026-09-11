"""
Step3 数据清洗 - 清洗结果质量检查

运行命令：
    python check_clean.py
"""

import pandas as pd

from db_helper import read_table


def check_comments():
    """检查评论清洗结果。"""
    print("\n[评论清洗结果检查]")
    df = read_table("dwd_comment_detail")
    print(f"  有效评论总数: {len(df)}")
    print(f"  平均评论长度: {df['content'].astype(str).str.len().mean():.2f}")
    print(f"  评论内容缺失数: {df['content'].isna().sum()}")

    # 检查是否还有明显无意义评论
    from clean_rules import is_meaningless_comment
    still_meaningless = df["content"].apply(is_meaningless_comment).sum()
    print(f"  剩余无意义评论数: {still_meaningless}")


def check_users():
    """检查用户清洗结果。"""
    print("\n[用户清洗结果检查]")
    df = read_table("dwd_user_info")
    print(f"  用户总数: {len(df)}")
    print(f"  各字段缺失值:")
    for col in df.columns:
        missing = df[col].isna().sum()
        print(f"    {col:20s}: {missing}")


def check_songs():
    """检查歌曲清洗结果。"""
    print("\n[歌曲清洗结果检查]")
    df = read_table("dwd_song_info")
    print(f"  歌曲总数: {len(df)}")
    print(f"  各字段缺失值:")
    for col in df.columns:
        missing = df[col].isna().sum()
        print(f"    {col:20s}: {missing}")


def check_behaviors():
    """检查行为清洗结果。"""
    print("\n[行为清洗结果检查]")
    df = read_table("dwd_behavior_detail")
    print(f"  行为总数: {len(df)}")
    print(f"  行为类型分布:")
    print(df["behavior_type"].value_counts().to_string().replace("\n", "\n    "))
    print(f"  时间范围: {df['behavior_time'].min()} ~ {df['behavior_time'].max()}")


def main():
    print("=" * 60)
    print("Step3 数据清洗 - 质量检查")
    print("=" * 60)

    check_comments()
    check_users()
    check_songs()
    check_behaviors()

    print("\n" + "=" * 60)
    print("清洗质量检查完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
