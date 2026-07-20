<template>
  <div class="leaderboard page-content" :class="{ 'public-page': isPublicMode, 'embedded-mode': embedded }">
    <div v-if="isPublicMode && !embedded" class="public-nav">
      <router-link to="/" class="brand">智友辰周任务汇总</router-link>
      <div class="public-links">
        <router-link to="/write">提交周报</router-link>
        <router-link to="/leaderboard">排行榜</router-link>
        <router-link to="/admin/login">管理员登录</router-link>
      </div>
    </div>
    <div class="page-header">
      <div>
        <span v-if="embedded" class="embedded-kicker">排行榜分析</span>
        <h1>{{ embedded ? '评分结果' : '排行榜' }}</h1>
        <p class="page-subtitle">{{ embedded ? '按周期查看团队评分排名与趋势。' : '评分排名与可视化分析' }}</p>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <SelectButton v-model="period" :options="periodOptions" optionLabel="label" optionValue="value" />
      <Dropdown v-model="sortBy" :options="sortOptions" optionLabel="label" optionValue="value"
        placeholder="排序方式" style="min-width:140px;margin-left:12px" />
      <div class="filter-spacer"></div>
      <span class="total-info">共 {{ totalReports }} 条评分记录</span>
    </div>

    <div class="content-layout">
      <!-- 左：排行表格 -->
      <div class="table-area">
        <Card class="table-card">
          <template #content>
            <DataTable :value="rankings" :loading="loading" class="dark-table"
              responsiveLayout="scroll"
              :pt="{ bodyRow: ({ context }) => rowPt(context.index) }">
              <template #empty>
                <div class="empty-state">
                  <i class="pi pi-inbox empty-icon"></i>
                  <div class="empty-text">暂无排行数据</div>
                </div>
              </template>
              <Column header="排名" style="min-width:70px">
                <template #body="{ data, index }">
                  <div class="rank-cell">
                    <span v-if="index === 0" class="rank-medal rank-medal-1"><i class="pi pi-trophy"></i></span>
                    <span v-else-if="index === 1" class="rank-medal rank-medal-2"><i class="pi pi-star"></i></span>
                    <span v-else-if="index === 2" class="rank-medal rank-medal-3"><i class="pi pi-bolt"></i></span>
                    <span v-else class="rank-number">#{{ index + 1 }}</span>
                  </div>
                </template>
              </Column>
              <Column field="author_name" header="姓名" sortable style="min-width:120px">
                <template #body="{ data }">
                  <div class="user-cell">
                    <Avatar :label="(data.author_name || '?')[0]" size="small" class="user-avatar" shape="circle" />
                    <span>{{ data.author_name }}</span>
                  </div>
                </template>
              </Column>
              <Column field="department" header="部门" style="min-width:80px">
                <template #body="{ data }">
                  <Tag v-if="data.department" :value="data.department" severity="info" />
                  <span v-else class="text-muted">-</span>
                </template>
              </Column>
              <Column field="total_score" header="总分" sortable style="min-width:80px">
                <template #body="{ data }">
                  <ScoreBadge v-if="data.total_score != null" :score="Number(data.total_score)" size="sm" />
                  <span v-else class="text-muted">-</span>
                </template>
              </Column>
              <Column field="avg_score" header="平均分" sortable style="min-width:80px">
                <template #body="{ data }">
                  <span v-if="data.avg_score != null">{{ Math.round(Number(data.avg_score)) }}</span>
                  <span v-else class="text-muted">-</span>
                </template>
              </Column>
              <Column field="chat_score" header="沟通分" sortable style="min-width:80px">
                <template #body="{ data }">
                  <span v-if="data.chat_score != null" class="chat-score">{{ Number(data.chat_score).toFixed(1) }}</span>
                  <span v-else class="text-muted">-</span>
                </template>
              </Column>
              <Column field="report_count" header="周报数" sortable style="min-width:70px">
                <template #body="{ data }">
                  <span>{{ data.report_count }}</span>
                </template>
              </Column>
              <Column header="等级" style="min-width:60px">
                <template #body="{ data }">
                  <span v-if="data.latest_grade" :class="['grade-tag', gradeClass(data.latest_grade)]">
                    {{ getGradeName(data.latest_grade) }}
                  </span>
                </template>
              </Column>
            </DataTable>
          </template>
        </Card>
      </div>

      <!-- 右：图表 -->
      <div class="side-panel">
        <!-- 前三名 -->
        <Card class="side-card">
          <template #title><i class="pi pi-trophy" style="color:#d97706;margin-right:6px"></i>本期前三</template>
          <template #content>
            <div class="top3-list" v-if="rankings.length >= 3">
              <div class="top3-item gold">
                <span class="top3-rank top3-rank-1"><i class="pi pi-trophy"></i></span>
                <span class="top3-name">{{ rankings[0]?.author_name }}</span>
                <span class="top3-score">{{ rankings[0]?.total_score }}</span>
              </div>
              <div class="top3-item silver">
                <span class="top3-rank top3-rank-2"><i class="pi pi-star"></i></span>
                <span class="top3-name">{{ rankings[1]?.author_name }}</span>
                <span class="top3-score">{{ rankings[1]?.total_score }}</span>
              </div>
              <div class="top3-item bronze">
                <span class="top3-rank top3-rank-3"><i class="pi pi-bolt"></i></span>
                <span class="top3-name">{{ rankings[2]?.author_name }}</span>
                <span class="top3-score">{{ rankings[2]?.total_score }}</span>
              </div>
            </div>
            <div v-else class="empty-hint">数据不足</div>
          </template>
        </Card>

        <!-- 评分柱状图 -->
        <Card class="side-card chart-card" :class="{ 'empty-chart-card': !rankings.length }" style="margin-top:16px">
          <template #title>评分分布</template>
          <template #content>
            <div v-if="rankings.length" ref="barChartRef" class="chart-container"></div>
            <div v-else class="chart-empty-hint">暂无评分分布数据</div>
          </template>
        </Card>

        <Card class="side-card chart-card" :class="{ 'empty-chart-card': !rankings.length }" style="margin-top:16px">
          <template #title><i class="pi pi-chart-line" style="color:#4f6bff;margin-right:6px"></i>维度雷达图</template>
          <template #content>
            <div v-if="rankings.length" ref="radarChartRef" class="chart-container"></div>
            <div v-else class="chart-empty-hint">暂无维度分析数据</div>
          </template>
        </Card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { leaderboardAPI } from '../api'
