# ── Stage 1: 构建前端 ──
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: 运行后端（含前端静态文件） ──
FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./

# 复制前端构建产物到后端期望的路径（backend/../frontend/dist → /frontend/dist）
COPY --from=frontend-builder /app/frontend/dist /frontend/dist

RUN mkdir -p /app/data /app/uploads /app/uploads/chat

ENV DATABASE_URL=sqlite+aiosqlite:////app/data/weekly_scorer.db
ENV DATA_DIR=/app/data
ENV TZ=Asia/Shanghai

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
