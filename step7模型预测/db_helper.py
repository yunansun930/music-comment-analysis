"""
Step7 模型预测 - 数据库读写公共模块
"""
import re
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text
from config import DB_CONFIG


_TABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_table_name(table_name: str) -> None:
    """校验表名仅包含字母、数字、下划线，防止 SQL 注入。"""
    if not isinstance(table_name, str) or not _TABLE_NAME_RE.match(table_name):
        raise ValueError(f"非法表名: {table_name}")


def build_engine():
    """创建 SQLAlchemy engine。"""
    url = (
        f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
        f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        f"?charset={DB_CONFIG['charset']}"
    )
    return create_engine(url)


def read_table(table_name: str) -> pd.DataFrame:
    """读取整张表。"""
    _validate_table_name(table_name)
    engine = build_engine()
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    finally:
        engine.dispose()


def read_sql(query: str, params: Optional[dict] = None) -> pd.DataFrame:
    """执行参数化 SQL 查询。"""
    engine = build_engine()
    try:
        return pd.read_sql(text(query), engine, params=params or {})
    finally:
        engine.dispose()


def write_table(df: pd.DataFrame, table_name: str, if_exists: str = "replace"):
    """写入 DataFrame 到数据库表。"""
    _validate_table_name(table_name)
    engine = build_engine()
    try:
        df.to_sql(
            name=table_name,
            con=engine,
            if_exists=if_exists,
            index=False,
            method="multi",
            chunksize=1000,
        )
    finally:
        engine.dispose()


def execute(sql: str, params: Optional[dict] = None):
    """执行写操作 SQL（支持参数化）。"""
    engine = build_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text(sql), params or {})
            conn.commit()
    finally:
        engine.dispose()