import { useDataRefresh, getLeaderboardEvents } from '../composables/useDataRefresh'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import SelectButton from 'primevue/selectbutton'
import Dropdown from 'primevue/dropdown'
import Avatar from 'primevue/avatar'
import Tag from 'primevue/tag'
import ScoreBadge from '../components/ui/ScoreBadge.vue'
import * as echarts from 'echarts'
import { useEChart } from '../composables/useEChart'

const props = defineProps({
  embedded: { type: Boolean, default: false },
})

const route = useRoute()
const isPublicMode = computed(() => props.embedded || !route.path.startsWith('/admin'))
const rankings = ref([])
const totalReports = ref(0)
const period = ref('week')
const sortBy = ref('total_score')
const barChartRef = ref(null)
const radarChartRef = ref(null)
const barChart = useEChart()
const radarChart = useEChart()

const periodOptions = [
  { label: '本周', value: 'week' },
  { label: '本月', value: 'month' },
  { label: '全部', value: 'all' },
]

const sortOptions = [
  { label: '按总分', value: 'total_score' },
  { label: '按平均分', value: 'avg_score' },
  { label: '按周报数', value: 'report_count' },
]

const gradeNames = { '优': '优', '良': '良', '一般': '一般', '差': '差' }

function gradeClass(g) {
  return { '优': 'grade-you', '良': 'grade-liang', '一般': 'grade-yiban', '差': 'grade-cha' }[g] || ''
}

