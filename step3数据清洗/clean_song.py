"""
Step3 数据清洗 - 歌曲数据清洗

处理逻辑：
1. 填充缺失的歌曲类型、语言、标签：标记为"未知"
2. 填充缺失的时长：用有效时长的中位数填充
3. 填充缺失的专辑：标记为"未知专辑"
4. 确保 release_time 格式正确
"""

import pandas as pd

from db_helper import read_table, to_sql_replace


def clean_songs() -> pd.DataFrame:
    """清洗歌曲数据并返回清洗后的 DataFrame。"""
    print("\n[Step3.3] 开始清洗歌曲数据...")

    df = read_table("dwd_song_info")
    original_count = len(df)
    print(f"  原始歌曲数: {original_count}")

    # 1. 文本字段去空白
    for col in ["song_name", "artist_name", "album", "category", "language", "tags"]:
        df[col] = df[col].fillna("").astype(str).str.strip()

    # 2. 填充缺失值
    df.loc[df["category"] == "", "category"] = "未知"
    df.loc[df["language"] == "", "language"] = "未知"
    df.loc[df["tags"] == "", "tags"] = "未知"
    df.loc[df["album"] == "", "album"] = "未知专辑"

    # 3. 时长填充：用中位数
    if df["duration"].notna().any():
        duration_median = int(df["duration"].median())
    else:
        duration_median = 0
    df["duration"] = df["duration"].fillna(duration_median).astype(int)

    # 4. 发布时间标准化
    df["release_time"] = pd.to_datetime(df["release_time"], errors="coerce")
    if df["release_time"].notna().any():
        min_release_time = df["release_time"].min()
    else:
        min_release_time = pd.Timestamp("2000-01-01")
    df["release_time"] = df["release_time"].fillna(min_release_time)

    # 5. 更新 etl_time
    df["etl_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    missing_after = df.isnull().sum().sum()
    print(f"  清洗后缺失值总数: {missing_after}")

    return df


def run():
    df_cleaned = clean_songs()
    to_sql_replace(df_cleaned, "dwd_song_info")
    print("[OK] 歌曲清洗完成并已写回 dwd_song_info")


if __name__ == "__main__":
    run()
