"""
Step3 数据清洗 - 数据库操作公共模块
"""

import re
from typing import Optional

import numpy as np
import pandas as pd
import pymysql
from sqlalchemy import create_engine, text

from config import DB_CONFIG


_TABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_table_name(table_name: str) -> None:
    """校验表名仅包含字母、数字、下划线，防止 SQL 注入。"""
    if not isinstance(table_name, str) or not _TABLE_NAME_RE.match(table_name):
        raise ValueError(f"非法表名: {table_name}")


def get_connection():
    """获取 MySQL 连接。"""
    return pymysql.connect(**DB_CONFIG)


def get_engine():
    """获取 SQLAlchemy engine，用于 pandas 读取。"""
    cfg = DB_CONFIG
    url = (
        f"mysql+pymysql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
        f"?charset={cfg['charset']}"
    )
    return create_engine(url)


def read_table(table_name: str) -> pd.DataFrame:
    """从 MySQL 读取整张表。"""
    _validate_table_name(table_name)
    engine = get_engine()
    try:
        return pd.read_sql(f"SELECT * FROM {table_name}", engine)
    finally:
        engine.dispose()


def read_sql(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    """执行参数化 SQL 查询。"""
    engine = get_engine()
    try:
        return pd.read_sql(text(sql), engine, params=params or {})
    finally:
        engine.dispose()


def to_sql_replace(df: pd.DataFrame, table_name: str):
    """
    将 DataFrame 写入 MySQL，采用先 TRUNCATE 再 INSERT 的方式，
    保证幂等性。
    """
    _validate_table_name(table_name)
    if df.empty:
        print(f"[Warning] {table_name} 数据为空，跳过写入")
        return

    df = df.replace({np.nan: None})
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].where(df[col].notna(), None)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {table_name}")

            columns = ", ".join([f"`{c}`" for c in df.columns])
            placeholders = ", ".join(["%s"] * len(df.columns))
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

            rows = [tuple(row) for row in df.values]
            cursor.executemany(sql, rows)
            conn.commit()
            print(f"[OK] {table_name}: 写入 {len(rows)} 行")
    finally:
        conn.close()


def execute_sql(sql: str, params: Optional[tuple] = None):
    """执行任意 SQL（不返回结果，支持参数化）。"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, params or ())
            conn.commit()
    finally:
        conn.close()
