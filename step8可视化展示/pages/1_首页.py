"""
Step8 可视化展示 - 首页总览

布局与 dashboard.html 首页保持一致：
- 4 个核心指标卡
- 近 30 天热度趋势 + 歌曲热度 Top5
- 用户画像分布 + 全局情感分布 + 爆款预测 Top10
- 用户活跃度热力图
"""
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db_helper import (
    cached_behavior_heatmap,
    cached_count,
    cached_home_trend,
    cached_hot_predict_top10,
    cached_sentiment_summary,
    cached_song_interaction_rate,
    cached_song_top5,
    cached_total_comments,
    cached_user_portrait_dist,
)
from style import BROWN, BRICK, CREAM, FOLK, SAGE, card, hit_progress, inject_theme, metric_card, nav_bar

inject_theme()
nav_bar(title="民谣风向标 · 数据洞察")

# ==================== 核心指标 ====================
m1, m2, m3, m4 = st.columns(4)
with m1:
    metric_card("总歌曲数", f"{cached_count('dwd_song_info'):,}")
with m2:
    metric_card("总评论数", f"{cached_total_comments():,}")
with m3:
    metric_card("总评论获赞", f"{cached_count('dwd_comment_detail'):,}")
with m4:
    metric_card("平均评论获赞率", f"{cached_song_interaction_rate():.2%}")

# 数据说明
st.markdown(
    "<div style='color:#8c7b6c;font-size:0.78rem;padding:4px 0 0 0;'>"
    "歌曲 / 歌手 / 评论数据来自网易云公开接口，分析口径基于真实评论行为（评论频次、情感、热词）。"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# ==================== 上排：趋势 + Top5 ====================
left, right = st.columns([2, 1])

with left:
    with card("📈 近 30 天歌曲热度趋势", "展示平台近 30 天整体热度、评论量与评论回复量的变化走势，帮助把握民谣内容的大盘节奏与波动趋势。"):
        start_dt = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        trend = cached_home_trend(start_dt)
        if trend.empty:
            st.info("近 30 天暂无热度趋势数据")
            fig = go.Figure()
        else:
            trend["dt"] = pd.to_datetime(trend["dt"]).dt.strftime("%m-%d")
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trend["dt"], y=trend["total_heat"], mode="lines", name="热度分",
                line=dict(color=BROWN, width=3),
                fill="tozeroy", fillcolor="rgba(139,107,77,0.12)"
            ))
            fig.add_trace(go.Scatter(
                x=trend["dt"], y=trend["total_comment"], mode="lines", name="评论数",
                line=dict(color=SAGE, width=2)
            ))
            fig.add_trace(go.Scatter(
                x=trend["dt"], y=trend["total_reply"], mode="lines", name="回复数",
                line=dict(color=BRICK, width=2)
            ))
        fig.update_layout(
            margin=dict(l=40, r=20, t=10, b=30),
            xaxis=dict(gridcolor="rgba(139,107,77,0.15)", linecolor="#d6c6b1", tickfont=dict(color="#6b5e52")),
            yaxis=dict(gridcolor="rgba(139,107,77,0.15)", linecolor="#d6c6b1", tickfont=dict(color="#6b5e52")),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM,
            hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            height=280,
        )
        st.plotly_chart(fig, use_container_width=True, height=280)

with right:
    with card("🔥 歌曲热度 Top5", "当前综合热度最高的 5 首民谣歌曲，反映近期最受用户关注与讨论的头部内容。"):
        top5 = cached_song_top5()
        if top5.empty:
            st.info("暂无歌曲热度数据")
            fig = go.Figure()
        else:
            top5["heat"] = top5["heat"].astype(float).round(2)
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=top5["heat"], y=top5["name"], orientation="h",
                marker=dict(color=[BRICK] * len(top5), line=dict(width=0),
                            coloraxis=None, colorscale=None),
                text=top5["heat"], textposition="outside", textfont=dict(color="#4a3f35", size=10)
            ))
            fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            margin=dict(l=10, r=40, t=5, b=5),
            xaxis=dict(gridcolor="rgba(139,107,77,0.15)", tickfont=dict(color="#6b5e52")),
            yaxis=dict(tickfont=dict(color="#4a3f35", size=11)),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, showlegend=False, height=280,
        )
        st.plotly_chart(fig, use_container_width=True, height=280)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# ==================== 中排：画像 + 情感 + 爆款 ====================
c1, c2, c3 = st.columns(3)

