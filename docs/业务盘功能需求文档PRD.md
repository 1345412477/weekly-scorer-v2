# 业务盘功能需求文档 PRD

## 一、项目背景与目标

### 1.1 项目背景
当前周报评分系统已实现个人周报的上传、AI评分和数据聚合功能，但缺少**部门级别的整体工作事项汇总与展示**能力。管理层需要一个能够快速浏览各部门上周和本周工作重点的视图，以便掌握公司整体业务进展。

### 1.2 项目目标
- 新增「业务盘」功能页面，按部门维度展示工作事项
- 通过 AI 自动总结各部门上周工作回顾和本周工作重点
- 提供重点关注标记功能，便于管理层聚焦关键事项
- 支持抽屉式详情展开，查看部门人员和详细事项
- 将业务盘提示词纳入系统设置的提示词管理体系

### 1.3 目标用户
- 公司管理层（CEO、部门总监等）
- 人力资源部门
- 行政管理人员

---

## 二、功能需求详细描述

### 2.1 导航入口
- **位置**：左侧导航栏，「仪表盘」下方
- **名称**：业务盘
- **图标**：建议使用 `pi pi-briefcase` 或 `pi pi-folder`
- **权限**：仅管理员可访问

### 2.2 业务盘主页面

#### 2.2.1 页面布局
- 页面顶部：标题「业务盘」+ 周次选择器（默认当前周）
- 主体区域：部门卡片网格布局（响应式，默认 3 列）
- 每个部门以「长方块」卡片形式展示

#### 2.2.2 部门卡片（长方块）
每个部门卡片包含以下信息：

| 区域 | 内容 | 说明 |
|------|------|------|
| 顶部 | 部门名称 | 加粗显示，可点击标记为重点关注 |
| 中部-上 | 上周工作事项 | AI 总结的 3-5 条核心事项，每条可点击加粗标记重点 |
| 中部-下 | 本周工作事项 | AI 总结的 3-5 条核心事项，每条可点击加粗标记重点 |
| 底部 | 人员数量 / 状态 | 显示部门人数和汇总状态（已生成/生成中） |

#### 2.2.3 重点关注交互
- 点击部门名称：标记/取消标记该部门为「重点关注」，卡片边框高亮
- 点击单条事项文字：标记/取消标记该事项为「重点」，文字加粗 + 星标图标
- 重点关注状态持久化存储，刷新页面后保持

#### 2.2.4 抽屉详情
- **触发方式**：点击部门卡片的空白区域（非文字区域）
- **抽屉方向**：从右侧滑出
- **抽屉宽度**：约 50% 屏幕宽度
- **抽屉内容**：
  - 部门名称 + 描述
  - 上周工作事项（完整列表，含每条事项的负责人）
  - 本周工作事项（完整列表，含每条事项的负责人）
  - 涉及人员列表（姓名 + 职位）
  - 重新生成按钮（手动触发 AI 重新总结）

### 2.3 AI 总结功能

#### 2.3.1 数据来源
- **上周工作回顾**：基于该部门所有员工上周提交的周报内容
- **本周工作重点**：基于该部门所有员工本周提交的周报内容

#### 2.3.2 总结要求
- 按周报中提及的工作事项进行总结归类
- 每个部门总结 3-5 条核心事项
- 每条事项尽量具体，避免空泛
- 识别跨成员的共同项目/事项进行合并
- 标注每条事项的主要负责人（可多人）

#### 2.3.3 生成时机
- **手动触发**：管理员在页面点击「生成」按钮，触发所有部门的 AI 总结
- 后续可考虑接入定时任务实现自动生成（本期不实现）

### 2.4 提示词管理

#### 2.4.1 配置位置
系统设置 → 三项评分 Prompt 模板下方，新增「业务盘总结 Prompt」板块

#### 2.4.2 配置项
- **业务盘总结提示词**：用于 AI 总结部门工作事项的系统提示词
- **默认值**：内置一套经过优化的默认提示词
- **支持变量**：`{department}`（部门名称）、`{week_label}`（周次）、`{reports}`（周报内容汇总）

