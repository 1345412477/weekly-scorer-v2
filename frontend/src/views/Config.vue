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

    <!-- 评分维度 + 等级阈值 -->
    <section class="panel-card collapsible" :class="{ collapsed: !expanded.dimensions }">
      <header class="panel-header clickable" @click="toggle('dimensions')">
        <div class="header-left">
          <h3>评分维度与等级阈值</h3>
        </div>
        <div class="header-right">
          <Button label="添加维度" icon="pi pi-plus" text size="small" @click.stop="addDim" />
          <i :class="['chevron', 'pi', expanded.dimensions ? 'pi-chevron-up' : 'pi-chevron-down']"></i>
        </div>
      </header>
      <div class="panel-body" v-show="expanded.dimensions">
        <div class="sub-grid">
          <!-- 左：评分维度表 -->
          <div>
            <div class="table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th style="width: 22%">维度名称</th>
                    <th style="width: 12%">最高分</th>
                    <th style="width: 12%">最低分</th>
                    <th style="width: 12%">满分</th>
                    <th>考核内容</th>
                    <th style="width: 48px"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(dim, idx) in dimensions" :key="idx">
                    <td data-label="维度名称">
                      <InputText v-model="dim.name" placeholder="请输入" class="cell-input" />
                    </td>
                    <td data-label="最高分">
                      <InputNumber v-model="dim.highest_score" :min="0" :max="dim.full_score || 100" size="small" :showButtons="false" class="cell-input" />
                    </td>
                    <td data-label="最低分">
                      <InputNumber v-model="dim.lowest_score" :min="0" :max="dim.full_score || 100" size="small" :showButtons="false" class="cell-input" />
                    </td>
                    <td data-label="满分">
                      <InputNumber v-model="dim.full_score" :min="1" :max="100" size="small" :showButtons="false" class="cell-input" />
                    </td>
                    <td data-label="考核内容">
                      <InputText v-model="dim.evaluation_content" placeholder="描述考核要点" class="cell-input" />
                    </td>
                    <td class="action-cell">
                      <Button icon="pi pi-trash" severity="danger" text rounded size="small" @click="removeDim(idx)" :disabled="dimensions.length <= 1" />
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="totals-row">
              <span class="totals-label">总满分</span>
              <span class="totals-value">{{ totalFullScore }} 分</span>
            </div>
          </div>

          <!-- 右：等级阈值 -->
          <div>
            <div class="sub-section-label">等级阈值（{{ totalFullScore }}分制）</div>
            <div class="threshold-grid">
              <div v-for="(val, key) in gradeThresholds" :key="key" :class="['threshold-item', 't-' + gradeIndex(key)]">
                <span :class="['th-label', 'g-' + gradeIndex(key)]">{{ key }}</span>
                <span class="th-label-op">得分 ≥</span>
                <InputNumber v-model="gradeThresholds[key]" :min="0" :max="totalFullScore" size="small" :showButtons="false" class="th-input-num" />
              </div>
            </div>
          </div>
        </div>

      </div>
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
            <span class="prompt-sub-title">周报评分提示词</span>
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
            <span class="prompt-sub-title">考勤评分提示词</span>
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

        <!-- 沟通/一周小结评分提示词 -->
        <div class="prompt-sub-section">
          <div class="prompt-sub-header">
            <span class="prompt-sub-title">沟通/一周小结评分提示词</span>
            <Button label="重置默认" icon="pi pi-refresh" text size="small" @click="resetChatPrompt" />
          </div>
          <div class="prompt-block">
            <div class="prompt-block-head">
              <span class="prompt-field-label">权重</span>
              <InputNumber v-model.number="weights.chat" :min="0" :step="1" size="small" :showButtons="false" class="weight-input" />
            </div>
            <Textarea v-model="chatPrompt" rows="6" class="prompt-area" placeholder="请输入沟通/一周小结评分提示词...（如工作会话次数、响应效率、沟通质量）" autoResize />
          </div>
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
import InputNumber from 'primevue/inputnumber'
import InputSwitch from 'primevue/inputswitch'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const { execute } = useDataOperation()

