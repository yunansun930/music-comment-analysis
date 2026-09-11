"""
本地静态 HTML 大屏生成器（带侧边导航多页面版）
从 MySQL 拉取真实数据，生成自包含 HTML（内嵌 ECharts CDN）
点击左侧导航切换右侧内容区域。
"""
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import pymysql


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


def get_conn():
    return pymysql.connect(**DB_CONFIG)


def q(sql, args=None):
    conn = get_conn()
    try:
        cur = conn.cursor(pymysql.cursors.DictCursor)
        cur.execute(sql, args or ())
        return cur.fetchall()
    finally:
        conn.close()


def safe_json(obj):
    from decimal import Decimal
    import datetime as _dt

    def default(o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (_dt.datetime, _dt.date)):
            return o.isoformat()
        if isinstance(o, bytes):
            return o.decode("utf-8", errors="ignore")
        return str(o)

    return json.dumps(obj, ensure_ascii=False, default=default)


def collect_data():
    """采集所有页面需要的数据"""
    data = {}

    # ========== 公共 ==========
    data["count_users"] = (q("SELECT COUNT(*) AS c FROM dwd_user_info") or [{}])[0].get("c", 0)
    data["count_songs"] = (q("SELECT COUNT(*) AS c FROM dwd_song_info") or [{}])[0].get("c", 0)
    data["count_comments"] = (q("SELECT COUNT(*) AS c FROM dwd_comment_detail") or [{}])[0].get("c", 0)
    data["count_artists"] = (q("SELECT COUNT(*) AS c FROM dwd_artist_info") or [{}])[0].get("c", 0)

    # 评论获赞率（评论获赞数 / 评论数）
    ir = q("""
        SELECT
            SUM(like_count) AS like_cnt,
            COUNT(*) AS comment_cnt
        FROM dwd_comment_detail
    """)
    ir = ir[0] if ir else {}
    like_cnt = int(ir.get("like_cnt") or 0)
    comment_cnt = int(ir.get("comment_cnt") or 0)
    data["interaction_rate"] = (like_cnt / comment_cnt) if comment_cnt else 0.0
    data["total_likes"] = like_cnt

    # 总评论数（直接查询评论明细表）
    total_comment_row = q("SELECT COUNT(*) AS total FROM dwd_comment_detail")
    data["total_comments"] = int((total_comment_row[0] if total_comment_row else {}).get("total") or 0)

    # ========== 首页 ==========
    data["trend_30d"] = q("""
        SELECT dt, SUM(heat_score) AS total_heat, SUM(comment_count) AS total_comment,
               SUM(reply_count) AS total_reply
        FROM dws_song_daily
        WHERE dt >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
        GROUP BY dt ORDER BY dt
    """)
    data["song_top5"] = q("""
        SELECT s.song_name AS name, AVG(r.heat_score) AS heat
        FROM dws_song_daily r JOIN dwd_song_info s ON r.song_id = s.song_id
        GROUP BY r.song_id, s.song_name ORDER BY heat DESC LIMIT 5
    """)
    data["user_portrait"] = q("""
        SELECT user_type, COUNT(*) AS cnt FROM ads_user_portrait GROUP BY user_type
    """)
    data["sentiment_summary"] = (q("""
        SELECT positive_ratio, neutral_ratio, negative_ratio, satisfaction_score
        FROM ads_sentiment_summary LIMIT 1
    """) or [{}])
    if data["sentiment_summary"]:
        data["sentiment_summary"] = data["sentiment_summary"][0]
    data["hot_predict_top10"] = q("""
        SELECT s.song_name, p.hot_prob
        FROM ads_hot_predict p JOIN dwd_song_info s ON p.song_id = s.song_id
        ORDER BY p.hot_prob DESC LIMIT 10
    """)

    # 热力图（基于真实评论时间）
    heat = q("""
        SELECT comment_time AS behavior_time FROM dwd_comment_detail
        WHERE comment_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    """)
    hour_dow = defaultdict(lambda: defaultdict(int))
    for row in heat:
        bt = row.get("behavior_time")
        if bt is None:
            continue
        try:
            hour_dow[bt.weekday()][bt.hour] += 1
        except Exception:
            continue
    dow_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    heat_data = []
    max_cnt = 1
    for dow in range(7):
        for hr in range(24):
            v = hour_dow[dow][hr]
            max_cnt = max(max_cnt, v)
            heat_data.append([hr, dow, v])
    data["heatmap"] = {"data": heat_data, "y_labels": dow_labels, "max": max_cnt}

    # ========== 歌曲分析 ==========
    # 取全部歌曲作为下拉（按评论数排序）
    data["song_list"] = q("""
        SELECT s.song_id, s.song_name, a.artist_name,
               COUNT(c.comment_id) AS comment_count
        FROM dwd_song_info s
        LEFT JOIN dwd_artist_info a ON s.artist_id = a.artist_id
        LEFT JOIN dwd_comment_detail c ON s.song_id = c.song_id
        GROUP BY s.song_id, s.song_name, a.artist_name
        ORDER BY comment_count DESC
    """)
    # 批量预加载所有歌曲的详情（避免 N+1 查询）
    song_ids = [s["song_id"] for s in data["song_list"]]

    # 批量查生命周期
    life_rows = q("""
        SELECT song_id, dt, heat_score, comment_count, reply_count
        FROM dws_song_daily
        ORDER BY song_id, dt
    """)
    life_map = {}
    for r in life_rows:
        life_map.setdefault(r["song_id"], []).append(r)

    # 批量查关键词（每首取前 12 个）
    kw_rows = q("""
        SELECT song_id, word, score FROM ads_song_keywords
        ORDER BY song_id, keyword_rank
    """)
    kw_map = {}
    kw_counter = {}
    for r in kw_rows:
        sid = r["song_id"]
        cnt = kw_counter.get(sid, 0)
        if cnt < 12:
            kw_map.setdefault(sid, []).append(r)
            kw_counter[sid] = cnt + 1

    # 批量查情感
    sent_rows = q("SELECT song_id, positive, neutral, negative FROM ads_song_sentiment")
    sent_map = {r["song_id"]: r for r in sent_rows}

    # 批量查每首歌高赞评论 Top10
    comment_rows = q("""
        SELECT song_id, content, like_count, comment_time
        FROM dwd_comment_detail
        ORDER BY song_id, like_count DESC, comment_time DESC
    """)
    comment_map = {}
    comment_counter = {}
    for r in comment_rows:
        sid = r["song_id"]
        cnt = comment_counter.get(sid, 0)
        if cnt < 10:
            comment_map.setdefault(sid, []).append(r)
            comment_counter[sid] = cnt + 1

    # 组装详情
    song_details = []
    for s in data["song_list"]:
        sid = s["song_id"]
        detail = {
            "song_id": sid,
            "song_name": s["song_name"],
            "artist_name": s["artist_name"],
            "comment_count": s["comment_count"],
            "lifecycle": life_map.get(sid, []),
            "keywords": kw_map.get(sid, []),
            "sentiment": sent_map.get(sid, {}),
            "top_comments": comment_map.get(sid, []),
        }
        song_details.append(detail)
    data["song_details"] = song_details

    # ========== 用户画像 ==========
    data["top_users"] = q("""
        SELECT u.user_id, u.nickname, p.user_value,
               p.comment_count_total AS total_comment,
               p.reply_count_total AS total_reply,
               p.like_received_total AS total_like,
               p.avg_sentiment,
               p.active_period,
               p.sentiment_type,
               p.user_type
        FROM ads_user_portrait p
        JOIN dwd_user_info u ON p.user_id = u.user_id
        ORDER BY p.user_value DESC LIMIT 15
    """)
    # 用户价值分布：在 Python 端分箱（ECharts 标准版不支持 histogram）
    uv_rows = q("SELECT user_value FROM ads_user_portrait")
    uv_values = [float(r["user_value"]) for r in uv_rows if r.get("user_value") is not None]
    if uv_values:
        uv_min, uv_max = min(uv_values), max(uv_values)
        bins = 20
        # 避免所有值相同导致除零
        if uv_max - uv_min < 1e-9:
            uv_max = uv_min + 1
        step = (uv_max - uv_min) / bins
        counts = [0] * bins
        for v in uv_values:
            idx = int((v - uv_min) / step)
            if idx >= bins:
                idx = bins - 1
            counts[idx] += 1
        data["user_value_dist"] = [
            {
                "range": f"{uv_min + i * step:.3f} - {uv_min + (i + 1) * step:.3f}",
                "mid": uv_min + (i + 0.5) * step,
                "count": counts[i],
            }
            for i in range(bins)
        ]
    else:
        data["user_value_dist"] = []
    # 评论时段分布（凌晨/上午/下午/晚上）
    data["comment_pattern"] = q("""
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
    """)

    # ========== 文本洞察 ==========
    data["global_keywords"] = q("""
        SELECT word, score FROM ads_global_keywords
        ORDER BY keyword_rank LIMIT 20
    """)
    data["topics"] = q("""
        SELECT topic_id, topic_name, keywords, keyword_count FROM ads_comment_topic
        ORDER BY topic_id
    """)
    # 主题分布（带主题名）
    data["topic_dist"] = q("""
        SELECT td.topic_id, COALESCE(t.topic_name, CONCAT('主题', td.topic_id)) AS topic_name,
               SUM(td.comment_num) AS cnt
        FROM ads_song_topic_dist td
        LEFT JOIN ads_comment_topic t ON td.topic_id = t.topic_id
        GROUP BY td.topic_id, t.topic_name
        ORDER BY cnt DESC
    """)
    # 情感明细（取每首歌的汇总）
    data["song_sentiments"] = q("""
        SELECT s.song_name, ss.positive, ss.neutral, ss.negative, ss.satisfaction_score
        FROM ads_song_sentiment ss
        JOIN dwd_song_info s ON ss.song_id = s.song_id
        ORDER BY ss.satisfaction_score DESC LIMIT 15
    """)

    # ========== 爆款预测 ==========
    data["model_metrics"] = q("""
        SELECT model_name, auc, f1, accuracy FROM ads_model_metrics
        ORDER BY auc DESC
    """)
    data["feature_importance"] = q("""
        SELECT feature, importance FROM ads_feature_importance
        ORDER BY importance DESC LIMIT 15
    """)
    data["hot_predict_all"] = q("""
        SELECT s.song_name, a.artist_name, p.hot_prob, p.is_hot_predicted
        FROM ads_hot_predict p
        JOIN dwd_song_info s ON p.song_id = s.song_id
        LEFT JOIN dwd_artist_info a ON s.artist_id = a.artist_id
        ORDER BY p.hot_prob DESC LIMIT 20
    """)

    # ========== 时间序列预测 ==========
    forecast_songs = q("""
        SELECT DISTINCT s.song_id, s.song_name
        FROM ads_song_forecast f JOIN dwd_song_info s ON f.song_id = s.song_id
        ORDER BY s.song_name
    """)
    # 批量预加载所有预测数据
    fc_rows = q("""
        SELECT song_id, forecast_date, heat_score, heat_score_lower, heat_score_upper
        FROM ads_song_forecast ORDER BY song_id, forecast_date
    """)
    fc_map = {}
    for r in fc_rows:
        fc_map.setdefault(r["song_id"], []).append(r)

    forecast_list = []
    for fs in forecast_songs:
        sid = fs["song_id"]
        fc = fc_map.get(sid, [])
        if fc:
            forecast_list.append({
                "song_id": sid,
                "song_name": fs["song_name"],
                "data": fc,
            })
    data["forecast_list"] = forecast_list

    # ========== 用户行为（A+B+C 模块新增） ==========
    # 模块 A：RFM 分群
    try:
        data["rfm_dist"] = q("""
            SELECT rfm_label, COUNT(*) AS cnt
            FROM ads_user_rfm
            GROUP BY rfm_label
            ORDER BY cnt DESC
        """)
        data["rfm_total"] = sum(int(r["cnt"]) for r in (data["rfm_dist"] or []))
    except Exception:
        data["rfm_dist"] = []
        data["rfm_total"] = 0

    # 模块 C：行为时间模式（24h / 周内 / 月度）
    try:
        data["tp_hourly"] = q("""
            SELECT hour, comment_count, reply_count, like_total, peak_label
            FROM ads_time_pattern_hourly ORDER BY hour
        """)
    except Exception:
        data["tp_hourly"] = []
    try:
        data["tp_weekday"] = q("""
            SELECT weekday, weekday_name, comment_count, is_weekend
            FROM ads_time_pattern_weekday ORDER BY weekday
        """)
    except Exception:
        data["tp_weekday"] = []
    try:
        data["tp_monthly"] = q("""
            SELECT month, comment_count, season
            FROM ads_time_pattern_monthly ORDER BY month
        """)
    except Exception:
        data["tp_monthly"] = []

    # 模块 B：流失预测
    try:
        data["churn_risk_dist"] = q("""
            SELECT risk_level, COUNT(*) AS cnt
            FROM ads_churn_predict
            GROUP BY risk_level
            ORDER BY FIELD(risk_level, '低', '中', '高')
        """)
        data["churn_total"] = sum(int(r["cnt"]) for r in (data["churn_risk_dist"] or []))
        data["churn_high_count"] = next((int(r["cnt"]) for r in (data["churn_risk_dist"] or []) if r["risk_level"] == "高"), 0)
    except Exception:
        data["churn_risk_dist"] = []
        data["churn_total"] = 0
        data["churn_high_count"] = 0

    try:
        data["churn_metrics"] = q("""
            SELECT model_name, auc, auc_std, f1, accuracy
            FROM ads_churn_metrics
            ORDER BY auc DESC
        """)
    except Exception:
        data["churn_metrics"] = []

    try:
        data["churn_high_users"] = q("""
            SELECT user_id, churn_prob, risk_level, recency_days
            FROM ads_churn_predict
            WHERE risk_level = '高'
            ORDER BY churn_prob DESC LIMIT 10
        """)
    except Exception:
        data["churn_high_users"] = []

    # 评论高峰时段
    try:
        peak_row = q("""
            SELECT hour, comment_count FROM ads_time_pattern_hourly
            ORDER BY comment_count DESC LIMIT 1
        """)
        peak = peak_row[0] if peak_row else {}
        data["peak_hour"] = f"{int(peak.get('hour', 0)):02d}:00" if peak else "-"
    except Exception:
        data["peak_hour"] = "-"

    # ========== 情感研究（情感加速度） ==========
    # 拉取每条评论的情感概率 + 评论时间
    sent_rows = q("""
        SELECT s.song_id, si.song_name, s.positive_prob, s.sentiment, c.comment_time
        FROM ads_comment_sentiment s
        JOIN dwd_comment_detail c ON s.comment_id = c.comment_id
        JOIN dwd_song_info si ON s.song_id = si.song_id
    """)

    # 1) 平台级情感加速度：按周聚合
    from datetime import timedelta

    def get_week(dt):
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt)
        # 返回该周周一的日期字符串
        monday = dt - timedelta(days=dt.weekday())
        return monday.date().isoformat()

    week_stats = defaultdict(lambda: {"pos": 0, "neg": 0, "neu": 0, "total_prob": 0.0, "cnt": 0})
    for r in sent_rows:
        if r.get("comment_time") is None:
            continue
        w = get_week(r["comment_time"])
        week_stats[w]["cnt"] += 1
        week_stats[w]["total_prob"] += float(r.get("positive_prob") or 0)
        sentiment = r.get("sentiment", "neutral")
        if sentiment == "positive":
            week_stats[w]["pos"] += 1
        elif sentiment == "negative":
            week_stats[w]["neg"] += 1
        else:
            week_stats[w]["neu"] += 1

    weekly = []
    for w, v in sorted(week_stats.items()):
        cnt = v["cnt"]
        if cnt == 0:
            continue
        weekly.append({
            "week": w,
            "positive_ratio": v["pos"] / cnt,
            "negative_ratio": v["neg"] / cnt,
            "neutral_ratio": v["neu"] / cnt,
            "avg_positive_prob": v["total_prob"] / cnt,
            "count": cnt,
        })

    # 计算速度和加速度（基于 positive_ratio）
    for i in range(len(weekly)):
        if i == 0:
            weekly[i]["velocity"] = 0.0
            weekly[i]["acceleration"] = 0.0
        else:
            weekly[i]["velocity"] = weekly[i]["positive_ratio"] - weekly[i - 1]["positive_ratio"]
            if i == 1:
                weekly[i]["acceleration"] = 0.0
            else:
                weekly[i]["acceleration"] = weekly[i]["velocity"] - weekly[i - 1]["velocity"]
    # 只取最近 30 周展示
    data["sentiment_weekly"] = weekly[-30:] if len(weekly) > 30 else weekly

    # 2) 歌曲级情感升温/降温排行
    song_comments = defaultdict(list)
    for r in sent_rows:
        if r.get("comment_time") is None:
            continue
        song_comments[r["song_id"]].append({
            "song_name": r["song_name"],
            "positive_prob": float(r.get("positive_prob") or 0),
            "sentiment": r.get("sentiment", "neutral"),
            "comment_time": r["comment_time"],
        })

    song_accel = []
    for sid, comments in song_comments.items():
        if len(comments) < 10:
            continue
        # 按时间排序，取前 30% 为早期，后 30% 为近期
        comments = sorted(comments, key=lambda x: x["comment_time"])
        n = len(comments)
        early = comments[: max(1, int(n * 0.3))]
        recent = comments[-max(1, int(n * 0.3)):]

        def positive_ratio(items):
            pos = sum(1 for x in items if x["sentiment"] == "positive")
            return pos / len(items) if items else 0

        early_pos = positive_ratio(early)
        recent_pos = positive_ratio(recent)
        # 变化率（加速度近似），避免除零
        if early_pos <= 1e-6:
            change_rate = (recent_pos - early_pos) * 100
        else:
            change_rate = (recent_pos - early_pos) / early_pos * 100

        song_accel.append({
            "song_id": sid,
            "song_name": comments[0]["song_name"],
            "early_positive_ratio": early_pos,
            "recent_positive_ratio": recent_pos,
            "change_rate": change_rate,
            "recent_avg_prob": sum(x["positive_prob"] for x in recent) / len(recent),
            "comment_count": n,
        })

    # 升温最快 Top10 / 降温最快 Top10
    song_accel_sorted = sorted(song_accel, key=lambda x: x["change_rate"], reverse=True)
    data["sentiment_rising"] = song_accel_sorted[:10]
    data["sentiment_falling"] = song_accel_sorted[-10:][::-1]
    data["sentiment_scatter"] = song_accel


    # ========== 实验分析 ==========
    try:
        stat_tests = q("SELECT test_name, test_type, metric_name, sample_size, statistic, p_value, effect_size, ci_lower, ci_upper, conclusion FROM ads_stat_tests ORDER BY test_id")
        data["stat_tests"] = stat_tests or []
    except Exception:
        data["stat_tests"] = []

    try:
        cohort = q("SELECT cohort_week, cohort_size, week_offset, active_users, retention FROM ads_cohort_retention WHERE week_offset <= 8 ORDER BY cohort_week, week_offset")
        data["cohort_retention"] = cohort or []
    except Exception:
        data["cohort_retention"] = []

    try:
        ab_test = q("SELECT test_name, metric_name, control_mean, treatment_mean, lift_ratio, sample_size, statistic, p_value, effect_size, ci_lower, ci_upper, is_significant, conclusion FROM ads_ab_test_results")
        data["ab_test"] = ab_test or []
    except Exception:
        data["ab_test"] = []

    data["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return data


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>音乐评论用户行为分析 - 数据大屏</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
<style>
  :root {
    /* 民谣主题色板 */
    --paper: #f5efe6;
    --paper-2: #ede4d6;
    --paper-3: #e6d9c6;
    --ink: #4a3f35;
    --ink-light: #6b5e52;
    --muted: #8c7b6c;
    --rule: #d6c6b1;
    --brown: #8b6b4d;
    --brown-dark: #6d5137;
    --brick: #c0392b;
    --sage: #5a7d6b;
    --sage-light: #7a9d8b;
    --cream: #faf6f0;
    --shadow: rgba(74,63,53,0.08);
    --accent: var(--brown);
    --accent2: var(--sage);
    --warm: var(--brick);
    --danger: var(--brick);
    --ok: var(--sage);
    --side-w: 220px;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    font-family: 'PingFang SC', 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--paper);
    color: var(--ink);
    line-height: 1.65;
    overflow-x: hidden;
    width: 100%;
    min-height: 100%;
  }
  /* 轻微纸张纹理 */
  body::before {
    content: "";
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    opacity: 0.35;
    z-index: 0;
    background-image:
      radial-gradient(circle at 20% 30%, rgba(139,107,77,0.04) 0%, transparent 40%),
      radial-gradient(circle at 80% 70%, rgba(192,57,43,0.03) 0%, transparent 40%);
  }

  /* ============ 侧边导航 ============ */
  .sidebar {
    position: fixed;
    top: 0; left: 0; bottom: 0;
    width: var(--side-w);
    background: linear-gradient(180deg, var(--paper-2), var(--paper));
    border-right: 1px solid var(--rule);
    padding: 1.5rem 0;
    overflow-y: auto;
    z-index: 100;
    box-shadow: 2px 0 12px var(--shadow);
  }
  .sidebar .logo {
    text-align: center;
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--rule);
  }
  .sidebar .logo h1 {
    font-size: 1rem;
    color: var(--brown-dark);
    font-weight: 700;
    margin-bottom: 0.2rem;
  }
  .sidebar .logo .sub {
    font-size: 0.7rem;
    color: var(--muted);
    letter-spacing: 0.08em;
  }
  .nav-item {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.75rem 1.25rem;
    color: var(--ink-light);
    cursor: pointer;
    font-size: 0.88rem;
    border-left: 3px solid transparent;
    transition: all 0.2s;
  }
  .nav-item:hover {
    background: rgba(139,107,77,0.08);
    color: var(--ink);
  }
  .nav-item.active {
    background: rgba(139,107,77,0.12);
    color: var(--brown-dark);
    border-left-color: var(--brown);
    font-weight: 600;
  }
  .nav-item .ic {
    font-size: 1rem;
    width: 1.2rem;
    text-align: center;
  }

  /* ============ 主内容 ============ */
  .main {
    margin-left: var(--side-w);
    padding: 1.5rem 2rem 2rem;
    max-width: calc(100vw - var(--side-w));
    overflow-x: hidden;
    position: relative;
    z-index: 1;
  }
  .topbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1.25rem;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid var(--rule);
  }
  .topbar h2 {
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--brown-dark);
    letter-spacing: 0.05em;
    font-family: 'STKaiti', 'KaiTi', 'SimKaiti', 'PingFang SC', serif;
  }
  .topbar .meta { color: var(--muted); font-size: 0.82rem; }

  /* ============ 卡片/图表 ============ */
  .metrics-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1.25rem;
    margin-bottom: 1.5rem;
  }
  .metric-card {
    background: var(--cream);
    border: 1px solid var(--rule);
    border-radius: 10px;
    padding: 1.1rem;
    text-align: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 3px 10px var(--shadow);
  }
  .metric-card::before {
    content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, var(--brown), var(--brick));
  }
  .metric-card .label {
    color: var(--muted); font-size: 0.74rem;
    letter-spacing: 0.05em;
    margin-bottom: 0.4rem;
  }
  .metric-card .value {
    font-size: 1.55rem; font-weight: 700; color: var(--brown-dark);
    font-family: 'Consolas', 'STKaiti', monospace;
  }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
  .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-bottom: 1rem; }
  .grid-2-1 { display: grid; grid-template-columns: 2fr 1fr; gap: 1rem; margin-bottom: 1rem; }
  .grid-1-2 { display: grid; grid-template-columns: 1fr 2fr; gap: 1rem; margin-bottom: 1rem; }
  .panel {
    background: var(--cream);
    border: 1px solid var(--rule);
    border-radius: 10px;
    padding: 1rem 1.25rem;
    box-shadow: 0 2px 8px var(--shadow);
  }
  .panel h3 {
    font-size: 0.95rem; font-weight: 600;
    color: var(--brown-dark); margin-bottom: 0.4rem;
    display: flex; align-items: center; gap: 0.4rem;
    font-family: 'STKaiti', 'KaiTi', 'SimKaiti', 'PingFang SC', serif;
  }
  .panel .desc {
    color: var(--muted); font-size: 0.78rem;
    line-height: 1.6; margin-bottom: 0.7rem;
    font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  }
  .chart { width: 100%; height: 280px; min-width: 0; }
  .chart.sm { height: 220px; }
  .chart.lg { height: 320px; }

  /* ============ 表格 ============ */
  .table { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
  .table th, .table td {
    padding: 0.5rem 0.6rem; text-align: left;
    border-bottom: 1px solid var(--rule);
  }
  .table th {
    color: var(--brown-dark); font-weight: 600;
    background: rgba(139,107,77,0.06);
    position: sticky; top: 0;
  }
  .table tr:hover td { background: rgba(139,107,77,0.05); }
  .table td.num { color: var(--brown); font-family: 'Consolas', monospace; }
  .table-wrap { max-height: 360px; overflow-y: auto; }

  /* ============ 爆款进度条 ============ */
  .hit-row { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.5rem; font-size: 0.82rem; }
  .hit-row .name { width: 35%; color: var(--ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .hit-row .bar-bg { flex: 1; height: 14px; background: rgba(139,107,77,0.12); border-radius: 7px; overflow: hidden; }
  .hit-row .bar-fill { height: 100%; background: linear-gradient(90deg, var(--brick), #d98880); border-radius: 7px; }
  .hit-row .val { width: 60px; text-align: right; color: var(--brick); font-family: 'Consolas', monospace; }

  /* ============ 主题列表 ============ */
  .topic-list { font-size: 0.85rem; line-height: 1.9; color: var(--ink-light); }
  .topic-list .t { color: var(--brown); font-weight: 600; margin-right: 0.4rem; }

  /* ============ 高赞评论滚动 ============ */
  .comment-scroll {
    height: 180px;
    overflow: hidden;
    position: relative;
    background: var(--paper-2);
    border-radius: 10px;
    border: 1px solid var(--rule);
  }
  .comment-list {
    position: absolute;
    top: 0; left: 0; right: 0;
    transition: transform 0.6s ease-in-out;
  }
  .comment-item {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.65rem 1rem;
    border-bottom: 1px solid var(--rule);
    font-size: 0.86rem;
    line-height: 1.55;
    height: 60px;
    min-height: 60px;
    box-sizing: border-box;
    color: var(--ink);
  }
  .comment-item:last-child { border-bottom: none; }
  .comment-item .rank {
    flex-shrink: 0;
    width: 22px; height: 22px;
    border-radius: 50%;
    background: var(--brown);
    color: #fff;
    font-size: 0.7rem;
    font-weight: 700;
    display: flex; align-items: center; justify-content: center;
    margin-top: 2px;
  }
  .comment-item .body { flex: 1; min-width: 0; }
  .comment-item .text {
    color: var(--ink);
    word-break: break-all;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .comment-item .meta {
    color: var(--muted);
    font-size: 0.74rem;
    margin-top: 0.25rem;
  }
  .comment-item .meta span { margin-right: 0.8rem; }
  .comment-item .like { color: var(--brick); font-weight: 600; }

  /* ============ 切换器 ============ */
  .selector {
    display: inline-block;
    background: var(--cream);
    border: 1px solid var(--rule);
    border-radius: 8px;
    padding: 0.4rem 0.8rem;
    color: var(--ink);
    font-size: 0.85rem;
    cursor: pointer;
    margin-bottom: 0.75rem;
    min-width: 240px;
  }
  .selector:focus { outline: 2px solid var(--brown); }
    .select-wrap { position: relative; }
    .select-search {
      background: var(--cream);
      border: 1px solid var(--rule);
      border-radius: 8px;
      padding: 0.4rem 0.75rem;
      color: var(--ink);
      font-size: 0.85rem;
      margin-right: 0.5rem;
      width: 220px;
    }
    .select-search:focus { outline: 2px solid var(--brown); }
    select.selector { max-width: 100%; }

    .empty { color: var(--muted); font-style: italic; text-align: center; padding: 2rem 0; }

  /* ============ 页面切换 ============ */
  .page { display: none; }
  .page.active { display: block; }

  .foot {
    margin-top: 2rem; padding-top: 1rem;
    border-top: 1px solid var(--rule);
    text-align: center; color: var(--muted);
    font-size: 0.78rem;
  }

  @media (max-width: 1100px) {
    .grid-3 { grid-template-columns: 1fr; }
    .grid-2-1, .grid-1-2 { grid-template-columns: 1fr; }
  }
  @media (max-width: 768px) {
    .sidebar { width: 60px; }
    .sidebar .logo h1, .sidebar .logo .sub, .nav-item span { display: none; }
    .main { margin-left: 60px; padding: 1rem; }
    .grid-2 { grid-template-columns: 1fr; }
  }
</style>
</head>
<body>

<!-- 侧边导航 -->
<aside class="sidebar">
  <div class="logo">
    <h1>🎶 音乐数据分析</h1>
    <div class="sub">用户行为大屏</div>
  </div>
  <div class="nav-item active" data-page="home"><span class="ic">📊</span><span>首页总览</span></div>
  <div class="nav-item" data-page="songs"><span class="ic">🎵</span><span>歌曲分析</span></div>
  <div class="nav-item" data-page="users"><span class="ic">👥</span><span>用户画像</span></div>
  <div class="nav-item" data-page="text"><span class="ic">💬</span><span>文本洞察</span></div>
  <div class="nav-item" data-page="sentiment"><span class="ic">❤️</span><span>情感研究</span></div>
  <div class="nav-item" data-page="predict"><span class="ic">🚀</span><span>爆款预测</span></div>
  <div class="nav-item" data-page="forecast"><span class="ic">🔮</span><span>热度预测</span></div>
  <div class="nav-item" data-page="behavior"><span class="ic">📈</span><span>用户行为</span></div>
    <div class="nav-item" data-page="exp"><span class="ic">🧪</span><span>实验分析</span></div>
</aside>

<!-- 主内容区 -->
<main class="main">
  <div class="topbar">
    <h2 id="page-title">民谣风向标 · 数据洞察</h2>
    <div class="meta">数据生成时间：<span id="gen-at"></span></div>
  </div>

  <!-- ============ 首页 ============ -->
  <section class="page active" id="page-home">
    <div class="metrics-row">
      <div class="metric-card"><div class="label">总歌曲数</div><div class="value" id="m-songs">-</div></div>
      <div class="metric-card"><div class="label">总评论数</div><div class="value" id="m-comments">-</div></div>
      <div class="metric-card"><div class="label">总评论获赞</div><div class="value" id="m-likes">-</div></div>
      <div class="metric-card"><div class="label">平均获赞率</div><div class="value" id="m-rate">-</div></div>
    </div>

    <div class="grid-2-1">
      <div class="panel">
        <h3>📈 近 30 天歌曲热度趋势</h3>
        <p class="desc">展示平台近 30 天整体热度与评论量的变化走势，帮助把握民谣内容的大盘节奏与波动趋势。</p>
        <div id="c-trend" class="chart lg"></div>
      </div>
      <div class="panel">
        <h3>🔥 歌曲热度 Top5</h3>
        <p class="desc">当前综合热度最高的 5 首民谣歌曲，反映近期最受用户关注与讨论的头部内容。</p>
        <div id="c-top5" class="chart"></div>
      </div>
    </div>

    <div class="grid-3">
      <div class="panel">
        <h3>👥 用户画像分布</h3>
        <p class="desc">按互动深度将用户划分为核心粉丝、内容消费者和轻度用户，识别社区活跃度的主要贡献群体。</p>
        <div id="c-portrait" class="chart"></div>
      </div>
      <div class="panel">
        <h3>😊 全局情感分布</h3>
        <p class="desc">全部评论的情感倾向占比，正面/中性/负面分布反映用户对平台内容的总体情绪基调。</p>
        <div id="c-sentiment" class="chart"></div>
      </div>
      <div class="panel">
        <h3>🚀 爆款预测 Top10</h3>
        <p class="desc">基于热度与互动特征，模型预测未来最可能成为爆款的 10 首歌曲，为运营与推荐提供参考。</p>
        <div id="hot-list" style="padding-top: 0.5rem;"></div>
      </div>
    </div>

    <div class="panel">
      <h3>🔥 用户活跃度热力图（星期 × 小时）</h3>
      <p class="desc">展示用户在一周不同日期、一天不同时段的活跃密度，颜色越深表示该时段互动行为越密集，可用于选择最佳内容发布与运营时间。</p>
      <div id="c-heatmap" class="chart lg"></div>
    </div>
  </section>

  <!-- ============ 歌曲分析 ============ -->
  <section class="page" id="page-songs">
    <div class="panel" style="margin-bottom: 1rem;">
      <h3>🎵 选择歌曲</h3>
      <div class="select-wrap">
        <input type="text" class="select-search" id="song-search" placeholder="输入歌名/歌手快速筛选...">
        <select class="selector" id="song-select"></select>
      </div>
      <p style="color: var(--muted); font-size: 0.78rem; margin-top: 0.25rem;">共 <span id="song-count">-</span> 首歌曲可供选择</p>
    </div>

    <div class="panel" style="margin-bottom: 1rem;">
      <h3>📈 歌曲生命周期曲线</h3>
      <p class="desc">展示所选歌曲随时间变化的热度分与评论量，帮助判断歌曲处于上升期、稳定期还是衰退期。</p>
      <div id="c-lifecycle" class="chart"></div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3>🏷️ 评论热词</h3>
        <p class="desc">提取该歌曲评论中出现频率最高的关键词，反映听众讨论这首歌时最关心的内容和表达。</p>
        <div id="c-song-kw" class="chart"></div>
      </div>
      <div class="panel">
        <h3>😊 情感分布</h3>
        <p class="desc">该歌曲评论中正面、中性、负面情感的占比，直观呈现听众对这首歌的总体情绪反馈。</p>
        <div id="c-song-sent" class="chart"></div>
      </div>
    </div>

    <div class="panel" style="margin-bottom: 1rem;">
      <h3>💬 高赞评论滚动（Top10）</h3>
      <p class="desc">按点赞数排序的 Top10 热门评论，滚动展示听众最有共鸣、最具代表性的声音。</p>
      <div class="comment-scroll" id="comment-scroll">
        <div class="comment-list" id="comment-list"></div>
      </div>
    </div>

    <div class="panel">
      <h3>📋 歌曲评论数 Top20</h3>
      <p class="desc">评论数量最多的 20 首歌曲排行，评论量通常意味着更高的用户参与度和话题性。</p>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>歌曲名</th><th>歌手</th><th>评论数</th></tr></thead>
          <tbody id="t-song-list"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ============ 用户画像 ============ -->
  <section class="page" id="page-users">
    <div class="grid-2">
      <div class="panel">
        <h3>👥 用户类型分布</h3>
        <p class="desc">核心粉丝、内容消费者与轻度用户的占比，帮助识别社区主要由哪类用户构成。</p>
        <div id="c-user-type" class="chart"></div>
      </div>
      <div class="panel">
        <h3>📊 用户价值分布</h3>
        <p class="desc">按综合评论行为价值对用户进行区间划分，了解不同价值段用户的数量分布。</p>
        <div id="c-user-value" class="chart"></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3>🕐 评论时段分布</h3>
        <p class="desc">用户评论行为在不同时段（凌晨/上午/下午/晚上）的分布，反映社区讨论的活跃时间规律。</p>
        <div id="c-behavior" class="chart"></div>
      </div>
      <div class="panel">
        <h3>🏆 高价值用户 Top15</h3>
        <p class="desc">综合评论数、获赞数、情感倾向等评论行为计算出的高价值用户，是社区运营和维护的重点对象。</p>
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th>用户ID</th><th>昵称</th><th>类型</th><th>价值</th><th>评论数</th><th>获赞数</th><th>时段</th><th>情感</th></tr></thead>
            <tbody id="t-users"></tbody>
          </table>
        </div>
      </div>
    </div>
  </section>

  <!-- ============ 文本洞察 ============ -->
  <section class="page" id="page-text">
    <div class="grid-2-1">
      <div class="panel">
        <h3>🔑 全局热门关键词 Top20</h3>
        <p class="desc">全平台评论中出现最多的 20 个关键词，反映民谣听众共同关注的话题和表达主题。</p>
        <div id="c-keywords" class="chart"></div>
      </div>
      <div class="panel">
        <h3>📚 LDA 主题关键词</h3>
        <p class="desc">通过主题模型聚类出的评论主题及对应关键词，揭示听众讨论的隐性话题结构。</p>
        <div class="topic-list" id="topic-list"></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3>📊 主题分布</h3>
        <p class="desc">各主题评论数量的占比分布，直观展示民谣听众讨论焦点的集中与分散程度。</p>
        <div id="c-topic-dist" class="chart"></div>
      </div>
      <div class="panel">
        <h3>😊 歌曲情感 Top15（按满意度）</h3>
        <p class="desc">满意度最高的 15 首歌曲及其情感构成，帮助发现口碑最好、用户评价最积极的民谣作品。</p>
        <div id="c-song-sent-list" class="chart"></div>
      </div>
    </div>
  </section>

  <!-- ============ 情感研究 ============ -->
  <section class="page" id="page-sentiment">
    <div class="metrics-row">
      <div class="metric-card"><div class="label">评论总数</div><div class="value" id="sm-comments">-</div></div>
      <div class="metric-card"><div class="label">正面评论占比</div><div class="value" id="sm-pos">-</div></div>
      <div class="metric-card"><div class="label">负面评论占比</div><div class="value" id="sm-neg">-</div></div>
      <div class="metric-card"><div class="label">平均正面概率</div><div class="value" id="sm-prob">-</div></div>
    </div>

    <div class="panel" style="margin-bottom: 1rem;">
      <h3>📈 平台情感加速度趋势（近 30 周）</h3>
      <p class="desc">观察平台整体正面情感占比及其变化速度、加速度，判断用户好评情绪是在加速升温还是减速回落。</p>
      <div id="c-sentiment-weekly" class="chart lg"></div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3>🚀 情感升温最快歌曲 Top10</h3>
        <p class="desc">近期正面情感占比相比早期明显上升的歌曲，可能是口碑正在发酵、值得关注的潜力作品。</p>
        <div id="c-rising" class="chart"></div>
      </div>
      <div class="panel">
        <h3>🧊 情感降温最快歌曲 Top10</h3>
        <p class="desc">近期正面情感占比相比早期明显下降的歌曲，提示可能需要关注用户反馈变化或内容生命周期衰退。</p>
        <div id="c-falling" class="chart"></div>
      </div>
    </div>

    <div class="panel" style="margin-bottom: 1rem;">
      <h3>💨 情感得分 - 情感加速度矩阵</h3>
      <p class="desc">横轴为近期正面情感占比，纵轴为情感变化率。右上方代表“口碑好且快速升温”的高潜力歌曲。</p>
      <div id="c-sentiment-scatter" class="chart lg"></div>
    </div>
  </section>

  <!-- ============ 爆款预测 ============ -->
  <section class="page" id="page-predict">
    <div class="grid-2">
      <div class="panel">
        <h3>📊 模型对比评估</h3>
        <p class="desc">对比 XGBoost、逻辑回归等模型在 AUC、F1、Accuracy 上的表现，评估预测方案的可信度。</p>
        <div id="c-model" class="chart"></div>
      </div>
      <div class="panel">
        <h3>⚙️ 特征重要性 Top15</h3>
        <p class="desc">模型判断歌曲是否会爆最重要的 15 个特征，帮助理解哪些因素对热度预测影响最大。</p>
        <div id="c-feat" class="chart"></div>
      </div>
    </div>

    <div class="panel">
      <h3>🚀 预测爆款概率 Top20</h3>
      <p class="desc">综合模型给出的每首歌成为爆款的概率，并标注是否达到“预测爆款”阈值。</p>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>排名</th><th>歌曲名</th><th>歌手</th><th>爆款概率</th><th>是否预测爆款</th></tr></thead>
          <tbody id="t-hot-predict"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ============ 热度预测 ============ -->
  <section class="page" id="page-forecast">
    <div class="panel" style="margin-bottom: 1rem;">
      <h3>🔮 选择歌曲查看未来 30 天热度预测</h3>
      <div class="select-wrap">
        <input type="text" class="select-search" id="forecast-search" placeholder="输入歌名快速筛选...">
        <select class="selector" id="forecast-select"></select>
      </div>
      <p style="color: var(--muted); font-size: 0.78rem; margin-top: 0.25rem;">共 <span id="forecast-count">-</span> 首歌曲可预测</p>
    </div>

    <div class="panel">
      <h3 id="forecast-title">📈 预测热度趋势（含置信区间）</h3>
      <p class="desc">基于时间序列模型预测所选歌曲未来 30 天的热度走势，阴影区域表示置信区间，反映预测的不确定性。</p>
      <div id="c-forecast" class="chart lg"></div>
    </div>

    <div class="panel">
      <h3>📋 可预测歌曲列表</h3>
      <p class="desc">所有具备足够历史数据、可生成未来 30 天热度预测的歌曲清单。</p>
      <div class="table-wrap">
        <table class="table">
          <thead><tr><th>歌曲名</th><th>预测天数</th><th>预测起始</th><th>预测结束</th></tr></thead>
          <tbody id="t-forecast-list"></tbody>
        </table>
      </div>
    </div>
  </section>

  <!-- ============ 用户行为 ============ -->
  <section class="page" id="page-behavior">
    <div class="metrics-row">
      <div class="metric-card"><div class="label">RFM 用户分层</div><div class="value" id="b-rfm-total">-</div></div>
      <div class="metric-card"><div class="label">流失预测样本</div><div class="value" id="b-churn-total">-</div></div>
      <div class="metric-card"><div class="label">高风险流失</div><div class="value" id="b-churn-high">-</div></div>
      <div class="metric-card"><div class="label">评论高峰时段</div><div class="value" id="b-peak-hour">-</div></div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3>🎯 RFM 用户分群分布</h3>
        <p class="desc">基于评论行为的三维 RFM 模型（最近评论距今天数 R / 评论频率 F / 评论获赞 M）进行 K-means 聚类，将用户分为高价值、成长、沉默、流失风险四类，为运营精细化触达提供分层依据。</p>
        <div id="c-rfm-pie" class="chart"></div>
      </div>
      <div class="panel">
        <h3>⚠️ 用户流失风险分布</h3>
        <p class="desc">基于 XGBoost 流失预测模型输出的概率，按 &lt;0.3 / 0.3-0.7 / &gt;0.7 划分为低/中/高三种风险等级，帮助识别需要挽留的高风险用户群体。</p>
        <div id="c-churn-pie" class="chart"></div>
      </div>
    </div>

    <div class="grid-3">
      <div class="panel">
        <h3>🕐 24 小时评论分布</h3>
        <p class="desc">所有评论在一天 24 个小时内的分布，识别用户最活跃的时段，为内容发布与推送时间提供依据。</p>
        <div id="c-hourly" class="chart"></div>
      </div>
      <div class="panel">
        <h3>📅 周内评论分布</h3>
        <p class="desc">从周一到周日的评论量分布，对比工作日与周末的活跃度差异，判断平台用户的行为节律。</p>
        <div id="c-weekday" class="chart"></div>
      </div>
      <div class="panel">
        <h3>🗓️ 月度评论分布</h3>
        <p class="desc">12 个月的评论量分布，识别暑假/寒假等季节性效应，为年度内容运营节奏提供参考。</p>
        <div id="c-monthly" class="chart"></div>
      </div>
    </div>

    <div class="grid-2">
      <div class="panel">
        <h3>🏆 流失预测模型对比</h3>
        <p class="desc">三种机器学习模型（Logistic Regression / Random Forest / XGBoost）在流失预测任务上的 AUC/F1/Accuracy 对比，选出综合表现最优的模型作为最终预测模型。</p>
        <div id="c-churn-metrics" class="chart"></div>
      </div>
      <div class="panel">
        <h3>🚨 高风险流失用户 Top10</h3>
        <p class="desc">流失概率最高的 10 位用户列表，结合其历史评论数据，便于运营人员制定精准挽留策略。</p>
        <div class="table-wrap">
          <table class="table">
            <thead><tr><th>用户ID</th><th>流失概率</th><th>风险等级</th><th>最近评论距今</th></tr></thead>
            <tbody id="t-churn-high"></tbody>
          </table>
        </div>
      </div>
    </div>
  </section>


  <!-- ============ 实验分析 ============ -->
  <section class="page" id="page-exp">
    <!-- 统计检验 -->
    <div class="panel" style="margin-bottom: 1rem;">
      <h3>📊 统计假设检验</h3>
      <p class="desc">对关键指标进行统计检验，为业务结论提供显著性支撑（p<0.05 视为显著）。</p>
      <table class="data-table">
        <thead><tr><th>检验名称</th><th>类型</th><th>样本量</th><th>统计量</th><th>p值</th><th>效应量</th><th>显著性</th><th>结论</th></tr></thead>
        <tbody id="t-stat-tests"></tbody>
      </table>
    </div>

    <!-- 同期群留存 -->
    <div class="panel" style="margin-bottom: 1rem;">
      <h3>🔥 同期群留存矩阵</h3>
      <p class="desc">按用户首次评论周分群，追踪各 cohort 的评论留存率变化。颜色越深表示留存率越高。</p>
      <div id="c-cohort" class="chart" style="height: 400px;"></div>
    </div>

    <!-- A/B 实验 -->
    <div class="panel">
      <h3>🧪 A/B 测试报告</h3>
      <p class="desc">模拟实验：对热门歌曲推送通知，对比推送组 vs 对照组的评论数变化。展示完整实验设计流程。</p>
      <div id="ab-test-report"></div>
    </div>
  </section>

  <div class="foot">
    本页数据由 Python 脚本从 MySQL 实时拉取生成 · 内嵌 ECharts CDN · 仅供本地查看
  </div>
</main>

<script>
const DATA = __DATA__;
const INK = '#4a3f35';
const AL = '#6b5e52';
const GRID = '#d6c6b1';
const FOLK = ['#8b6b4d', '#c0392b', '#5a7d6b', '#d4a373', '#a98467', '#7a9d8b', '#b07d62', '#d98880'];

function grid(opt) {
  return Object.assign({ left: 50, right: 20, top: 30, bottom: 35, containLabel: true }, opt || {});
}
function axis(color) {
  return {
    axisLine: { lineStyle: { color: color || GRID } },
    axisLabel: { color: AL },
    splitLine: { lineStyle: { color: 'rgba(51,65,85,0.4)' } }
  };
}

// 记录所有 ECharts 实例，便于切换页面时 resize
const chartInstances = {};
function makeChart(id) {
  const el = document.getElementById(id);
  if (!el) return null;
  const inst = echarts.init(el);
  chartInstances[id] = inst;
  return inst;
}

// ============ 导航切换 ============
const pageTitles = {
  home: '首页总览',
  songs: '歌曲分析',
  users: '用户画像',
  text: '文本洞察',
  sentiment: '情感研究',
  predict: '爆款预测',
  forecast: '热度预测',
  behavior: '用户行为',
  exp: '实验分析'
};
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    const page = item.dataset.page;
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    item.classList.add('active');
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('page-' + page).classList.add('active');
    document.getElementById('page-title').textContent = pageTitles[page];
    // 触发所有 chart resize（延迟确保容器已渲染）
    setTimeout(() => {
      Object.values(chartInstances).forEach(c => c && c.resize());
      // 切到歌曲分析页时，确保评论滚动已启动
      if (page === 'songs') {
        const songSel = document.getElementById('song-select');
        if (songSel) songSel.dispatchEvent(new Event('change'));
      }
    }, 150);
  });
});

document.getElementById('gen-at').textContent = DATA.generated_at;

// ============ 首页 ============
(function home() {
  document.getElementById('m-songs').textContent = (DATA.count_songs || 0).toLocaleString();
  document.getElementById('m-comments').textContent = (DATA.total_comments || 0).toLocaleString();
  document.getElementById('m-likes').textContent = (DATA.total_likes || 0).toLocaleString();
  document.getElementById('m-rate').textContent = ((DATA.interaction_rate || 0) * 100).toFixed(2) + '%';

  // 趋势
  const tEl = document.getElementById('c-trend');
  if (!DATA.trend_30d || DATA.trend_30d.length === 0) {
    tEl.innerHTML = '<div class="empty">暂无近 30 天热度数据</div>';
  } else {
    const chart = makeChart('c-trend');
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['热度分', '评论数', '回复数'], textStyle: { color: INK }, top: 0 },
      grid: grid({ top: 35 }),
      xAxis: Object.assign({ type: 'category', data: DATA.trend_30d.map(r => r.dt) }, axis()),
      yAxis: Object.assign({ type: 'value' }, axis()),
      series: [
        { name: '热度分', type: 'line', smooth: true, data: DATA.trend_30d.map(r => Number(r.total_heat || 0)),
          itemStyle: { color: '#8b6b4d' },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(139,107,77,0.35)' }, { offset: 1, color: 'rgba(139,107,77,0.02)' }
          ]) },
          lineStyle: { width: 3 }
        },
        { name: '评论数', type: 'line', smooth: true, data: DATA.trend_30d.map(r => Number(r.total_comment || 0)), itemStyle: { color: '#5a7d6b' } },
        { name: '回复数', type: 'line', smooth: true, data: DATA.trend_30d.map(r => Number(r.total_reply || 0)), itemStyle: { color: '#c0392b' } },
      ]
    });
  }

  // Top5
  const top5El = document.getElementById('c-top5');
  if (!DATA.song_top5 || DATA.song_top5.length === 0) {
    top5El.innerHTML = '<div class="empty">暂无歌曲热度数据</div>';
  } else {
    const chart = makeChart('c-top5');
    chart.setOption({
      tooltip: { trigger: 'axis', formatter: function(p) {
        return p[0].name + '<br/>热度分: ' + Number(p[0].value).toFixed(4);
      }},
      grid: grid({ left: 110, right: 70 }),
      xAxis: Object.assign({
        type: 'value',
        axisLabel: { color: INK, formatter: function(v) { return Number(v).toFixed(2); } }
      }, axis({ splitLine: { lineStyle: { color: 'rgba(139,107,77,0.15)' } } })),
      yAxis: Object.assign({ type: 'category', data: DATA.song_top5.map(r => r.name), inverse: true },
        { axisLabel: { color: INK, fontSize: 11 }, axisLine: { lineStyle: { color: GRID } }, splitLine: { show: false } }),
      series: [{
        type: 'bar', data: DATA.song_top5.map(r => Number(r.heat || 0)),
        itemStyle: { color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#c0392b' }, { offset: 1, color: '#d98880' }
        ]), borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: 'right', color: INK, formatter: function(p) { return Number(p.value).toFixed(2); } },
        barMaxWidth: 26
      }]
    });
  }

  // 用户画像
  const pEl = document.getElementById('c-portrait');
  if (!DATA.user_portrait || DATA.user_portrait.length === 0) {
    pEl.innerHTML = '<div class="empty">暂无数据</div>';
  } else {
    const chart = makeChart('c-portrait');
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      series: [{
        type: 'pie', radius: ['35%', '65%'],
        data: DATA.user_portrait.map(r => ({ name: r.user_type, value: r.cnt })),
        label: { color: INK, fontSize: 10, formatter: '{b}\n{d}%' },
        itemStyle: { borderColor: '#f5efe6', borderWidth: 2 },
        color: ['#8b6b4d', '#c0392b', '#5a7d6b', '#d4a373', '#a98467', '#7a9d8b']
      }]
    });
  }

  // 情感
  const sEl = document.getElementById('c-sentiment');
  const s = DATA.sentiment_summary || {};
  if (!s.positive_ratio && !s.neutral_ratio && !s.negative_ratio) {
    sEl.innerHTML = '<div class="empty">暂无数据</div>';
  } else {
    const chart = makeChart('c-sentiment');
    chart.setOption({
      tooltip: { trigger: 'item' },
      series: [{
        type: 'pie', radius: ['45%', '70%'],
        data: [
          { name: '正面', value: Number(s.positive_ratio || 0), itemStyle: { color: '#5a7d6b' } },
          { name: '中性', value: Number(s.neutral_ratio || 0), itemStyle: { color: '#8c7b6c' } },
          { name: '负面', value: Number(s.negative_ratio || 0), itemStyle: { color: '#c0392b' } },
        ],
        label: { color: INK, formatter: '{b}\n{d}%' },
        itemStyle: { borderColor: '#f5efe6', borderWidth: 2 }
      }]
    });
  }

  // 爆款 Top10 进度条
  const hEl = document.getElementById('hot-list');
  if (!DATA.hot_predict_top10 || DATA.hot_predict_top10.length === 0) {
    hEl.innerHTML = '<div class="empty">暂无爆款预测数据</div>';
  } else {
    const maxProb = Math.max(...DATA.hot_predict_top10.map(r => Number(r.hot_prob || 0)), 0.01);
    hEl.innerHTML = DATA.hot_predict_top10.map(r => {
      const prob = Number(r.hot_prob || 0);
      const w = (prob / maxProb * 100).toFixed(1);
      return '<div class="hit-row">'
        + '<div class="name" title="' + r.song_name + '">' + r.song_name + '</div>'
        + '<div class="bar-bg"><div class="bar-fill" style="width:' + w + '%;"></div></div>'
        + '<div class="val">' + (prob * 100).toFixed(2) + '%</div></div>';
    }).join('');
  }

  // 热力图
  const hmEl = document.getElementById('c-heatmap');
  if (!DATA.heatmap || !DATA.heatmap.data || DATA.heatmap.data.length === 0) {
    hmEl.innerHTML = '<div class="empty">暂无行为数据</div>';
  } else {
    const chart = makeChart('c-heatmap');
    const hours = Array.from({ length: 24 }, (_, i) => i + ':00');
    chart.setOption({
      tooltip: { position: 'top' },
      grid: grid({ left: 50, right: 10, top: 10, bottom: 50 }),
      xAxis: Object.assign({ type: 'category', data: hours, splitArea: { show: true } }, axis()),
      yAxis: Object.assign({ type: 'category', data: DATA.heatmap.y_labels, splitArea: { show: true } },
        { axisLabel: { color: INK }, axisLine: { lineStyle: { color: GRID } } }),
      visualMap: {
        min: 0, max: DATA.heatmap.max,
        orient: 'horizontal', left: 'center', bottom: 5,
        textStyle: { color: INK },
        inRange: { color: ['#faf6f0', '#f0e6d6', '#e0cfba', '#c9a87c', '#8b6b4d'] }
      },
      series: [{
        type: 'heatmap',
        data: DATA.heatmap.data.map(d => [d[0], d[1], d[2]]),
        label: { show: false },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(74,63,53,0.3)' } }
      }]
    });
  }
})();

