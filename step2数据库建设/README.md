# Step2 数据库建设

本目录包含「音乐平台用户行为洞察与内容增长分析系统」第二步的数据库建设代码。

## 目录结构

```text
step2数据库建设/
├── config.py          # 数据库连接配置
├── schema.sql         # MySQL 数仓分层建表语句（ODS/DWD/DWS/ADS）
├── init_db.py         # 初始化数据库和表结构
├── load_data.py       # 将 step1 CSV 数据加载到 ODS/DWD
├── check_db.py        # 数据库数据质量检查
├── requirements.txt   # 依赖包
└── README.md          # 使用说明
```

## 数据仓库分层设计

| 分层 | 说明 | 本步骤创建的表 |
|------|------|---------------|
| **ODS** | 贴源层，结构与 CSV 一致 | `ods_song`, `ods_artist`, `ods_user`, `ods_comment`, `ods_behavior` |
| **DWD** | 明细层，清洗后的标准表 | `dwd_song_info`, `dwd_artist_info`, `dwd_user_info`, `dwd_comment_detail`, `dwd_behavior_detail` |
| **DWS** | 服务层，按日聚合的指标表 | `dws_song_daily`, `dws_user_daily`, `dws_artist_daily` |
| **ADS** | 应用层，面向分析主题 | `ads_song_rank`, `ads_user_portrait`, `ads_song_lifecycle` |

## 环境准备

### 1. 安装 MySQL

确保本地已安装并启动 MySQL 服务，记住 root 密码。

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置数据库连接

编辑 `config.py`，或在运行前设置环境变量：

```bash
# Windows PowerShell
$env:DB_HOST="localhost"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="你的密码"
$env:DB_NAME="music_analysis"
```

## 运行步骤

### 第一步：创建数据库和表

```bash
python init_db.py
```

该脚本会：
- 创建数据库 `music_analysis`
- 创建 ODS / DWD / DWS / ADS 四层数据表

### 第二步：加载 CSV 数据

```bash
python load_data.py
```

该脚本会：
- 将 `../step1数据采集/data/` 下的 CSV 加载到 ODS 层
- 清洗后写入 DWD 层

### 第三步：检查数据质量

```bash
python check_db.py
```

该脚本会：
- 输出各表数据量
- 检查表间关联一致性

## 注意事项

1. **字符集**：所有表使用 `utf8mb4`，确保中文评论和昵称正常存储。
2. **幂等性**：`load_data.py` 每次运行会先 `TRUNCATE` ODS 表，再重新加载；DWD 层使用 `INSERT ... ON DUPLICATE KEY UPDATE`，可重复执行。
3. **DWS/ADS 表**：本步骤仅创建表结构，数据将在 Step4（指标体系建设）和后续分析步骤中填充。
