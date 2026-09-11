"""
Step8 可视化展示 - 歌曲分析

布局与 dashboard.html 歌曲分析页保持一致：
- 歌曲选择器
- 生命周期曲线
- 评论热词 + 情感分布
- 高赞评论滚动
- 歌曲评论数 Top20
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db_helper import (
    cached_comment_count,
    cached_song_comment_top20,
    cached_song_daily,
    cached_song_detail_list,
    cached_song_keywords,
    cached_song_sentiment,
    cached_song_top_comments,
)
from style import BROWN, BRICK, CREAM, SAGE, card, inject_theme, render_comments

inject_theme()
st.markdown('<div class="dashboard-nav-title" style="padding:0 0 8px 0;">🎵 歌曲分析</div>', unsafe_allow_html=True)

# 歌曲列表
songs = cached_song_detail_list()
if songs.empty:
    st.warning("歌曲数据为空，请先运行 step1/step2 数据采集与入库")
    st.stop()

# 搜索 + 选择
search_col, select_col, count_col = st.columns([1, 2, 1])
with search_col:
    kw = st.text_input("输入歌名/歌手快速筛选", "", key="song_search")
with select_col:
    mask = songs.apply(lambda r: kw.lower() in f"{r['song_name']} {r['artist_name']}".lower(), axis=1)
    filtered = songs[mask].reset_index(drop=True)
    if filtered.empty:
        st.warning("无匹配歌曲，请调整筛选条件")
        st.stop()
    options = filtered.apply(lambda r: f"{r['song_name']} - {r['artist_name']} ({r['comment_count']}评论)", axis=1).tolist()
    selected = st.selectbox("选择歌曲", options, key="song_analysis_select")
    song_id = int(filtered.iloc[options.index(selected)]["song_id"])
with count_col:
    st.markdown(f"<div style='padding-top:28px;color:#8c7b6c;font-size:0.85rem;'>共 <b>{len(filtered)}</b> 首歌曲可供选择</div>", unsafe_allow_html=True)

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

has_comments = cached_comment_count(song_id) > 0

# 生命周期曲线
with card("📈 歌曲生命周期曲线", "展示所选歌曲随时间变化的热度分与评论量，帮助判断歌曲处于上升期、稳定期还是衰退期。"):
    daily = cached_song_daily(song_id)
    if daily.empty:
        st.info("该歌曲暂无日度热度数据")
        fig = go.Figure()
    else:
        daily["dt"] = pd.to_datetime(daily["dt"]).dt.strftime("%m-%d")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily["dt"], y=daily["heat_score"], mode="lines", name="热度分", line=dict(color=BROWN, width=3)))
        fig.add_trace(go.Scatter(x=daily["dt"], y=daily["comment_count"], mode="lines", name="评论数", line=dict(color=SAGE, width=2)))
    fig.update_layout(
        margin=dict(l=40, r=20, t=10, b=30),
        xaxis=dict(gridcolor="rgba(139,107,77,0.15)", linecolor="#d6c6b1", tickfont=dict(color="#6b5e52")),
        yaxis=dict(gridcolor="rgba(139,107,77,0.15)", linecolor="#d6c6b1", tickfont=dict(color="#6b5e52")),
        plot_bgcolor=CREAM, paper_bgcolor=CREAM,
        hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=230,
    )
    st.plotly_chart(fig, use_container_width=True, height=230)

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

# 热词 + 情感
col1, col2 = st.columns(2)
with col1:
    with card("🏷️ 评论热词", "提取该歌曲评论中出现频率最高的关键词，反映听众讨论这首歌时最关心的内容和表达。"):
        keywords = cached_song_keywords(song_id)
        if not has_comments:
            st.info("该歌曲暂无评论数据")
            fig = go.Figure()
        elif keywords.empty:
            st.info("暂无关键词数据")
            fig = go.Figure()
        else:
            fig = go.Figure(go.Bar(
                x=keywords["score"], y=keywords["word"], orientation="h",
                marker=dict(color=BROWN), text=keywords["score"], textposition="outside", textfont=dict(color="#4a3f35", size=10)
            ))
            fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            margin=dict(l=10, r=40, t=5, b=10),
            xaxis=dict(gridcolor="rgba(139,107,77,0.15)", tickfont=dict(color="#6b5e52")),
            yaxis=dict(tickfont=dict(color="#4a3f35", size=11)),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, showlegend=False, height=190,
        )
        st.plotly_chart(fig, use_container_width=True, height=190)

with col2:
    with card("😊 情感分布", "该歌曲评论中正面、中性、负面情感的占比，直观呈现听众对这首歌的总体情绪反馈。"):
        sentiment = cached_song_sentiment(song_id)
        if not has_comments:
            st.info("该歌曲暂无评论数据")
            fig = go.Figure()
        elif sentiment.empty:
            st.info("暂无情感数据")
            fig = go.Figure()
        else:
            values = [float(sentiment["positive"].iloc[0]), float(sentiment["neutral"].iloc[0]), float(sentiment["negative"].iloc[0])]
            fig = go.Figure(go.Pie(
                labels=["正面", "中性", "负面"], values=values, hole=0.45,
                marker=dict(colors=[SAGE, "#8c7b6c", BRICK], line=dict(color="#f5efe6", width=2)),
                textinfo="label+percent", textfont=dict(color="#4a3f35", size=11)
            ))
        fig.update_layout(
            margin=dict(l=5, r=5, t=5, b=5), showlegend=False,
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, height=190,
        )
        st.plotly_chart(fig, use_container_width=True, height=190)

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

# 高赞评论滚动
with card("💬 高赞评论滚动（Top10）", "按点赞数排序的 Top10 热门评论，滚动展示听众最有共鸣、最具代表性的声音。"):
    if not has_comments:
        st.info("该歌曲暂无评论数据")
    else:
        comments = cached_song_top_comments(song_id, limit=10)
        if comments.empty:
            st.info("暂无高赞评论数据")
        else:
            items = comments.to_dict("records")
            st.markdown(render_comments(items), unsafe_allow_html=True)

st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)

# 歌曲评论数 Top20
with card("📋 歌曲评论数 Top20", "评论数量最多的 20 首歌曲排行，评论量通常意味着更高的用户参与度和话题性。"):
    top20 = cached_song_comment_top20()
    if top20.empty:
        st.info("暂无歌曲评论排行数据")
    else:
        top20 = top20.rename(columns={"song_name": "歌曲名", "artist_name": "歌手", "comment_count": "评论数"})
        st.dataframe(top20, use_container_width=True, height=190, hide_index=True)
