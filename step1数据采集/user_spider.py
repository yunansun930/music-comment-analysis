"""
Step1 数据采集 - 用户数据采集

负责：
1. 根据评论表中的 user_id 去重
2. 调用网易云用户详情接口获取用户信息
3. 输出 dim_user.csv

注意：
- 网易云音乐用户详情接口有较高的反爬限制，如果无法获取全部用户，
  可先从评论中提取 user_id + nickname 作为基础用户数据，后续分析仍可进行。
"""

import time

import pandas as pd

from config import API, LIMITS, OUTPUT
from utils import fetch_json, ms_to_datetime, save_csv


def get_user_detail(user_id: int) -> dict:
    """
    获取用户详情。
    接口：https://music.163.com/api/v1/user/detail/{user_id}
    """
    url = API["user_detail"].format(user_id=user_id)
    return fetch_json(url) or {}


def parse_user_from_comment(user_id, nickname: str) -> dict:
    """从评论中解析出最基础的用户信息。"""
    return {
        "user_id": user_id,
        "nickname": nickname,
        "level": None,
        "gender": None,
        "age_group": None,
        "register_time": None,
        "province": None,
        "city": None,
    }


def parse_user_detail(raw: dict) -> dict:
    """解析用户详情接口返回的数据。"""
    profile = raw.get("profile", {})
    return {
        "user_id": profile.get("userId"),
        "nickname": profile.get("nickname"),
        "level": raw.get("level"),
        "gender": profile.get("gender"),  # 0=保密, 1=男, 2=女
        "age_group": None,
        "register_time": ms_to_datetime(profile.get("createTime")),
        "province": profile.get("province"),
        "city": profile.get("city"),
    }


def run_user_spider(comment_df: pd.DataFrame) -> pd.DataFrame:
    """
    执行用户数据采集。

    参数：
        comment_df: fact_comment DataFrame，用于提取 user_id 和 nickname
    """
    print("\n[Step1.4] 开始采集用户数据...")

    # 先从评论中提取用户基础信息（使用评论接口返回的真实 nickname）
    if "user_nickname" in comment_df.columns:
        base_users = (
            comment_df[["user_id", "user_nickname"]]
            .rename(columns={"user_nickname": "nickname"})
            .groupby("user_id")
            .first()
            .reset_index()
        )
    else:
        # 兼容旧数据：如果没有 nickname 列，则留空
        base_users = (
            comment_df[["user_id"]]
            .drop_duplicates()
            .assign(nickname=None)
        )
    print(f"  -> 从评论中提取到 {len(base_users)} 个用户")

    # 尝试补充用户详情（可能部分被限制）
    enriched_users = []
    for idx, row in base_users.iterrows():
        user_id = row["user_id"]
        raw = get_user_detail(int(user_id))
        if raw and raw.get("code") == 200:
            enriched_users.append(parse_user_detail(raw))
        else:
            enriched_users.append(parse_user_from_comment(user_id, row["nickname"]))

        if (idx + 1) % 20 == 0:
            print(f"     已处理 {idx + 1}/{len(base_users)} 个用户...")
        time.sleep(LIMITS["request_delay"])

    df = pd.DataFrame(enriched_users)
    save_csv(df, OUTPUT["dim_user"])
    return df


if __name__ == "__main__":
    comment_df = pd.read_csv(OUTPUT["fact_comment"])
    run_user_spider(comment_df)
