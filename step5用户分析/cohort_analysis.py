"""
Step5 用户分析 - 同期群分析（Cohort Analysis）

按用户首次评论日期分群，追踪各 cohort 的评论留存率。
输出留存矩阵到 ads_cohort_retention 表。
"""
import numpy as np
import pandas as pd

from db_helper import read_sql, to_sql_replace, execute


def _create_table():
    execute("""
        CREATE TABLE IF NOT EXISTS ads_cohort_retention (
            cohort_week   VARCHAR(30)  COMMENT '首次评论周(YYYY-MM-DD/YYYY-MM-DD)',
            cohort_size   INT          COMMENT '该 cohort 用户总数',
            week_offset   INT          COMMENT '距首次评论的周偏移(0=首周)',
            active_users  INT          COMMENT '该周仍评论的用户数',
            retention     DECIMAL(6,4) COMMENT '留存率',
            update_time   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
            PRIMARY KEY (cohort_week, week_offset)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-同期群留存分析'
    """)
    try:
        execute("ALTER TABLE ads_cohort_retention MODIFY COLUMN cohort_week VARCHAR(30)")
    except Exception:
        pass


def build_cohort_matrix() -> pd.DataFrame:
    """构建同期群留存矩阵。"""
    print("\n[Step5.4] 同期群分析（Cohort Analysis）...")

    df = read_sql("""
        SELECT user_id, comment_time
        FROM dwd_comment_detail
        WHERE comment_time IS NOT NULL
    """)

    if df.empty:
        print("  评论数据为空，跳过")
        return pd.DataFrame()

    df["comment_time"] = pd.to_datetime(df["comment_time"])
    df["dt"] = df["comment_time"].dt.date

    first_comment = df.groupby("user_id")["dt"].min().reset_index()
    first_comment.columns = ["user_id", "first_dt"]
    first_comment["first_dt"] = pd.to_datetime(first_comment["first_dt"])

    first_comment["cohort_week"] = first_comment["first_dt"].dt.to_period("W").astype(str)

    merged = pd.merge(df, first_comment[["user_id", "cohort_week", "first_dt"]], on="user_id", how="left")
    merged["comment_dt"] = pd.to_datetime(merged["dt"])
    merged["week_offset"] = ((merged["comment_dt"] - merged["first_dt"]).dt.days / 7).astype(int)
    merged = merged[merged["week_offset"] >= 0]

    cohort_size = first_comment.groupby("cohort_week")["user_id"].nunique().reset_index()
    cohort_size.columns = ["cohort_week", "cohort_size"]

    active = merged.groupby(["cohort_week", "week_offset"])["user_id"].nunique().reset_index()
    active.columns = ["cohort_week", "week_offset", "active_users"]

    result = pd.merge(cohort_size, active, on="cohort_week", how="left")
    result["retention"] = (result["active_users"] / result["cohort_size"]).round(4)
    result = result.sort_values(["cohort_week", "week_offset"]).reset_index(drop=True)

    print(f"  共 {result['cohort_week'].nunique()} 个 cohort, 最大周偏移 {result['week_offset'].max()}")
    print(f"  平均首周留存率: {result[result['week_offset']==0]['retention'].mean():.4f}")
    if result["week_offset"].max() >= 1:
        wk1 = result[result["week_offset"] == 1]
        if not wk1.empty:
            print(f"  平均第1周留存率: {wk1['retention'].mean():.4f}")

    return result


def print_retention_matrix(df: pd.DataFrame):
    """打印留存矩阵热力图（文本版）。"""
    if df.empty:
        return

    pivot = df.pivot(index="cohort_week", columns="week_offset", values="retention")
    max_weeks = min(8, pivot.columns.max() + 1)
    pivot = pivot[list(range(max_weeks))]

    print("\n  ═══ 留存矩阵（前8周） ═══")
    header = f"  {'Cohort':<14s}" + "".join(f" W{i:<6d}" for i in range(max_weeks))
    print(header)
    print("  " + "-" * (14 + max_weeks * 8))

    for cohort, row in pivot.iterrows():
        vals = ""
        for w in range(max_weeks):
            v = row.get(w, np.nan)
            if pd.isna(v):
                vals += "   --   "
            else:
                vals += f" {v*100:5.1f}% "
        print(f"  {cohort:<14s}{vals}")
    print("  " + "-" * (14 + max_weeks * 8))


def run():
    _create_table()

    df = build_cohort_matrix()
    if df.empty:
        print("  [Warning] 同期群分析无数据")
        return

    print_retention_matrix(df)

    to_sql_replace(df, "ads_cohort_retention")
    print("  [OK] 留存矩阵已写入 ads_cohort_retention")
