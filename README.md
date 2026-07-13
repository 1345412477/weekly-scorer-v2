# 智友辰评分系统

> 基于 AI 的智能周报评估平台，通过自动化评分机制提升团队周报质量，为管理者提供数据化的团队工作表现洞察。

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green)
![Vue](https://img.shields.io/badge/Vue-3.4-brightgreen)
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

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + PrimeVue 4 + ECharts 5 + Vue Router 4 + Pinia |
| 后端 | FastAPI + SQLAlchemy (async) + SQLite + Pydantic v2 |
| 定时任务 | APScheduler（异步调度，独立事务） |
| AI | 豆包 (火山引擎) / DeepSeek / OpenAI 兼容接口 |
| 部署 | Docker (多阶段构建) + docker-compose |

## 快速开始

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆仓库
git clone https://gitee.com/yostore/weekly-scorer-v2.git
cd weekly-scorer-v2

# 2. 创建配置文件
cp .env.example .env
# 编辑 .env，填入 ARK_API_KEY 等配置

# 3. 创建数据目录
mkdir -p data uploads

# 4. 构建并启动
docker compose up -d --build
```

访问 `http://localhost` 即可使用。

### 方式二：本地开发

**后端**

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
cp .env.example .env            # 填入 AI API Key
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**前端**

```bash
cd frontend
npm install
npm run dev
```

访问 `http://localhost:3001`

### 默认账号

- 用户名：`admin`
- 密码：`admin123`

> 首次登录后请在系统设置中修改默认密码。

## Docker 部署详解

### 架构说明

采用多阶段 Docker 构建：
- **Stage 1**：Node 20 构建前端 Vue 应用
- **Stage 2**：Python 3.11 运行后端 FastAPI，内嵌前端静态文件

单容器即可运行完整系统，无需额外 Nginx 或数据库容器。

### 目录结构

```
weekly-scorer-v2/
├── data/              # 数据库文件（volume 挂载）
├── uploads/           # 上传文件（volume 挂载）
├── backend/           # 后端代码
├── frontend/          # 前端代码
├── Dockerfile         # 多阶段构建
├── docker-compose.yml # 编排配置
├── .env.example       # 环境变量模板
└── deploy.sh          # 一键部署脚本
```

### 环境变量配置

复制 `.env.example` 为 `.env`，修改以下关键配置：

| 变量 | 说明 | 必填 |
|------|------|------|
| `AUTH_SECRET_KEY` | JWT 签名密钥（随机字符串） | 是 |
| `ADMIN_PASSWORD` | 管理员密码 | 是 |
| `CORS_ALLOW_ORIGINS` | 允许的前端地址 | 是 |
| `ARK_API_KEY` | 火山引擎豆包 API Key | 是 |
| `ARK_BASE_URL` | AI 接口地址 | 否 |
| `SCORING_MODEL` | AI 模型名称 | 否 |
| `DATABASE_URL` | 数据库连接（默认 SQLite） | 否 |

### 数据持久化

通过 Docker Volume 挂载，容器重建不会丢失数据：

- `./data` → `/app/data`（数据库文件）
- `./uploads` → `/app/uploads`（上传文件）

### 一键部署脚本

```bash
chmod +x deploy.sh
./deploy.sh
```

脚本自动完成：构建镜像 → 停止旧容器 → 启动新容器 → 检查状态。

## 项目结构

```
weekly-scorer-v2/
├── backend/
│   ├── app/
│   │   ├── api/                  # API 路由层
│   │   │   ├── auth.py              # 认证登录
│   │   │   ├── config.py            # 评分配置 & AI 状态检测
│   │   │   ├── templates.py         # 模板管理
│   │   │   ├── reports.py           # 周报 CRUD
│   │   │   ├── leaderboard.py       # 排行榜 & 仪表盘
│   │   │   ├── departments.py       # 部门管理
│   │   │   ├── persons.py           # 人员管理
│   │   │   ├── weekly_aggregates.py # 周评聚合评分
│   │   │   ├── scoring_run.py       # 聚合评分执行
│   │   │   ├── attendance.py        # 考勤数据
│   │   │   ├── chat.py              # 沟通数据
│   │   │   ├── upload_unified.py    # 统一上传接口
│   │   │   ── weeklysummary.py     # 周小结 OCR
│   │   ├── core/                 # 核心服务
│   │   │   ├── auth.py              # JWT 认证
│   │   │   └── task_queue.py        # 定时任务调度
│   │   ├── models/               # SQLAlchemy 数据模型
│   │   ├── schemas/              # Pydantic 请求/响应模型
│   │   ├── services/             # 业务逻辑层
│   │   │   ├── ai_scorer.py         # AI 评分引擎
│   │   │   ├── scoring.py           # 评分调度 & 规则兜底
│   │   │   ├── aggregator.py        # 周评聚合
│   │   │   ├── document_parser.py   # 文档解析（Excel/Word/PDF）
│   │   │   ├── ocr_service.py       # OCR 图片识别
│   │   │   └── wechat_parser.py     # 微信数据解析
│   │   ├── utils/                # 工具类
│   │   ├── config.py              # 应用配置
│   │   ├── database.py            # 数据库连接 & 自动迁移
│   │   └── main.py                # FastAPI 入口
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/                # 页面组件
│   │   ├── components/ui/        # 可复用 UI 组件
│   │   ├── composables/          # 组合式函数
│   │   ├── utils/                # 工具函数
│   │   ├── layouts/              # 布局组件
│   │   └── router/               # 路由配置
│   ├── package.json
│   └── vite.config.js
├── docs/                         # 需求文档
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── deploy.sh
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

### 默认评分维度

| 维度 | 满分 | 考核内容 |
|------|------|----------|
| 工作反馈深度 | 14 | 问题发现 + 分析 + 解决方案 |
| 进度节点明确 | 13 | 项目是否有明确进度/节点 |
| 计划可行性 | 10 | 下周计划是否具体可执行 |
| 工作连续性 | 13 | 是否承接上周计划且有闭环 |

### 等级阈值

| 等级 | 分数 |
|------|------|
| 优 | ≥ 45 |
| 良 | ≥ 38 |
| 一般 | ≥ 33 |
| 差 | < 28 |

## API 文档

后端启动后访问：

- Swagger UI：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/health`

## 开发约定

- **时间**：所有时间以北京时间（Asia/Shanghai）为准，JWT exp 除外（RFC 7519 UTC）
- **数据库**：SQLite + 自动迁移新增列，兼容 PostgreSQL
- **前端代理**：`vite.config.js` 将 `/api/*` 代理到 `http://localhost:8000`
- **AI 状态检测**：`GET /api/v1/config/ai-status`，30 分钟缓存，支持 `?force=true` 强制刷新

## 许可证

本项目为内部使用工具，保留所有权利。
