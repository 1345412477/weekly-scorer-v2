# ============================================
# 前端 Dockerfile - 多阶段构建
# ============================================

# --- 阶段1: 构建 ---
FROM node:20-alpine AS builder

WORKDIR /build

# 复制依赖文件
COPY package.json ./

# 安装依赖
RUN npm ci --no-optional

# 复制源码
COPY . .

# 构建生产版本
RUN npm run build

# --- 阶段2: Nginx 托管 ---
FROM nginx:1.25-alpine

# 复制构建产物
COPY --from=builder /build/dist /usr/share/nginx/html

# 复制 Nginx 配置
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
