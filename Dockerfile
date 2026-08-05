# ── Stage 1: 构建前端 ──
FROM node:20-alpine AS frontend-builder
ARG NPM_REGISTRY=https://registry.npmmirror.com
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --registry="$NPM_REGISTRY" --no-audit --no-fund \
      --fetch-retries=5 --fetch-retry-mintimeout=10000 --fetch-retry-maxtimeout=120000 \
  || npm ci --registry=https://registry.npmjs.org --no-audit --no-fund \
      --fetch-retries=5 --fetch-retry-mintimeout=10000 --fetch-retry-maxtimeout=120000
COPY frontend/ ./
RUN npm run build

# ─ Stage 2: 运行后端（含前端静态文件） ──
FROM python:3.11-slim
WORKDIR /app

# 换用阿里云镜像加速 apt 和 pip
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true && \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com -r requirements.txt

COPY backend/ ./

# 复制前端构建产物到后端期望的路径（backend/../frontend/dist → /frontend/dist）
COPY --from=frontend-builder /app/frontend/dist /frontend/dist

RUN mkdir -p /app/data /app/uploads /app/uploads/chat

ENV TZ=Asia/Shanghai

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
