"""
Step1 数据采集 - 通用工具函数
"""

import json
import time
from typing import Any, Optional

import pandas as pd
import requests

from config import HEADERS, LIMITS


def fetch_json(
    url: str,
    params: Optional[dict] = None,
    max_retries: int = LIMITS["max_retries"],
    delay: float = LIMITS["request_delay"],
) -> Optional[dict]:
    """
    发送 GET 请求并返回 JSON 数据。

    参数：
        url: 请求地址
        params: URL 查询参数
        max_retries: 最大重试次数
        delay: 基础重试间隔（会随重试指数递增）

    返回：
        请求成功返回 dict，失败返回 None
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=15,
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                print(f"[HTTP {resp.status_code}] {url} (attempt {attempt})")
        except Exception as e:
            print(f"[Request Error] {url} (attempt {attempt}): {e}")

        if attempt < max_retries:
            sleep_time = delay * attempt
            print(f"  -> {sleep_time}s 后重试...")
            time.sleep(sleep_time)

    return None


def save_csv(df: pd.DataFrame, path, mode: str = "w") -> None:
    """将 DataFrame 保存为 CSV（UTF-8-BOM，兼容 Excel 打开中文）。"""
    if df.empty:
        print(f"[Warning] 数据为空，跳过保存: {path}")
        return
    header = mode == "w"
    df.to_csv(path, index=False, mode=mode, header=header, encoding="utf-8-sig")
    print(f"[Saved CSV] {path} ({len(df)} rows)")


def save_json(data: Any, path) -> None:
    """将数据保存为 JSON 文件。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[Saved JSON] {path}")


def safe_get(data: dict, *keys, default=None):
    """安全地获取嵌套字典中的值。"""
    for key in keys:
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return default
    return data


def ms_to_datetime(ts) -> Optional[str]:
    """
    将毫秒时间戳转换为 MySQL 兼容的 datetime 字符串。

    参数：
        ts: 毫秒级时间戳，可为 int/float/str

    返回：
        格式化字符串 "%Y-%m-%d %H:%M:%S"，转换失败返回 None
    """
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return None
    try:
        return pd.to_datetime(int(ts), unit="ms").strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
