<template>
  <div class="report-list page-content">
    <FilterBar>
      <div class="app-filter-item">
        <label>提交人</label>
        <InputText v-model="filters.author_name" placeholder="输入提交人姓名" class="filter-input" />
      </div>
      <div class="app-filter-item">
        <label>部门</label>
        <InputText v-model="filters.department" placeholder="输入部门名称" class="filter-input" />
      </div>
      <div class="app-filter-item">
        <label>选择周次</label>
        <div class="week-selector">
          <Dropdown
            v-model="selectedYear"
            :options="yearOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="年份"
            class="year-dropdown"
            @change="onYearChange"
          />
          <Dropdown
            v-model="selectedWeekLabel"
            :options="filteredWeekOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="选择周次"
            class="week-dropdown"
            @change="onWeekChange"
          />
        </div>
      </div>
      <div class="app-filter-item filter-action-group">
        <label>&nbsp;</label>
        <div class="filter-action-buttons">
          <Button label="筛选" icon="pi pi-search" @click="loadData" class="filter-action-btn" />
          <Button label="重置" icon="pi pi-refresh" @click="resetFilters" severity="secondary" class="filter-action-btn" />
        </div>
      </div>
    </FilterBar>

    <!-- 评分状态指示器 -->
    <div v-if="scoringStatus.visible" class="scoring-status-bar"
         :class="scoringStatus.running ? 'status-running' : (scoringStatus.lastResult === 'error' ? 'status-error' : 'status-done')">
      <template v-if="scoringStatus.running">
        <i class="pi pi-spin pi-spinner" style="font-size:16px;margin-right:8px"></i>
        <span>正在定时聚合评分… {{ scoringStatus.processed }}/{{ scoringStatus.total }}
          <template v-if="scoringStatus.currentPerson">（当前：{{ scoringStatus.currentPerson }}）</template>
          <template v-if="scoringStatus.errors"> | ⚠ {{ scoringStatus.errors }} 人失败</template>
        </span>
      </template>
      <template v-else>
        <i class="pi" :class="scoringStatus.lastResult === 'error' ? 'pi-exclamation-triangle' : 'pi-check-circle'" style="font-size:16px;margin-right:8px"></i>
        <span>{{ scoringStatus.lastMessage || '评分已完成' }}</span>
        <span v-if="scoringStatus.lastRunAt" class="status-time">{{ formatBeijingTimeShort(scoringStatus.lastRunAt) }}</span>
        <Button icon="pi pi-replay" severity="secondary" text rounded size="small" :loading="triggerLoading" @click="onTriggerScoring" style="margin-left:8px" v-tooltip.top="'手动触发评分'" />
        <Button icon="pi pi-times" severity="secondary" text rounded size="small" @click="scoringStatus.visible = false" style="margin-left:4px" />
      </template>
    </div>

    <!-- 批量操作栏 -->
    <div v-if="aggregates.length" class="batch-bar">
      <div class="batch-bar-left">
        <span class="batch-count">已选 <strong>{{ selectedRows.length }}</strong> 条</span>
      </div>
      <div class="batch-bar-right">
        <Button label="批量导出周报" icon="pi pi-download" severity="success"
                :disabled="!selectedRows.length"
                @click="onBatchExport" outlined size="small" />
        <Button label="批量删除" icon="pi pi-trash" severity="danger"
                :disabled="!selectedRows.length"
                @click="onBatchDelete" outlined size="small" />
      </div>
    </div>

    <ResponsiveTableShell>
      <DataTable :key="tableRefreshKey" :value="aggregates" :loading="loading" :paginator="true" :rows="pageSize"
          :totalRecords="total" @page="onPage" :first="(page - 1) * pageSize" :lazy="true"
          paginatorPosition="bottom"
          class="dark-table" dataKey="id"
          selectionMode="multiple" v-model:selection="selectedRows"
          responsiveLayout="scroll">
        <template #empty>
          <div class="empty-state">
            <i class="pi pi-inbox empty-icon"></i>
            <div class="empty-text">暂无周评数据，请先上传周报、考勤或聊天记录</div>
          </div>
        </template>

        <!-- 复选框列（PrimeVue 原生） -->
        <Column selectionMode="multiple" headerStyle="width: 56px" style="width: 56px"></Column>

        <!-- 周次 -->
        <Column header="周次" style="min-width:110px">
          <template #body="{ data }">
            <Tag :value="formatWeek(data.week_start, data.week_end)" severity="info" />
          </template>
        </Column>

        <!-- 提交人 -->
        <Column field="author_name" header="提交人" style="min-width:100px" />

        <!-- 部门 -->
        <Column field="department" header="部门" style="min-width:120px">
          <template #body="{ data }">
            <span>{{ data.department || '-' }}</span>
          </template>
        </Column>

        <!-- 考勤分 -->
        <Column header="考勤分" style="min-width:100px">
          <template #body="{ data }">
            <template v-if="data.status === 'pending'">
              <span class="text-muted">-</span>
            </template>
            <template v-else>
              <span
                v-if="data.attendance_score != null"
                :class="['score-cell', 'editable', { 'score-cell-zero': Number(data.attendance_score) === 0 }]"
                @dblclick="openEdit(data, 'attendance_score')"
                :title="'双击修改考勤分'">
                {{ Math.round(Number(data.attendance_score)) }}
              </span>
              <span v-else class="text-muted">/</span>
            </template>
          </template>
        </Column>

        <!-- 周报分 -->
        <Column header="周报分" style="min-width:100px">
          <template #body="{ data }">
            <span
              v-if="data.report_score != null"
              :class="['score-cell', 'editable', { 'score-cell-zero': Number(data.report_score) === 0 }]"
              @dblclick="openEdit(data, 'report_score')"
              :title="'双击修改周报分'">
              {{ Math.round(Number(data.report_score)) }}
            </span>
            <span v-else-if="getStatusMeta(data)"
                  class="status-inline"
                  :class="getStatusMeta(data).severity === 'danger' ? 'text-danger' : (getStatusMeta(data).severity === 'warning' ? 'text-warning' : 'text-muted')"
                  :title="getStatusMeta(data).tooltip">
              <i :class="getStatusMeta(data).icon" :style="{ marginRight: '4px' }"></i>{{ getStatusMeta(data).text }}
            </span>
            <span v-else class="text-muted">/</span>
          </template>
        </Column>

        <!-- 沟通分 -->
        <Column header="沟通分" style="min-width:100px">
          <template #body="{ data }">
            <span
              v-if="data.chat_score != null"
              :class="['score-cell', 'editable', { 'score-cell-zero': Number(data.chat_score) === 0 }]"
              @dblclick="openEdit(data, 'chat_score')"
              :title="'双击修改沟通分'">
              {{ Math.round(Number(data.chat_score)) }}
            </span>
            <span v-else class="text-muted">/</span>
          </template>
        </Column>

        <!-- 总分 -->
        <Column header="总分" style="min-width:110px">
          <template #body="{ data }">
            <template v-if="getStatusMeta(data)">
              <Tag :value="getStatusMeta(data).text"
                   :severity="getStatusMeta(data).severity"
                   :icon="getStatusMeta(data).icon"
                   :pt="getStatusMeta(data).severity === 'danger' ? { root: { style: 'background:#fde2e2;color:#b71c1c;border:1px solid #f5b7b7' } } : undefined"
                   :title="getStatusMeta(data).tooltip" />
            </template>
            <template v-else>
              <ScoreBadge v-if="data.composite_score != null" :score="Number(data.composite_score)" size="sm" />
              <span v-else class="text-muted">-</span>
            </template>
          </template>
        </Column>

        <!-- 更新时间 -->
        <Column header="更新时间" style="min-width:160px">
          <template #body="{ data }">
            <span class="text-muted small">{{ formatBeijingTimeShort(data.modified_at || data.updated_at) }}</span>
          </template>
        </Column>

        <!-- 操作 -->
        <Column header="操作" style="min-width:420px" :frozen="false">
          <template #body="{ data }">
            <div class="row-actions">
              <Button
                v-if="data.status === 'failed' || isPendingTimeout(data)"
                label="重新评分"
                :icon="rescoringIds.has(data.id) ? 'pi pi-spin pi-spinner' : 'pi pi-replay'"
                size="small" outlined severity="warning"
                :disabled="rescoringIds.has(data.id)"
                :loading="rescoringIds.has(data.id)"
                @click="onRescore(data)" />
              <Button label="查看周报" icon="pi pi-eye"
                      size="small" text severity="info" @click="viewReport(data)" />
              <Button label="下载周报" icon="pi pi-download"
                      size="small" text severity="success" @click="onDownloadReport(data)" />
              <Button label="删除" icon="pi pi-trash"
                      size="small" text severity="danger" @click="onDelete(data)" />
            </div>
          </template>
        </Column>
      </DataTable>
    </ResponsiveTableShell>

    <!-- 修改分数弹窗 -->
    <Dialog v-model:visible="editDialog.show" header="修改分数" :style="{ width: '420px' }" :closable="true">
      <div class="edit-body">
        <div class="edit-info">
          <div><strong>{{ editDialog.author_name }}</strong> · {{ editDialog.department || '-' }}</div>
          <div class="text-muted small">{{ editDialog.week_range }}</div>
          <div class="edit-field-name">修改字段：<strong>{{ fieldLabelMap[editDialog.field] }}</strong></div>
        </div>

        <div class="input-row">
          <label>新的分数（0 ~ 100）</label>
          <InputNumber v-model="editDialog.newValue" :min="0" :max="100" :step="0.5" :maxFractionDigits="1"
                       placeholder="输入新分数" style="width:100%" />
        </div>

        <div class="edit-preview">
          <div>当前三项分数：</div>
          <div class="score-preview">
            <span>考勤 {{ editDialog.attendance_score ?? '-' }}</span>
            <span>周报 {{ editDialog.report_score ?? '-' }}</span>
            <span>沟通 {{ editDialog.chat_score ?? '-' }}</span>
          </div>
          <div class="composite-preview">保存后总分：<strong>{{ computedComposite }}</strong></div>
        </div>
      </div>
      <template #footer>
        <Button label="取消" icon="pi pi-times" severity="secondary" @click="editDialog.show = false" />
        <Button label="保存" icon="pi pi-check" :disabled="editDialog.newValue == null"
                :loading="editDialog.saving" @click="saveEdit" />
      </template>
    </Dialog>

    <!-- 确认弹窗（替代 PrimeVue ConfirmService，更稳定） -->
    <Dialog v-model:visible="confirmDialog.show" :header="confirmDialog.title" :style="{ width: '400px' }" :closable="true">
      <div class="confirm-body">
        <div class="confirm-icon">
          <i class="pi pi-exclamation-triangle" style="font-size:32px;color:#e74c3c"></i>
        </div>
        <div class="confirm-message">{{ confirmDialog.message }}</div>
      </div>
      <template #footer>
        <Button label="取消" icon="pi pi-times" severity="secondary" @click="confirmDialog.show = false" />
        <Button label="确认" icon="pi pi-check" severity="danger" :loading="confirmDialog.saving" @click="onConfirmAccept" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'

