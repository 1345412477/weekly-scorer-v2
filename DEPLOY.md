# 周报评分系统 v2 - 部署与运维指南

## 一、系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose                          │
├─────────────────────────────────────────────────────────────┤
│  ─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   Nginx     │  │   Backend   │  │    PostgreSQL       │ │
│  │  (前端静态)  │──│  (FastAPI)  │──│   (主数据库)        │ │
│  │   Port 80   │  │  Port 8000  │  │   Port 5432         │ │
│  └─────────────┘  └──────┬──────┘  └─────────────────────┘ │
│                          │                                    │
│                   ┌──────┴──────┐                            │
│                   │    Redis    │                            │
│                   │  (缓存层)   │                            │
│                   │  Port 6379  │                            │
│                   └─────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

## 二、Docker 部署策略

### 2.1 目录结构

```
weekly-scorer-v2/
├── backend/
│   ├── Dockerfile          # 后端镜像
│   ├── requirements.txt
│   ── app/
├── frontend/
│   ├── Dockerfile          # 前端镜像
│   ├── nginx.conf          # Nginx 配置
│   └── src/
├── docker-compose.yml      # 编排文件
├── .env.example            # 环境变量模板
├── .dockerignore
├── init.sql                # PostgreSQL 初始化脚本
└── scripts/
    └── migrate_sqlite_to_pg.py  # 数据迁移脚本
```

### 2.2 部署步骤

#### 步骤 1: 准备服务器环境

```bash
# 安装 Docker 和 Docker Compose
curl -fsSL https://get.docker.com | sh
sudo systemctl enable docker
sudo systemctl start docker

# 安装 Docker Compose (如未自带)
sudo apt-get install docker-compose-plugin
```

#### 步骤 2: 克隆项目并配置

```bash
git clone <your-repo-url> weekly-scorer-v2
cd weekly-scorer-v2

# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，修改以下关键配置:
# - DB_PASSWORD: 数据库密码（强密码）
# - AUTH_SECRET_KEY: JWT 密钥（openssl rand -hex 32 生成）
# - ADMIN_PASSWORD: 管理员密码
# - CORS_ALLOW_ORIGINS: 前端域名
# - ARK_API_KEY: AI 服务密钥
```

#### 步骤 3: 构建并启动

```bash
# 首次部署（构建镜像）
docker-compose build

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 检查服务状态
docker-compose ps
```

#### 步骤 4: 验证部署

```bash
# 检查后端健康
curl http://localhost:8000/health

# 检查前端
curl http://localhost/

# 查看容器日志
docker-compose logs backend
docker-compose logs frontend
```

### 2.3 生产环境优化

#### Nginx HTTPS 配置

创建 `nginx-ssl.conf`:

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 其他配置同 nginx.conf
}

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}
```

#### 性能优化

```yaml
# docker-compose.yml 中添加资源限制
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## 三、PostgreSQL 迁移策略

### 3.1 迁移前准备

#### 备份 SQLite 数据

```bash
# 停止服务
docker-compose down

# 备份 SQLite 数据库
cp backend/weekly_scorer.db backend/weekly_scorer.db.backup.$(date +%Y%m%d)
```

#### 安装迁移依赖

```bash
cd backend
pip install asyncpg aiosqlite
```

### 3.2 执行迁移

```bash
# 1. 先启动 PostgreSQL（不启动后端）
docker-compose up -d postgres

# 2. 等待数据库就绪
docker-compose logs -f postgres
# 看到 "database system is ready to accept connections" 即可

# 3. 执行迁移（先 dry-run 测试）
python scripts/migrate_sqlite_to_pg.py \
  --sqlite ./backend/weekly_scorer.db \
  --pg "postgresql+asyncpg://ws_user:YOUR_PASSWORD@localhost:5432/weekly_scorer" \
  --dry-run

# 4. 确认无误后正式迁移
python scripts/migrate_sqlite_to_pg.py \
  --sqlite ./backend/weekly_scorer.db \
  --pg "postgresql+asyncpg://ws_user:YOUR_PASSWORD@localhost:5432/weekly_scorer"
```

### 3.3 迁移后验证

```bash
# 连接 PostgreSQL 验证数据
docker-compose exec postgres psql -U ws_user -d weekly_scorer

# 检查表数据
SELECT COUNT(*) FROM weekly_reports;
SELECT COUNT(*) FROM persons;
SELECT COUNT(*) FROM departments;

# 检查索引
\di

# 退出
\q
```

### 3.4 切换数据库配置

修改 `.env`:

```env
DATABASE_URL=postgresql+asyncpg://ws_user:YOUR_PASSWORD@postgres:5432/weekly_scorer
```

重新启动后端:

```bash
docker-compose up -d backend
```

## 四、更新迭代方案

### 4.1 版本管理策略

采用 **语义化版本 (SemVer)**:

- **主版本 (X.0.0)**: 不兼容的 API 变更
- **次版本 (0.X.0)**: 向后兼容的功能新增
- **修订版 (0.0.X)**: 向后兼容的 bug 修复

### 4.2 更新流程

#### 方案 A: 滚动更新（推荐）

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 重新构建镜像
docker-compose build --no-cache

# 3. 滚动更新（零停机）
docker-compose up -d

