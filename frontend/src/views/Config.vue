<template>
  <div class="config-page page-content">
    <!-- AI 模型状态 -->
    <section class="panel-card status-card">
      <header class="panel-header">
        <div class="header-left">
          <div class="status-icon"><i class="pi pi-bolt"></i></div>
          <div class="status-text">
            <span class="status-provider">{{ providerName }}</span>
            <span class="status-model"><i class="pi pi-box"></i> {{ aiStatus.model || '模型加载中...' }}</span>
            <span class="status-check-time" v-if="aiStatus.checkedAt">上次检测：{{ formatBeijingTimeShort(aiStatus.checkedAt) }}<span v-if="aiStatus.cached"> · 缓存</span></span>
          </div>
        </div>
        <div class="header-right">
          <div class="status-indicator">
            <span :class="['indicator-dot', { ok: aiStatus.success === true, fail: aiStatus.success === false }]"></span>
            <span class="indicator-text">
              {{ aiStatus.success === true ? '已连接' : aiStatus.success === false ? '连接失败' : '检测中...' }}
            </span>
          </div>
          <Button icon="pi pi-refresh" text severity="secondary" size="small" @click="checkAiStatus(true)" class="refresh-btn" v-tooltip.bottom="'重新检测模型（会产生少量 token 消耗）'" />
        </div>
      </header>
    </section>

    <!-- 提示词设置 -->
    <section class="panel-card collapsible" :class="{ collapsed: !expanded.prompts }">
      <header class="panel-header clickable" @click="toggle('prompts')">
        <div class="header-left">
          <h3>提示词设置</h3>
          <p class="panel-desc">配置各项 AI 评分和总结的提示词模板，评分标准与分数范围由提示词决定</p>
        </div>
        <div class="header-right">
          <i :class="['chevron', 'pi', expanded.prompts ? 'pi-chevron-up' : 'pi-chevron-down']"></i>
        </div>
      </header>
      <div class="panel-body" v-show="expanded.prompts">
        <!-- 周报评分提示词 -->
        <div class="prompt-sub-section">
          <div class="prompt-sub-header">
            <span class="prompt-sub-title">周报评分提示词 <span class="required-mark">*</span></span>
            <Button label="重置默认" icon="pi pi-refresh" text size="small" @click="resetReportPrompt" />
          </div>
          <div class="prompt-block">
            <div class="prompt-block-head">
              <span class="prompt-field-label">权重</span>
              <InputNumber v-model.number="weights.report" :min="0" :step="1" size="small" :showButtons="false" class="weight-input" />
            </div>
            <Textarea v-model="reportPrompt" rows="6" class="prompt-area" placeholder="请输入周报评分提示词...（建议包含评分维度、标准与分数范围）" autoResize />
          </div>
        </div>

        <!-- 考勤评分提示词 -->
        <div class="prompt-sub-section">
          <div class="prompt-sub-header">
            <span class="prompt-sub-title">考勤评分提示词 <span class="required-mark">*</span></span>
            <Button label="重置默认" icon="pi pi-refresh" text size="small" @click="resetAttendancePrompt" />
          </div>
          <div class="prompt-block">
            <div class="prompt-block-head">
              <span class="prompt-field-label">权重</span>
              <InputNumber v-model.number="weights.attendance" :min="0" :step="1" size="small" :showButtons="false" class="weight-input" />
            </div>
            <Textarea v-model="attendancePrompt" rows="6" class="prompt-area" placeholder="请输入考勤评分提示词...（例如工作时长、迟到、异常、加班等标准）" autoResize />
          </div>
        </div>

        <!-- 会话评分提示词 -->
        <div class="prompt-sub-section">
          <div class="prompt-sub-header">
            <span class="prompt-sub-title">会话评分提示词 <span class="required-mark">*</span></span>
            <Button label="重置默认" icon="pi pi-refresh" text size="small" @click="resetChatPrompt" />
          </div>
          <p class="prompt-sub-desc">用于会话记录评分（满分80分），包含敏感词和响应时间扣分规则</p>
          <div class="prompt-block">
            <div class="prompt-block-head">
              <span class="prompt-field-label">权重</span>
              <InputNumber v-model.number="weights.chat" :min="0" :step="1" size="small" :showButtons="false" class="weight-input" />
            </div>
            <Textarea v-model="chatPrompt" rows="6" class="prompt-area" placeholder="请输入会话评分提示词...（包含会话记录敏感词/响应时间规则）" autoResize />
          </div>
        </div>

        <!-- 一周小结评分提示词 -->
        <div class="prompt-sub-section">
          <div class="prompt-sub-header">
            <span class="prompt-sub-title">一周小结评分提示词 <span class="required-mark">*</span></span>
            <Button label="重置默认" icon="pi pi-refresh" text size="small" @click="resetSummaryPrompt" />
          </div>
          <p class="prompt-sub-desc">用于一周小结独立评分（满分20分），包含工作会话次数和最晚时间扣分规则</p>
          <Textarea v-model="summaryPrompt" rows="6" class="prompt-area" placeholder="请输入一周小结评分提示词...（20分制，包含工作会话次数和最晚时间扣分规则）" autoResize />
        </div>

        <!-- OCR 一周小结提示词 -->
        <div class="prompt-sub-section">
          <div class="prompt-sub-header">
            <span class="prompt-sub-title">OCR 一周小结提示词 <span class="required-mark">*</span></span>
            <Button label="重置默认" icon="pi pi-refresh" text size="small" @click="resetOcrPrompt" />
          </div>
          <p class="prompt-sub-desc">用于 AI 从一周小结图片中提取工作会话次数、最晚时间等结构化字段</p>
          <Textarea v-model="ocrPrompt" rows="6" class="prompt-area" placeholder="请输入 OCR 一周小结提示词..." autoResize />
        </div>

        <!-- 业务盘总结提示词 -->
        <div class="prompt-sub-section">
          <div class="prompt-sub-header">
            <span class="prompt-sub-title">业务盘总结提示词</span>
            <Button label="重置默认" icon="pi pi-refresh" text size="small" @click="resetBusinessPrompt" />
          </div>
          <p class="prompt-sub-desc">用于 AI 总结各部门每周工作事项，支持变量：{department}（部门名称）、{week_label}（周次）、{reports}（周报内容汇总）</p>
          <Textarea v-model="businessSummaryPrompt" rows="12" class="prompt-area" placeholder="请输入业务盘总结提示词..." autoResize />
        </div>

        <div class="weights-sum-row">
          <span class="weights-label">综合得分 = 周报分 × {{ weights.report }} + 考勤分 × {{ weights.attendance }} + 沟通分 × {{ weights.chat }}</span>
        </div>
      </div>
    </section>

    <!-- AI 模型管理 -->
    <section class="panel-card collapsible" :class="{ collapsed: !expanded.aiModels }">
      <header class="panel-header clickable" @click="toggle('aiModels')">
        <div class="header-left">
          <h3>AI 模型管理</h3>
          <p class="panel-desc">自定义模型 ID、API Key 和 Base URL，支持新增、切换和删除模型</p>
        </div>
        <div class="header-right">
          <Button label="添加模型" icon="pi pi-plus" text size="small" @click.stop="openAddModel" />
          <i :class="['chevron', 'pi', expanded.aiModels ? 'pi-chevron-up' : 'pi-chevron-down']"></i>
        </div>
      </header>
      <div class="panel-body" v-show="expanded.aiModels">
        <div class="model-list">
          <div v-if="aiModels.length === 0" class="empty-line">暂无自定义模型，请点击右上角"添加模型"</div>
          <div v-for="m in aiModels" :key="m.id" class="model-row" :class="{ 'model-active': m.is_active }">
            <div class="model-info">
              <div class="model-name-row">
                <span class="model-name">{{ m.name }}</span>
                <Tag v-if="m.is_active" value="当前使用" severity="success" class="model-active-tag" />
                <Tag v-if="m.is_vision" value="视觉" severity="info" class="model-vision-tag" />
              </div>
              <div class="model-meta">
                <span class="model-provider">{{ m.provider }}</span>
                <span class="model-sep">·</span>
                <span class="model-id-text">{{ m.model_id }}</span>
              </div>
              <div class="model-meta">
                <span class="model-key-text">Key: {{ m.api_key_masked }}</span>
              </div>
              <div class="model-meta">
                <span class="model-url-text">{{ m.base_url }}</span>
              </div>
            </div>
            <div class="model-actions">
              <Button v-if="!m.is_active" label="切换" icon="pi pi-check" size="small" severity="success" outlined @click="activateModel(m.id)" />
              <Button label="测试" icon="pi pi-bolt" size="small" severity="info" outlined @click="testModel(m)" />
              <Button label="编辑" icon="pi pi-pencil" size="small" text @click="editModel(m)" />
              <Button label="删除" icon="pi pi-trash" size="small" severity="danger" text @click="deleteModel(m)" :disabled="m.is_active" v-tooltip.top="m.is_active ? '不能删除当前使用的模型' : ''" />
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 定时评分设置 -->
    <section class="panel-card schedule-panel collapsible" :class="{ collapsed: !expanded.schedule }">
      <header class="panel-header clickable" @click="toggle('schedule')">
        <div class="header-left">
          <h3>定时聚合评分</h3>
          <p class="panel-sub">在配置时间自动聚合考勤分与沟通分。员工提交的周报会立即 AI 评分，无需等待。</p>
        </div>
        <div class="header-right">
          <div class="schedule-toggle-wrap" @click.stop>
            <InputSwitch v-model="schedule.enabled" :disabled="scheduleSaving" />
            <span class="schedule-status">{{ schedule.enabled ? '已启用' : '已禁用' }}</span>
          </div>
          <i :class="['chevron', 'pi', expanded.schedule ? 'pi-chevron-up' : 'pi-chevron-down']"></i>
        </div>
      </header>
      <div class="panel-body" v-show="expanded.schedule">
        <div class="schedule-row">
          <label class="field-label">运行频率</label>
          <Dropdown
            v-model="schedule.recurrence"
            :options="[{ label: '每天', value: 'daily' }, { label: '每周（按星期）', value: 'weekly' }]"
            optionLabel="label"
            optionValue="value"
            :disabled="!schedule.enabled || scheduleSaving"
            class="schedule-select"
            placeholder="选择频率"
          />
        </div>

        <div class="schedule-row">
          <label class="field-label">运行时间</label>
          <div class="time-inputs">
            <InputNumber v-model.number="schedule.hour" :min="0" :max="23" :step="1" :showButtons="false" size="large" :disabled="!schedule.enabled" />
            <span class="time-sep">:</span>
            <InputNumber v-model.number="schedule.minute" :min="0" :max="59" :step="1" :showButtons="false" size="large" :disabled="!schedule.enabled" />
          </div>
        </div>

        <div v-if="schedule.recurrence === 'weekly'" class="schedule-row">
          <label class="field-label">运行日</label>
          <div class="weekday-toggles">
            <button
              v-for="(label, idx) in WEEKDAY_LABELS"
              :key="idx"
              type="button"
              class="weekday-btn"
              :class="{ 'selected': isWeekdaySelected(idx), 'disabled': !schedule.enabled }"
              :disabled="!schedule.enabled"
              @click="toggleWeekday(idx)"
            >
              {{ label }}
            </button>
          </div>
        </div>

        <div class="schedule-row schedule-hint-row">
          <span class="schedule-hint">
            <template v-if="schedule.recurrence === 'daily'">
              系统会在每天 {{ String(schedule.hour).padStart(2, '0') }}:{{ String(schedule.minute).padStart(2, '0') }} 自动聚合本周的考勤与沟通数据
            </template>
            <template v-else>
              系统会在每周 {{ formatWeekdayHint() }} {{ String(schedule.hour).padStart(2, '0') }}:{{ String(schedule.minute).padStart(2, '0') }} 自动聚合本周的考勤与沟通数据
            </template>
          </span>
        </div>

        <div v-if="scheduleMsg" class="schedule-msg" :class="scheduleMsg.type">
          <i :class="scheduleMsg.type === 'success' ? 'pi pi-check-circle' : 'pi pi-exclamation-triangle'"></i>
          <span>{{ scheduleMsg.text }}</span>
        </div>
      </div>
    </section>

    <!-- 提交期限设置 -->
    <section class="panel-card collapsible" :class="{ collapsed: !expanded.deadline }">
      <header class="panel-header clickable" @click="toggle('deadline')">
        <div class="header-left">
          <h3>提交期限设置</h3>
          <p class="panel-desc">设置每周周报提交的截止时间，超过正常期限未提交视为迟交，超过补交期限提交视为补交（记 0 分）</p>
        </div>
        <div class="header-right">
          <i :class="['chevron', 'pi', expanded.deadline ? 'pi-chevron-up' : 'pi-chevron-down']"></i>
        </div>
      </header>
      <div class="panel-body" v-show="expanded.deadline">
        <div class="deadline-grid">
          <div class="deadline-item">
            <label class="field-label">正常提交期限（迟交起点）</label>
            <div class="deadline-input-row">
              <span class="deadline-prefix">本周</span>
              <Dropdown v-model="submissionWeekday" :options="deadlineWeekdayOptions" optionLabel="label" optionValue="value" class="deadline-picker" />
              <DatePicker v-model="submissionTime" timeOnly :stepMinute="15" hourFormat="24" class="deadline-picker" />
            </div>
            <span class="deadline-hint">例：本周日 15:00 之前提交为正常，之后提交视为迟交（扣 5 分）</span>
          </div>
          <div class="deadline-item">
            <label class="field-label">补交期限</label>
            <div class="deadline-input-row">
              <Dropdown v-model="lateWeekOffset" :options="deadlineWeekOffsetOptions" optionLabel="label" optionValue="value" class="deadline-picker" />
              <Dropdown v-model="lateWeekday" :options="deadlineWeekdayOptions" optionLabel="label" optionValue="value" class="deadline-picker" />
              <DatePicker v-model="lateTime" timeOnly :stepMinute="15" hourFormat="24" class="deadline-picker" />
            </div>
            <span class="deadline-hint">例：下周日 15:00 之前仍可补交，超过后提交记 0 分</span>
          </div>
        </div>
        <div class="deadline-summary">
          <i class="pi pi-info-circle"></i>
          <span>迟交期限：{{ formatDeadlineHint(submissionDeadlineHours) }} | 补交期限：{{ formatDeadlineHint(lateDeadlineHours) }}</span>
        </div>
      </div>
    </section>

    <!-- 人员与部门管理 -->
    <div class="grid-wrap">
      <section class="panel-card">
        <header class="panel-header">
          <div class="header-left">
            <h3>部门管理</h3>
          </div>
        </header>
        <div class="panel-body">
          <div class="add-row">
            <InputText v-model="newDeptName" placeholder="部门名称" class="grow-input" />
            <InputText v-model="newDeptDesc" placeholder="部门描述（可选）" class="grow-input" />
            <Button label="添加" icon="pi pi-plus" @click="addDepartment" :disabled="!newDeptName.trim()" />
          </div>

          <div class="item-list">
            <div v-if="!departments.length" class="empty-line">暂无部门数据</div>
            <div v-for="dept in departments" :key="dept.id" class="item-row">
              <template v-if="editingDeptId === dept.id">
                <InputText v-model="editingDeptName" placeholder="部门名称" class="grow-input" />
                <InputText v-model="editingDeptDesc" placeholder="部门描述" class="grow-input" />
                <Button icon="pi pi-check" @click="saveEditDepartment(dept.id)" size="small" :disabled="!editingDeptName.trim()" />
                <Button icon="pi pi-times" severity="secondary" text @click="cancelEditDepartment" size="small" />
              </template>
              <template v-else>
                <div class="item-info">
                  <span class="item-title">{{ dept.name }}</span>
                  <span class="item-sub">{{ dept.description || '无描述' }}</span>
                </div>
                <div class="item-actions">
                  <Button icon="pi pi-pencil" text rounded size="small" @click="startEditDepartment(dept)" />
                  <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="deleteDepartment(dept.id)" />
                </div>
              </template>
            </div>
          </div>
        </div>
      </section>

      <section class="panel-card">
        <header class="panel-header">
          <div class="header-left">
            <h3>人员管理</h3>
          </div>
        </header>
        <div class="panel-body">
          <div class="add-row">
            <InputText v-model="newPersonName" placeholder="姓名" class="grow-input" />
            <Dropdown v-model="newPersonDept" :options="departments" optionLabel="name" placeholder="选择部门" showClear class="grow-input" />
            <InputText v-model="newPersonPosition" placeholder="职位（可选）" class="grow-input" />
            <Button label="添加" icon="pi pi-plus" @click="addPerson" :disabled="!newPersonName.trim()" />
          </div>

          <div class="item-list">
            <div v-if="!persons.length" class="empty-line">暂无人员数据</div>
            <div v-for="person in persons" :key="person.id" class="item-row">
              <template v-if="editingPersonId === person.id">
                <InputText v-model="editingPersonName" placeholder="姓名" class="grow-input" />
                <Dropdown v-model="editingPersonDept" :options="departments" optionLabel="name" placeholder="部门" showClear class="grow-input" />
                <InputText v-model="editingPersonPosition" placeholder="职位" class="grow-input" />
                <Button icon="pi pi-check" @click="saveEditPerson(person.id)" size="small" :disabled="!editingPersonName.trim()" />
                <Button icon="pi pi-times" severity="secondary" text @click="cancelEditPerson" size="small" />
              </template>
              <template v-else>
                <div class="item-info">
                  <span class="item-title">{{ person.name }}</span>
                  <span class="item-sub">{{ person.department_name || '未分配部门' }}{{ person.position ? ' · ' + person.position : '' }}</span>
                </div>
                <div class="item-actions">
                  <Button icon="pi pi-pencil" text rounded size="small" @click="startEditPerson(person)" />
                  <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="deletePerson(person.id)" />
                </div>
              </template>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 底部固定操作栏 -->
    <div class="config-sticky-bar">
      <span class="config-sticky-hint">修改配置后请点击保存才能生效</span>
      <div class="config-sticky-buttons">
        <Button label="重置默认" severity="secondary" outlined @click="resetConfig" />
        <Button label="保存配置" icon="pi pi-save" @click="saveConfig" :loading="saving" />
      </div>
    </div>

    <!-- AI 模型添加/编辑弹窗 -->
    <Dialog v-model:visible="showAddModel" :header="editingModelId ? '编辑模型' : '添加模型'" :modal="true" :style="{ width: '520px' }" :closable="true">
      <div class="model-form">
        <div class="form-field">
          <label class="form-label">模型名称 <span class="required">*</span></label>
          <InputText v-model="modelForm.name" placeholder="例如：豆包 Pro、DeepSeek V3" class="form-input" />
        </div>
        <div class="form-field">
          <label class="form-label">厂商 <span class="required">*</span></label>
          <Dropdown v-model="modelForm.provider" :options="providerOptions" optionLabel="label" optionValue="value" placeholder="选择厂商" class="form-input" />
        </div>
        <div class="form-field">
          <label class="form-label">模型 ID <span class="required">*</span></label>
          <InputText v-model="modelForm.model_id" placeholder="例如：doubao-seed-2.0-pro、deepseek-chat" class="form-input" />
        </div>
        <div class="form-field">
          <label class="form-label">API Key <span class="required">*</span></label>
          <InputText v-model="modelForm.api_key" :placeholder="editingModelId ? '留空则不修改' : '请输入 API Key'" class="form-input" type="password" />
        </div>
        <div class="form-field">
          <label class="form-label">Base URL <span class="required">*</span></label>
          <InputText v-model="modelForm.base_url" placeholder="例如：https://ark.cn-beijing.volces.com/api/v3" class="form-input" />
        </div>
        <div class="form-field-row">
          <label class="form-checkbox">
            <InputSwitch v-model="modelForm.is_active" />
            <span>设为当前使用模型</span>
          </label>
          <label class="form-checkbox">
            <InputSwitch v-model="modelForm.is_vision" />
            <span>视觉模型（支持图片识别）</span>
          </label>
        </div>
      </div>
      <template #footer>
        <Button label="取消" severity="secondary" text @click="showAddModel = false" />
        <Button :label="editingModelId ? '保存' : '添加'" icon="pi pi-check" @click="saveModel" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { configAPI, departmentAPI, personAPI, reportAPI, aggregateAPI, aiModelAPI } from '../api'
