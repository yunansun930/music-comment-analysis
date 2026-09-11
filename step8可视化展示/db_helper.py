"""
Step8 可视化展示 - 数据访问层（安全 + 缓存 + 兜底）

改进点：
1. 表名白名单校验，杜绝 SQL 注入
2. 所有动态参数走 SQLAlchemy text() + params 绑定
3. 统一 try/except，失败时返回空 DataFrame 而非崩溃页面
4. @st.cache_data(ttl=300) 缓存高频查询，降低数据库压力
"""
import logging
from typing import Optional

import numpy as np
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from config import DB_CONFIG

logger = logging.getLogger("step8.db_helper")

# 允许读取的表名白名单，杜绝 SQL 注入
ALLOWED_TABLES = {
    "dwd_user_info",
    "dwd_song_info",
    "dwd_artist_info",
    "dwd_comment_detail",
    "dws_song_daily",
    "dws_artist_daily",
    "dws_user_daily",
    "ads_user_portrait",
    "ads_song_metrics",
    "ads_song_keywords",
    "ads_song_sentiment",
    "ads_comment_sentiment",
    "ads_comment_topic",
    "ads_comment_topic_detail",
    "ads_song_topic_dist",
    "ads_global_keywords",
    "ads_sentiment_summary",
    "ads_hot_predict",
    "ads_song_forecast",
    "ads_model_metrics",
    "ads_feature_importance",
}

_EMPTY_DF = pd.DataFrame()


def build_engine():
    """创建 SQLAlchemy engine。"""
    url = (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        f"?charset={DB_CONFIG['charset']}"
    )
    return create_engine(url)


def _execute_read(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    """执行查询，捕获异常返回空 DataFrame。"""
    try:
        engine = build_engine()
        try:
            return pd.read_sql(text(query), engine, params=params or {})
        finally:
            engine.dispose()
    except SQLAlchemyError as e:
        logger.exception("查询失败: %s | params=%s", query, params)
        st.error(f"数据库查询失败，已展示空数据：{e.__class__.__name__}")
        return _EMPTY_DF.copy()
    except Exception as e:  # noqa: BLE001  兜底，保证页面不崩
        logger.exception("未知查询错误: %s", query)
        st.error(f"查询发生未知错误：{e.__class__.__name__}")
        return _EMPTY_DF.copy()


def read_table(table_name: str) -> pd.DataFrame:
    """读取整张表（表名走白名单校验）。"""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table_name}")
    return _execute_read(f"SELECT * FROM {table_name}")


def read_sql(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    """执行参数化 SQL 查询。推荐使用 :name 占位符 + params 字典。"""
    return _execute_read(query, params)


# ==================== 缓存层 ====================
# 所有高频查询走缓存，TTL=5 分钟，降低数据库压力


@st.cache_data(ttl=300, show_spinner=False)
def cached_read_sql(query: str, _cache_key: str = "") -> pd.DataFrame:
    """缓存版查询：query 必须为静态 SQL，_cache_key 用于区分调用点。"""
    return _execute_read(query)


@st.cache_data(ttl=300, show_spinner=False)
def cached_count(table_name: str) -> int:
    """缓存表行数。"""
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table_name}")
    df = _execute_read(f"SELECT COUNT(*) AS cnt FROM {table_name}")
    if df.empty:
        return 0
    return int(df["cnt"].iloc[0])


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_interaction_rate() -> float:
    """缓存评论获赞率（评论获赞数 / 评论数）。"""
    df = _execute_read(
        """
        SELECT
            SUM(like_count) AS like_cnt,
            COUNT(*) AS comment_cnt
        FROM dwd_comment_detail
        """
    )
    if df.empty:
        return 0.0
    comments = max(int(df["comment_cnt"].iloc[0]), 1)
    likes = int(df["like_cnt"].iloc[0] or 0)
    return likes / comments


@st.cache_data(ttl=300, show_spinner=False)
def cached_total_comments() -> int:
    """缓存总评论数（直接查询评论明细表）。"""
    df = _execute_read("SELECT COUNT(*) AS total FROM dwd_comment_detail")
    if df.empty:
        return 0
    return int(df["total"].iloc[0] or 0)


