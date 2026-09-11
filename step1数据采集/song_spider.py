"""
Step1 数据采集 - 歌曲数据采集

负责：
1. 根据关键词调用网易云搜索接口获取歌曲列表
2. 调用歌曲详情接口补全歌曲字段
3. 输出 dim_song.csv
"""

import time
from typing import List

import pandas as pd

from config import API, LIMITS, OUTPUT
from utils import fetch_json, ms_to_datetime, save_csv, safe_get


def search_songs(keyword: str, limit: int = LIMITS["songs_per_keyword"]) -> List[dict]:
    """
    根据关键词搜索歌曲。
    接口文档（公开分析）：https://music.163.com/api/search/get/web
    """
    params = {
        "csrf_token": "",
        "hlpretag": "",
        "hlposttag": "",
        "s": keyword,
        "type": 1,       # 1=单曲
        "offset": 0,
        "total": "true",
        "limit": limit,
    }
    data = fetch_json(API["search"], params=params)
    if data is None:
        return []

    # 接口返回结构可能嵌套在 result.songs 下
    songs = safe_get(data, "result", "songs", default=[])
    if not songs:
        songs = safe_get(data, "result", default=[])
    return songs if isinstance(songs, list) else []


def get_song_detail(song_id: int) -> dict:
    """
    获取歌曲详情，用于补充专辑、时长等信息。
    """
    params = {
        "id": song_id,
        "ids": f"[{song_id}]",
    }
    data = fetch_json(API["song_detail"], params=params)
    songs = safe_get(data, "songs", default=[])
    return songs[0] if songs else {}


def parse_song(raw: dict) -> dict:
    """将原始歌曲数据解析为 dim_song 字段格式。"""
    artists = raw.get("artists", [])
    artist_id = artists[0]["id"] if artists else None
    artist_name = artists[0]["name"] if artists else None
    album = safe_get(raw, "album", "name", default="") or safe_get(raw, "al", "name", default="")

    # alias 字段是歌曲别名列表，元素为字符串
    alias_list = raw.get("alias", [])
    if isinstance(alias_list, list) and alias_list:
        category = ",".join([str(a) for a in alias_list if a]) or None
    else:
        category = None

    return {
        "song_id": raw.get("id"),
        "song_name": raw.get("name"),
        "artist_id": artist_id,
        "artist_name": artist_name,
        "album": album,
        "category": category,
        "duration": raw.get("duration") or safe_get(raw, "dt", default=None),
        "release_time": ms_to_datetime(safe_get(raw, "album", "publishTime", default=None)),
        "language": None,  # 网易云公开接口不直接返回语言，可在后续清洗阶段推断
        "tags": None,
    }


def run_song_spider() -> pd.DataFrame:
    """
    执行歌曲数据采集，返回 dim_song DataFrame。
    """
    print("\n[Step1.1] 开始采集歌曲数据...")
    all_raw_songs = []

    for keyword in LIMITS["search_keywords"]:
        print(f"  -> 搜索关键词: {keyword}")
        songs = search_songs(keyword)
        print(f"     获取到 {len(songs)} 首歌曲")
        all_raw_songs.extend(songs)
        time.sleep(LIMITS["request_delay"])

    # 按 song_id 去重
    unique_songs = {s["id"]: s for s in all_raw_songs if s.get("id")}
    print(f"  -> 去重后共 {len(unique_songs)} 首歌曲")

    parsed_songs = []
    for idx, raw in enumerate(unique_songs.values(), 1):
        # 如果搜索结果信息不全，尝试补全详情
        detail = get_song_detail(raw["id"])
        if detail:
            raw.update(detail)
        parsed_songs.append(parse_song(raw))
        if idx % 10 == 0:
            print(f"     已处理 {idx}/{len(unique_songs)} 首...")
        time.sleep(0.5)

    df = pd.DataFrame(parsed_songs)
    save_csv(df, OUTPUT["dim_song"])
    return df


if __name__ == "__main__":
    run_song_spider()