import { useDataRefresh, getConfigEvents } from '../composables/useDataRefresh'
import { useDataOperation } from '../composables/useDataOperation'
import { DataEventType, emitDataChanged } from '../utils/dataEvents'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputSwitch from 'primevue/inputswitch'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import DatePicker from 'primevue/datepicker'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const { execute } = useDataOperation()

// 各板块展开状态
const expanded = reactive({
  status: true,
  prompts: false,
  businessPrompt: false,
  aiModels: false,
  schedule: false,
  deadline: false,
})
function toggle(key) {
  if (key in expanded) expanded[key] = !expanded[key]
}

const saving = ref(false)
const testing = ref(false)
const aiStatus = ref({ provider: '', model: '', success: null, checkedAt: '', cached: false, ttl_remaining: 0 })
const promptTemplate = ref('')
// v3 三项提示词 + 三项权重
const reportPrompt = ref('')
const attendancePrompt = ref('')
const chatPrompt = ref('')
const summaryPrompt = ref('')
const ocrPrompt = ref('')
const businessSummaryPrompt = ref('')
const weights = ref({ report: 1, attendance: 1, chat: 1 })
// 定时评分设置
const schedule = ref({
  enabled: false,
  hour: 3,
  minute: 0,
  recurrence: 'daily',          // 'daily' / 'weekly'
  weekdays: [0, 1, 2, 3, 4],    // 0=周一 ... 6=周日
})
const WEEKDAY_LABELS = ['一', '二', '三', '四', '五', '六', '日']
const scheduleSaving = ref(false)
const scheduleMsg = ref(null)
const testFile = ref(null)
const testFileInput = ref(null)
const testResult = ref(null)

