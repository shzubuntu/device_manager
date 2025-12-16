# Multi-stage build: build wheels in builder, produce minimal runtime image

FROM python:3.10-slim-bookworm AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
WORKDIR /wheels

# 替换为国内镜像源以提高 apt 下载速度（先清理旧的 sources.list.d）
RUN set -eux; \
    rm -rf /etc/apt/sources.list.d/*; \
    cat > /etc/apt/sources.list <<'EOF'
deb http://mirrors.aliyun.com/debian/ bookworm main contrib non-free
deb-src http://mirrors.aliyun.com/debian/ bookworm main contrib non-free
deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free
deb-src http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free
deb http://mirrors.aliyun.com/debian/ bookworm-updates main contrib non-free
deb-src http://mirrors.aliyun.com/debian/ bookworm-updates main contrib non-free
EOF

# 为 pip 配置国内镜像源，加快依赖下载（同时把 trusted-host 写入）
RUN set -eux; \
    mkdir -p /etc; \
    printf '[global]\nindex-url = https://mirrors.aliyun.com/pypi/simple/\ntrusted-host = mirrors.aliyun.com\n' > /etc/pip.conf

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      gcc \
      pkg-config \
      python3-dev \
      libmariadb-dev \
      libmariadb-dev-compat \
      ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 构建 wheel，避免在运行镜像中编译扩展（使用 pip.conf 中的镜像）
RUN pip wheel --no-cache-dir -r requirements.txt -w /wheels

# ---------------- runtime stage ----------------
FROM python:3.10-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
WORKDIR /app

# 替换为国内镜像源（先清理旧的 sources.list.d）
RUN set -eux; \
    rm -rf /etc/apt/sources.list.d/*; \
    cat > /etc/apt/sources.list <<'EOF'
deb http://mirrors.aliyun.com/debian/ bookworm main contrib non-free
deb-src http://mirrors.aliyun.com/debian/ bookworm main contrib non-free
deb http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free
deb-src http://mirrors.aliyun.com/debian-security bookworm-security main contrib non-free
deb http://mirrors.aliyun.com/debian/ bookworm-updates main contrib non-free
deb-src http://mirrors.aliyun.com/debian/ bookworm-updates main contrib non-free
EOF

# 同样为运行时设置 pip 源（以便 pip --upgrade pip 等命令也走镜像）
RUN set -eux; \
    mkdir -p /etc; \
    printf '[global]\nindex-url = https://mirrors.aliyun.com/pypi/simple/\ntrusted-host = mirrors.aliyun.com\n' > /etc/pip.conf

# 仅安装运行时必要的系统包，避免编译工具留在最终镜像
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      libmariadb3 \
      mariadb-client \
      ca-certificates \
      netcat-openbsd && \
    rm -rf /var/lib/apt/lists/*

# 使用预构建的 wheels 安装 Python 依赖（pip 会使用 /etc/pip.conf 指定的镜像）
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

# 复制应用代码（尽量精确复制以减少上下文体积）
COPY manage.py .
COPY device_manager/ device_manager/
COPY authentication/ authentication/
COPY devices/ devices/
COPY static/ static/
COPY templates/ templates/
COPY start.sh .


RUN mkdir -p /app/logs && chmod +x start.sh

# 创建非 root 用户并把应用目录归属给该用户（安全与兼容性）
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin -u 1000 app \
    && chown -R app:app /app 

USER app

# 在运行阶段执行 collectstatic（如果依赖环境变量，构建运行时可在启动流程执行）
# 捕获失败以避免构建失败（如果执行 collectstatic 需要运行时 env，可在容器启动脚本中执行）
# RUN python manage.py collectstatic --noinput || true

EXPOSE 8000

CMD ["bash", "start.sh"]
