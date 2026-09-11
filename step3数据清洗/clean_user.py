"""
Step3 数据清洗 - 用户数据清洗

处理逻辑：
1. 填充缺失的用户等级：用众数填充
2. 填充缺失的性别：标记为 0（保密）
3. 填充缺失的年龄段：标记为"未知"
4. 填充缺失的注册时间：用最早的有效注册时间填充
5. 填充缺失的省份/城市编码：标记为 0
"""

import pandas as pd

from db_helper import read_table, to_sql_replace


def clean_users() -> pd.DataFrame:
    """清洗用户数据并返回清洗后的 DataFrame。"""
    print("\n[Step3.2] 开始清洗用户数据...")

    df = read_table("dwd_user_info")
    original_count = len(df)
    print(f"  原始用户数: {original_count}")

    # 1. 昵称清洗：去除首尾空白
    df["nickname"] = df["nickname"].fillna("").astype(str).str.strip()
    df.loc[df["nickname"] == "", "nickname"] = "未知用户"

    # 2. 等级填充：用众数
    if df["level"].notna().any():
        level_mode = int(df["level"].mode().iloc[0])
    else:
        level_mode = 1
    df["level"] = df["level"].fillna(level_mode).astype(int)

    # 3. 性别填充：缺失标记为 0（保密）
    df["gender"] = df["gender"].fillna(0).astype(int)

    # 4. 年龄段填充：缺失标记为"未知"
    df["age_group"] = df["age_group"].fillna("未知")

    # 5. 注册时间填充：用最早的有效注册时间
    if df["register_time"].notna().any():
        min_register_time = df["register_time"].min()
    else:
        min_register_time = pd.Timestamp("2000-01-01")
    df["register_time"] = df["register_time"].fillna(min_register_time)

    # 6. 省份/城市编码填充：缺失标记为 0
    df["province"] = df["province"].fillna(0).astype(int)
    df["city"] = df["city"].fillna(0).astype(int)

    # 7. 更新 etl_time
    df["etl_time"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

    missing_after = df.isnull().sum().sum()
    print(f"  清洗后缺失值总数: {missing_after}")

    return df


def run():
    df_cleaned = clean_users()
    to_sql_replace(df_cleaned, "dwd_user_info")
    print("[OK] 用户清洗完成并已写回 dwd_user_info")


if __name__ == "__main__":
    run()