// ============ 歌曲分析 ============
(function songs() {
  // 填充下拉
  const sel = document.getElementById('song-select');
  const search = document.getElementById('song-search');
  const countEl = document.getElementById('song-count');
  if (!DATA.song_details || DATA.song_details.length === 0) {
    sel.innerHTML = '<option>暂无歌曲数据</option>';
    return;
  }
  function renderOptions(items, selectedIdx) {
    sel.innerHTML = items.map((s, i) =>
      '<option value="' + s._idx + '">' + s.song_name + ' - ' + (s.artist_name || '未知歌手') + ' (' + s.comment_count + '评论)</option>'
    ).join('');
    // 保持当前选择或默认第一项
    const want = selectedIdx !== undefined ? selectedIdx : 0;
    if (sel.querySelector('option[value="' + want + '"]')) {
      sel.value = want;
    } else if (sel.options.length) {
      sel.selectedIndex = 0;
    }
    countEl.textContent = items.length;
  }
  DATA.song_details.forEach((s, i) => s._idx = i);
  renderOptions(DATA.song_details);

  search.addEventListener('input', () => {
    const kw = search.value.trim().toLowerCase();
    const filtered = kw ? DATA.song_details.filter(s =>
      (s.song_name + ' ' + (s.artist_name || '')).toLowerCase().indexOf(kw) !== -1
    ) : DATA.song_details.slice();
    const currentVal = parseInt(sel.value, 10);
    renderOptions(filtered, isNaN(currentVal) ? undefined : currentVal);
  });

  // 评论数列表
  const tb = document.getElementById('t-song-list');
  tb.innerHTML = DATA.song_details.map(s =>
    '<tr><td>' + s.song_name + '</td><td>' + (s.artist_name || '-') + '</td>'
    + '<td class="num">' + (s.comment_count || 0) + '</td></tr>'
  ).join('');

  function renderSong(idx) {
    const s = DATA.song_details[idx];
    if (!s) return;

    // 生命周期
    const lcEl = document.getElementById('c-lifecycle');
    if (chartInstances['c-lifecycle']) { chartInstances['c-lifecycle'].dispose(); }
    if (!s.lifecycle || s.lifecycle.length === 0) {
      lcEl.innerHTML = '<div class="empty">该歌曲暂无日度热度数据</div>';
    } else {
      const chart = makeChart('c-lifecycle');
      chart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['热度分', '评论数', '回复数'], textStyle: { color: INK }, top: 0 },
        grid: grid({ top: 35 }),
        xAxis: Object.assign({ type: 'category', data: s.lifecycle.map(r => r.dt) }, axis()),
        yAxis: Object.assign({ type: 'value' }, axis()),
        series: [
          { name: '热度分', type: 'line', smooth: true, data: s.lifecycle.map(r => Number(r.heat_score || 0)),
            itemStyle: { color: '#8b6b4d' }, lineStyle: { width: 3 } },
          { name: '评论数', type: 'line', smooth: true, data: s.lifecycle.map(r => Number(r.comment_count || 0)), itemStyle: { color: '#5a7d6b' } },
          { name: '回复数', type: 'line', smooth: true, data: s.lifecycle.map(r => Number(r.reply_count || 0)), itemStyle: { color: '#c0392b' } },
        ]
      });
    }

    // 关键词
    const kwEl = document.getElementById('c-song-kw');
    if (chartInstances['c-song-kw']) { chartInstances['c-song-kw'].dispose(); }
    if (!s.keywords || s.keywords.length === 0) {
      kwEl.innerHTML = '<div class="empty">该歌曲暂无关键词（可能无评论数据）</div>';
    } else {
      const chart = makeChart('c-song-kw');
      const kws = s.keywords;
      chart.setOption({
        grid: grid({ left: 90 }),
        xAxis: Object.assign({ type: 'value' }, axis()),
        yAxis: Object.assign({ type: 'category', data: kws.map(k => k.word), inverse: true },
          { axisLabel: { color: INK, fontSize: 11 }, axisLine: { lineStyle: { color: GRID } } }),
        series: [{
          type: 'bar', data: kws.map(k => Number(k.score || 0)),
          itemStyle: { color: '#8b6b4d', borderRadius: [0, 3, 3, 0] },
          label: { show: true, position: 'right', color: INK }
        }]
      });
    }

    // 情感
    const sentEl = document.getElementById('c-song-sent');
    if (chartInstances['c-song-sent']) { chartInstances['c-song-sent'].dispose(); }
    const sent = s.sentiment || {};
    if (!sent.positive && !sent.neutral && !sent.negative) {
      sentEl.innerHTML = '<div class="empty">该歌曲暂无情感数据</div>';
    } else {
      const chart = makeChart('c-song-sent');
      chart.setOption({
        tooltip: { trigger: 'item' },
        series: [{
          type: 'pie', radius: ['45%', '70%'],
          data: [
            { name: '正面', value: Number(sent.positive || 0), itemStyle: { color: '#5a7d6b' } },
            { name: '中性', value: Number(sent.neutral || 0), itemStyle: { color: '#8c7b6c' } },
            { name: '负面', value: Number(sent.negative || 0), itemStyle: { color: '#c0392b' } },
          ],
          label: { color: INK, formatter: '{b}\n{d}%' },
          itemStyle: { borderColor: '#f5efe6', borderWidth: 2 }
        }]
      });
    }

    // 高赞评论滚动
    renderComments(s.top_comments || []);
  }

  // 高赞评论渲染与自动滚动
  let commentTimer = null;
  function renderComments(comments) {
    const listEl = document.getElementById('comment-list');
    clearInterval(commentTimer);
    if (!comments || comments.length === 0) {
      listEl.innerHTML = '<div class="empty" style="padding-top:3rem;">该歌曲暂无评论数据</div>';
      return;
    }
    // 复制一份用于无缝滚动
    const items = comments.slice();
    const dup = items.concat(items);
    listEl.innerHTML = dup.map((c, i) => {
      const rank = (i % items.length) + 1;
      const date = c.comment_time ? c.comment_time.split('T')[0] : '-';
      return '<div class="comment-item">'
        + '<div class="rank">' + rank + '</div>'
        + '<div class="body">'
        + '<div class="text">' + (c.content || '').replace(/</g, '&lt;').replace(/>/g, '&gt;') + '</div>'
        + '<div class="meta"><span class="like">👍 ' + (c.like_count || 0) + '</span><span>' + date + '</span></div>'
        + '</div></div>';
    }).join('');

    // 每次滚动一条评论的高度（使用 CSS 固定高度 60px，避免页面初始隐藏时 offsetHeight 为 0）
    const itemH = 60;
    let pos = 0;
    listEl.style.transform = 'translateY(0px)';
    commentTimer = setInterval(() => {
      pos += itemH;
      if (pos >= itemH * items.length) {
        listEl.style.transition = 'none';
        pos = 0;
        listEl.style.transform = 'translateY(0px)';
        // 强制重绘
        listEl.offsetHeight;
        listEl.style.transition = 'transform 0.6s ease-in-out';
      }
      listEl.style.transform = 'translateY(-' + pos + 'px)';
    }, 2500);
  }

  sel.addEventListener('change', () => renderSong(parseInt(sel.value)));
  renderSong(0);
})();


