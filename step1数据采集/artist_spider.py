"""
Step1 数据采集 - 歌手数据采集

负责：
1. 根据歌曲表中的 artist_id 去重
2. 调用网易云歌手接口获取歌手信息
3. 输出 dim_artist.csv
"""

import time

import pandas as pd

from config import API, LIMITS, OUTPUT
from utils import fetch_json, save_csv


def get_artist_detail(artist_id: int) -> dict:
    """
    获取歌手详情。
    接口：https://music.163.com/api/v1/artist/{artist_id}
    """
    url = API["artist"].format(artist_id=artist_id)
    return fetch_json(url) or {}


def parse_artist(raw: dict) -> dict:
    """
    将原始歌手数据解析为 dim_artist 字段格式。

    说明：
    - 网易云公开接口仅能稳定返回歌手 ID 和名称。
    - 性别、国籍、出道时间、粉丝数、类型、曲风等字段在公开接口中不稳定或缺失，
      因此暂不保留，避免空列干扰后续分析；如需使用可通过行为数据聚合衍生。
    """
    data = raw.get("data", raw)  # 兼容不同返回结构
    artist = data.get("artist", {}) if isinstance(data, dict) else {}
    return {
        "artist_id": artist.get("id"),
        "artist_name": artist.get("name"),
    }


def run_artist_spider(song_df: pd.DataFrame) -> pd.DataFrame:
    """
    执行歌手数据采集。

    参数：
        song_df: dim_song DataFrame，用于提取 artist_id
    """
    print("\n[Step1.2] 开始采集歌手数据...")
    artist_ids = song_df["artist_id"].dropna().unique().tolist()
    print(f"  -> 共 {len(artist_ids)} 个歌手需要去重采集")

    artists = []
    for idx, artist_id in enumerate(artist_ids, 1):
        raw = get_artist_detail(int(artist_id))
        if raw:
            artists.append(parse_artist(raw))
        if idx % 10 == 0:
            print(f"     已处理 {idx}/{len(artist_ids)} 个歌手...")
        time.sleep(LIMITS["request_delay"])

    df = pd.DataFrame(artists)
    save_csv(df, OUTPUT["dim_artist"])
    return df


if __name__ == "__main__":
    # 单独测试时需要先有 dim_song.csv
    song_df = pd.read_csv(OUTPUT["dim_song"])
    run_artist_spider(song_df)