// 提交期限设置（按“周几 + 时间”展示，底层仍以“周一 00:00 起算的小时数”存储）
const submissionDeadlineHours = ref(159)  // 默认本周日 15:00
const lateDeadlineHours = ref(327)        // 默认下周日 15:00
const submissionWeekday = ref(6)
const submissionTime = ref(null)
const lateWeekOffset = ref(1)
const lateWeekday = ref(6)
const lateTime = ref(null)

const DEADLINE_WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
const DEADLINE_WEEK_OFFSET_LABELS = ['本周', '下周', '下下周']
const deadlineWeekdayOptions = DEADLINE_WEEKDAY_LABELS.map((label, value) => ({ label, value }))
const deadlineWeekOffsetOptions = DEADLINE_WEEK_OFFSET_LABELS.map((label, value) => ({ label, value }))

function makeTime(hour, minute) {
  const d = new Date(2000, 0, 1, 0, 0, 0, 0)
  d.setHours(hour, minute, 0, 0)
  return d
}

function hoursToDeadlineParts(hours) {
  const total = Math.max(0, Number(hours) || 0)
  const weekOffset = Math.floor(total / 168)
  const rem = total - weekOffset * 168
  const weekday = Math.min(6, Math.floor(rem / 24))
  const minutes = Math.round((rem - weekday * 24) * 60)
  return { weekOffset, weekday, hour: Math.floor(minutes / 60), minute: minutes % 60 }
}

function deadlinePartsToHours(weekOffset, weekday, hour, minute) {
  return weekOffset * 168 + weekday * 24 + hour + minute / 60
}

function syncDeadlineFromHours() {
  const p = hoursToDeadlineParts(submissionDeadlineHours.value)
  submissionWeekday.value = p.weekday
  submissionTime.value = makeTime(p.hour, p.minute)
  const q = hoursToDeadlineParts(lateDeadlineHours.value)
  lateWeekOffset.value = Math.min(2, q.weekOffset)
  lateWeekday.value = q.weekday
  lateTime.value = makeTime(q.hour, q.minute)
}

function syncDeadlineToHours() {
  const st = submissionTime.value || makeTime(15, 0)
  const lt = lateTime.value || makeTime(15, 0)
  submissionDeadlineHours.value = deadlinePartsToHours(0, submissionWeekday.value, st.getHours(), st.getMinutes())
  lateDeadlineHours.value = deadlinePartsToHours(lateWeekOffset.value, lateWeekday.value, lt.getHours(), lt.getMinutes())
}

function formatDeadlineHint(hours) {
  const p = hoursToDeadlineParts(hours)
  const weekLabel = DEADLINE_WEEK_OFFSET_LABELS[Math.min(2, p.weekOffset)] || `第${p.weekOffset + 1}周`
  return `${weekLabel}${DEADLINE_WEEKDAY_LABELS[p.weekday]} ${String(p.hour).padStart(2, '0')}:${String(p.minute).padStart(2, '0')}`
}

function resetDeadlines() {
  submissionDeadlineHours.value = 159
  lateDeadlineHours.value = 327
  submissionWeekday.value = 6
  submissionTime.value = makeTime(15, 0)
  lateWeekOffset.value = 1
  lateWeekday.value = 6
  lateTime.value = makeTime(15, 0)
}

function resetSchedule() {
  schedule.value = {
    enabled: true,
    hour: 3,
    minute: 0,
    recurrence: 'daily',
    weekdays: [0, 1, 2, 3, 4],
  }
}

watch(
  [submissionWeekday, submissionTime, lateWeekOffset, lateWeekday, lateTime],
  () => { syncDeadlineToHours() }
)

// AI 模型管理
const aiModels = ref([])
const showAddModel = ref(false)
const editingModelId = ref(null)
const modelForm = ref({
  name: '',
  provider: '',
  model_id: '',
  api_key: '',
  base_url: '',
  is_active: false,
  is_vision: false,
})

const providerOptions = [
  { label: '小米 MiMo', value: 'mimo' },
  { label: '豆包 (火山引擎)', value: 'ark' },
  { label: 'DeepSeek', value: 'deepseek' },
  { label: 'OpenAI', value: 'openai' },
  { label: '自定义', value: 'custom' },
]

const departments = ref([])
const persons = ref([])
const newDeptName = ref('')
const newDeptDesc = ref('')
const newPersonName = ref('')
const newPersonDept = ref(null)
const newPersonPosition = ref('')

const editingDeptId = ref(null)
const editingDeptName = ref('')
const editingDeptDesc = ref('')
const editingPersonId = ref(null)
const editingPersonName = ref('')
const editingPersonDept = ref(null)
const editingPersonPosition = ref('')

const providerName = computed(() => {
  const p = aiStatus.value.provider
  if (p === 'mimo') return '小米 MiMo'
  if (p === 'ark') return '豆包 (火山引擎)'
  if (p === 'deepseek') return 'DeepSeek'
  return p || '待检测'
})

function gradeSeverity(g) {
  if (g === '优') return 'success'
  if (g === '良') return 'info'
  if (g === '一般') return 'warn'
  return 'danger'
}

