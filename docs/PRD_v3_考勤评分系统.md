# PR：周报评分系统 v3 —— 考勤 · 周报 · 沟通（含一周小结） 综合评分

> 状态：**已确认**
> 作者：开发团队
> 阅读对象：产品 / 技术负责人 / 运维

---

## 1. 需求变更总览（相对 v2 的核心调整）

| # | 需求 | 影响范围 |
|---|------|---------|
| 1 | **评分标准提示词化** —— 后端仅负责采集原始数据，**不做任何规则评分**；评分标准与分数范围由提示词规定，由 AI 按提示词打分；管理员可在列表页二次覆盖 | 后端算法层、前后端数据契约、前端表单 |
| 2 | **新增「一周小结」图片上传**（首页入口）—— 员工上传企业微信一周小结图片（含姓名、处理工作会话次数、总耗时、最晚时间），由 AI 做 OCR 提取姓名 + 工作会话次数，**作为沟通分的辅助输入**，与聊天记录共同构成沟通分 | 首页上传区、后端图像上传/OCR、数据库表扩列 |
| 3 | **周报列表 → 周评列表** —— 新增「考勤分 / 周报分 / 沟通分 / 总分」字段；沟通分综合聊天记录和一周小结两项数据；`composite_score = report_score + attendance_score + chat_score`（三项权重均为 1） | 前端列表页、后端查询接口 |
| 4 | **管理员双击修改分数** —— 在周评列表中双击任一分数字段（考勤分/周报分/沟通分）可直接修改；总分随修改自动刷新；**总分本身不可直接修改** | 前端列表页交互、后端 update 接口 |
| 5 | **保留「查看周报」功能** —— 原有的文件下载/预览功能不动，不作为编辑入口 | 前端详情页 / 列表按钮栏 |
| 6 | **打卡地点** —— 考勤数据额外采集「上班打卡地点 / 下班打卡地点」 | 后端考勤表、解析逻辑 |
| 7 | **数据自动更新** —— 移除管理员手动「重算某周」按钮，任何数据变动（上传/修改）后由后端自动刷新该员工该周的综合得分 | 后端聚合服务 |

---

## 2. 架构图

核心原则：**评分标准不在后端代码中，只在提示词里。**

```
┌────────────── 员工端（PublicHome.vue） ──────────────┐
│   [① 上传周报 XLSX] ─────────┐                       │
│   [② 上传一周小结图片] ───────┼──→ 上传 API           │
└───────────────────────────────────────────────────────┘
                              │
                              ▼
┌────────────── 后端 API（采集 + 调用 AI 打分） ────────┐
│  reports/upload        → weekly_reports + report_scores│
│                          （AI 按 report_prompt 打分）   │
│  weeklysummary/upload  → weekly_summaries（OCR 采关键│
│                          字段，作为沟通分辅助数据源）    │
│  attendance/upload     → attendance_records（含地点）  │
│                          （AI 按 attendance_prompt 打分）│
│  chat/upload           → chat_records                   │
│                          （AI 按 chat_prompt 打分）      │
│  weekly-aggregates/    → 周评列表（只读展示 + 管理员修改）│
└────────────────────────────────────────────────────────┘
                              │
                              ▼
         ┌─────────────────────────────────────────┐
         │  ⚡ 每次上传 / 修改后自动聚合               │
         │  chat_score 综合 chat_records +          │
         │  weekly_summaries 两项数据，统一按         │
         │  chat_prompt 由 AI 打分                   │
         │  无手动重算按钮                            │
         └─────────────────────────────────────────┘
                              │
                              ▼
┌────────────── 管理员端（Admin Console） ─────────────┐
│  /admin/dashboard  仪表盘（综合得分）                 │
│  /admin/reports    周评列表（考勤/周报/沟通/总分）    │
│                    · 双击分数字段 → 弹框修改          │
│                    · 总分随任一分修改自动刷新         │
│                    · 「查看周报」跳详情页              │
│  /admin/reports/:id  周报详情页（保留原文件预览）      │
│  /admin/wechat     企业微信数据上传页                 │
│  /admin/config     系统设置（提示词管理 + 部门/人员） │
│                    · 周报 / 考勤 / 沟通 三项提示词    │
│                    · 三项权重 {report:1, attendance:1,│
│                      chat:1}，总分即三项之和          │
└───────────────────────────────────────────────────────┘
```

---

## 3. 数据流全景

