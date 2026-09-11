# Step1 数据采集

本目录包含「音乐平台用户行为洞察与内容增长分析系统」第一步的数据采集代码。

## 目录结构

```
step1数据采集/
├── config.py               # 全局配置：路径、API 地址、采集限制
├── utils.py                # 通用工具：HTTP 请求、CSV/JSON 保存、时间戳转换
├── song_spider.py          # 歌曲数据采集
├── artist_spider.py        # 歌手数据采集
├── comment_spider.py       # 评论数据采集
├── user_spider.py          # 用户数据采集
├── behavior_generator.py   # 用户行为数据生成
├── run.py                  # 一键运行入口
├── check_data.py           # 数据质量检查
├── fix_existing_data.py    # 存量数据修复（时间戳、昵称等）
├── requirements.txt        # 依赖包
└── data/                   # 生成的数据文件目录
    ├── dim_song.csv
    ├── dim_artist.csv
    ├── dim_user.csv
    ├── fact_comment.csv
    └── fact_behavior.csv
```

## 数据说明

| 文件 | 对应表 | 数据来源 | 说明 |
|------|--------|---------|------|
| dim_song.csv | 歌曲维度表 | 网易云音乐搜索 + 歌曲详情接口 | 真实数据 |
| dim_artist.csv | 歌手维度表 | 网易云音乐歌手接口 | 真实数据 |
| dim_user.csv | 用户维度表 | 网易云音乐用户详情接口 + 评论提取 | 部分真实数据 |
| fact_comment.csv | 评论事实表 | 网易云音乐评论接口 | 真实数据 |
| fact_behavior.csv | 行为事实表 | 基于歌曲/评论生成 | 模拟数据 |

> 说明：
> - 用户行为日志属于平台内部数据，不对外公开，因此通过基于真实歌曲和评论数据生成模拟行为日志，用于后续指标体系建设和模型训练。
> - `dim_artist.csv` 仅保留 `artist_id` 和 `artist_name`，因为网易云公开接口无法稳定返回歌手性别、粉丝数等字段；歌手影响力特征将在后续通过行为数据聚合衍生。

## 环境准备

```bash
pip install -r requirements.txt
```

## 运行方式

### 一键运行全部流程（推荐）

使用 PowerShell 脚本，自动开启实时输出模式，方便查看进度：

```powershell
.\start.ps1
```

或直接运行（Windows 下输出可能有缓冲，建议用上面的脚本）：

```bash
python run.py
```

### 单独运行某个模块

```bash
# 仅采集歌曲
python song_spider.py

# 仅采集评论（需要先运行 song_spider.py 生成 dim_song.csv）
python comment_spider.py

# 仅生成行为数据（需要先完成歌曲、评论、用户采集）
python behavior_generator.py
```

### 数据质量检查

```bash
python check_data.py
```

### 存量数据修复

如果已经采集过数据，但需要修复时间戳格式或重新获取用户昵称，可运行：

```bash
python fix_existing_data.py
```

## 配置调整

编辑 `config.py` 中的 `LIMITS` 字典可调整采集规模：

```python
LIMITS = {
    "search_keywords": ["周杰伦", "林俊杰", "邓紫棋"],  # 搜索关键词
    "songs_per_keyword": 20,      # 每个关键词搜索歌曲数
    "comments_per_song": 30,      # 每首歌采集评论数
    "request_delay": 1.5,         # 请求间隔（秒）
}
```

## 注意事项

1. **合法合规**：本项目仅用于学习数据分析，采集数据量默认设置较小，请勿用于商业用途或大规模爬取。
2. **反爬限制**：网易云音乐接口可能存在访问频率限制，如遇失败请增大 `request_delay` 或分时段运行。
3. **数据质量**：部分字段（如歌手性别、用户性别、歌曲语言）在公开接口中不直接提供，会在后续数据清洗阶段补充或标记为空。