// 通用中文映射
const MODEL_LABEL = { XGBoost: 'XGBoost 梯度提升', LogisticRegression: '逻辑回归' };
const FEATURE_LABEL = {
  total_comment_count: '歌曲累计评论数', total_reply_count: '歌曲累计回复数',
  total_like_total: '歌曲累计获赞数', valid_comment_count: '有效评论数',
  negative_ratio: '负面情感占比', positive_ratio: '正面情感占比',
  avg_heat_score: '平均热度分', max_heat_score: '最高热度分',
  days_since_release: '发行距今天数', release_year: '发行年份',
  artist_comment_count: '歌手累计评论数', artist_reply_count: '歌手累计回复数',
  artist_like_total: '歌手累计获赞数', release_month: '发行月份',
  topic_count: '主题覆盖数', like_per_comment: '每条评论平均获赞',
  reply_per_comment: '每条评论平均回复'
};
const FEATURE_DESC = {
  total_comment_count: '该歌曲收到的评论总数，反映用户参与度',
  total_reply_count: '该歌曲评论的回复总数，反映讨论深度',
  total_like_total: '该歌曲评论获得的总点赞数，反映共鸣程度',
  valid_comment_count: '经过去重、清洗后保留的有效评论数量',
  negative_ratio: '负面情感评论在所有评论中的占比',
  positive_ratio: '正面情感评论在所有评论中的占比',
  avg_heat_score: '该歌曲日均热度分的平均值',
  days_since_release: '歌曲发行日期距离现在的天数，越新天数越小',
  max_heat_score: '该歌曲曾达到的最高热度分',
  release_year: '歌曲发行年份',
  artist_comment_count: '该歌手所有歌曲的累计评论数',
  artist_reply_count: '该歌手所有歌曲的累计回复数',
  artist_like_total: '该歌手所有歌曲评论的累计获赞数',
  release_month: '歌曲发行月份',
  topic_count: '该歌曲评论覆盖的 LDA 主题数量',
  like_per_comment: '每条评论平均获得的点赞数，反映评论质量',
  reply_per_comment: '每条评论平均收到的回复数，反映讨论深度'
};
const METRIC_DESC = {
  AUC: 'ROC 曲线下面积：衡量模型区分爆款与非爆款的能力，越接近 1 越好',
  F1: '精确率与召回率的调和平均：综合衡量模型预测的准确性',
  Accuracy: '准确率：预测正确的样本占总样本的比例'
};

