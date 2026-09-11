"""
Step3 数据清洗 - 全局配置
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

# 项目根目录
BASE_DIR = Path(__file__).parent.resolve()

# MySQL 连接配置（密码必须从环境变量读取，禁止硬编码）
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
