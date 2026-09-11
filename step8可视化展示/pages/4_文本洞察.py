"""
Step8 可视化展示 - 文本洞察

布局与 dashboard.html 文本洞察页保持一致：
- 全局热门关键词 + LDA 主题关键词
- 主题分布 + 歌曲情感 Top15（按满意度）
"""
import plotly.graph_objects as go
import streamlit as st

from db_helper import cached_comment_topics, cached_global_keywords, cached_song_sentiments_top15, cached_topic_dist
from style import BROWN, BRICK, CREAM, FOLK, SAGE, card, inject_theme, topic_list_html

inject_theme()
st.markdown('<div class="dashboard-nav-title" style="padding:0 0 8px 0;">💬 文本洞察</div>', unsafe_allow_html=True)

# 上排：关键词 + 主题列表
c1, c2 = st.columns([2, 1])
with c1:
    with card("🔑 全局热门关键词 Top20", "全平台评论中出现最多的 20 个关键词，反映民谣听众共同关注的话题和表达主题。"):
        keywords = cached_global_keywords()
        if keywords.empty:
            st.info("暂无全局关键词数据")
            fig = go.Figure()
        else:
            keywords = keywords.sort_values("score")
            fig = go.Figure(go.Bar(
                x=keywords["score"], y=keywords["word"], orientation="h",
                marker=dict(color=BROWN), text=keywords["score"], textposition="outside", textfont=dict(color="#4a3f35", size=10)
            ))
        fig.update_layout(
            margin=dict(l=10, r=50, t=5, b=10),
            xaxis=dict(gridcolor="rgba(139,107,77,0.15)", tickfont=dict(color="#6b5e52")),
            yaxis=dict(tickfont=dict(color="#4a3f35", size=11)),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, showlegend=False, height=260,
        )
        st.plotly_chart(fig, use_container_width=True, height=260)

with c2:
    with card("📚 LDA 主题关键词", "通过主题模型聚类出的评论主题及对应关键词，揭示听众讨论的隐性话题结构。"):
        topics = cached_comment_topics()
        if topics.empty:
            st.info("暂无主题数据")
        else:
            st.markdown(topic_list_html(topics.to_dict("records")), unsafe_allow_html=True)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# 下排：主题分布 + 歌曲情感
c3, c4 = st.columns(2)
with c3:
    with card("📊 主题分布", "各主题评论数量的占比分布，直观展示民谣听众讨论焦点的集中与分散程度。"):
        td = cached_topic_dist()
        if td.empty:
            st.info("暂无主题分布数据")
            fig = go.Figure()
        else:
            fig = go.Figure(go.Pie(
                labels=td["topic_name"], values=td["cnt"], hole=0.4,
                marker=dict(colors=FOLK[: len(td)], line=dict(color="#f5efe6", width=2)),
                textinfo="label+percent", textfont=dict(color="#4a3f35", size=11)
            ))
        fig.update_layout(
            margin=dict(l=5, r=5, t=5, b=5), showlegend=False,
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, height=260,
        )
        st.plotly_chart(fig, use_container_width=True, height=260)

with c4:
    with card("😊 歌曲情感 Top15（按满意度）", "满意度最高的 15 首歌曲及其情感构成，帮助发现口碑最好、用户评价最积极的民谣作品。"):
        ss = cached_song_sentiments_top15()
        if ss.empty:
            st.info("暂无歌曲情感数据")
            fig = go.Figure()
        else:
            ss = ss.sort_values("satisfaction_score")
            fig = go.Figure()
            fig.add_trace(go.Bar(y=ss["song_name"], x=ss["positive"], orientation="h", name="正面", marker=dict(color=SAGE)))
            fig.add_trace(go.Bar(y=ss["song_name"], x=ss["neutral"], orientation="h", name="中性", marker=dict(color="#8c7b6c")))
            fig.add_trace(go.Bar(y=ss["song_name"], x=ss["negative"], orientation="h", name="负面", marker=dict(color=BRICK)))
            fig.update_layout(barmode="stack")
        fig.update_layout(
            margin=dict(l=10, r=10, t=5, b=10),
            xaxis=dict(gridcolor="rgba(139,107,77,0.15)", tickfont=dict(color="#6b5e52")),
            yaxis=dict(tickfont=dict(color="#4a3f35", size=10)),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            height=260,
        )
        st.plotly_chart(fig, use_container_width=True, height=260)
