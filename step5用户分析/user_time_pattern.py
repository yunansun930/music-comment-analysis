"""
Step5 用户分析 - 行为时间模式分析

从评论时间维度挖掘用户行为节律：
  1. 24 小时分布：每小时评论量 / 回复量 / 获赞量
  2. 周内分布：周一到周日评论量差异
  3. 节假日效应：周末 vs 工作日 / 月份季节效应

写入三张 ADS 表：
  - ads_time_pattern_hourly:  24 行
  - ads_time_pattern_weekday: 7 行
  - ads_time_pattern_monthly: 12 行
"""

import numpy as np
import pandas as pd

from db_helper import read_sql, to_sql_replace, execute


def _create_tables():
    execute("""
        CREATE TABLE IF NOT EXISTS ads_time_pattern_hourly (
            hour            INT PRIMARY KEY COMMENT '小时(0-23)',
            comment_count   INT COMMENT '评论数',
            reply_count     INT COMMENT '回复数',
            like_total      INT COMMENT '获赞总数',
            user_count      INT COMMENT '评论用户数',
            pct             DECIMAL(8,4) COMMENT '占全天评论比例',
            peak_label      VARCHAR(16) COMMENT '时段标签：凌晨/上午/下午/晚上'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-24小时行为分布'
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS ads_time_pattern_weekday (
            weekday         INT PRIMARY KEY COMMENT '星期(0=周一,6=周日)',
            weekday_name    VARCHAR(8) COMMENT '中文星期',
            comment_count   INT COMMENT '评论数',
            reply_count     INT COMMENT '回复数',
            like_total      INT COMMENT '获赞总数',
            user_count      INT COMMENT '评论用户数',
            is_weekend      TINYINT COMMENT '是否周末(1=是,0=否)',
            pct             DECIMAL(8,4) COMMENT '占全周评论比例'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-周内行为分布'
    """)
    execute("""
        CREATE TABLE IF NOT EXISTS ads_time_pattern_monthly (
            month           INT PRIMARY KEY COMMENT '月份(1-12)',
            comment_count   INT COMMENT '评论数',
            reply_count     INT COMMENT '回复数',
            like_total      INT COMMENT '获赞总数',
            user_count      INT COMMENT '评论用户数',
            season          VARCHAR(8) COMMENT '季节：春/夏/秋/冬',
            pct             DECIMAL(8,4) COMMENT '占全年评论比例'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-月度行为分布'
    """)


def _load_comment_time() -> pd.DataFrame:
    """加载评论数据（含 comment_time / reply_count / like_count）。"""
    print("  [时间模式] 读取 dwd_comment_detail...")
    df = read_sql("""
        SELECT
            user_id,
            comment_time,
            like_count,
            reply_count
        FROM dwd_comment_detail
        WHERE comment_time IS NOT NULL
    """)
    df["comment_time"] = pd.to_datetime(df["comment_time"], errors="coerce")
    df = df.dropna(subset=["comment_time"])
    df["like_count"] = df["like_count"].fillna(0).astype(int)
    df["reply_count"] = df["reply_count"].fillna(0).astype(int)
    print(f"    有效评论数: {len(df):,}")
    return df


def _analyze_hourly(df: pd.DataFrame) -> pd.DataFrame:
    """24 小时分布。"""
    print("\n  [时间模式] 24 小时分布...")

    df = df.copy()
    df["hour"] = df["comment_time"].dt.hour

    agg = df.groupby("hour").agg(
        comment_count=("user_id", "count"),
        reply_count=("reply_count", "sum"),
        like_total=("like_count", "sum"),
        user_count=("user_id", "nunique"),
    ).reset_index()

    total = agg["comment_count"].sum()
    agg["pct"] = (agg["comment_count"] / total).round(4)

    def _label(h):
        if 0 <= h < 6:
            return "凌晨"
        elif 6 <= h < 12:
            return "上午"
        elif 12 <= h < 18:
            return "下午"
        else:
            return "晚上"
    agg["peak_label"] = agg["hour"].apply(_label)

    peak_hour = int(agg.loc[agg["comment_count"].idxmax(), "hour"])
    low_hour = int(agg.loc[agg["comment_count"].idxmin(), "hour"])
    print(f"    高峰时段: {peak_hour:02d}:00 ({agg['comment_count'].max():,} 条)")
    print(f"    低谷时段: {low_hour:02d}:00 ({agg['comment_count'].min():,} 条)")
    return agg


