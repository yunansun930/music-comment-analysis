"""
Step6 文本分析 - 数据库操作公共模块
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
    return pymysql.connect(**DB_CONFIG)


def get_engine():
    cfg = DB_CONFIG
    url = (
        f"mysql+pymysql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['database']}"
        f"?charset={cfg['charset']}"
    )
    return create_engine(url)


def read_table(table_name: str) -> pd.DataFrame:
    _validate_table_name(table_name)
    engine = get_engine()
    try:
        df = pd.read_sql(f"SELECT * FROM {table_name}", engine)
        return df
    finally:
        engine.dispose()


def read_sql(sql: str, params: Optional[dict] = None) -> pd.DataFrame:
    engine = get_engine()
    try:
        df = pd.read_sql(text(sql), engine, params=params or {})
        return df
    finally:
        engine.dispose()


def to_sql_replace(df: pd.DataFrame, table_name: str, batch_size: int = 2000):
    _validate_table_name(table_name)
    if df.empty:
        print(f"[Warning] {table_name} 数据为空，跳过写入")
        return

    df = df.replace({np.nan: None})
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].where(df[col].notna(), None)

    rows = [tuple(row) for row in df.values]
    total = len(rows)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {table_name}")
            conn.commit()

            columns = ", ".join([f"`{c}`" for c in df.columns])
            placeholders = ", ".join(["%s"] * len(df.columns))
            sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

            for i in range(0, total, batch_size):
                batch = rows[i : i + batch_size]
                cursor.executemany(sql, batch)
                conn.commit()
                print(f"  [{table_name}] 已写入 {min(i + batch_size, total)}/{total} 条", flush=True)

            print(f"[OK] {table_name}: 写入 {total} 行")
    finally:
        conn.close()


def ensure_table(sql: str):
    """如果表不存在则创建。支持多条 CREATE TABLE 语句。"""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 按分号拆分，逐条执行
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if stmt:
                    cursor.execute(stmt + ";")
            conn.commit()
    finally:
        conn.close()