function getGradeName(g) {
  return gradeNames[g] || g
}

function rowPt(index) {
  const base = { style: 'background:var(--bg-card); color:var(--text-primary); border-color:var(--border-color);' }
  if (index === 0) return { style: `${base.style} background: linear-gradient(90deg, rgba(234,179,8,0.12), var(--bg-card));` }
  if (index === 1) return { style: `${base.style} background: linear-gradient(90deg, rgba(148,163,184,0.08), var(--bg-card));` }
  if (index === 2) return { style: `${base.style} background: linear-gradient(90deg, rgba(180,83,9,0.08), var(--bg-card));` }
  return base
}

async function loadLeaderboard() {
  const res = await leaderboardAPI.get({
    period: period.value,
    sort_by: sortBy.value,
  })
  rankings.value = res.data.rankings || []
  totalReports.value = res.data.total_reports || 0

  await nextTick()
  renderBarChart()
  renderRadarChart()
}

// 使用自动刷新 composable，监听排行榜和报表变更事件
const { loading } = useDataRefresh({
  loadFn: loadLeaderboard,
  watchEvents: getLeaderboardEvents(),
  debounceMs: 300,
})

const unwatchFilters = watch([period, sortBy], () => { loadLeaderboard() })
onUnmounted(() => { unwatchFilters() })

function renderBarChart() {
  if (!barChartRef.value || !rankings.value.length) return
  const top10 = rankings.value.slice(0, 10)
  barChart.render(barChartRef, {
    backgroundColor: 'transparent',
    grid: { top: 10, right: 10, bottom: 30, left: 50 },
    xAxis: {
      type: 'category',
      data: top10.map(r => r.author_name),
      axisLabel: { color: '#7C8698', fontSize: 11, rotate: 30 },
      axisLine: { lineStyle: { color: '#E6EAF2' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { color: '#7C8698', fontSize: 11 },
      splitLine: { lineStyle: { color: '#EEF2F8', type: 'dashed' } },
    },
    series: [{
      data: top10.map(r => ({
        value: r.total_score,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#45D0B5' },
            { offset: 0.55, color: '#4F8CFF' },
            { offset: 1, color: '#746BFF' },
          ]),
          borderRadius: [8, 8, 0, 0],
          shadowColor: 'rgba(79, 140, 255, 0.18)',
          shadowBlur: 8,
        },
      })),
      type: 'bar',
      barWidth: '60%',
    }],
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#FFFFFF',
      borderColor: '#ECEEF2',
      textStyle: { color: '#1A1D26' },
    },
  })
}

function renderRadarChart() {
  if (!radarChartRef.value || !rankings.value.length) return
  const top5 = rankings.value.slice(0, 5)
  const indicators = top5.map(r => ({ name: r.author_name, max: 100 }))
  radarChart.render(radarChartRef, {
    backgroundColor: 'transparent',
    radar: {
      indicator: indicators,
      shape: 'polygon',
      splitArea: { areaStyle: { color: ['transparent'] } },
      splitLine: { lineStyle: { color: '#E2E4E9' } },
      axisLine: { lineStyle: { color: '#E2E4E9' } },
      axisName: { color: '#3D4150', fontSize: 11 },
    },
    series: [{
      type: 'radar',
      data: [{
        value: top5.map(r => r.avg_score),
        name: '平均分',
        areaStyle: { color: 'rgba(91, 95, 199, 0.15)' },
        lineStyle: { color: '#5B5FC7', width: 2 },
        itemStyle: { color: '#5B5FC7' },
      }],
    }],
    tooltip: {
      backgroundColor: '#FFFFFF',
      borderColor: '#ECEEF2',
      textStyle: { color: '#1A1D26' },
    },
  })
}
</script>

<style scoped>
.public-page {
  min-height: 100vh;
  padding: var(--content-padding);
  background: var(--public-bg-gradient);
}