const scoringStatus = reactive({
  visible: false,
  running: false,
  total: 0,
  processed: 0,
  errors: 0,
  currentPerson: '',
  lastRunAt: null,
  lastResult: null,
  lastMessage: '',
})

let scoringPollTimer = null
let dataPollTimer = null
const triggerLoading = ref(false)
const rescoringIds = ref(new Set())  // 单条重新评分的 loading 状态

async function fetchScoringStatus() {
  try {
    const { data } = await aggregateAPI.scoringStatus()
    const wasRunning = scoringStatus.running
    Object.assign(scoringStatus, data)

    // 若从未执行过且当前不在运行 → 不显示，停止轮询
    if (!scoringStatus.running && !scoringStatus.lastRunAt) {
      scoringStatus.visible = false
      stopScoringPoll()
      return
    }

    // 刚结束一轮评分 → 显示结果、刷新列表、停止轮询
    if (wasRunning && !scoringStatus.running) {
      scoringStatus.visible = true
      loadData()
      stopScoringPoll()
      return
    }

    // 正在运行 → 持续显示，继续轮询
    if (scoringStatus.running) {
      scoringStatus.visible = true
    }

    // 非运行态但有历史记录 → 显示最近一次结果，停止轮询
    if (!scoringStatus.running && scoringStatus.lastRunAt) {
      scoringStatus.visible = true
      stopScoringPoll()
    }
  } catch {
    // 接口挂了不弹错误，静默跳过
  }
}