// 各板块展开状态
const expanded = reactive({
  status: true,
  dimensions: false,
  prompts: false,
  businessPrompt: false,
  aiModels: false,
  schedule: false,
})
function toggle(key) {
  if (key in expanded) expanded[key] = !expanded[key]
}

const saving = ref(false)
const testing = ref(false)
const aiStatus = ref({ provider: '', model: '', success: null, checkedAt: '', cached: false, ttl_remaining: 0 })
const dimensions = ref([
  { name: '工作反馈深度', full_score: 14, highest_score: null, lowest_score: null, evaluation_content: '问题发现+分析+解决方案' },
  { name: '进度节点明确', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '项目是否有明确进度/节点' },
  { name: '计划可行性', full_score: 10, highest_score: null, lowest_score: null, evaluation_content: '下周计划是否具体可执行' },
  { name: '工作连续性', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '是否承接上周计划且有闭环' },
])
const gradeThresholds = ref({ '优': 45, '良': 38, '一般': 33, '差': 28 })
const promptTemplate = ref('')
// v3 三项提示词 + 三项权重
const reportPrompt = ref('')
const attendancePrompt = ref('')
const chatPrompt = ref('')
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

const totalFullScore = computed(() => dimensions.value.reduce((s, d) => s + (d.full_score || 0), 0))

const providerName = computed(() => {
  const p = aiStatus.value.provider
  if (p === 'mimo') return '小米 MiMo'
  if (p === 'ark') return '豆包 (火山引擎)'
  if (p === 'deepseek') return 'DeepSeek'
  return p || '待检测'
})

function gradeIndex(g) {
  return { '优': 0, '良': 1, '一般': 2, '差': 3 }[g] ?? 0
}

function gradeSeverity(g) {
  if (g === '优') return 'success'
  if (g === '良') return 'info'
  if (g === '一般') return 'warn'
  return 'danger'
}

function addDim() {
  dimensions.value.push({ name: '', full_score: 10, highest_score: null, lowest_score: null, evaluation_content: '' })
}

function removeDim(idx) {
  dimensions.value.splice(idx, 1)
}

