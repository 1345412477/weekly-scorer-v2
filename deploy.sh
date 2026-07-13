#!/bin/bash
# 智友辰评分系统 Docker 部署脚本
# 目标服务器: 192.168.1.119
# 用户名: zyc-lmt
#
# 首次部署：
#   git clone https://gitee.com/yostore/weekly-scorer-v2.git
#   cd weekly-scorer-v2
#   cp .env.example .env   # 编辑 .env 填入配置
#   mkdir -p data uploads
#   chmod +x deploy.sh
#   ./deploy.sh
#
# 更新部署：
#   cd ~/weekly-scorer-v2
#   ./deploy.sh   # 自动拉取最新代码并重新部署

set -e

REPO_URL="https://gitee.com/yostore/weekly-scorer-v2.git"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  智友辰评分系统 - Docker 部署"
echo "=========================================="

# 0. 拉取最新代码
echo ""
echo "[0/5] 拉取最新代码..."
if [ -d "$PROJECT_DIR/.git" ]; then
    git pull origin master || echo "警告: 拉取代码失败，使用当前代码继续部署"
else
    echo "当前目录不是 Git 仓库，跳过拉取"
fi

# 1. 构建 Docker 镜像
echo ""
echo "[1/5] 构建 Docker 镜像..."
docker compose build

# 2. 停止旧容器
echo ""
echo "[2/5] 停止旧容器..."
docker compose down || true

# 3. 启动新容器
echo ""
echo "[3/5] 启动新容器..."
docker compose up -d

# 4. 等待服务就绪
echo ""
echo "[4/5] 等待服务启动..."
for i in $(seq 1 15); do
    if curl -sf http://localhost/health > /dev/null 2>&1; then
        echo "服务已就绪"
        break
    fi
    if [ "$i" -eq 15 ]; then
        echo "警告: 服务启动超时，请检查日志"
    fi
    sleep 2
done

# 5. 查看状态
echo ""
echo "[5/5] 检查服务状态..."
docker compose ps

echo ""
echo "=========================================="
echo "  部署完成！"
echo "  访问地址: http://192.168.1.119"
echo "  健康检查: http://192.168.1.119/health"
echo "  仓库地址: $REPO_URL"
echo "=========================================="