function startScoringPoll() {
  if (scoringPollTimer) return // 避免重复启动
  fetchScoringStatus()
  scoringPollTimer = setInterval(fetchScoringStatus, 10000)
}

function stopScoringPoll() {
  if (scoringPollTimer) {
    clearInterval(scoringPollTimer)
    scoringPollTimer = null
  }
}

/** 轮询刷新列表（仅当有评分中记录时） */
function startDataPoll() {
  dataPollTimer = setInterval(async () => {
    const hasPending = aggregates.value.some(a => a.status === 'pending')
    if (hasPending && !loading.value) {
      loadData()
    }
  }, 3000)
}

async function onTriggerScoring() {
  triggerLoading.value = true
  try {
    await aggregateAPI.triggerScoring()
    scoringStatus.visible = true
    scoringStatus.running = true
    startScoringPoll()
  } catch (e) {
    const msg = e.response?.data?.detail || '触发失败'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  } finally {
    triggerLoading.value = false
  }
}
import { useRouter } from 'vue-router'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import Dropdown from 'primevue/dropdown'
import { useToast } from 'primevue/usetoast'

import ResponsiveTableShell from '../components/ui/ResponsiveTableShell.vue'
import FilterBar from '../components/ui/FilterBar.vue'
import ScoreBadge from '../components/ui/ScoreBadge.vue'
import { formatBeijingTimeShort, getBeijingDateFilename } from '../utils/timeUtil.js'
import { aggregateAPI } from '../api'
import { emitDataChanged, DataEventType } from '../utils/dataEvents'

