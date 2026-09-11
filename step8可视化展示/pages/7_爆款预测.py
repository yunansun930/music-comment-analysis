"""
Step8 可视化展示 - 爆款预测

布局与 dashboard.html 爆款预测页保持一致：
- 模型对比评估 + 特征重要性 Top15
- 预测爆款概率 Top20
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from db_helper import cached_feature_importance_top15, cached_hot_predict_top20, cached_model_metrics
from style import BROWN, BRICK, CREAM, SAGE, card, inject_theme

inject_theme()
st.markdown('<div class="dashboard-nav-title" style="padding:0 0 8px 0;">🚀 爆款预测</div>', unsafe_allow_html=True)

# 上排：模型 + 特征
c1, c2 = st.columns(2)
with c1:
    with card("📊 模型对比评估", "对比 XGBoost、逻辑回归等模型在 AUC、F1、Accuracy 上的表现，评估预测方案的可信度。"):
        metrics = cached_model_metrics()
        if metrics.empty:
            st.info("暂无模型指标数据")
            fig = go.Figure()
        else:
            label_map = {"XGBoost": "XGBoost", "LogisticRegression": "逻辑回归"}
            metrics["model_label"] = metrics["model_name"].map(label_map).fillna(metrics["model_name"])
            fig = go.Figure()
            fig.add_trace(go.Bar(x=metrics["model_label"], y=metrics["auc"], name="AUC", marker=dict(color=BROWN)))
            fig.add_trace(go.Bar(x=metrics["model_label"], y=metrics["f1"], name="F1", marker=dict(color=BRICK)))
            fig.add_trace(go.Bar(x=metrics["model_label"], y=metrics["accuracy"], name="Accuracy", marker=dict(color=SAGE)))
        fig.update_layout(
            margin=dict(l=40, r=20, t=10, b=30),
            xaxis=dict(tickfont=dict(color="#4a3f35")),
            yaxis=dict(gridcolor="rgba(139,107,77,0.15)", tickfont=dict(color="#6b5e52"), range=[0, 1]),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            barmode="group", height=250,
        )
        st.plotly_chart(fig, use_container_width=True, height=250)

with c2:
    with card("⚙️ 特征重要性 Top15", "模型判断歌曲是否会爆最重要的 15 个特征，帮助理解哪些因素对热度预测影响最大。"):
        feats = cached_feature_importance_top15()
        if feats.empty:
            st.info("暂无特征重要性数据")
            fig = go.Figure()
        else:
            label_map = {
                # 评论衍生特征（基于公开评论数据）
                "total_comment_count": "歌曲累计评论数",
                "total_reply_count": "歌曲累计回复数",
                "total_like_total": "歌曲累计获赞数",
                "artist_comment_count": "歌手累计评论数",
                "artist_reply_count": "歌手累计回复数",
                "artist_like_total": "歌手累计获赞数",
                "like_per_comment": "评论获赞率",
                "reply_per_comment": "评论回复率",
                "valid_comment_count": "有效评论数",
                "topic_count": "评论主题数",
                "positive_ratio": "正面情感占比",
                "negative_ratio": "负面情感占比",
                # 热度与发布时间特征
                "avg_heat_score": "平均热度分",
                "max_heat_score": "最高热度分",
                "release_year": "发行年份",
                "release_month": "发行月份",
                "days_since_release": "发行距今天数",
            }
            feats["feature_label"] = feats["feature"].map(label_map).fillna(feats["feature"])
            feats = feats.sort_values("importance")
            fig = go.Figure(go.Bar(
                x=feats["importance"], y=feats["feature_label"], orientation="h",
                marker=dict(color=BROWN), text=feats["importance"].round(3), textposition="outside", textfont=dict(color="#4a3f35", size=9)
            ))
        fig.update_layout(
            margin=dict(l=10, r=50, t=5, b=10),
            xaxis=dict(gridcolor="rgba(139,107,77,0.15)", tickfont=dict(color="#6b5e52")),
            yaxis=dict(tickfont=dict(color="#4a3f35", size=10)),
            plot_bgcolor=CREAM, paper_bgcolor=CREAM, showlegend=False, height=250,
        )
        st.plotly_chart(fig, use_container_width=True, height=250)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

# 下排：预测表
with card("🚀 预测爆款概率 Top20", "综合模型给出的每首歌成为爆款的概率，并标注是否达到“预测爆款”阈值。"):
    hot = cached_hot_predict_top20()
    if hot.empty:
        st.info("暂无爆款预测数据")
    else:
        hot["hot_prob"] = hot["hot_prob"].astype(float)
        hot["is_hot_predicted"] = hot["is_hot_predicted"].apply(lambda x: "✓ 爆款" if int(x) else "-")
        hot = hot.rename(columns={
            "song_name": "歌曲名", "artist_name": "歌手", "hot_prob": "爆款概率", "is_hot_predicted": "是否预测爆款"
        })
        st.dataframe(hot, use_container_width=True, height=260, hide_index=True)