```
 员工首页上传                管理员后台上传              管理员操作
      │                          │                           │
      │ ①周报XLSX                │ ②企业微信打卡Excel         │ ④双击单元格修改
      │ ③一周小结图片            │ ⑤企业微信聊天记录Excel     │   PUT /weekly-aggregates/:id
      ▼                          ▼                           ▼
 reports/upload              attendance/upload          PUT 改分
 chat/upload
      │
      ▼
 weekly_reports + report_scores     attendance_records
（AI 按 report_prompt）            （含 check_in/out_location）
 weekly_summaries（OCR 结果）      chat_records
      │                          │
      └────────────┬─────────────┘
                   ▼
      ┌────────────────────────────────────────────┐
      │  auto_aggregate(weekly_aggregates)           │
      │  1. report_score = report_scores.total_score │
      │  2. attendance_score = AI(attendance_records,│
      │     attendance_prompt)                       │
      │  3. chat_score = AI(chat_records +           │
      │     weekly_summaries, chat_prompt)           │
      │  4. composite_score = report_score +         │
      │     attendance_score + chat_score            │
      │  5. manual_override 字段保留人工修改痕迹     │
      └────────────────────────────────────────────┘
                   │
                   ▼
           weekly_aggregates 表（周评列表数据来源）
```

---

## 4. 数据库表设计（新增 / 扩列）

### 4.1 新表 `weekly_summaries` —— 一周小结图片解析结果

```
字段                  类型            说明
────────────────────────────────────────────────────
id                    VARCHAR(36)    PK
person_id             VARCHAR(36)    FK → persons
author_name           VARCHAR(50)    员工姓名（OCR 提取）
department            VARCHAR(50)    部门
department_id         VARCHAR(36)    部门 ID
week_start            DATE           周一
week_end              DATE           周日
work_session_count    INTEGER        处理工作会话次数（沟通效率指标）
total_minutes         INTEGER        总耗时（参考）
latest_time           VARCHAR(50)    最晚时间原文
latest_time_parsed    DATETIME       解析后标准时间（可空）
raw_ocr_text          TEXT           OCR 原始文本
source_file           VARCHAR(200)   图片文件名
created_at / updated_at DATETIME
索引：(week_start, week_end, person_id) UNIQUE
```

### 4.2 修改 `attendance_records` —— 增加「打卡地点」

```
check_in_location   VARCHAR(200)   上班打卡地点
check_out_location  VARCHAR(200)   下班打卡地点
```

### 4.3 `report_scores` —— 不扩字段，语义升级

`total_score` 现语义为"周报分"；分数范围由 `report_prompt` 规定，后端不强制校验。

### 4.4 `weekly_aggregates` —— 周评综合表（核心展示表）

```
字段                  类型            说明
────────────────────────────────────────────────────
id                    VARCHAR(36)    PK
person_id / author_name / department / department_id
week_start / week_end DATE
report_score          DECIMAL(5,1)   周报分
attendance_score      DECIMAL(5,1)   考勤分
chat_score            DECIMAL(5,1)   沟通分
composite_score       DECIMAL(6,2)   总分 = 三项之和

manual_override       TEXT           人工修改标记（JSON）
modified_by           VARCHAR(50)    最后修改人
modified_at           DATETIME       最后修改时间

report_score_id       VARCHAR(36)    引用 report_scores.id
summary_id            VARCHAR(36)    引用 weekly_summaries.id
created_at / updated_at DATETIME
唯一索引：(week_start, week_end, person_id)
```

### 4.5 `scoring_configs` 扩列 —— 三项提示词 + 三项权重

```
report_prompt        TEXT    周报评分提示词
attendance_prompt    TEXT    考勤表现评分提示词
chat_prompt          TEXT    企业微信沟通评分提示词
weights              TEXT    三项权重 JSON（默认 {"report":1,"attendance":1,"chat":1}）
```

**数据库迁移方案**（在 `seed_default_data()` 中执行）：

```sql
ALTER TABLE scoring_configs ADD COLUMN report_prompt TEXT;
ALTER TABLE scoring_configs ADD COLUMN attendance_prompt TEXT;
ALTER TABLE scoring_configs ADD COLUMN chat_prompt TEXT;
ALTER TABLE scoring_configs ADD COLUMN weights TEXT;
UPDATE scoring_configs SET report_prompt = prompt_template WHERE report_prompt IS NULL;
```

---

## 5. 后端 API 设计

全部路由需经 `require_admin` 鉴权（员工端首页上传除外）。

