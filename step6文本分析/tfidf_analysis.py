"""
Step6 文本分析 - TF-IDF 热门关键词提取
"""

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from db_helper import to_sql_replace


def extract_global_keywords(df: pd.DataFrame, top_n: int = 100) -> pd.DataFrame:
    """提取全局热门关键词。"""
    print("\n[Step6.2] 开始 TF-IDF 全局关键词提取...")

    corpus = df["tokens_str"].tolist()

    vectorizer = TfidfVectorizer(max_features=5000)
    tfidf_matrix = vectorizer.fit_transform(corpus)

    feature_names = vectorizer.get_feature_names_out()
    scores = tfidf_matrix.sum(axis=0).A1

    keywords = pd.DataFrame({
        "word": feature_names,
        "score": scores,
    }).sort_values("score", ascending=False).head(top_n).reset_index(drop=True)

    keywords["keyword_rank"] = keywords.index + 1
    keywords = keywords[["keyword_rank", "word", "score"]]

    print(f"  提取全局关键词 {len(keywords)} 个")
    return keywords


def extract_song_keywords(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """按歌曲提取 TF-IDF 关键词。"""
    print("\n[Step6.3] 开始按歌曲提取 TF-IDF 关键词...")

    results = []
    grouped = df.groupby("song_id")
    total = grouped.ngroups

    for idx, (song_id, group) in enumerate(grouped, 1):
        if len(group) < 3:
            continue

        corpus = group["tokens_str"].tolist()
        vectorizer = TfidfVectorizer(max_features=100)
        tfidf_matrix = vectorizer.fit_transform(corpus)

        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.sum(axis=0).A1

        song_keywords = pd.DataFrame({
            "word": feature_names,
            "score": scores,
        }).sort_values("score", ascending=False).head(top_n)

        for rank, row in enumerate(song_keywords.itertuples(), 1):
            results.append({
                "song_id": song_id,
                "keyword_rank": rank,
                "word": row.word,
                "score": round(row.score, 6),
            })

        if idx % 50 == 0 or idx == total:
            print(f"  已处理 {idx}/{total} 首歌曲", flush=True)

    result_df = pd.DataFrame(results)
    print(f"  共提取 {len(result_df)} 条歌曲关键词")
    return result_df


def run_tfidf(df: pd.DataFrame):
    """执行 TF-IDF 分析并写入数据库。"""
    global_keywords = extract_global_keywords(df)
    song_keywords = extract_song_keywords(df)

    to_sql_replace(global_keywords, "ads_global_keywords")
    to_sql_replace(song_keywords, "ads_song_keywords")
