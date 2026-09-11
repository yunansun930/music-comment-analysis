# Step4 指标体系建设

本目录包含「音乐平台用户行为洞察与内容增长分析系统」第四步的指标体系建设代码。

## 目录结构

```text
step4指标体系/
├── config.py              # 全局配置（数据库连接、权重、阈值）
├── db_helper.py           # 数据库读写公共模块
├── dws_song_daily.py      # 歌曲日指标
├── dws_user_daily.py      # 用户日指标
├── dws_artist_daily.py    # 歌手日指标
├── ads_song_metrics.py    # 歌曲热度排名 & 生命周期
├── ads_user_portrait.py   # 用户画像 & 用户价值
├── run.py                 # 一键运行入口
├── check_indicators.py    # 计算结果质量检查
├── requirements.txt       # 依赖包
└── README.md              # 使用说明
```

## 指标体系说明

### DWS 层

| 表 | 说明 |
|----|------|
| `dws_song_daily` | 歌曲日指标：评论数、获赞数、回复数、热度分、增长率 |
| `dws_user_daily` | 用户日指标：评论数、获赞数、回复数、活跃歌曲数、平均评论长度 |
| `dws_artist_daily` | 歌手日指标：评论数、获赞数、回复数 |

### ADS 层

| 表 | 说明 |
|----|------|
| `ads_song_rank` | 每日歌曲热度排名、生命周期阶段 |
| `ads_song_lifecycle` | 每日歌曲生命周期阶段 |
| `ads_user_portrait` | 用户累计行为、用户价值分、用户类型 |

## 核心指标公式

### 歌曲热度分 Heat Score

```text
Heat Score =
0.5 × 评论增长率 +
0.3 × 获赞增长率 +
0.2 × 回复增长率
```

另外加入 `0.01 × log(评论数 + 1)` 作为基础热度修正，避免全是 0 增长时分值为 0。

### 用户价值分 User Value

```text
User Value =
0.4 × 活跃度（标准化评论数）+
0.3 × 互动贡献（标准化获赞数）+
0.3 × 内容贡献（标准化回复数）
```

### 生命周期阶段

| 阶段 | 判断条件 |
|------|---------|
| 冷启动 | 日评论数 ≤ 5 且热度分 ≤ 0 |
| 爆发期 | 评论增长率 ≥ 50%，或热度分进入当日 Top 20% |
| 增长期 | 评论增长率 ≥ 10% |
| 衰退期 | 评论增长率 ≤ -10% |
| 稳定期 | 其他情况 |

## 运行步骤

### 一键运行

```bash
cd "c:\Users\EDY\Desktop\syn\syn\音乐评论用户行为分析\step4指标体系"
python run.py
python check_indicators.py
```

### 单独运行某个模块

```bash
python dws_song_daily.py
python dws_user_daily.py
python dws_artist_daily.py
python ads_song_metrics.py
python ads_user_portrait.py
```

## 说明

- 所有指标表采用 `TRUNCATE + INSERT` 方式写入，可重复运行。
- `ads_user_portrait` 中的 `cluster_label` 字段在 Step4 中默认为 -1，将在 Step5 用户聚类分析后更新。
