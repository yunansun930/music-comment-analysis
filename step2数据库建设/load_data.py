"""
Step2 数据库建设 - 加载 CSV 数据到 MySQL

运行命令：
    python load_data.py

说明：
- 将 step1数据采集/data/ 目录下的 CSV 文件加载到 ODS 层
- 然后从 ODS 层清洗写入 DWD 层
"""

import re

import numpy as np
import pandas as pd
import pymysql

from config import CSV_TABLE_MAP, DB_CONFIG, STEP1_DATA_DIR


_TABLE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_table_name(table_name: str) -> None:
    """校验表名仅包含字母、数字、下划线，防止 SQL 注入。"""
    if not isinstance(table_name, str) or not _TABLE_NAME_RE.match(table_name):
        raise ValueError(f"非法表名: {table_name}")


def get_connection():
    """获取 MySQL 连接。"""
    return pymysql.connect(**DB_CONFIG)


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """清理 DataFrame，将 NaN/NaT 替换为 None，便于 MySQL 插入。"""
    df = df.replace({np.nan: None})
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = df[col].where(df[col].notna(), None)
    return df


def load_csv_to_mysql(csv_name: str, table_name: str, batch_size: int = 2000):
    """将单个 CSV 文件分批加载到指定 MySQL 表。"""
    _validate_table_name(table_name)
    csv_path = STEP1_DATA_DIR / csv_name
    if not csv_path.exists():
        print(f"[Warning] 文件不存在，跳过: {csv_path}")
        return

    df = pd.read_csv(csv_path, encoding="utf-8-sig")
    df = clean_dataframe(df)

    if df.empty:
        print(f"[Warning] 数据为空，跳过: {csv_name}")
        return

    rows = [tuple(row) for row in df.values]
    total = len(rows)

    columns = ", ".join([f"`{c}`" for c in df.columns])
    placeholders = ", ".join(["%s"] * len(df.columns))
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    # 先清空表，保证幂等
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(f"TRUNCATE TABLE {table_name}")
            conn.commit()

            for i in range(0, total, batch_size):
                batch = rows[i : i + batch_size]
                cursor.executemany(sql, batch)
                conn.commit()
                print(f"  [{table_name}] 已写入 {min(i + batch_size, total)}/{total} 条")

            print(f"[OK] {csv_name} -> {table_name}: {total} rows")
    finally:
        conn.close()


def load_ods_data():
    """加载所有 CSV 到 ODS 层。"""
    print("\n[Step2.1] 加载数据到 ODS 层...")
    for csv_name, (_, table_name) in CSV_TABLE_MAP.items():
        load_csv_to_mysql(csv_name, table_name)