.public-nav {
  max-width: 1120px;
  margin: 0 auto var(--spacing-lg);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-radius: var(--radius-lg);
  background: rgba(255,255,255,0.86);
  box-shadow: var(--shadow-sm);
}

.brand {
  font-size: 18px;
  font-weight: 800;
  color: var(--text-primary);
}

.public-links {
  display: flex;
  gap: 18px;
  font-weight: 700;
}

.public-page .page-header,
.public-page .filter-bar,
.public-page .content-layout {
  max-width: 1120px;
  margin-left: auto;
  margin-right: auto;
}

.embedded-mode.public-page {
  min-height: auto;
  padding: 0;
  background: transparent;
}

.embedded-mode.public-page .page-header,
.embedded-mode.public-page .filter-bar,
.embedded-mode.public-page .content-layout {
  max-width: none;
}

.embedded-mode .page-header {
  margin-bottom: var(--spacing-xs);
}

.embedded-mode .page-header h1 {
  font-size: var(--text-lg);
  color: var(--text-secondary);
}

.embedded-mode .page-subtitle {
  font-size: var(--text-xs);
}

.embedded-kicker {
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
}

.embedded-mode .side-panel {
  position: static;
}

.embedded-mode .filter-bar {
  margin-bottom: var(--spacing-sm);
}

/* ========== 筛选栏 ========== */
.filter-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-lg);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: var(--spacing-sm) var(--spacing-md);
}

.filter-spacer { flex: 1; }

.total-info {
  font-size: var(--text-sm);
  color: var(--text-muted);
}

.filter-bar :deep(.p-selectbutton .p-button) {
  background: var(--bg-dark) !important;
  border-color: var(--border-color) !important;
  color: var(--text-secondary) !important;
  font-size: var(--text-sm) !important;
  padding: 6px 12px !important;
  transition: background var(--transition-fast), color var(--transition-fast), border-color var(--transition-fast) !important;
}

.filter-bar :deep(.p-selectbutton .p-button:hover:not(.p-highlight)) {
  background: var(--bg-card-hover) !important;
}

.filter-bar :deep(.p-selectbutton .p-button.p-highlight) {
  background: var(--primary) !important;
  border-color: var(--primary) !important;
  color: var(--text-inverse) !important;
}

/* ========== 布局 ========== */
.content-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: var(--spacing-md);
  align-items: start;
}

.embedded-mode .content-layout {
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: var(--spacing-md);
}

.table-area {
  min-width: 0;
  overflow: hidden;
}

.side-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  position: sticky;
  top: var(--spacing-lg);
}

/* ========== 表格 ========== */
.table-card :deep(.p-card-body) { padding: 0; }
.table-card :deep(.p-card-content) { padding: 0; width: 100%; overflow-x: auto; }
.table-card :deep(.p-datatable) { min-width: 600px; }
.table-card :deep(.p-datatable-table-container) { min-height: 236px; }
.embedded-mode .table-card :deep(.p-datatable-table-container) { min-height: 212px; }
.table-card :deep(.p-datatable-emptymessage) {
  background: var(--bg-card) !important;
}

.table-card .empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  padding: var(--spacing-xl) var(--spacing-md);
  color: var(--text-muted);
}

.embedded-mode .table-card .empty-state {
  min-height: 164px;
  padding: var(--spacing-lg) var(--spacing-md);
}

.table-card .empty-state .empty-icon {
  font-size: 2.5rem;
  opacity: 0.36;
  margin-bottom: var(--spacing-sm);
}

.table-card .empty-state .empty-text {
  font-size: var(--text-lg);
  color: var(--text-secondary);
}