#### 2.4.3 保存与生效
- 提示词修改后即时保存
- 下次 AI 总结时自动使用新提示词
- 提供「恢复默认」按钮

---

## 三、技术方案

### 3.1 技术栈
- **后端**：Python 3.10+ / FastAPI / SQLAlchemy (Async)
- **前端**：Vue 3 + PrimeVue 4 + Vite
- **数据库**：SQLite
- **AI 模型**：复用现有 AI 评分通道（MiMo / 豆包 / DeepSeek）

### 3.2 后端架构设计

#### 3.2.1 新增数据模型

**DepartmentSummary（部门周总结表）**
```
- id: String (UUID, 主键)
- department_id: String (部门ID)
- department_name: String (部门名称，冗余)
- week_start: Date (周开始日期)
- week_end: Date (周结束日期)
- last_week_summary: JSON (上周工作事项列表)
  [{"content": "事项内容", "highlight": false, "persons": ["张三", "李四"]}]
- this_week_summary: JSON (本周工作事项列表)
  [{"content": "事项内容", "highlight": false, "persons": ["张三", "李四"]}]
- is_department_highlight: Boolean (部门是否重点关注)
- status: String (生成状态: pending/generating/done/failed)
- error_message: Text (失败原因)
- generated_at: DateTime (生成时间)
- created_at: DateTime
- updated_at: DateTime
```

**唯一约束**：`(department_id, week_start)`

#### 3.2.2 新增 API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/business-dashboard` | 获取业务盘数据（所有部门当周总结） |
| GET | `/api/v1/business-dashboard/{dept_id}` | 获取单个部门的详细总结 |
| POST | `/api/v1/business-dashboard/generate` | 触发所有部门的 AI 总结 |
| POST | `/api/v1/business-dashboard/{dept_id}/generate` | 触发单个部门的 AI 重新总结 |
| PATCH | `/api/v1/business-dashboard/{dept_id}/highlight` | 更新部门/事项的重点关注状态 |

#### 3.2.3 服务层设计

**business_summary_service.py**
- `generate_all_department_summaries(week_start, week_end)`: 生成所有部门总结
- `generate_department_summary(dept_id, week_start, week_end)`: 生成单个部门总结
- `collect_department_reports(dept_id, week_start, week_end)`: 收集部门周报数据
- `call_ai_summary(department, reports, prompt)`: 调用 AI 进行总结
- `parse_ai_summary(raw_text)`: 解析 AI 返回的结构化数据
- `update_highlight(dept_id, summary_type, item_index, highlight)`: 更新重点关注状态

### 3.3 前端架构设计

#### 3.3.1 新增页面
- `views/BusinessDashboard.vue` - 业务盘主页面

#### 3.3.2 新增组件
- `components/DepartmentCard.vue` - 部门卡片组件
- `components/DepartmentDrawer.vue` - 部门详情抽屉组件

#### 3.3.3 路由配置
- 路径：`/admin/business-dashboard`
- 名称：`BusinessDashboard`
- 元信息：`{ title: '业务盘', requiresAdmin: true }`

#### 3.3.4 API 封装
在 `api/index.js` 中新增 `businessAPI` 对象：
```javascript
export const businessAPI = {
  list: (params) => api.get('/business-dashboard', { params }),
  get: (deptId) => api.get(`/business-dashboard/${deptId}`),
  generateAll: () => api.post('/business-dashboard/generate'),
  generateDept: (deptId) => api.post(`/business-dashboard/${deptId}/generate`),
  updateHighlight: (deptId, data) => api.patch(`/business-dashboard/${deptId}/highlight`, data),
}
```

### 3.4 数据库迁移方案

#### 3.4.1 新增表
- 创建 `department_summaries` 表
- 创建相关索引：`idx_dept_summary_week`、`idx_dept_summary_dept`

#### 3.4.2 配置表扩展
在 `ScoringConfig` 模型中新增字段：
- `business_summary_prompt: Text` - 业务盘总结提示词

---

## 四、开发计划与里程碑

### 4.1 开发阶段划分

