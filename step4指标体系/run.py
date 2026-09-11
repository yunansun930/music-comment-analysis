"""
Step4 指标体系 - 主运行入口

运行命令：
    python run.py
"""

import dws_song_daily
import dws_user_daily
import dws_artist_daily
import ads_song_metrics
import ads_user_portrait
import stat_tests


def main():
    print("=" * 60)
    print("Step4 指标体系建设")
    print("=" * 60)

    dws_song_daily.run()
    dws_user_daily.run()
    dws_artist_daily.run()
    ads_song_metrics.run()
    ads_user_portrait.run()
    stat_tests.run()

    print("\n" + "=" * 60)
    print("指标体系计算完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
