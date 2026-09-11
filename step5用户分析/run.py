"""
Step5 用户分析 - 主运行入口

运行命令：
    python -u run.py
"""

from kmeans_cluster import run as run_clustering
import cohort_analysis
import rfm_clustering
import user_time_pattern


def main():
    print("=" * 60)
    print("Step5 用户分析 - K-means 聚类 + RFM 分群 + 时间模式 + 同期群")
    print("=" * 60)

    run_clustering()
    cohort_analysis.run()
    rfm_clustering.run()
    user_time_pattern.run()

    print("\n" + "=" * 60)
    print("用户分析完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
