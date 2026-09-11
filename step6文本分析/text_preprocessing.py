"""
Step6 文本分析 - 文本预处理
"""

import re

import jieba
import pandas as pd

from config import STOPWORDS


def clean_text(text: str) -> str:
    """清洗评论文本。"""
    if not isinstance(text, str):
        return ""

    # 去除 URL
    text = re.sub(r"https?://\S+|www\.\S+", "", text)
    # 去除 @用户名
    text = re.sub(r"@[\w\u4e00-\u9fa5]+", "", text)
    # 去除话题标签符号，保留内容
    text = re.sub(r"#", "", text)
    # 去除纯数字、纯英文过短、特殊符号
    text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9，。！？；：""''（）]", " ", text)
    # 合并连续空格
    text = re.sub(r"\s+", " ", text).strip()

    return text


def tokenize(text: str) -> list:
    """分词并去除停用词。"""
    text = clean_text(text)
    if not text:
        return []

    words = jieba.lcut(text)
    words = [w.strip() for w in words if w.strip()]
    words = [w for w in words if len(w) > 1 or re.match(r"[\u4e00-\u9fa5]", w)]
    words = [w for w in words if w.lower() not in STOPWORDS]

    return words


def preprocess_comments(df: pd.DataFrame) -> pd.DataFrame:
    """对评论数据进行预处理。"""
    print("\n[Step6.1] 开始文本预处理...")

    df = df[["comment_id", "song_id", "user_id", "content", "like_count", "comment_time"]].copy()
    df["content"] = df["content"].fillna("").astype(str)

    # 清洗文本
    df["clean_content"] = df["content"].apply(clean_text)

    # 分词
    df["tokens"] = df["content"].apply(tokenize)
    df["tokens_str"] = df["tokens"].apply(lambda x: " ".join(x))

    # 过滤空分词
    df = df[df["tokens"].apply(len) > 0].reset_index(drop=True)

    print(f"  预处理后有效评论数: {len(df)}")
    return df