function resetConfig() {
  dimensions.value = [
    { name: '工作反馈深度', full_score: 14, highest_score: null, lowest_score: null, evaluation_content: '问题发现+分析+解决方案' },
    { name: '进度节点明确', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '项目是否有明确进度/节点' },
    { name: '计划可行性', full_score: 10, highest_score: null, lowest_score: null, evaluation_content: '下周计划是否具体可执行' },
    { name: '工作连续性', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '是否承接上周计划且有闭环' },
  ]
  gradeThresholds.value = { '优': 45, '良': 38, '一般': 33, '差': 28 }
  promptTemplate.value = `# 周报评分系统提示词

## 角色设定
你是一位专业、客观的工作报告评审专家。请根据以下评分维度对员工周报进行综合评估。

## 评分原则
1. 客观公正：基于周报内容进行评价，避免主观臆断
2. 鼓励量化：对有数据支撑、可量化成果的内容给予更高评价
3. 关注闭环：重视"计划→执行→结果"的完整闭环
4. 提供建设性：评语和建议应具体、可操作

## 评分维度
  1. 工作反馈深度（满分14分，最高分14分，最低分8分，考核内容：问题发现+分析+解决方案）
  2. 进度节点明确（满分13分，最高分13分，最低分7分，考核内容：项目是否有明确进度/节点）
  3. 计划可行性（满分10分，最高分10分，最低分6分，考核内容：下周计划是否具体可执行）
  4. 工作连续性（满分13分，最高分13分，最低分7分，考核内容：是否承接上周计划且有闭环）

## 评分标准
- 每个维度独立打分，不超过该维度满分
- 综合评分 = 各维度分数直接相加（28-50分）
- 等级划分：优(≥43)、良(≥38)、一般(≥33)、差(≥28)

## 输出要求
请以 JSON 格式返回评分结果，包含：
- dimension_scores: 各维度得分及评语（含name、score、max、comment）
- total_score: 综合得分（28-50分）
- grade: 等级（优/良/一般/差）
- comment: 总体评语（100字以内）
- suggestion: 改进建议（具体可执行）

## 周报内容
\x7bcontent\x7d`
  reportPrompt.value = `# 周报评分提示词

请根据员工提交的周报在 28-50 分范围进行评分。

## 评分维度
  1. 工作反馈深度（满分14分，最高分14分，最低分8分，考核内容：问题发现+分析+解决方案）
  2. 进度节点明确（满分13分，最高分13分，最低分7分，考核内容：项目是否有明确进度/节点）
  3. 计划可行性（满分10分，最高分10分，最低分6分，考核内容：下周计划是否具体可执行）
  4. 工作连续性（满分13分，最高分13分，最低分7分，考核内容：是否承接上周计划且有闭环）

## 等级划分
优(≥43)、良(≥38)、一般(≥33)、差(≥28)

## 输出要求
请以 JSON 格式返回：
- dimension_scores（每项含name/score/max/comment）
- total_score（各维度相加）
- grade（优/良/一般/差）
- comment（总体评语）
- suggestion（改进建议）

## 周报内容
\x7bcontent\x7d`
  attendancePrompt.value = `# 考勤评分提示词

请根据员工本周的考勤打卡数据，在 0-100 分范围内进行客观评分。

## 评分参考维度
1. 出勤完整性：是否全勤，有无迟到、早退、缺卡
2. 工作时长：每日工作时长是否达标
3. 异常情况：是否有未说明的异常考勤
4. 加班情况：合理加班视为积极表现（无需额外加分上限）

## 输出要求
请以 JSON 格式返回：
- score（0-100 的数值）
- comment（简短点评）`
  chatPrompt.value = `# 沟通与一周小结评分提示词

请根据员工本周的工作沟通记录（企业微信对话记录）以及一周小结内容，在 0-100 分范围内对其沟通质量和响应效率进行评分。

## 评分参考维度
1. 工作会话数量：处理的工作相关对话数（体现在一周小结中）
2. 响应效率：回复是否及时，阻塞时长如何
3. 沟通质量：表达清晰、有层次、提供必要信息
4. 一周小结完整性：是否完整反映本周工作

## 输出要求
请以 JSON 格式返回：
- score（0-100 的数值）
- comment（简短点评）`
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
| **summary** | 精炼描述（30-80字），必须包含：①做了什么 ②关键成果/数据 当前状态。避免空泛描述 |
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
  weights.value = { report: 1, attendance: 1, chat: 1 }
  toast.add({ severity: 'info', summary: '已重置为默认配置', life: 2000 })
}

function resetReportPrompt() {
  reportPrompt.value = `# 周报评分提示词

请根据员工提交的周报在 28-50 分范围进行评分。

## 评分维度
  1. 工作反馈深度（满分14分，最高分14分，最低分8分，考核内容：问题发现+分析+解决方案）
  2. 进度节点明确（满分13分，最高分13分，最低分7分，考核内容：项目是否有明确进度/节点）
  3. 计划可行性（满分10分，最高分10分，最低分6分，考核内容：下周计划是否具体可执行）
  4. 工作连续性（满分13分，最高分13分，最低分7分，考核内容：是否承接上周计划且有闭环）

## 等级划分
优(≥43)、良(≥38)、一般(≥33)、差(≥28)

## 输出要求
请以 JSON 格式返回：
- dimension_scores（每项含name/score/max/comment）
- total_score（各维度相加）
- grade（优/良/一般/差）
- comment（总体评语）
- suggestion（改进建议）

## 周报内容
\x7bcontent\x7d`
  toast.add({ severity: 'info', summary: '已重置周报评分提示词', life: 2000 })
}