.rank-cell { display: flex; align-items: center; }
.rank-medal {
  font-size: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.rank-medal-1 { color: #d97706; }
.rank-medal-2 { color: #64748b; }
.rank-medal-3 { color: #b45309; }
.rank-number { color: var(--text-secondary); font-weight: var(--font-semibold); font-size: var(--text-base); }

.user-cell {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.user-avatar {
  background: var(--primary) !important;
  color: var(--text-inverse) !important;
  font-size: 12px !important;
}

.text-muted { color: var(--text-muted); font-size: var(--text-sm); }

/* ========== 侧边卡片 ========== */
.side-card {
  min-height: 150px;
}

.side-card :deep(.p-card-body) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.side-card :deep(.p-card-content) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.embedded-mode .side-card {
  min-height: 136px;
}

.chart-card,
.embedded-mode .chart-card {
  min-height: 212px;
}

.side-card :deep(.p-card-title) {
  color: var(--text-secondary) !important;
  font-size: var(--text-sm) !important;
}

.top3-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.top3-item {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  transition: transform var(--transition-fast);
}

.top3-item:hover { transform: translateX(4px); }

.top3-item.gold {
  background: linear-gradient(135deg, rgba(234,179,8,0.12), rgba(234,179,8,0.04));
  border: 1px solid rgba(234,179,8,0.2);
}

.top3-item.silver {
  background: linear-gradient(135deg, rgba(148,163,184,0.1), rgba(148,163,184,0.03));
  border: 1px solid rgba(148,163,184,0.15);
}

.top3-item.bronze {
  background: linear-gradient(135deg, rgba(180,83,9,0.1), rgba(180,83,9,0.03));
  border: 1px solid rgba(180,83,9,0.12);
}

.top3-rank {
  font-size: 18px;
  margin-right: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.top3-rank-1 { color: #d97706; }
.top3-rank-2 { color: #64748b; }
.top3-rank-3 { color: #b45309; }
.top3-name { flex: 1; color: var(--text-primary); font-weight: var(--font-medium); font-size: var(--text-sm); }
.top3-score { color: var(--primary); font-weight: var(--font-bold); }

.chart-container { 
  width: 100%; 
  height: 180px; 
  min-height: 150px;
}

.embedded-mode .chart-container {
  height: 150px;
  min-height: 132px;
}

.empty-hint,
.chart-empty-hint {
  flex: 1;
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: var(--text-muted);
  padding: var(--spacing-md);
  font-size: var(--text-sm);
}

.chart-empty-hint {
  min-height: 132px;
}

.embedded-mode .chart-empty-hint {
  min-height: 118px;
}

.empty-chart-card :deep(.p-card-body) {
  padding-bottom: var(--spacing-md);
}

/* ========== 响应式断点 ========== */

@media (max-width: 1200px) {
  .content-layout,
  .embedded-mode .content-layout {
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  .side-panel {
    position: static;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--spacing-md);
  }

  .side-card[style] {
    margin-top: 0 !important;
  }

  .side-card:first-child {
    grid-column: 1 / -1;
  }
}

@media (max-width: 640px) {
  .leaderboard.public-page {
    padding: 14px;
  }

  .embedded-mode.public-page {
    padding: 0;
  }

  .public-nav {
    flex-direction: column;
    align-items: stretch;
    gap: var(--spacing-sm);
  }

  .public-links {
    justify-content: space-between;
    gap: var(--spacing-sm);
    font-size: var(--text-xs);
  }

  .filter-bar {
    flex-direction: column;
    align-items: stretch;
    gap: var(--spacing-sm);
  }

  .side-panel {
    grid-template-columns: 1fr;
  }

  .side-card:first-child {
    grid-column: auto;
  }

  .filter-bar :deep(.p-selectbutton) {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    width: 100%;
  }

  .filter-bar :deep(.p-selectbutton .p-button) {
    min-width: 0;
    padding: 7px 8px !important;
  }
  
  .filter-spacer { display: none; }

  .total-info {
    text-align: center;
  }
  
  .side-panel {
    grid-template-columns: 1fr;
  }

  .chart-container {
    height: 180px;
    min-height: 160px;
  }

  .table-card .empty-state {
    min-height: 180px;
    padding: var(--spacing-lg);
  }
}
</style>
