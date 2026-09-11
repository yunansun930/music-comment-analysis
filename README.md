# 基于公开评论数据的音乐评论用户行为分析

> 端到端数据分析项目：从网易云公开评论数据出发，完成数据采集 → 数仓建模 → 清洗 → 指标体系 → 用户分群 → 文本挖掘 → 模型预测 → 可视化 → 实验设计的全流程闭环。

## 项目背景

网易云音乐的播放、收藏、分享等用户行为数据不公开，但评论数据完全公开。本项目以 **仅评论数据** 为唯一真实来源，构建了一套完整的用户行为分析体系，用评论互动指标替代传统播放/收藏指标，实现从数据采集到模型预测的全流程分析。

## 核心数据

| 指标 | 数值 |
|------|------|
| 采集歌曲数 | 300 首 |
| 原始评论数 | 26 万条 |
| 清洗后评论数 | 21.5 万条（保留率 83%） |
| 覆盖用户数 | 2.2 万人 |
| 数据库表数 | 31 张 |
| Dashboard 页面 | 9 页 |

## 技术栈

| 类别 | 技术 |
|------|------|
| 数据采集 | requests、SimHash 去重 |
| 数据存储 | MySQL（ODS → DWD → DWS → ADS 四层数仓） |
| 数据清洗 | pandas、SimHash、正则过滤 |
| 文本分析 | jieba 分词、LDA 主题模型、BERT 情感分析 |
| 机器学习 | XGBoost、RandomForest、LogisticRegression、Prophet |
| 模型评估 | 5 折交叉验证、Bootstrap 95%CI、PR-AUC、SHAP |
| 统计检验 | t 检验、Mann-Whitney U、卡方检验、Kruskal-Wallis |
| 实验设计 | A/B 测试框架（样本量 → 分组 → 检验 → 效应量） |
| 可视化 | Streamlit、ECharts、HTML Dashboard |
| 部署 | Docker、docker-compose |

## 项目结构

```
音乐评论用户行为分析/
├── step1数据采集/          # 爬虫采集歌曲、歌手、评论数据
├── step2数据库建设/         # MySQL 四层数仓建表与数据加载
├── step3数据清洗/           # SimHash 去重、无效评论过滤
├── step4指标体系/           # DWS 汇总层 + ADS 应用层指标计算
├── step5用户分析/           # K-means 聚类、RFM 分层、同期群分析
├── step6文本分析/           # LDA 主题模型、BERT 情感分类、TF-IDF
├── step7模型预测/           # 流失预测(AUC=0.77)、爆款预测(AUC=0.88)、时序预测
├── step8可视化展示/         # Streamlit Dashboard（9 页）
├── step9实验设计/           # A/B 测试框架
├── tests/                  # 测试与架构图
├── report_images/          # 报告配图
├── docker-compose.yml       # 一键启动 MySQL + Dashboard
├── Dockerfile
├── sql_showcase.sql         # 进阶 SQL 展示（窗口函数/CTE/漏斗）
├── 项目架构设计方案.md
├── 项目完整报告_最终版.md
├── 业务洞察报告.md
├── 字段映射表.html
└── requirements.txt
```

## 快速开始

### 方式一：Docker 一键启动（推荐）

```bash
# 1. 复制环境变量配置
cp .env.example .env
# 编辑 .env 填入你的 MySQL 密码

# 2. 启动
docker-compose up -d

# 3. 访问 Dashboard
# http://localhost:8501
```

### 方式二：本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 MySQL 连接信息

# 3. 初始化数据库
cd step2数据库建设 && python init_db.py && python load_data.py

# 4. 运行数据清洗
cd ../step3数据清洗 && python run.py

# 5. 计算指标
cd ../step4指标体系 && python run.py

# 6. 用户分析
cd ../step5用户分析 && python run.py

# 7. 文本分析
cd ../step6文本分析 && python run.py

# 8. 模型训练
cd ../step7模型预测 && python run.py

# 9. 启动 Dashboard
cd ../step8可视化展示 && streamlit run app.py
```

## 分析流程

```
数据来源 → 数据采集 → ODS贴源层 → DWD清洗层 → DWS汇总层 → ADS应用层 → 模型预测 → 可视化展示
```

每个步骤目录下都有独立的 `README.md`，包含详细的模块说明和运行方式。

## 核心成果

- **数据治理**：SimHash 去重，26 万 → 21.5 万条（保留率 83%）
- **数仓建模**：4 层 31 表，覆盖 ODS/DWD/DWS/ADS 全链路
- **用户分群**：K-means + RFM 双视角聚类，识别核心用户群体
- **文本洞察**：LDA 5 主题 + BERT 情感分类（82.9% 正面）
- **模型预测**：流失预测 AUC=0.77，爆款预测 AUC=0.88
- **业务建议**：8 条可落地建议，覆盖用户运营、推送优化、内容治理
- **实验设计**：A/B 测试框架，从样本量计算到效应量评估

## License

MIT
