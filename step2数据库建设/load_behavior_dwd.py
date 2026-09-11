"""
Step2 数据库建设 - 单独加载 dwd_behavior_detail

使用场景：
- ODS 层其他表已经加载完成
- 只需要把 ods_behavior 清洗写入 dwd_behavior_detail

运行命令（推荐在终端执行，实时显示进度）：
    python -u load_behavior_dwd.py
"""

import sys

# 复用 load_data.py 中的函数
from load_data import _load_behavior_to_dwd


def main():
    print("=" * 60)
    print("Step2 数据库建设 - 单独加载 dwd_behavior_detail")
    print("=" * 60)

    _load_behavior_dwd(batch_size=10000)

    print("\n" + "=" * 60)
    print("dwd_behavior_detail 加载完成")
    print("=" * 60)


def _load_behavior_dwd(batch_size: int = 10000):
    """从 ods_behavior 读取并清洗写入 dwd_behavior_detail（使用游标分批）。"""
    print("\n  [dwd_behavior_detail] 开始分批清洗写入...")

    from load_data import get_connection

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


if __name__ == "__main__":
    main()