function resetConfig() {
  promptTemplate.value = `# 周报评分系统提示词

## 角色设定
你是一位专业、客观的工作报告评审专家。请根据以下评分维度对员工周报进行综合评估。

## 评分原则
1. 客观公正：基于周报内容进行评价，避免主观臆断
2. 鼓励量化：对有数据支撑、可量化成果的内容给予更高评价
3. 关注闭环：重视"计划→执行→结果"的完整闭环
4. 提供建设性：评语和建议应具体、可操作

## 评分维度

### 1. 工作反馈深度（满分12分，最低分7分）
评估员工对本周工作内容的总结深度和问题分析能力。
- **高分标准（10-12分）**：不仅罗列工作内容，还能深入分析遇到的问题、产生的原因，并提出具体的解决方案或改进思路；有数据支撑或量化成果。
- **中等标准（8-9分）**：对工作内容有基本总结，提及了部分问题但分析不够深入，解决方案较笼统。
- **低分标准（7分）**：仅简单罗列工作内容，缺乏问题分析，未提及遇到的困难或解决思路。

### 2. 进度节点明确（满分10分，最低分6分）
评估员工对项目/任务进度的描述是否清晰、是否有明确的里程碑或时间节点。
- **高分标准（8-10分）**：清晰描述各任务的当前进度（如百分比、完成阶段），标注关键里程碑和预期完成时间，进度描述具体可追踪。
- **中等标准（7分）**：有进度描述但较笼统，如"进行中""已完成部分"，缺少具体时间节点。
- **低分标准（6分）**：未提及进度或进度描述模糊，无法判断任务实际推进情况。

### 3. 计划可行性（满分8分，最低分5分）
评估员工对下周工作计划的描述是否具体、可执行、可验证。
- **高分标准（7-8分）**：下周计划具体明确，包含可量化的目标、清晰的执行步骤和预期交付物，计划合理可落地。
- **中等标准（6分）**：有下周计划但较笼统，如"继续推进XX项目"，缺少具体目标或执行细节。
- **低分标准（5分）**：未提及下周计划，或计划过于空泛无法执行。

### 4. 工作连续性（满分10分，最低分6分）
评估员工本周工作是否承接上周计划，是否形成"计划→执行→结果→新计划"的闭环。
- **高分标准（8-10分）**：本周工作明确承接上周计划，对上周未完成事项有跟进说明，形成完整的工作闭环；新计划与本周结果有逻辑关联。
- **中等标准（7分）**：部分承接上周计划，但对未完成事项缺乏跟进，闭环不够完整。
- **低分标准（6分）**：本周工作与上周计划无明显关联，或完全未提及上周计划的执行情况。

## 评分标准
- 每个维度独立打分，不超过该维度满分
- 综合评分 = 各维度分数直接相加（28-40分）
- 等级划分：优(35-40)、良(31-34)、一般(29-30)、差(28)

## 输出要求
请以 JSON 格式返回评分结果，包含：
- dimension_scores: 各维度得分及评语（含name、score、max、comment）
- total_score: 综合得分（28-40分）
- grade: 等级（优/良/一般/差）
- comment: 总体评语（100字以内）
- suggestion: 改进建议（具体可执行）

## 周报内容
\x7bcontent\x7d`
  reportPrompt.value = `# 周报评分提示词\n\n请根据员工提交的周报在 28-40 分范围进行评分。\n\n## 评分维度\n\n### 1. 工作反馈深度（满分12分，最低分8分）\n评估员工对本周工作内容的总结深度和问题分析能力。\n- **高分标准（12分）**：不仅罗列工作内容，还能深入分析遇到的问题、产生的原因，并提出具体的解决方案或改进思路；有数据支撑或量化成果。\n- **中等标准（10分）**：对工作内容有基本总结，提及了部分问题但分析不够深入，解决方案较笼统。\n- **低分标准（8分）**：仅简单罗列工作内容，缺乏问题分析，未提及遇到的困难或解决思路。\n\n### 2. 进度节点明确（满分11分，最低分7分）\n评估员工对项目/任务进度的描述是否清晰、是否有明确的里程碑或时间节点。\n- **高分标准（11分）**：清晰描述各任务的当前进度（如百分比、完成阶段），标注关键里程碑和预期完成时间，进度描述具体可追踪。\n- **中等标准（9分）**：有进度描述但较笼统，如"进行中""已完成部分"，缺少具体时间节点。\n- **低分标准（7分）**：未提及进度或进度描述模糊，无法判断任务实际推进情况。\n\n### 3. 计划可行性（满分8分，最低分6分）\n评估员工对下周工作计划的描述是否具体、可执行、可验证。\n- **高分标准（8分）**：下周计划具体明确，包含可量化的目标、清晰的执行步骤和预期交付物，计划合理可落地。\n- **中等标准（7分）**：有下周计划但较笼统，如"继续推进XX项目"，缺少具体目标或执行细节。\n- **低分标准（6分）**：未提及下周计划，或计划过于空泛无法执行。\n\n### 4. 工作连续性（满分10分，最低分7分）\n评估员工本周工作是否承接上周计划，是否形成"计划→执行→结果→新计划"的闭环。\n- **高分标准（9分）**：本周工作明确承接上周计划，对上周未完成事项有跟进说明，形成完整的工作闭环；新计划与本周结果有逻辑关联。\n- **中等标准（8分）**：部分承接上周计划，但对未完成事项缺乏跟进，闭环不够完整。\n- **低分标准（7分）**：本周工作与上周计划无明显关联，或完全未提及上周计划的执行情况。\n\n## 等级划分\n- 优：35-40分\n- 良：31-34分\n- 一般：29-30分\n- 差：28分\n\n## 迟交/补交规则\n- 迟交：提交时间超过正常提交期限但未超过补交期限 → 基础分扣 5 分（最低可到 23 分）。\n- 补交：提交时间超过补交期限 → 该周报记为 0 分。\n- 说明：AI 只按周报内容评定 28-40 分的基础分；最终得分由系统按提交时间与期限自动计算。\n\n## 输出要求\n请以 JSON 格式返回：\n- dimension_scores（每项含name/score/max/comment）\n- total_score（各维度相加，范围28-40，为基础分）\n- grade（优/良/一般/差）\n- comment（总体评语，100字以内）\n- suggestion（改进建议，具体可执行）\n\n## 周报内容\n{content}`
  attendancePrompt.value = `# 考勤评分提示词\n\n你是考勤评分专家。请根据员工本周的考勤打卡数据，按以下规则评分。\n\n## 评分规则（基础分 100 分，纯扣分制，最低 0 分；加班分在基础分之上累加，不设上限）\n\n1. 全勤判定（以周为单位，仅统计工作日；周六/周日休息日不计入）：\n   - 全勤：每个工作日都有上班和下班打卡，且无迟到、缺卡、请假等异常。\n   - 非全勤：本周内出现迟到、缺卡、请假、旷工等任一异常 → 扣 3 分（每周一次性）。\n   - 出差视为全勤，不扣分；状态文本包含「正常」（如 正常、正常(外出打卡)、正常(补卡)、正常(审批打卡)）均视为正常。\n\n2. 迟到：每次迟到扣 5 分（状态文本含「迟到」即计 1 次，迟到 1 分钟也扣）。\n3. 缺卡：工作日当天上班或下班任一时间缺失记 1 次缺卡，每次扣 5 分；\n   若当天上班与下班都缺失，只记 1 次缺卡（不重复计 2 次），并同时按非全勤扣 3 分。\n4. 请假、旷工等其他异常：计入非全勤扣 3 分；涉及缺卡的仍按规则 3 叠加扣分。\n5. 加班分（当日加班总时长不足 1 小时不计分；有加班时才有加班打卡数据）：\n   - 工作日：以下班打卡时间从 18:00 起计算加班时长，只有完整跨满区间才加分，跨满后按档累加：\n     - 加班满 1 小时（下班 ≥ 19:00）：加 2 分\n     - 加班满 2 小时（下班 ≥ 20:00）：再加 1 分\n     - 加班满 4 小时（下班 ≥ 22:00）：再加 1 分\n   - 非工作日（周六/周日，以当天有打卡记录为准）：\n     - 全天投入（上班到下班 ≥6 小时）加 3 分\n     - 半天投入（≥3 小时）加 2 分\n   - 示例：工作日下班 19:01 → 只加 2 分；下班 20:30 → 加 2+1=3 分；下班 22:10 → 加 2+1+1=4 分；下班 18:30（不足1小时）→ 0 分。\n\n## 输出要求\n请严格以 JSON 格式返回，不要额外文字：\n{"score": 最终得分(基础分-扣分+加班分，可超过100), "full_attendance": true/false, "late_count": 迟到次数, "missing_count": 缺卡次数, "overtime_points": 加班分, "comment": "简短点评（说明扣分与加班加分原因）"}`
  chatPrompt.value = `你是一位专业的沟通评分专家。请对员工的会话记录进行评分（满分80分）。

## 扣分规则
- 敏感词检测：每出现一次敏感词扣10分
- 响应时间：
  - 工作日（周一至周五）9:00-18:00：5分钟内回复不扣分，超过5分钟或不回复扣5分
  - 非工作日（周六、周日）及其他非工作时间：10分钟内回复不扣分，超过10分钟或不回复扣5分

会话记录得分 = max(0, 80 - 以上扣分总和)

## 输出要求
请严格以 JSON 格式返回，不要额外文字：
{"score": 会话记录得分(0-80), "comment": "简短点评（说明扣分原因）"}`
  businessSummaryPrompt.value = `你是一位资深的项目管理分析师，擅长从周报中提炼项目全景、归并子任务、识别重点项目并评估进度。

## 任务目标

根据部门员工提交的周报内容，按**项目维度**进行高度归并，将零散的子任务/功能点/工作项聚类为完整的项目，区分**上周已完成**与**本周进行中**的项目。

## 核心原则：先归并，再输出

周报中的 \`### N. xxx\` 标题通常是**子任务或功能模块**，不是项目名。你必须将这些子任务归并到所属项目下。

### 归并规则（必须严格遵守）

1. **同一系统的子模块 → 归并为一个项目**
   - 例：「AI评分引擎」「系统监控」「安全加固」「性能优化」→ 归并为「考勤评分系统」
   - 例：「赢筑小程序」「消息推送」「性能优化」「单元测试」→ 归并为「赢筑小程序」
   - 例：「前端开发」「代码优化」「Bug修复」→ 归并为所属项目名（如「考勤评分系统」或「赢筑小程序」）

2. **同一客户/产品的不同工作 → 归并为一个项目**
   - 例：「YY客户上线实施」「YY客户操作培训」「客户响应机制建设」→ 归并为「YY客户上线项目」
   - 例：「XX客户运维支持」→ 归并为「XX客户运维项目」

3. **同一产品生命周期的工作 → 归并为一个项目**
   - 例：「产品规划」「用户调研」「原型设计」「需求文档」→ 归并为「产品规划与调研」

4. **通用/杂项工作 → 归并为「基础建设与优化」**
   - 例：「文档整理」「学习培训」「技术文档」「代码评审」→ 归并为「基础建设与优化」
   - 这类工作通常不涉及具体项目交付，作为兜底分类

5. **跨人员协作 → 必须合并为一条**
   - 不同员工参与同一项目的不同模块，必须合并为一条项目记录，persons 列出所有参与者

### 归并示例

假设研发部有以下周报内容：
- 员工A：### 1. AI评分引擎 / ### 2. 系统监控 / ### 3. 安全加固
- 员工B：### 1. 考勤评分系统 / ### 2. 业务盘功能 / ### 3. 技术文档
- 员工C：### 1. 前端开发 / ### 2. 代码优化 / ### 3. Bug修复

正确归并结果（2个项目）：
- 「考勤评分系统」：包含AI评分引擎、系统监控、安全加固、业务盘功能、前端开发、代码优化、Bug修复（A+B+C参与）
- 「基础建设与优化」：包含技术文档（B参与）

错误做法（7个独立项目）：
- AI评分引擎、系统监控、安全加固、考勤评分系统、业务盘功能、前端开发、代码优化... ← 这是把子任务当项目

## 输出格式

请严格按照以下 JSON 格式输出，不要包含其他内容：

\`\`\`json
\x7b
  "last_week_projects": [
    \x7b
      "name": "项目名称",
      "progress": 100,
      "highlight": true,
      "summary": "精炼描述",
      "persons": ["张三", "李四"]
    \x7d
  ],
  "this_week_projects": [
    \x7b
      "name": "项目名称",
      "progress": 60,
      "highlight": false,
      "summary": "精炼描述",
      "persons": ["张三"]
    \x7d
  ]
\x7d
\`\`\`

## 字段定义

| 字段 | 说明 |
|------|------|
| **name** | 归并后的项目名称（不超过15字）。不是子任务名，是所属的系统/产品/客户项目名 |
| **progress** | 进度百分比（0-100）。评估标准：已完成/已上线/已交付=100；联调/测试中=70-90；开发中=40-70；设计/调研中=10-30；未启动=0 |
| **highlight** | 是否重点项目（true/false）。满足任一条件即为重点：①跨人员协作（≥2人）②核心业务/营收相关系统 ③涉及架构升级或技术攻坚 ④有明确里程碑交付 |
| **summary** | 精炼描述（30-80字），必须包含：①做了什么 ②关键成果/数据 ③当前状态。避免空泛描述 |
| **persons** | 参与该项目的所有人员姓名（去重） |

## 输出约束

1. 每个周期的项目数量控制在 **2-5个**，超过说明归并不够
2. 禁止将子任务/功能模块作为独立项目输出
3. 通用/杂项工作统一归入「基础建设与优化」
4. 若某周期无有效项目信息，对应数组返回空数组 \`[]\`

## 上下文信息

- 部门名称：\x7bdepartment\x7d
- 统计周期：\x7bweek_label\x7d

## 员工周报内容

\x7breports\x7d

请输出 JSON 格式的项目总结（先归并，再输出）：`
  resetSummaryPrompt()
  resetOcrPrompt()
  resetDeadlines()
  scheduleResetGuard = true
  resetSchedule()
  setTimeout(() => { scheduleResetGuard = false }, 0)
  weights.value = { report: 1, attendance: 1, chat: 1 }
  toast.add({ severity: 'info', summary: '已重置为默认配置，请点击“保存配置”生效', life: 3000 })
}

function resetReportPrompt() {
  reportPrompt.value = `# 周报评分提示词\n\n请根据员工提交的周报在 28-40 分范围进行评分。\n\n## 评分维度\n\n### 1. 工作反馈深度（满分12分，最低分8分）\n评估员工对本周工作内容的总结深度和问题分析能力。\n- **高分标准（12分）**：不仅罗列工作内容，还能深入分析遇到的问题、产生的原因，并提出具体的解决方案或改进思路；有数据支撑或量化成果。\n- **中等标准（10分）**：对工作内容有基本总结，提及了部分问题但分析不够深入，解决方案较笼统。\n- **低分标准（8分）**：仅简单罗列工作内容，缺乏问题分析，未提及遇到的困难或解决思路。\n\n### 2. 进度节点明确（满分11分，最低分7分）\n评估员工对项目/任务进度的描述是否清晰、是否有明确的里程碑或时间节点。\n- **高分标准（11分）**：清晰描述各任务的当前进度（如百分比、完成阶段），标注关键里程碑和预期完成时间，进度描述具体可追踪。\n- **中等标准（9分）**：有进度描述但较笼统，如"进行中""已完成部分"，缺少具体时间节点。\n- **低分标准（7分）**：未提及进度或进度描述模糊，无法判断任务实际推进情况。\n\n### 3. 计划可行性（满分8分，最低分6分）\n评估员工对下周工作计划的描述是否具体、可执行、可验证。\n- **高分标准（8分）**：下周计划具体明确，包含可量化的目标、清晰的执行步骤和预期交付物，计划合理可落地。\n- **中等标准（7分）**：有下周计划但较笼统，如"继续推进XX项目"，缺少具体目标或执行细节。\n- **低分标准（6分）**：未提及下周计划，或计划过于空泛无法执行。\n\n### 4. 工作连续性（满分10分，最低分7分）\n评估员工本周工作是否承接上周计划，是否形成"计划→执行→结果→新计划"的闭环。\n- **高分标准（9分）**：本周工作明确承接上周计划，对上周未完成事项有跟进说明，形成完整的工作闭环；新计划与本周结果有逻辑关联。\n- **中等标准（8分）**：部分承接上周计划，但对未完成事项缺乏跟进，闭环不够完整。\n- **低分标准（7分）**：本周工作与上周计划无明显关联，或完全未提及上周计划的执行情况。\n\n## 等级划分\n- 优：35-40分\n- 良：31-34分\n- 一般：29-30分\n- 差：28分\n\n## 迟交/补交规则\n- 迟交：提交时间超过正常提交期限但未超过补交期限 → 基础分扣 5 分（最低可到 23 分）。\n- 补交：提交时间超过补交期限 → 该周报记为 0 分。\n- 说明：AI 只按周报内容评定 28-40 分的基础分；最终得分由系统按提交时间与期限自动计算。\n\n## 输出要求\n请以 JSON 格式返回：\n- dimension_scores（每项含name/score/max/comment）\n- total_score（各维度相加，范围28-40，为基础分）\n- grade（优/良/一般/差）\n- comment（总体评语，100字以内）\n- suggestion（改进建议，具体可执行）\n\n## 周报内容\n{content}`
  toast.add({ severity: 'info', summary: '已重置周报评分提示词', life: 2000 })
}

