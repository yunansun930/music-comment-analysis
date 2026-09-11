"""
Step4 指标体系 - 统计假设检验

对指标计算结果进行统计检验，为业务结论提供显著性支撑：
  1. t 检验：评论增长率是否显著异于 0
  2. 卡方检验：歌曲活跃天数分布是否均匀
  3. Mann-Whitney U：高热度 vs 低热度歌曲评论数差异
"""
import numpy as np
import pandas as pd
from scipy import stats

from db_helper import read_sql, read_table, execute


def _create_table():
    execute("""
        CREATE TABLE IF NOT EXISTS ads_stat_tests (
            test_id      INT AUTO_INCREMENT PRIMARY KEY COMMENT '检验ID',
            test_name    VARCHAR(128) COMMENT '检验名称',
            test_type    VARCHAR(32)  COMMENT '检验类型: t_test/chi2/mannwhitney',
            metric_name  VARCHAR(64)  COMMENT '检验指标',
            sample_size  INT          COMMENT '样本量',
            statistic    DECIMAL(12,6) COMMENT '统计量',
            p_value      DECIMAL(12,6) COMMENT 'p值',
            effect_size  DECIMAL(12,6) COMMENT '效应量(Cohen d / Cramers V)',
            ci_lower     DECIMAL(12,6) COMMENT '95%置信区间下界',
            ci_upper     DECIMAL(12,6) COMMENT '95%置信区间上界',
            conclusion   VARCHAR(256) COMMENT '结论',
            update_time  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-统计检验结果'
    """)


def _cohen_d(a, b):
    a, b = np.array(a, dtype=float), np.array(b, dtype=float)
    pooled_std = np.sqrt(((len(a)-1)*a.std(ddof=1)**2 + (len(b)-1)*b.std(ddof=1)**2) / (len(a)+len(b)-2))
    if pooled_std == 0:
        return 0.0
    return (a.mean() - b.mean()) / pooled_std


def test_growth_rate_significance():
    """t 检验：评论数日环比增长率是否显著异于 0。"""
    print("\n  [统计检验] t检验: 评论增长率是否显著异于0")

    df = read_table("dws_song_daily")
    if df.empty:
        print("    dws_song_daily 为空，跳过")
        return None

    growth = df["comment_growth_rate"].dropna()
    growth = growth[growth != 0]

    if len(growth) < 5:
        print("    有效样本不足(<5)，跳过")
        return None

    t_stat, p_val = stats.ttest_1samp(growth, popmean=0.0)
    mean_val = growth.mean()
    se = growth.std(ddof=1) / np.sqrt(len(growth))
    ci_lower = mean_val - 1.96 * se
    ci_upper = mean_val + 1.96 * se
    cohen_d_val = mean_val / growth.std(ddof=1) if growth.std(ddof=1) > 0 else 0.0

    conclusion = f"增长率均值={mean_val:.4f}, {'显著' if p_val < 0.05 else '不显著'}(p={p_val:.4f}), 95%CI=[{ci_lower:.4f},{ci_upper:.4f}]"

    print(f"    t={t_stat:.4f}, p={p_val:.4f}, Cohen d={cohen_d_val:.4f}")
    print(f"    {conclusion}")

    return {
        "test_name": "评论增长率是否显著异于0",
        "test_type": "t_test",
        "metric_name": "comment_growth_rate",
        "sample_size": int(len(growth)),
        "statistic": float(t_stat),
        "p_value": float(p_val),
        "effect_size": float(cohen_d_val),
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "conclusion": conclusion,
    }