with c1:
    with card("👥 用户画像分布", "按互动深度将用户划分为核心粉丝、内容消费者和轻度用户，识别社区活跃度的主要贡献群体。"):
        portrait = cached_user_portrait_dist()
        if portrait.empty:
            st.info("暂无用户画像数据")
            fig = go.Figure()
        else:
            fig = go.Figure(go.Pie(
                labels=portrait["user_type"], values=portrait["cnt"], hole=0.4,
                marker=dict(colors=FOLK[: len(portrait)], line=dict(color="#f5efe6", width=2)),
                textinfo="label+percent", textfont=dict(color="#4a3f35", size=10)
            ))
        fig.update_layout(
            margin=dict(l=5, r=5, t=5, b=5), showlegend=False,
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, height=210,
        )
        st.plotly_chart(fig, use_container_width=True, height=210)

with c2:
    with card("😊 全局情感分布", "全部评论的情感倾向占比，正面/中性/负面分布反映用户对平台内容的总体情绪基调。"):
        sent = cached_sentiment_summary()
        if sent.empty:
            st.info("暂无情感汇总数据")
            fig = go.Figure()
        else:
            values = [float(sent["positive_ratio"].iloc[0]), float(sent["neutral_ratio"].iloc[0]), float(sent["negative_ratio"].iloc[0])]
            fig = go.Figure(go.Pie(
                labels=["正面", "中性", "负面"], values=values, hole=0.45,
                marker=dict(colors=[SAGE, "#8c7b6c", BRICK], line=dict(color="#f5efe6", width=2)),
                textinfo="label+percent", textfont=dict(color="#4a3f35", size=10)
            ))
        fig.update_layout(
            margin=dict(l=5, r=5, t=5, b=5), showlegend=False,
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, height=210,
        )
        st.plotly_chart(fig, use_container_width=True, height=210)

with c3:
    with card("🚀 爆款预测 Top10", "基于热度与互动特征，模型预测未来最可能成为爆款的 10 首歌曲，为运营与推荐提供参考。"):
        hot = cached_hot_predict_top10()
        if hot.empty:
            st.info("暂无爆款预测数据")
        else:
            hot["hot_prob"] = hot["hot_prob"].astype(float)
            max_prob = max(float(hot["hot_prob"].max()), 0.01)
            html = ""
            for _, row in hot.iterrows():
                name = row["song_name"]
                prob = float(row["hot_prob"])
                html += hit_progress(name, prob / max_prob * 100, f"{prob:.2%}")
            st.markdown(html, unsafe_allow_html=True)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# ==================== 下排：热力图 ====================
with card("🔥 用户活跃度热力图（星期 × 小时）", "展示用户在一周不同日期、一天不同时段的活跃密度，颜色越深表示该时段互动行为越密集，可用于选择最佳内容发布与运营时间。"):
    heat = cached_behavior_heatmap(start_dt)
    if heat.empty:
        st.info("近 30 天暂无用户行为数据")
        fig = go.Figure()
    else:
        heat["behavior_time"] = pd.to_datetime(heat["behavior_time"])
        heat["hour"] = heat["behavior_time"].dt.hour
        heat["dow"] = heat["behavior_time"].dt.day_name()
        pivot = heat.groupby(["dow", "hour"]).size().reset_index(name="cnt")
        all_hours = list(range(24))
        all_dows = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        dow_labels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        full_idx = pd.MultiIndex.from_product([all_dows, all_hours], names=["dow", "hour"])
        pivot = pivot.set_index(["dow", "hour"]).reindex(full_idx, fill_value=0).reset_index()
        pivot.columns = ["dow", "hour", "cnt"]
        pivot["dow"] = pd.Categorical(pivot["dow"], categories=all_dows, ordered=True)
        mat = pivot.pivot(index="dow", columns="hour", values="cnt").values
        fig = go.Figure(data=go.Heatmap(
            z=mat, x=[f"{h}:00" for h in all_hours], y=dow_labels,
            colorscale=[[0, "#faf6f0"], [0.25, "#f0e6d6"], [0.5, "#e0cfba"], [0.75, "#c9a87c"], [1, "#8b6b4d"]],
            showscale=False, hovertemplate="%{y} %{x}<br>活跃度: %{z}<extra></extra>"
        ))
    fig.update_layout(
        margin=dict(l=10, r=10, t=5, b=30),
        xaxis=dict(tickfont=dict(size=10, color="#6b5e52"), nticks=12),
        yaxis=dict(tickfont=dict(size=11, color="#4a3f35")),
        plot_bgcolor=CREAM, paper_bgcolor=CREAM, height=190,
    )
    st.plotly_chart(fig, use_container_width=True, height=190)
