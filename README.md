# 周报评分系统 v2

基于 AI 的智能周报评估平台，通过自动化评分机制提升团队周报质量，为管理者提供数据化的团队工作表现洞察。

## ✨ 核心功能

- **管理配置**：评分维度、权重、等级阈值、AI Prompt、模板管理
- **模板管理**：周报模板 CRUD、默认模板设置
- **周报管理**：文件上传（Excel/Word/PDF）、在线编辑、草稿保存、提交评分
- **AI 评分**：多维度自动评分，支持 DeepSeek / 豆包 / MiMo API，规则降级兜底
- **排行榜**：评分排名、等级分布、时间趋势、多维度筛选
- **部门 / 人员管理**：部门信息管理、人员信息管理
- **工作区视图**：角色化首页，管理者和员工看到不同的功能入口
- **安全认证**：管理员账号登录与路由守卫，保护管理操作
- **数据监控**：数据状态概览、数据库备份、AI 服务状态检测

## 🛠️ 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 + PrimeVue 4 (Aura) + ECharts 5 + Vue Router 4 |
| 后端 | FastAPI + SQLAlchemy (async) + SQLite + Pydantic v2 |
| AI | DeepSeek API / 豆包 API / MiMo API (OpenAI 兼容) |

## 🚀 快速启动

### 后端

```bash
cd backend
python -m venv venv
venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env     # 填入 AI API Key
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

访问 <http://localhost:3001>

### 默认管理员账号

- 用户名：`admin`
- 密码：`admin123`
- 首次登录后建议在后端配置文件中修改默认账号与密码

## 📁 项目结构

```
weekly-scorer-v2/
├── backend/
│   ├── app/
│   │   ├── api/                  # API 路由
│   │   │   ├── auth.py              # 认证登录
│   │   │   ├── config.py            # 评分配置
│   │   │   ├── templates.py         # 模板管理
│   │   │   ├── reports.py           # 周报 CRUD
│   │   │   ├── leaderboard.py       # 排行榜
│   │   │   ├── departments.py       # 部门管理
│   │   │   └── persons.py           # 人员管理
│   │   ├── core/                 # 核心服务
│   │   │   └── auth.py              # 认证 / 默认管理员
│   │   ├── models/               # 数据模型
│   │   │   └── models.py            # 数据库表定义
│   │   ├── schemas/              # Pydantic Schemas
│   │   │   └── schemas.py           # API 请求/响应模型
│   │   ├── services/             # 业务逻辑
│   │   │   ├── ai_scorer.py         # AI 评分引擎
│   │   │   ├── scoring.py           # 评分调度与规则兜底
│   │   │   └── document_parser.py   # Excel / Word / PDF 文档解析
│   │   ├── utils/                # 工具类
│   │   │   ├── exceptions.py        # 异常处理
│   │   │   └── logger.py            # 结构化日志
│   │   ├── config.py              # 应用配置与环境变量
│   │   ├── database.py            # 数据库连接与会话
│   │   └── main.py                # FastAPI 入口与中间件
│   ├── backups/                  # 数据库备份（不入库）
│   ├── uploads/                  # 用户上传文件（不入库）
│   ├── tests/                    # pytest 测试
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/                # 页面组件
│   │   │   ├── AdminLogin.vue      # 管理员登录
│   │   │   ├── PublicHome.vue      # 公开首页 / 员工写周报入口
│   │   │   ├── Workspace.vue       # 工作区（管理者视角）
│   │   │   ├── Dashboard.vue       # 仪表盘 / 趋势图表
│   │   │   ├── Config.vue          # 评分配置
│   │   │   ├── WriteReport.vue     # 在线写周报
│   │   │   ├── ReportList.vue      # 周报列表
│   │   │   ├── ReportDetail.vue    # 周报详情 / 评分
│   │   │   └── Leaderboard.vue     # 排行榜
│   │   ├── components/ui/        # 可复用 UI 组件
│   │   │   ├── EmptyState.vue
│   │   │   ├── FilterBar.vue
│   │   │   ├── GradeTag.vue
│   │   │   ├── MetricCard.vue
│   │   │   ├── PageHeader.vue
│   │   │   ├── ResponsiveTableShell.vue
│   │   │   ├── ScoreBadge.vue
│   │   │   ├── SectionCard.vue
│   │   │   ├── StatusPill.vue
│   │   │   └── ToolbarActions.vue
│   │   ├── composables/          # 组合式函数
│   │   │   ├── useDataOperation.js  # 通用 CRUD 操作
│   │   │   ├── useDataRefresh.js    # 统一刷新逻辑
│   │   │   └── useEChart.js         # ECharts 封装
│   │   ├── utils/                # 工具
│   │   │   ├── auth.js             # 登录状态与 token
│   │   │   ├── dimensionValidator.js # 评分配置校验
│   │   │   └── timeUtil.js         # 周次 / 日期计算
│   │   ├── layouts/              # 布局组件
│   │   ├── router/               # 路由配置（含守卫）
│   │   ├── api/                  # API 调用层
│   │   ├── assets/               # 全局样式
│   │   └── App.vue / main.js
│   ├── package.json
│   └── vite.config.js
├── .gitignore
└── README.md
```

## 📊 默认配置

### 默认评分维度

| 维度名称 | 满分 | 考核内容 |
| --- | --- | --- |
| 工作反馈深度 | 14 | 问题发现 + 分析 + 解决方案 |
| 进度节点明确 | 13 | 项目是否有明确进度 / 节点 |
| 计划可行性 | 10 | 下周计划是否具体可执行 |
| 工作连续性 | 13 | 是否承接上周计划且有闭环 |

### 默认等级阈值

| 等级 | 分数阈值 |
| --- | --- |
| 优 | ≥45 |
| 良 | ≥38 |
| 一般 | ≥33 |
| 差 | <28 |

## 📝 开发说明

### API 文档

后端启动后，可以访问 `http://localhost:8002/docs` 查看 Swagger API 文档；`http://localhost:8002/health` 可做健康检测。

### 评分流程

1. 用户提交周报（文件上传或在线编辑）
2. 系统自动识别周报时间并分类
3. 调用 AI 服务进行多维度评分
4. AI 服务不可用时自动切换为规则评分
5. 应用评分约束（维度分差与等级阈值）
6. 保存评分结果并更新周报状态

### 环境变量配置

在 `backend/.env` 文件中配置：

- AI API Key（DeepSeek / 豆包 / MiMo 任一 OpenAI 兼容服务）
- 模型名称、接口地址等可选配置

### 前端代理

前端 dev server 通过 `vite.config.js` 将 `/api/*` 代理到 `http://localhost:8002`，开发阶段无需额外处理跨域。

## 🎯 项目目标

- **效率提升**：自动评分替代人工评审，节省大量周报审核时间
- **质量提升**：通过多维度评分引导员工产出高质量周报
- **数据洞察**：提供周报质量趋势分析、团队排行榜等数据可视化
- **灵活配置**：支持自定义评分维度、权重和等级标准
- **降级兜底**：AI 服务不可用时自动切换为规则评分

## 📄 许可证

本项目为内部使用工具。
