# ============================================================
# SecScan Dockerfile — 多阶段构建生产级镜像
# 策略：builder 阶段安装依赖 → runtime 阶段仅复制产物
# 安全：非 root 用户运行
# 健康：内置 HEALTHCHECK 指令
# ============================================================

# -------------------- 第一阶段：builder --------------------
FROM python:3.13-slim AS builder

# 设置工作目录
WORKDIR /build

# 仅复制依赖文件，利用 Docker 层缓存
# 只要 requirements.txt 不变，pip install 层就会被缓存
COPY requirements.txt .

# 创建虚拟环境，隔离依赖（避免与系统包冲突）
RUN python -m venv /opt/venv

# 激活虚拟环境并安装依赖
# --no-cache-dir 不保存 pip 缓存，减小镜像体积
# --upgrade pip 确保使用最新版 pip
RUN /opt/venv/bin/pip install --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# -------------------- 第二阶段：runtime --------------------
FROM python:3.13-slim AS runtime

# 设置环境变量
# PYTHONUNBUFFERED=1 禁用输出缓冲，日志实时输出
# PYTHONDONTWRITEBYTECODE=1 不生成 .pyc 文件
# PYTHONPATH 设置模块搜索路径
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# 安装 curl（HEALTHCHECK 需要）+ 清理 apt 缓存减小体积
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 从 builder 阶段复制虚拟环境（仅包含已安装的依赖）
COPY --from=builder /opt/venv /opt/venv

# 创建非 root 用户和组（安全最佳实践）
RUN groupadd -r secscan && useradd -r -g secscan -d /app -s /sbin/nologin secscan

# 设置工作目录
WORKDIR /app

# 复制应用代码（放在依赖安装之后，最大化层缓存命中）
COPY --chown=secscan:secscan . .

# 切换到非 root 用户
USER secscan

# 暴露端口
EXPOSE 8000

# 健康检查：每 30 秒请求一次 /health 端点
# --interval=30s 检查间隔
# --timeout=5s 单次检查超时
# --start-period=10s 容器启动后等待 10 秒再开始检查
# --retries=3 连续 3 次失败才标记为 unhealthy
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
