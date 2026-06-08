<template>
  <div class="report-list page-content">
    <div class="page-header">
      <div>
        <h1>周报列表</h1>
        <p class="page-subtitle">查看所有已提交的周报及评分结果</p>
      </div>
    </div>

    <!-- 批量操作工具栏 -->
    <div class="batch-toolbar">
      <div class="batch-info">
        <span>已选择 <strong>{{ selectedReports?.length || 0 }}</strong> 条数据</span>
      </div>
      <div class="batch-actions">
        <Button label="导出周报" icon="pi pi-download" @click="exportReports"
          :loading="exportLoading" :disabled="!selectedReports || selectedReports.length === 0" />
        <Button label="批量删除" icon="pi pi-trash" severity="danger"
          @click="confirmBatchDelete" :disabled="!selectedReports || selectedReports.length === 0" />
      </div>
    </div>

    <!-- 筛选区域 -->
    <Card class="filter-card">
      <template #content>
        <div class="filter-row">
          <div class="filter-item">
            <label>提交人</label>
            <InputText v-model="filters.author_name" placeholder="输入提交人姓名" class="filter-input" />
          </div>
          <div class="filter-item">
            <label>部门</label>
            <InputText v-model="filters.department" placeholder="输入部门名称" class="filter-input" />
          </div>
          <div class="filter-item">
            <label>是否补周报</label>
            <Dropdown v-model="filters.is_catch_up" :options="catchUpOptions" optionLabel="label" optionValue="value"
              placeholder="全部" class="filter-dropdown" />
          </div>
          <div class="filter-item">
            <label>排序字段</label>
            <Dropdown v-model="filters.sort_by" :options="sortOptions" optionLabel="label" optionValue="value"
              placeholder="默认排序" class="filter-dropdown" />
          </div>
          <div class="filter-item">
            <label>排序方向</label>
            <Dropdown v-model="filters.sort_order" :options="orderOptions" optionLabel="label" optionValue="value"
              class="filter-dropdown" />
          </div>
          <Button label="筛选" icon="pi pi-search" @click="applyFilters" class="filter-button" />
          <Button label="重置" icon="pi pi-refresh" @click="resetFilters" severity="secondary" class="filter-button" />
        </div>
      </template>
    </Card>

    <!-- 表格区域 -->
    <div class="list-container">
      <DataTable :key="tableRefreshKey" :value="reports" :loading="loading || deleting" :paginator="true" :rows="pageSize"
          :totalRecords="total" @page="onPage" :first="(page - 1) * pageSize" :lazy="true"
          paginatorPosition="bottom"
          class="dark-table" dataKey="id"
          responsiveLayout="scroll"
          v-model:selection="selectedReports"
          selectionMode="multiple"
          @update:selection="onSelectionChange">
          <template #empty>
            <div class="empty-state">
              <i class="pi pi-inbox empty-icon"></i>
              <div class="empty-text">暂无周报数据</div>
            </div>
          </template>

          <!-- 选择列 -->
          <Column selectionMode="multiple" headerStyle="width: 3rem" />

          <!-- 周次 -->
          <Column header="周次" style="min-width:80px">
            <template #body="{ data }">
              <Tag :value="`第${data.week_num || '-'}周`" severity="info" />
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

          <!-- 评分 -->
          <Column header="评分" style="min-width:80px">
            <template #body="{ data }">
              <span v-if="data.total_score" class="score-badge">{{ data.total_score }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </Column>

          <!-- 等级 -->
          <Column header="等级" style="min-width:60px">
            <template #body="{ data }">
              <span v-if="data.grade" :class="['grade-tag', gradeClass(data.grade)]">{{ getGradeName(data.grade) }}</span>
              <span v-else class="text-muted">-</span>
            </template>
          </Column>

          <!-- 是否补周报 -->
          <Column header="是否补周报" style="min-width:100px">
            <template #body="{ data }">
              <Tag :value="data.report_type === 'catch_up' ? '是' : '否'"
                :severity="data.report_type === 'catch_up' ? 'warn' : 'success'" />
            </template>
          </Column>

          <!-- 提交时间 -->
          <Column header="提交时间" style="min-width:160px">
            <template #body="{ data }">
              <span class="text-muted">{{ formatBeijingTime(data.submit_time || data.created_at) }}</span>
            </template>
          </Column>

          <!-- 操作 -->
          <Column header="操作" style="min-width:180px">
            <template #body="{ data }">
              <div class="action-buttons">
                <router-link :to="`/reports/${data.id}`">
                  <Button label="查看" icon="pi pi-eye" text size="small" v-tooltip="'查看详情'" />
                </router-link>
                <Button label="下载" icon="pi pi-download" text size="small"
                  @click="downloadReport(data)" v-tooltip="'下载周报文件'"
                  :disabled="!data.original_filename" />
                <Button label="删除" icon="pi pi-trash" text size="small" severity="danger"
                  @click="confirmDelete(data)" v-tooltip="'删除周报'" />
              </div>
            </template>
          </Column>
        </DataTable>
      </div>

    <!-- 单个删除确认对话框 -->
    <Dialog v-model:visible="deleteDialog.visible" header="确认删除" :style="{ width: '450px' }" modal>
      <div class="confirmation-content">
        <i class="pi pi-exclamation-triangle mr-3" style="font-size: 2rem" />
        <span>确定要删除周报吗？</span>
        <div class="delete-info">
          <div><strong>提交人：</strong>{{ deleteDialog.report?.author_name }}</div>
          <div><strong>周次：</strong>第{{ deleteDialog.report?.week_num }}周</div>
          <div><strong>提交时间：</strong>{{ formatBeijingTime(deleteDialog.report?.submit_time) }}</div>
        </div>
        <div class="warning-text">删除后将无法恢复，请谨慎操作！</div>
      </div>
      <template #footer>
        <Button label="取消" icon="pi pi-times" @click="deleteDialog.visible = false" text />
        <Button label="确认删除" icon="pi pi-check" @click="executeDelete" severity="danger" autofocus />
      </template>
    </Dialog>

    <!-- 批量删除确认对话框 -->
    <Dialog v-model:visible="batchDeleteDialog.visible" header="批量删除确认" :style="{ width: '450px' }" modal>
      <div class="confirmation-content">
        <i class="pi pi-exclamation-triangle mr-3" style="font-size: 2rem" />
        <span>确定要删除选中的 <strong>{{ selectedReports.length }}</strong> 份周报吗？</span>
        <div class="warning-text">此操作不可恢复！删除后将无法恢复这些周报数据。</div>
      </div>
      <template #footer>
        <Button label="取消" icon="pi pi-times" @click="batchDeleteDialog.visible = false" text />
        <Button label="确认删除" icon="pi pi-check" @click="executeBatchDelete" severity="danger" autofocus />
      </template>
    </Dialog>

    <!-- 导出加载遮罩 -->
    <div v-if="exportLoading" class="export-overlay">
      <div class="export-loading">
        <i class="pi pi-spin pi-spinner" style="font-size: 2rem" />
        <span>正在导出数据...</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { reportAPI } from '../api'
import { useDataRefresh, getReportEvents } from '../composables/useDataRefresh'
import { useDataOperation } from '../composables/useDataOperation'
import { DataEventType } from '../utils/dataEvents'
import { formatBeijingTime } from '../utils/timeUtil'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ColumnGroup from 'primevue/columngroup'
import Row from 'primevue/row'
import Button from 'primevue/button'
import Tag from 'primevue/tag'
import InputText from 'primevue/inputtext'
import Dropdown from 'primevue/dropdown'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const { operationInProgress: deleting, execute } = useDataOperation()

const exportLoading = ref(false)
const tableRefreshKey = ref(0)
const reports = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const selectedReports = ref([])

// 筛选条件
const filters = ref({
  author_name: '',
  department: '',
  is_catch_up: null,
  sort_by: null,
  sort_order: 'desc'
})

// 筛选选项
const catchUpOptions = [
  { label: '全部', value: null },
  { label: '是', value: 'yes' },
  { label: '否', value: 'no' }
]

const sortOptions = [
  { label: '默认排序', value: null },
  { label: '周次', value: 'week' },
  { label: '提交时间', value: 'submit_time' }
]

const orderOptions = [
  { label: '降序', value: 'desc' },
  { label: '升序', value: 'asc' }
]

// 删除确认对话框
const deleteDialog = ref({
  visible: false,
  report: null
})

// 批量删除确认对话框
const batchDeleteDialog = ref({
  visible: false
})

const gradeNames = { '优': '优', '良': '良', '一般': '一般', '差': '差' }

function gradeClass(g) {
  return { '优': 'grade-you', '良': 'grade-liang', '一般': 'grade-yiban', '差': 'grade-cha' }[g] || ''
}

function getGradeName(g) {
  return gradeNames[g] || g
}

async function loadReports() {
  const params = {
    page: page.value,
    size: pageSize.value
  }

  if (filters.value.author_name) {
    params.author_name = filters.value.author_name
  }
  if (filters.value.department) {
    params.department = filters.value.department
  }
  if (filters.value.is_catch_up) {
    params.is_catch_up = filters.value.is_catch_up
  }
  if (filters.value.sort_by) {
    params.sort_by = filters.value.sort_by
    params.sort_order = filters.value.sort_order
  }

  const res = await reportAPI.list(params)
  reports.value = res.data.items || []
  total.value = res.data.total || 0
  
  // 重置选择状态并强制刷新表格
  selectedReports.value = []
  tableRefreshKey.value++
}

function onPage(e) {
  page.value = e.page + 1
  loadReports()
}

function applyFilters() {
  page.value = 1
  loadReports()
}

function resetFilters() {
  filters.value = {
    author_name: '',
    department: '',
    is_catch_up: null,
    sort_by: null,
    sort_order: 'desc'
  }
  page.value = 1
  loadReports()
}

function onSelectionChange(e) {
  selectedReports.value = e
}

async function downloadReport(report) {
  try {
    const res = await reportAPI.download(report.id)
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', report.original_filename || `周报_${report.id}.xlsx`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    toast.add({ severity: 'success', summary: '下载成功', life: 2000 })
  } catch (e) {
    console.error('[ReportList] 下载失败:', e)
    toast.add({ severity: 'error', summary: '下载失败', detail: e.userMessage || '请稍后重试', life: 3000 })
  }
}

async function exportReports() {
  if (!selectedReports.value || selectedReports.value.length === 0) {
    toast.add({ severity: 'warn', summary: '请先选择要导出的周报', life: 2000 })
    return
  }

  exportLoading.value = true
  try {
    const reportIds = selectedReports.value.map(r => r.id)
    const res = await reportAPI.export(reportIds)
    
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const link = document.createElement('a')
    link.href = url
    
    let filename = null
    const disposition = res.headers['content-disposition']
    if (disposition) {
      const match = disposition.match(/filename\*=UTF-8''(.+)/)
      if (match) {
        filename = decodeURIComponent(match[1])
      } else {
        const fallback = disposition.split('filename=')[1]
        if (fallback) filename = fallback.replace(/"/g, '')
      }
    }
    if (!filename) filename = `周报_${new Date().getTime()}.zip`
    link.setAttribute('download', filename)
    
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    
    toast.add({ severity: 'success', summary: '导出成功', life: 2000 })
  } catch (e) {
    console.error('[ReportList] 导出失败:', e)
    toast.add({ severity: 'error', summary: '导出失败', detail: e.userMessage || '请稍后重试', life: 3000 })
  } finally {
    exportLoading.value = false
  }
}

function confirmDelete(report) {
  deleteDialog.value.report = report
  deleteDialog.value.visible = true
}

async function executeDelete() {
  const reportId = deleteDialog.value.report?.id
  if (!reportId) return

  deleteDialog.value.visible = false

  const { success } = await execute(
    () => reportAPI.delete(reportId),
    {
      name: '删除周报',
      eventTypes: [DataEventType.REPORTS_CHANGED, DataEventType.LEADERBOARD_CHANGED],
      successMsg: '删除成功',
      errorMsg: '删除失败',
    }
  )

  if (success) {
    await loadReports()
  }
}

function confirmBatchDelete() {
  batchDeleteDialog.value.visible = true
}

async function executeBatchDelete() {
  const reportIds = selectedReports.value.map(r => r.id)
  if (reportIds.length === 0) {
    batchDeleteDialog.value.visible = false
    return
  }

  batchDeleteDialog.value.visible = false

  const { success } = await execute(
    () => reportAPI.batchDelete(reportIds),
    {
      name: '批量删除',
      eventTypes: [DataEventType.REPORTS_CHANGED, DataEventType.LEADERBOARD_CHANGED],
      successMsg: '批量删除成功',
      errorMsg: '批量删除失败',
    }
  )

  if (success) {
    selectedReports.value = []
    await loadReports()
  }
}

// 使用自动刷新 composable（autoLoad 默认 true，会在挂载时自动加载）
const { loading } = useDataRefresh({
  loadFn: loadReports,
  watchEvents: getReportEvents(),
  debounceMs: 300,
})
</script>

<style scoped>
/* ========== 批量操作工具栏 ========== */
.batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  margin-bottom: var(--spacing-lg);
  border: 1px solid var(--border-light);
}

.batch-info {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

.batch-info strong {
  color: var(--primary);
  font-weight: 600;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

/* ========== 筛选卡片 ========== */
.filter-card {
  margin-bottom: var(--spacing-lg);
}

.filter-card :deep(.p-card-body) {
  padding: var(--spacing-md);
}

.filter-card :deep(.p-card-content) {
  padding: 0;
}

.filter-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.filter-item label {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}

.filter-input {
  width: 150px;
}

.filter-dropdown {
  width: 120px;
}

.filter-button {
  margin-left: var(--spacing-sm);
}

.export-btn {
  background: var(--success);
  border-color: var(--success);
}

.export-btn:hover {
  background: var(--success-hover);
  border-color: var(--success-hover);
}

/* ========== 列表容器 ========== */
.list-container {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.list-container :deep(.p-datatable) {
  min-width: 1000px;
}

.list-container :deep(.p-datatable-emptymessage) {
  background: var(--bg-card) !important;
}

.list-container .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  padding: var(--spacing-3xl);
  color: var(--text-muted);
}

.list-card .empty-state .empty-icon {
  font-size: 4rem;
  opacity: 0.4;
  margin-bottom: var(--spacing-lg);
}

.list-card .empty-state .empty-text {
  font-size: var(--text-lg);
  color: var(--text-secondary);
}

.text-muted {
  color: var(--text-muted);
  font-size: var(--text-sm);
}

/* ========== 操作按钮 ========== */
.action-buttons {
  display: flex;
  gap: var(--spacing-xs);
}

/* ========== 删除确认对话框 ========== */
.confirmation-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-lg);
  text-align: center;
}

.confirmation-content i {
  color: var(--color-warning);
  margin-bottom: var(--spacing-md);
}

.delete-info {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  text-align: left;
}

.delete-info div {
  margin-bottom: var(--spacing-xs);
}

.warning-text {
  margin-top: var(--spacing-md);
  color: var(--color-danger);
  font-size: var(--text-sm);
}

/* ========== 导出加载遮罩 ========== */
.export-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.export-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-xl);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  color: var(--text-primary);
}

/* ========== 响应式断点 ========== */
@media (max-width: 1024px) {
  .filter-row {
    flex-wrap: wrap;
  }

  .filter-input {
    width: 120px;
  }

  .filter-dropdown {
    width: 100px;
  }

  .list-card :deep(.p-datatable) {
    min-width: 900px;
  }
}

@media (max-width: 640px) {
  .batch-toolbar {
    flex-direction: column;
    gap: var(--spacing-md);
  }

  .filter-item {
    flex-direction: column;
    align-items: flex-start;
    width: 100%;
  }

  .filter-input,
  .filter-dropdown {
    width: 100%;
  }

  .filter-button {
    width: 100%;
    margin-left: 0;
  }

  .list-container :deep(.p-paginator) {
    flex-wrap: wrap;
    gap: var(--spacing-xs);
  }

  .action-buttons {
    flex-direction: column;
  }
}
</style>