function resetAttendancePrompt() {
  attendancePrompt.value = `# 考勤评分提示词

请根据员工本周的考勤打卡数据，在 0-100 分范围内进行客观评分。

## 评分参考维度
1. 出勤完整性：是否全勤，有无迟到、早退、缺卡
2. 工作时长：每日工作时长是否达标
3. 异常情况：是否有未说明的异常考勤
4. 加班情况：合理加班视为积极表现（无需额外加分上限）

## 输出要求
请以 JSON 格式返回：
- score（0-100 的数值）
- comment（简短点评）`
  toast.add({ severity: 'info', summary: '已重置考勤评分提示词', life: 2000 })
}

function resetChatPrompt() {
  chatPrompt.value = `# 沟通与一周小结评分提示词

请根据员工本周的工作沟通记录（企业微信对话记录）以及一周小结内容，在 0-100 分范围内对其沟通质量和响应效率进行评分。

## 评分参考维度
1. 工作会话数量：处理的工作相关对话数（体现在一周小结中）
2. 响应效率：回复是否及时，阻塞时长如何
3. 沟通质量：表达清晰、有层次、提供必要信息
4. 一周小结完整性：是否完整反映本周工作

## 输出要求
请以 JSON 格式返回：
- score（0-100 的数值）
- comment（简短点评）`
  toast.add({ severity: 'info', summary: '已重置沟通评分提示词', life: 2000 })
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
| **summary** | 精炼描述（30-80字），必须包含：①做了什么 ②关键成果/数据 当前状态。避免空泛描述 |
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
    const d = res.data
    if (d.dimensions?.length) dimensions.value = d.dimensions
    if (d.grade_thresholds) gradeThresholds.value = d.grade_thresholds
    if (d.prompt_template) promptTemplate.value = d.prompt_template
    // v3 三项提示词
    if (typeof d.report_prompt === 'string') reportPrompt.value = d.report_prompt
    if (typeof d.attendance_prompt === 'string') attendancePrompt.value = d.attendance_prompt
    if (typeof d.chat_prompt === 'string') chatPrompt.value = d.chat_prompt
    if (typeof d.business_summary_prompt === 'string') businessSummaryPrompt.value = d.business_summary_prompt
    if (d.weights && typeof d.weights === 'object') {
      weights.value = {
        report: Number(d.weights.report ?? 1),
        attendance: Number(d.weights.attendance ?? 1),
        chat: Number(d.weights.chat ?? 1),
      }
    }
  } catch (e) { console.error('[Config] 加载失败:', e) }
}

