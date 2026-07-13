#!/bin/bash
# 智友辰评分系统 Docker 部署脚本
# 目标服务器: 192.168.1.119
# 用户名: zyc-lmt

set -e

echo "=========================================="
echo "  智友辰评分系统 - Docker 部署"
echo "=========================================="

# 1. 构建 Docker 镜像
echo ""
echo "[1/4] 构建 Docker 镜像..."
docker compose build

# 2. 停止旧容器
echo ""
echo "[2/4] 停止旧容器..."
docker compose down || true

# 3. 启动新容器
echo ""
echo "[3/4] 启动新容器..."
docker compose up -d

# 4. 查看状态
echo ""
echo "[4/4] 检查服务状态..."
docker compose ps

echo ""
echo "=========================================="
echo "  部署完成！"
echo "  访问地址: http://192.168.1.119"
echo "  健康检查: http://192.168.1.119/health"
echo "=========================================="
