"""
Step8 可视化展示 - 全局样式模块（民谣暖色主题）

配色参考 dashboard.html：
- 背景 #f5efe6，主色 #8b6b4d，砖红 #c0392b，鼠尾草绿 #5a7d6b，奶油色 #faf6f0
"""

from contextlib import contextmanager
from datetime import datetime

import streamlit as st

# 民谣主题色板
PAPER = "#f5efe6"
PAPER_2 = "#ede4d6"
CREAM = "#faf6f0"
INK = "#4a3f35"
INK_LIGHT = "#6b5e52"
MUTED = "#8c7b6c"
RULE = "#d6c6b1"
BROWN = "#8b6b4d"
BROWN_DARK = "#6d5137"
BRICK = "#c0392b"
SAGE = "#5a7d6b"
SAGE_LIGHT = "#7a9d8b"
WARM = "#d4a373"
FOLK = ["#8b6b4d", "#c0392b", "#5a7d6b", "#d4a373", "#a98467", "#7a9d8b", "#b07d62", "#d98880"]

THEME_CSS = f"""
<style>
/* 全局背景与字体 */
.stApp {{
    background: {PAPER};
    font-family: 'PingFang SC', 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, sans-serif;
    color: {INK};
}}

/* 轻微纸张纹理 */
.stApp::before {{
    content: "";
    position: fixed; top: 0; left: 0; right: 0; bottom: 0;
    pointer-events: none;
    opacity: 0.35;
    z-index: 0;
    background-image:
      radial-gradient(circle at 20% 30%, rgba(139,107,77,0.04) 0%, transparent 40%),
      radial-gradient(circle at 80% 70%, rgba(192,57,43,0.03) 0%, transparent 40%);
}}

/* 隐藏 Streamlit 默认头部与底部 */
#MainMenu {{visibility: hidden;}}
footer {{visibility: hidden;}}
header {{visibility: hidden;}}

/* 主容器紧凑布局 */
[data-testid="stAppViewContainer"] > .main {{
    overflow-y: hidden !important;
}}
[data-testid="stAppViewContainer"] > .main > div:first-child {{
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
}}
.block-container {{
    padding-top: 0.5rem !important;
    padding-bottom: 0.5rem !important;
    max-width: 100% !important;
}}

/* 标题、子标题紧凑 */
h1, h2, h3 {{
    margin-top: 0.2rem !important;
    margin-bottom: 0.3rem !important;
    color: {BROWN_DARK} !important;
    font-family: 'STKaiti', 'KaiTi', 'SimKaiti', 'PingFang SC', serif;
}}
.stMarkdown p {{
    margin-bottom: 0.25rem !important;
    color: {INK};
}}

/* 顶部导航栏 */
.dashboard-nav {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: {CREAM};
    border-radius: 10px;
    padding: 12px 22px;
    margin-bottom: 12px;
    box-shadow: 0 3px 10px rgba(74,63,53,0.08);
    border: 1px solid {RULE};
}}
.dashboard-nav-brand {{
    display: flex;
    align-items: center;
    gap: 12px;
}}
.dashboard-nav-icon {{
    width: 36px;
    height: 36px;
    border-radius: 10px;
    background: linear-gradient(135deg, {BROWN} 0%, {BRICK} 100%);
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 20px;
}}
.dashboard-nav-title {{
    font-size: 1.35rem;
    font-weight: 700;
    color: {BROWN_DARK};
    letter-spacing: 0.05em;
    font-family: 'STKaiti', 'KaiTi', 'SimKaiti', 'PingFang SC', serif;
}}
.dashboard-nav-subtitle {{
    font-size: 12px;
    color: {MUTED};
    margin-top: 1px;
}}
.dashboard-nav-time {{
    font-size: 12px;
    color: {MUTED};
    background: {PAPER_2};
    padding: 6px 12px;
    border-radius: 8px;
    border: 1px solid {RULE};
}}

/* 指标卡片 */
.metric-card {{
    background: {CREAM};
    border: 1px solid {RULE};
    border-radius: 10px;
    padding: 14px 12px;
    text-align: center;
    position: relative;
    overflow: hidden;
    box-shadow: 0 3px 10px rgba(74,63,53,0.08);
}}
.metric-card::before {{
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0; height: 3px;
    background: linear-gradient(90deg, {BROWN}, {BRICK});
}}
.metric-label {{
    color: {MUTED};
    font-size: 12px;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}}
.metric-value {{
    font-size: 1.55rem;
    font-weight: 700;
    color: {BROWN_DARK};
    font-family: 'Consolas', 'STKaiti', monospace;
}}

/* 内容卡片 */
.content-card {{
    background: {CREAM};
    border: 1px solid {RULE};
    border-radius: 10px;
    padding: 12px 14px;
    box-shadow: 0 2px 8px rgba(74,63,53,0.08);
    height: 100%;
}}
.card-title {{
    font-size: 0.95rem;
    font-weight: 600;
    color: {BROWN_DARK};
    margin-bottom: 0.4rem;
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-family: 'STKaiti', 'KaiTi', 'SimKaiti', 'PingFang SC', serif;
}}
.card-desc {{
    color: {MUTED};
    font-size: 0.78rem;
    line-height: 1.5;
    margin-bottom: 0.5rem;
}}

/* 爆款进度条 */
.hit-progress {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
    font-size: 0.82rem;
}}
.hit-name {{
    width: 40%;
    color: {INK};
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.hit-bar-bg {{
    flex: 1;
    height: 14px;
    background: rgba(139,107,77,0.12);
    border-radius: 7px;
    overflow: hidden;
}}
.hit-bar-fill {{
    height: 100%;
    border-radius: 7px;
    background: linear-gradient(90deg, {BRICK}, #d98880);
}}
.hit-value {{
    width: 60px;
    text-align: right;
    color: {BRICK};
    font-family: 'Consolas', monospace;
    font-weight: 600;
}}

/* 高赞评论滚动 */
.comment-scroll {{
    height: 180px;
    overflow: hidden;
    position: relative;
    background: {PAPER_2};
    border-radius: 10px;
    border: 1px solid {RULE};
}}
.comment-list {{
    animation: scrollComments 20s linear infinite;
}}
.comment-item {{
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.65rem 1rem;
    border-bottom: 1px solid {RULE};
    font-size: 0.86rem;
    line-height: 1.55;
    height: 60px;
    box-sizing: border-box;
    color: {INK};
}}
.comment-item:last-child {{ border-bottom: none; }}
.comment-rank {{
    flex-shrink: 0;
    width: 22px; height: 22px;
    border-radius: 50%;
    background: {BROWN};
    color: #fff;
    font-size: 0.7rem;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 2px;
}}
.comment-body {{ flex: 1; min-width: 0; }}
.comment-text {{
    color: {INK};
    word-break: break-all;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}}
.comment-meta {{
    color: {MUTED};
    font-size: 0.74rem;
    margin-top: 0.25rem;
}}
.comment-like {{ color: {BRICK}; font-weight: 600; }}
@keyframes scrollComments {{
    0% {{ transform: translateY(0); }}
    100% {{ transform: translateY(-50%); }}
}}

/* 主题列表 */
.topic-list {{
    font-size: 0.85rem;
    line-height: 1.9;
    color: {INK_LIGHT};
}}
.topic-list .t {{
    color: {BROWN};
    font-weight: 600;
    margin-right: 0.4rem;
}}

/* 侧边栏 */
[data-testid="stSidebar"] {{
    background: linear-gradient(180deg, {PAPER_2}, {PAPER}) !important;
    border-right: 1px solid {RULE};
}}
[data-testid="stSidebar"] .block-container {{
    padding-top: 24px;
}}

/* 强制侧边栏始终展开 */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div:first-child,
[data-testid="stSidebar"] > div:nth-child(2) {{
    min-width: 260px !important;
    max-width: 260px !important;
    width: 260px !important;
    transform: translateX(0) !important;
    visibility: visible !important;
    opacity: 1 !important;
    display: flex !important;
    position: relative !important;
    left: 0 !important;
    margin-left: 0 !important;
}}
[data-testid="stSidebar"] [data-testid="stSidebarNavSection"],
[data-testid="stSidebar"] .block-container {{
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
}}
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarNavCollapseButton"] {{
    display: none !important;
}}

/* 覆盖 Streamlit 响应式隐藏侧边栏 */
@media (max-width: 991px) {{
    [data-testid="stSidebar"] {{
        display: flex !important;
        transform: translateX(0) !important;
    }}
    [data-testid="stAppViewContainer"] {{
        flex-direction: row !important;
    }}
}}

/* 隐藏侧边栏默认的 app 入口，只保留自定义页面 */
[data-testid="stSidebarNav"] > ul > li:first-child {{
    display: none !important;
}}

/* 数据表格 */
.stDataFrame {{
    border-radius: 10px;
    overflow: hidden;
}}

/* select / input 样式 */
.stSelectbox, .stTextInput > div > div > input {{
    background: {CREAM} !important;
    border: 1px solid {RULE} !important;
    border-radius: 8px !important;
    color: {INK} !important;
}}
</style>
"""