@st.cache_data(ttl=300, show_spinner=False)
def cached_home_trend(start_dt: str) -> pd.DataFrame:
    """缓存首页 30 天热度趋势。"""
    return _execute_read(
        """
        SELECT
            dt,
            SUM(heat_score) AS total_heat,
            SUM(comment_count) AS total_comment,
            SUM(reply_count) AS total_reply
        FROM dws_song_daily
        WHERE dt >= :start_dt
        GROUP BY dt
        ORDER BY dt
        """,
        params={"start_dt": start_dt},
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_top5() -> pd.DataFrame:
    """缓存歌曲热度 Top5。"""
    return _execute_read(
        """
        SELECT
            s.song_name AS name,
            AVG(r.heat_score) AS heat
        FROM dws_song_daily r
        JOIN dwd_song_info s ON r.song_id = s.song_id
        GROUP BY r.song_id, s.song_name
        ORDER BY heat DESC
        LIMIT 5
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_user_portrait_dist() -> pd.DataFrame:
    """缓存用户画像分布。"""
    return _execute_read(
        """
        SELECT user_type, COUNT(*) AS cnt
        FROM ads_user_portrait
        GROUP BY user_type
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_user_value_dist() -> pd.DataFrame:
    """缓存用户价值分布（已分箱为 20 个区间，与 dashboard.html 一致）。"""
    df = _execute_read("SELECT user_value FROM ads_user_portrait")
    if df.empty:
        return _EMPTY_DF.copy()
    values = df["user_value"].dropna().astype(float)
    if len(values) == 0:
        return _EMPTY_DF.copy()
    # 构造 20 个等宽区间
    bins = np.linspace(values.min(), values.max(), 21)
    counts, edges = np.histogram(values, bins=bins)
    ranges = [f"{edges[i]:.2f}-{edges[i+1]:.2f}" for i in range(len(counts))]
    mids = [(edges[i] + edges[i + 1]) / 2 for i in range(len(counts))]
    return pd.DataFrame({"range": ranges, "mid": mids, "count": counts})


@st.cache_data(ttl=300, show_spinner=False)
def cached_top_users() -> pd.DataFrame:
    """缓存高价值用户 TOP15。"""
    return _execute_read(
        """
        SELECT u.user_id, u.nickname, p.user_type, p.user_value,
               p.comment_count_total AS total_comment,
               p.reply_count_total AS total_reply,
               p.like_received_total AS total_like,
               p.avg_sentiment,
               p.active_period,
               p.sentiment_type
        FROM ads_user_portrait p
        JOIN dwd_user_info u ON p.user_id = u.user_id
        ORDER BY p.user_value DESC
        LIMIT 15
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_comment_pattern() -> pd.DataFrame:
    """缓存用户评论时段分布（凌晨/上午/下午/晚上）。"""
    return _execute_read(
        """
        SELECT
            CASE
                WHEN HOUR(comment_time) < 6 THEN '凌晨'
                WHEN HOUR(comment_time) < 12 THEN '上午'
                WHEN HOUR(comment_time) < 18 THEN '下午'
                ELSE '晚上'
            END AS time_period,
            COUNT(*) AS cnt
        FROM dwd_comment_detail
        GROUP BY time_period
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_sentiment_summary() -> pd.DataFrame:
    """缓存全局情感汇总。"""
    return _execute_read(
        "SELECT positive_ratio, neutral_ratio, negative_ratio, satisfaction_score, total_comments FROM ads_sentiment_summary LIMIT 1"
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_hot_predict_top10() -> pd.DataFrame:
    """缓存爆款预测 Top10。"""
    return _execute_read(
        """
        SELECT s.song_name, p.hot_prob
        FROM ads_hot_predict p
        JOIN dwd_song_info s ON p.song_id = s.song_id
        ORDER BY p.hot_prob DESC
        LIMIT 10
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_behavior_heatmap(start_dt: str) -> pd.DataFrame:
    """缓存近 30 天用户活跃度热力图原始数据（基于 comment_time）。start_dt 仅用于缓存键。"""
    return _execute_read(
        """
        SELECT comment_time AS behavior_time
        FROM dwd_comment_detail
        WHERE comment_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_detail_list() -> pd.DataFrame:
    """缓存歌曲分析页的歌曲列表（含评论数）。"""
    return _execute_read(
        """
        SELECT
            s.song_id,
            s.song_name,
            a.artist_name,
            COUNT(c.comment_id) AS comment_count
        FROM dwd_song_info s
        JOIN dwd_artist_info a ON s.artist_id = a.artist_id
        LEFT JOIN dwd_comment_detail c ON s.song_id = c.song_id
        GROUP BY s.song_id, s.song_name, a.artist_name
        ORDER BY s.song_name
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_comment_count(song_id: int) -> int:
    """缓存指定歌曲评论数。"""
    df = _execute_read(
        "SELECT COUNT(*) AS cnt FROM dwd_comment_detail WHERE song_id = :sid",
        params={"sid": song_id},
    )
    if df.empty:
        return 0
    return int(df["cnt"].iloc[0])


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_daily(song_id: int) -> pd.DataFrame:
    """缓存指定歌曲生命周期曲线数据（基于真实评论指标）。"""
    return _execute_read(
        """
        SELECT dt, heat_score, comment_count, reply_count, like_total
        FROM dws_song_daily
        WHERE song_id = :sid
        ORDER BY dt
        """,
        params={"sid": song_id},
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_keywords(song_id: int) -> pd.DataFrame:
    """缓存指定歌曲评论热词 TOP12。"""
    return _execute_read(
        """
        SELECT word, score
        FROM ads_song_keywords
        WHERE song_id = :sid
        ORDER BY keyword_rank
        LIMIT 12
        """,
        params={"sid": song_id},
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_sentiment(song_id: int) -> pd.DataFrame:
    """缓存指定歌曲情感分布。"""
    return _execute_read(
        "SELECT positive, neutral, negative FROM ads_song_sentiment WHERE song_id = :sid",
        params={"sid": song_id},
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_top_comments(song_id: int, limit: int = 10) -> pd.DataFrame:
    """缓存指定歌曲高赞评论 TopN。"""
    return _execute_read(
        """
        SELECT content, like_count, comment_time
        FROM dwd_comment_detail
        WHERE song_id = :sid
        ORDER BY like_count DESC
        LIMIT :lim
        """,
        params={"sid": song_id, "lim": limit},
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_comment_top20() -> pd.DataFrame:
    """缓存歌曲评论数 Top20。"""
    return _execute_read(
        """
        SELECT s.song_name, a.artist_name, COUNT(c.comment_id) AS comment_count
        FROM dwd_song_info s
        JOIN dwd_artist_info a ON s.artist_id = a.artist_id
        LEFT JOIN dwd_comment_detail c ON s.song_id = c.song_id
        GROUP BY s.song_id, s.song_name, a.artist_name
        ORDER BY comment_count DESC
        LIMIT 20
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_model_metrics() -> pd.DataFrame:
    """缓存模型评估指标。"""
    return _execute_read("SELECT * FROM ads_model_metrics")


@st.cache_data(ttl=300, show_spinner=False)
def cached_feature_importance_top15() -> pd.DataFrame:
    """缓存特征重要性 TOP15。"""
    return _execute_read(
        """
        SELECT feature, importance
        FROM ads_feature_importance
        ORDER BY importance DESC
        LIMIT 15
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_hot_predict_top20() -> pd.DataFrame:
    """缓存爆款预测 TOP20。"""
    return _execute_read(
        """
        SELECT s.song_name, a.artist_name, p.hot_prob, p.is_hot_predicted
        FROM ads_hot_predict p
        JOIN dwd_song_info s ON p.song_id = s.song_id
        JOIN dwd_artist_info a ON s.artist_id = a.artist_id
        ORDER BY p.hot_prob DESC
        LIMIT 20
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_forecast_songs() -> pd.DataFrame:
    """缓存可查看预测趋势的歌曲列表。"""
    return _execute_read(
        """
        SELECT DISTINCT s.song_id, s.song_name, a.artist_name
        FROM ads_song_forecast f
        JOIN dwd_song_info s ON f.song_id = s.song_id
        JOIN dwd_artist_info a ON s.artist_id = a.artist_id
        ORDER BY s.song_name
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_forecast(song_id: int) -> pd.DataFrame:
    """缓存指定歌曲未来 30 天热度预测。"""
    return _execute_read(
        """
        SELECT forecast_date, heat_score, heat_score_lower, heat_score_upper
        FROM ads_song_forecast
        WHERE song_id = :sid
        ORDER BY forecast_date
        """,
        params={"sid": song_id},
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_global_keywords() -> pd.DataFrame:
    """缓存全局热门关键词 TOP20。"""
    return _execute_read(
        """
        SELECT word, score FROM ads_global_keywords
        ORDER BY keyword_rank LIMIT 20
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_comment_topics() -> pd.DataFrame:
    """缓存 LDA 主题关键词。"""
    return _execute_read("SELECT topic_id, topic_name, keywords FROM ads_comment_topic ORDER BY topic_id")


@st.cache_data(ttl=300, show_spinner=False)
def cached_topic_dist() -> pd.DataFrame:
    """缓存主题分布。"""
    return _execute_read(
        """
        SELECT t.topic_id, t.topic_name, COUNT(d.comment_id) AS cnt
        FROM ads_comment_topic_detail d
        JOIN ads_comment_topic t ON d.topic_id = t.topic_id
        GROUP BY t.topic_id, t.topic_name
        ORDER BY cnt DESC
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_song_sentiments_top15() -> pd.DataFrame:
    """缓存歌曲情感满意度 Top15。"""
    return _execute_read(
        """
        SELECT s.song_name, se.positive, se.neutral, se.negative, se.satisfaction_score
        FROM ads_song_sentiment se
        JOIN dwd_song_info s ON se.song_id = s.song_id
        ORDER BY se.satisfaction_score DESC
        LIMIT 15
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_comment_sentiment_time() -> pd.DataFrame:
    """缓存全部评论情感与时间，用于情感研究页计算周趋势与歌曲变化。"""
    return _execute_read(
        """
        SELECT c.comment_id, c.song_id, c.comment_time, s.positive_prob
        FROM dwd_comment_detail c
        JOIN ads_comment_sentiment s ON c.comment_id = s.comment_id
        """
    )


@st.cache_data(ttl=300, show_spinner=False)
def cached_sentiment_weekly() -> pd.DataFrame:
    """缓存平台情感加速度趋势（近 30 周），直接查询过滤后数据以提升性能。"""
    # 仅取最近 35 周（留余量）的评论，避免全表扫描
    df = _execute_read(
        """
        SELECT c.comment_time, s.positive_prob
        FROM dwd_comment_detail c
        JOIN ads_comment_sentiment s ON c.comment_id = s.comment_id
        WHERE c.comment_time >= DATE_SUB(CURDATE(), INTERVAL 245 DAY)
        """
    )
    if df.empty:
        return _EMPTY_DF.copy()
    df["comment_time"] = pd.to_datetime(df["comment_time"])
    df["week"] = df["comment_time"].dt.to_period("W-MON").apply(lambda r: r.start_time.strftime("%Y-%m-%d"))
    weekly = (
        df.groupby("week")
        .agg(
            count=("positive_prob", "count"),
            positive_ratio=("positive_prob", lambda x: (x > 0.6).mean()),
            negative_ratio=("positive_prob", lambda x: (x < 0.4).mean()),
            neutral_ratio=("positive_prob", lambda x: ((x >= 0.4) & (x <= 0.6)).mean()),
            avg_positive_prob=("positive_prob", "mean"),
        )
        .reset_index()
        .sort_values("week")
        .tail(30)
        .reset_index(drop=True)
    )
    weekly["velocity"] = weekly["positive_ratio"].diff().fillna(0)
    weekly["acceleration"] = weekly["velocity"].diff().fillna(0)
    return weekly


def _compute_song_sentiment_change(min_comments: int = 6) -> pd.DataFrame:
    """向量化计算每首歌曲早期/近期正面情感占比与变化率。"""
    df = cached_comment_sentiment_time()
    if df.empty:
        return _EMPTY_DF.copy()
    df["comment_time"] = pd.to_datetime(df["comment_time"])
    df = df.sort_values(["song_id", "comment_time"]).reset_index(drop=True)
    df["rank"] = df.groupby("song_id").cumcount()
    df["n"] = df.groupby("song_id")["comment_id"].transform("count")
    df = df[df["n"] >= min_comments].copy()
    if df.empty:
        return _EMPTY_DF.copy()
    df["half"] = df["n"] // 2
    df["period"] = (df["rank"] >= df["half"]).astype(int)  # 0=early, 1=recent
    df["is_pos"] = (df["positive_prob"] > 0.6).astype(int)
    stats = (
        df.groupby(["song_id", "period"])
        .agg(positive_ratio=("is_pos", "mean"), avg_prob=("positive_prob", "mean"), cnt=("comment_id", "count"))
        .unstack(fill_value=0)
        .reset_index()
    )
    # flatten columns
    stats.columns = ["song_id", "early_positive_ratio", "recent_positive_ratio", "early_avg_prob", "recent_avg_prob", "early_count", "recent_count"]
    stats["comment_count"] = stats["early_count"] + stats["recent_count"]
    # 避免除零
    stats = stats[stats["early_positive_ratio"] > 0].copy()
    stats["change_rate"] = (stats["recent_positive_ratio"] - stats["early_positive_ratio"]) / stats["early_positive_ratio"] * 100
    songs = cached_song_detail_list()
    if not songs.empty:
        stats = stats.merge(songs[["song_id", "song_name"]], on="song_id", how="left")
    return stats


@st.cache_data(ttl=300, show_spinner=False)
def cached_sentiment_rising() -> pd.DataFrame:
    """缓存情感升温最快歌曲 Top10。"""
    stats = _compute_song_sentiment_change()
    if stats.empty:
        return _EMPTY_DF.copy()
    return stats.sort_values("change_rate", ascending=False).head(10)


@st.cache_data(ttl=300, show_spinner=False)
def cached_sentiment_falling() -> pd.DataFrame:
    """缓存情感降温最快歌曲 Top10。"""
    stats = _compute_song_sentiment_change()
    if stats.empty:
        return _EMPTY_DF.copy()
    return stats.sort_values("change_rate").head(10)


@st.cache_data(ttl=300, show_spinner=False)
def cached_sentiment_scatter() -> pd.DataFrame:
    """缓存情感得分 - 情感加速度矩阵数据。"""
    return _compute_song_sentiment_change()


# ==================== 环比计算 ====================


def _calc_growth(current: float, previous: float) -> Optional[float]:
    """计算环比增长率。previous 为 0 或空时返回 None。"""
    if previous is None or previous == 0 or current is None:
        return None
    return (current - previous) / previous


def growth_today_vs_yesterday(table: str, count_col: str = "*") -> Optional[float]:
    """
    计算今日 vs 昨日数量环比增长率。
    用于替换首页虚假的 ↑ X.X% 静态文本。
    返回 None 表示无数据可计算，调用方应隐藏增长率。
    """
    if table not in ALLOWED_TABLES:
        raise ValueError(f"非法表名: {table}")
    df = _execute_read(
        f"""
        SELECT
            SUM(CASE WHEN DATE(etl_time) = CURDATE() THEN 1 ELSE 0 END) AS today_cnt,
            SUM(CASE WHEN DATE(etl_time) = DATE_SUB(CURDATE(), INTERVAL 1 DAY) THEN 1 ELSE 0 END) AS yest_cnt
        FROM {table}
        """
    )
    if df.empty:
        return None
    today = float(df["today_cnt"].iloc[0] or 0)
    yest = float(df["yest_cnt"].iloc[0] or 0)
    return _calc_growth(today, yest)


def growth_dws_metric(metric_col: str) -> Optional[float]:
    """
    计算 dws_song_daily 中指定指标的环比（今日 vs 昨日合计）。
    metric_col 取值如 'heat_score' / 'comment_count' / 'reply_count'。
    """
    if not metric_col.replace("_", "").isalnum():
        raise ValueError(f"非法字段名: {metric_col}")
    df = _execute_read(
        f"""
        SELECT
            SUM(CASE WHEN dt = CURDATE() THEN {metric_col} ELSE 0 END) AS today_val,
            SUM(CASE WHEN dt = DATE_SUB(CURDATE(), INTERVAL 1 DAY) THEN {metric_col} ELSE 0 END) AS yest_val
        FROM dws_song_daily
        """
    )
    if df.empty:
        return None
    today = float(df["today_val"].iloc[0] or 0)
    yest = float(df["yest_val"].iloc[0] or 0)
    return _calc_growth(today, yest)


def fmt_growth(g: Optional[float]) -> str:
    """格式化增长率为展示文本；None 时返回空串（隐藏增长率）。"""
    if g is None:
        return ""
    arrow = "↑" if g >= 0 else "↓"
    return f"{arrow} {abs(g):.1%}"
