# 智友辰评分系统

> 基于 AI 的智能周报评估平台，通过自动化评分机制提升团队周报质量，为管理者提供数据化的团队工作表现洞察。

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Vue](https://img.shields.io/badge/Vue-3.4-brightgreen)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-336791)
![License](https://img.shields.io/badge/License-Private-red)

## 功能概览

| 模块 | 功能 |
|------|------|
| 仪表盘 | 本周提交/未提交统计、未提交人员列表、评分趋势图、整体评分概况 |
| 业务盘 | 部门维度业务分析、周次对比、AI 业务总结 |
| 周评列表 | 聚合评分结果、多维筛选、批量导出/删除 |
| 排行榜 | 评分排名、等级分布、时间趋势 |
| 企业微信数据上传 | 考勤打卡数据、聊天记录数据上传解析 |
| 系统设置 | 评分配置、模板管理、部门/人员管理、AI 模型管理、定时任务 |
| 员工端 | 在线写周报、文件上传（Excel/Word/PDF/图片）、周报详情查看 |

## 技术架构

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + PrimeVue 4 + ECharts 5 + Vue Router 4 + Pinia |
| 后端 | FastAPI + SQLAlchemy (async) + Pydantic v2 |
| 数据库 | PostgreSQL (生产) / SQLite (开发) |
| 定时任务 | APScheduler（异步调度，独立事务） |
| AI 模型 | 豆包 (火山引擎) / DeepSeek / OpenAI 兼容接口 |
| 部署 | Docker (多阶段构建) + docker-compose |

## 项目结构

```
weekly-scorer-v2/
├── backend/
│   ├── app/
│   │   ├── api/                  # API 路由层
│   │   ├── core/                 # 核心服务（认证、定时任务）
│   │   ├── models/               # SQLAlchemy 数据模型
│   │   ├── schemas/              # Pydantic 请求/响应模型
│   │   ├── services/             # 业务逻辑层（AI 评分、解析）
│   │   ├── utils/                # 工具类
│   │   ├── config.py             # 应用配置
│   │   ├── database.py           # 数据库连接
│   │   └── main.py               # FastAPI 入口
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/                # 页面组件
│   │   ├── components/ui/        # 可复用 UI 组件
│   │   ├── composables/          # 组合式函数
│   │   └── router/               # 路由配置
│   └── package.json
├── Dockerfile                    # 多阶段构建
├── docker-compose.yml             # 编排配置
├── .env.example                  # 环境变量模板
└── deploy.sh                     # 一键部署脚本
```

## 评分流程

```
用户提交周报
    ↓
系统识别周报时间并分类
    ↓
调用 AI 多维度评分（豆包/DeepSeek）
    ↓
AI 不可用 → 自动切换规则兜底评分
    ↓
应用评分约束（维度分差 & 等级阈值）
    ↓
保存评分结果
    ↓
定时任务聚合（周报 + 考勤 + 沟通）→ 产出周评
```

## 部署方式

### 环境要求

- Docker 20.10+
- Docker Compose 2.0+
- PostgreSQL 12+

### 部署步骤

```bash
# 1. 克隆代码
git clone <仓库地址>
cd weekly-scorer-v2

# 2. 创建环境配置文件
cp .env.example .env
# 编辑 .env 文件，填入必要配置

# 3. 创建上传目录
mkdir -p uploads

# 4. 执行部署脚本
chmod +x deploy.sh
./deploy.sh
```

### 环境配置

编辑 `.env` 文件，主要配置项：

| 变量 | 说明 | 必填 |
|------|------|------|
| `AUTH_SECRET_KEY` | JWT 签名密钥（随机字符串） | 是 |
| `ADMIN_PASSWORD` | 初始管理员密码 | 是 |
| `CORS_ALLOW_ORIGINS` | 允许的前端访问地址 | 是 |
| `ARK_API_KEY` | 火山引擎豆包 API Key | 是 |
| `DATABASE_URL` | PostgreSQL 数据库连接串 | 是 |

**数据库连接格式：**

```
postgresql+asyncpg://<用户名>:<密码>@<数据库主机>:<端口>/<数据库名>
```

> 注意：Docker 容器内访问宿主机数据库使用 `host.docker.internal` 而非 `localhost`

### 更新部署

```bash
cd weekly-scorer-v2
./deploy.sh
```

### 访问入口

- 系统首页：部署后通过配置的域名或 IP 访问
- 健康检查：`/health`
- API 文档：`/docs`

## 本地开发

### 后端

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
cp .env.example .env            # 使用 SQLite 配置
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端开发服务器默认运行在 3001 端口，通过 Vite 代理访问后端 API。

## 开发约定

- **时间**：所有时间以北京时间（Asia/Shanghai）为准，JWT exp 除外（RFC 7519 UTC）
- **数据库**：PostgreSQL（生产）/ SQLite（开发），自动迁移新增列
- **前端代理**：`vite.config.js` 将 `/api/*` 代理到后端服务
- **AI 状态检测**：提供接口查询 AI 模型可用性，支持强制刷新

## 许可证

本项目为内部使用工具，保留所有权利。
