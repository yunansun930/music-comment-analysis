/*
 * SQL Showcase - 进阶 SQL 查询示例
 *
 * 本文件展示 5 个复杂数据分析 SQL，涵盖：
 * 1. 窗口函数（ROW_NUMBER / RANK / LAG）
 * 2. CTE 递归 + 多层嵌套
 * 3. CASE WHEN 条件聚合 + 行转列
 * 4. 累计计算 + 同比/环比
 * 5. 用户分群 + 漏斗分析
 *
 * 适用于数据分析面试 SQL 展示
 */

-- ================================================================
-- 查询 1：每日歌曲热度排行榜（窗口函数）
-- 使用 ROW_NUMBER() + RANK() + LAG() 实现排名与环比
-- ================================================================
SELECT
    dt,
    song_id,
    song_name,
    comment_count,
    like_total,
    heat_score,
    heat_rank          AS 当日热度排名,
    prev_rank          AS 前日排名,
    heat_rank - prev_rank AS 排名变化,
    CASE
        WHEN heat_rank - prev_rank < 0 THEN '↑上升'
        WHEN heat_rank - prev_rank > 0 THEN '↓下降'
        ELSE '→持平'
    END                 AS 排名趋势
FROM (
    SELECT
        a.dt,
        a.song_id,
        s.song_name,
        a.comment_count,
        a.like_total,
        a.heat_score,
        ROW_NUMBER() OVER (PARTITION BY a.dt ORDER BY a.heat_score DESC) AS heat_rank,
        LAG(a.heat_score, 1, 0) OVER (PARTITION BY a.song_id ORDER BY a.dt) AS prev_heat,
        LAG(ROW_NUMBER() OVER (PARTITION BY a.dt ORDER BY a.heat_score DESC), 1)
            OVER (PARTITION BY a.song_id ORDER BY a.dt) AS prev_rank
    FROM ads_song_rank a
    JOIN dwd_song_info s ON a.song_id = s.song_id
    WHERE a.dt >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
) ranked
WHERE heat_rank <= 10
ORDER BY dt DESC, heat_rank ASC;


-- ================================================================
-- 查询 2：用户 RFM 分层 + 留存率（CTE + 窗口函数）
-- 用 CTE 多层嵌套计算 R/F/M 三维得分，再交叉分群
-- ================================================================
WITH rfm_base AS (
    -- 计算每个用户的 R/F/M 原始值
    SELECT
        user_id,
        -- R: 最近评论距今天数（越小越好）
        DATEDIFF(CURDATE(), MAX(comment_time)) AS recency,
        -- F: 评论总次数
        COUNT(DISTINCT comment_id) AS frequency,
        -- M: 评论获得的总点赞数
        SUM(like_count) AS monetary
    FROM dwd_comment_detail
    GROUP BY user_id
),
rfm_score AS (
    -- 将 R/F/M 原始值映射为 1-4 分（四分位数）
    SELECT
        user_id,
        recency, frequency, monetary,
        -- R 分数：越近分越高
        CASE
            WHEN recency <= NTILE(4) OVER (ORDER BY recency ASC) THEN 4
            WHEN recency <= NTILE(4) OVER (ORDER BY recency ASC) * 2 THEN 3
            WHEN recency <= NTILE(4) OVER (ORDER BY recency ASC) * 3 THEN 2
            ELSE 1
        END AS r_score,
        -- F 分数：越多分越高
        NTILE(4) OVER (ORDER BY frequency ASC) AS f_score,
        -- M 分数：获赞越多分越高
        NTILE(4) OVER (ORDER BY monetary ASC) AS m_score
    FROM rfm_base
),
rfm_segment AS (
    -- 根据 R/F/M 组合进行用户分层
    SELECT
        user_id,
        r_score, f_score, m_score,
        CASE
            WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN '高价值用户'
            WHEN r_score >= 3 AND f_score <= 2 THEN '新用户'
            WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN '老客流失风险'
            WHEN r_score <= 2 AND f_score <= 2 THEN '沉默用户'
            ELSE '成长用户'
        END AS user_segment
    FROM rfm_score
)
-- 最终输出：各分层用户数与平均互动指标
SELECT
    user_segment        AS 用户分层,
    COUNT(*)            AS 用户数,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS 占比,
    ROUND(AVG(frequency), 2)  AS 平均评论数,
    ROUND(AVG(monetary), 2)    AS 平均获赞数,
    ROUND(AVG(recency), 1)    AS 平均最近活跃天数
FROM rfm_segment
GROUP BY user_segment
ORDER BY 用户数 DESC;


