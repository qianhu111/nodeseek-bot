# 使用轻量稳定基础镜像
FROM python:3.11-slim-bullseye

# 设置时区
ENV TZ=Asia/Shanghai

# 安装必要系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential gcc curl wget libffi-dev libssl-dev ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制代码
COPY main.py /app/main.py

# 更新 pip & 使用官方 PyPI 源 & 安装 Python 依赖
RUN python -m pip install --upgrade pip && \
    pip config set global.index-url https://pypi.org/simple && \
    pip install --no-cache-dir \
    "python-telegram-bot>=20,<21" \
    cloudscraper \
    requests \
    pytz

# 运行主程序
CMD ["python", "main.py"]
