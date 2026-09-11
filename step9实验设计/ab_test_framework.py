"""
Step9 实验设计 - A/B 测试框架

模拟实验：假设对 Top 热门歌曲推送通知，对比推送组 vs 对照组的评论数变化。
展示完整实验设计能力：样本量计算 → 分组 → 检验 → 效应量 → 置信区间。

注意：此模块为模拟实验，展示的是实验设计方法论，非真实业务结论。
"""
import numpy as np
import pandas as pd
from scipy import stats

from config import AB_TEST_CONFIG
from db_helper import read_sql, execute


def _create_table():
    execute("""
        CREATE TABLE IF NOT EXISTS ads_ab_test_results (
            test_id        INT AUTO_INCREMENT PRIMARY KEY COMMENT '检验ID',
            test_name      VARCHAR(128) COMMENT '实验名称',
            metric_name    VARCHAR(64)  COMMENT '核心指标',
            control_mean   DECIMAL(12,6) COMMENT '对照组均值',
            treatment_mean DECIMAL(12,6) COMMENT '实验组均值',
            lift_ratio     DECIMAL(8,4)  COMMENT '相对提升率',
            sample_size    INT           COMMENT '每组样本量',
            statistic      DECIMAL(12,6) COMMENT '统计量',
            p_value        DECIMAL(12,6) COMMENT 'p值',
            effect_size    DECIMAL(12,6) COMMENT 'Cohen d效应量',
            ci_lower       DECIMAL(12,6) COMMENT '95%CI下界(提升率)',
            ci_upper       DECIMAL(12,6) COMMENT '95%CI上界(提升率)',
            is_significant TINYINT       COMMENT '是否显著(1=显著,0=不显著)',
            conclusion     VARCHAR(512) COMMENT '结论',
            update_time    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-A/B测试结果'
    """)


def calc_sample_size(baseline_mean, baseline_std, mde_ratio=0.10, alpha=0.05, power=0.80):
    """
    计算最小样本量。
    MDE: 最小可检测效应（基线均值的 10% 提升）
    """
    from statsmodels.stats.power import tt_solve_power

    effect_size = (baseline_mean * mde_ratio) / baseline_std
    n = tt_solve_power(effect_size=effect_size, alpha=alpha, power=power, alternative="two-sided")

    print(f"\n  [样本量计算]")
    print(f"    基线均值: {baseline_mean:.2f}")
    print(f"    基线标准差: {baseline_std:.2f}")
    print(f"    MDE(最小可检测效应): {mde_ratio*100:.0f}% 提升 = {baseline_mean*mde_ratio:.2f}")
    print(f"    显著性水平 alpha: {alpha}")
    print(f"    统计功效 power: {power}")
    print(f"    最小样本量(每组): {int(np.ceil(n))} 人")

    return int(np.ceil(n))


