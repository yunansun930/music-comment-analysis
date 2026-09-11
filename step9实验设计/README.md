# Step9 实验设计 - A/B 测试框架

## 目标
展示完整的 A/B 实验设计能力：假设 → 样本量计算 → 分组 → 检验 → 效应量 → 置信区间 → 结论。

## 模块说明
- `ab_test_framework.py`：模拟实验（推送通知对评论数的影响）
- `config.py`：实验配置（alpha/power/MDE）
- `db_helper.py`：数据库操作
- `run.py`：入口

## 输出表
| 表名 | 说明 |
|------|------|
| `ads_ab_test_results` | A/B 测试结果（含统计量/p值/效应量/CI） |

## 运行
```powershell
cd step9实验设计 ; python run.py ; cd ..
```

## 注意
此模块为**模拟实验**，展示的是实验设计方法论，非真实业务结论。
