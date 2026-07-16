<template>
  <div class="business-dashboard">
    <div class="page-header">
      <div class="header-actions">
        <div class="week-selector">
          <Dropdown
            v-model="selectedYear"
            :options="yearOptions"
            optionLabel="label"
            optionValue="value"
            placeholder="选择年份"
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
        <Button
          label="生成总结"
          icon="pi pi-refresh"
          :loading="generating"
          @click="generateAll"
          severity="primary"
        />
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <ProgressSpinner />
    </div>

    <div v-else-if="departmentsWithData.length === 0" class="empty-state">
      <i class="pi pi-inbox"></i>
      <p>暂无业务数据</p>
      <p class="sub-text">请先在系统设置中生成部门总结</p>
    </div>

    <div v-else class="department-grid">
      <div
        v-for="dept in departmentsWithData"
        :key="dept.id"
        class="department-card"
        :class="{ highlighted: dept.is_department_highlight }"
        @click="openDrawer(dept)"
      >
        <div class="card-header">
          <div
            class="department-name"
            @click.stop="toggleDepartmentHighlight(dept)"
          >
            {{ dept.department_name }}
            <i
              v-if="dept.is_department_highlight"
              class="pi pi-star-fill highlight-icon"
            ></i>
          </div>
          <Tag
            :value="getStatusText(dept.status)"
            :severity="getStatusSeverity(dept.status)"
          />
        </div>

        <div class="card-content">
          <div class="summary-section">
            <div class="section-title">
              <i class="pi pi-calendar"></i>
              上周已完成项目
            </div>
            <div class="project-list">
              <div
                v-for="(project, idx) in (dept.last_week_projects || [])"
                :key="idx"
                class="project-item"
                :class="{ 'project-highlight': project.highlight }"
              >
                <div class="project-header">
                  <span class="project-name" :class="{ 'project-name-bold': project.highlight }">
                    {{ project.name }}
                  </span>
                  <div class="project-progress-wrapper">
                    <div class="progress-bar-bg">
                      <div
                        class="progress-bar-fill"
                        :style="{ width: project.progress + '%' }"
                        :class="getProgressColor(project.progress)"
                      ></div>
                    </div>
                    <span class="progress-text">{{ project.progress }}%</span>
                  </div>
                </div>
              </div>
              <div v-if="!dept.last_week_projects?.length" class="empty-text">
                暂无数据
              </div>
            </div>
          </div>

          <div class="summary-section">
            <div class="section-title">
              <i class="pi pi-calendar-plus"></i>
              本周进行中项目
            </div>
            <div class="project-list">
              <div
                v-for="(project, idx) in (dept.this_week_projects || [])"
                :key="idx"
                class="project-item"
                :class="{ 'project-highlight': project.highlight }"
              >
                <div class="project-header">
                  <span class="project-name" :class="{ 'project-name-bold': project.highlight }">
                    {{ project.name }}
                  </span>
                </div>
              </div>
              <div v-if="!dept.this_week_projects?.length" class="empty-text">
                暂无数据
              </div>
            </div>
          </div>
        </div>

        <div class="card-footer">
          <span class="generated-time" v-if="dept.generated_at">
            生成于 {{ formatTime(dept.generated_at) }}
          </span>
          <span class="generated-time" v-else>未生成</span>
        </div>
      </div>
    </div>

    <!-- 部门详情抽屉 - 全屏展开，左右分栏 -->
    <Drawer
      v-model:visible="drawerVisible"
      position="full"
      header="部门详情"
    >
      <div v-if="selectedDepartment" class="drawer-content-full">
        <div class="drawer-header">
          <h2>{{ selectedDepartment.department_name }}</h2>
          <div class="drawer-actions">
            <Button
              label="重新生成"
              icon="pi pi-refresh"
              :loading="generatingDept"
              @click="generateDept"
              severity="primary"
              size="small"
            />
          </div>
        </div>

        <div class="drawer-body">
          <!-- 左侧：上周工作内容（有进度） -->
          <div class="drawer-column">
            <div class="column-header">
              <i class="pi pi-calendar"></i>
              <h3>上周工作内容</h3>
              <span class="column-badge">已预估进度</span>
            </div>
            <div class="project-detail-list">
              <div
                v-for="(project, idx) in (selectedDepartment.last_week_projects || [])"
                :key="idx"
                class="project-detail-item"
                :class="{ 'project-detail-highlight': project.highlight }"
              >
                <div class="project-detail-header">
                  <span class="project-detail-name" :class="{ 'project-detail-name-bold': project.highlight }">
                    {{ project.name }}
                  </span>
                  <div class="project-detail-progress">
                    <div class="progress-bar-bg">
                      <div
                        class="progress-bar-fill"
                        :style="{ width: project.progress + '%' }"
                        :class="getProgressColor(project.progress)"
                      ></div>
                    </div>
                    <span class="progress-text">{{ project.progress }}%</span>
                  </div>
                </div>
                <div class="project-detail-summary" v-if="project.summary">
                  {{ project.summary }}
                </div>
                <div class="item-persons" v-if="project.persons?.length">
                  <Tag
                    v-for="person in project.persons"
                    :key="person"
                    :value="person"
                    severity="info"
                    class="person-tag"
                  />
                </div>
              </div>
              <div v-if="!selectedDepartment.last_week_projects?.length" class="empty-text">
                暂无数据
              </div>
            </div>
          </div>

          <!-- 右侧：本周工作计划（无进度） -->
          <div class="drawer-column">
            <div class="column-header">
              <i class="pi pi-calendar-plus"></i>
              <h3>本周工作计划</h3>
              <span class="column-badge secondary">待执行</span>
            </div>
            <div class="project-detail-list">
              <div
                v-for="(project, idx) in (selectedDepartment.this_week_projects || [])"
                :key="idx"
                class="project-detail-item"
                :class="{ 'project-detail-highlight': project.highlight }"
              >
                <div class="project-detail-header-no-progress">
                  <span class="project-detail-name" :class="{ 'project-detail-name-bold': project.highlight }">
                    {{ project.name }}
                  </span>
                </div>
                <div class="project-detail-summary" v-if="project.summary">
                  {{ project.summary }}
                </div>
                <div class="item-persons" v-if="project.persons?.length">
                  <Tag
                    v-for="person in project.persons"
                    :key="person"
                    :value="person"
                    severity="info"
                    class="person-tag"
                  />
                </div>
              </div>
              <div v-if="!selectedDepartment.this_week_projects?.length" class="empty-text">
                暂无数据
              </div>
            </div>
          </div>
        </div>

        <!-- 涉及人员 -->
        <div class="drawer-footer" v-if="persons.length > 0">
          <h3>
            <i class="pi pi-users"></i>
            涉及人员
          </h3>
          <div class="person-list">
            <div
              v-for="person in persons"
              :key="person.name"
              class="person-item"
            >
              <span class="person-name">{{ person.name }}</span>
              <span class="person-position" v-if="person.position">
                {{ person.position }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { businessAPI } from '../api'
import { useToast } from 'primevue/usetoast'
import Dropdown from 'primevue/dropdown'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'
import Drawer from 'primevue/drawer'

const toast = useToast()

const loading = ref(false)
const generating = ref(false)
const generatingDept = ref(false)
const departments = ref([])
const selectedWeek = ref(new Date())
const selectedYear = ref(new Date().getFullYear())
const selectedWeekLabel = ref('')
const drawerVisible = ref(false)
const selectedDepartment = ref(null)
const persons = ref([])

/** 获取 ISO 周数 */
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

/** 获取周日日期 */
function getSunday(d) {
  const monday = getMonday(d)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  return sunday
}

/** 格式化日期 YYYY-MM-DD */
function formatDate(d) {
  if (!d) return ''
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 格式化日期 MM.DD */
function formatDateShort(d) {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${m}.${day}`
}

/** 生成年份选项列表（最近3年） */
const yearOptions = computed(() => {
  const currentYear = new Date().getFullYear()
  return [
    { label: `${currentYear}年`, value: currentYear },
    { label: `${currentYear - 1}年`, value: currentYear - 1 },
    { label: `${currentYear - 2}年`, value: currentYear - 2 },
  ]
})

/** 生成指定年份的周选项列表 */
function generateWeekOptionsForYear(year) {
  const options = []
  // 找到该年第1周的周一（ISO 8601）
  const jan4 = new Date(year, 0, 4) // 1月4日一定在第1周
  const jan4Day = jan4.getDay() || 7 // 周日=7
  const firstMonday = new Date(jan4)
  firstMonday.setDate(jan4.getDate() - (jan4Day - 1))
  
  // 生成53周选项
  for (let week = 1; week <= 53; week++) {
    const monday = new Date(firstMonday)
    monday.setDate(firstMonday.getDate() + (week - 1) * 7)
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    
    // 只包含该年内的周
    if (monday.getFullYear() === year || sunday.getFullYear() === year) {
      const label = `第${week}周 ${formatDateShort(monday)}~${formatDateShort(sunday)}`
      const value = formatDate(monday)
      options.push({ label, value })
    }
  }
  return options
}

/** 根据选中年份过滤周选项 */
const filteredWeekOptions = computed(() => {
  return generateWeekOptionsForYear(selectedYear.value)
})

/** 周显示文本 */
const weekDisplayText = computed(() => {
  const d = selectedWeek.value
  if (!d) return ''
  const year = d.getFullYear()
  const weekNum = getISOWeek(d)
  const monday = getMonday(d)
  const sunday = getSunday(d)
  return `${year}年第${weekNum}周 ${formatDateShort(monday)}~${formatDateShort(sunday)}`
})

/** 过滤有数据的部门（必须有项目） */
const departmentsWithData = computed(() => {
  return departments.value.filter(dept => {
    // 有上周或本周项目才算有数据
    const hasProjects = (dept.last_week_projects?.length || 0) > 0 || 
                        (dept.this_week_projects?.length || 0) > 0
    return hasProjects
  })
})

/** 年份选择变更 */
function onYearChange(event) {
  selectedYear.value = event.value
  // 切换年份时，清空周选择，让用户重新选择
  selectedWeekLabel.value = ''
}

/** 周选择变更 */
function onWeekChange(event) {
  // event.value 是 YYYY-MM-DD 字符串，解析为本地日期并确保是周一
  const [y, m, d] = event.value.split('-').map(Number)
  selectedWeek.value = new Date(y, m - 1, d)
  loadDepartments()
}

const loadDepartments = async () => {
  loading.value = true
  try {
    const weekStart = formatDate(selectedWeek.value)
    const res = await businessAPI.list({ week_start: weekStart })
    const respData = res.data.data || res.data
    departments.value = respData.items || []
  } catch (error) {
    console.error('加载部门数据失败:', error)
    toast.add({
      severity: 'error',
      summary: '加载失败',
      detail: error.message || '无法加载部门数据',
      life: 3000,
    })
  } finally {
    loading.value = false
  }
}

/** 异步生成任务ID */
const generatingTaskId = ref(null)
/** 轮询定时器 */
let pollTimer = null

/** 开始轮询生成状态 */
const startPolling = () => {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = setInterval(async () => {
    try {
      const weekStart = formatDate(selectedWeek.value)
      const res = await businessAPI.list({ week_start: weekStart })
      const respData = res.data.data || res.data
      departments.value = respData.items || []
      const genInProgress = respData.generation_in_progress || false

      // 检查是否所有部门都生成完成
      const allDone = departments.value.every(
        dept => dept.status === 'done' || dept.status === 'failed'
      )

      // 检查是否所有部门都是 pending（无数据场景）
      const allPending = departments.value.every(
        dept => dept.status === 'pending'
      )

      // 生成任务已完成（锁已释放）时停止轮询
      if (!genInProgress && (allDone || allPending)) {
        stopPolling()
        generating.value = false
        if (allDone && departments.value.length > 0) {
          toast.add({
            severity: 'success',
            summary: '生成完成',
            detail: '所有部门总结已生成',
            life: 3000,
          })
        } else {
          toast.add({
            severity: 'info',
            summary: '本周暂无数据',
            detail: '请先上传本周周报数据',
            life: 3000,
          })
        }
      }
    } catch (error) {
      console.error('轮询失败:', error)
    }
  }, 3000) // 每3秒轮询一次
}

/** 停止轮询 */
const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const generateAll = async () => {
  generating.value = true
  toast.add({
    severity: 'info',
    summary: '正在生成',
    detail: '业务盘数据正在后台生成，请稍候...',
    life: 5000,
  })

  // 立即启动轮询（不等待 API 返回）
  startPolling()

  // 异步发送生成请求，不阻塞轮询
  businessAPI.generateAll({ week_start: formatDate(selectedWeek.value) }).catch(error => {
    console.error('生成任务失败:', error)
    // 409 表示上一轮还在进行中，不显示错误（轮询会继续）
    if (error.response?.status !== 409) {
      const errorMsg = error.response?.data?.detail || error.message || '生成任务异常'
      toast.add({
        severity: 'error',
        summary: '生成失败',
        detail: errorMsg,
        life: 3000,
      })
    }
  })

  // 超时保护：60秒后如果轮询还没停止，强制停止
  setTimeout(() => {
    if (generating.value) {
      stopPolling()
      generating.value = false
      toast.add({
        severity: 'warning',
        summary: '生成超时',
        detail: '生成任务响应超时，请刷新页面重试',
        life: 3000,
      })
    }
  }, 60000)
}

const generateDept = async () => {
  if (!selectedDepartment.value) return
  generatingDept.value = true
  try {
    const weekStart = formatDate(selectedWeek.value)
    await businessAPI.generateDept(selectedDepartment.value.department_id, {
      week_start: weekStart,
    })
    toast.add({
      severity: 'info',
      summary: '正在生成',
      detail: '部门总结正在后台生成，请稍候...',
      life: 5000,
    })

    // 轮询等待生成完成
    let attempts = 0
    const maxAttempts = 20 // 最多轮询 60 秒
    const pollInterval = setInterval(async () => {
      attempts++
      try {
        const res = await businessAPI.get(selectedDepartment.value.department_id, { week_start: weekStart })
        const respData = res.data.data || res.data
        const status = respData?.status
        if (status === 'done' || status === 'failed' || attempts >= maxAttempts) {
          clearInterval(pollInterval)
          generatingDept.value = false
          if (status === 'done') {
            toast.add({
              severity: 'success',
              summary: '生成成功',
              detail: '部门总结已重新生成',
              life: 3000,
            })
          } else if (status === 'failed') {
            toast.add({
              severity: 'error',
              summary: '生成失败',
              detail: respData?.error_message || 'AI 生成失败',
              life: 3000,
            })
          } else {
            toast.add({
              severity: 'warning',
              summary: '生成超时',
              detail: '生成任务响应超时，请刷新页面重试',
              life: 3000,
            })
          }
          await loadDepartments()
          await loadDepartmentDetail(selectedDepartment.value.department_id)
        }
      } catch (e) {
        console.error('轮询部门生成状态失败:', e)
      }
    }, 3000)
  } catch (error) {
    console.error('生成失败:', error)
    generatingDept.value = false
    const errorMsg = error.response?.data?.detail || error.message || '无法生成部门总结'
    toast.add({
      severity: 'error',
      summary: '生成失败',
      detail: errorMsg,
      life: 3000,
    })
  }
}

const openDrawer = async (dept) => {
  selectedDepartment.value = dept
  drawerVisible.value = true
  await loadDepartmentDetail(dept.department_id)
}

const loadDepartmentDetail = async (deptId) => {
  try {
    const weekStart = formatDate(selectedWeek.value)
    const res = await businessAPI.get(deptId, { week_start: weekStart })
    const respData = res.data.data || res.data
    selectedDepartment.value = respData
    persons.value = respData.persons || []
  } catch (error) {
    console.error('加载部门详情失败:', error)
  }
}

const toggleDepartmentHighlight = async (dept) => {
  try {
    const weekStart = formatDate(selectedWeek.value)
    await businessAPI.updateHighlight(dept.department_id, {
      week_start: weekStart,
      type: 'department',
      highlight: !dept.is_department_highlight,
    })
    dept.is_department_highlight = !dept.is_department_highlight
  } catch (error) {
    console.error('更新重点状态失败:', error)
    toast.add({
      severity: 'error',
      summary: '更新失败',
      detail: error.message || '无法更新重点状态',
      life: 3000,
    })
  }
}

const toggleItemHighlight = async (dept, itemType, idx, item) => {
  try {
    const weekStart = formatDate(selectedWeek.value)
    await businessAPI.updateHighlight(dept.department_id, {
      week_start: weekStart,
      type: 'item',
      item_type: itemType,
      item_index: idx,
      highlight: !item.highlight,
    })
    item.highlight = !item.highlight
  } catch (error) {
    console.error('更新重点状态失败:', error)
    toast.add({
      severity: 'error',
      summary: '更新失败',
      detail: error.message || '无法更新重点状态',
      life: 3000,
    })
  }
}

const formatTime = (timeStr) => {
  if (!timeStr) return ''
  const date = new Date(timeStr)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hour}:${minute}`
}

const getStatusText = (status) => {
  const map = {
    pending: '待生成',
    generating: '生成中',
    done: '已生成',
    failed: '生成失败',
  }
  return map[status] || status
}

const getStatusSeverity = (status) => {
  const map = {
    pending: 'secondary',
    generating: 'warn',
    done: 'success',
    failed: 'danger',
  }
  return map[status] || 'secondary'
}

const getProgressColor = (progress) => {
  if (progress >= 80) return 'progress-success'
  if (progress >= 50) return 'progress-warning'
  return 'progress-danger'
}

onMounted(async () => {
  // 初始化：默认显示本周时间
  const currentMonday = getMonday(new Date())
  selectedWeek.value = currentMonday
  selectedYear.value = currentMonday.getFullYear()
  
  // 获取当前周对应的 value（Dropdown 需要绑定 optionValue，即日期字符串）
  const currentWeekOptions = generateWeekOptionsForYear(selectedYear.value)
  const currentWeekOpt = currentWeekOptions.find(opt => opt.value === formatDate(currentMonday))
  if (currentWeekOpt) {
    selectedWeekLabel.value = currentWeekOpt.value
  }
  
  // 加载当前周数据（不自动切换到上一周）
  await loadDepartments()
})
</script>

<style scoped>
.business-dashboard {
  padding: 24px;
  max-width: 1600px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.page-header h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: var(--text-color);
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.week-selector {
  display: flex;
  align-items: center;
  gap: 8px;
}

.week-dropdown {
  min-width: 280px;
}

.week-dropdown :deep(.p-dropdown-label) {
  font-size: 14px;
  font-weight: 500;
}

.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 400px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 400px;
  color: var(--text-color-secondary);
}

.empty-state i {
  font-size: 64px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-state p {
  margin: 8px 0;
  font-size: 16px;
}

.empty-state .sub-text {
  font-size: 14px;
  opacity: 0.7;
}

.department-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: 24px;
}

.department-card {
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  padding: 0;
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06), 0 1px 2px rgba(0, 0, 0, 0.04);
  overflow: hidden;
}

.department-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.1), 0 2px 6px rgba(0, 0, 0, 0.06);
  transform: translateY(-3px);
  border-color: #cbd5e1;
}