def _analyze_weekday(df: pd.DataFrame) -> pd.DataFrame:
    """周内分布。"""
    print("\n  [时间模式] 周内分布...")

    df = df.copy()
    df["weekday"] = df["comment_time"].dt.weekday  # 0=Monday, 6=Sunday

    agg = df.groupby("weekday").agg(
        comment_count=("user_id", "count"),
        reply_count=("reply_count", "sum"),
        like_total=("like_count", "sum"),
        user_count=("user_id", "nunique"),
    ).reset_index()

    total = agg["comment_count"].sum()
    agg["pct"] = (agg["comment_count"] / total).round(4)
    agg["is_weekend"] = (agg["weekday"] >= 5).astype(int)
    agg["weekday_name"] = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

    weekend_count = agg[agg["is_weekend"] == 1]["comment_count"].sum()
    weekday_count = agg[agg["is_weekend"] == 0]["comment_count"].sum()
    weekend_avg = weekend_count / 2
    weekday_avg = weekday_count / 5
    ratio = weekend_avg / weekday_avg if weekday_avg > 0 else 0
    print(f"    周末日均评论: {weekend_avg:,.0f} 条")
    print(f"    工作日日均评论: {weekday_avg:,.0f} 条")
    print(f"    周末/工作日活跃比: {ratio:.2f}x")

    peak_day = int(agg.loc[agg["comment_count"].idxmax(), "weekday"])
    print(f"    评论最多: {agg.loc[peak_day, 'weekday_name']} ({agg['comment_count'].max():,} 条)")
    return agg


def _analyze_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """月度分布 + 季节标签。"""
    print("\n  [时间模式] 月度分布...")

    df = df.copy()
    df["month"] = df["comment_time"].dt.month

    agg = df.groupby("month").agg(
        comment_count=("user_id", "count"),
        reply_count=("reply_count", "sum"),
        like_total=("like_count", "sum"),
        user_count=("user_id", "nunique"),
    ).reset_index()

    total = agg["comment_count"].sum()
    agg["pct"] = (agg["comment_count"] / total).round(4)

    def _season(m):
        if m in [3, 4, 5]:
            return "春"
        elif m in [6, 7, 8]:
            return "夏"
        elif m in [9, 10, 11]:
            return "秋"
        else:
            return "冬"
    agg["season"] = agg["month"].apply(_season)

    peak_month = int(agg.loc[agg["comment_count"].idxmax(), "month"])
    print(f"    评论高峰月: {peak_month} 月 ({agg['comment_count'].max():,} 条)")
    season_dist = agg.groupby("season")["comment_count"].sum()
    print(f"    季节分布: {dict(season_dist)}")
    return agg


def run():
    print("\n[Step5.5] 行为时间模式分析...")

    _create_tables()
    df = _load_comment_time()

    hourly = _analyze_hourly(df)
    weekday = _analyze_weekday(df)
    monthly = _analyze_monthly(df)

    to_sql_replace(hourly, "ads_time_pattern_hourly")
    to_sql_replace(weekday, "ads_time_pattern_weekday")
    to_sql_replace(monthly, "ads_time_pattern_monthly")

    print("\n[OK] 行为时间模式分析完成")
    print("  - ads_time_pattern_hourly: 24 行")
    print("  - ads_time_pattern_weekday: 7 行")
    print("  - ads_time_pattern_monthly: 12 行")
