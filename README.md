# 周报评分系统 v2

基于 AI 的智能周报评估平台，通过自动化评分机制提升团队周报质量，为管理者提供数据化的团队工作表现洞察。

## ✨ 核心功能

- **管理配置**：评分维度、权重、等级阈值、AI Prompt、模板管理
- **模板管理**：周报模板 CRUD、默认模板设置
- **周报管理**：文件上传（Excel/Word/PDF）、在线编辑、草稿保存、提交评分
- **AI 评分**：多维度自动评分，支持 DeepSeek / 豆包 / MiMo API，规则降级兜底
- **排行榜**：评分排名、等级分布、时间趋势、多维度筛选
- **周评列表**：聚合评分结果展示，支持按部门 / 人员 / 周次筛选，展示员工综合表现
- **定时聚合评分**：定时（周/天）自动聚合周报与考勤、沟通维度，产出团队周评，支持手动触发
- **微信数据上传**：考勤记录与沟通记录的导入，补充评分依据
- **周小结（OCR）**：支持图片上传并通过 OCR 自动识别小结内容，并入评分流程
- **部门 / 人员管理**：部门信息管理、人员信息管理
- **工作区视图**：角色化首页，管理者和员工看到不同的功能入口
- **安全认证**：管理员账号登录与路由守卫，保护管理操作
- **数据监控**：数据状态概览、数据库备份、AI 服务状态检测（带缓存，避免频繁调用消耗 token）
- **数据安全**：删除周报联动清理聚合数据，同周重复提交拦截（author_name + week_start 唯一约束）