function resetAttendancePrompt() {
  attendancePrompt.value = `# 考勤评分提示词\n\n你是考勤评分专家。请根据员工本周的考勤打卡数据，按以下规则评分。\n\n## 评分规则（基础分 100 分，纯扣分制，最低 0 分；加班分在基础分之上累加，不设上限）\n\n1. 全勤判定（以周为单位，仅统计工作日；周六/周日休息日不计入）：\n   - 全勤：每个工作日都有上班和下班打卡，且无迟到、缺卡、请假等异常。\n   - 非全勤：本周内出现迟到、缺卡、请假、旷工等任一异常 → 扣 3 分（每周一次性）。\n   - 出差视为全勤，不扣分；状态文本包含「正常」（如 正常、正常(外出打卡)、正常(补卡)、正常(审批打卡)）均视为正常。\n\n2. 迟到：每次迟到扣 5 分（状态文本含「迟到」即计 1 次，迟到 1 分钟也扣）。\n3. 缺卡：工作日当天上班或下班任一时间缺失记 1 次缺卡，每次扣 5 分；\n   若当天上班与下班都缺失，只记 1 次缺卡（不重复计 2 次），并同时按非全勤扣 3 分。\n4. 请假、旷工等其他异常：计入非全勤扣 3 分；涉及缺卡的仍按规则 3 叠加扣分。\n5. 加班分（当日加班总时长不足 1 小时不计分；有加班时才有加班打卡数据）：\n   - 工作日：以下班打卡时间从 18:00 起计算加班时长，只有完整跨满区间才加分，跨满后按档累加：\n     - 加班满 1 小时（下班 ≥ 19:00）：加 2 分\n     - 加班满 2 小时（下班 ≥ 20:00）：再加 1 分\n     - 加班满 4 小时（下班 ≥ 22:00）：再加 1 分\n   - 非工作日（周六/周日，以当天有打卡记录为准）：\n     - 全天投入（上班到下班 ≥6 小时）加 3 分\n     - 半天投入（≥3 小时）加 2 分\n   - 示例：工作日下班 19:01 → 只加 2 分；下班 20:30 → 加 2+1=3 分；下班 22:10 → 加 2+1+1=4 分；下班 18:30（不足1小时）→ 0 分。\n\n## 输出要求\n请严格以 JSON 格式返回，不要额外文字：\n{"score": 最终得分(基础分-扣分+加班分，可超过100), "full_attendance": true/false, "late_count": 迟到次数, "missing_count": 缺卡次数, "overtime_points": 加班分, "comment": "简短点评（说明扣分与加班加分原因）"}`
  toast.add({ severity: 'info', summary: '已重置考勤评分提示词', life: 2000 })
}

function resetChatPrompt() {
  chatPrompt.value = `你是一位专业的沟通评分专家。请对员工的会话记录进行评分（满分80分）。

## 扣分规则
- 敏感词检测：每出现一次敏感词扣10分
- 响应时间：
  - 工作日（周一至周五）9:00-18:00：5分钟内回复不扣分，超过5分钟或不回复扣5分
  - 非工作日（周六、周日）及其他非工作时间：10分钟内回复不扣分，超过10分钟或不回复扣5分

会话记录得分 = max(0, 80 - 以上扣分总和)

## 输出要求
请严格以 JSON 格式返回，不要额外文字：
{"score": 会话记录得分(0-80), "comment": "简短点评（说明扣分原因）"}`
  toast.add({ severity: 'info', summary: '已重置会话评分提示词', life: 2000 })
}

function resetSummaryPrompt() {
  summaryPrompt.value = `你是一位专业的沟通评分专家。请对员工的一周小结进行评分（满分20分）。

## 扣分规则
- 工作会话次数 >= 300：不扣分
- 300 > 工作会话次数 >= 200：扣5分
- 200 > 工作会话次数 >= 100：扣10分
- 工作会话次数 < 100：扣15分
- 最晚时间在晚上6点（18:00）之前：扣5分

一周小结得分 = max(0, 20 - 以上扣分总和)

## 输出要求
请严格以 JSON 格式返回，不要额外文字：
{"score": 一周小结得分(0-20), "comment": "简短点评（说明扣分原因）"}`
  toast.add({ severity: 'info', summary: '已重置一周小结评分提示词', life: 2000 })
}

function resetOcrPrompt() {
  ocrPrompt.value = `你是一个精准的 OCR 解析助手。用户会上传一张「一周小结」的图片，
请从图片内容中提取以下字段并严格以 JSON 格式输出：
- author_name: 员工姓名（字符串）
- work_session_count: 本周处理的工作会话次数（整数，**必须识别，例如「共 12 次会话」「12 次会话」「处理了 12 次会话」等字样中的数字）
- total_minutes: 本周工作总耗时（分钟，整数；若无法识别则 null）
- latest_time: 最晚工作时间原文（字符串，如「22:35」或「周一 22:35」）
- week_start: 本周周一日期（YYYY-MM-DD；若图片未明确给出则填 null）
- week_end: 本周周日日期（YYYY-MM-DD；若图片未明确给出则填 null）
注意：
- 必须严格输出 JSON，不要额外文字；
- 若图片中没有姓名（例如仅有「一周小结」字样）则 work_session_count 必须返回 null，不要编造；
- 只输出一个 JSON 对象，不要包含说明文字。`
  toast.add({ severity: 'info', summary: '已重置 OCR 一周小结提示词', life: 2000 })
}

function resetBusinessPrompt() {
  businessSummaryPrompt.value = `你是一位资深的项目管理分析师，擅长从周报中提炼项目全景、归并子任务、识别重点项目并评估进度。

## 任务目标

根据部门员工提交的周报内容，按**项目维度**进行高度归并，将零散的子任务/功能点/工作项聚类为完整的项目，区分**上周已完成**与**本周进行中**的项目。

## 核心原则：先归并，再输出

周报中的 \`### N. xxx\` 标题通常是**子任务或功能模块**，不是项目名。你必须将这些子任务归并到所属项目下。

### 归并规则（必须严格遵守）

1. **同一系统的子模块 → 归并为一个项目**
   - 例：「AI评分引擎」「系统监控」「安全加固」「性能优化」→ 归并为「考勤评分系统」
   - 例：「赢筑小程序」「消息推送」「性能优化」「单元测试」→ 归并为「赢筑小程序」
   - 例：「前端开发」「代码优化」「Bug修复」→ 归并为所属项目名（如「考勤评分系统」或「赢筑小程序」）

2. **同一客户/产品的不同工作 → 归并为一个项目**
   - 例：「YY客户上线实施」「YY客户操作培训」「客户响应机制建设」→ 归并为「YY客户上线项目」
   - 例：「XX客户运维支持」→ 归并为「XX客户运维项目」

3. **同一产品生命周期的工作 → 归并为一个项目**
   - 例：「产品规划」「用户调研」「原型设计」「需求文档」→ 归并为「产品规划与调研」

4. **通用/杂项工作 → 归并为「基础建设与优化」**
   - 例：「文档整理」「学习培训」「技术文档」「代码评审」→ 归并为「基础建设与优化」
   - 这类工作通常不涉及具体项目交付，作为兜底分类

5. **跨人员协作 → 必须合并为一条**
   - 不同员工参与同一项目的不同模块，必须合并为一条项目记录，persons 列出所有参与者

### 归并示例

假设研发部有以下周报内容：
- 员工A：### 1. AI评分引擎 / ### 2. 系统监控 / ### 3. 安全加固
- 员工B：### 1. 考勤评分系统 / ### 2. 业务盘功能 / ### 3. 技术文档
- 员工C：### 1. 前端开发 / ### 2. 代码优化 / ### 3. Bug修复

正确归并结果（2个项目）：
- 「考勤评分系统」：包含AI评分引擎、系统监控、安全加固、业务盘功能、前端开发、代码优化、Bug修复（A+B+C参与）
- 「基础建设与优化」：包含技术文档（B参与）

错误做法（7个独立项目）：
- AI评分引擎、系统监控、安全加固、考勤评分系统、业务盘功能、前端开发、代码优化... ← 这是把子任务当项目

## 输出格式

请严格按照以下 JSON 格式输出，不要包含其他内容：

\`\`\`json
\x7b
  "last_week_projects": [
    \x7b
      "name": "项目名称",
      "progress": 100,
      "highlight": true,
      "summary": "精炼描述",
      "persons": ["张三", "李四"]
    \x7d
  ],
  "this_week_projects": [
    \x7b
      "name": "项目名称",
      "progress": 60,
      "highlight": false,
      "summary": "精炼描述",
      "persons": ["张三"]
    \x7d
  ]
\x7d
\`\`\`

## 字段定义

| 字段 | 说明 |
|------|------|
| **name** | 归并后的项目名称（不超过15字）。不是子任务名，是所属的系统/产品/客户项目名 |
| **progress** | 进度百分比（0-100）。评估标准：已完成/已上线/已交付=100；联调/测试中=70-90；开发中=40-70；设计/调研中=10-30；未启动=0 |
| **highlight** | 是否重点项目（true/false）。满足任一条件即为重点：①跨人员协作（≥2人）②核心业务/营收相关系统 ③涉及架构升级或技术攻坚 ④有明确里程碑交付 |
| **summary** | 精炼描述（30-80字），必须包含：①做了什么 ②关键成果/数据 ③当前状态。避免空泛描述 |
| **persons** | 参与该项目的所有人员姓名（去重） |

## 输出约束

1. 每个周期的项目数量控制在 **2-5个**，超过说明归并不够
2. 禁止将子任务/功能模块作为独立项目输出
3. 通用/杂项工作统一归入「基础建设与优化」
4. 若某周期无有效项目信息，对应数组返回空数组 \`[]\`

## 上下文信息

- 部门名称：\x7bdepartment\x7d
- 统计周期：\x7bweek_label\x7d

## 员工周报内容

\x7breports\x7d

请输出 JSON 格式的项目总结（先归并，再输出）：`
  toast.add({ severity: 'info', summary: '已重置业务盘总结提示词', life: 2000 })
}

