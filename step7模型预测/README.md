# Step7 模型预测

## 功能

- 爆款歌曲预测：基于歌曲特征、歌手影响力、评论情感、主题多样性，使用 Logistic Regression + XGBoost 预测歌曲是否会成为爆款。
- 时间序列热度预测：使用 Prophet 为每首歌预测未来 30 天热度趋势。

## 运行方式

```bash
cd "c:\Users\EDY\Desktop\syn\syn\音乐评论用户行为分析\step7模型预测"
pip install -r requirements.txt
python -u run.py
python -u check_models.py
```

## 输出结果

| 表 | 说明 |
|----|------|
| `ads_hot_predict` | 每首歌的爆款概率及是否预测为爆款 |
| `ads_model_metrics` | LR / XGBoost 模型评估指标 |
| `ads_feature_importance` | 特征重要性排名 |
| `ads_song_forecast` | 未来 30 天热度预测 |

## 模型文件

- `models/logistic_regression_hot_song_model.pkl`
- `models/xgboost_hot_song_model.pkl`
- `models/scaler.pkl`
- `models/feature_cols.pkl`
- `models/prophet_forecasters_sample.pkl`
