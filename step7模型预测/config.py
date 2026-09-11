"""
Step7 模型预测 - 全局配置
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env():
    """向上查找项目根目录的 .env 文件并加载。"""
    path = Path(__file__).resolve().parent
    for _ in range(3):
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(dotenv_path=env_file)
            return
        path = path.parent


_load_env()

# MySQL 数据库配置（密码必须从环境变量读取，禁止硬编码）
_DB_PASSWORD = os.getenv("DB_PASSWORD")
if not _DB_PASSWORD:
    raise ValueError("请先设置环境变量 DB_PASSWORD，例如：$env:DB_PASSWORD='你的密码'")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": _DB_PASSWORD,
    "database": os.getenv("DB_NAME", "music_analysis"),
    "charset": "utf8mb4",
}

# 爆款歌曲预测配置
HOT_SONG_CONFIG = {
    "top_percent": 0.10,          # Top 10% 评论量作为爆款
    "test_size": 0.2,             # 测试集比例
    "random_state": 42,
    "xgb_params": {
        "n_estimators": 100,
        "max_depth": 4,
        "learning_rate": 0.1,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "objective": "binary:logistic",
        "eval_metric": "auc",
        "use_label_encoder": False,
        "random_state": 42,
        "n_jobs": -1,
    },
    "lr_params": {
        "max_iter": 1000,
        "random_state": 42,
    },
    "forecast_days": 30,          # Prophet 预测未来 30 天
}

# 输出模型文件保存目录
MODEL_DIR = "models"