def inject_theme():
    """注入全局民谣暖色主题 CSS。"""
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def nav_bar(title: str = "民谣风向标 · 数据洞察", update_time: str = ""):
    """渲染顶部导航栏。"""
    if not update_time:
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
        <div class="dashboard-nav">
            <div class="dashboard-nav-brand">
                <div class="dashboard-nav-icon">🎶</div>
                <div>
                    <div class="dashboard-nav-title">{title}</div>
                    <div class="dashboard-nav-subtitle">音乐评论用户行为分析 - 数据大屏</div>
                </div>
            </div>
            <div class="dashboard-nav-time">📅 数据更新时间：{update_time}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric_card(label: str, value: str):
    """渲染单个指标卡片（无增长率，与 dashboard.html 一致）。"""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


@contextmanager
def card(title: str, desc: str = ""):
    """带标题与说明文字的卡片容器（与 dashboard.html .panel 一致）。"""
    title_html = f'<div class="card-title">{title}</div>'
    desc_html = f'<div class="card-desc">{desc}</div>' if desc else ""
    st.markdown(
        f'<div class="content-card">{title_html}{desc_html}',
        unsafe_allow_html=True,
    )
    try:
        yield
    finally:
        st.markdown("</div>", unsafe_allow_html=True)


def section_title(title: str, desc: str):
    """独立 section 标题 + 说明（用于 panel 外部需要额外说明的场景）。"""
    st.markdown(
        f"""
        <div class="card-title" style="margin-bottom:0.2rem;">{title}</div>
        <div class="card-desc">{desc}</div>
        """,
        unsafe_allow_html=True,
    )