// ============ 用户画像 ============
(function users() {
  // 用户类型解释
  const USER_TYPE_DESC = {
    '核心粉丝': '高频评论、深度互动：评论数、回复数、获赞数均显著高于平均水平，是社区活跃度和热度的主要贡献者。',
    '内容消费者': '以浏览和轻度评论为主：经常发表评论，但回复、获赞等深度互动较少，是社区的主要流量基础。',
    '轻度用户': '偶尔评论、低活跃度：评论和互动行为都很少，处于流失边缘或新进入社区。'
  };

  // 用户类型
  const utEl = document.getElementById('c-user-type');
  if (!DATA.user_portrait || DATA.user_portrait.length === 0) {
    utEl.innerHTML = '<div class="empty">暂无用户画像数据</div>';
  } else {
    const chart = makeChart('c-user-type');
    chart.setOption({
      tooltip: {
        trigger: 'item',
        confine: true,
        extraCssText: 'max-width:260px; white-space:normal; word-wrap:break-word; line-height:1.6;',
        formatter: function(p) {
          const desc = USER_TYPE_DESC[p.name] || '';
          return '<strong>' + p.name + '</strong>'
            + '<br/>数量: ' + p.value.toLocaleString()
            + '<br/>占比: ' + p.percent + '%'
            + (desc ? '<br/><br/>' + desc : '');
        }
      },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: DATA.user_portrait.map(r => ({ name: r.user_type, value: r.cnt })),
        label: { color: INK, formatter: '{b}\n{d}%' },
        itemStyle: { borderColor: '#f5efe6', borderWidth: 2 },
        color: ['#8b6b4d', '#c0392b', '#5a7d6b', '#d4a373', '#a98467', '#7a9d8b']
      }]
    });
  }

  // 用户价值分布
  const uvEl = document.getElementById('c-user-value');
  if (!DATA.user_value_dist || DATA.user_value_dist.length === 0) {
    uvEl.innerHTML = '<div class="empty">暂无数据</div>';
  } else {
    const chart = makeChart('c-user-value');
    const uvData = DATA.user_value_dist.filter(r => r.count > 0);
    chart.setOption({
      tooltip: { trigger: 'axis', formatter: function(p) {
        const d = p[0];
        return d.name + '<br/>人数: ' + d.value;
      }},
      grid: grid({ bottom: 50 }),
      xAxis: Object.assign({
        type: 'category',
        data: DATA.user_value_dist.map(r => r.range),
        name: '用户价值区间',
        nameTextStyle: { color: AL },
        axisLabel: { color: AL, rotate: 35, fontSize: 9, interval: 0 }
      }, axis()),
      yAxis: Object.assign({ type: 'value', name: '人数', nameTextStyle: { color: AL } }, axis()),
      series: [{
        type: 'bar',
        data: DATA.user_value_dist.map(r => r.count),
        itemStyle: { color: '#8b6b4d', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 30
      }]
    });
  }

  // 评论时段分布
  const bEl = document.getElementById('c-behavior');
  if (!DATA.comment_pattern || DATA.comment_pattern.length === 0) {
    bEl.innerHTML = '<div class="empty">暂无评论时段数据</div>';
  } else {
    const order = ['凌晨', '上午', '下午', '晚上'];
    const sorted = order.map(o => DATA.comment_pattern.find(r => r.time_period === o) || { time_period: o, cnt: 0 });
    const chart = makeChart('c-behavior');
    chart.setOption({
      tooltip: { trigger: 'axis', formatter: function(p) { return p[0].name + '<br/>评论数: ' + p[0].value.toLocaleString(); } },
      grid: grid({ left: 50, right: 30 }),
      xAxis: Object.assign({ type: 'category', data: sorted.map(r => r.time_period), name: '时段', nameTextStyle: { color: AL } }, axis()),
      yAxis: Object.assign({ type: 'value', name: '评论数', nameTextStyle: { color: AL } }, axis()),
      series: [{
        type: 'bar',
        data: sorted.map(r => r.cnt),
        itemStyle: { color: '#5a7d6b', borderRadius: [3, 3, 0, 0] },
        barMaxWidth: 50,
        label: { show: true, position: 'top', color: INK }
      }]
    });
  }

  // 高价值用户表
  const tb = document.getElementById('t-users');
  if (!DATA.top_users || DATA.top_users.length === 0) {
    tb.innerHTML = '<tr><td colspan="8" class="empty">暂无数据</td></tr>';
  } else {
    tb.innerHTML = DATA.top_users.map(u =>
      '<tr><td class="num">' + u.user_id + '</td><td>' + (u.nickname || '-') + '</td>'
      + '<td>' + (u.user_type || '-') + '</td>'
      + '<td class="num">' + Number(u.user_value || 0).toFixed(4) + '</td>'
      + '<td class="num">' + (u.total_comment || 0) + '</td>'
      + '<td class="num">' + (u.total_like || 0) + '</td>'
      + '<td>' + (u.active_period || '-') + '</td>'
      + '<td>' + (u.sentiment_type || '-') + '</td></tr>'
    ).join('');
  }
})();

