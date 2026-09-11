"""
Step6 文本分析 - LDA 主题模型
"""

import pandas as pd
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

from config import N_TOPICS, TOPIC_N_WORDS
from db_helper import to_sql_replace


def run_lda(df: pd.DataFrame):
    """执行 LDA 主题模型并输出主题关键词。"""
    print("\n[Step6.4] 开始 LDA 主题模型分析...")

    corpus = df["tokens_str"].tolist()

    vectorizer = CountVectorizer(max_features=3000)
    doc_term_matrix = vectorizer.fit_transform(corpus)

    lda = LatentDirichletAllocation(
        n_components=N_TOPICS,
        random_state=42,
        max_iter=20,
        learning_method="online",
        n_jobs=-1,
    )
    lda.fit(doc_term_matrix)

    feature_names = vectorizer.get_feature_names_out()

    # 提取每个主题的关键词
    topics = []
    for topic_idx, topic in enumerate(lda.components_):
        top_indices = topic.argsort()[-TOPIC_N_WORDS:][::-1]
        top_words = [feature_names[i] for i in top_indices]
        topics.append({
            "topic_id": topic_idx,
            "topic_name": f"主题{topic_idx + 1}",
            "keywords": ",".join(top_words),
            "keyword_count": len(top_words),
        })

    topics_df = pd.DataFrame(topics)
    print("\n  [LDA 主题结果]")
    for _, row in topics_df.iterrows():
        print(f"    {row['topic_name']}: {row['keywords']}")

    # 为每条评论分配主题
    topic_probs = lda.transform(doc_term_matrix)
    dominant_topics = topic_probs.argmax(axis=1)

    comment_topics = pd.DataFrame({
        "comment_id": df["comment_id"].values,
        "song_id": df["song_id"].values,
        "topic_id": dominant_topics,
        "topic_prob": topic_probs.max(axis=1).round(6),
    })

    # 歌曲主题分布
    song_topic_dist = comment_topics.groupby(["song_id", "topic_id"]).size().reset_index(name="comment_num")
    song_topic_total = song_topic_dist.groupby("song_id")["comment_num"].sum().reset_index(name="total")
    song_topic_dist = pd.merge(song_topic_dist, song_topic_total, on="song_id")
    song_topic_dist["ratio"] = (song_topic_dist["comment_num"] / song_topic_dist["total"]).round(4)
    song_topic_dist = song_topic_dist.drop(columns=["total"])

    to_sql_replace(topics_df, "ads_comment_topic")
    to_sql_replace(comment_topics, "ads_comment_topic_detail")
    to_sql_replace(song_topic_dist, "ads_song_topic_dist")