async function saveConfig() {
  for (const dim of dimensions.value) {
    if (!dim.name?.trim()) {
      toast.add({ severity: 'warn', summary: '请填写所有维度名称', life: 2000 })
      return
    }
    if (!dim.full_score || dim.full_score <= 0) {
      toast.add({ severity: 'warn', summary: `维度 "${dim.name}" 的满分必须大于 0`, life: 2000 })
      return
    }
  }
  saving.value = true
  try {
    // 保存配置
    await configAPI.save({
      dimensions: dimensions.value,
      grade_thresholds: gradeThresholds.value,
      prompt_template: promptTemplate.value,
      report_prompt: reportPrompt.value,
      attendance_prompt: attendancePrompt.value,
      chat_prompt: chatPrompt.value,
      business_summary_prompt: businessSummaryPrompt.value,
      weights: {
        report: Number(weights.value.report ?? 1),
        attendance: Number(weights.value.attendance ?? 1),
        chat: Number(weights.value.chat ?? 1),
      },
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
  const dims = dimensions.value.map((d, i) => {
    let line = `  ${i + 1}. ${d.name}（满分${d.full_score}分`
    if (d.highest_score != null) line += `，最高分${d.highest_score}分`
    if (d.lowest_score != null) line += `，最低分${d.lowest_score}分`
    line += `，考核内容：${d.evaluation_content || '待补充'}）`
    return line
  }).join('\n')
  const gradeText = Object.entries(gradeThresholds.value)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${k}(≥${v})`)
    .join('、')
  reportPrompt.value = `# 周报评分提示词\n\n请根据员工提交的周报在 0-${totalFullScore.value} 分范围进行评分。\n\n## 评分维度\n${dims}\n\n## 等级划分\n${gradeText}\n\n## 输出要求\n请以 JSON 格式返回：\n- dimension_scores（每项含name/score/max/comment）\n- total_score（各维度相加）\n- grade（优/良/一般/差）\n- comment（总体评语）\n- suggestion（改进建议）\n\n## 周报内容\n{content}`

  // 考勤
  attendancePrompt.value = `# 考勤评分提示词\n\n请根据员工本周的考勤打卡数据，在 0-100 分范围内进行客观评分。\n\n## 评分参考维度\n1. 出勤完整性：是否全勤，有无迟到、早退、缺卡\n2. 工作时长：每日工作时长是否达标\n3. 异常情况：是否有未说明的异常考勤\n4. 加班情况：合理加班视为积极表现（无需额外加分上限）\n\n## 输出要求\n请以 JSON 格式返回：\n- score（0-100 的数值）\n- comment（简短点评）`

  // 沟通
  chatPrompt.value = `# 沟通与一周小结评分提示词\n\n请根据员工本周的工作沟通记录（企业微信对话记录）以及一周小结内容，在 0-100 分范围内对其沟通质量和响应效率进行评分。\n\n## 评分参考维度\n1. 工作会话数量：处理的工作相关对话数（体现在一周小结中）\n2. 响应效率：回复是否及时，阻塞时长如何\n3. 沟通质量：表达清晰、有层次、提供必要信息\n4. 一周小结完整性：是否完整反映本周工作\n\n## 输出要求\n请以 JSON 格式返回：\n- score（0-100 的数值）\n- comment（简短点评）`

  toast.add({ severity: 'success', summary: '已生成三项默认提示词', life: 2000 })
}

function generateBusinessPrompt() {
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
{
  "last_week_projects": [
    {
      "name": "项目名称",
      "progress": 100,
      "highlight": true,
      "summary": "精炼描述",
      "persons": ["张三", "李四"]
    }
  ],
  "this_week_projects": [
    {
      "name": "项目名称",
      "progress": 60,
      "highlight": false,
      "summary": "精炼描述",
      "persons": ["张三"]
    }
  ]
}
\`\`\`

## 字段定义

| 字段 | 说明 |
|------|------|
| **name** | 归并后的项目名称（不超过15字）。不是子任务名，是所属的系统/产品/客户项目名 |
| **progress** | 进度百分比（0-100）。评估标准：已完成/已上线/已交付=100；联调/测试中=70-90；开发中=40-70；设计/调研中=10-30；未启动=0 |
| **highlight** | 是否重点项目（true/false）。满足任一条件即为重点：①跨人员协作（≥2人）②核心业务/营收相关系统 ③涉及架构升级或技术攻坚 ④有明确里程碑交付 |
| **summary** | 精炼描述（30-80字），必须包含：①做了什么 ②关键成果/数据 当前状态。避免空泛描述 |
| **persons** | 参与该项目的所有人员姓名（去重） |

## 输出约束

1. 每个周期的项目数量控制在 **2-5个**，超过说明归并不够
2. 禁止将子任务/功能模块作为独立项目输出
3. 通用/杂项工作统一归入「基础建设与优化」
4. 若某周期无有效项目信息，对应数组返回空数组 \`[]\`

## 上下文信息

- 部门名称：{department}
- 统计周期：{week_label}

## 员工周报内容

{reports}

请输出 JSON 格式的项目总结（先归并，再输出）：`

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
  const dims = dimensions.value.map((d, i) => {
    let line = `  ${i + 1}. ${d.name}（满分${d.full_score}分`
    if (d.highest_score != null) line += `，最高分${d.highest_score}分`
    if (d.lowest_score != null) line += `，最低分${d.lowest_score}分`
    line += `，考核内容：${d.evaluation_content || '待补充'}）`
    return line
  }).join('\n')

  const gradeText = Object.entries(gradeThresholds.value)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${k}(≥${v})`)
    .join('、')

  promptTemplate.value = `# 智友辰周任务汇总系统提示词\n\n## 角色设定\n你是一位专业、客观的工作报告评审专家。请根据以下评分维度对员工周报进行综合评估。\n\n## 评分原则\n1. 客观公正：基于周报内容进行评价，避免主观臆断\n2. 鼓励量化：对有数据支撑、可量化成果的内容给予更高评价\n3. 关注闭环：重视"计划→执行→结果"的完整闭环\n4. 提供建设性：评语和建议应具体、可操作\n\n## 评分维度\n${dims || '（请先配置评分维度）'}\n\n## 评分标准\n- 每个维度独立打分，不超过该维度满分\n- 综合评分 = 各维度分数直接相加（${totalFullScore.value}分制）\n- 等级划分：${gradeText}\n\n## 输出要求\n请以 JSON 格式返回评分结果，包含：\n- dimension_scores: 各维度得分及评语（含name、score、max、comment）\n- total_score: 综合得分\n- grade: 等级（优/良/一般/差）\n- comment: 总体评语（100字以内）\n- suggestion: 改进建议（具体可执行）\n\n## 周报内容\n{content}`

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
    const uploadData = uploadRes.data
    if (uploadData.report_id) {
      const detailRes = await reportAPI.get(uploadData.report_id)
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
watch(
  () => schedule.value.enabled,
  (newVal, oldVal) => {
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

/* 子网格：评分维度表 + 等级阈值 */
.sub-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 18px;
  align-items: start;
}

.sub-section-label {
  font-size: 13px;
  color: #1e2335;
  font-weight: 600;
  margin-bottom: 8px;
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

.totals-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(79, 107, 255, 0.06), #fff);
  border-radius: 10px;
  border: 1px solid #dde5ff;
}

.totals-label {
  font-size: 13px;
  color: #5a6481;
}

.totals-value {
  font-size: 18px;
  font-weight: 700;
  color: #4f6bff;
}

/* 等级阈值 - 右栏单列垂直排列 */
.threshold-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.threshold-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid #eef1f9;
  background: #f8faff;
}

.threshold-item.t-0 { border-color: rgba(22, 168, 117, 0.25); background: rgba(22, 168, 117, 0.06); }
.threshold-item.t-1 { border-color: rgba(79, 107, 255, 0.25); background: rgba(79, 107, 255, 0.06); }
.threshold-item.t-2 { border-color: rgba(217, 119, 6, 0.25); background: rgba(217, 119, 6, 0.06); }
.threshold-item.t-3 { border-color: rgba(239, 68, 68, 0.25); background: rgba(239, 68, 68, 0.06); }

.th-label {
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.th-label.g-0 { color: #16a875; }
.th-label.g-1 { color: #4f6bff; }
.th-label.g-2 { color: #d97706; }
.th-label.g-3 { color: #ef4444; }

.th-label-op {
  font-size: 13px;
  color: #5a6481;
  flex-shrink: 0;
}

.th-input-num :deep(.p-inputnumber) {
  flex: 1;
}
.th-input-num :deep(.p-inputnumber-input) {
  height: 34px;
}

/* Prompt */
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

/* 评分维度板块：窄屏下双栏→单列堆叠 */
@media (max-width: 900px) {
  .sub-grid {
    grid-template-columns: 1fr;
    gap: 16px;
  }
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

  .totals-row {
    padding: 10px 14px;
    margin-top: 10px;
  }

  .sub-section-label {
    font-size: 12px;
    margin-top: 4px;
  }
  .threshold-grid {
    grid-template-columns: 1fr;
  }
  .threshold-item {
    padding: 10px 12px;
  }
  .th-label { font-size: 13px; }

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
