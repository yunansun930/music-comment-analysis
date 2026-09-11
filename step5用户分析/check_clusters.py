"""
Step5 用户分析 - 聚类结果检查

运行命令：
    python -u check_clusters.py
"""

import pandas as pd
from db_helper import read_table, read_sql


def main():
    print("=" * 60)
    print("Step5 用户分析 - 聚类结果检查")
    print("=" * 60)

    portrait = read_table("ads_user_portrait")

    print("\n[用户类型分布]")
    dist = portrait["user_type"].value_counts()
    for user_type, cnt in dist.items():
        pct = cnt / len(portrait) * 100
        print(f"  {user_type:8s}: {cnt:6d} 人 ({pct:5.2f}%)")

    print("\n[各类型用户价值分统计]")
    stats = portrait.groupby("user_type")["user_value"].agg(["count", "mean", "min", "max"]).round(4)
    print(stats)

    print("\n[用户价值分 TOP 10]")
    top10 = portrait.nlargest(10, "user_value")[["user_id", "user_type", "user_value"]]
    if "comment_count_total" in portrait.columns:
        top10 = portrait.nlargest(10, "user_value")[
            ["user_id", "user_type", "user_value", "comment_count_total", "avg_sentiment"]
        ]
    print(top10.to_string(index=False))

    print("\n[检查完成]")


if __name__ == "__main__":
    main()
