"""
音乐评论用户行为分析 - 数据大屏（民谣主题）

页面结构（与 dashboard.html 一致）：
- 首页总览
- 歌曲分析
- 用户画像
- 文本洞察
- 情感研究
- 爆款预测
- 热度预测
"""
import streamlit as st

from style import inject_theme

st.set_page_config(
    page_title="音乐评论用户行为分析 - 数据大屏",
    page_icon="🎶",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_theme()

pages = [
    st.Page("pages/1_首页.py", title="首页总览", icon="📊", default=True),
    st.Page("pages/2_歌曲分析.py", title="歌曲分析", icon="🎵"),
    st.Page("pages/3_用户画像.py", title="用户画像", icon="👥"),
    st.Page("pages/4_文本洞察.py", title="文本洞察", icon="💬"),
    st.Page("pages/5_情感研究.py", title="情感研究", icon="❤️"),
    st.Page("pages/7_爆款预测.py", title="爆款预测", icon="🚀"),
    st.Page("pages/6_热度预测.py", title="热度预测", icon="🔮"),
]

pg = st.navigation(pages, position="sidebar")
pg.run()