def hit_progress(name: str, width_pct: float, value_text: str):
    """爆款进度条单项。"""
    return f"""
    <div class="hit-progress">
        <div class="hit-name" title="{name}">{name}</div>
        <div class="hit-bar-bg"><div class="hit-bar-fill" style="width: {width_pct:.1f}%;"></div></div>
        <div class="hit-value">{value_text}</div>
    </div>
    """


def render_comments(items):
    """渲染可滚动高赞评论 HTML。"""
    if not items:
        return '<div style="color:#8c7b6c;text-align:center;padding:2rem 0;font-style:italic;">暂无高赞评论数据</div>'
    # 复制一份实现无缝滚动
    all_items = items + items
    rows = ""
    for i, c in enumerate(all_items):
        rank = (i % len(items)) + 1
        date = c.get("comment_time", "-")[:10] if c.get("comment_time") else "-"
        text = str(c.get("content", "")).replace("<", "&lt;").replace(">", "&gt;")
        like = c.get("like_count", 0)
        rows += f"""
        <div class="comment-item">
            <div class="comment-rank">{rank}</div>
            <div class="comment-body">
                <div class="comment-text">{text}</div>
                <div class="comment-meta"><span class="comment-like">👍 {like}</span><span>{date}</span></div>
            </div>
        </div>
        """
    return f'<div class="comment-scroll"><div class="comment-list">{rows}</div></div>'


def topic_list_html(topics):
    """渲染 LDA 主题列表。"""
    if not topics:
        return '<div style="color:#8c7b6c;text-align:center;padding:2rem 0;font-style:italic;">暂无主题数据</div>'
    html = '<div class="topic-list">'
    for t in topics:
        name = t.get("topic_name") or f"主题{t.get('topic_id', '')}"
        html += f'<div><span class="t">{name}</span>{t.get("keywords", "-")}</div>'
    html += "</div>"
    return html