async function loadConfig() {
  try {
    const res = await configAPI.get()
    if (!res || !res.data) return
    const d = res.data
    if (d.prompt_template) promptTemplate.value = d.prompt_template
    // v3 三项提示词
    if (typeof d.report_prompt === 'string') reportPrompt.value = d.report_prompt
    if (typeof d.attendance_prompt === 'string') attendancePrompt.value = d.attendance_prompt
    if (typeof d.chat_prompt === 'string') chatPrompt.value = d.chat_prompt
    if (typeof d.summary_prompt === 'string') summaryPrompt.value = d.summary_prompt
    if (typeof d.ocr_prompt === 'string') ocrPrompt.value = d.ocr_prompt
    if (typeof d.business_summary_prompt === 'string') businessSummaryPrompt.value = d.business_summary_prompt
    if (d.weights && typeof d.weights === 'object') {
      weights.value = {
        report: Number(d.weights.report ?? 1),
        attendance: Number(d.weights.attendance ?? 1),
        chat: Number(d.weights.chat ?? 1),
      }
    }
    // 提交期限设置
    if (d.submission_deadline_hours != null) submissionDeadlineHours.value = Number(d.submission_deadline_hours)
    if (d.late_deadline_hours != null) lateDeadlineHours.value = Number(d.late_deadline_hours)
    syncDeadlineFromHours()
  } catch (e) { console.error('[Config] 加载失败:', e) }
}

async function saveConfig() {
  // 校验提示词必填
  const promptFields = [
    { name: '周报评分提示词', value: reportPrompt.value },
    { name: '考勤评分提示词', value: attendancePrompt.value },
    { name: '会话评分提示词', value: chatPrompt.value },
    { name: '一周小结评分提示词', value: summaryPrompt.value },
    { name: 'OCR 一周小结提示词', value: ocrPrompt.value },
  ]
  const emptyPrompts = promptFields.filter(p => !p.value?.trim())
  if (emptyPrompts.length) {
    const names = emptyPrompts.map(p => p.name).join('、')
    toast.add({ severity: 'warn', summary: `提示词未填写完整`, detail: `请补充：${names}`, life: 5000 })
    return
  }

  // 把“周几 + 时间”换算回小时并校验
  syncDeadlineToHours()
  if (lateDeadlineHours.value <= submissionDeadlineHours.value) {
    toast.add({ severity: 'warn', summary: '补交期限必须晚于正常提交期限', life: 4000 })
    return
  }

  saving.value = true
  try {
    // 保存配置
    await configAPI.save({
      prompt_template: promptTemplate.value,
      report_prompt: reportPrompt.value,
      attendance_prompt: attendancePrompt.value,
      chat_prompt: chatPrompt.value,
      summary_prompt: summaryPrompt.value,
      ocr_prompt: ocrPrompt.value,
      business_summary_prompt: businessSummaryPrompt.value,
      weights: {
        report: Number(weights.value.report ?? 1),
        attendance: Number(weights.value.attendance ?? 1),
        chat: Number(weights.value.chat ?? 1),
      },
      submission_deadline_hours: Number(submissionDeadlineHours.value),
      late_deadline_hours: Number(lateDeadlineHours.value),
    })
    
    // 同时保存定时设置
    await aggregateAPI.saveSchedule({
      enabled: schedule.value.enabled,
      hour: schedule.value.hour,
      minute: schedule.value.minute,
      recurrence: schedule.value.recurrence,
      weekdays: schedule.value.weekdays,
    })
    
    emitDataChanged(DataEventType.CONFIG_CHANGED, { source: 'saveConfig' })
    toast.add({ severity: 'success', summary: '配置保存成功', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: '保存失败', life: 2000 })
  } finally {
    saving.value = false
  }
}

function generateAllPrompts() {
  // 周报
  resetReportPrompt()

  // 考勤
  resetAttendancePrompt()

  // 沟通
  resetChatPrompt()

  toast.add({ severity: 'success', summary: '已生成三项默认提示词', life: 2000 })
}

function generateBusinessPrompt() {
  resetBusinessPrompt()
  toast.add({ severity: 'success', summary: '已生成业务盘默认提示词', life: 2000 })
}

function triggerTestFileInput() {
  testFileInput.value?.click()
}

function onTestFileSelect(e) {
  const file = e.target.files[0]
  if (file) testFile.value = file
}

function onTestDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) testFile.value = file
}

function clearTestFile() {
  testFile.value = null
  if (testFileInput.value) testFileInput.value.value = ''
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function generateDefaultPrompt() {
  promptTemplate.value = `# 智友辰周任务汇总系统提示词\n\n## 角色设定\n你是一位专业、客观的工作报告评审专家。请对员工的周报进行综合评估。\n\n## 评分原则\n1. 客观公正：基于周报内容进行评价，避免主观臆断\n2. 鼓励量化：对有数据支撑、可量化成果的内容给予更高评价\n3. 关注闭环：重视"计划→执行→结果"的完整闭环\n4. 提供建设性：评语和建议应具体、可操作\n\n## 输出要求\n请以 JSON 格式返回评分结果，包含：\n- total_score: 综合得分（0-100）\n- grade: 等级（优/良/一般/差）\n- comment: 总体评语（100字以内）\n- suggestion: 改进建议（具体可执行）\n\n## 周报内容\n{content}`
  toast.add({ severity: 'success', summary: '已生成默认模板', life: 2000 })
}

async function runTest() {
  if (!testFile.value) return
  testing.value = true
  testResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', testFile.value)
    const uploadRes = await reportAPI.upload(formData)
    if (!uploadRes || !uploadRes.data) return
    const uploadData = uploadRes.data
    if (uploadData.report_id) {
      const detailRes = await reportAPI.get(uploadData.report_id)
      if (!detailRes || !detailRes.data) return
      const detail = detailRes.data
      testResult.value = {
        total_score: detail.total_score || uploadData.total_score,
        grade: detail.grade || uploadData.grade,
        dimension_scores: detail.dimension_scores || [],
        ai_comment: detail.ai_comment || '',
        ai_suggestion: detail.ai_suggestion || '',
      }
      toast.add({ severity: 'success', summary: '评分完成', life: 2000 })
      try { await reportAPI.delete(uploadData.report_id) } catch { /* 清理失败不阻塞 */ }
    } else {
      toast.add({ severity: 'warn', summary: uploadData.message || '上传成功但未获取评分', life: 3000 })
    }
  } catch (e) {
    const msg = e.response?.data?.detail || '测试失败'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  } finally {
    testing.value = false
  }
}

function resetTest() {
  testFile.value = null
  testResult.value = null
  if (testFileInput.value) testFileInput.value.value = ''
}

async function loadDepartments() {
  try {
    const res = await departmentAPI.list()
    departments.value = res.data || []
  } catch (e) { console.error('[Config] 加载部门失败:', e) }
}

async function loadPersons() {
  try {
    const res = await personAPI.list()
    persons.value = res.data || []
  } catch (e) { console.error('[Config] 加载人员失败:', e) }
}

async function loadManagementData() {
  await Promise.all([loadDepartments(), loadPersons()])
}

async function addDepartment() {
  if (!newDeptName.value.trim()) return
  const { success } = await execute(
    () => departmentAPI.create({ name: newDeptName.value, description: newDeptDesc.value }),
    { name: '添加部门', eventTypes: DataEventType.DEPARTMENTS_CHANGED, successMsg: '部门添加成功' }
  )
  if (success) {
    newDeptName.value = ''
    newDeptDesc.value = ''
    loadDepartments()
  }
}

async function deleteDepartment(id) {
  const { success } = await execute(
    () => departmentAPI.delete(id),
    { name: '删除部门', eventTypes: DataEventType.DEPARTMENTS_CHANGED, successMsg: '部门已删除' }
  )
  if (success) loadDepartments()
}

function startEditDepartment(dept) {
  editingDeptId.value = dept.id
  editingDeptName.value = dept.name
  editingDeptDesc.value = dept.description || ''
}

function cancelEditDepartment() {
  editingDeptId.value = null
  editingDeptName.value = ''
  editingDeptDesc.value = ''
}

async function saveEditDepartment(id) {
  if (!editingDeptName.value.trim()) {
    toast.add({ severity: 'warn', summary: '部门名称不能为空', life: 2000 })
    return
  }
  const { success } = await execute(
    () => departmentAPI.update(id, { name: editingDeptName.value.trim(), description: editingDeptDesc.value.trim() }),
    { name: '更新部门', eventTypes: DataEventType.DEPARTMENTS_CHANGED, successMsg: '部门更新成功' }
  )
  if (success) {
    cancelEditDepartment()
    loadDepartments()
  }
}

async function addPerson() {
  if (!newPersonName.value.trim()) return
  const data = { name: newPersonName.value, position: newPersonPosition.value }
  if (newPersonDept.value) {
    data.department_id = newPersonDept.value.id
    data.department_name = newPersonDept.value.name
  }
  const { success } = await execute(
    () => personAPI.create(data),
    { name: '添加人员', eventTypes: DataEventType.PERSONS_CHANGED, successMsg: '人员添加成功' }
  )
  if (success) {
    newPersonName.value = ''
    newPersonDept.value = null
    newPersonPosition.value = ''
    loadPersons()
  }
}

async function deletePerson(id) {
  const { success } = await execute(
    () => personAPI.delete(id),
    { name: '删除人员', eventTypes: DataEventType.PERSONS_CHANGED, successMsg: '人员已删除' }
  )
  if (success) loadPersons()
}

function startEditPerson(person) {
  editingPersonId.value = person.id
  editingPersonName.value = person.name
  editingPersonPosition.value = person.position || ''
  editingPersonDept.value = person.department_id ? departments.value.find(d => d.id === person.department_id) || null : null
}

function cancelEditPerson() {
  editingPersonId.value = null
  editingPersonName.value = ''
  editingPersonDept.value = null
  editingPersonPosition.value = ''
}

async function saveEditPerson(id) {
  if (!editingPersonName.value.trim()) {
    toast.add({ severity: 'warn', summary: '姓名不能为空', life: 2000 })
    return
  }
  const data = { name: editingPersonName.value.trim(), position: editingPersonPosition.value.trim() }
  if (editingPersonDept.value) {
    data.department_id = editingPersonDept.value.id
    data.department_name = editingPersonDept.value.name
  }
  const { success } = await execute(
    () => personAPI.update(id, data),
    { name: '更新人员', eventTypes: DataEventType.PERSONS_CHANGED, successMsg: '人员信息更新成功' }
  )
  if (success) {
    cancelEditPerson()
    loadPersons()
  }
}

async function checkAiStatus(force = false) {
  try {
    const res = await configAPI.aiStatus(force)
    const data = res.data || {}
    aiStatus.value = {
      ...data,
      // checkedAt 可能来自后端（缓存场景=checked_at，真测时需用返回值的时间）
      checkedAt: data.checked_at || data.checkedAt || new Date().toISOString(),
      cached: !!data.cached,
    }
  } catch (e) {
    aiStatus.value = { success: false, provider: 'unknown', model: '', error: '无法获取状态', checkedAt: '', cached: false }
  }
}

