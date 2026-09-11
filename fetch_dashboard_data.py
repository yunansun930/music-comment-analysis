import sys
sys.path.insert(0, 'step4指标体系')
from config import DB_CONFIG
import pymysql, json
from decimal import Decimal
from datetime import datetime, date

def safe_json(obj):
    if isinstance(obj, (Decimal, datetime, date)):
        return str(obj)
    raise TypeError(f'Not serializable {type(obj)}')

conn = pymysql.connect(**DB_CONFIG)
cur = conn.cursor(pymysql.cursors.DictCursor)
data = {}

# Core counts
cur.execute('SELECT COUNT(*) c FROM dwd_song_info'); data['song_count'] = cur.fetchone()['c']
cur.execute('SELECT COUNT(*) c FROM dwd_user_info'); data['user_count'] = cur.fetchone()['c']
cur.execute('SELECT COUNT(*) c FROM dwd_comment_detail'); data['comment_count'] = cur.fetchone()['c']
cur.execute('SELECT COUNT(*) c FROM dwd_artist_info'); data['artist_count'] = cur.fetchone()['c']
cur.execute('SELECT SUM(like_count) s FROM dwd_comment_detail'); r = cur.fetchone(); data['total_likes'] = int(r['s'] or 0)
cur.execute('SELECT SUM(reply_count) s FROM dwd_comment_detail'); r = cur.fetchone(); data['total_replies'] = int(r['s'] or 0)
data['interaction_rate'] = round((data['total_likes'] + data['total_replies']) / max(data['comment_count'],1) * 100, 2)

# Hot songs - join with dwd_song_info for names
cur.execute('SELECT r.song_id, r.heat_rank, r.heat_score, r.comment_count, r.like_total, r.lifecycle_stage, s.song_name, s.artist_name FROM ads_song_rank r JOIN dwd_song_info s ON r.song_id = s.song_id ORDER BY r.heat_score DESC LIMIT 10')
data['hot_songs'] = cur.fetchall()

# K-means clusters
cur.execute('SELECT user_type, COUNT(*) user_count, ROUND(COUNT(*)*100.0/(SELECT COUNT(*) FROM ads_user_portrait WHERE user_type IS NOT NULL), 1) pct FROM ads_user_portrait WHERE user_type IS NOT NULL GROUP BY user_type')
data['kmeans_clusters'] = cur.fetchall()

# RFM
cur.execute('SELECT rfm_label, COUNT(*) user_count FROM ads_user_rfm GROUP BY rfm_label')
data['rfm_dist'] = cur.fetchall()

# Sentiment summary
cur.execute('SELECT * FROM ads_sentiment_summary LIMIT 1')
data['sentiment_summary'] = cur.fetchone()

# Model metrics (hot song prediction)
cur.execute('SELECT * FROM ads_model_metrics')
data['model_metrics'] = cur.fetchall()

# Churn metrics
cur.execute('SELECT * FROM ads_churn_metrics')
data['churn_metrics'] = cur.fetchall()

# Churn risk
cur.execute('SELECT risk_level, COUNT(*) user_count FROM ads_churn_predict GROUP BY risk_level')
data['churn_risk'] = cur.fetchall()

# Feature importance
cur.execute('SELECT feature, importance FROM ads_feature_importance LIMIT 8')
data['feature_importance'] = cur.fetchall()

# Hourly pattern
cur.execute('SELECT hour, comment_count, user_count, pct FROM ads_time_pattern_hourly ORDER BY hour')
data['hourly'] = cur.fetchall()

# Weekday pattern
cur.execute('SELECT weekday, weekday_name, comment_count, user_count, pct FROM ads_time_pattern_weekday ORDER BY weekday')
data['weekday'] = cur.fetchall()

# Stat tests
cur.execute('SELECT test_name, test_type, p_value, effect_size, conclusion FROM ads_stat_tests')
data['stat_tests'] = cur.fetchall()

# A/B test
cur.execute('SELECT test_name, metric_name, control_mean, treatment_mean, lift_ratio, p_value, effect_size, ci_lower, ci_upper, is_significant, conclusion FROM ads_ab_test_results LIMIT 1')
data['ab_test'] = cur.fetchone()

# Cohort retention
cur.execute('SELECT week_offset, ROUND(AVG(retention)*100, 2) avg_retention, COUNT(*) cohort_count FROM ads_cohort_retention GROUP BY week_offset ORDER BY week_offset LIMIT 9')
data['cohort'] = cur.fetchall()

# Topics
cur.execute('SELECT topic_id, topic_name, keywords FROM ads_comment_topic ORDER BY topic_id')
data['topics'] = cur.fetchall()

# Top artists
cur.execute('SELECT s.artist_name, COUNT(DISTINCT d.comment_id) comments, SUM(d.like_count) likes, COUNT(DISTINCT d.user_id) users FROM dwd_comment_detail d JOIN dwd_song_info s ON d.song_id = s.song_id GROUP BY s.artist_name ORDER BY likes DESC LIMIT 5')
data['top_artists'] = cur.fetchall()

# 30-day trend
cur.execute("SELECT DATE(comment_time) d, COUNT(*) c FROM dwd_comment_detail WHERE comment_time >= DATE_SUB((SELECT MAX(comment_time) FROM dwd_comment_detail), INTERVAL 30 DAY) GROUP BY d ORDER BY d")
data['trend_30d'] = cur.fetchall()

# Song sentiment
cur.execute('SELECT ROUND(AVG(positive)*100,1) pos_pct, ROUND(AVG(negative)*100,1) neg_pct, ROUND(AVG(neutral)*100,1) neu_pct, ROUND(AVG(satisfaction_score),2) sat_score FROM ads_song_sentiment')
data['song_sentiment_avg'] = cur.fetchone()

# User value distribution
cur.execute('SELECT CASE WHEN user_value >= 0.7 THEN "high" WHEN user_value >= 0.4 THEN "medium" ELSE "low" END as value_level, COUNT(*) cnt FROM ads_user_portrait GROUP BY value_level')
data['user_value_dist'] = cur.fetchall()

# Lifecycle stages
cur.execute('SELECT lifecycle_stage, COUNT(*) cnt FROM ads_song_rank GROUP BY lifecycle_stage')
data['lifecycle_stages'] = cur.fetchall()

conn.close()

with open('dashboard_data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, default=safe_json, indent=2)

print(f"Done! {len(data)} keys")
for k, v in data.items():
    if isinstance(v, list):
        print(f"  {k}: list[{len(v)}]")
    elif isinstance(v, dict):
        print(f"  {k}: dict {len(v)} keys")
    else:
        print(f"  {k}: {v}")