// ============ 文本洞察 ============
(function text() {
  // 全局关键词
  const kEl = document.getElementById('c-keywords');
  if (!DATA.global_keywords || DATA.global_keywords.length === 0) {
    kEl.innerHTML = '<div class="empty">暂无关键词数据</div>';
  } else {
    const chart = makeChart('c-keywords');
    const kws = DATA.global_keywords;
    chart.setOption({
      grid: grid({ left: 90 }),
      xAxis: Object.assign({ type: 'value' }, axis()),
      yAxis: Object.assign({ type: 'category', data: kws.map(k => k.word).reverse() },
        { axisLabel: { color: INK, fontSize: 11 }, axisLine: { lineStyle: { color: GRID } } }),
      series: [{
        type: 'bar', data: kws.map(k => Number(k.score || 0)).reverse(),
        itemStyle: { color: '#8b6b4d', borderRadius: [0, 3, 3, 0] },
        label: { show: true, position: 'right', color: INK }
      }]
    });
  }

  // 主题列表
  const tl = document.getElementById('topic-list');
  if (!DATA.topics || DATA.topics.length === 0) {
    tl.innerHTML = '<div class="empty">暂无主题数据</div>';
  } else {
    tl.innerHTML = DATA.topics.map(t => {
      const name = t.topic_name || ('主题' + t.topic_id);
      return '<div><span class="t">' + name + '</span>' + (t.keywords || '-') + '</div>';
    }).join('');
  }

  // 主题分布
  const tdEl = document.getElementById('c-topic-dist');
  if (!DATA.topic_dist || DATA.topic_dist.length === 0) {
    tdEl.innerHTML = '<div class="empty">暂无主题分布数据</div>';
  } else {
    const chart = makeChart('c-topic-dist');
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
      series: [{
        type: 'pie', radius: ['40%', '70%'],
        data: DATA.topic_dist.map(r => ({ name: r.topic_name || ('主题' + r.topic_id), value: r.cnt })),
        label: { color: INK, formatter: '{b}\n{d}%' },
        itemStyle: { borderColor: '#f5efe6', borderWidth: 2 },
        color: ['#8b6b4d', '#c0392b', '#5a7d6b', '#d4a373', '#a98467', '#7a9d8b']
      }]
    });
  }

  // 歌曲情感 Top15
  const sslEl = document.getElementById('c-song-sent-list');
  if (!DATA.song_sentiments || DATA.song_sentiments.length === 0) {
    sslEl.innerHTML = '<div class="empty">暂无数据</div>';
  } else {
    const chart = makeChart('c-song-sent-list');
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['正面', '中性', '负面'], textStyle: { color: INK }, top: 0 },
      grid: grid({ top: 35, left: 130 }),
      xAxis: Object.assign({ type: 'value' }, axis()),
      yAxis: Object.assign({ type: 'category', data: DATA.song_sentiments.map(s => s.song_name), inverse: true },
        { axisLabel: { color: INK, fontSize: 10 }, axisLine: { lineStyle: { color: GRID } } }),
      series: [
        { name: '正面', type: 'bar', stack: 't', data: DATA.song_sentiments.map(s => Number(s.positive || 0)), itemStyle: { color: '#5a7d6b' } },
        { name: '中性', type: 'bar', stack: 't', data: DATA.song_sentiments.map(s => Number(s.neutral || 0)), itemStyle: { color: '#8c7b6c' } },
        { name: '负面', type: 'bar', stack: 't', data: DATA.song_sentiments.map(s => Number(s.negative || 0)), itemStyle: { color: '#c0392b' } },
      ]
    });
  }
})();

