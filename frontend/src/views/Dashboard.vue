<template>
  <div class="dashboard page-content">
    <div class="page-header">
      <div>
        <h1>仪表盘</h1>
        <p class="page-subtitle">周报评分系统总览</p>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-grid">
      <div class="stat-card" v-for="stat in stats" :key="stat.label">
        <div class="stat-icon" :style="{ background: stat.bg }">
          <i :class="stat.icon" :style="{ color: stat.color }"></i>
        </div>
        <div class="stat-info">
          <span class="stat-value">{{ stat.value }}</span>
          <span class="stat-label">{{ stat.label }}</span>
        </div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="charts-grid">
      <Card class="chart-card">
        <template #title>📈 近12周评分趋势</template>
        <template #content>
          <div ref="trendChartRef" class="chart-container"></div>
        </template>
      </Card>

      <Card class="chart-card">
        <template #title>📊 等级分布</template>
        <template #content>
          <div ref="gradeChartRef" class="chart-container"></div>
        </template>
      </Card>
    </div>

    <!-- 最近周报 -->
    <Card class="recent-card">
      <template #title>📋 最近提交的周报</template>
      <template #content>
        <DataTable :value="recentReports" :loading="loading" class="dark-table" :rows="5">
          <Column field="author_name" header="提交人" style="min-width:100px" />
          <Column field="week_num" header="周次" style="min-width:60px">
            <template #body="{ data }">
              <Tag :value="`第${data.week_num || '-'}周`" severity="info" />
            </template>
          </Column>
          <Column field="total_score" header="评分" style="min-width:80px">
            <template #body="{ data }">
              <span v-if="data.total_score" class="score-badge">{{ data.total_score }}</span>
              <span v-else class="text-muted">待评分</span>
            </template>
          </Column>
          <Column field="grade" header="等级" style="min-width:60px">
            <template #body="{ data }">
              <span v-if="data.grade" :class="['grade-tag', gradeClass(data.grade)]">{{ data.grade }}</span>
            </template>
          </Column>
          <Column field="status" header="状态" style="min-width:80px">
            <template #body="{ data }">
              <Tag :value="statusLabel(data.status)" :severity="statusSeverity(data.status)" />
            </template>
          </Column>
          <Column header="操作" style="min-width:80px">
            <template #body="{ data }">
              <router-link :to="`/reports/${data.id}`">
                <Button icon="pi pi-eye" text size="small" rounded />
              </router-link>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { leaderboardAPI, reportAPI } from '../api'
import { useDataRefresh, getDashboardEvents } from '../composables/useDataRefresh'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import * as echarts from 'echarts'

const recentReports = ref([])
const trendChartRef = ref(null)
const gradeChartRef = ref(null)

const stats = ref([
  { label: '总报告数', value: '-', icon: 'pi pi-file', bg: 'rgba(79,70,229,0.12)', color: '#818CF8' },
  { label: '已评分', value: '-', icon: 'pi pi-check-circle', bg: 'rgba(34,197,94,0.12)', color: '#22C55E' },
  { label: '平均分', value: '-', icon: 'pi pi-chart-line', bg: 'rgba(245,158,11,0.12)', color: '#F59E0B' },
  { label: '本周提交', value: '-', icon: 'pi pi-calendar', bg: 'rgba(236,72,153,0.12)', color: '#EC4899' },
])

function gradeClass(g) {
  return { S: 'grade-s', A: 'grade-a', B: 'grade-b', C: 'grade-c', D: 'grade-d' }[g] || ''
}

function statusLabel(s) {
  return { draft: '草稿', submitted: '已提交', scored: '已评分' }[s] || s
}

function statusSeverity(s) {
  return { draft: 'secondary', submitted: 'warning', scored: 'success' }[s] || 'info'
}

async function loadData() {
  const [statsRes, reportsRes] = await Promise.all([
    leaderboardAPI.stats(),
    reportAPI.list({ size: 5 }),
  ])
  const d = statsRes.data
  stats.value[0].value = d.total_reports
  stats.value[1].value = d.scored_reports
  stats.value[2].value = d.avg_score
  stats.value[3].value = d.total_reports // 简化
  recentReports.value = reportsRes.data.items || []

  await nextTick()
  renderTrendChart(d.weekly_trend || [])
  renderGradeChart(d.grade_distribution || {})
}

// 使用自动刷新 composable，监听报表和配置变更事件
const { loading } = useDataRefresh({
  loadFn: loadData,
  watchEvents: getDashboardEvents(),
  debounceMs: 300,
})

function renderTrendChart(data) {
  if (!trendChartRef.value || !data.length) return
  const chart = echarts.init(trendChartRef.value)
  chart.setOption({
    backgroundColor: 'transparent',
    grid: { top: 20, right: 20, bottom: 30, left: 50 },
    xAxis: {
      type: 'category',
      data: data.map(d => d.week_start?.slice(5) || ''),
      axisLabel: { color: '#6B7280', fontSize: 11 },
      axisLine: { lineStyle: { color: '#E2E4E9' } },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { color: '#6B7280', fontSize: 11 },
      splitLine: { lineStyle: { color: '#E2E4E9' } },
    },
    series: [{
      data: data.map(d => d.avg_score),
      type: 'line',
      smooth: true,
      lineStyle: { color: '#5B5FC7', width: 3 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(91,95,199,0.2)' },
          { offset: 1, color: 'rgba(91,95,199,0.02)' },
        ]),
      },
      itemStyle: { color: '#5B5FC7' },
    }],
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#FFFFFF',
      borderColor: '#ECEEF2',
      textStyle: { color: '#1A1D26' },
    },
  })
  window.addEventListener('resize', () => chart.resize())
}

function renderGradeChart(data) {
  if (!gradeChartRef.value || !Object.keys(data).length) return
  const chart = echarts.init(gradeChartRef.value)
  const colors = { '优': '#22C55E', '良': '#3B82F6', '一般': '#F59E0B', '差': '#EF4444' }
  chart.setOption({
    backgroundColor: 'transparent',
    series: [{
      type: 'pie',
      radius: ['45%', '72%'],
      center: ['50%', '50%'],
      data: Object.entries(data).map(([k, v]) => ({
        name: k,
        value: v,
        itemStyle: { color: colors[k] || '#6B7280' },
      })),
      label: { color: '#6B7280', fontSize: 12 },
      emphasis: { label: { fontSize: 14, fontWeight: 'bold' } },
    }],
    tooltip: {
      backgroundColor: '#FFFFFF',
      borderColor: '#ECEEF2',
      textStyle: { color: '#1A1D26' },
    },
  })
  window.addEventListener('resize', () => chart.resize())
}

</script>

<style scoped>
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  transition: transform var(--transition-fast), box-shadow var(--transition-fast);
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}

.stat-value {
  display: block;
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
}

.stat-label {
  display: block;
  font-size: var(--text-xs);
  color: var(--text-muted);
  margin-top: 2px;
}

.charts-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.chart-card :deep(.p-card-title) {
  color: var(--text-secondary) !important;
  font-size: var(--text-sm) !important;
}

.chart-container {
  width: 100%;
  height: 260px;
}

.recent-card :deep(.p-card-title) {
  color: var(--text-secondary) !important;
  font-size: var(--text-sm) !important;
}

.text-muted {
  color: var(--text-muted);
  font-size: var(--text-sm);
}
</style>
