FROM python:3.11-slim

LABEL maintainer="Lumina Team"
LABEL description="Lumina - 本地文件知识提取与结构化笔记生成系统"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制项目文件
COPY pyproject.toml requirements.txt ./
COPY src/ ./src/
COPY docs/ ./docs/
COPY examples/ ./examples/

# 安装 Python 依赖
RUN pip install --no-cache-dir -e .

# 创建数据目录
RUN mkdir -p /data/notes /data/cache /data/history /data/vector_store

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV LUMINA_DATA_DIR=/data
ENV LUMINA_LOG_LEVEL=INFO

# 暴露端口
EXPOSE 5088

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from lumina.health_check import get_health_status; import json; status = get_health_status(); print(json.dumps(status, indent=2)); exit(0 if status['status'] == 'healthy' else 1)"

# 启动命令
CMD ["lumina", "serve", "--host", "0.0.0.0", "--port", "5088"]