// ============ 情感研究 ============
(function sentiment() {
  const w = DATA.sentiment_weekly || [];
  const rising = DATA.sentiment_rising || [];
  const falling = DATA.sentiment_falling || [];
  const scatter = DATA.sentiment_scatter || [];

  // 顶部指标卡
  const totalComments = w.length ? w[w.length - 1].count : 0;
  const totalAll = w.reduce((s, x) => s + x.count, 0);
  const avgPos = w.length ? (w.reduce((s, x) => s + x.positive_ratio, 0) / w.length) : 0;
  const avgNeg = w.length ? (w.reduce((s, x) => s + x.negative_ratio, 0) / w.length) : 0;
  const avgProb = w.length ? (w.reduce((s, x) => s + x.avg_positive_prob, 0) / w.length) : 0;
  document.getElementById('sm-comments').textContent = totalAll.toLocaleString();
  document.getElementById('sm-pos').textContent = (avgPos * 100).toFixed(1) + '%';
  document.getElementById('sm-neg').textContent = (avgNeg * 100).toFixed(1) + '%';
  document.getElementById('sm-prob').textContent = (avgProb * 100).toFixed(1) + '%';

  // 1. 平台情感加速度趋势
  const swEl = document.getElementById('c-sentiment-weekly');
  if (w.length === 0) {
    swEl.innerHTML = '<div class="empty">暂无情感时间序列数据</div>';
  } else {
    const chart = makeChart('c-sentiment-weekly');
    chart.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
      legend: { data: ['正面情感占比', '情感速度', '情感加速度'], textStyle: { color: INK }, top: 0 },
      grid: grid({ top: 50, left: 55, right: 55 }),
      xAxis: Object.assign({ type: 'category', data: w.map(r => r.week) }, axis()),
      yAxis: [
        Object.assign({ type: 'value', name: '占比', axisLabel: { formatter: '{value} %' }, nameTextStyle: { color: AL } }, axis()),
        Object.assign({ type: 'value', name: '变化', axisLabel: { formatter: '{value}' }, nameTextStyle: { color: AL } }, axis())
      ],
      series: [
        {
          name: '正面情感占比', type: 'line', smooth: true,
          data: w.map(r => Number((r.positive_ratio * 100).toFixed(2))),
          itemStyle: { color: '#5a7d6b' },
          areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(90,125,107,0.25)' }, { offset: 1, color: 'rgba(90,125,107,0.02)' }
          ]) },
          yAxisIndex: 0
        },
        {
          name: '情感速度', type: 'line', smooth: true,
          data: w.map(r => Number((r.velocity * 100).toFixed(2))),
          itemStyle: { color: '#8b6b4d' }, lineStyle: { type: 'dashed' },
          yAxisIndex: 1
        },
        {
          name: '情感加速度', type: 'bar',
          data: w.map(r => Number((r.acceleration * 100).toFixed(2))),
          itemStyle: {
            color: function(p) { return p.value >= 0 ? '#8b6b4d' : '#c0392b'; }
          },
          yAxisIndex: 1
        }
      ]
    });
  }

  // 2. 情感升温最快 Top10
  const risingEl = document.getElementById('c-rising');
  if (rising.length === 0) {
    risingEl.innerHTML = '<div class="empty">暂无数据</div>';
  } else {
    const chart = makeChart('c-rising');
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: function(params) {
          const d = rising[params[0].dataIndex];
          return '<strong>' + d.song_name + '</strong><br/>'
            + '早期正面占比: ' + (d.early_positive_ratio * 100).toFixed(1) + '%<br/>'
            + '近期正面占比: ' + (d.recent_positive_ratio * 100).toFixed(1) + '%<br/>'
            + '变化率: +' + Number(d.change_rate).toFixed(1) + '%';
        }
      },
      grid: grid({ left: 130 }),
      xAxis: Object.assign({ type: 'value', axisLabel: { formatter: '{value}%' } }, axis()),
      yAxis: Object.assign({ type: 'category', data: rising.map(r => r.song_name).reverse(), inverse: true },
        { axisLabel: { color: INK, fontSize: 10 }, axisLine: { lineStyle: { color: GRID } } }),
      series: [{
        type: 'bar', data: rising.map(r => Number(r.change_rate).toFixed(1)).reverse(),
        itemStyle: { color: '#5a7d6b', borderRadius: [0, 3, 3, 0] },
        label: { show: true, position: 'right', color: INK, formatter: '{c}%' }
      }]
    });
  }

  // 3. 情感降温最快 Top10
  const fallingEl = document.getElementById('c-falling');
  if (falling.length === 0) {
    fallingEl.innerHTML = '<div class="empty">暂无数据</div>';
  } else {
    const chart = makeChart('c-falling');
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: function(params) {
          const d = falling[params[0].dataIndex];
          return '<strong>' + d.song_name + '</strong><br/>'
            + '早期正面占比: ' + (d.early_positive_ratio * 100).toFixed(1) + '%<br/>'
            + '近期正面占比: ' + (d.recent_positive_ratio * 100).toFixed(1) + '%<br/>'
            + '变化率: ' + Number(d.change_rate).toFixed(1) + '%';
        }
      },
      grid: grid({ left: 130 }),
      xAxis: Object.assign({ type: 'value', axisLabel: { formatter: '{value}%' } }, axis()),
      yAxis: Object.assign({ type: 'category', data: falling.map(r => r.song_name).reverse(), inverse: true },
        { axisLabel: { color: INK, fontSize: 10 }, axisLine: { lineStyle: { color: GRID } } }),
      series: [{
        type: 'bar', data: falling.map(r => Number(r.change_rate).toFixed(1)).reverse(),
        itemStyle: { color: '#c0392b', borderRadius: [0, 3, 3, 0] },
        label: { show: true, position: 'right', color: INK, formatter: '{c}%' }
      }]
    });
  }

  // 4. 情感得分 - 情感加速度散点图
  const scEl = document.getElementById('c-sentiment-scatter');
  if (scatter.length === 0) {
    scEl.innerHTML = '<div class="empty">暂无数据</div>';
  } else {
    const chart = makeChart('c-sentiment-scatter');
    chart.setOption({
      tooltip: {
        formatter: function(p) {
          const d = p.data;
          return '<strong>' + d[2] + '</strong><br/>'
            + '近期正面占比: ' + (d[0] * 100).toFixed(1) + '%<br/>'
            + '变化率: ' + Number(d[1]).toFixed(1) + '%<br/>'
            + '评论数: ' + d[3];
        }
      },
      grid: grid({ left: 60, right: 40 }),
      xAxis: Object.assign({ type: 'value', name: '近期正面占比', nameTextStyle: { color: AL }, axisLabel: { formatter: '{value}%' } }, axis()),
      yAxis: Object.assign({ type: 'value', name: '变化率', nameTextStyle: { color: AL }, axisLabel: { formatter: '{value}%' } }, axis()),
      series: [{
        type: 'scatter',
        data: scatter.map(r => [
          Number((r.recent_positive_ratio * 100).toFixed(1)),
          Number(r.change_rate.toFixed(1)),
          r.song_name,
          r.comment_count
        ]),
        symbolSize: function(d) { return Math.max(8, Math.min(28, 8 + d[3] / 8)); },
        itemStyle: {
          color: function(p) {
            const v = p.data[1];
            if (v >= 20) return '#5a7d6b';
            if (v >= 0) return '#8b6b4d';
            if (v >= -20) return '#d4a373';
            return '#c0392b';
          },
          opacity: 0.85
        }
      }]
    });
  }
})();

