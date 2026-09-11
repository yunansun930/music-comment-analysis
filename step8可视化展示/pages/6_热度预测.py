"""
Step8 可视化展示 - 热度预测

布局与 dashboard.html 热度预测页保持一致：
- 歌曲选择器
- 预测热度趋势（含置信区间）
- 可预测歌曲列表
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db_helper import cached_forecast_songs, cached_song_forecast, read_sql
from style import BROWN, CREAM, card, inject_theme

inject_theme()
st.markdown('<div class="dashboard-nav-title" style="padding:0 0 8px 0;">🔮 热度预测</div>', unsafe_allow_html=True)

songs = cached_forecast_songs()
if songs.empty:
    st.warning("暂无歌曲预测数据，请先运行 step7 时间序列预测")
    st.stop()

# 搜索 + 选择
search_col, select_col, count_col = st.columns([1, 2, 1])
with search_col:
    kw = st.text_input("输入歌名快速筛选", "", key="forecast_search")
with select_col:
    mask = songs.apply(lambda r: kw.lower() in str(r["song_name"]).lower(), axis=1)
    filtered = songs[mask].reset_index(drop=True)
    if filtered.empty:
        st.warning("无匹配歌曲")
        st.stop()
    options = filtered.apply(lambda r: f"{r['song_name']} - {r['artist_name']}", axis=1).tolist()
    selected = st.selectbox("选择歌曲查看预测趋势", options, key="forecast_select")
    song_id = int(filtered.iloc[options.index(selected)]["song_id"])
    song_name = filtered.iloc[options.index(selected)]["song_name"]
with count_col:
    st.markdown(f"<div style='padding-top:28px;color:#8c7b6c;font-size:0.85rem;'>共 <b>{len(filtered)}</b> 首歌曲可预测</div>", unsafe_allow_html=True)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# 预测趋势
with card(f"📈 {song_name} - 预测热度趋势（含置信区间）", "基于时间序列模型预测所选歌曲未来 30 天的热度走势，阴影区域表示置信区间，反映预测的不确定性。"):
    forecast = cached_song_forecast(song_id)
    if forecast.empty:
        st.info("该歌曲暂无预测数据")
        fig = go.Figure()
    else:
        forecast["forecast_date"] = pd.to_datetime(forecast["forecast_date"]).dt.strftime("%m-%d")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=forecast["forecast_date"], y=forecast["heat_score_upper"],
            mode="lines", line=dict(color="rgba(139,107,77,0)", width=0), showlegend=False,
            hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=forecast["forecast_date"], y=forecast["heat_score_lower"],
            mode="lines", line=dict(color="rgba(139,107,77,0)", width=0), fill="tonexty",
            fillcolor="rgba(139,107,77,0.18)", name="置信区间", hoverinfo="skip"
        ))
        fig.add_trace(go.Scatter(
            x=forecast["forecast_date"], y=forecast["heat_score"],
            mode="lines", name="预测热度", line=dict(color=BROWN, width=3)
        ))
    fig.update_layout(
        margin=dict(l=40, r=20, t=10, b=30),
        xaxis=dict(tickfont=dict(color="#6b5e52"), gridcolor="rgba(139,107,77,0.15)"),
        yaxis=dict(title="热度分", tickfont=dict(color="#6b5e52"), gridcolor="rgba(139,107,77,0.15)"),
        plot_bgcolor=CREAM, paper_bgcolor=CREAM,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=280,
    )
    st.plotly_chart(fig, use_container_width=True, height=280)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# 可预测歌曲列表
with card("📋 可预测歌曲列表", "所有具备足够历史数据、可生成未来 30 天热度预测的歌曲清单。"):
    list_df = read_sql(
        """
        SELECT s.song_name,
               COUNT(*) AS days,
               MIN(f.forecast_date) AS start_date,
               MAX(f.forecast_date) AS end_date
        FROM ads_song_forecast f
        JOIN dwd_song_info s ON f.song_id = s.song_id
        GROUP BY s.song_id, s.song_name
        ORDER BY s.song_name
        """
    )
    if list_df.empty:
        st.info("暂无预测列表数据")
    else:
        list_df = list_df.rename(columns={
            "song_name": "歌曲名", "days": "预测天数", "start_date": "预测起始", "end_date": "预测结束"
        })
        st.dataframe(list_df, use_container_width=True, height=260, hide_index=True)
