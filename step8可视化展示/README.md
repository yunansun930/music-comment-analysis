# Step8 可视化展示

## 功能

基于 Streamlit + Plotly 构建的音乐平台用户行为洞察 Dashboard，包含 5 个页面：

| 页面 | 功能 |
|------|------|
| 首页 | 平台核心指标、热门歌曲 TOP 10、生命周期阶段分布 |
| 歌曲分析 | 搜索歌曲、查看生命周期曲线、评论热词、情感分布 |
| 用户画像 | 用户类型分布、用户价值分布、高价值用户 TOP 10 |
| 文本洞察 | 全局关键词、LDA 主题、全局情感汇总 |
| 爆款预测 | 模型指标、特征重要性、预测爆款 TOP 20、未来热度趋势 |

## 运行方式

```bash
cd "c:\Users\EDY\Desktop\syn\syn\音乐评论用户行为分析\step8可视化展示"
pip install -r requirements.txt
streamlit run app.py
```

运行后会自动打开浏览器访问 `http://localhost:8501`。

## 依赖

- streamlit
- plotly
- pandas
- pymysql
- SQLAlchemy