// ============ 爆款预测 ============
(function predict() {
  // 模型对比
  const mEl = document.getElementById('c-model');
  if (!DATA.model_metrics || DATA.model_metrics.length === 0) {
    mEl.innerHTML = '<div class="empty">暂无模型评估数据</div>';
  } else {
    const chart = makeChart('c-model');
    chart.setOption({
      tooltip: {
        trigger: 'axis',
        formatter: function(params) {
          let html = '<strong>' + (MODEL_LABEL[params[0].axisValue] || params[0].axisValue) + '</strong>';
          params.forEach(p => {
            html += '<br/>' + p.marker + ' ' + p.seriesName + ': ' + Number(p.value).toFixed(3)
              + '<br/><span style="max-width:220px;display:inline-block;white-space:normal;line-height:1.5;color:#94a3b8;font-size:12px;">' + (METRIC_DESC[p.seriesName] || '') + '</span>';
          });
          return html;
        }
      },
      legend: { data: ['AUC', 'F1', 'Accuracy'], textStyle: { color: INK }, top: 0 },
      grid: grid({ top: 35 }),
      xAxis: Object.assign({ type: 'category', data: DATA.model_metrics.map(r => r.model_name) }, axis()),
      yAxis: Object.assign({ type: 'value', min: 0, max: 1 }, axis()),
      series: [
        { name: 'AUC', type: 'bar', data: DATA.model_metrics.map(r => Number(r.auc || 0)), itemStyle: { color: '#8b6b4d' } },
        { name: 'F1', type: 'bar', data: DATA.model_metrics.map(r => Number(r.f1 || 0)), itemStyle: { color: '#c0392b' } },
        { name: 'Accuracy', type: 'bar', data: DATA.model_metrics.map(r => Number(r.accuracy || 0)), itemStyle: { color: '#5a7d6b' } },
      ]
    });
  }

  // 特征重要性
  const fEl = document.getElementById('c-feat');
  if (!DATA.feature_importance || DATA.feature_importance.length === 0) {
    fEl.innerHTML = '<div class="empty">暂无特征重要性</div>';
  } else {
    const chart = makeChart('c-feat');
    const feats = DATA.feature_importance;
    chart.setOption({
      tooltip: {
        trigger: 'item',
        formatter: function(p) {
          const cn = FEATURE_LABEL[p.name] || p.name;
          const desc = FEATURE_DESC[p.name] || '';
          return '<strong>' + cn + '</strong><br/>重要性: ' + Number(p.value).toFixed(4)
            + (desc ? '<br/><br/><span style="max-width:220px;display:inline-block;white-space:normal;line-height:1.5;color:#8c7b6c;font-size:12px;">' + desc + '</span>' : '');
        }
      },
      grid: grid({ left: 160, right: 70 }),
      xAxis: Object.assign({ type: 'value', axisLabel: { formatter: function(v) { return v.toFixed(2); } } }, axis()),
      yAxis: Object.assign({ type: 'category', data: feats.map(f => FEATURE_LABEL[f.feature] || f.feature).reverse() },
        { axisLabel: { color: INK, fontSize: 10 }, axisLine: { lineStyle: { color: GRID } }, splitLine: { show: false } }),
      series: [{
        type: 'bar', data: feats.map(f => Number(f.importance || 0)).reverse(),
        itemStyle: { color: '#8b6b4d', borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: 'right', color: INK, formatter: function(p) { return Number(p.value).toFixed(3); } },
        barMaxWidth: 20
      }]
    });
  }

  // 爆款预测表
  const tb = document.getElementById('t-hot-predict');
  if (!DATA.hot_predict_all || DATA.hot_predict_all.length === 0) {
    tb.innerHTML = '<tr><td colspan="5" class="empty">暂无数据</td></tr>';
  } else {
    tb.innerHTML = DATA.hot_predict_all.map((r, i) =>
      '<tr><td class="num">' + (i + 1) + '</td><td>' + r.song_name + '</td><td>' + (r.artist_name || '-') + '</td>'
      + '<td class="num">' + (Number(r.hot_prob || 0) * 100).toFixed(2) + '%</td>'
      + '<td>' + (r.is_hot_predicted ? '<span style="color:#5a7d6b">✓ 爆款</span>' : '<span style="color:#8c7b6c">-</span>') + '</td></tr>'
    ).join('');
  }
})();

// ============ 热度预测 ============
(function forecast() {
  const sel = document.getElementById('forecast-select');
  const search = document.getElementById('forecast-search');
  const countEl = document.getElementById('forecast-count');
  if (!DATA.forecast_list || DATA.forecast_list.length === 0) {
    sel.innerHTML = '<option>暂无预测数据</option>';
    document.getElementById('c-forecast').innerHTML = '<div class="empty">暂无预测数据</div>';
    document.getElementById('t-forecast-list').innerHTML = '<tr><td colspan="4" class="empty">暂无数据</td></tr>';
    return;
  }
  DATA.forecast_list.forEach((f, i) => f._idx = i);
  function renderFcOptions(items, selectedIdx) {
    sel.innerHTML = items.map(f =>
      '<option value="' + f._idx + '">' + f.song_name + '</option>'
    ).join('');
    const want = selectedIdx !== undefined ? selectedIdx : 0;
    if (sel.querySelector('option[value="' + want + '"]')) {
      sel.value = want;
    } else if (sel.options.length) {
      sel.selectedIndex = 0;
    }
    countEl.textContent = items.length;
  }
  renderFcOptions(DATA.forecast_list);

  search.addEventListener('input', () => {
    const kw = search.value.trim().toLowerCase();
    const filtered = kw ? DATA.forecast_list.filter(f => f.song_name.toLowerCase().indexOf(kw) !== -1) : DATA.forecast_list.slice();
    const currentVal = parseInt(sel.value, 10);
    renderFcOptions(filtered, isNaN(currentVal) ? undefined : currentVal);
  });

  // 列表
  const tb = document.getElementById('t-forecast-list');
  tb.innerHTML = DATA.forecast_list.map(f => {
    const data = f.data || [];
    return '<tr><td>' + f.song_name + '</td>'
      + '<td class="num">' + data.length + '</td>'
      + '<td class="num">' + (data[0] ? data[0].forecast_date : '-') + '</td>'
      + '<td class="num">' + (data[data.length - 1] ? data[data.length - 1].forecast_date : '-') + '</td></tr>';
  }).join('');

  function renderFc(idx) {
    const f = DATA.forecast_list[idx];
    if (!f) return;
    document.getElementById('forecast-title').textContent = '📈 ' + f.song_name + ' - 预测热度趋势（含置信区间）';
    const el = document.getElementById('c-forecast');
    if (chartInstances['c-forecast']) { chartInstances['c-forecast'].dispose(); }
    const data = f.data || [];
    if (data.length === 0) {
      el.innerHTML = '<div class="empty">该歌曲暂无预测数据</div>';
      return;
    }
    const chart = makeChart('c-forecast');
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['预测热度', '置信区间'], textStyle: { color: INK }, top: 0 },
      grid: grid({ top: 35 }),
      xAxis: Object.assign({ type: 'category', data: data.map(r => r.forecast_date) }, axis()),
      yAxis: Object.assign({ type: 'value', name: '热度分', nameTextStyle: { color: AL } }, axis()),
      series: [
        {
          name: '置信区间', type: 'line',
          data: data.map(r => [Number(r.heat_score_lower || 0), Number(r.heat_score_upper || 0)]),
          itemStyle: { color: 'rgba(139,107,77,0.18)' },
          lineStyle: { opacity: 0 },
          areaStyle: { color: 'rgba(139,107,77,0.18)' },
          symbol: 'none'
        },
        {
          name: '预测热度', type: 'line', smooth: true,
          data: data.map(r => Number(r.heat_score || 0)),
          itemStyle: { color: '#8b6b4d' }, lineStyle: { width: 3 }
        },
      ]
    });
  }
  sel.addEventListener('change', () => renderFc(parseInt(sel.value)));
  renderFc(0);
})();

