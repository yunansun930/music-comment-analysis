"""
Step1 数据采集 - 数据质量检查脚本
"""

import pandas as pd
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

FILES = {
    "dim_song": DATA_DIR / "dim_song.csv",
    "dim_artist": DATA_DIR / "dim_artist.csv",
    "dim_user": DATA_DIR / "dim_user.csv",
    "fact_comment": DATA_DIR / "fact_comment.csv",
    "fact_behavior": DATA_DIR / "fact_behavior.csv",
}


def check_basic(df, name):
    print(f"\n【{name}】")
    print(f"  行数: {len(df)}")
    print(f"  列数: {len(df.columns)}")
    print(f"  列名: {list(df.columns)}")
    print("  缺失值:")
    for col, cnt in df.isnull().sum().items():
        if cnt > 0:
            print(f"    {col}: {cnt}")
    dup_count = df.duplicated().sum()
    print(f"  完全重复行数: {dup_count}")


def check_referential_integrity(frames):
    print("\n" + "=" * 70)
    print("关联一致性检查")
    print("=" * 70)

    song_ids = set(frames["dim_song"]["song_id"].dropna().astype(int))
    artist_ids = set(frames["dim_artist"]["artist_id"].dropna())
    user_ids = set(frames["dim_user"]["user_id"].dropna())

    comment_song_ids = set(frames["fact_comment"]["song_id"].dropna().astype(int))
    missing = comment_song_ids - song_ids
    print(f"\n  fact_comment 中不在 dim_song 的 song_id 数量: {len(missing)}")

    comment_user_ids = set(frames["fact_comment"]["user_id"].dropna())
    missing = comment_user_ids - user_ids
    print(f"  fact_comment 中不在 dim_user 的 user_id 数量: {len(missing)}")

    behavior_song_ids = set(frames["fact_behavior"]["song_id"].dropna().astype(int))
    missing = behavior_song_ids - song_ids
    print(f"  fact_behavior 中不在 dim_song 的 song_id 数量: {len(missing)}")

    behavior_user_ids = set(frames["fact_behavior"]["user_id"].dropna())
    missing = behavior_user_ids - user_ids
    print(f"  fact_behavior 中不在 dim_user 的 user_id 数量: {len(missing)}")

    song_artist_ids = set(frames["dim_song"]["artist_id"].dropna())
    missing = song_artist_ids - artist_ids
    print(f"  dim_song 中不在 dim_artist 的 artist_id 数量: {len(missing)}")


def show_samples(frames):
    print("\n" + "=" * 70)
    print("样本数据展示")
    print("=" * 70)
    for name, df in frames.items():
        print(f"\n【{name}】前 3 行:")
        print(df.head(3).to_string(index=False))


def main():
    print("=" * 70)
    print("Step1 数据采集 - 数据质量检查报告")
    print("=" * 70)

    frames = {}
    for name, path in FILES.items():
        df = pd.read_csv(path)
        frames[name] = df
        check_basic(df, name)

    check_referential_integrity(frames)
    show_samples(frames)


if __name__ == "__main__":
    main()
