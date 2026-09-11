"""
Step7 模型预测 - 时间序列热度预测（Prophet）
"""
import os
import pandas as pd
import numpy as np
import joblib
from prophet import Prophet
from config import HOT_SONG_CONFIG
from db_helper import read_sql, write_table


def build_forecast():
    """为每首歌预测未来 30 天热度趋势。"""
    df = read_sql("""
        SELECT song_id, dt, heat_score
        FROM dws_song_daily
        ORDER BY song_id, dt
    """)

    if df.empty:
        print("  [Warn] dws_song_daily 为空，跳过时间序列预测")
        return pd.DataFrame()

    # 只保留 heat_score 非空且非负的记录
    df = df.dropna(subset=["heat_score"])
    df["dt"] = pd.to_datetime(df["dt"])

    forecast_days = HOT_SONG_CONFIG["forecast_days"]
    results = []
    forecasters = {}

    song_ids = df["song_id"].unique()
    total = len(song_ids)
    print(f"  [Prophet] 开始对 {total} 首歌曲进行热度预测...")

    for idx, song_id in enumerate(song_ids, 1):
        sub = df[df["song_id"] == song_id][["dt", "heat_score"]].copy()
        sub.columns = ["ds", "y"]
        # Prophet 要求 y >= 0
        sub["y"] = sub["y"].clip(lower=0)

        # 数据太少则跳过
        if len(sub) < 14:
            continue

        try:
            model = Prophet(
                yearly_seasonality=False,
                weekly_seasonality=True,
                daily_seasonality=False,
                interval_width=0.8,
                changepoint_prior_scale=0.05,
            )
            model.fit(sub)

            future = model.make_future_dataframe(periods=forecast_days)
            forecast = model.predict(future)

            # 只取未来 30 天
            future_forecast = forecast[forecast["ds"] > sub["ds"].max()].copy()
            future_forecast["song_id"] = song_id
            future_forecast = future_forecast[["song_id", "ds", "yhat", "yhat_lower", "yhat_upper"]]
            future_forecast.columns = ["song_id", "forecast_date", "heat_score", "heat_score_lower", "heat_score_upper"]
            results.append(future_forecast)

            # 只保存部分模型示例
            if idx <= 10:
                forecasters[str(song_id)] = model
        except Exception as e:
            print(f"  [Warn] song_id={song_id} Prophet 预测失败: {e}")
            continue

        if idx % 50 == 0:
            print(f"     已处理 {idx}/{total} 首歌曲...")

    if results:
        result_df = pd.concat(results, ignore_index=True)
        result_df["update_time"] = pd.Timestamp.now()
        # Prophet 可能输出负数，做截断
        result_df["heat_score"] = result_df["heat_score"].clip(lower=0)
        result_df["heat_score_lower"] = result_df["heat_score_lower"].clip(lower=0)
        result_df["heat_score_upper"] = result_df["heat_score_upper"].clip(lower=0)

        write_table(result_df, "ads_song_forecast", if_exists="replace")
        print(f"  [OK] ads_song_forecast 已写入 {len(result_df)} 条预测结果")

        # 保存示例模型
        os.makedirs("models", exist_ok=True)
        joblib.dump(forecasters, "models/prophet_forecasters_sample.pkl")
        return result_df
    else:
        print("  [Warn] 没有生成任何预测结果")
        return pd.DataFrame()
