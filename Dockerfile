# 音乐评论用户行为分析 - 应用容器化
# 改进点：消除本地环境差异，提供一键启动 Dashboard
#
# 构建：docker build -t music-analysis-dashboard .
# 运行：docker run -p 8501:8501 --env-file .env music-analysis-dashboard

FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖（MySQL 客户端编译需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 先复制 requirements 利用 Docker 缓存
COPY step8可视化展示/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY step8可视化展示/ ./app/

WORKDIR /app

EXPOSE 8501

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# 通过环境变量注入数据库配置，避免密码硬编码
ENV DB_HOST=localhost \
    DB_PORT=3306 \
    DB_USER=root \
    DB_PASSWORD="" \
    DB_NAME=music_analysis

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
