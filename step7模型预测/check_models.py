"""
Step7 模型预测 - 结果检查
"""
import pandas as pd
from db_helper import read_table


def main():
    print("=" * 60)
    print("Step7 模型预测 - 结果检查")
    print("=" * 60)
    print()

    tables = {
        "ads_hot_predict": "爆款预测结果",
        "ads_model_metrics": "模型评估指标",
        "ads_feature_importance": "特征重要性",
        "ads_song_forecast": "热度趋势预测",
    }

    print("[各结果表数据量]")
    for table, desc in tables.items():
        try:
            df = read_table(table)
            print(f"  {table:30s}: {len(df):>6d} 条 ({desc})")
        except Exception as e:
            print(f"  {table:30s}: 读取失败 - {e}")
    print()

    # 模型指标
    print("[模型评估指标]")
    try:
        metrics = read_table("ads_model_metrics")
        print(metrics.to_string(index=False))
    except Exception as e:
        print(f"  读取失败: {e}")
    print()

    # 特征重要性 TOP 10
    print("[特征重要性 TOP 10]")
    try:
        importance = read_table("ads_feature_importance").head(10)
        print(importance.to_string(index=False))
    except Exception as e:
        print(f"  读取失败: {e}")
    print()

    # 爆款预测 TOP 10
    print("[预测爆款概率 TOP 10]")
    try:
        hot = read_table("ads_hot_predict").sort_values("hot_prob", ascending=False).head(10)
        print(hot[["song_id", "actual_comment_count", "hot_prob", "is_hot_predicted"]].to_string(index=False))
    except Exception as e:
        print(f"  读取失败: {e}")
    print()

    print("[检查完成]")


if __name__ == "__main__":
    main()
