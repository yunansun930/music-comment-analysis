"""
Step2 数据库建设 - 初始化数据库与表结构

运行命令：
    python init_db.py
"""

import pymysql
import pymysql.constants.CLIENT as CLIENT

from config import DB_CONFIG


def get_connection(use_database: bool = True, multi_statements: bool = False):
    """获取 MySQL 连接。"""
    config = DB_CONFIG.copy()
    if not use_database:
        config.pop("database", None)
    if multi_statements:
        config["client_flag"] = CLIENT.MULTI_STATEMENTS
    return pymysql.connect(**config)


def create_database():
    """创建数据库。"""
    conn = get_connection(use_database=False)
    try:
        with conn.cursor() as cursor:
            db_name = DB_CONFIG["database"]
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {db_name} "
                f"DEFAULT CHARACTER SET utf8mb4 "
                f"DEFAULT COLLATE utf8mb4_unicode_ci"
            )
            print(f"[OK] 数据库 '{db_name}' 创建/确认成功")
    finally:
        conn.close()


def create_tables():
    """执行 schema.sql 创建所有表。"""
    # 启用多语句执行，确保 DROP TABLE 和 CREATE TABLE 顺序正确执行
    conn = get_connection(use_database=True, multi_statements=True)
    try:
        with conn.cursor() as cursor:
            with open("schema.sql", "r", encoding="utf-8") as f:
                sql_statements = f.read()
            cursor.execute(sql_statements)
            # 需要消耗掉所有结果集
            while cursor.nextset():
                pass
            conn.commit()
            print("[OK] 所有数据仓库表创建成功")
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("Step2 数据库建设 - 初始化")
    print("=" * 60)

    create_database()
    create_tables()

    print("\n" + "=" * 60)
    print("数据库初始化完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
