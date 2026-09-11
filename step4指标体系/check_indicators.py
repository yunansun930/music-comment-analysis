"""
Step4 指标体系 - 计算结果质量检查

运行命令：
    python check_indicators.py
"""

import pandas as pd

from db_helper import read_table


def check_dws():
    print("\n[DWS 层指标检查]")
    for table in ["dws_song_daily", "dws_user_daily", "dws_artist_daily"]:
        df = read_table(table)
        print(f"\n  {table}: {len(df)} rows")
        print(f"    时间范围: {df['dt'].min()} ~ {df['dt'].max()}")
        if "heat_score" in df.columns:
            print(f"    heat_score 范围: {df['heat_score'].min():.4f} ~ {df['heat_score'].max():.4f}")


def check_ads():
    print("\n[ADS 层指标检查]")

    # 歌曲排名
    rank_df = read_table("ads_song_rank")
    print(f"\n  ads_song_rank: {len(rank_df)} rows")
    print(f"    每日 Top3 歌曲示例:")
    top3 = rank_df[rank_df["heat_rank"] <= 3].sort_values(["dt", "heat_rank"]).head(9)
    print(top3[["dt", "song_id", "heat_rank", "heat_score", "lifecycle_stage"]].to_string(index=False))

    # 生命周期
    lifecycle_df = read_table("ads_song_lifecycle")
    print(f"\n  ads_song_lifecycle: {len(lifecycle_df)} rows")
    print(f"    生命周期阶段分布:")
    print(lifecycle_df["lifecycle_stage"].value_counts().to_string().replace("\n", "\n    "))

    # 用户画像
    portrait_df = read_table("ads_user_portrait")
    print(f"\n  ads_user_portrait: {len(portrait_df)} rows")
    print(f"    user_value 范围: {portrait_df['user_value'].min():.4f} ~ {portrait_df['user_value'].max():.4f}")
    print(f"    用户类型分布:")
    print(portrait_df["user_type"].value_counts().to_string().replace("\n", "\n    "))


def main():
    print("=" * 60)
    print("Step4 指标体系 - 质量检查")
    print("=" * 60)

    check_dws()
    check_ads()

    print("\n" + "=" * 60)
    print("指标体系检查完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