| 方法 | 路径 | 页面来源 | 说明 |
|------|------|---------|------|
| POST | `/api/v1/reports/upload` | PublicHome.vue | 上传周报 XLSX；AI 按 report_prompt 打分；写入 weekly_reports + report_scores；触发 auto_aggregate |
| POST | `/api/v1/weeklysummary/upload` | PublicHome.vue | 上传一周小结图片（PNG/JPG）；OCR 提取姓名 + 会话次数；匹配人员库；写入 weekly_summaries；触发 auto_aggregate（并入沟通分口径） |
| POST | `/api/v1/attendance/upload` | WeChatDataUpload.vue | 上传企业微信打卡 Excel；解析姓名/日期/上下班时间/工作时长/打卡地点/考勤状态；AI 按 attendance_prompt 打分；触发 auto_aggregate |
| POST | `/api/v1/chat/upload` | WeChatDataUpload.vue | 上传企业微信聊天记录 Excel；AI 按 chat_prompt 打沟通分；触发 auto_aggregate |
| GET  | `/api/v1/weekly-aggregates` | ReportList.vue | 分页返回周评列表（report_score / attendance_score / chat_score / composite_score / manual_override / modified_at） |
| PUT  | `/api/v1/weekly-aggregates/:id` | ReportList.vue（双击修改） | 修改三项分数字段之一；设置 manual_override；自动重算 composite_score；**禁止直接修改 composite_score** |
| POST | `/api/v1/weekly-aggregates/:id/restore-ai` | ReportList.vue（可选） | 对人工覆盖字段重新跑 AI 评分，恢复 AI 原始值 |
| GET  | `/api/v1/reports/:id` | ReportDetail.vue | 保留：原查看接口，返回周报内容与文件下载路径 |
| GET  | `/api/v1/config` | Config.vue | 返回三项提示词与 weights |
| PUT  | `/api/v1/config` | Config.vue | 保存三项提示词与权重 |
| GET  | `/health` | —— | 健康检查 |

**关键约定**：无手动重算接口；`composite_score` 由后端重算并返回，前端不做计算。

---

## 6. 后端文件变更清单

### 6.1 新增文件

| 文件 | 说明 |
|------|------|
| `backend/app/api/weeklysummary.py` | 一周小结图片上传 + OCR 解析接口 |
| `backend/app/api/attendance.py` | 考勤 Excel 上传接口（含打卡地点解析） |
| `backend/app/api/chat.py` | 聊天记录 Excel 上传接口 |
| `backend/app/api/weekly_aggregates.py` | 周评列表查询 + 管理员修改 + 恢复 AI 评分 |
| `backend/app/services/wechat_parser.py` | 企业微信 Excel 解析函数（考勤/聊天） |
| `backend/app/services/ocr_service.py` | 图片 OCR 服务（走现有的同一大模型 API） |
| `backend/app/services/aggregator.py` | `auto_aggregate(person_id, week_start, week_end)` —— 自动重算该员工该周综合分 |

### 6.2 修改文件

| 文件 | 改动点 |
|------|--------|
| `backend/app/models/models.py` | 新增 `WeeklySummary` / `AttendanceRecord` / `ChatRecord` / `WeeklyAggregate` 模型；`ScoringConfig` 扩 3 个提示词 + weights 字段 |
| `backend/app/api/reports.py` | upload 后触发 `auto_aggregate()`；保留原下载/详情接口 |
| `backend/app/api/config.py` | GET/PUT 支持三个提示词 + weights 字段 |
| `backend/app/main.py` | 注册 4 个新 router（weeklysummary / attendance / chat / weekly-aggregates） |
| `backend/app/database.py` | `init_db()` 保持；`seed_default_data()` 中执行迁移 |
| `backend/app/services/ai_scorer.py` | 新增 `score_attendance` / `score_chat`；`score_chat` 输入包含聊天摘要 + 一周小结 OCR 摘要 |

### 6.3 AI 评分函数签名

```python
# backend/app/services/ai_scorer.py

# 已有（不改）
async def score_report(content, author_name, department, prompt_template, dimensions=None):
    """周报评分：按 report_prompt 打分"""

# 新增
async def score_attendance(summary_text, author_name, department, prompt_template):
    """考勤评分：把本周打卡摘要（日期+上下班+地点+状态）按 attendance_prompt 打分"""

async def score_chat(summary_text, author_name, department, prompt_template):
    """沟通评分：聊天摘要 + 一周小结 OCR 摘要，一并按 chat_prompt 打分"""
```

### 6.4 自动聚合触发点

以下事件后立即调用 `auto_aggregate(person_id, week_start, week_end)`：

- `reports/upload` 写入成功
- `weeklysummary/upload` 写入成功
- `attendance/upload` 写入成功
- `chat/upload` 写入成功
- `weekly-aggregates/:id` PUT 成功（管理员修改）

---

## 7. 前端改动

### 7.1 路由（`frontend/src/router/index.js`）

新增路由：`{ path: '/admin/wechat', name: 'WeChatData', component: WeChatDataUpload.vue, meta: { requiresAdmin: true } }`

### 7.2 PublicHome.vue —— 首页改造（员工端）

