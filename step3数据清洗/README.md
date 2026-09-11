# Step3 数据清洗

本目录包含「音乐平台用户行为洞察与内容增长分析系统」第三步的数据清洗代码。

## 目录结构

```text
step3数据清洗/
├── config.py          # 数据库连接配置
├── db_helper.py       # 数据库读写公共模块
├── clean_rules.py     # 评论清洗规则定义
├── clean_comment.py   # 评论数据清洗
├── clean_user.py      # 用户数据清洗
├── clean_song.py      # 歌曲数据清洗
├── clean_behavior.py  # 行为数据清洗
├── run.py             # 一键运行入口
├── check_clean.py     # 清洗结果质量检查
├── requirements.txt   # 依赖包
└── README.md          # 使用说明
```

## 清洗内容

| 数据类型 | 清洗操作 |
|---------|---------|
| **评论** | 去除无意义评论、按歌曲去重、文本规范化、去除控制字符和重复标点 |
| **用户** | 填充缺失等级/性别/年龄段/注册时间/省份/城市 |
| **歌曲** | 填充缺失类型/语言/标签/专辑/时长/发布时间 |
| **行为** | 过滤空值、过滤非法行为类型、过滤未来时间、去除重复行为 |

## 无意义评论过滤规则

以下评论会被视为无意义并删除：

- 长度小于 3 个字符的短评
- 黑名单词：`666`、`哈哈`、`好听`、`不错`、`赞`、`good`、`nice` 等
- 纯数字、纯语气词、纯标点

## 环境准备

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置数据库连接

编辑 `config.py`，或在运行前设置环境变量：

```powershell
$env:DB_HOST="localhost"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="你的密码"
$env:DB_NAME="music_analysis"
```

> 环境变量只在当前 PowerShell 窗口有效。

## 运行步骤

### 一键运行全部清洗

```bash
python run.py
```

### 单独运行某个清洗模块

```bash
python clean_comment.py
python clean_user.py
python clean_song.py
python clean_behavior.py
```

### 检查清洗结果

```bash
python check_clean.py
```

## 说明

- 清洗后的数据会**覆盖写回** `dwd_comment_detail`、`dwd_user_info`、`dwd_song_info`、`dwd_behavior_detail`。
- 每个模块都采用 `TRUNCATE + INSERT` 的方式，可重复运行，保证幂等性。
- 如果需要保留原始 DWD 数据，请在运行前先备份。
