"""
Step7 模型预测 - 一键运行入口

改进点：统一日志框架（logging），输出含时间戳/级别/模块
"""
import logging
import sys

from features import build_features
from hot_song_predict import train_models, save_hot_predict_results
from time_series_forecast import build_forecast
import churn_predict


def setup_logging():
    """统一日志配置：输出到 stdout，格式 含时间戳/级别/模块。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def main():
    setup_logging()
    log = logging.getLogger("step7")
    log.info("=" * 60)
    log.info("Step7 模型预测 - 爆款预测 / 时序预测 / 用户流失预测")
    log.info("=" * 60)

    # 1. 特征工程
    log.info("[Step7.1] 开始构建爆款预测特征...")
    df = build_features()
    hot_count = df["label"].sum()
    log.info("  [特征工程] 共 %d 首歌曲", len(df))
    log.info("  [标签] 复合热度 Top 10%% 为爆款，共 %d 首 (%.1f%%)",
             int(hot_count), hot_count / len(df) * 100)

    # 2. 爆款歌曲预测
    log.info("[Step7.2] 训练爆款歌曲预测模型...")
    df_result, metrics, importance = train_models(df)

    # 3. 保存爆款预测结果
    log.info("[Step7.3] 生成爆款预测结果...")
    save_hot_predict_results(df_result, metrics, importance)

    # 4. 时间序列热度预测
    log.info("[Step7.4] 开始时间序列热度预测...")
    build_forecast()

    # 5. 用户流失预测
    log.info("[Step7.5] 训练用户流失预测模型...")
    churn_predict.run()

    log.info("=" * 60)
    log.info("Step7 模型预测完成")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