- 原功能：**上传周报 XLSX**（保留）
- 新增：**上传一周小结图片**（PNG/JPG，OCR 识别姓名与会话次数）
- 上传完成后展示：姓名 / 本周周次 / 综合得分（含三项明细）

### 7.3 ReportList.vue —— 周报列表 → 周评列表

**列**：周次 / 姓名 / 部门 / 考勤分 / 周报分 / 沟通分 / 总分 / 更新时间 / 操作（查看 / 删除）

**交互**：
- 双击「考勤分 / 周报分 / 沟通分」单元格 → 弹数字输入框 → 保存后后端重算总分
- 双击「总分」单元格 → 不可修改（弹提示）
- 「查看周报」→ 跳 `/admin/reports/:id`
- 「删除」→ 移除周报并触发重新聚合

示例行：`2026-W23 | 张三 | 产品部 | 85 | 78 | 70 | 233 | 2026-06-08 | [查看] [删除]`

### 7.4 ReportDetail.vue —— 周报详情（保留）

保留原文件预览与 report_scores 评分展示。

### 7.5 WeChatDataUpload.vue —— 企业微信数据上传（新增）

- 考勤数据上传：企业微信「上下班打卡_日报_YYYYMMDD-YYYYMMDD.xlsx」
- 聊天记录上传：企业微信聊天记录导出 Excel
- 展示：本次上传统计（已匹配 / 未匹配人数）

### 7.6 Config.vue —— 系统设置页改造

| 区块 | 调整 |
|------|------|
| 评分维度 / 等级阈值 | **移除** |
| AI 连接状态 | 保留 |
| 提示词管理 | **3 个大文本框**：周报 / 考勤 / 沟通 |
| 权重 | **三项权重**（report:1 / attendance:1 / chat:1） |
| 部门管理 / 人员管理 | 保留 |

### 7.7 Dashboard.vue —— 仪表盘

- 统计卡片：本周参与评分人数 / 本周平均总分 / 待上传人数 / 被人工修改次数
- 图表：综合得分 Top5 / Bottom5，部门平均分对比，周趋势图

### 7.8 前端 API 扩展（`frontend/src/api/index.js`）

```js
export const weeklySummaryAPI = { upload: (file, authorName) => { /* FormData POST */ } };
export const attendanceAPI    = { upload: (file) => { /* FormData POST */ } };
export const chatAPI          = { upload: (file) => { /* FormData POST */ } };
export const aggregateAPI     = {
  list: (params) => api.get('/api/v1/weekly-aggregates', { params }),
  update: (id, data) => api.put(`/api/v1/weekly-aggregates/${id}`, data),
  restoreAI: (id) => api.post(`/api/v1/weekly-aggregates/${id}/restore-ai`),
};
```

---

## 8. 测试用例

### 8.1 后端单元测试

| # | 用例 | 预期 |
|---|------|------|
| 1 | `auto_aggregate`（三源齐全：周报 + 考勤 + 聊天/小结） | `composite_score` 与三项之和一致 |
| 2 | `auto_aggregate`（只有周报，其他为空） | 其他两项为 NULL，`composite_score = report_score` |
| 3 | 管理员 PUT 修改 `report_score` 为 99 | `manual_override.report_score = true`，`composite_score` 按新值 + 另两项求和刷新 |
| 4 | PUT 修改 `composite_score` 为固定值 | 后端拒绝（总分只读） |
| 5 | OCR 解析示例一周小结图片 | 能正确识别「姓名」和「处理工作会话次数」 |
| 6 | 解析企业微信打卡 Excel | 每条记录包含 `check_in_location` / `check_out_location` |
| 7 | 系统设置保存「三项权重 = [1,1,1]」 | GET /config 返回 {"report":1,"attendance":1,"chat":1}；auto_aggregate 使用该权重求和 |

### 8.2 前端冒烟测试

| # | 场景 | 期望 |
|---|------|------|
| 1 | 员工首页上传一周小结图片 | OCR 识别姓名 → 返回本周综合得分 → 页面展示 |
| 2 | 管理员上传考勤 Excel | 考勤记录入库，周评列表对应员工的「考勤分」出现 |
| 3 | 管理员在周评列表双击「考勤分」→ 输入新值保存 | 单元格更新；「总分」随之更新 |
| 4 | 管理员修改「周报评分提示词」并保存 | 下次新的周报 AI 评分使用新提示词 |
| 5 | 管理员点击某行「查看周报」 | 跳转到周报详情页，文件可下载 |
| 6 | 管理员在周评列表点击删除 | 移除该周周报，auto_aggregate 刷新综合得分 |
| 7 | 管理员双击「总分」单元格 | 弹不可修改提示，不发起请求 |

---

**确认后按文档推进开发。`docs/PR_v3_考勤评分系统.md` 为最终规格。**
