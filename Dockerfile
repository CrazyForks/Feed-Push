FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY telegram_rss_bot.py .

# 创建数据目录
RUN mkdir -p data

# 设置环境变量默认值
ENV TELEGRAM_BOT_TOKEN=""
ENV ROOT_ID=""
ENV WHITELIST_GROUP_ID=""
ENV ENABLE_GROUP_VERIFY="false"
ENV UPDATE_INTERVAL="300"

# 运行应用
CMD ["python", "telegram_rss_bot.py"]
