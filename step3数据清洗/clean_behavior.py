"""
Step3 数据清洗 - 行为数据清洗

处理逻辑：
1. 过滤 user_id 或 song_id 为空的记录
2. 过滤 behavior_type 不在合法枚举中的记录
3. 过滤 behavior_time 为空或未来的记录
4. 去除重复的 behavior_id
5. 标准化 behavior_type 为小写
"""

import pandas as pd

from db_helper import read_table, to_sql_replace

VALID_BEHAVIOR_TYPES = {"play", "like", "collect", "comment", "share"}


def clean_behaviors() -> pd.DataFrame:
    """清洗行为数据并返回清洗后的 DataFrame。"""
    print("\n[Step3.4] 开始清洗行为数据...")

    df = read_table("dwd_behavior_detail")
    original_count = len(df)
    print(f"  原始行为数: {original_count}")

    # 1. 过滤关键字段为空
    df = df.dropna(subset=["user_id", "song_id", "behavior_type", "behavior_time"])

    # 2. 标准化 behavior_type
    df["behavior_type"] = df["behavior_type"].astype(str).str.strip().str.lower()

    # 3. 过滤非法行为类型
    df = df[df["behavior_type"].isin(VALID_BEHAVIOR_TYPES)]

    # 4. 过滤未来时间
    now = pd.Timestamp.now()
    df["behavior_time"] = pd.to_datetime(df["behavior_time"], errors="coerce")
    df = df[df["behavior_time"] <= now]

    # 5. 去除重复 behavior_id，保留第一条
    df = df.drop_duplicates(subset=["behavior_id"], keep="first")

    # 6. 其他字段清洗
    df["session_id"] = df["session_id"].fillna("").astype(str).str.strip()
    df["device"] = df["device"].fillna("unknown").astype(str).str.strip()
    df["source"] = df["source"].fillna("unknown").astype(str).str.strip()

    # 7. 更新 etl_time
    df["etl_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    cleaned_count = len(df)
    print(f"  清洗后行为数: {cleaned_count}")
    print(f"  过滤掉行为数: {original_count - cleaned_count}")

    return df


def run():
    df_cleaned = clean_behaviors()
    to_sql_replace(df_cleaned, "dwd_behavior_detail")
    print("[OK] 行为清洗完成并已写回 dwd_behavior_detail")


if __name__ == "__main__":
    run()
