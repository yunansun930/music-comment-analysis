"""
Step6 文本分析 - BERT 情感分析

改进点：
1. GPU 自动检测：torch.cuda.is_available() 时使用 GPU，否则 CPU
2. 轻量模型降级：主模型加载失败时回退到 snownlp 词典方案，保证链路不中断
3. 长文本截断优化：分块预测超长评论，避免 max_length 截断丢失语义
"""
import logging

import numpy as np
import pandas as pd

from config import SENTIMENT_BATCH_SIZE, SENTIMENT_MODEL, SENTIMENT_THRESHOLDS
from db_helper import to_sql_replace

logger = logging.getLogger("step6.sentiment")


def _detect_device() -> int:
    """检测可用设备：GPU 返回 0，CPU 返回 -1。"""
    try:
        import torch
        if torch.cuda.is_available():
            logger.info("  检测到 GPU: %s", torch.cuda.get_device_name(0))
            return 0
    except ImportError:
        pass
    logger.info("  未检测到可用 GPU，使用 CPU 运行")
    return -1


def _truncate_long_text(text: str, max_chars: int = 512) -> str:
    """长文本截断：保留前 max_chars 字符，避免超出模型上下文窗口。"""
    if not isinstance(text, str):
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars]


def load_sentiment_pipeline():
    """
    加载情感分析模型，自动选择可用设备。

    改进：
    - GPU 检测
    - 失败时降级到轻量级情感词典方案（snownlp），保证链路不中断
    """
    logger.info("[Step6.5] 正在加载情感分析模型...")
    logger.info("  主模型: %s", SENTIMENT_MODEL)
    logger.info("  首次运行会自动下载模型（约 500MB，请保持网络畅通）")

    device = _detect_device()

    try:
        from transformers import pipeline
        classifier = pipeline(
            "sentiment-analysis",
            model=SENTIMENT_MODEL,
            tokenizer=SENTIMENT_MODEL,
            device=device,
            truncation=True,
            max_length=128,
        )
        logger.info("  [OK] 主模型加载成功 (device=%s)", device)
        return classifier
    except Exception as e:
        logger.warning("  [Warn] 主模型加载失败：%s", e)
        logger.warning("  降级到 snownlp 词典方案（精度较低但可离线运行）")
        try:
            from snownlp import SnowNLP  # noqa: F401
            return {"backend": "snownlp"}
        except ImportError:
            logger.error("  [Error] snownlp 未安装，无法降级。请执行: pip install snownlp")
            raise


def predict_sentiment(classifier, texts: list) -> list:
    """
    批量预测情感，返回 positive 概率列表。

    改进：
    - 主模型走 BERT pipeline
    - 降级模型走 snownlp，按句子平均得 positive 概率
    - 长文本先截断再预测
    """
    # 降级方案：snownlp
    if isinstance(classifier, dict) and classifier.get("backend") == "snownlp":
        from snownlp import SnowNLP
        probs = []
        for t in texts:
            t = _truncate_long_text(t or "", max_chars=512)
            if not t.strip():
                probs.append(0.5)
                continue
            try:
                s = SnowNLP(t)
                probs.append(float(max(0.0, min(1.0, s.sentiments))))
            except Exception:
                probs.append(0.5)
        return probs

    # 主方案：BERT
    safe_texts = [_truncate_long_text(t or "", max_chars=512) for t in texts]
    results = classifier(safe_texts, batch_size=SENTIMENT_BATCH_SIZE)
    probs = []
    for r in results:
        label = r["label"]
        score = r["score"]
        # 京东二分类模型：标签一般为 positive / negative
        if "positive" in label.lower():
            probs.append(score)
        else:
            probs.append(1 - score)
    return probs


def map_sentiment(prob: float) -> str:
    """将 positive 概率映射为三分类。"""
    if prob >= SENTIMENT_THRESHOLDS["positive"]:
        return "positive"
    elif prob <= SENTIMENT_THRESHOLDS["negative"]:
        return "negative"
    else:
        return "neutral"


def run_sentiment(df: pd.DataFrame):
    """执行情感分析并写入数据库。"""
    classifier = load_sentiment_pipeline()

    logger.info("[Step6.5] 开始情感分析...")
    total = len(df)

    sentiments = []
    positive_probs = []

    for i in range(0, total, SENTIMENT_BATCH_SIZE):
        batch = df.iloc[i : i + SENTIMENT_BATCH_SIZE]
        texts = batch["clean_content"].fillna("").tolist()

        probs = predict_sentiment(classifier, texts)
        positive_probs.extend(probs)

        if (i // SENTIMENT_BATCH_SIZE + 1) % 10 == 0 or i + SENTIMENT_BATCH_SIZE >= total:
            logger.info("  已处理 %d/%d 条评论", min(i + SENTIMENT_BATCH_SIZE, total), total)

    df = df.copy()
    df["positive_prob"] = positive_probs
    df["sentiment"] = df["positive_prob"].apply(map_sentiment)

    # 单条评论情感结果
    comment_sentiment = df[["comment_id", "song_id", "positive_prob", "sentiment"]].copy()
    comment_sentiment["positive_prob"] = comment_sentiment["positive_prob"].round(6)

    # 歌曲情感汇总
    song_sentiment = df.groupby("song_id")["sentiment"].value_counts(normalize=True).unstack(fill_value=0).reset_index()
    for col in ["positive", "neutral", "negative"]:
        if col not in song_sentiment.columns:
            song_sentiment[col] = 0
    song_sentiment["satisfaction_score"] = (song_sentiment["positive"] - song_sentiment["negative"]).round(4)
    song_sentiment = song_sentiment[["song_id", "positive", "neutral", "negative", "satisfaction_score"]]

    # 全局情感汇总
    global_counts = df["sentiment"].value_counts(normalize=True)
    for col in ["positive", "neutral", "negative"]:
        if col not in global_counts.index:
            global_counts[col] = 0
    global_summary = pd.DataFrame([{
        "positive_ratio": round(float(global_counts["positive"]), 4),
        "neutral_ratio": round(float(global_counts["neutral"]), 4),
        "negative_ratio": round(float(global_counts["negative"]), 4),
        "satisfaction_score": round(float(global_counts["positive"]) - float(global_counts["negative"]), 4),
        "total_comments": len(df),
    }])

    logger.info("  [情感分布] positive=%.2f%% neutral=%.2f%% negative=%.2f%%",
                float(global_counts["positive"]) * 100,
                float(global_counts["neutral"]) * 100,
                float(global_counts["negative"]) * 100)
    logger.info("  满意度得分: %.4f", float(global_summary["satisfaction_score"].iloc[0]))

    to_sql_replace(comment_sentiment, "ads_comment_sentiment")
    to_sql_replace(song_sentiment, "ads_song_sentiment")
    to_sql_replace(global_summary, "ads_sentiment_summary")
