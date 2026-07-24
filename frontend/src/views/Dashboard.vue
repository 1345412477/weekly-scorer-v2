<template>
  <div class="dashboard page-content">
    <!-- 顶部概览 -->
    <div class="overview-row fade-in-up" style="--delay: 0ms">
      <div class="overview-item clickable fade-in-up" :style="{ '--delay': (80 * 0) + 'ms' }" @click="showTotalPersonsDialog">
        <span class="overview-label">本周应提交</span>
        <span class="overview-value">{{ animatedTotalPersons }}</span>
      </div>
      <div class="overview-item clickable fade-in-up" :style="{ '--delay': (80 * 1) + 'ms' }" @click="showSubmittedDialog">
        <span class="overview-label">已提交</span>
        <span class="overview-value highlight-green">{{ animatedSubmitted }}</span>
      </div>
    </div>

    <!-- 异常人员 + 正在进行项目 -->
    <div class="panels-grid-two">
      <!-- 异常人员 -->
      <section class="panel fade-in-up" :style="{ '--delay': '120ms' }">
        <header class="panel-header">
          <div>
            <h3>本周异常人员</h3>
            <p class="panel-sub-title">未提交 {{ notSubmittedCount }} 人 · 迟交 {{ lateSubmittedCount }} 人</p>
          </div>
          <span class="panel-count">{{ abnormalPersons.length }} 人</span>
        </header>
        <div class="panel-body">
          <div v-if="abnormalPersons.length === 0" class="empty-state fade-in-up" style="--delay: 80ms">
            <i class="pi pi-check-circle empty-icon success"></i>
            <span>全员正常提交，非常棒！</span>
          </div>
          <div v-else class="list-items">
            <div
              v-for="(item, idx) in abnormalPersons"
              :key="item.name"
              class="list-item fade-in-up"
              :style="{ '--delay': (120 + idx * 40) + 'ms' }"
            >
              <span class="item-index">{{ idx + 1 }}</span>
              <div class="item-main">
                <span class="item-name">{{ item.name }}</span>
                <span class="item-meta">{{ item.department || '未分配' }}{{ item.position ? ' · ' + item.position : '' }}</span>
              </div>
              <span :class="['item-badge', item.status === '未提交' ? 'item-badge-warn' : 'item-badge-late']">
                {{ item.status }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- 正在进行项目 -->
      <section class="panel fade-in-up" :style="{ '--delay': '200ms' }">
        <header class="panel-header">
          <div>
            <h3>正在进行项目</h3>
            <p class="panel-sub-title">本周 {{ currentProjects.length }} 个项目</p>
          </div>
        </header>
        <div class="panel-body">
          <div v-if="currentProjects.length === 0" class="empty-state fade-in-up" style="--delay: 80ms">
            <i class="pi pi-folder empty-icon muted"></i>
            <span>本周暂无项目信息</span>
          </div>
          <div v-else class="project-list">
            <div
              v-for="(proj, idx) in currentProjects"
              :key="proj.name"
              class="project-item fade-in-up"
              :class="{ 'project-highlight': proj.highlight }"
              :style="{ '--delay': (200 + idx * 60) + 'ms' }"
            >
              <div class="project-header">
                <div class="project-name-row">
                  <i v-if="proj.highlight" class="pi pi-star-fill project-star"></i>
                  <span class="project-name">{{ proj.name }}</span>
                  <span class="project-progress-badge" :class="progressClass(proj.progress)">{{ proj.progress }}%</span>
                </div>
                <div class="project-departments">
                  <span v-for="dept in proj.departments" :key="dept" class="project-dept-tag">{{ dept }}</span>
                </div>
              </div>
              <div class="project-progress-bar">
                <div class="project-progress-fill" :style="{ width: proj.progress + '%' }"></div>
              </div>
              <p v-if="proj.summary" class="project-summary">{{ proj.summary }}</p>
              <div class="project-persons">
                <span v-for="person in proj.persons" :key="person" class="project-person-tag">{{ person }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 人员详情对话框 -->
    <Dialog v-model:visible="personsDialogVisible" :header="personsDialogTitle" modal :style="{ width: '600px', maxHeight: '80vh' }">
      <div class="persons-dialog-content">
        <div v-if="personsDialogList.length === 0" class="empty-state">
          <i class="pi pi-inbox empty-icon muted"></i>
          <span>暂无人员数据</span>
        </div>
        <div v-else class="persons-list">
          <div v-for="(person, idx) in personsDialogList" :key="person.name" class="person-item">
            <span class="person-index">{{ idx + 1 }}</span>
            <div class="person-info">
              <span class="person-name">{{ person.name }}</span>
              <span class="person-meta">{{ person.department || '未分配' }}{{ person.position ? ' · ' + person.position : '' }}</span>
            </div>
            <span v-if="person.status" :class="['person-badge', person.status === '未提交' ? 'badge-warn' : 'badge-late']">
              {{ person.status }}
            </span>
          </div>
        </div>
      </div>
    </Dialog>

    <!-- 历史项目情况 -->
    <section class="panel fade-in-up" :style="{ '--delay': '300ms' }">
      <header class="panel-header">
        <div>
          <h3>历史项目情况</h3>
        </div>
        <div class="history-nav" v-if="historyWeeks.length > 1">
          <button class="nav-btn" @click="prevHistoryWeek" :disabled="historyWeekIndex === 0">
            <i class="pi pi-chevron-left"></i>
          </button>
          <span class="history-nav-label">{{ historyWeekIndex + 1 }} / {{ historyWeeks.length }}</span>
          <button class="nav-btn" @click="nextHistoryWeek" :disabled="historyWeekIndex === historyWeeks.length - 1">
            <i class="pi pi-chevron-right"></i>
          </button>
        </div>
      </header>
      <div class="panel-body">
        <div v-if="historyWeeks.length === 0" class="empty-state fade-in-up" style="--delay: 80ms">
          <i class="pi pi-history empty-icon muted"></i>
          <span>暂无历史项目数据</span>
        </div>
        <div v-else class="history-week">
          <div class="history-week-header">
            <i class="pi pi-calendar"></i>
            <span class="history-week-label">{{ currentHistoryWeek.week_label }}</span>
            <span class="history-week-count">{{ currentHistoryWeek.projects.length }} 个项目</span>
          </div>
          <div class="history-projects">
            <div
              v-for="proj in currentHistoryWeek.projects"
              :key="proj.name"
              class="history-project-item"
              :class="{ 'project-highlight': proj.highlight }"
            >
              <div class="history-proj-head">
                <i v-if="proj.highlight" class="pi pi-star-fill project-star"></i>
                <span class="history-proj-name">{{ proj.name }}</span>
                <span class="project-progress-badge" :class="progressClass(proj.progress)">{{ proj.progress }}%</span>
              </div>
              <p v-if="proj.summary" class="history-proj-summary">{{ proj.summary }}</p>
              <div class="project-persons">
                <span v-for="person in proj.persons" :key="person" class="project-person-tag">{{ person }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import Dialog from 'primevue/dialog'
import { leaderboardAPI, reportAPI } from '../api'
import { useDataRefresh, getDashboardEvents } from '../composables/useDataRefresh'

// 人员详情对话框
const personsDialogVisible = ref(false)
const personsDialogTitle = ref('')
const personsDialogList = ref([])
const allPersons = ref([]) // 所有在职人员（用于"本周应提交"弹窗）

function showTotalPersonsDialog() {
  personsDialogTitle.value = `本周应提交人员（${allPersons.value.length} 人）`
  personsDialogList.value = allPersons.value.map(p => ({
    name: p.name,
    department: p.department_name || '',
    position: p.position || '',
  }))
  personsDialogVisible.value = true
}

function showSubmittedDialog() {
  // 已提交 = 全部人员 - 异常人员
  const abnormalNames = new Set(abnormalPersons.value.map(p => p.name))
  const submitted = allPersons.value
    .filter(p => !abnormalNames.has(p.name))
    .map(p => ({ name: p.name, department: p.department_name || '', position: p.position || '' }))
  personsDialogTitle.value = `已提交人员（${submitted.length} 人）`
  personsDialogList.value = submitted
  personsDialogVisible.value = true
}

// 弹出确认对话框
const emitConfirm = (msg, onOk) => {
  if (window.confirm(msg)) onOk()
}

const abnormalPersons = ref([])
const notSubmittedCount = ref(0)
const lateSubmittedCount = ref(0)
const currentProjects = ref([])
const historyWeeks = ref([])
const historyWeekIndex = ref(0)

const currentHistoryWeek = computed(() => {
  return historyWeeks.value[historyWeekIndex.value] || { week_label: '', projects: [] }
})

function prevHistoryWeek() {
  if (historyWeekIndex.value > 0) historyWeekIndex.value--
}

function nextHistoryWeek() {
  if (historyWeekIndex.value < historyWeeks.value.length - 1) historyWeekIndex.value++
}
const totalPersons = ref(0)
const submittedCount = ref(0)
const stats = ref({ total_reports: 0, scored_reports: 0, avg_score: 0 })
const weeklyTrend = ref([])
const gradeDist = ref({})
const trendChartRef = ref(null)
const trendChartInstance = ref(null)
const gradeBarVisible = ref(false)

// 计数动画
const animatedTotalPersons = ref(0)
const animatedSubmitted = ref(0)
const animatedAbnormal = ref(0)
const animatedTotalReports = ref(0)
const animatedScoredReports = ref(0)
const animatedAvgScore = ref(0)

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3)
}

function animateNumber(target, from = 0, to = 0, duration = 900) {
  const start = performance.now()
  const diff = to - from
  function tick(now) {
    const p = Math.min(1, (now - start) / duration)
    target.value = Math.round(from + diff * easeOutCubic(p))
    if (p < 1) requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

function runAllCountAnims() {
  animateNumber(animatedTotalPersons, 0, totalPersons.value || 0)
  animateNumber(animatedSubmitted, 0, submittedCount.value || 0)
  animateNumber(animatedAbnormal, 0, abnormalPersons.value.length || 0)
  animateNumber(animatedTotalReports, 0, stats.value.total_reports || 0)
  animateNumber(animatedScoredReports, 0, stats.value.scored_reports || 0)
  animateNumber(animatedAvgScore, 0, Math.round(Number(stats.value.avg_score)) || 0, 1100)
}

function progressClass(progress) {
  if (progress >= 80) return 'progress-high'
  if (progress >= 50) return 'progress-mid'
  return 'progress-low'
}

const maxGrade = computed(() => {
  const values = Object.values(gradeDist.value || {})
  return values.length ? Math.max(...values) : 0
})

function gradeBarWidth(v) {
  if (!maxGrade.value) return 0
  return Math.round((v / maxGrade.value) * 100)
}

function gradeIdx(g) {
  return { '优': 1, '良': 2, '一般': 3, '差': 4 }[g] || 0
}

function gradeClass(g) {
  return { '优': 'grade-you', '良': 'grade-liang', '一般': 'grade-yiban', '差': 'grade-cha' }[g] || ''
}

const hasAnyData = computed(() => {
  const s = stats.value || {}
  return (s.total_reports || 0) > 0 ||
    (s.scored_reports || 0) > 0 ||
    (weeklyTrend.value || []).length > 0 ||
    Object.keys(gradeDist.value || {}).length > 0
})

async function confirmClearAll() {
  const s = stats.value || {}
  const msg = `确认清空所有评分数据？\n\n将删除：\n· ${s.total_reports || 0} 条周报\n· ${s.scored_reports || 0} 条评分记录\n· 所有周聚合分数\n· 所有趋势图表数据\n\n此操作不可恢复！`
  if (!window.confirm(msg)) return

  try {
    const res = await reportAPI.clearAll()
    const d = res.data
    console.log('[Dashboard] 清空完成:', d)
    window.alert(
      `✅ 清空完成！\n\n` +
      `删除了 ${d.deleted_reports} 条周报、${d.deleted_scores} 条评分记录\n` +
      `删除了 ${d.deleted_aggregates} 条聚合分数、${d.deleted_files} 个文件`
    )
    loadData()
  } catch (e) {
    console.error('[Dashboard] 清空失败:', e)
    const errDetail = e?.response?.data?.detail || e?.message || '未知错误'
    window.alert('❌ 清空失败：' + errDetail)
  }
}

async function loadData() {
  try {
    gradeBarVisible.value = false
    const [overviewRes, statsRes] = await Promise.all([
      leaderboardAPI.dashboard(),
      leaderboardAPI.stats(),
    ])

    const overview = overviewRes.data
    abnormalPersons.value = overview.abnormal_persons || []
    notSubmittedCount.value = overview.not_submitted_count || 0
    lateSubmittedCount.value = overview.late_submitted_count || 0
    currentProjects.value = overview.current_projects || []
    historyWeeks.value = overview.history_weeks || []
    totalPersons.value = overview.total_persons || 0
    submittedCount.value = overview.submitted_count || 0
    allPersons.value = overview.all_persons || []

    const sd = statsRes.data
    stats.value = {
      total_reports: sd.total_reports || 0,
      scored_reports: sd.scored_reports || 0,
      avg_score: sd.avg_score || 0,
    }
    weeklyTrend.value = sd.weekly_trend || []
    gradeDist.value = sd.grade_distribution || {}

    await nextTick()
    renderTrendChart()
    // 触发数字与条目的动画
    runAllCountAnims()
    // 让等级条稍后从 0 展开
    setTimeout(() => {
      gradeBarVisible.value = true
    }, 180)
  } catch (e) {
    console.error('[Dashboard] 加载失败:', e)
  }
}

const { loading } = useDataRefresh({
  loadFn: loadData,
  watchEvents: getDashboardEvents(),
  debounceMs: 400,
})

function renderTrendChart() {
  if (!trendChartRef.value) return
  if (!weeklyTrend.value.length) return

  // 动态导入 echarts（若已渲染则复用）
  import('echarts').then(echarts => {
    if (!trendChartInstance.value) {
      trendChartInstance.value = echarts.init(trendChartRef.value)
    }
    const data = [...weeklyTrend.value].reverse()
    trendChartInstance.value.setOption({
      backgroundColor: 'transparent',
      grid: { top: 20, right: 20, bottom: 30, left: 40 },
      tooltip: { trigger: 'axis' },
      animationDuration: 1000,
      animationEasing: 'cubicOut',
      xAxis: {
        type: 'category',
        data: data.map(d => d.week_start?.slice(5) || ''),
        axisLine: { lineStyle: { color: '#dde3ef' } },
        axisLabel: { color: '#8a92a8', fontSize: 11 },
        axisTick: { show: false },
      },
      yAxis: {
        type: 'value',
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { color: '#8a92a8', fontSize: 11 },
        splitLine: { lineStyle: { color: '#eef1f9', type: 'dashed' } },
      },
      series: [{
        data: data.map(d => d.avg_score),
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 7,
        lineStyle: { color: '#4f6bff', width: 3 },
        itemStyle: { color: '#ffffff', borderColor: '#4f6bff', borderWidth: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(79,107,255,0.25)' },
            { offset: 1, color: 'rgba(79,107,255,0.02)' },
          ]),
        },
      }],
    })
  })
}

onMounted(() => { loadData() })

// 窗口 resize 处理
if (typeof window !== 'undefined') {
  window.addEventListener('resize', () => {
    trendChartInstance.value?.resize()
  })
}
</script>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* 统一的入场动效：从下方轻微上浮并渐显 */
.fade-in-up {
  opacity: 0;
  transform: translateY(14px);
  animation: fadeInUp 560ms cubic-bezier(0.22, 1, 0.36, 1) forwards;
  animation-delay: var(--delay, 0ms);
  will-change: transform, opacity;
}

@keyframes fadeInUp {
  0% {
    opacity: 0;
    transform: translateY(14px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 顶部概览 */
.overview-row {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 14px;
}

.overview-item {
  background: #ffffff;
  border: 1px solid #eef1f9;
  border-radius: 16px;
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}

.overview-item.clickable {
  cursor: pointer;
}

.overview-item.clickable:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -12px rgba(47, 68, 160, 0.18);
  border-color: #4f6bff;
}

.overview-item:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -12px rgba(47, 68, 160, 0.18);
  border-color: #dde5ff;
}

.overview-label {
  font-size: 13px;
  color: #5a6481;
}

.overview-value {
  font-size: 28px;
  font-weight: 800;
  color: #1e2335;
  letter-spacing: -0.5px;
  font-variant-numeric: tabular-nums;
}

.highlight-green { color: #16a875; }
.highlight-red { color: #ef4444; }
.highlight-blue { color: #4f6bff; }

/* 两个主面板（异常人员 + 正在进行项目） */
.panels-grid-two {
  display: grid;
  grid-template-columns: 1fr 2fr;
  gap: 18px;
}

.panel-sub-title {
  margin: 4px 0 0;
  font-size: 12px;
  color: #7a819a;
  font-weight: 400;
}

.panel {
  background: #ffffff;
  border: 1px solid #eef1f9;
  border-radius: 18px;
  overflow: hidden;
  transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease;
}

.panel:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px -14px rgba(47, 68, 160, 0.18);
  border-color: #dde5ff;
}

.panel-accent {
  background: linear-gradient(180deg, #f4f7ff 0%, #ffffff 60%);
  border-color: #dde5ff;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 18px 20px 12px;
  gap: 10px;
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.danger-link-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.08);
  border: none;
  padding: 7px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 600;
  transition: all 0.15s ease;
}

.danger-link-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.18);
  color: #dc2626;
}

.danger-link-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.panel-header h3 {
  margin: 0;
  font-size: 17px;
  color: #1e2335;
  font-weight: 700;
}

.panel-count {
  font-size: 13px;
  color: #5a6481;
  background: #f0f3fb;
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 600;
}

.panel-body {
  padding: 4px 20px 20px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 30px 10px;
  color: #8a92a8;
  font-size: 13px;
}

.empty-icon { font-size: 28px; }
.empty-icon.success { color: #16a875; }
.empty-icon.muted { color: #b4bac9; }

.list-items {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 320px;
  overflow-y: auto;
}

.list-items::-webkit-scrollbar {
  width: 4px;
}

.list-items::-webkit-scrollbar-thumb {
  background: #d0d5e8;
  border-radius: 4px;
}

.list-items::-webkit-scrollbar-track {
  background: transparent;
}

.list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8faff;
  transition: background 0.18s ease, transform 0.18s ease;
}

.list-item:hover {
  background: #eef2ff;
  transform: translateX(2px);
}

.item-index {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: #e4e9f6;
  color: #4f6bff;
  font-weight: 700;
  font-size: 12px;
  flex-shrink: 0;
}

.item-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.item-meta {
  font-size: 12px;
  color: #8a92a8;
}

.item-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
}

.item-badge-warn { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.item-badge-late { background: rgba(251, 146, 60, 0.1); color: #fb923c; }
.item-badge-improve { background: rgba(22, 168, 117, 0.12); color: #16a875; }

.item-score-box {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.item-score {
  font-size: 16px;
  font-weight: 700;
  color: #4f6bff;
  font-variant-numeric: tabular-nums;
}

.grade-chip {
  padding: 3px 10px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 700;
}

.grade-you { background: rgba(22, 168, 117, 0.12); color: #16a875; }
.grade-liang { background: rgba(79, 107, 255, 0.12); color: #4f6bff; }
.grade-yiban { background: rgba(217, 119, 6, 0.12); color: #d97706; }
.grade-cha { background: rgba(239, 68, 68, 0.12); color: #ef4444; }

.grade-chip-1 { background: rgba(22, 168, 117, 0.12); color: #16a875; }
.grade-chip-2 { background: rgba(79, 107, 255, 0.12); color: #4f6bff; }
.grade-chip-3 { background: rgba(217, 119, 6, 0.12); color: #d97706; }
.grade-chip-4 { background: rgba(239, 68, 68, 0.12); color: #ef4444; }

/* 图表区 */
.charts-row {
  display: grid;
  grid-template-columns: 1fr;
  gap: 18px;
}

.chart-panel { padding-bottom: 20px; }

.stats-block {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  padding: 0 20px;
  margin-bottom: 20px;
}

.stat-box {
  background: #f8faff;
  border-radius: 12px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  align-items: flex-start;
  transition: background 0.2s ease, transform 0.2s ease;
}

.stat-box:hover {
  background: #eef2ff;
  transform: translateY(-1px);
}

.stat-label { font-size: 12px; color: #5a6481; }
.stat-value {
  font-size: 22px;
  font-weight: 700;
  color: #1e2335;
  font-variant-numeric: tabular-nums;
}
.stat-value.primary { color: #4f6bff; }

.mini-chart-block {
  padding: 0 20px;
  margin-bottom: 16px;
}

.mini-chart-block h4,
.grade-block h4 {
  font-size: 13px;
  color: #5a6481;
  font-weight: 600;
  margin: 0 0 12px;
}

.mini-chart {
  width: 100%;
  height: 200px;
}

.grade-block {
  padding: 0 20px;
}

.grade-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.grade-bar-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.grade-bar-bg {
  flex: 1;
  height: 8px;
  background: #eef1f9;
  border-radius: 4px;
  overflow: hidden;
}

.grade-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #4f6bff, #7c8fff);
  border-radius: 4px;
  width: 0;
  transition: width 800ms cubic-bezier(0.22, 1, 0.36, 1);
}

.grade-count {
  font-size: 13px;
  color: #5a6481;
  min-width: 30px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

/* 项目卡片样式 */
.project-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 400px;
  overflow-y: auto;
}

.project-list::-webkit-scrollbar {
  width: 4px;
}

.project-list::-webkit-scrollbar-thumb {
  background: #d0d5e8;
  border-radius: 4px;
}

.project-list::-webkit-scrollbar-track {
  background: transparent;
}

.project-item {
  padding: 14px 16px;
  border-radius: 12px;
  background: #f8faff;
  border: 1px solid #eef1f9;
  transition: all 0.2s ease;
}

.project-item:hover {
  background: #eef2ff;
  border-color: #dde5ff;
  transform: translateY(-1px);
}

.project-item.project-highlight {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.05), #f8faff);
  border-color: rgba(251, 191, 36, 0.3);
}

.project-header {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}

.project-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.project-star {
  color: #fbbf24;
  font-size: 14px;
}

.project-name {
  font-size: 15px;
  font-weight: 600;
  color: #1e2335;
  flex: 1;
}

.project-progress-badge {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
}

.project-progress-badge.progress-high {
  background: rgba(22, 168, 117, 0.12);
  color: #16a875;
}

.project-progress-badge.progress-mid {
  background: rgba(79, 107, 255, 0.12);
  color: #4f6bff;
}

.project-progress-badge.progress-low {
  background: rgba(251, 146, 60, 0.12);
  color: #fb923c;
}

.project-departments {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.project-dept-tag {
  font-size: 11px;
  color: #5a6481;
  background: #e4e9f6;
  padding: 2px 8px;
  border-radius: 6px;
}

.project-progress-bar {
  height: 6px;
  background: #eef1f9;
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 10px;
}

.project-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4f6bff, #6ed0ff);
  border-radius: 3px;
  transition: width 0.6s ease;
}

.project-summary {
  font-size: 13px;
  color: #5a6481;
  line-height: 1.6;
  margin: 0 0 10px 0;
}

.project-persons {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.project-person-tag {
  font-size: 11px;
  color: #4f6bff;
  background: rgba(79, 107, 255, 0.08);
  padding: 3px 8px;
  border-radius: 6px;
}

/* 历史项目样式 */
/* 历史周切换导航 */
.history-nav {
  display: flex;
  align-items: center;
  gap: 10px;
}

.nav-btn {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: 1px solid #dde5ff;
  background: #f0f3ff;
  color: #4f6bff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.nav-btn:hover:not(:disabled) {
  background: #4f6bff;
  color: #fff;
  border-color: #4f6bff;
}

.nav-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.nav-btn .pi {
  font-size: 16px;
}

.history-nav-label {
  font-size: 14px;
  color: #5a6481;
  font-weight: 600;
  min-width: 48px;
  text-align: center;
}

.history-week {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-week-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: linear-gradient(135deg, #f4f7ff, #ffffff);
  border: 1px solid #dde5ff;
  border-radius: 10px;
}

.history-week-header i {
  color: #4f6bff;
  font-size: 16px;
}

.history-week-label {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
  flex: 1;
}

.history-week-count {
  font-size: 12px;
  color: #5a6481;
}

.history-projects {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
  padding-left: 8px;
}

.history-project-item {
  padding: 12px 14px;
  border-radius: 10px;
  background: #f8faff;
  border: 1px solid #eef1f9;
  transition: all 0.2s ease;
}

.history-project-item:hover {
  background: #eef2ff;
  border-color: #dde5ff;
}

.history-project-item.project-highlight {
  background: linear-gradient(135deg, rgba(251, 191, 36, 0.05), #f8faff);
  border-color: rgba(251, 191, 36, 0.3);
}

.history-proj-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.history-proj-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
  flex: 1;
}

.history-proj-summary {
  font-size: 12px;
  color: #5a6481;
  line-height: 1.5;
  margin: 0 0 8px 0;
}

/* 人员详情对话框 */
.persons-dialog-content {
  max-height: 400px;
  overflow-y: auto;
  padding-right: 4px;
}

.persons-dialog-content::-webkit-scrollbar {
  width: 6px;
}

.persons-dialog-content::-webkit-scrollbar-thumb {
  background: #d0d5e8;
  border-radius: 3px;
}

.persons-dialog-content::-webkit-scrollbar-track {
  background: transparent;
}

.persons-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.person-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #f8faff;
  border-radius: 10px;
  border: 1px solid #eef1f9;
}

.person-index {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #4f6bff;
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
}

.person-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.person-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.person-meta {
  font-size: 12px;
  color: #5a6481;
}

.person-badge {
  font-size: 12px;
  font-weight: 500;
  padding: 4px 10px;
  border-radius: 999px;
}

.person-badge.badge-warn {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.person-badge.badge-late {
  background: rgba(251, 146, 60, 0.1);
  color: #fb923c;
}

/* 响应式 */
@media (max-width: 1200px) {
  .panels-grid-two { grid-template-columns: 1fr; }
  .overview-row { grid-template-columns: repeat(2, 1fr); }
  .history-projects { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .stats-block { grid-template-columns: 1fr; }
  .overview-value { font-size: 22px; }
  .history-projects { grid-template-columns: 1fr; }
}
</style>
