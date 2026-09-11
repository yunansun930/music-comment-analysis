"""
Step6 文本分析 - 全局配置
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env():
    """向上查找项目根目录的 .env 文件并加载。"""
    path = Path(__file__).resolve().parent
    for _ in range(3):
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(dotenv_path=env_file)
            return
        path = path.parent


_load_env()

BASE_DIR = Path(__file__).parent.resolve()

# MySQL 连接配置（密码必须从环境变量读取，禁止硬编码）
_DB_PASSWORD = os.getenv("DB_PASSWORD")
if not _DB_PASSWORD:
    raise ValueError("请先设置环境变量 DB_PASSWORD，例如：$env:DB_PASSWORD='你的密码'")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": _DB_PASSWORD,
    "database": os.getenv("DB_NAME", "music_analysis"),
    "charset": "utf8mb4",
}

# LDA 主题数
N_TOPICS = 5

# 每个主题显示的关键词数
TOPIC_N_WORDS = 10

# TF-IDF 每个歌曲提取的关键词数
TFIDF_TOP_N = 20

# BERT 情感分析批量大小
SENTIMENT_BATCH_SIZE = 64

# BERT 情感阈值：二分类模型输出 positive 概率，按阈值映射为三分类
SENTIMENT_THRESHOLDS = {
    "positive": 0.6,
    "negative": 0.4,
}

# 情感分析模型
SENTIMENT_MODEL = "uer/roberta-base-finetuned-jd-binary-chinese"

# jieba 停用词（基础版）
STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个", "上", "也",
    "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好", "自己", "这", "那",
    "啊", "哦", "呢", "吧", "吗", "哈", "哈哈", "呜呜", "呜呜呜", "呜呜呜呜", "了", "的", "地",
    "得", "着", "过", "但", "而", "之", "与", "及", "等", "或", "但是", "因为", "所以", "如果",
    "虽然", "还是", "只是", "这样", "那么", "什么", "怎么", "为什么", "如何", "谁", "哪", "哪个",
    "哪些", "哪里", "那里", "这里", "这个", "那个", "一样", "一般", "一直", "一下", "一些",
    "可以", "可能", "应该", "觉得", "感觉", "真的", "非常", "特别", "比较", "挺", "太", "更",
    "最", "已经", "正在", "曾经", "现在", "当时", "以后", "之前", "之后", "时候", "时间",
    "今天", "明天", "昨天", "每天", "一年", "一直", "一直", "总是", "经常", "偶尔",
    "歌", "歌曲", "音乐", "听", " listeners", "首", "张", "专辑",
}
