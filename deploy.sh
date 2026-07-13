#!/bin/bash
# 智友辰评分系统 服务器部署脚本
# 目标服务器: 192.168.1.119
# 部署目录: /home/zyc-lmt/web/weekly-scorer-v2
# 数据库: PostgreSQL (端口 5433)
#
# 首次部署：
#   cd /home/zyc-lmt/web
#   git clone https://gitee.com/yostore/weekly-scorer-v2.git
#   cd weekly-scorer-v2
#   cp .env.example .env   # 编辑 .env 填入配置
#   mkdir -p uploads
#   chmod +x deploy.sh
#   ./deploy.sh
#
# 更新部署：
#   cd /home/zyc-lmt/web/weekly-scorer-v2
#   ./deploy.sh   # 自动拉取最新代码并重新部署

set -e

REPO_URL="https://gitee.com/yostore/weekly-scorer-v2.git"
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DB_HOST="host.docker.internal"
DB_PORT="5433"
DB_USER="user_tScewp"
DB_NAME="weekly_scorer"

echo "=========================================="
echo "  智友辰评分系统 - 服务器部署"
echo "=========================================="
echo "部署目录: $PROJECT_DIR"
echo "代码仓库: $REPO_URL"
echo "=========================================="

# 0. 拉取最新代码
echo ""
echo "[0/6] 拉取最新代码..."
if [ -d "$PROJECT_DIR/.git" ]; then
    # 修复 remote URL（去掉用户名避免每次输密码，公开仓库无需认证）
    CURRENT_URL=$(git remote get-url origin 2>/dev/null)
    if echo "$CURRENT_URL" | grep -q "@gitee.com"; then
        FIXED_URL=$(echo "$CURRENT_URL" | sed 's/[^/]*@gitee.com/gitee.com/')
        git remote set-url origin "$FIXED_URL"
        echo "✓ 已修复 remote URL，去掉用户名认证"
    fi
    git pull origin master || echo "警告: 拉取代码失败，使用当前代码继续部署"
else
    echo "当前目录不是 Git 仓库，跳过拉取"
fi

# 1. 检查 PostgreSQL 连接
echo ""
echo "[1/6] 检查 PostgreSQL 数据库连接..."
if command -v psql &> /dev/null; then
    if PGPASSWORD="password_jaMRPK" psql -h localhost -p $DB_PORT -U $DB_USER -d $DB_NAME -c '\q' 2>/dev/null; then
        echo "✓ PostgreSQL 连接成功"
    else
        echo "✗ PostgreSQL 连接失败，请检查:"
        echo "  - 数据库服务是否运行"
        echo "  - 用户名/密码是否正确"
        echo "  - 数据库 '$DB_NAME' 是否存在"
        exit 1
    fi
else
    echo "⚠ 未安装 psql 客户端，跳过数据库连接检查"
    echo "  请确保 PostgreSQL 在端口 $DB_PORT 运行"
fi

# 2. 检查 .env 配置文件
echo ""
echo "[2/6] 检查环境配置..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "✗ .env 文件不存在"
    echo "请执行: cp .env.example .env && nano .env"
    exit 1
fi

# 验证关键配置
if ! grep -q "AUTH_SECRET_KEY=.*[^ ]" .env || grep -q "AUTH_SECRET_KEY=your-random-secret-key-here" .env; then
    echo "⚠ AUTH_SECRET_KEY 未配置或使用默认值，建议修改"
fi

if ! grep -q "ARK_API_KEY=.*[^ ]" .env || grep -q "ARK_API_KEY=your_ark_api_key_here" .env; then
    echo "⚠ ARK_API_KEY 未配置，AI 评分功能将不可用"
fi

echo "✓ 环境配置检查完成"

# 3. 构建 Docker 镜像
echo ""
echo "[3/6] 构建 Docker 镜像..."
docker compose build --no-cache

# 4. 停止旧容器
echo ""
echo "[4/6] 停止旧容器..."
docker compose down || true

# 5. 启动新容器
echo ""
echo "[5/6] 启动新容器..."
docker compose up -d

# 6. 等待服务就绪
echo ""
echo "[6/6] 等待服务启动..."
MAX_WAIT=120
WAITED=0
while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -sf http://localhost:8081/health > /dev/null 2>&1; then
        echo "✓ 服务已就绪"
        break
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo "  等待中... ($WAITED/$MAX_WAIT 秒)"
done

if [ $WAITED -ge $MAX_WAIT ]; then
    echo "⚠ 服务启动超时，请检查日志:"
    echo "  docker compose logs"
    echo "  注：健康检查超时不代表启动失败，容器可能仍在初始化"
fi

# 显示状态
echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
docker compose ps
echo ""
echo "访问地址: http://192.168.1.119:8081"
echo "健康检查: http://192.168.1.119:8081/health"
echo "API 文档: http://192.168.1.119:8081/docs"
echo ""
echo "默认管理员账号:"
echo "  用户名: admin"
echo "  密码: admin123 (请及时修改)"
echo "=========================================="
