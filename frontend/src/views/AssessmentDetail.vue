<template>
  <div class="assessment-detail">
    <div class="page-header">
      <Button icon="pi pi-arrow-left" label="返回列表" @click="goBack" text />
      <h2>{{ authorName }} - 考核详情</h2>
      <p class="page-desc">{{ department }} | {{ formatDate(startDate) }} 至 {{ formatDate(endDate) }}</p>
    </div>

    <div v-if="loading" class="loading-container">
      <ProgressSpinner />
    </div>

    <div v-else-if="!detail" class="empty-container">
      <Message severity="warn">暂无考核数据</Message>
    </div>

    <template v-else>
      <!-- 汇总卡片 -->
      <div class="summary-cards">
        <Card class="summary-card">
          <template #content>
            <div class="card-content">
              <div class="card-icon composite">
                <i class="pi pi-chart-line"></i>
              </div>
              <div class="card-info">
                <span class="card-label">综合平均分</span>
                <span class="card-value">{{ detail.summary.avg_composite_score }}</span>
              </div>
            </div>
          </template>
        </Card>

        <Card class="summary-card">
          <template #content>
            <div class="card-content">
              <div class="card-icon report">
                <i class="pi pi-file"></i>
              </div>
              <div class="card-info">
                <span class="card-label">周报平均分</span>
                <span class="card-value">{{ detail.summary.avg_report_score }}</span>
              </div>
            </div>
          </template>
        </Card>

        <Card class="summary-card">
          <template #content>
            <div class="card-content">
              <div class="card-icon attendance">
                <i class="pi pi-clock"></i>
              </div>
              <div class="card-info">
                <span class="card-label">考勤平均分</span>
                <span class="card-value">{{ detail.summary.avg_attendance_score }}</span>
              </div>
            </div>
          </template>
        </Card>

        <Card class="summary-card">
          <template #content>
            <div class="card-content">
              <div class="card-icon chat">
                <i class="pi pi-comments"></i>
              </div>
              <div class="card-info">
                <span class="card-label">沟通平均分</span>
                <span class="card-value">{{ detail.summary.avg_chat_score }}</span>
              </div>
            </div>
          </template>
        </Card>

        <Card class="summary-card">
          <template #content>
            <div class="card-content">
              <div class="card-icon submission">
                <i class="pi pi-check-circle"></i>
              </div>
              <div class="card-info">
                <span class="card-label">提交率</span>
                <span class="card-value">{{ submissionRate }}%</span>
                <span class="card-sub">{{ detail.summary.submitted_weeks }} / {{ detail.summary.total_weeks }} 周</span>
              </div>
            </div>
          </template>
        </Card>
      </div>

      <!-- 分数趋势图 -->
      <Card class="chart-card">
        <template #title>
          <div class="card-header">
            <span>分数趋势</span>
          </div>
        </template>
        <template #content>
          <div class="chart-container">
            <LineChart :data="chartData" :options="chartOptions" class="h-30rem" />
          </div>
        </template>
      </Card>

      <!-- 项目贡献表格 -->
      <Card class="projects-card">
        <template #title>
          <div class="card-header">
            <span>项目贡献分析</span>
            <Tag :value="`共 ${detail.projects.length} 个项目`" severity="info" />
          </div>
        </template>
        <template #content>
          <DataTable 
            :value="detail.projects" 
            stripedRows 
            responsiveLayout="scroll"
            :paginator="detail.projects.length > 10"
            :rows="10"
            v-if="detail.projects.length > 0"
          >
            <template #empty>暂无项目数据</template>
            
            <Column field="project_name" header="项目名称">
              <template #body="{ data }">
                <div class="project-name">
                  <i class="pi pi-folder"></i>
                  <span>{{ data.project_name }}</span>
                </div>
              </template>
            </Column>
            
            <Column field="participation_weeks" header="参与周数">
              <template #body="{ data }">
                <span class="weeks-badge">{{ data.participation_weeks }} 周</span>
              </template>
            </Column>
            
            <Column field="participation_rate" header="参与率">
              <template #body="{ data }">
                <div class="rate-cell">
                  <ProgressBar :value="data.participation_rate" :showValue="false" class="w-8rem" />
                  <span class="rate-text">{{ data.participation_rate }}%</span>
                </div>
              </template>
            </Column>
            
            <Column field="work_items_count" header="工作条目">
              <template #body="{ data }">
                <span class="items-count">{{ data.work_items_count }} 条</span>
              </template>
            </Column>
          </DataTable>
          
          <Message v-else severity="info">该员工在此时间段内暂无项目贡献记录</Message>
        </template>
      </Card>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import Message from 'primevue/message'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ProgressBar from 'primevue/progressbar'
import Tag from 'primevue/tag'
import Chart from 'primevue/chart'
import { assessmentAPI } from '../api'
import { useToast } from 'primevue/usetoast'