## 🛠️ 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 + PrimeVue 4 (Aura) + ECharts 5 + Vue Router 4 |
| 后端 | FastAPI + SQLAlchemy (async) + SQLite + Pydantic v2 |
| 定时任务 | APScheduler（异步调度，独立事务提交，保证不相互影响）|
| AI | DeepSeek API / 豆包 (火山引擎) / MiMo API (OpenAI 兼容）|
| OCR | Tesseract + PaddleOCR（可选，自动降级为规则兜底）|

## 🚀 快速启动

### 后端

```bash
cd backend
python -m venv venv
venv/Scripts/activate   # Windows
pip install -r requirements.txt
cp .env.example .env     # 填入 AI API Key
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
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

### 定时聚合评分调度器

- 后端启动时会自动从数据库读取调度配置（默认每周二 16:00）
- 可在后端的「系统设置 → 定时聚合评分」中修改时间和开启/关闭
- 调度器状态可在后端启动日志中查看（关键词：`[scheduler]`

## 📁 项目结构

```
weekly-scorer-v2/
├── backend/
│   ├── app/
│   │   ├── api/                  # API 路由
│   │   │   ├── auth.py              # 认证登录
│   │   │   ├── config.py            # 评分配置（含 AI 连接状态检测与缓存
│   │   │   ├── templates.py         # 模板管理
│   │   │   ├── reports.py           # 周报 CRUD（含同周重复提交拦截）
│   │   │   ├── leaderboard.py       # 排行榜
│   │   │   ├── departments.py       # 部门管理
│   │   │   ├── persons.py         # 人员管理
│   │   │   ├── weekly_aggregates.py  # 周评聚合评分（自动/手动触发
│   │   │   ├── scoring_run.py      # 聚合评分执行
│   │   │   ├── attendance.py      # 考勤数据
│   │   │   ├── chat.py             # 沟通数据
│   │   │   ├── upload_unified.py     # 微信数据上传（考勤 / 沟通 / 周小结）
│   │   │   └── weeklysummary.py    # 周小结（OCR 图片识别
│   │   ├── core/                 # 核心服务
│   │   │   ├── auth.py              # 认证 / 默认管理员
│   │   │   └── task_queue.py        # 定时任务调度器（APScheduler）
│   │   ├── models/               # 数据模型
│   │   │   └── models.py            # 数据库表定义（含 WeeklyReport 唯一约束）
│   │   ├── schemas/              # Pydantic Schemas
│   │   │   └── schemas.py           # API 请求/响应模型
│   │   ├── services/             # 业务逻辑
│   │   │   ├── ai_scorer.py         # AI 评分引擎（含 AI 连接状态缓存）
│   │   │   ├── scoring.py           # 评分调度与规则兜底
│   │   │   ├── aggregator.py       # 周评聚合（周报 + 考勤 + 沟通
│   │   │   ├── document_parser.py   # Excel / Word / PDF 文档解析
│   │   │   ├── ocr_service.py       # 周小结图片 OCR（可选
│   │   │   └── wechat_parser.py    # 微信数据解析
│   │   ├── utils/                # 工具类
│   │   │   ├── exceptions.py        # 异常处理
│   │   │   ├── logger.py            # 结构化日志
│   │   │   └── time_utils.py       # 北京时间统一时间工具
│   │   ├── config.py              # 应用配置与环境变量
│   │   ├── database.py            # 数据库连接与会话（含自动迁移新增列
│   │   └── main.py                # FastAPI 入口与中间件
│   ├── scripts/                  # 一键诊断脚本（diag_scheduler.py / diag_aggregate.py / test_aggregate_now.py / diag_full_startup.py
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
│   │   │   ├── Config.vue          # 评分配置（含 AI 连接状态、定时任务
│   │   │   ├── WriteReport.vue     # 在线写周报
│   │   │   ├── ReportList.vue      # 周评列表（含评分状态轮询
│   │   │   ├── ReportDetail.vue    # 周报详情 / 评分
│   │   │   ├── Leaderboard.vue     # 排行榜
│   │   │   └── WeChatDataUpload.vue  # 微信数据上传
│   │   ├── components/ui/        # 可复用 UI 组件
│   │   ├── composables/          # 组合式函数
│   │   ├── utils/                # 工具
│   │   ├── layouts/              # 布局组件
│   │   ├── router/               # 路由配置（含守卫）
│   │   ├── api/                  # API 调用层
│   │   ├── assets/               # 全局样式
│   │   └── App.vue / main.js
│   ├── package.json
│   └── vite.config.js           # 代理 /api/* → http://localhost:8000
├── docs/
│   ├── DEVELOPMENT.md
│   ├── PRD_v3_考勤评分系统.md
│   └── 评分系统需求文档prd.md
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

后端启动后，可以访问后端 `http://localhost:8000/docs` 查看 Swagger API 文档；`http://localhost:8000/health` 可做健康检测。

### 评分流程

1. 用户提交周报（文件上传或在线编辑）
2. 系统自动识别周报时间并分类
3. 调用 AI 服务进行多维度评分
4. AI 服务不可用时自动切换为后端评分规则
5. 应用评分约束（维度分差与等级阈值）
6. 保存评分结果并更新周报状态
7. 定时任务或手动触发聚合评分，合并周报、考勤、沟通维度，产出周评

### 周评聚合

- 周评基于 author_name + week_start 作为聚合键
- WeeklyReport 表在（author_name, week_start）上有唯一约束，防止同周重复提交
- 删除周报时会联动清理对应 WeeklyAggregate 记录，保证仪表盘数据一致性
- 聚合任务使用独立事务提交，避免一人失败导致全员回滚
- 聚合失败时回落到规则兜底评分（基础分 97，扣除迟到 / 早退 / 补卡 / 加班）

### 后端时间约定

- 所有时间以北京时间（Asia/Shanghai）
- JWT token exp 字段仍以 UTC 为准（RFC 7519）
- 数据库 DATETIME 字段存北京时间 naive datetime
- 前端解析后端 datetime 字符串为本地时间，保持一致展示

### 后端环境变量配置

在后端 `.env` 文件中配置：

- AI API Key（后端 API Key）
- 模型名称、接口地址等可选配置
- 可通过后端 `AI_PROVIDER` 切换 AI 服务商（deepseek / ark / mimo）

### 前端代理

前端 dev server 通过后端 `vite.config.js` 将 `/api/*` 代理到 `http://localhost:8000`，开发阶段无需额外处理跨域。

### AI 连接状态检测

后端提供 `GET /api/v1/config/ai-status` 接口检测 AI 服务是否可用，并有 30 分钟缓存，避免频繁检测产生 token 消耗。缓存写入数据库，支持 `?force=true` 可强制重新检测。

### 诊断脚本

后端 `backend/scripts/` 提供一键诊断：

- `diag_scheduler.py` - 调度器诊断
- `diag_aggregate.py` - 聚合评分执行结果诊断
- `test_aggregate_now.py` - 模拟定时任务执行
- `diag_full_startup.py` - 全流程启动诊断

## 🎯 项目目标

- **效率提升**：自动评分替代人工评审，节省大量周报审核时间
- **质量提升**：通过多维度评分引导员工产出高质量周报
- **数据洞察**：提供后端质量趋势分析、团队排行榜等数据可视化
- **灵活配置**：支持自定义评分维度、权重和等级标准
- **降级兜底**：AI 服务不可用时自动切换为后端评分规则
- **定时聚合**：周/天定时自动聚合，支持手动触发，实时同步

##  许可证

本项目为内部使用工具。
