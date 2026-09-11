"""
Step3 数据清洗 - 主运行入口

改进点：统一日志框架（logging），输出含时间戳、级别、模块名
运行命令：
    python run.py
"""
import logging
import sys

import clean_comment
import clean_user
import clean_song
import clean_behavior


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
    log = logging.getLogger("step3")
    log.info("=" * 60)
    log.info("Step3 数据清洗")
    log.info("=" * 60)

    # 建议按依赖顺序执行：先清洗评论、用户、歌曲，最后行为
    clean_comment.run()
    clean_user.run()
    clean_song.run()
    clean_behavior.run()

    log.info("=" * 60)
    log.info("数据清洗完成")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