| 阶段 | 内容 | 预计工作量 |
|------|------|-----------|
| Phase 1 | 数据库模型 + 后端 API 框架 | 2h |
| Phase 2 | AI 总结服务（提示词 + 调用 + 解析） | 3h |
| Phase 3 | 后端 API 完整实现 | 2h |
| Phase 4 | 前端页面 + 组件开发 | 4h |
| Phase 5 | 提示词管理配置集成 | 1.5h |
| Phase 6 | 联调测试 + Bug 修复 | 2h |
| **合计** | | **约 14.5h** |

### 4.2 详细任务拆解

#### Phase 1：数据模型与基础框架
- [x] 新增 `DepartmentSummary` 数据模型
- [x] 扩展 `ScoringConfig` 模型，添加 `business_summary_prompt` 字段
- [x] 创建 `business_summary.py` API 路由文件
- [x] 在 `main.py` 中注册新路由
- [x] 数据库迁移脚本（create_all 自动创建）

#### Phase 2：AI 总结服务
- [x] 编写默认业务盘总结提示词
- [x] 实现 `collect_department_reports` 函数
- [x] 实现 AI 总结调用函数（复用 ai_scorer 的 client）
- [x] 实现 AI 返回结果解析函数
- [x] 异常处理与重试机制

#### Phase 3：后端 API 完整实现
- [x] GET /business-dashboard（列表查询）
- [x] GET /business-dashboard/{dept_id}（详情查询）
- [x] POST /business-dashboard/generate（全量生成）
- [x] POST /business-dashboard/{dept_id}/generate（单部门生成）
- [x] PATCH /business-dashboard/{dept_id}/highlight（更新重点）
- [x] 配置 API 扩展（读取/保存业务盘提示词）

#### Phase 4：前端页面开发
- [x] 新增路由配置
- [x] 更新左侧导航栏（添加业务盘入口）
- [x] DepartmentCard 组件开发
- [x] DepartmentDrawer 组件开发
- [x] BusinessDashboard 主页面开发
- [x] 周次选择器集成
- [x] 重点关注交互实现
- [x] 加载状态与空状态处理

#### Phase 5：提示词管理集成
- [x] 后端：配置 API 支持 business_summary_prompt 字段
- [x] 前端：Config.vue 新增业务盘提示词板块
- [x] 默认提示词生成功能
- [x] 保存与恢复默认功能

#### Phase 6：测试与优化
- [x] 端到端功能测试（后端 API 全接口测试通过，前端页面功能验证通过）
- [x] AI 总结效果调优（复用现有 AI 评分通道，提示词可配置）
- [x] 边界情况处理（无周报返回空数组、部门不存在返回 404、空部门卡片正常展示）
- [x] 性能优化（JSON 字段 nullable、数据库索引已创建）
- [x] Bug 修复：修复 `write_operation_log` 参数传递错误（`detail` 字典被错误传入 `request` 位置参数）

---

## 五、风险与应对

### 5.1 技术风险
| 风险 | 影响 | 应对措施 |
|------|------|---------|
| AI 总结质量不稳定 | 总结结果不符合预期 | 提供手动编辑功能（后续迭代）；优化提示词 |
| 多部门同时生成 API 超时 | 前端请求失败 | 后端改为异步任务，前端轮询状态 |
| 周报内容过长导致 token 超限 | AI 调用失败 | 对周报内容进行摘要截断，优先保留重点 |

### 5.2 业务风险
| 风险 | 影响 | 应对措施 |
|------|------|---------|
| 部门周报内容少，总结无意义 | 功能价值降低 | 空状态友好提示；支持手动编辑补充 |
| 重点关注数据量大 | 页面性能下降 | 分页加载；虚拟滚动（后续优化） |

---

## 六、成功指标

1. **功能完整性**：所有需求点 100% 实现
2. **AI 总结质量**：人工抽查 80% 以上的总结被认为有价值
3. **性能指标**：页面首屏加载 < 2s，单部门 AI 总结 < 30s
4. **用户体验**：操作流畅，无明显 Bug

---

## 七、后续迭代方向（非本期）

1. 支持手动编辑 AI 总结的事项内容
2. 支持事项拖拽排序
3. 部门间事项关联与依赖关系展示
4. 导出为 PDF / 图片
5. 业务盘数据的历史趋势对比