# 4. 验证服务
docker-compose ps
curl http://localhost:8000/health

# 5. 清理旧镜像
docker image prune -f
```

#### 方案 B: 蓝绿部署（大型更新）

```bash
# 1. 构建新版本镜像（标记版本）
docker-compose build
docker tag ws-backend:latest ws-backend:v2.1.3
docker tag ws-frontend:latest ws-frontend:v2.1.3

# 2. 启动新版本（不同端口）
docker-compose -f docker-compose.green.yml up -d

# 3. 验证新版本
curl http://localhost:8001/health

# 4. 切换流量（修改 Nginx 配置）
# 将 proxy_pass 从 backend:8000 改为 backend-green:8000

# 5. 停止旧版本
docker-compose down
```

### 4.3 数据库迁移（Schema 变更）

```bash
# 1. 备份当前数据库
docker-compose exec postgres pg_dump -U ws_user weekly_scorer > backup_$(date +%Y%m%d).sql

# 2. 执行迁移脚本（如有）
docker-compose exec backend python -m alembic upgrade head

# 3. 验证数据完整性
docker-compose exec postgres psql -U ws_user -d weekly_scorer -c "SELECT COUNT(*) FROM weekly_reports;"
```

### 4.4 前端更新

```bash
# 前端更新无需重启后端
docker-compose build frontend
docker-compose up -d frontend

# 清除浏览器缓存（强制刷新）
# Ctrl+Shift+R (Windows) 或 Cmd+Shift+R (Mac)
```

## 五、故障回滚策略

### 5.1 快速回滚命令

```bash
# 回滚到上一个版本（使用旧镜像）
docker-compose down
docker-compose up -d

# 如果镜像已被清理，从备份恢复
docker load -i backup_image_v2.1.2.tar
docker-compose up -d
```

### 5.2 数据库回滚

```bash
# 1. 停止服务
docker-compose down

# 2. 恢复数据库备份
docker-compose up -d postgres
docker-compose exec -T postgres psql -U ws_user -d weekly_scorer < backup_20260708.sql

# 3. 重启后端
docker-compose up -d backend
```

### 5.3 回滚检查清单

- [ ] 确认回滚版本镜像存在
- [ ] 备份当前数据库（防止二次故障）
- [ ] 停止所有服务
- [ ] 恢复数据库（如需要）
- [ ] 启动旧版本服务
- [ ] 验证核心功能
- [ ] 通知相关人员

### 5.4 监控与告警

#### 健康检查配置

```yaml
# docker-compose.yml 中已配置健康检查
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

#### 日志监控

```bash
# 实时查看日志
docker-compose logs -f backend

# 查看错误日志
docker-compose logs backend | grep -i error

# 查看最近 100 行
docker-compose logs --tail=100 backend
```

#### 性能监控

```bash
# 查看容器资源使用
docker stats

# 查看数据库连接数
docker-compose exec postgres psql -U ws_user -d weekly_scorer -c "SELECT count(*) FROM pg_stat_activity;"
```

## 六、运维命令速查

### 6.1 常用命令

```bash
# 启动/停止/重启
docker-compose up -d
docker-compose down
docker-compose restart backend

# 查看状态
docker-compose ps
docker-compose logs -f

# 进入容器
docker-compose exec backend bash
docker-compose exec postgres psql -U ws_user -d weekly_scorer

# 备份数据库
docker-compose exec postgres pg_dump -U ws_user weekly_scorer > backup.sql

# 恢复数据库
docker-compose exec -T postgres psql -U ws_user -d weekly_scorer < backup.sql
```

### 6.2 故障排查

```bash
# 1. 检查容器状态
docker-compose ps

# 2. 查看日志
docker-compose logs backend

# 3. 检查健康状态
docker inspect ws-backend | grep -A 10 Health

# 4. 测试 API
curl http://localhost:8000/health

# 5. 检查数据库连接
docker-compose exec backend python -c "from app.database import engine; print(engine)"
```

## 七、安全建议

### 7.1 生产环境检查清单

- [ ] 修改默认密码（DB_PASSWORD, ADMIN_PASSWORD）
- [ ] 生成强随机 AUTH_SECRET_KEY
- [ ] 配置 HTTPS（SSL 证书）
- [ ] 限制数据库端口暴露（仅内部访问）
- [ ] 配置防火墙规则
- [ ] 定期备份数据库
- [ ] 更新依赖包（安全补丁）
- [ ] 配置日志轮转

### 7.2 定期维护

```bash
# 每周备份数据库
0 2 * * 0 docker-compose exec postgres pg_dump -U ws_user weekly_scorer > /backup/weekly_$(date +\%Y\%m\%d).sql

# 每月清理日志
0 0 1 * * docker-compose logs --tail=10000 > /var/log/weekly-scorer-$(date +\%Y\%m).log
```

## 八、扩展方案

### 8.1 水平扩展

```yaml
# docker-compose.scale.yml
services:
  backend:
    deploy:
      replicas: 3
    ports:
      - "8000-8002:8000"
```

### 8.2 高可用部署

- 使用 PostgreSQL 主从复制
- Redis Sentinel 集群
- Nginx 负载均衡
- 多节点部署

---

**文档版本**: v1.0  
**最后更新**: 2026-07-08  
**维护者**: 周报评分系统团队
