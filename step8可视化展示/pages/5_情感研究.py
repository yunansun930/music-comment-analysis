"""
Step8 可视化展示 - 情感研究

布局与 dashboard.html 情感研究页保持一致：
- 4 个核心指标卡
- 平台情感加速度趋势（近 30 周）
- 情感升温最快 Top10 + 情感降温最快 Top10
- 情感得分 - 情感加速度矩阵
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db_helper import (
    cached_sentiment_falling,
    cached_sentiment_rising,
    cached_sentiment_scatter,
    cached_sentiment_summary,
    cached_sentiment_weekly,
)
from style import BROWN, BRICK, CREAM, SAGE, card, inject_theme, metric_card

inject_theme()
st.markdown('<div class="dashboard-nav-title" style="padding:0 0 8px 0;">❤️ 情感研究</div>', unsafe_allow_html=True)

sent = cached_sentiment_summary()
weekly = cached_sentiment_weekly()

# 顶部指标
m1, m2, m3, m4 = st.columns(4)
total_comments = int(sent["total_comments"].iloc[0]) if not sent.empty else 0
pos_ratio = float(sent["positive_ratio"].iloc[0]) if not sent.empty else 0
neg_ratio = float(sent["negative_ratio"].iloc[0]) if not sent.empty else 0
avg_prob = float(sent["positive_ratio"].iloc[0]) if not sent.empty else 0
if not weekly.empty:
    total_comments = int(weekly["count"].sum())
    pos_ratio = weekly["positive_ratio"].mean()
    neg_ratio = weekly["negative_ratio"].mean()
    avg_prob = weekly["avg_positive_prob"].mean()

with m1:
    metric_card("评论总数", f"{total_comments:,}")
with m2:
    metric_card("正面评论占比", f"{pos_ratio:.1%}")
with m3:
    metric_card("负面评论占比", f"{neg_ratio:.1%}")
with m4:
    metric_card("平均正面概率", f"{avg_prob:.1%}")

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# 情感周趋势
with card("📈 平台情感加速度趋势（近 30 周）", "观察平台整体正面情感占比及其变化速度、加速度，判断用户好评情绪是在加速升温还是减速回落。"):
    if weekly.empty:
        st.info("暂无情感时间序列数据")
        fig = go.Figure()
    else:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=weekly["week"], y=weekly["positive_ratio"] * 100, mode="lines", name="正面情感占比",
            line=dict(color=SAGE, width=3), fill="tozeroy", fillcolor="rgba(90,125,107,0.12)", yaxis="y1"
        ))
        fig.add_trace(go.Scatter(
            x=weekly["week"], y=weekly["velocity"] * 100, mode="lines", name="情感速度",
            line=dict(color=BROWN, width=2, dash="dash"), yaxis="y2"
        ))
        fig.add_trace(go.Bar(
            x=weekly["week"], y=weekly["acceleration"] * 100, name="情感加速度",
            marker=dict(color=[SAGE if v >= 0 else BRICK for v in weekly["acceleration"]]), yaxis="y2"
        ))
    fig.update_layout(
        margin=dict(l=50, r=50, t=10, b=30),
        xaxis=dict(tickfont=dict(color="#6b5e52")),
        yaxis=dict(title="占比", titlefont=dict(color=SAGE), tickfont=dict(color="#6b5e52"), gridcolor="rgba(139,107,77,0.15)"),
        yaxis2=dict(title="变化", titlefont=dict(color=BROWN), tickfont=dict(color="#6b5e52"), overlaying="y", side="right"),
        plot_bgcolor=CREAM, paper_bgcolor=CREAM,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        height=260,
    )
    st.plotly_chart(fig, use_container_width=True, height=260)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# 升温 + 降温
c1, c2 = st.columns(2)
with c1:
    with card("🚀 情感升温最快歌曲 Top10", "近期正面情感占比相比早期明显上升的歌曲，可能是口碑正在发酵、值得关注的潜力作品。"):
        rising = cached_sentiment_rising()
        if rising.empty:
            st.info("暂无升温数据")
            fig = go.Figure()
        else:
            rising = rising.sort_values("change_rate")
            fig = go.Figure(go.Bar(
                x=rising["change_rate"], y=rising["song_name"], orientation="h",
                marker=dict(color=SAGE), text=rising["change_rate"].round(1), textposition="outside", textfont=dict(color="#4a3f35", size=10),
                hovertemplate="%{y}<br>变化率: %{x:.1f}%<extra></extra>"
            ))
        fig.update_layout(
            margin=dict(l=10, r=50, t=5, b=10),
            xaxis=dict(tickfont=dict(color="#6b5e52"), title="变化率 %"),
            yaxis=dict(tickfont=dict(color="#4a3f35", size=10)),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, showlegend=False, height=250,
        )
        st.plotly_chart(fig, use_container_width=True, height=250)

with c2:
    with card("🧊 情感降温最快歌曲 Top10", "近期正面情感占比相比早期明显下降的歌曲，提示可能需要关注用户反馈变化或内容生命周期衰退。"):
        falling = cached_sentiment_falling()
        if falling.empty:
            st.info("暂无降温数据")
            fig = go.Figure()
        else:
            falling = falling.sort_values("change_rate", ascending=False)
            fig = go.Figure(go.Bar(
                x=falling["change_rate"], y=falling["song_name"], orientation="h",
                marker=dict(color=BRICK), text=falling["change_rate"].round(1), textposition="outside", textfont=dict(color="#4a3f35", size=10),
                hovertemplate="%{y}<br>变化率: %{x:.1f}%<extra></extra>"
            ))
        fig.update_layout(
            margin=dict(l=10, r=50, t=5, b=10),
            xaxis=dict(tickfont=dict(color="#6b5e52"), title="变化率 %"),
            yaxis=dict(tickfont=dict(color="#4a3f35", size=10)),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, showlegend=False, height=250,
        )
        st.plotly_chart(fig, use_container_width=True, height=250)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# 散点矩阵
with card("💨 情感得分 - 情感加速度矩阵", "横轴为近期正面情感占比，纵轴为情感变化率。右上方代表“口碑好且快速升温”的高潜力歌曲。"):
    scatter = cached_sentiment_scatter()
    if scatter.empty:
        st.info("暂无散点数据")
        fig = go.Figure()
    else:
        scatter = scatter.dropna(subset=["recent_positive_ratio", "change_rate"])
        sizes = np.clip(8 + scatter["comment_count"] / 8, 8, 28)
        colors = scatter["change_rate"].apply(lambda v: SAGE if v >= 20 else (BROWN if v >= 0 else ("#d4a373" if v >= -20 else BRICK)))
        fig = go.Figure(go.Scatter(
            x=scatter["recent_positive_ratio"] * 100, y=scatter["change_rate"], mode="markers",
            marker=dict(size=sizes, color=colors, opacity=0.85),
            text=scatter["song_name"],
            hovertemplate="%{text}<br>近期正面占比: %{x:.1f}%<br>变化率: %{y:.1f}%<extra></extra>"
        ))
    fig.update_layout(
        margin=dict(l=50, r=20, t=10, b=40),
        xaxis=dict(title="近期正面情感占比", tickfont=dict(color="#6b5e52"), gridcolor="rgba(139,107,77,0.15)"),
        yaxis=dict(title="变化率", tickfont=dict(color="#6b5e52"), gridcolor="rgba(139,107,77,0.15)"),
        plot_bgcolor=CREAM, paper_bgcolor=CREAM, height=260,
    )
    st.plotly_chart(fig, use_container_width=True, height=260)