const toast = useToast()
const router = useRouter()

const loading = ref(false)
const aggregates = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const tableRefreshKey = ref(0)
const selectedRows = ref([])
const availableWeeks = ref([]) // 有数据的周列表

const filters = reactive({
  author_name: '',
  department: '',
  week_start: '',
})

// 周筛选
const selectedYear = ref(new Date().getFullYear())
const selectedWeekLabel = ref('')

/** 获取ISO周数 */
function getISOWeek(d) {
  const date = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()))
  const dayNum = date.getUTCDay() || 7
  date.setUTCDate(date.getUTCDate() + 4 - dayNum)
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1))
  return Math.ceil((((date - yearStart) / 86400000) + 1) / 7)
}

/** 获取周一日期 */
function getMonday(d) {
  const date = new Date(d)
  const day = date.getDay()
  const diff = date.getDate() - day + (day === 0 ? -6 : 1)
  date.setDate(diff)
  date.setHours(0, 0, 0, 0)
  return date
}

/** 格式化日期 YYYY-MM-DD */
function formatYMD(d) {
  if (!d) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 格式化日期 MM.DD */
function formatShort(d) {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${m}.${day}`
}

/** 年份选项 */
const yearOptions = computed(() => {
  const currentYear = new Date().getFullYear()
  return [
    { label: `${currentYear}年`, value: currentYear },
    { label: `${currentYear - 1}年`, value: currentYear - 1 },
    { label: `${currentYear - 2}年`, value: currentYear - 2 },
  ]
})

/** 生成指定年份的周选项 */
function generateWeekOptionsForYear(year) {
  const options = []
  const jan4 = new Date(year, 0, 4)
  const jan4Day = jan4.getDay() || 7
  const firstMonday = new Date(jan4)
  firstMonday.setDate(jan4.getDate() - (jan4Day - 1))
  for (let week = 1; week <= 53; week++) {
    const monday = new Date(firstMonday)
    monday.setDate(firstMonday.getDate() + (week - 1) * 7)
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    if (monday.getFullYear() === year || sunday.getFullYear() === year) {
      const label = `第${week}周 ${formatShort(monday)}~${formatShort(sunday)}`
      const value = formatYMD(monday)
      options.push({ label, value })
    }
  }
  return options
}

/** 根据选中年份过滤周选项，只显示有数据的周 */
const filteredWeekOptions = computed(() => {
  const allWeeks = generateWeekOptionsForYear(selectedYear.value)
  // 如果没有可用周数据，显示所有周
  if (!availableWeeks.value.length) return allWeeks
  // 只显示有数据的周
  return allWeeks.filter(week => availableWeeks.value.includes(week.value))
})

function onYearChange(event) {
  selectedYear.value = event.value
  selectedWeekLabel.value = ''
  filters.week_start = ''
}

function onWeekChange(event) {
  filters.week_start = event.value
}

const editDialog = reactive({
  show: false,
  saving: false,
  id: null,
  author_name: '',
  department: '',
  week_range: '',
  field: '',
  newValue: null,
  attendance_score: null,
  report_score: null,
  chat_score: null,
})

const confirmDialog = reactive({
  show: false,
  title: '确认操作',
  message: '',
  saving: false,
  onAccept: null, // 保存回调：点击确认后执行
})

const fieldLabelMap = {
  attendance_score: '考勤分',
  report_score: '周报分',
  chat_score: '沟通分',
}

const computedComposite = computed(() => {
  const a = editDialog.field === 'attendance_score' ? editDialog.newValue : editDialog.attendance_score
  const r = editDialog.field === 'report_score' ? editDialog.newValue : editDialog.report_score
  const c = editDialog.field === 'chat_score' ? editDialog.newValue : editDialog.chat_score
  let sum = 0
  if (a != null) sum += Number(a)
  if (r != null) sum += Number(r)
  if (c != null) sum += Number(c)
  return Math.round(sum)
})

function formatWeek(ws, we) {
  if (!ws) return '-'
  return `${String(ws).slice(5, 10)} ~ ${String(we || '').slice(5, 10) || '-'} `
}

async function loadData() {
  loading.value = true
  try {
    const params = {
      page: page.value,
      size: pageSize.value,
    }
    if (filters.author_name) params.author_name = filters.author_name
    if (filters.department) params.department = filters.department
    if (filters.week_start) {
      params.week_start = filters.week_start
    }
    const res = await aggregateAPI.list(params)
    aggregates.value = res.data.items || []
    total.value = Number(res.data.total || 0)

    // 获取有数据的周列表（用于筛选）
    if (res.data.available_weeks) {
      availableWeeks.value = res.data.available_weeks
    }
  } catch (e) {
    toast.add({ severity: 'error', summary: '加载失败', life: 3000 })
  } finally {
    loading.value = false
    selectedRows.value = []
  }
}

function toISODate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function isDate(v) { return v instanceof Date && !isNaN(v.valueOf()) }

function resetFilters() {
  filters.author_name = ''
  filters.department = ''
  filters.week_start = ''
  // 重置到默认状态：显示全部周
  selectedYear.value = new Date().getFullYear()
  selectedWeekLabel.value = ''
  page.value = 1
  clearSavedFilters()
  loadData()
}

function onPage(e) {
  page.value = e.page + 1
  loadData()
}

function openEdit(data, field) {
  editDialog.show = true
  editDialog.saving = false
  editDialog.id = data.id
  editDialog.author_name = data.author_name
  editDialog.department = data.department || ''
  editDialog.week_range = `${data.week_start || '-'} ~ ${data.week_end || '-'}`
  editDialog.field = field
  editDialog.attendance_score = data.attendance_score
  editDialog.report_score = data.report_score
  editDialog.chat_score = data.chat_score
  editDialog.newValue = Number(data[field]) ?? 0
}

async function saveEdit() {
  if (editDialog.newValue == null) return
  editDialog.saving = true
  try {
    const payload = { [editDialog.field]: Number(editDialog.newValue) }
    await aggregateAPI.update(editDialog.id, payload)
    toast.add({ severity: 'success', summary: '分数更新成功', life: 2500 })
    editDialog.show = false
    loadData()
  } catch (e) {
    const msg = e.response?.data?.detail || '更新失败，请重试'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  } finally {
    editDialog.saving = false
  }
}

function saveFiltersToStorage() {
  try {
    sessionStorage.setItem('reportListFilters', JSON.stringify({
      author_name: filters.author_name,
      department: filters.department,
      week_start: filters.week_start,
      selectedYear: selectedYear.value,
      selectedWeekLabel: selectedWeekLabel.value,
      page: page.value,
    }))
  } catch {}
}

function restoreFiltersFromStorage() {
  try {
    const saved = sessionStorage.getItem('reportListFilters')
    if (!saved) return false
    const s = JSON.parse(saved)
    filters.author_name = s.author_name || ''
    filters.department = s.department || ''
    filters.week_start = s.week_start || ''
    selectedYear.value = s.selectedYear ?? new Date().getFullYear()
    selectedWeekLabel.value = s.selectedWeekLabel || ''
    page.value = s.page || 1
    return true
  } catch {
    return false
  }
}

function clearSavedFilters() {
  try { sessionStorage.removeItem('reportListFilters') } catch {}
}

function viewReport(data) {
  if (data.report_id) {
    saveFiltersToStorage()
    router.push(`/admin/reports/${data.report_id}`)
    return
  }
  toast.add({ severity: 'warn', summary: '该周评暂未关联周报', life: 2500 })
}

function downloadBlob(blob, filename) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  window.URL.revokeObjectURL(url)
}

async function onDownloadReport(data) {
  try {
    const res = await aggregateAPI.downloadReport(data.id)
    // 从响应头提取原始文件名
    const contentDisposition = res.headers['content-disposition']
    let filename = `${data.author_name}_${data.week_start}_周报.xlsx`
    if (contentDisposition) {
      // 解析 filename*=UTF-8''xxx 格式
      const match = contentDisposition.match(/filename\*=(?:UTF-8''|utf-8'')(.+)/i)
      if (match) {
        filename = decodeURIComponent(match[1])
      } else {
        // 解析 filename="xxx" 格式
        const match2 = contentDisposition.match(/filename="?([^";]+)"?/)
        if (match2) {
          filename = decodeURIComponent(match2[1])
        }
      }
    }
    downloadBlob(res.data, filename)
    toast.add({ severity: 'success', summary: '下载成功', life: 2000 })
  } catch (e) {
    const msg = e.response?.data?.detail || '下载失败'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  }
}

function onDelete(data) {
  confirmDialog.title = '删除确认'
  confirmDialog.message = `确认删除「${data.author_name} · ${formatWeek(data.week_start, data.week_end)}」的周评记录吗？`
  confirmDialog.show = true
  confirmDialog.onAccept = async () => {
    try {
      await aggregateAPI.delete(data.id)
      toast.add({ severity: 'success', summary: '已删除', life: 2000 })
      loadData()
      emitDataChanged(DataEventType.REPORTS_CHANGED)
    } catch (e) {
      const msg = e.response?.data?.detail || '删除失败'
      toast.add({ severity: 'error', summary: msg, life: 3000 })
    }
  }
}

/** 判断 pending 是否超时（>=20分钟 或 retry_count>=1） */
function isPendingTimeout(data) {
  if (!data || data.status !== 'pending') return false
  if (Number(data.retry_count || 0) >= 1) return true
  const ts = data.modified_at || data.updated_at || data.created_at
  if (!ts) return false
  try {
    const t = typeof ts === 'string' ? Date.parse(ts.replace('Z', '')) : Number(ts)
    if (!t) return false
    return Date.now() - t > 20 * 60 * 1000
  } catch {
    return false
  }
}

/** 获取状态 Tag 的元数据（failed / pending 超时 / 评分中）*/
function getStatusMeta(data) {
  if (!data) return null
  if (data.status === 'failed') {
    return {
      text: '评分失败',
      severity: 'danger',
      icon: 'pi pi-times-circle',
      tooltip: data.error_message || '评分连续失败，已停止自动重试'
    }
  }
  if (data.status === 'pending') {
    const retryCount = Number(data.retry_count || 0)
    if (isPendingTimeout(data)) {
      return {
        text: retryCount ? `重试中(${retryCount})` : '评分超时',
        severity: 'warning',
        icon: 'pi pi-exclamation-triangle',
        tooltip: data.error_message || '评分时间过长，建议点击"重新评分"手动重试'
      }
    }
    return {
      text: '评分中',
      severity: 'warn',
      icon: 'pi pi-spin pi-spinner',
      tooltip: 'AI 正在评分，请稍候…'
    }
  }
  return null
}

async function onRescore(data) {
  const id = data.id
  const set = new Set(rescoringIds.value)
  set.add(id)
  rescoringIds.value = set
  try {
    const res = await aggregateAPI.rescore(id)
    const newAgg = res.data?.aggregate || {}
    if (newAgg.status === 'done' || newAgg.report_score != null) {
      toast.add({ severity: 'success', summary: `${data.author_name} 重新评分成功`, life: 3000 })
    } else if (newAgg.status === 'failed') {
      toast.add({
        severity: 'warn',
        summary: `${data.author_name} 仍评分失败：${(newAgg.error_message || '').slice(0, 60)}`,
        life: 4500
      })
    } else {
      toast.add({ severity: 'info', summary: `${data.author_name} 已提交重新评分`, life: 2500 })
    }
    loadData()
  } catch (e) {
    const msg = e.response?.data?.detail || '重新评分失败，请稍后重试'
    toast.add({ severity: 'error', summary: msg, life: 4500 })
    loadData()
  } finally {
    const next = new Set(rescoringIds.value)
    next.delete(id)
    rescoringIds.value = next
  }
}

function onBatchDelete() {
  if (!selectedRows.value.length) return
  const ids = selectedRows.value.map(r => r.id)
  confirmDialog.title = '批量删除确认'
  confirmDialog.message = `确认删除所选 ${ids.length} 条周评记录吗？`
  confirmDialog.show = true
  confirmDialog.onAccept = async () => {
    try {
      await aggregateAPI.batchDelete(ids)
      toast.add({ severity: 'success', summary: `已删除 ${ids.length} 条记录`, life: 2500 })
      loadData()
      emitDataChanged(DataEventType.REPORTS_CHANGED)
    } catch (e) {
      const msg = e.response?.data?.detail || '批量删除失败'
      toast.add({ severity: 'error', summary: msg, life: 3000 })
    }
  }
}

async function onConfirmAccept() {
  const cb = confirmDialog.onAccept
  confirmDialog.saving = true
  try {
    if (typeof cb === 'function') {
      await Promise.resolve(cb())
    }
  } finally {
    confirmDialog.show = false
    confirmDialog.saving = false
    confirmDialog.onAccept = null
  }
}

async function onBatchExport() {
  if (!selectedRows.value.length) return
  const ids = selectedRows.value.map(r => r.id)
  try {
    const res = await aggregateAPI.export({ ids })
    downloadBlob(res.data, `周报打包_${ids.length}份_${getBeijingDateFilename()}.zip`)
    toast.add({ severity: 'success', summary: `已打包 ${ids.length} 份周报`, life: 2500 })
  } catch (e) {
    const msg = e.response?.data?.detail || '导出失败'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  }
}

onMounted(() => {
  // 尝试从 sessionStorage 恢复筛选状态（从周报详情返回时）
  const restored = restoreFiltersFromStorage()
  if (!restored) {
    // 无缓存：默认显示全部周，不设置周筛选
    selectedYear.value = new Date().getFullYear()
    selectedWeekLabel.value = ''
    filters.week_start = ''
  }
  loadData()
  startScoringPoll()
  startDataPoll()
})

onUnmounted(() => {
  if (scoringPollTimer) {
    clearInterval(scoringPollTimer)
    scoringPollTimer = null
  }
  if (dataPollTimer) {
    clearInterval(dataPollTimer)
    dataPollTimer = null
  }
  // 离开列表页时清除缓存（避免下次进入仍保留旧筛选）
  // 仅在路由不是 ReportDetail 时清除
  const currentPath = router.currentRoute.value.path
  if (!currentPath.startsWith('/admin/reports/')) {
    clearSavedFilters()
  }
})
</script>

<style scoped>
.report-list { display: flex; flex-direction: column; gap: 18px; }

.page-header h1 {
  font-size: 26px;
  color: #1e2335;
  margin: 0 0 6px;
}
.page-desc {
  color: #5a6481;
  font-size: 14px;
  margin: 0;
}

.score-cell.editable {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 8px;
  background: rgba(79, 107, 255, 0.08);
  color: #4f6bff;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.15s;
  font-variant-numeric: tabular-nums;
}
.score-cell.editable:hover {
  background: rgba(79, 107, 255, 0.16);
}
.score-cell.score-cell-zero {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}
.score-cell.score-cell-zero:hover {
  background: rgba(239, 68, 68, 0.2);
}
.text-muted { color: #97a0bd; }
.text-muted.small { font-size: 12px; }

.row-actions { display: flex; gap: 6px; flex-wrap: wrap; }

/* 评分状态指示器 */
.scoring-status-bar {
  display: flex;
  align-items: center;
  padding: 10px 16px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 500;
}
.scoring-status-bar.status-running {
  background: #e8f0ff;
  color: #1a56db;
  border: 1px solid #b3d4ff;
}
.scoring-status-bar.status-done {
  background: #ecfdf5;
  color: #065f46;
  border: 1px solid #a7f3d0;
}
.scoring-status-bar.status-error {
  background: #fef2f2;
  color: #991b1b;
  border: 1px solid #fecaca;
}
.scoring-status-bar .status-time {
  margin-left: 12px;
  font-size: 12px;
  opacity: 0.7;
}

/* 筛选/重置按钮组 */
.filter-action-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}
.filter-action-group {
  align-self: stretch;
}

.week-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.week-selector .year-dropdown {
  min-width: 110px;
}

.week-selector .week-dropdown {
  min-width: 280px;
}

.filter-action-btn {
  padding: 0 18px !important;
  height: 38px;
}

.batch-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: #f8faff;
  border: 1px solid #e1e7ff;
  border-radius: 10px;
}
.batch-bar-left { display: flex; align-items: center; gap: 12px; }
.batch-bar-right { display: flex; gap: 8px; }
.batch-count { font-size: 13px; color: #5a6481; }
.batch-count strong { color: #1e2335; font-size: 14px; }

.edit-body, .confirm-body { display: flex; flex-direction: column; gap: 14px; }

.confirm-body {
  flex-direction: row;
  align-items: center;
  gap: 16px;
  padding: 8px 4px;
}
.confirm-icon { flex-shrink: 0; }
.confirm-message { font-size: 14px; color: #3a4059; line-height: 1.6; }

.edit-info {
  padding: 12px 14px;
  background: #f8faff;
  border-radius: 10px;
  line-height: 1.7;
  font-size: 14px;
  color: #1e2335;
}
.edit-field-name { margin-top: 6px; color: #4f6bff; }

.input-row { display: flex; flex-direction: column; gap: 6px; }
.input-row label { font-size: 13px; color: #5a6481; font-weight: 500; }

.edit-preview {
  padding: 12px 14px;
  background: rgba(22, 168, 117, 0.06);
  border-radius: 10px;
  font-size: 13px;
  color: #3a4059;
  line-height: 1.8;
}
.score-preview { display: flex; gap: 16px; margin: 4px 0; font-variant-numeric: tabular-nums; }
.composite-preview { margin-top: 6px; color: #16a875; font-size: 14px; }

.report-detail-body { display: flex; flex-direction: column; gap: 8px; font-size: 14px; color: #3a4059; }
.info-line { display: flex; gap: 16px; flex-wrap: wrap; }
</style>