// ============ 用户行为 ============
(function behavior() {
  document.getElementById('b-rfm-total').textContent = (DATA.rfm_total || 0).toLocaleString();
  document.getElementById('b-churn-total').textContent = (DATA.churn_total || 0).toLocaleString();
  document.getElementById('b-churn-high').textContent = (DATA.churn_high_count || 0).toLocaleString();
  document.getElementById('b-peak-hour').textContent = DATA.peak_hour || '-';

  // RFM 饼图
  const rfmEl = document.getElementById('c-rfm-pie');
  if (!DATA.rfm_dist || DATA.rfm_dist.length === 0) {
    rfmEl.innerHTML = '<div class="empty">暂无 RFM 数据</div>';
  } else {
    const chart = makeChart('c-rfm-pie');
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}: {c} 人 ({d}%)' },
      legend: { bottom: 0, textStyle: { color: INK } },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        data: DATA.rfm_dist.map((r, i) => ({
          name: r.rfm_label,
          value: Number(r.cnt),
          itemStyle: { color: FOLK[i % FOLK.length] }
        })),
        label: { color: INK, formatter: '{b}\n{d}%' }
      }]
    });
  }

  // 流失风险饼图
  const churnEl = document.getElementById('c-churn-pie');
  if (!DATA.churn_risk_dist || DATA.churn_risk_dist.length === 0) {
    churnEl.innerHTML = '<div class="empty">暂无流失预测数据</div>';
  } else {
    const colorMap = { '低': '#5a7d6b', '中': '#d4a373', '高': '#c0392b' };
    const chart = makeChart('c-churn-pie');
    chart.setOption({
      tooltip: { trigger: 'item', formatter: '{b}风险: {c} 人 ({d}%)' },
      legend: { bottom: 0, textStyle: { color: INK } },
      series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        data: DATA.churn_risk_dist.map(r => ({
          name: r.risk_level,
          value: Number(r.cnt),
          itemStyle: { color: colorMap[r.risk_level] || '#8b6b4d' }
        })),
        label: { color: INK, formatter: '{b}\n{d}%' }
      }]
    });
  }

  // 24h 评论分布
  const hourlyEl = document.getElementById('c-hourly');
  if (!DATA.tp_hourly || DATA.tp_hourly.length === 0) {
    hourlyEl.innerHTML = '<div class="empty">暂无时段数据</div>';
  } else {
    const chart = makeChart('c-hourly');
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: grid({ top: 20 }),
      xAxis: Object.assign({ type: 'category', data: DATA.tp_hourly.map(r => String(r.hour).padStart(2, '0') + ':00') }, axis()),
      yAxis: Object.assign({ type: 'value', name: '评论数' }, axis()),
      series: [{
        type: 'bar',
        data: DATA.tp_hourly.map(r => Number(r.comment_count || 0)),
        itemStyle: { color: '#8b6b4d' },
        markPoint: {
          data: [{ type: 'max', name: '高峰' }],
          symbolSize: 50,
          itemStyle: { color: '#c0392b' }
        }
      }]
    });
  }

  // 周内分布
  const weekdayEl = document.getElementById('c-weekday');
  if (!DATA.tp_weekday || DATA.tp_weekday.length === 0) {
    weekdayEl.innerHTML = '<div class="empty">暂无周内数据</div>';
  } else {
    const chart = makeChart('c-weekday');
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: grid({ top: 20 }),
      xAxis: Object.assign({ type: 'category', data: DATA.tp_weekday.map(r => r.weekday_name) }, axis()),
      yAxis: Object.assign({ type: 'value', name: '评论数' }, axis()),
      series: [{
        type: 'bar',
        data: DATA.tp_weekday.map(r => ({
          value: Number(r.comment_count || 0),
          itemStyle: { color: Number(r.is_weekend) === 1 ? '#c0392b' : '#8b6b4d' }
        }))
      }]
    });
  }

  // 月度分布
  const monthlyEl = document.getElementById('c-monthly');
  if (!DATA.tp_monthly || DATA.tp_monthly.length === 0) {
    monthlyEl.innerHTML = '<div class="empty">暂无月度数据</div>';
  } else {
    const seasonColor = { '春': '#7a9d8b', '夏': '#c0392b', '秋': '#d4a373', '冬': '#8b6b4d' };
    const chart = makeChart('c-monthly');
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: grid({ top: 20 }),
      xAxis: Object.assign({ type: 'category', data: DATA.tp_monthly.map(r => r.month + '月') }, axis()),
      yAxis: Object.assign({ type: 'value', name: '评论数' }, axis()),
      series: [{
        type: 'bar',
        data: DATA.tp_monthly.map(r => ({
          value: Number(r.comment_count || 0),
          itemStyle: { color: seasonColor[r.season] || '#8b6b4d' }
        }))
      }]
    });
  }

  // 流失预测模型对比
  const metricsEl = document.getElementById('c-churn-metrics');
  if (!DATA.churn_metrics || DATA.churn_metrics.length === 0) {
    metricsEl.innerHTML = '<div class="empty">暂无模型对比数据</div>';
  } else {
    const chart = makeChart('c-churn-metrics');
    chart.setOption({
      tooltip: { trigger: 'axis' },
      legend: { data: ['AUC', 'F1', 'Accuracy'], textStyle: { color: INK }, top: 0 },
      grid: grid({ top: 35 }),
      xAxis: Object.assign({ type: 'category', data: DATA.churn_metrics.map(r => r.model_name) }, axis()),
      yAxis: Object.assign({ type: 'value', min: 0.5, max: 1.0 }, axis()),
      series: [
        { name: 'AUC', type: 'bar', data: DATA.churn_metrics.map(r => Number(r.auc || 0)), itemStyle: { color: '#8b6b4d' } },
        { name: 'F1', type: 'bar', data: DATA.churn_metrics.map(r => Number(r.f1 || 0)), itemStyle: { color: '#c0392b' } },
        { name: 'Accuracy', type: 'bar', data: DATA.churn_metrics.map(r => Number(r.accuracy || 0)), itemStyle: { color: '#5a7d6b' } },
      ]
    });
  }

  // 高风险流失用户列表
  const churnTb = document.getElementById('t-churn-high');
  if (!DATA.churn_high_users || DATA.churn_high_users.length === 0) {
    churnTb.innerHTML = '<tr><td colspan="4" class="empty">暂无高风险用户</td></tr>';
  } else {
    churnTb.innerHTML = DATA.churn_high_users.map(r =>
      '<tr><td>' + r.user_id + '</td>'
      + '<td class="num">' + (Number(r.churn_prob || 0) * 100).toFixed(2) + '%</td>'
      + '<td><span style="color:#c0392b;font-weight:600;">' + r.risk_level + '</span></td>'
      + '<td class="num">' + r.recency_days + ' 天</td></tr>'
    ).join('');
  }
})();

// 全局 resize
window.addEventListener('resize', () => {
  Object.values(chartInstances).forEach(c => c && c.resize());
});
// ============ 实验分析 ============
(function exp() {
  // 统计检验表
  const stEl = document.getElementById('t-stat-tests');
  if (!DATA.stat_tests || DATA.stat_tests.length === 0) {
    stEl.innerHTML = '<tr><td colspan="8" class="empty">暂无统计检验数据</td></tr>';
  } else {
    stEl.innerHTML = DATA.stat_tests.map(r => {
      const sig = Number(r.p_value) < 0.05;
      const sigText = sig ? '<span style="color:#c0392b;font-weight:bold">显著</span>' : '<span style="color:#5a7d6b">不显著</span>';
      return '<tr>'
        + '<td>' + (r.test_name || '-') + '</td>'
        + '<td>' + (r.test_type || '-') + '</td>'
        + '<td class="num">' + (r.sample_size || 0) + '</td>'
        + '<td class="num">' + Number(r.statistic || 0).toFixed(4) + '</td>'
        + '<td class="num">' + Number(r.p_value || 0).toFixed(4) + '</td>'
        + '<td class="num">' + Number(r.effect_size || 0).toFixed(4) + '</td>'
        + '<td>' + sigText + '</td>'
        + '<td style="font-size:0.75rem">' + (r.conclusion || '-') + '</td>'
        + '</tr>';
    }).join('');
  }

  // 同期群留存热力图
  const coEl = document.getElementById('c-cohort');
  if (!DATA.cohort_retention || DATA.cohort_retention.length === 0) {
    coEl.innerHTML = '<div class="empty">暂无同期群留存数据</div>';
  } else {
    // 构建热力图数据
    const weeks = Array.from(new Set(DATA.cohort_retention.map(r => r.cohort_week))).slice(-20);
    const offsets = [0, 1, 2, 3, 4, 5, 6, 7, 8];
    const heatData = [];
    for (let w of weeks) {
      for (let o of offsets) {
        const row = DATA.cohort_retention.find(r => r.cohort_week === w && r.week_offset === o);
        heatData.push([
          offsets.indexOf(o),
          weeks.indexOf(w),
          row ? Number(row.retention * 100).toFixed(1) : 0
        ]);
      }
    }
    const chart = makeChart('c-cohort');
    chart.setOption({
      tooltip: { position: 'top', formatter: p => `Cohort: ${weeks[p.value[1]]}<br/>第${p.value[0]}周<br/>留存率: ${p.value[2]}%` },
      grid: { top: 30, right: 20, bottom: 60, left: 120, containLabel: true },
      xAxis: { type: 'category', data: offsets.map(o => '第' + o + '周'), axisLabel: { color: AL }, splitArea: { show: true } },
      yAxis: { type: 'category', data: weeks, axisLabel: { color: AL, fontSize: 9 }, splitArea: { show: true } },
      visualMap: { min: 0, max: 5, calculable: true, orient: 'horizontal', left: 'center', bottom: 0,
        textStyle: { color: AL }, inRange: { color: ['#faf6f0', '#e6d9c6', '#d4a373', '#c0392b'] } },
      series: [{ name: '留存率', type: 'heatmap', data: heatData,
        label: { show: true, color: '#3a2e22', fontSize: 8 },
        emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' } } }]
    });
  }

  // A/B 测试报告
  const abEl = document.getElementById('ab-test-report');
  if (!DATA.ab_test || DATA.ab_test.length === 0) {
    abEl.innerHTML = '<div class="empty">暂无A/B测试数据</div>';
  } else {
    const r = DATA.ab_test[0];
    const sig = Number(r.is_significant) === 1;
    const sigColor = sig ? '#c0392b' : '#5a7d6b';
    const sigText = sig ? '显著' : '不显著';
    abEl.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.75rem;margin-bottom:1rem;">
        <div class="metric-card" style="text-align:center;padding:0.75rem;">
          <div style="font-size:0.7rem;color:#9a8a78;">对照组均值</div>
          <div style="font-size:1.3rem;font-weight:bold;color:#8b6b4d;">${Number(r.control_mean).toFixed(2)}</div>
        </div>
        <div class="metric-card" style="text-align:center;padding:0.75rem;">
          <div style="font-size:0.7rem;color:#9a8a78;">实验组均值</div>
          <div style="font-size:1.3rem;font-weight:bold;color:#5a7d6b;">${Number(r.treatment_mean).toFixed(2)}</div>
        </div>
        <div class="metric-card" style="text-align:center;padding:0.75rem;">
          <div style="font-size:0.7rem;color:#9a8a78;">相对提升</div>
          <div style="font-size:1.3rem;font-weight:bold;color:#c0392b;">+${(Number(r.lift_ratio)*100).toFixed(2)}%</div>
        </div>
        <div class="metric-card" style="text-align:center;padding:0.75rem;">
          <div style="font-size:0.7rem;color:#9a8a78;">显著性</div>
          <div style="font-size:1.3rem;font-weight:bold;color:${sigColor};">${sigText}</div>
        </div>
      </div>
      <table class="data-table">
        <tr><td>实验名称</td><td>${r.test_name || '-'}</td></tr>
        <tr><td>核心指标</td><td>${r.metric_name || '-'}</td></tr>
        <tr><td>每组样本量</td><td>${r.sample_size || 0} 人</td></tr>
        <tr><td>统计量</td><td>${Number(r.statistic).toFixed(4)}</td></tr>
        <tr><td>p值</td><td>${Number(r.p_value).toFixed(4)}</td></tr>
        <tr><td>Cohen d 效应量</td><td>${Number(r.effect_size).toFixed(4)}</td></tr>
        <tr><td>95%置信区间</td><td>[${(Number(r.ci_lower)*100).toFixed(2)}%, ${(Number(r.ci_upper)*100).toFixed(2)}%]</td></tr>
        <tr><td>结论</td><td style="font-size:0.8rem;">${r.conclusion || '-'}</td></tr>
      </table>
    `;
  }
})();

</script>
</body>
</html>
"""


def main():
    print("[1/2] 正在从 MySQL 拉取数据...")
    data = collect_data()
    print(f"  用户 {data['count_users']} / 歌曲 {data['count_songs']} / 评论 {data['count_comments']}")
    print(f"  30天趋势 {len(data['trend_30d'])} 点 / Top5 {len(data['song_top5'])} / 主题 {len(data['topics'])}")
    print(f"  歌曲详情 {len(data['song_details'])} / 预测歌曲 {len(data['forecast_list'])}")
    print(f"  RFM 分群 {data.get('rfm_total', 0)} / 流失预测 {data.get('churn_total', 0)} / 时段数据 {len(data.get('tp_hourly', []))}")

    print("[2/2] 正在生成 HTML...")
    html = HTML_TEMPLATE.replace("__DATA__", safe_json(data))
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  [OK] 已生成: {out_path}")
    print(f"  文件大小: {os.path.getsize(out_path) / 1024:.1f} KB")


if __name__ == "__main__":
    main()
