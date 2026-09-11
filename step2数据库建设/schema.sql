-- ============================================================
-- 音乐平台用户行为洞察系统 - Step2 数据库建设
-- MySQL 数据仓库分层建表 SQL
-- ============================================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS music_analysis
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE music_analysis;

-- ============================================================
-- ODS 层：贴源层，结构与 CSV 保持一致
-- ============================================================

DROP TABLE IF EXISTS ods_song;
CREATE TABLE ods_song (
    song_id       BIGINT COMMENT '歌曲ID',
    song_name     VARCHAR(255) COMMENT '歌曲名称',
    artist_id     BIGINT COMMENT '歌手ID',
    artist_name   VARCHAR(128) COMMENT '歌手名称',
    album         VARCHAR(255) COMMENT '专辑名称',
    category      VARCHAR(64) COMMENT '歌曲类型/风格',
    duration      INT COMMENT '歌曲时长（秒）',
    release_time  DATETIME COMMENT '发布时间',
    language      VARCHAR(32) COMMENT '语言',
    tags          VARCHAR(500) COMMENT '标签',
    load_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据加载时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ODS-歌曲贴源表';

DROP TABLE IF EXISTS ods_artist;
CREATE TABLE ods_artist (
    artist_id     BIGINT COMMENT '歌手ID',
    artist_name   VARCHAR(128) COMMENT '歌手名称',
    load_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据加载时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ODS-歌手贴源表';

DROP TABLE IF EXISTS ods_user;
CREATE TABLE ods_user (
    user_id       BIGINT COMMENT '用户ID',
    nickname      VARCHAR(128) COMMENT '昵称',
    level         INT COMMENT '用户等级',
    gender        TINYINT COMMENT '性别：0保密，1男，2女',
    age_group     VARCHAR(16) COMMENT '年龄段',
    register_time DATETIME COMMENT '注册时间',
    province      BIGINT COMMENT '省份编码',
    city          BIGINT COMMENT '城市编码',
    load_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据加载时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ODS-用户贴源表';

DROP TABLE IF EXISTS ods_comment;
CREATE TABLE ods_comment (
    comment_id    BIGINT COMMENT '评论ID',
    song_id       BIGINT COMMENT '歌曲ID',
    user_id       BIGINT COMMENT '用户ID',
    user_nickname VARCHAR(128) COMMENT '用户昵称（冗余字段，用于构建dim_user）',
    content       TEXT COMMENT '评论内容',
    like_count    INT COMMENT '点赞数',
    reply_count   INT COMMENT '回复数',
    comment_time  DATETIME COMMENT '评论时间',
    load_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据加载时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ODS-评论贴源表';

DROP TABLE IF EXISTS ods_behavior;
CREATE TABLE ods_behavior (
    behavior_id   VARCHAR(64) COMMENT '行为ID',
    user_id       BIGINT COMMENT '用户ID',
    song_id       BIGINT COMMENT '歌曲ID',
    behavior_type VARCHAR(32) COMMENT '行为类型：play/like/collect/comment/share',
    behavior_time DATETIME COMMENT '行为时间',
    session_id    VARCHAR(64) COMMENT '会话ID',
    device        VARCHAR(32) COMMENT '设备类型',
    source        VARCHAR(64) COMMENT '流量来源',
    load_time     DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据加载时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ODS-行为贴源表';

-- ============================================================
-- DWD 层：明细层，清洗后的标准表
-- ============================================================

DROP TABLE IF EXISTS dwd_song_info;
CREATE TABLE dwd_song_info (
    song_id       BIGINT PRIMARY KEY COMMENT '歌曲ID',
    song_name     VARCHAR(255) NOT NULL COMMENT '歌曲名称',
    artist_id     BIGINT COMMENT '歌手ID',
    artist_name   VARCHAR(128) COMMENT '歌手名称',
    album         VARCHAR(255) COMMENT '专辑名称',
    category      VARCHAR(64) COMMENT '歌曲类型/风格',
    duration      INT COMMENT '歌曲时长（秒）',
    release_time  DATETIME COMMENT '发布时间',
    language      VARCHAR(32) COMMENT '语言',
    tags          VARCHAR(500) COMMENT '标签',
    etl_time      DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据清洗时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='DWD-歌曲信息明细表';

DROP TABLE IF EXISTS dwd_artist_info;
CREATE TABLE dwd_artist_info (
    artist_id     BIGINT PRIMARY KEY COMMENT '歌手ID',
    artist_name   VARCHAR(128) NOT NULL COMMENT '歌手名称',
    etl_time      DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据清洗时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='DWD-歌手信息明细表';

DROP TABLE IF EXISTS dwd_user_info;
CREATE TABLE dwd_user_info (
    user_id       BIGINT PRIMARY KEY COMMENT '用户ID',
    nickname      VARCHAR(128) COMMENT '昵称',
    level         INT COMMENT '用户等级',
    gender        TINYINT COMMENT '性别：0保密，1男，2女',
    age_group     VARCHAR(16) COMMENT '年龄段',
    register_time DATETIME COMMENT '注册时间',
    province      BIGINT COMMENT '省份编码',
    city          BIGINT COMMENT '城市编码',
    etl_time      DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据清洗时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='DWD-用户信息明细表';

DROP TABLE IF EXISTS dwd_comment_detail;
CREATE TABLE dwd_comment_detail (
    comment_id    BIGINT PRIMARY KEY COMMENT '评论ID',
    song_id       BIGINT NOT NULL COMMENT '歌曲ID',
    user_id       BIGINT NOT NULL COMMENT '用户ID',
    content       TEXT COMMENT '评论内容',
    like_count    INT DEFAULT 0 COMMENT '点赞数',
    reply_count   INT DEFAULT 0 COMMENT '回复数',
    comment_time  DATETIME NOT NULL COMMENT '评论时间',
    etl_time      DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据清洗时间',
    KEY idx_song_id (song_id),
    KEY idx_user_id (user_id),
    KEY idx_comment_time (comment_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='DWD-评论明细表';

DROP TABLE IF EXISTS dwd_behavior_detail;
CREATE TABLE dwd_behavior_detail (
    behavior_id   VARCHAR(64) PRIMARY KEY COMMENT '行为ID',
    user_id       BIGINT NOT NULL COMMENT '用户ID',
    song_id       BIGINT NOT NULL COMMENT '歌曲ID',
    behavior_type VARCHAR(32) NOT NULL COMMENT '行为类型',
    behavior_time DATETIME NOT NULL COMMENT '行为时间',
    session_id    VARCHAR(64) COMMENT '会话ID',
    device        VARCHAR(32) COMMENT '设备类型',
    source        VARCHAR(64) COMMENT '流量来源',
    etl_time      DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据清洗时间',
    KEY idx_user_id (user_id),
    KEY idx_song_id (song_id),
    KEY idx_behavior_time (behavior_time),
    KEY idx_behavior_type (behavior_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='DWD-行为明细表';

-- ============================================================
-- DWS 层：服务层，按日聚合的指标表
-- ============================================================

DROP TABLE IF EXISTS dws_song_daily;
CREATE TABLE dws_song_daily (
    dt                  DATE NOT NULL COMMENT '日期',
    song_id             BIGINT NOT NULL COMMENT '歌曲ID',
    comment_count       INT DEFAULT 0 COMMENT '歌曲日评论数',
    reply_count         INT DEFAULT 0 COMMENT '歌曲日回复数',
    like_total          INT DEFAULT 0 COMMENT '歌曲日评论获赞数',
    comment_user_count  INT DEFAULT 0 COMMENT '歌曲日评论用户数',
    heat_score          DECIMAL(10,4) DEFAULT 0 COMMENT '热度分数',
    comment_growth_rate DECIMAL(10,4) DEFAULT 0 COMMENT '评论数增长率',
    reply_growth_rate   DECIMAL(10,4) DEFAULT 0 COMMENT '回复数增长率',
    update_time         DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (dt, song_id),
    KEY idx_song_id (song_id),
    KEY idx_heat_score (dt, heat_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='DWS-歌曲日评论指标表';

DROP TABLE IF EXISTS dws_user_daily;
CREATE TABLE dws_user_daily (
    dt                  DATE NOT NULL COMMENT '日期',
    user_id             BIGINT NOT NULL COMMENT '用户ID',
    comment_count       INT DEFAULT 0 COMMENT '用户日评论数',
    reply_count         INT DEFAULT 0 COMMENT '用户日回复数',
    like_received       INT DEFAULT 0 COMMENT '用户日评论获赞数',
    active_song_num     INT DEFAULT 0 COMMENT '评论歌曲数',
    avg_comment_length  DECIMAL(10,2) DEFAULT 0 COMMENT '平均评论字数',
    update_time         DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (dt, user_id),
    KEY idx_user_id (user_id),
    KEY idx_dt (dt)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='DWS-用户日评论指标表';

DROP TABLE IF EXISTS dws_artist_daily;
CREATE TABLE dws_artist_daily (
    dt            DATE NOT NULL COMMENT '日期',
    artist_id     BIGINT NOT NULL COMMENT '歌手ID',
    comment_count INT DEFAULT 0 COMMENT '歌手日评论数',
    reply_count   INT DEFAULT 0 COMMENT '歌手日回复数',
    like_total    INT DEFAULT 0 COMMENT '歌手日评论获赞数',
    update_time   DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (dt, artist_id),
    KEY idx_artist_id (artist_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='DWS-歌手日评论指标表';

-- ============================================================
-- ADS 层：应用层，面向分析主题
-- ============================================================

DROP TABLE IF EXISTS ads_song_rank;
CREATE TABLE ads_song_rank (
    dt              DATE NOT NULL COMMENT '日期',
    song_id         BIGINT NOT NULL COMMENT '歌曲ID',
    heat_rank       INT COMMENT '热度排名',
    heat_score      DECIMAL(10,4) DEFAULT 0 COMMENT '热度分数',
    comment_count   INT DEFAULT 0 COMMENT '评论数',
    reply_count     INT DEFAULT 0 COMMENT '回复数',
    like_total      INT DEFAULT 0 COMMENT '评论获赞数',
    lifecycle_stage VARCHAR(32) COMMENT '生命周期阶段',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (dt, song_id),
    KEY idx_dt_rank (dt, heat_rank),
    KEY idx_song_id (song_id),
    KEY idx_lifecycle_stage (lifecycle_stage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-歌曲热度排名表';

DROP TABLE IF EXISTS ads_user_portrait;
CREATE TABLE ads_user_portrait (
    user_id             BIGINT PRIMARY KEY COMMENT '用户ID',
    cluster_label       INT COMMENT '聚类标签',
    user_type           VARCHAR(32) COMMENT '用户类型：核心粉丝/内容消费者/轻度用户',
    user_value          DECIMAL(10,4) DEFAULT 0 COMMENT '用户价值分',
    comment_count_total INT DEFAULT 0 COMMENT '总评论数',
    reply_count_total   INT DEFAULT 0 COMMENT '总回复数',
    like_received_total  INT DEFAULT 0 COMMENT '总评论获赞数',
    activity_score       DECIMAL(10,4) DEFAULT 0 COMMENT '活跃度',
    interaction_score    DECIMAL(10,4) DEFAULT 0 COMMENT '互动贡献',
    diversity_score      DECIMAL(10,4) DEFAULT 0 COMMENT '内容多样性',
    avg_sentiment        DECIMAL(10,4) DEFAULT 0 COMMENT '平均情感倾向(0-1)',
    preferred_topic_id   INT DEFAULT 0 COMMENT '偏好主题ID',
    active_period        VARCHAR(16) COMMENT '活跃时段：凌晨/上午/下午/晚上',
    sentiment_type       VARCHAR(16) COMMENT '情感标签：正面/中性/负面',
    update_time    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-用户评论画像表';

DROP TABLE IF EXISTS ads_song_lifecycle;
CREATE TABLE ads_song_lifecycle (
    dt              DATE NOT NULL COMMENT '日期',
    song_id         BIGINT NOT NULL COMMENT '歌曲ID',
    lifecycle_stage VARCHAR(32) COMMENT '生命周期阶段：冷启动/增长期/爆发期/衰退期',
    heat_score      DECIMAL(10,4) DEFAULT 0 COMMENT '热度分数',
    update_time     DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (dt, song_id),
    KEY idx_song_id (song_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ADS-歌曲生命周期表';