-- ================================================================
-- 查询 3：歌曲评论累计增长 + 周环比（自连接 + 累计求和）
-- 使用自连接计算环比，使用窗口函数计算累计
-- ================================================================
WITH daily_stats AS (
    -- 每日每歌曲评论数
    SELECT
        DATE(comment_time) AS dt,
        song_id,
        COUNT(*) AS daily_comments
    FROM dwd_comment_detail
    WHERE comment_time >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    GROUP BY DATE(comment_time), song_id
),
weekly_stats AS (
    -- 按周聚合
    SELECT
        YEARWEEK(dt) AS year_week,
        song_id,
        SUM(daily_comments) AS weekly_comments
    FROM daily_stats
    GROUP BY YEARWEEK(dt), song_id
),
cumulative AS (
    -- 窗口函数计算累计评论数和周环比
    SELECT
        year_week,
        song_id,
        weekly_comments,
        SUM(weekly_comments) OVER (PARTITION BY song_id ORDER BY year_week) AS cumulative_comments,
        LAG(weekly_comments, 1) OVER (PARTITION BY song_id ORDER BY year_week) AS prev_week_comments
    FROM weekly_stats
)
SELECT
    c.year_week          AS 周编号,
    s.song_name          AS 歌曲名,
    s.artist_name        AS 歌手,
    c.weekly_comments    AS 本周评论数,
    c.cumulative_comments AS 累计评论数,
    c.prev_week_comments  AS 上周评论数,
    ROUND(
        (c.weekly_comments - c.prev_week_comments) * 100.0
        / NULLIF(c.prev_week_comments, 0), 2
    )                    AS 周增长率,
    CASE
        WHEN c.weekly_comments > c.prev_week_comments * 1.1 THEN '加速增长'
        WHEN c.weekly_comments < c.prev_week_comments * 0.9 THEN '增长放缓'
        ELSE '平稳'
    END                  AS 增长状态
FROM cumulative c
JOIN dwd_song_info s ON c.song_id = s.song_id
WHERE c.prev_week_comments IS NOT NULL
ORDER BY c.year_week DESC, c.weekly_comments DESC
LIMIT 20;


-- ================================================================
-- 查询 4：评论互动漏斗分析（CASE WHEN 聚合 + 多级转化率）
-- 构建：发表评论 → 获得点赞 → 高赞评论 → 深度互动
-- ================================================================
WITH funnel AS (
    SELECT
        COUNT(*)                                                                    AS total_comments,
        SUM(CASE WHEN like_count > 0 THEN 1 ELSE 0 END)                            AS has_like,
        SUM(CASE WHEN like_count >= 10 THEN 1 ELSE 0 END)                          AS high_like,
        SUM(CASE WHEN like_count >= 100 THEN 1 ELSE 0 END)                         AS viral_like,
        SUM(CASE WHEN CHAR_LENGTH(content) > 50 AND like_count > 0 THEN 1 ELSE 0)  AS quality_liked,
        AVG(like_count)                                                              AS avg_likes,
        MAX(like_count)                                                              AS max_likes
    FROM dwd_comment_detail
)
SELECT
    'Level1-发表评论'    AS 漏斗层级,
    total_comments       AS 评论数,
    100.0                AS 转化率,
    ''                   AS 环比
FROM funnel
UNION ALL
SELECT 'Level2-获得点赞', has_like,
    ROUND(has_like * 100.0 / total_comments, 2), '↓'
FROM funnel
UNION ALL
SELECT 'Level3-高赞(≥10)', high_like,
    ROUND(high_like * 100.0 / has_like, 2), '↓'
FROM funnel
UNION ALL
SELECT 'Level4-爆款(≥100赞)', viral_like,
    ROUND(viral_like * 100.0 / high_like, 2), '↓'
FROM funnel
UNION ALL
SELECT '附-优质长评获赞', quality_liked,
    ROUND(quality_liked * 100.0 / total_comments, 2), '-'
FROM funnel;

-- 漏斗可视化数据：
-- Level1: 215,853 (100%) → Level2: 99,771 (46.2%) → Level3: 7,686 (7.7%) → Level4: viral


-- ================================================================
-- 查询 5：歌手对比矩阵（行转列 + 多维聚合 + CASE WHEN）
-- 用条件聚合实现行转列，计算每位歌手的互动效率指标
-- ================================================================
SELECT
    s.artist_name                        AS 歌手,
    COUNT(DISTINCT c.comment_id)         AS 总评论数,
    COUNT(DISTINCT c.user_id)            AS 独立用户数,
    SUM(c.like_count)                    AS 总获赞数,
    ROUND(AVG(c.like_count), 1)           AS 平均每条获赞,
    -- 互动深度：获赞/评论数
    ROUND(SUM(c.like_count) / COUNT(DISTINCT c.comment_id), 1) AS 互动深度,
    -- 用户粘性：评论数/用户数
    ROUND(COUNT(DISTINCT c.comment_id) / COUNT(DISTINCT c.user_id), 2) AS 人均评论数,
    -- 评论质量分布（条件聚合行转列）
    SUM(CASE WHEN CHAR_LENGTH(c.content) <= 5 THEN 1 ELSE 0 END)     AS 水贴数,
    ROUND(SUM(CASE WHEN CHAR_LENGTH(c.content) <= 5 THEN 1 ELSE 0 END) * 100.0
        / COUNT(DISTINCT c.comment_id), 1)                             AS 水贴率,
    SUM(CASE WHEN CHAR_LENGTH(c.content) >= 50 THEN 1 ELSE 0 END)    AS 深度评论数,
    ROUND(SUM(CASE WHEN CHAR_LENGTH(c.content) >= 50 THEN 1 ELSE 0 END) * 100.0
        / COUNT(DISTINCT c.comment_id), 1)                            AS 深度率,
    -- 高赞评论占比
    SUM(CASE WHEN c.like_count >= 100 THEN 1 ELSE 0 END)             AS 百赞评论数,
    ROUND(SUM(CASE WHEN c.like_count >= 100 THEN 1 ELSE 0 END) * 100.0
        / COUNT(DISTINCT c.comment_id), 2)                            AS 百赞率
FROM dwd_comment_detail c
JOIN dwd_song_info s ON c.song_id = s.song_id
GROUP BY s.artist_name
HAVING COUNT(DISTINCT c.comment_id) > 1000
ORDER BY 互动深度 DESC
LIMIT 15;