.department-card.highlighted {
  border-color: var(--primary-color);
  box-shadow: 0 0 0 1px var(--primary-color), 0 4px 16px rgba(0, 0, 0, 0.08);
}

.department-card.highlighted:hover {
  box-shadow: 0 0 0 1px var(--primary-color), 0 8px 24px rgba(0, 0, 0, 0.12);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 22px 14px;
  border-bottom: 1px solid #f1f5f9;
}

.department-name {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.department-name:hover {
  color: var(--primary-color);
}

.highlight-icon {
  color: #f59e0b;
  font-size: 16px;
}

.card-content {
  display: flex;
  flex-direction: column;
  padding: 16px 22px;
  gap: 16px;
}

.summary-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.section-title i {
  font-size: 14px;
  color: #94a3b8;
}

.project-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.project-item {
  padding: 12px 14px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.project-item:hover {
  background: #f1f5f9;
  border-color: #e2e8f0;
}

.project-item.project-highlight {
  background: #fffbeb;
  border-color: #fde68a;
}

.project-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.project-name {
  font-size: 14px;
  color: #334155;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.project-name-bold {
  font-weight: 700;
  color: #1e293b;
}

.project-progress-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  min-width: 120px;
}

.progress-bar-bg {
  flex: 1;
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.progress-bar-fill.progress-success {
  background: linear-gradient(90deg, #10b981, #34d399);
}

.progress-bar-fill.progress-warning {
  background: linear-gradient(90deg, #f59e0b, #fbbf24);
}

.progress-bar-fill.progress-danger {
  background: linear-gradient(90deg, #ef4444, #f87171);
}

.progress-text {
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  min-width: 40px;
  text-align: right;
}

.empty-text {
  font-size: 13px;
  color: #94a3b8;
  padding: 8px 4px;
  font-style: italic;
}

.card-footer {
  margin-top: 0;
  padding: 12px 22px;
  border-top: 1px solid #f1f5f9;
  background: #fafbfc;
}

.generated-time {
  font-size: 12px;
  color: #94a3b8;
}

.drawer-content {
  padding: 24px;
}

.drawer-content h2 {
  margin: 0 0 28px 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-color);
  padding-bottom: 16px;
  border-bottom: 2px solid #f1f5f9;
}

.detail-section {
  margin-bottom: 28px;
}

.detail-section h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px 0;
  font-size: 15px;
  font-weight: 600;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.detail-section h3 i {
  color: #94a3b8;
  font-size: 16px;
}

.detail-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.detail-item {
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

.detail-item:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.item-header {
  margin-bottom: 10px;
}

.item-header .item-content {
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.item-persons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.person-tag {
  font-size: 12px;
}

.person-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.person-item {
  padding: 14px 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: all 0.2s ease;
}

.person-item:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.person-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
}

.person-position {
  font-size: 12px;
  color: #94a3b8;
}

.project-detail-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.project-detail-item {
  padding: 16px 18px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  transition: all 0.2s ease;
}

.project-detail-item:hover {
  background: #f1f5f9;
  border-color: #cbd5e1;
}

.project-detail-item.project-detail-highlight {
  background: #fffbeb;
  border-color: #fde68a;
}

.project-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.project-detail-name {
  font-size: 15px;
  color: #334155;
  flex: 1;
}

.project-detail-name-bold {
  font-weight: 700;
  color: #1e293b;
}

.project-detail-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  min-width: 140px;
}

.project-detail-summary {
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
  margin-bottom: 10px;
  padding: 8px 12px;
  background: #ffffff;
  border-radius: 6px;
  border-left: 3px solid #e2e8f0;
}

.project-detail-item.project-detail-highlight .project-detail-summary {
  border-left-color: #f59e0b;
}

.drawer-actions {
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid #f1f5f9;
}

/* 全屏抽屉样式 */
.drawer-content-full {
  padding: 24px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 2px solid #f1f5f9;
}

.drawer-header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: var(--text-color);
}

.drawer-body {
  flex: 1;
  display: flex;
  gap: 24px;
  overflow: hidden;
}

.drawer-column {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding-right: 12px;
}

.drawer-column::-webkit-scrollbar {
  width: 6px;
}

.drawer-column::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 3px;
}

.drawer-column::-webkit-scrollbar-thumb {
  background: #cbd5e1;
  border-radius: 3px;
}

.drawer-column::-webkit-scrollbar-thumb:hover {
  background: #94a3b8;
}

.column-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e2e8f0;
}

.column-header i {
  font-size: 18px;
  color: #64748b;
}

.column-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #334155;
}

.column-badge {
  padding: 4px 10px;
  background: #10b981;
  color: white;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.column-badge.secondary {
  background: #64748b;
}

.drawer-footer {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #f1f5f9;
}

.drawer-footer h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px 0;
  font-size: 15px;
  font-weight: 600;
  color: #64748b;
}

.drawer-footer h3 i {
  color: #94a3b8;
  font-size: 16px;
}

.project-detail-header-no-progress {
  margin-bottom: 10px;
}

.project-detail-header-no-progress .project-detail-name {
  font-size: 15px;
  color: #334155;
}
</style>
