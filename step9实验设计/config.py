"""
Step9 实验设计 - 全局配置
"""
import os
from pathlib import Path

from dotenv import load_dotenv


def _load_env():
    path = Path(__file__).resolve().parent
    for _ in range(3):
        env_file = path / ".env"
        if env_file.exists():
            load_dotenv(dotenv_path=env_file)
            return
        path = path.parent


_load_env()

_DB_PASSWORD = os.getenv("DB_PASSWORD")
if not _DB_PASSWORD:
    raise ValueError("请先设置环境变量 DB_PASSWORD")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "root"),
    "password": _DB_PASSWORD,
    "database": os.getenv("DB_NAME", "music_analysis"),
    "charset": "utf8mb4",
}

AB_TEST_CONFIG = {
    "alpha": 0.05,
    "power": 0.80,
    "mde_ratio": 0.10,
    "n_bootstrap": 1000,
    "random_state": 42,
}