function formatBeijingTimeShort(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    if (isNaN(d.getTime())) return String(iso).slice(0, 10)
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${m}-${day} ${hh}:${mm}`
  } catch (e) {
    return ''
  }
}

async function loadSchedule() {
  try {
    const res = await aggregateAPI.getSchedule()
    const wd = res.data.weekdays
    let weekdays = Array.isArray(wd) ? wd.filter(v => typeof v === 'number' && v >= 0 && v <= 6) : [0, 1, 2, 3, 4]
    schedule.value = {
      enabled: !!res.data.enabled,
      hour: Number(res.data.hour ?? 3),
      minute: Number(res.data.minute ?? 0),
      recurrence: res.data.recurrence === 'weekly' ? 'weekly' : 'daily',
      weekdays,
    }
  } catch (e) {
    console.warn('[schedule] 加载失败:', e)
  }
}

async function saveSchedule() {
  scheduleSaving.value = true
  scheduleMsg.value = null
  try {
    const recurrence = schedule.value.recurrence === 'weekly' ? 'weekly' : 'daily'
    const weekdays = Array.isArray(schedule.value.weekdays)
      ? [...new Set(schedule.value.weekdays.filter(v => Number.isInteger(v) && v >= 0 && v <= 6))].sort((a, b) => a - b)
      : []
    const payload = {
      enabled: schedule.value.enabled,
      hour: Math.min(23, Math.max(0, Number(schedule.value.hour) || 0)),
      minute: Math.min(59, Math.max(0, Number(schedule.value.minute) || 0)),
      recurrence,
      weekdays,
    }
    const res = await aggregateAPI.saveSchedule(payload)
    scheduleMsg.value = { type: 'success', text: res.data.message || '已保存' }
    toast.add({ severity: 'success', summary: '定时设置已更新', life: 2500 })
    setTimeout(() => { scheduleMsg.value = null }, 4000)
  } catch (e) {
    const msg = e.response?.data?.detail || '保存失败，请重试'
    scheduleMsg.value = { type: 'error', text: msg }
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  } finally {
    scheduleSaving.value = false
  }
}

function toggleWeekday(day) {
  if (!schedule.value.enabled) return
  const idx = schedule.value.weekdays.indexOf(day)
  if (idx >= 0) {
    if (schedule.value.weekdays.length > 1) {
      schedule.value.weekdays.splice(idx, 1)
    }
  } else {
    schedule.value.weekdays.push(day)
    schedule.value.weekdays.sort((a, b) => a - b)
  }
}
function isWeekdaySelected(day) {
  return schedule.value.weekdays.includes(day)
}
function formatWeekdayHint() {
  return schedule.value.weekdays.map(i => WEEKDAY_LABELS[i]).join('、')
}

async function loadAiModels() {
  try {
    const res = await aiModelAPI.list()
    aiModels.value = res.data.models || []
  } catch (e) {
    console.error('[Config] 加载 AI 模型失败:', e)
  }
}

async function activateModel(id) {
  try {
    const res = await aiModelAPI.activate(id)
    toast.add({ severity: 'success', summary: res.data.message || '已切换模型', life: 2000 })
    await loadAiModels()
    checkAiStatus(true)
  } catch (e) {
    const msg = e.response?.data?.detail || '切换失败'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  }
}

async function testModel(m) {
  toast.add({ severity: 'info', summary: '正在测试连接...', life: 2000 })
  try {
    // 列表返回的是脱敏 Key，需要先获取完整模型数据
    const detail = await aiModelAPI.get(m.id)
    const res = await aiModelAPI.test({
      api_key: detail.data.api_key || '',
      base_url: detail.data.base_url,
      model_id: detail.data.model_id,
    })
    if (res.data.success) {
      toast.add({ severity: 'success', summary: '连接成功', detail: res.data.message, life: 3000 })
    } else {
      toast.add({ severity: 'error', summary: '连接失败', detail: res.data.message, life: 4000 })
    }
  } catch (e) {
    const msg = e.response?.data?.detail || '连接失败'
    toast.add({ severity: 'error', summary: '测试失败', detail: msg, life: 4000 })
  }
}

function editModel(m) {
  editingModelId.value = m.id
  modelForm.value = {
    name: m.name,
    provider: m.provider,
    model_id: m.model_id,
    api_key: '',
    base_url: m.base_url,
    is_active: m.is_active,
    is_vision: m.is_vision,
  }
  showAddModel.value = true
}

async function deleteModel(m) {
  if (m.is_active) {
    toast.add({ severity: 'warn', summary: '不能删除当前使用的模型', life: 2000 })
    return
  }
  if (!confirm(`确定删除模型 "${m.name}" 吗？`)) return
  try {
    await aiModelAPI.delete(m.id)
    toast.add({ severity: 'success', summary: '模型已删除', life: 2000 })
    await loadAiModels()
  } catch (e) {
    const msg = e.response?.data?.detail || '删除失败'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  }
}

function openAddModel() {
  editingModelId.value = null
  modelForm.value = {
    name: '',
    provider: 'custom',
    model_id: '',
    api_key: '',
    base_url: '',
    is_active: false,
    is_vision: false,
  }
  showAddModel.value = true
}

async function saveModel() {
  const f = modelForm.value
  if (!f.name.trim()) {
    toast.add({ severity: 'warn', summary: '请填写模型名称', life: 2000 })
    return
  }
  if (!f.provider.trim()) {
    toast.add({ severity: 'warn', summary: '请选择厂商', life: 2000 })
    return
  }
  if (!f.model_id.trim()) {
    toast.add({ severity: 'warn', summary: '请填写模型 ID', life: 2000 })
    return
  }
  if (!f.base_url.trim()) {
    toast.add({ severity: 'warn', summary: '请填写 Base URL', life: 2000 })
    return
  }

  try {
    if (editingModelId.value) {
      const data = {
        name: f.name.trim(),
        provider: f.provider,
        model_id: f.model_id.trim(),
        base_url: f.base_url.trim(),
        is_active: f.is_active,
        is_vision: f.is_vision,
      }
      if (f.api_key.trim()) {
        data.api_key = f.api_key.trim()
      }
      await aiModelAPI.update(editingModelId.value, data)
      toast.add({ severity: 'success', summary: '模型已更新', life: 2000 })
    } else {
      if (!f.api_key.trim()) {
        toast.add({ severity: 'warn', summary: '请填写 API Key', life: 2000 })
        return
      }
      await aiModelAPI.create({
        name: f.name.trim(),
        provider: f.provider,
        model_id: f.model_id.trim(),
        api_key: f.api_key.trim(),
        base_url: f.base_url.trim(),
        is_active: f.is_active,
        is_vision: f.is_vision,
      })
      toast.add({ severity: 'success', summary: '模型已添加', life: 2000 })
    }
    showAddModel.value = false
    await loadAiModels()
    if (f.is_active) checkAiStatus(true)
  } catch (e) {
    const msg = e.response?.data?.detail || '保存失败'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  }
}

onMounted(() => {
  loadConfig()
  loadManagementData()
  // 仅加载缓存状态，不触发真实检测（避免消耗额度）
  checkAiStatus(false)
  loadSchedule()
  loadAiModels()
})

// 监听定时评分开关变化，自动保存
let scheduleLoaded = false
let scheduleResetGuard = false
watch(
  () => schedule.value.enabled,
  (newVal, oldVal) => {
    // 重置默认时临时屏蔽“开关变化自动保存”，避免未点保存就入库
    if (scheduleResetGuard) {
      scheduleResetGuard = false
      return
    }
    // 页面刚加载时 loadSchedule 会设置 enabled 值，跳过首次
    if (!scheduleLoaded) {
      scheduleLoaded = true
      return
    }
    if (newVal !== oldVal) {
      saveSchedule()
    }
  }
)

useDataRefresh({
  loadFn: loadManagementData,
  watchEvents: getConfigEvents(),
  debounceMs: 300,
  autoLoad: false,
})
</script>

<style scoped>
.config-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-top: 4px;
}

/* ========== 可收起板块通用样式 ========== */
.panel-card {
  background: #fff;
  border: 1px solid #eef1f9;
  border-radius: 16px;
  overflow: hidden;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  width: 100%;
  box-sizing: border-box;
}
.panel-card:hover {
  border-color: #dde5ff;
}
.panel-card.collapsed {
  box-shadow: none;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
}
.panel-header.clickable {
  cursor: pointer;
  user-select: none;
}
.panel-header.clickable:hover {
  background: #fafbff;
}
.panel-header h3 {
  margin: 0;
  font-size: 15px;
  color: #1e2335;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.panel-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #7a819a;
  line-height: 1.5;
}
.panel-sub {
  margin: 4px 0 0;
  font-size: 12px;
  color: #7a819a;
}

.header-left,
.header-right {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}
.header-left {
  flex: 1;
}

.chevron {
  font-size: 14px;
  color: #6a7288;
  transition: transform 0.2s ease, color 0.2s ease;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  min-height: 32px;
  border-radius: 8px;
  cursor: pointer;
  margin-left: 4px;
}
.panel-header.clickable:hover .chevron {
  color: #4f6bff;
}

.panel-body {
  padding: 4px 22px 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-top: 1px dashed #e3e7f3;
  padding-top: 18px;
}

/* ========== 顶部状态卡片（AI 模型状态） ========== */
.status-card .panel-header {
  background: linear-gradient(135deg, #f4f7ff 0%, #ffffff 80%);
}
.status-card .status-icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #4f6bff, #6ed0ff);
  color: #fff;
  font-size: 20px;
  flex-shrink: 0;
  box-shadow: 0 6px 16px rgba(79, 107, 255, 0.25);
}
.status-card .status-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.status-card .status-provider {
  font-size: 15px;
  color: #1e2335;
  font-weight: 700;
}
.status-card .status-model {
  font-size: 12px;
  color: #5a6481;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.status-card .status-check-time {
  display: block;
  font-size: 11px;
  color: #8892b0;
  margin-top: 3px;
}
.status-card .status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px;
  background: #fff;
  border: 1px solid #eef1f9;
  border-radius: 999px;
}
.status-card .indicator-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #f59e0b;
  position: relative;
}
.status-card .indicator-dot.ok {
  background: #10b981;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.15);
}
.status-card .indicator-dot.fail {
  background: #ef4444;
  box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.15);
}
.status-card .indicator-text {
  font-size: 12px;
  color: #1e2335;
  font-weight: 600;
}
.refresh-btn {
  width: 32px;
  height: 32px;
  border-radius: 10px;
}
/* panel-card 底部操作条（用于维度/阈值 section） */
.section-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 18px;
  padding-top: 18px;
  border-top: 1px dashed #e3e7f3;
  flex-wrap: wrap;
}

.section-actions-hint {
  font-size: 13px;
  color: #7a819a;
}

.section-actions-buttons {
  display: flex;
  gap: 10px;
}

/* 底部固定操作栏 */
.config-sticky-bar {
  position: sticky;
  bottom: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 22px;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
  border: 1px solid #dde5ff;
  border-radius: 14px;
  box-shadow: 0 -2px 12px rgba(79, 107, 255, 0.08);
  flex-wrap: wrap;
}

.config-sticky-hint {
  font-size: 13px;
  color: #7a819a;
}

.config-sticky-buttons {
  display: flex;
  gap: 10px;
}

/* 两栏网格（用于部门/人员管理） */
.grid-wrap {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
  align-items: stretch;
}

/* 注：通用 panel-card / panel-header / panel-desc 的主样式已在"可收起板块通用样式"区定义
   此处仅保留 section-divider 作为向后兼容占位（如有其他页面引用） */
.section-divider {
  height: 1px;
  background: #eef1f9;
  margin: 4px 0;
}

/* 数据表格 */
.table-wrap {
  overflow-x: auto;
  border: 1px solid #eef1f9;
  border-radius: 12px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table thead th {
  padding: 10px 14px;
  text-align: left;
  background: #f8faff;
  color: #5a6481;
  font-weight: 600;
  font-size: 12px;
  border-bottom: 1px solid #eef1f9;
  white-space: nowrap;
}

.data-table tbody td {
  padding: 10px 14px;
  border-bottom: 1px solid #f3f5fb;
  color: #1e2335;
  vertical-align: middle;
}

.data-table tbody tr:hover {
  background: #f8faff;
}

.cell-input :deep(.p-inputtext),
.cell-input :deep(.p-inputnumber) {
  width: 100%;
}

.cell-input :deep(.p-inputtext) {
  font-size: 13px;
  height: 34px;
}

.cell-input :deep(.p-inputnumber-input) {
  height: 34px;
}

.action-cell {
  text-align: center;
}

/* Prompt */
.required-mark {
  color: #ef4444;
  font-weight: bold;
}
.prompt-area :deep(textarea) {
  font-family: 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.7;
}

.prompt-vars {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #7a819a;
}

.var-desc {
  margin-right: 8px;
}

/* 三项提示词网格布局 */
.prompt-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

.prompt-block {
  background: #f8faff;
  border: 1px solid #e6ecff;
  border-radius: 12px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prompt-block-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.prompt-field-label {
  font-size: 12px;
  color: #7a819a;
  font-weight: 500;
}

.weight-input {
  width: 84px;
  flex-shrink: 0;
}
.weight-input :deep(.p-inputnumber-input) {
  text-align: center;
  height: 32px;
  font-weight: 600;
}

.weights-sum-row {
  padding: 10px 14px;
  background: #fff;
  border: 1px dashed #dde5ff;
  border-radius: 10px;
}
.weights-label {
  font-size: 12px;
  color: #4f6bff;
  font-weight: 600;
}

/* 测试卡片 */
.test-card {
  grid-column: 1 / -1;
}

.test-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.upload-box {
  display: flex;
  align-items: center;
  padding: 20px;
  border: 2px dashed #dde5ff;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: #f8faff;
}

.upload-box:hover {
  border-color: #4f6bff;
  background: rgba(79, 107, 255, 0.04);
}

.upload-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.upload-ic {
  font-size: 28px;
  color: #4f6bff;
  margin-bottom: 4px;
}

.upload-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.upload-hint {
  font-size: 12px;
  color: #7a819a;
}

.upload-filled {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
}

.file-ic {
  font-size: 28px;
  color: #16a875;
}

.file-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.file-size {
  font-size: 12px;
  color: #7a819a;
}

.test-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.test-result-box {
  margin-top: 8px;
  padding: 20px;
  background: linear-gradient(135deg, #f8faff 0%, #fff 100%);
  border: 1px solid #eef1f9;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 1px solid #eef1f9;
}

.result-score-wrap {
  display: flex;
  flex-direction: column;
}

.result-score {
  font-size: 36px;
  font-weight: 800;
  color: #4f6bff;
  line-height: 1;
}

.result-sub {
  font-size: 12px;
  color: #7a819a;
  margin-top: 4px;
}

.grade-pill {
  font-size: 14px;
  font-weight: 700;
  padding: 6px 16px;
}

.result-dims {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rd-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rd-name {
  font-size: 13px;
  color: #5a6481;
  min-width: 140px;
}

.rd-bar-bg {
  flex: 1;
  height: 6px;
  background: #eef1f9;
  border-radius: 3px;
  overflow: hidden;
}

.rd-bar {
  height: 100%;
  background: linear-gradient(90deg, #4f6bff, #6ed0ff);
  border-radius: 3px;
  transition: width 0.3s;
}

.rd-val {
  font-size: 13px;
  font-weight: 600;
  color: #1e2335;
  min-width: 60px;
  text-align: right;
}

.result-comment,
.result-suggestion {
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #eef1f9;
  border-radius: 10px;
}

.rc-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #5a6481;
  font-weight: 600;
  margin-bottom: 6px;
}

.result-comment p,
.result-suggestion p {
  margin: 0;
  font-size: 13px;
  color: #3a4059;
  line-height: 1.7;
}

/* 添加行 + 列表 */
.add-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.grow-input {
  flex: 1;
  min-width: 120px;
}

.grow-input :deep(.p-inputtext),
.grow-input :deep(.p-dropdown) {
  width: 100%;
}

.grow-input :deep(.p-inputtext) {
  height: 34px;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
  flex: 1;
  min-height: 0;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f8faff;
  border-radius: 10px;
  transition: background 0.2s;
}

.item-row:hover {
  background: #eef3ff;
}

.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.item-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.item-sub {
  font-size: 12px;
  color: #7a819a;
}

.item-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.empty-line {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #a6adc4;
}

/* 响应式 */
@media (max-width: 1100px) {
  .grid-wrap { grid-template-columns: 1fr; }
}

@media (max-width: 900px) {
}

@media (max-width: 640px) {
  /* 板块通用：减小内边距 */
  .panel-header {
    padding: 14px 16px;
    gap: 10px;
  }
  .panel-header h3 {
    font-size: 14px;
  }
  .panel-body {
    padding: 12px 16px 16px;
    gap: 12px;
  }

  /* 评分维度表：表格→卡片堆叠 */
  .table-wrap {
    border-radius: 10px;
    overflow: hidden;
  }
  .data-table thead {
    display: none;
  }
  .data-table tbody tr {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 12px 14px;
    border-bottom: 1px solid #eef1f9;
    position: relative;
  }
  .data-table tbody tr:last-child { border-bottom: none; }
  .data-table tbody td {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 0;
    border: none;
    font-size: 12px;
  }
  .data-table tbody td::before {
    content: attr(data-label);
    font-size: 11px;
    color: #7a819a;
    font-weight: 600;
  }
  .data-table tbody td.action-cell {
    position: absolute;
    top: 10px;
    right: 10px;
    display: block;
    padding: 0;
  }
  .data-table tbody td.action-cell::before { content: none; }
  .data-table tbody tr:hover { background: transparent; }
  .cell-input :deep(.p-inputtext) { font-size: 13px; }

  /* section-actions：纵向全宽，按钮自适应占满 */
  .section-actions {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    margin-top: 14px;
    padding-top: 14px;
  }
  .section-actions-buttons {
    flex-direction: column;
  }
  .section-actions-buttons :deep(.p-button) {
    width: 100%;
    justify-content: center;
  }

  /* 底部操作栏：移动端纵向 */
  .config-sticky-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
    padding: 12px 16px;
  }
  .config-sticky-buttons {
    flex-direction: column;
  }
  .config-sticky-buttons :deep(.p-button) {
    width: 100%;
    justify-content: center;
  }

  /* AI 状态卡片 */
  .status-card .header-left {
    flex-wrap: wrap;
  }
  .status-card .header-right {
    flex-wrap: wrap;
  }
  .status-card .status-indicator {
    padding: 4px 10px;
  }
  .status-card .status-provider {
    font-size: 14px;
  }
  .status-card .status-model {
    font-size: 11px;
  }
}
.schedule-panel .panel-header {
  align-items: flex-start;
}
.schedule-toggle-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}
.schedule-status {
  font-size: 14px;
  color: #5a6481;
  font-weight: 500;
}
.schedule-body {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px dashed #e3e7f3;
}
.schedule-row {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 18px;
}
.schedule-hint-row {
  margin-bottom: 8px;
}
.field-label {
  font-size: 14px;
  color: #1e2335;
  font-weight: 600;
}
.schedule-select {
  width: 220px;
}
.time-inputs {
  display: flex;
  align-items: center;
  gap: 8px;
}
.time-sep {
  font-size: 24px;
  font-weight: 700;
  color: #5a6481;
}
.weekday-toggles {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.weekday-btn {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  border: 1.5px solid #d7dcea;
  background: #fff;
  color: #5a6481;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}
.weekday-btn:hover:not(.disabled) {
  border-color: #6c8bff;
  color: #6c8bff;
}
.weekday-btn.selected {
  background: #6c8bff;
  border-color: #6c8bff;
  color: #fff;
}
.weekday-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.schedule-hint {
  font-size: 13px;
  color: #7a8397;
  background: #f4f7ff;
  padding: 8px 12px;
  border-radius: 8px;
}
.schedule-actions {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 12px;
}
.schedule-msg {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 13px;
}
.schedule-msg.success {
  background: #e8f7ee;
  color: #1a7e3a;
}
.schedule-msg.error {
  background: #fde8e8;
  color: #b42318;
}

/* 提交期限设置 */
.deadline-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.deadline-item {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.deadline-input-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.deadline-picker {
  width: 128px;
}

.deadline-prefix {
  font-size: 14px;
  color: #5a6481;
  font-weight: 500;
  white-space: nowrap;
}

.deadline-num-input :deep(.p-inputnumber-input) {
  height: 42px;
  font-size: 16px;
  font-weight: 600;
  width: 120px;
}

.deadline-unit {
  font-size: 14px;
  color: #5a6481;
  font-weight: 500;
}

.deadline-hint {
  font-size: 12px;
  color: #8a92a8;
  line-height: 1.5;
}

.deadline-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(79, 107, 255, 0.06), #fff);
  border: 1px solid #dde5ff;
  border-radius: 10px;
  font-size: 13px;
  color: #4f6bff;
  font-weight: 500;
}

.deadline-summary i {
  font-size: 16px;
}

@media (max-width: 768px) {
  .deadline-grid {
    grid-template-columns: 1fr;
  }
}

/* AI 模型管理 */
.model-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.model-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
  background: #f8faff;
  border: 1px solid #eef1f9;
  border-radius: 12px;
  transition: all 0.2s;
}

.model-row:hover {
  background: #eef3ff;
  border-color: #dde5ff;
}

.model-row.model-active {
  background: linear-gradient(135deg, rgba(79, 107, 255, 0.06), #fff);
  border-color: rgba(79, 107, 255, 0.3);
  box-shadow: 0 2px 8px rgba(79, 107, 255, 0.1);
}

.model-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
}

.model-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.model-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.model-active-tag,
.model-vision-tag {
  font-size: 11px;
  padding: 2px 8px;
}

.model-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #5a6481;
}

.model-sep {
  color: #a6adc4;
}

.model-provider {
  color: #4f6bff;
  font-weight: 500;
}

.model-id-text,
.model-key-text,
.model-url-text {
  font-family: 'Consolas', monospace;
  color: #7a819a;
}

.model-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

/* 模型表单 */
.model-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-label {
  font-size: 13px;
  font-weight: 600;
  color: #1e2335;
}

.form-label .required {
  color: #ef4444;
  margin-left: 2px;
}

.form-input :deep(.p-inputtext),
.form-input :deep(.p-dropdown) {
  width: 100%;
}

.form-input :deep(.p-inputtext) {
  height: 38px;
}

.form-field-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}

.form-checkbox {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #5a6481;
  cursor: pointer;
}
</style>
