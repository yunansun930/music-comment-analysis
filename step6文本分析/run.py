"""
Step6 文本分析 - 主运行入口

改进点：统一日志框架（logging），输出含时间戳/级别/模块
运行命令：
    python -u run.py
"""
import logging
import sys

from config import DB_CONFIG  # noqa: F401  保留以兼容外部调用
from db_helper import ensure_table, read_table
from text_preprocessing import preprocess_comments
from tfidf_analysis import run_tfidf
from lda_analysis import run_lda
from sentiment_analysis import run_sentiment


def setup_logging():
    """统一日志配置：输出到 stdout，格式 含时间戳/级别/模块。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS ads_global_keywords (
    keyword_rank  INT COMMENT '排名',
    word          VARCHAR(64) COMMENT '关键词',
    score         DECIMAL(12,6) COMMENT 'TF-IDF 分数',
    update_time   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-全局热门关键词';

CREATE TABLE IF NOT EXISTS ads_song_keywords (
    song_id      BIGINT COMMENT '歌曲ID',
    keyword_rank INT COMMENT '排名',
    word         VARCHAR(64) COMMENT '关键词',
    score        DECIMAL(12,6) COMMENT 'TF-IDF 分数',
    update_time  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_song_id (song_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-歌曲热门关键词';

CREATE TABLE IF NOT EXISTS ads_comment_topic (
    topic_id      INT COMMENT '主题ID',
    topic_name    VARCHAR(32) COMMENT '主题名称',
    keywords      VARCHAR(500) COMMENT '主题关键词',
    keyword_count INT COMMENT '关键词数量',
    update_time   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-评论主题表';

CREATE TABLE IF NOT EXISTS ads_comment_topic_detail (
    comment_id  BIGINT COMMENT '评论ID',
    song_id     BIGINT COMMENT '歌曲ID',
    topic_id    INT COMMENT '主题ID',
    topic_prob  DECIMAL(10,6) COMMENT '主题概率',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_comment_id (comment_id),
    KEY idx_song_id (song_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-评论主题明细';

CREATE TABLE IF NOT EXISTS ads_song_topic_dist (
    song_id      BIGINT COMMENT '歌曲ID',
    topic_id     INT COMMENT '主题ID',
    comment_num  INT COMMENT '评论数',
    ratio        DECIMAL(10,4) COMMENT '占比',
    update_time  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_song_id (song_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-歌曲主题分布';

CREATE TABLE IF NOT EXISTS ads_comment_sentiment (
    comment_id    BIGINT COMMENT '评论ID',
    song_id       BIGINT COMMENT '歌曲ID',
    positive_prob DECIMAL(10,6) COMMENT '正面情感概率',
    sentiment     VARCHAR(16) COMMENT '情感类别：positive/neutral/negative',
    update_time   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_comment_id (comment_id),
    KEY idx_song_id (song_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-评论情感明细';

CREATE TABLE IF NOT EXISTS ads_song_sentiment (
    song_id            BIGINT COMMENT '歌曲ID',
    positive           DECIMAL(10,4) COMMENT '正面占比',
    neutral            DECIMAL(10,4) COMMENT '中性占比',
    negative           DECIMAL(10,4) COMMENT '负面占比',
    satisfaction_score DECIMAL(10,4) COMMENT '满意度得分',
    update_time        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    KEY idx_song_id (song_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-歌曲情感汇总';

CREATE TABLE IF NOT EXISTS ads_sentiment_summary (
    positive_ratio     DECIMAL(10,4) COMMENT '正面占比',
    neutral_ratio      DECIMAL(10,4) COMMENT '中性占比',
    negative_ratio     DECIMAL(10,4) COMMENT '负面占比',
    satisfaction_score DECIMAL(10,4) COMMENT '满意度得分',
    total_comments     INT COMMENT '总评论数',
    update_time        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-全局情感汇总';
"""


def main():
    setup_logging()
    log = logging.getLogger("step6")
    log.info("=" * 60)
    log.info("Step6 文本分析 - TF-IDF / LDA / BERT 情感分析")
    log.info("=" * 60)

    # 1. 确保结果表存在
    log.info("[Step6.0] 检查并创建结果表...")
    ensure_table(CREATE_TABLE_SQL)
    log.info("  [OK] 结果表已就绪")

    # 2. 读取评论数据
    log.info("[Step6.0] 读取评论数据...")
    comment_df = read_table("dwd_comment_detail")
    log.info("  [OK] 读取 %d 条评论", len(comment_df))

    # 3. 文本预处理
    processed_df = preprocess_comments(comment_df)

    # 4. TF-IDF 分析
    run_tfidf(processed_df)

    # 5. LDA 主题模型
    run_lda(processed_df)

    # 6. BERT 情感分析
    run_sentiment(processed_df)

    log.info("=" * 60)
    log.info("文本分析完成")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
