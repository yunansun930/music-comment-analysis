# Step5 用户分析

本目录包含「音乐平台用户行为洞察与内容增长分析系统」第五步的用户分析代码。

## 目录结构

```
step5用户分析/
├── config.py               # 全局配置
├── db_helper.py            # 数据库操作公共模块
├── user_features.py        # 用户特征工程
├── kmeans_cluster.py       # K-means 聚类 + 用户标签
├── run.py                  # 一键运行入口
├── check_clusters.py       # 聚类结果检查
├── requirements.txt        # 依赖包
└── README.md               # 使用说明
```

## 功能说明

1. **特征工程**：从 `dws_user_daily` 聚合用户总播放、评论、点赞、收藏、分享次数，活跃天数，活跃歌曲数等指标。
2. **标准化**：对特征进行 StandardScaler 标准化。
3. **K-means 聚类**：将用户分为 3 类：
   - 核心粉丝
   - 内容消费者
   - 轻度用户
4. **更新画像表**：将聚类结果（`cluster_label`、`user_type`）更新到 `ads_user_portrait` 表。

## 环境准备

```bash
pip install -r requirements.txt
```

## 运行方式

### 一键运行

```bash
python -u run.py
```

### 检查聚类结果

```bash
python -u check_clusters.py
```

## 配置调整

编辑 `config.py` 可调整：

- `N_CLUSTERS`：聚类数量（默认 3）
- `RANDOM_STATE`：随机种子（默认 42）

## 注意事项

- 运行前请确保已完成 Step4 指标体系，即 `dws_user_daily` 表已有数据。
- 聚类标签根据聚类中心自动推断，每次结果会因数据分布略有不同，但总体模式稳定。
