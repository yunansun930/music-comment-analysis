# Step6 文本分析

本目录包含「音乐平台用户行为洞察与内容增长分析系统」第六步的文本分析代码。

## 目录结构

```
step6文本分析/
├── config.py                  # 全局配置
├── db_helper.py               # 数据库操作公共模块
├── text_preprocessing.py      # 文本预处理：清洗、分词、去停用词
├── tfidf_analysis.py          # TF-IDF 关键词提取
├── lda_analysis.py            # LDA 主题模型
├── sentiment_analysis.py      # BERT 情感分析
├── run.py                     # 一键运行入口
├── check_text.py              # 结果检查
├── requirements.txt           # 依赖包
└── README.md                  # 使用说明
```

## 功能说明

1. **文本预处理**
   - 清洗评论中的 URL、@用户名、特殊符号
   - 使用 jieba 分词
   - 去除停用词

2. **TF-IDF 关键词提取**
   - 提取全局热门关键词 Top 100
   - 按歌曲提取关键词 Top 20

3. **LDA 主题模型**
   - 将评论聚类为 5 个主题
   - 输出每个主题的关键词
   - 统计每首歌的主题分布

4. **BERT 情感分析**
   - 使用 `uer/roberta-base-finetuned-jd-binary-chinese` 模型
   - 输出每条评论的 positive 概率
   - 映射为 positive / neutral / negative 三分类
   - 计算歌曲和全局满意度得分

## 环境准备

```bash
pip install -r requirements.txt
```

> 首次运行会自动下载 BERT 模型（约 500MB），请保持网络畅通。

## 运行方式

### 一键运行

```bash
python -u run.py
```

### 检查文本分析结果

```bash
python -u check_text.py
```

## 配置调整

编辑 `config.py` 可调整：

- `N_TOPICS`：LDA 主题数（默认 5）
- `TOPIC_N_WORDS`：每个主题显示的关键词数（默认 10）
- `TFIDF_TOP_N`：每首歌提取的关键词数（默认 20）
- `SENTIMENT_BATCH_SIZE`：BERT 批处理大小（默认 64）
- `SENTIMENT_THRESHOLDS`：三分类阈值

## 注意事项

- 运行前请确保已完成 Step3 数据清洗，即 `dwd_comment_detail` 表已有数据。
- BERT 情感分析 2.5 万条评论预计需要 20~60 分钟（取决于 CPU 性能）。
- 如果模型下载失败，可以手动从 Hugging Face 下载后放到本地缓存目录。