def ods_to_dwd():
    """将 ODS 数据清洗后写入 DWD 层。"""
    print("\n[Step2.2] ODS -> DWD 数据清洗写入...")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # 清洗写入 dwd_song_info
            cursor.execute("""
                INSERT INTO dwd_song_info
                    (song_id, song_name, artist_id, artist_name, album, category,
                     duration, release_time, language, tags)
                SELECT
                    song_id,
                    TRIM(song_name),
                    artist_id,
                    TRIM(artist_name),
                    TRIM(album),
                    NULLIF(TRIM(category), ''),
                    duration,
                    release_time,
                    NULLIF(TRIM(language), ''),
                    NULLIF(TRIM(tags), '')
                FROM ods_song
                WHERE song_id IS NOT NULL
                ON DUPLICATE KEY UPDATE
                    song_name = VALUES(song_name),
                    artist_id = VALUES(artist_id),
                    artist_name = VALUES(artist_name),
                    album = VALUES(album),
                    category = VALUES(category),
                    duration = VALUES(duration),
                    release_time = VALUES(release_time),
                    language = VALUES(language),
                    tags = VALUES(tags)
            """)
            print(f"[OK] dwd_song_info: {cursor.rowcount} rows")

            # 清洗写入 dwd_artist_info
            cursor.execute("""
                INSERT INTO dwd_artist_info (artist_id, artist_name)
                SELECT artist_id, TRIM(artist_name)
                FROM ods_artist
                WHERE artist_id IS NOT NULL
                ON DUPLICATE KEY UPDATE artist_name = VALUES(artist_name)
            """)
            print(f"[OK] dwd_artist_info: {cursor.rowcount} rows")

            # 清洗写入 dwd_user_info
            cursor.execute("""
                INSERT INTO dwd_user_info
                    (user_id, nickname, level, gender, age_group, register_time, province, city)
                SELECT
                    user_id,
                    NULLIF(TRIM(nickname), ''),
                    level,
                    gender,
                    NULLIF(TRIM(age_group), ''),
                    register_time,
                    province,
                    city
                FROM ods_user
                WHERE user_id IS NOT NULL
                ON DUPLICATE KEY UPDATE
                    nickname = VALUES(nickname),
                    level = VALUES(level),
                    gender = VALUES(gender),
                    age_group = VALUES(age_group),
                    register_time = VALUES(register_time),
                    province = VALUES(province),
                    city = VALUES(city)
            """)
            print(f"[OK] dwd_user_info: {cursor.rowcount} rows")

            # 清洗写入 dwd_comment_detail
            cursor.execute("""
                INSERT INTO dwd_comment_detail
                    (comment_id, song_id, user_id, content, like_count, reply_count, comment_time)
                SELECT
                    comment_id,
                    song_id,
                    user_id,
                    TRIM(content),
                    COALESCE(like_count, 0),
                    COALESCE(reply_count, 0),
                    comment_time
                FROM ods_comment
                WHERE comment_id IS NOT NULL
                  AND song_id IS NOT NULL
                  AND user_id IS NOT NULL
                ON DUPLICATE KEY UPDATE
                    content = VALUES(content),
                    like_count = VALUES(like_count),
                    reply_count = VALUES(reply_count),
                    comment_time = VALUES(comment_time)
            """)
            print(f"[OK] dwd_comment_detail: {cursor.rowcount} rows")

            conn.commit()
    finally:
        conn.close()

    # 清洗写入 dwd_behavior_detail：数据量大，用 Python 分批处理避免单条 SQL 卡住
    _load_behavior_to_dwd()


def _load_behavior_to_dwd(batch_size: int = 10000):
    """从 ods_behavior 读取并清洗写入 dwd_behavior_detail（使用游标分批，避免 OFFSET 变慢）。"""
    print("\n  [dwd_behavior_detail] 开始分批清洗写入...")

    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE dwd_behavior_detail")
            conn.commit()

            total_sql = "SELECT COUNT(*) FROM ods_behavior"
            cursor.execute(total_sql)
            total = cursor.fetchone()[0]

            columns = ["behavior_id", "user_id", "song_id", "behavior_type",
                       "behavior_time", "session_id", "device", "source"]
            col_str = ", ".join([f"`{c}`" for c in columns])
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f"INSERT INTO dwd_behavior_detail ({col_str}) VALUES ({placeholders})"

            # 使用 last_id 游标代替 OFFSET，大数据量下不会变慢
            last_id = ""
            inserted = 0
            while True:
                cursor.execute(f"""
                    SELECT behavior_id, user_id, song_id, behavior_type,
                           behavior_time, session_id, device, source
                    FROM ods_behavior
                    WHERE behavior_id > %s
                    ORDER BY behavior_id
                    LIMIT {batch_size}
                """, (last_id,))
                rows = cursor.fetchall()
                if not rows:
                    break

                cleaned = []
                for row in rows:
                    behavior_id, user_id, song_id, behavior_type, behavior_time, session_id, device, source = row
                    cleaned.append((
                        behavior_id,
                        user_id,
                        song_id,
                        behavior_type.strip() if behavior_type else behavior_type,
                        behavior_time,
                        session_id.strip() if session_id else session_id,
                        device.strip() if device else device,
                        source.strip() if source else source,
                    ))

                cursor.executemany(insert_sql, cleaned)
                conn.commit()
                inserted += len(cleaned)
                last_id = cleaned[-1][0]
                print(f"  [dwd_behavior_detail] 已写入 {inserted}/{total} 条", flush=True)

            print(f"[OK] dwd_behavior_detail: {inserted} rows")
    finally:
        conn.close()


def main():
    print("=" * 60)
    print("Step2 数据库建设 - 加载 CSV 数据")
    print("=" * 60)

    load_ods_data()
    ods_to_dwd()

    print("\n" + "=" * 60)
    print("CSV 数据加载完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