def test_heat_group_difference():
    """Mann-Whitney U 检验：高热度组 vs 低热度组的评论数是否有显著差异。"""
    print("\n  [统计检验] Mann-Whitney U: 高热度组 vs 低热度组评论数差异")

    df = read_table("dws_song_daily")
    if df.empty:
        print("    dws_song_daily 为空，跳过")
        return None

    song_agg = df.groupby("song_id").agg(
        total_comment=("comment_count", "sum"),
        avg_heat=("heat_score", "mean"),
    ).reset_index()

    median_heat = song_agg["avg_heat"].median()
    high_group = song_agg[song_agg["avg_heat"] >= median_heat]["total_comment"]
    low_group = song_agg[song_agg["avg_heat"] < median_heat]["total_comment"]

    if len(high_group) < 3 or len(low_group) < 3:
        print("    分组样本不足，跳过")
        return None

    u_stat, p_val = stats.mannwhitneyu(high_group, low_group, alternative="two-sided")
    cohen_d_val = _cohen_d(high_group, low_group)

    conclusion = f"高热度组均值={high_group.mean():.1f}, 低热度组均值={low_group.mean():.1f}, {'显著' if p_val < 0.05 else '不显著'}(p={p_val:.4f})"

    print(f"    U={u_stat:.4f}, p={p_val:.4f}, Cohen d={cohen_d_val:.4f}")
    print(f"    {conclusion}")

    return {
        "test_name": "高热度组vs低热度组评论数差异",
        "test_type": "mannwhitney",
        "metric_name": "total_comment_count",
        "sample_size": int(len(high_group) + len(low_group)),
        "statistic": float(u_stat),
        "p_value": float(p_val),
        "effect_size": float(cohen_d_val),
        "ci_lower": 0.0,
        "ci_upper": 0.0,
        "conclusion": conclusion,
    }


def test_sentiment_distribution():
    """卡方检验：正面/负面评论比例是否偏离 50/50 基线。"""
    print("\n  [统计检验] 卡方检验: 正面vs负面评论比例是否偏离50/50")

    try:
        df = read_table("ads_comment_sentiment")
    except Exception:
        print("    ads_comment_sentiment 表不存在，跳过")
        return None

    if df.empty:
        print("    情感数据为空，跳过")
        return None

    pos_count = (df["sentiment"] == "positive").sum()
    neg_count = (df["sentiment"] == "negative").sum()
    total = pos_count + neg_count

    if total < 10:
        print("    正/负面样本不足(<10)，跳过")
        return None

    chi2_stat, p_val = stats.chisquare([pos_count, neg_count], f_exp=[total/2, total/2])
    cramers_v = np.sqrt(chi2_stat / total) if total > 0 else 0.0

    conclusion = f"正面={pos_count}({pos_count/total*100:.1f}%), 负面={neg_count}({neg_count/total*100:.1f}%), {'显著偏离50/50' if p_val < 0.05 else '未显著偏离'}(p={p_val:.4f})"

    print(f"    chi2={chi2_stat:.4f}, p={p_val:.4f}, Cramer V={cramers_v:.4f}")
    print(f"    {conclusion}")

    return {
        "test_name": "正面vs负面评论比例是否偏离50/50",
        "test_type": "chi2",
        "metric_name": "sentiment_positive_negative",
        "sample_size": int(total),
        "statistic": float(chi2_stat),
        "p_value": float(p_val),
        "effect_size": float(cramers_v),
        "ci_lower": 0.0,
        "ci_upper": 0.0,
        "conclusion": conclusion,
    }


def run():
    print("\n[Step4.6] 统计假设检验...")
    _create_table()

    results = []
    for test_fn in [test_growth_rate_significance, test_heat_group_difference, test_sentiment_distribution]:
        try:
            r = test_fn()
            if r:
                results.append(r)
        except Exception as e:
            print(f"  [Warning] {test_fn.__name__} 执行失败: {e}")

    if results:
        execute("TRUNCATE TABLE ads_stat_tests")
        for r in results:
            cols = ", ".join(f"`{k}`" for k in r.keys())
            placeholders = ", ".join(["%s"] * len(r))
            sql = f"INSERT INTO ads_stat_tests ({cols}) VALUES ({placeholders})"
            execute(sql, tuple(r.values()))
        print(f"  [OK] {len(results)} 项统计检验结果已写入 ads_stat_tests")
    else:
        print("  [Warning] 无有效检验结果")

    print("\n  ═══ 统计检验汇总 ═══")
    print(f"  {'检验名称':<30s} {'类型':<14s} {'p值':>8s} {'效应量':>8s} {'结论'}")
    print("  " + "-" * 100)
    for r in results:
        print(f"  {r['test_name']:<30s} {r['test_type']:<14s} {r['p_value']:>8.4f} {r['effect_size']:>8.4f} {'显著' if r['p_value'] < 0.05 else '不显著'}")
    print("  " + "-" * 100)
