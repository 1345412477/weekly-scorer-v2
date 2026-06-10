<template>
  <div class="dashboard page-content">
    <!-- 顶部概览 -->
    <div class="overview-row">
      <div class="overview-item">
        <span class="overview-label">本周应提交</span>
        <span class="overview-value">{{ totalPersons }}</span>
      </div>
      <div class="overview-item">
        <span class="overview-label">已提交</span>
        <span class="overview-value highlight-green">{{ submittedCount }}</span>
      </div>
      <div class="overview-item">
        <span class="overview-label">未提交</span>
        <span class="overview-value highlight-red">{{ notSubmitted.length }}</span>
      </div>
      <div class="overview-item">
        <span class="overview-label">进步人员</span>
        <span class="overview-value highlight-blue">{{ topImprovers.length }}</span>
      </div>
    </div>

    <!-- 三大区域 -->
    <div class="panels-grid">
      <!-- 未提交 -->
      <section class="panel">
        <header class="panel-header">
          <div>
            <span class="panel-eyebrow panel-eyebrow-red">待处理</span>
            <h3>本周未提交人员</h3>
          </div>
          <span class="panel-count">{{ notSubmitted.length }} 人</span>
        </header>
        <div class="panel-body">
          <div v-if="notSubmitted.length === 0" class="empty-state">
            <i class="pi pi-check-circle empty-icon success"></i>
            <span>全员已提交，非常棒 🎉</span>
          </div>
          <div v-else class="list-items">
            <div v-for="(item, idx) in notSubmitted" :key="item.name" class="list-item">
              <span class="item-index">{{ idx + 1 }}</span>
              <div class="item-main">
                <span class="item-name">{{ item.name }}</span>
                <span class="item-meta">{{ item.department || '未分配' }}{{ item.position ? ' · ' + item.position : '' }}</span>
              </div>
              <span class="item-badge item-badge-warn">未提交</span>
            </div>
          </div>
        </div>
      </section>

      <!-- 评级较低 -->
      <section class="panel">
        <header class="panel-header">
          <div>
            <span class="panel-eyebrow panel-eyebrow-amber">需关注</span>
            <h3>评级较低人员</h3>
          </div>
          <span class="panel-count">{{ lowScorers.length }} 人</span>
        </header>
        <div class="panel-body">
          <div v-if="lowScorers.length === 0" class="empty-state">
            <i class="pi pi-thumbs-up empty-icon success"></i>
            <span>暂无低分人员</span>
          </div>
          <div v-else class="list-items">
            <div v-for="(item, idx) in lowScorers" :key="item.name" class="list-item">
              <span class="item-index">{{ idx + 1 }}</span>
              <div class="item-main">
                <span class="item-name">{{ item.name }}</span>
                <span class="item-meta">{{ item.department || '—' }}</span>
              </div>
              <div class="item-score-box">
                <span class="item-score">{{ item.total_score }}</span>
                <span v-if="item.grade" :class="['grade-chip', gradeClass(item.grade)]">{{ item.grade }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 进步较大 -->
      <section class="panel panel-accent">
        <header class="panel-header">
          <div>
            <span class="panel-eyebrow panel-eyebrow-green">亮点</span>
            <h3>进步较大人员</h3>
          </div>
          <span class="panel-count">{{ topImprovers.length }} 人</span>
        </header>
        <div class="panel-body">
          <div v-if="topImprovers.length === 0" class="empty-state">
            <i class="pi pi-chart-line empty-icon muted"></i>
            <span>本周暂无对比数据</span>
          </div>
          <div v-else class="list-items">
            <div v-for="(item, idx) in topImprovers" :key="item.name" class="list-item">
              <span class="item-index">{{ idx + 1 }}</span>
              <div class="item-main">
                <span class="item-name">{{ item.name }}</span>
                <span class="item-meta">
                  {{ item.previous_avg }} → {{ item.current_avg }}
                </span>
              </div>
              <span class="item-badge item-badge-improve">
                <i class="pi pi-arrow-up"></i>
                {{ item.improvement }}
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 统计卡片 / 趋势 -->
    <div class="charts-row">
      <section class="panel chart-panel">
        <header class="panel-header">
          <div>
            <span class="panel-eyebrow">数据</span>
            <h3>整体评分概况</h3>
          </div>
        </header>
        <div class="stats-block">
          <div class="stat-box">
            <span class="stat-label">总报告数</span>
            <span class="stat-value">{{ stats.total_reports }}</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">已评分</span>
            <span class="stat-value">{{ stats.scored_reports }}</span>
          </div>
          <div class="stat-box">
            <span class="stat-label">平均分</span>
            <span class="stat-value primary">{{ stats.avg_score }}</span>
          </div>
        </div>
        <div v-if="weeklyTrend.length" class="mini-chart-block">
          <h4>近 12 周平均分趋势</h4>
          <div ref="trendChartRef" class="mini-chart"></div>
        </div>
        <div v-if="gradeDist && Object.keys(gradeDist).length" class="grade-block">
          <h4>等级分布</h4>
          <div class="grade-bars">
            <div v-for="(val, key) in gradeDist" :key="key" class="grade-bar-row">
              <span :class="['grade-chip grade-chip-' + gradeIdx(key)]">{{ key }}</span>
              <div class="grade-bar-bg">
                <div class="grade-bar-fill" :style="{ width: gradeBarWidth(val) + '%' }"></div>
              </div>
              <span class="grade-count">{{ val }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { leaderboardAPI } from '../api'
import { useDataRefresh, getDashboardEvents } from '../composables/useDataRefresh'

const notSubmitted = ref([])
const lowScorers = ref([])
const topImprovers = ref([])
const totalPersons = ref(0)
const submittedCount = ref(0)
const stats = ref({ total_reports: 0, scored_reports: 0, avg_score: 0 })
const weeklyTrend = ref([])
const gradeDist = ref({})
const trendChartRef = ref(null)
const trendChartInstance = ref(null)

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

async function loadData() {
  try {
    const [overviewRes, statsRes] = await Promise.all([
      leaderboardAPI.dashboard(),
      leaderboardAPI.stats(),
    ])

    const overview = overviewRes.data
    notSubmitted.value = overview.not_submitted || []
    lowScorers.value = overview.low_scorers || []
    topImprovers.value = overview.top_improvers || []
    totalPersons.value = overview.total_persons || 0
    submittedCount.value = overview.submitted_count || 0

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

/* 顶部概览 */
.overview-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
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
}

.highlight-green { color: #16a875; }
.highlight-red { color: #ef4444; }
.highlight-blue { color: #4f6bff; }

/* 三个主面板 */
.panels-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
}

.panel {
  background: #ffffff;
  border: 1px solid #eef1f9;
  border-radius: 18px;
  overflow: hidden;
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

.panel-eyebrow {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: #f0f3fb;
  color: #4f6bff;
  font-size: 12px;
  font-weight: 600;
  margin-bottom: 8px;
}

.panel-eyebrow-red { background: rgba(239, 68, 68, 0.1); color: #ef4444; }
.panel-eyebrow-amber { background: rgba(217, 119, 6, 0.12); color: #d97706; }
.panel-eyebrow-green { background: rgba(22, 168, 117, 0.12); color: #16a875; }

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
}

.list-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #f8faff;
  transition: background 0.15s ease;
}

.list-item:hover { background: #eef2ff; }

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
}

.stat-label { font-size: 12px; color: #5a6481; }
.stat-value { font-size: 22px; font-weight: 700; color: #1e2335; }
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
  transition: width 0.4s ease;
}

.grade-count {
  font-size: 13px;
  color: #5a6481;
  min-width: 30px;
  text-align: right;
}

/* 响应式 */
@media (max-width: 1200px) {
  .panels-grid { grid-template-columns: 1fr; }
  .overview-row { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 640px) {
  .stats-block { grid-template-columns: 1fr; }
  .overview-value { font-size: 22px; }
}
</style>