const LineChart = Chart

const route = useRoute()
const router = useRouter()
const toast = useToast()

const loading = ref(false)
const detail = ref(null)

const personId = computed(() => route.params.personId)
const startDate = computed(() => route.query.start_date)
const endDate = computed(() => route.query.end_date)
const authorName = computed(() => route.query.author_name || '员工')
const department = computed(() => route.query.department || '')

const submissionRate = computed(() => {
  if (!detail.value) return 0
  const { submitted_weeks, total_weeks } = detail.value.summary
  return total_weeks > 0 ? Math.round((submitted_weeks / total_weeks) * 100) : 0
})

const chartData = computed(() => {
  if (!detail.value || !detail.value.weekly_scores) return null
  
  const labels = detail.value.weekly_scores.map(item => {
    const date = new Date(item.week_start)
    return `${date.getMonth() + 1}/${date.getDate()}`
  })
  
  return {
    labels,
    datasets: [
      {
        label: '综合分',
        data: detail.value.weekly_scores.map(item => item.composite_score),
        borderColor: '#4f7cff',
        backgroundColor: 'rgba(79, 124, 255, 0.1)',
        tension: 0.4,
        fill: true
      },
      {
        label: '周报分',
        data: detail.value.weekly_scores.map(item => item.report_score),
        borderColor: '#10b981',
        backgroundColor: 'transparent',
        tension: 0.4,
        borderDash: [5, 5]
      },
      {
        label: '考勤分',
        data: detail.value.weekly_scores.map(item => item.attendance_score),
        borderColor: '#f59e0b',
        backgroundColor: 'transparent',
        tension: 0.4,
        borderDash: [5, 5]
      },
      {
        label: '沟通分',
        data: detail.value.weekly_scores.map(item => item.chat_score),
        borderColor: '#8b5cf6',
        backgroundColor: 'transparent',
        tension: 0.4,
        borderDash: [5, 5]
      }
    ]
  }
})

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'top',
      labels: {
        usePointStyle: true,
        padding: 20
      }
    },
    tooltip: {
      mode: 'index',
      intersect: false
    }
  },
  scales: {
    y: {
      beginAtZero: true,
      max: 100,
      grid: {
        color: 'rgba(0, 0, 0, 0.05)'
      }
    },
    x: {
      grid: {
        display: false
      }
    }
  }
}

onMounted(() => {
  loadDetail()
})

const loadDetail = async () => {
  if (!personId.value || !startDate.value || !endDate.value) {
    toast.add({ severity: 'error', summary: '缺少必要参数', life: 3000 })
    return
  }
  
  loading.value = true
  try {
    const res = await assessmentAPI.getDetail(personId.value, {
      start_date: startDate.value,
      end_date: endDate.value
    })
    detail.value = res.data
  } catch (error) {
    console.error('加载考核详情失败:', error)
    toast.add({ severity: 'error', summary: '加载考核详情失败', life: 3000 })
  } finally {
    loading.value = false
  }
}

const goBack = () => {
  router.push({
    name: 'AssessmentList',
    query: {
      start_date: startDate.value,
      end_date: endDate.value
    }
  })
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}
</script>

<style scoped>
.assessment-detail {
  padding: 1.5rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.page-desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.loading-container,
.empty-container {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.summary-card {
  border-radius: 12px;
}

.card-content {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  color: white;
}

.card-icon.composite {
  background: linear-gradient(135deg, #4f7cff, #6366f1);
}

.card-icon.report {
  background: linear-gradient(135deg, #10b981, #059669);
}

.card-icon.attendance {
  background: linear-gradient(135deg, #f59e0b, #d97706);
}

.card-icon.chat {
  background: linear-gradient(135deg, #8b5cf6, #7c3aed);
}

.card-icon.submission {
  background: linear-gradient(135deg, #06b6d4, #0891b2);
}

.card-info {
  display: flex;
  flex-direction: column;
}

.card-label {
  font-size: 0.875rem;
  color: var(--text-secondary);
  margin-bottom: 0.25rem;
}

.card-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
}

.card-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

.chart-card,
.projects-card {
  margin-bottom: 1.5rem;
  border-radius: 12px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.chart-container {
  height: 300px;
  position: relative;
}

.project-name {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.project-name i {
  color: var(--primary-color);
}

.weeks-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  background: var(--blue-100);
  color: var(--blue-800);
  border-radius: 1rem;
  font-size: 0.875rem;
  font-weight: 500;
}

.rate-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.rate-text {
  font-size: 0.875rem;
  color: var(--text-secondary);
  min-width: 3rem;
}

.items-count {
  color: var(--text-secondary);
}

@media (max-width: 768px) {
  .summary-cards {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .chart-container {
    height: 250px;
  }
}
</style>
