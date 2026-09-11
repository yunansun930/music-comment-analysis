"""
Step1 数据采集 - 全局配置

说明：
- 本项目仅采集网易云音乐公开数据，用于学习数据分析与数据仓库建模。
- 默认设置了较小的采集规模（如搜索关键词数、每首歌评论数），避免对目标站点造成压力。
- 如需扩大规模，请自行调整 LIMITS 中的数值，并遵守目标网站的 robots.txt 与服务条款。
"""

from pathlib import Path

# 当前脚本所在目录作为项目根目录
BASE_DIR = Path(__file__).parent.resolve()

# 数据存储目录
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# 请求头：模拟浏览器访问，降低被反爬拦截的概率
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://music.163.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 网易云音乐公开 API 地址（非官方文档，来自公开网络分析，仅供学习使用）
API = {
    "search": "https://music.163.com/api/search/get/web",
    "song_detail": "https://music.163.com/api/song/detail/",
    "comment": "https://music.163.com/api/v1/resource/comments/R_SO_4_{song_id}",
    "artist": "https://music.163.com/api/v1/artist/{artist_id}",
    "user_detail": "https://music.163.com/api/v1/user/detail/{user_id}",
}

# 采集限制配置
# 当前为中等规模配置，用于支撑后续用户分析、文本挖掘和预测模型：
#   预计歌曲数：10 个关键词 × 30 首 = 300 首
#   预计评论数：300 首 × 100 条 = 30,000 条
# 如仍被反爬拦截，可适当增大 request_delay 或降低 songs_per_keyword / comments_per_song。
LIMITS = {
    "search_keywords": [
        "赵雷", "宋冬野", "马頔", "陈鸿宇", "花粥",
        "房东的猫", "尧十三", "贰佰", "谢春花", "枯木逢春"
    ],
    "songs_per_keyword": 30,      # 每个关键词搜索多少首歌
    "comments_per_song": 100,     # 每首歌采集多少条评论
    "comment_offset_step": 20,    # 网易云评论接口分页步长
    "max_retries": 5,             # 请求失败最大重试次数
    "request_delay": 5.0,         # 每次请求间隔秒数（请保持礼貌）
}

# CSV 输出文件名
OUTPUT = {
    "dim_song": DATA_DIR / "dim_song.csv",
    "dim_artist": DATA_DIR / "dim_artist.csv",
    "dim_user": DATA_DIR / "dim_user.csv",
    "fact_comment": DATA_DIR / "fact_comment.csv",
    "fact_behavior": DATA_DIR / "fact_behavior.csv",
    "raw_search": DATA_DIR / "raw_search.json",
}
