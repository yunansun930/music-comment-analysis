"""
Step1 数据采集 - 主入口

运行命令：
    python run.py

流程：
    1. 采集歌曲 -> dim_song.csv
    2. 采集歌手 -> dim_artist.csv
    3. 采集评论 -> fact_comment.csv
    4. 采集用户 -> dim_user.csv
    5. 生成行为 -> fact_behavior.csv

注意事项：
- 本脚本会访问网易云音乐公开接口，请保持礼貌的请求频率。
- 如遇反爬限制（如 403/503），可适当增大 config.py 中的 request_delay，
  或分多次运行各个子模块。
"""

import sys

from song_spider import run_song_spider
from artist_spider import run_artist_spider
from comment_spider import run_comment_spider
from user_spider import run_user_spider
from behavior_generator import run_behavior_generator


def main():
    print("=" * 60)
    print("音乐平台用户行为洞察系统 - Step1 数据采集")
    print("=" * 60)

    try:
        # 1. 歌曲
        song_df = run_song_spider()
        if song_df.empty:
            print("[Error] 未采集到歌曲数据，请检查网络或接口可用性。")
            sys.exit(1)

        # 2. 歌手
        run_artist_spider(song_df)

        # 3. 评论
        comment_df = run_comment_spider(song_df)
        if comment_df.empty:
            print("[Warning] 未采集到评论数据，将跳过用户和行为数据生成。")
            sys.exit(0)

        # 4. 用户
        user_df = run_user_spider(comment_df)

        # 5. 行为
        run_behavior_generator(song_df, user_df, comment_df)

        print("\n" + "=" * 60)
        print("Step1 数据采集完成，所有文件已保存到 data/ 目录")
        print("=" * 60)

    except KeyboardInterrupt:
        print("\n[Interrupted] 用户手动中断。")
    except Exception as e:
        print(f"\n[Error] 运行过程中发生异常: {e}")
        raise


if __name__ == "__main__":
    main()
