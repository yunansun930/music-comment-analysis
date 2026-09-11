"""
Step2 数据库建设 - 数据库数据质量检查

运行命令：
    python check_db.py
"""

import pymysql

from config import DB_CONFIG


def get_connection():
    return pymysql.connect(**DB_CONFIG)


def check_table_counts(cursor):
    """检查各层表的数据量。"""
    tables = [
        "ods_song", "ods_artist", "ods_user", "ods_comment", "ods_behavior",
        "dwd_song_info", "dwd_artist_info", "dwd_user_info", "dwd_comment_detail", "dwd_behavior_detail",
        "dws_song_daily", "dws_user_daily", "dws_artist_daily",
        "ads_song_rank", "ads_user_portrait", "ads_song_lifecycle",
    ]

    print("\n[数据库表数据量检查]")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:30s}: {count:6d} rows")


def check_referential_integrity(cursor):
    """检查关键关联一致性。"""
    print("\n[关联一致性检查]")

    checks = [
        ("ods_comment 中不存在于 ods_song 的 song_id", """
            SELECT COUNT(DISTINCT song_id) FROM ods_comment
            WHERE song_id NOT IN (SELECT song_id FROM ods_song)
        """),
        ("ods_comment 中不存在于 ods_user 的 user_id", """
            SELECT COUNT(DISTINCT user_id) FROM ods_comment
            WHERE user_id NOT IN (SELECT user_id FROM ods_user)
        """),
        ("ods_behavior 中不存在于 ods_song 的 song_id", """
            SELECT COUNT(DISTINCT song_id) FROM ods_behavior
            WHERE song_id NOT IN (SELECT song_id FROM ods_song)
        """),
        ("ods_behavior 中不存在于 ods_user 的 user_id", """
            SELECT COUNT(DISTINCT user_id) FROM ods_behavior
            WHERE user_id NOT IN (SELECT user_id FROM ods_user)
        """),
        ("ods_song 中不存在于 ods_artist 的 artist_id", """
            SELECT COUNT(DISTINCT artist_id) FROM ods_song
            WHERE artist_id NOT IN (SELECT artist_id FROM ods_artist)
        """),
    ]

    for desc, sql in checks:
        cursor.execute(sql)
        count = cursor.fetchone()[0]
        status = "✅" if count == 0 else "❌"
        print(f"  {status} {desc}: {count}")


def main():
    print("=" * 60)
    print("Step2 数据库建设 - 数据质量检查")
    print("=" * 60)

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            check_table_counts(cursor)
            check_referential_integrity(cursor)
    finally:
        conn.close()

    print("\n" + "=" * 60)
    print("数据库检查完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