def simulate_experiment():
    """
    模拟 A/B 实验：推送通知 vs 不推送，对比评论数变化。
    用真实评论数据作为基线，通过 bootstrap 模拟实验组和对照组。
    """
    print("\n[Step9.1] A/B 实验设计（模拟）")
    print("  实验假设: 对热门歌曲推送通知能提升用户评论数")
    print("  分组方式: 随机分组 50/50")

    df = read_sql("""
        SELECT user_id, COUNT(*) AS comment_count
        FROM dwd_comment_detail
        GROUP BY user_id
    """)

    if df.empty:
        print("  评论数据为空，无法模拟实验")
        return None

    rng = np.random.RandomState(AB_TEST_CONFIG["random_state"])
    comment_counts = df["comment_count"].values
    baseline_mean = comment_counts.mean()
    baseline_std = comment_counts.std()

    n_per_group = calc_sample_size(
        baseline_mean, baseline_std,
        mde_ratio=AB_TEST_CONFIG["mde_ratio"],
        alpha=AB_TEST_CONFIG["alpha"],
        power=AB_TEST_CONFIG["power"],
    )

    n_actual = min(n_per_group, len(comment_counts) // 2)
    if n_actual < 10:
        print(f"  样本不足(n={n_actual})，跳过")
        return None

    control_idx = rng.choice(len(comment_counts), size=n_actual, replace=False)
    remaining_idx = np.setdiff1d(np.arange(len(comment_counts)), control_idx)
    treatment_idx = rng.choice(remaining_idx, size=n_actual, replace=False)

    control = comment_counts[control_idx].astype(float)
    treatment = comment_counts[treatment_idx].astype(float)

    treatment_lift = rng.normal(
        loc=baseline_mean * AB_TEST_CONFIG["mde_ratio"] * 0.5,
        scale=baseline_std * 0.3,
        size=n_actual,
    )
    treatment = treatment + treatment_lift
    treatment = np.maximum(treatment, 0)

    print(f"\n  [实验执行]")
    print(f"    对照组: {n_actual} 人, 平均评论数={control.mean():.2f}")
    print(f"    实验组: {n_actual} 人, 平均评论数={treatment.mean():.2f}")

    lift = (treatment.mean() - control.mean()) / control.mean()

    t_stat, p_val = stats.ttest_ind(treatment, control, equal_var=False)

    diff = treatment - control
    se_diff = diff.std(ddof=1) / np.sqrt(len(diff))
    ci_lower = lift - 1.96 * se_diff / control.mean()
    ci_upper = lift + 1.96 * se_diff / control.mean()

    pooled_std = np.sqrt(((len(control)-1)*control.std(ddof=1)**2 + (len(treatment)-1)*treatment.std(ddof=1)**2) / (len(control)+len(treatment)-2))
    cohen_d = (treatment.mean() - control.mean()) / pooled_std if pooled_std > 0 else 0.0

    is_sig = 1 if p_val < AB_TEST_CONFIG["alpha"] else 0
    conclusion = (
        f"实验组评论数 {'显著高于' if is_sig else '未显著高于'} 对照组 "
        f"(提升 {lift*100:.2f}%, p={p_val:.4f}, "
        f"95%CI=[{ci_lower*100:.2f}%, {ci_upper*100:.2f}%], "
        f"Cohen d={cohen_d:.4f})"
    )

    print(f"\n  [统计检验]")
    print(f"    t={t_stat:.4f}, p={p_val:.4f}")
    print(f"    相对提升: {lift*100:.2f}%")
    print(f"    95%CI: [{ci_lower*100:.2f}%, {ci_upper*100:.2f}%]")
    print(f"    Cohen d: {cohen_d:.4f}")
    print(f"    结论: {conclusion}")

    result = {
        "test_name": "推送通知对评论数的影响(模拟)",
        "metric_name": "comment_count",
        "control_mean": float(control.mean()),
        "treatment_mean": float(treatment.mean()),
        "lift_ratio": float(lift),
        "sample_size": int(n_actual),
        "statistic": float(t_stat),
        "p_value": float(p_val),
        "effect_size": float(cohen_d),
        "ci_lower": float(ci_lower),
        "ci_upper": float(ci_upper),
        "is_significant": is_sig,
        "conclusion": conclusion,
    }

    return result


def run():
    print("=" * 60)
    print("Step9 实验设计 - A/B 测试框架")
    print("=" * 60)

    _create_table()

    result = simulate_experiment()
    if result is None:
        print("  [Warning] 实验未完成")
        return

    execute("TRUNCATE TABLE ads_ab_test_results")
    cols = ", ".join(f"`{k}`" for k in result.keys())
    placeholders = ", ".join(["%s"] * len(result))
    sql = f"INSERT INTO ads_ab_test_results ({cols}) VALUES ({placeholders})"
    execute(sql, tuple(result.values()))

    print("\n  [OK] A/B 测试结果已写入 ads_ab_test_results")

    print("\n  ═══ 实验报告 ═══")
    print(f"  实验名称: {result['test_name']}")
    print(f"  核心指标: {result['metric_name']}")
    print(f"  对照组均值: {result['control_mean']:.4f}")
    print(f"  实验组均值: {result['treatment_mean']:.4f}")
    print(f"  相对提升: {result['lift_ratio']*100:.2f}%")
    print(f"  p值: {result['p_value']:.4f}")
    print(f"  95%CI: [{result['ci_lower']*100:.2f}%, {result['ci_upper']*100:.2f}%]")
    print(f"  Cohen d: {result['effect_size']:.4f}")
    print(f"  结论: {result['conclusion']}")
    print("=" * 60)
