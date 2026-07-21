<template>
  <div class="assessment-list">
    <div class="page-header">
      <h2>内部考核</h2>
      <p class="page-desc">查看员工在指定时间范围内的综合表现和项目贡献</p>
    </div>

    <Card class="filter-card">
      <template #content>
        <div class="filter-row">
          <div class="filter-item">
            <label>开始日期</label>
            <DatePicker v-model="startDate" dateFormat="yy-mm-dd" showIcon />
          </div>
          <div class="filter-item">
            <label>结束日期</label>
            <DatePicker v-model="endDate" dateFormat="yy-mm-dd" showIcon />
          </div>
          <div class="filter-item">
            <label>部门</label>
            <Dropdown
              v-model="selectedDepartment"
              :options="departments"
              optionLabel="name"
              optionValue="id"
              placeholder="全部部门"
              showClear
              class="w-full"
            />
          </div>
          <div class="filter-actions">
            <Button label="查询" icon="pi pi-search" @click="loadAssessments" :loading="loading" />
            <Button label="重置" icon="pi pi-refresh" @click="resetFilters" severity="secondary" outlined />
          </div>
        </div>
      </template>
    </Card>

    <Card class="table-card">
      <template #content>
        <DataTable
          :value="assessments"
          :loading="loading"
          stripedRows
          responsiveLayout="scroll"
          :paginator="true"
          :rows="20"
          :rowsPerPageOptions="[10, 20, 50]"
          paginatorTemplate="FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport RowsPerPageDropdown"
          currentPageReportTemplate="显示 {first} 到 {last} 条，共 {totalRecords} 条"
        >
          <template #empty>暂无数据</template>
          
          <Column field="author_name" header="姓名" :sortable="true">
            <template #body="{ data }">
              <div class="user-info">
                <Avatar :label="data.author_name?.charAt(0)" shape="circle" />
                <span>{{ data.author_name }}</span>
              </div>
            </template>
          </Column>
          
          <Column field="department" header="部门" :sortable="true" />
          
          <Column field="avg_composite_score" header="平均分" :sortable="true">
            <template #body="{ data }">
              <span class="score-badge" :class="getScoreClass(data.avg_composite_score)">
                {{ data.avg_composite_score?.toFixed(1) || '0.0' }}
              </span>
            </template>
          </Column>
          
          <Column field="submitted_weeks" header="提交周数" :sortable="true">
            <template #body="{ data }">
              <span>{{ data.submitted_weeks }} / {{ data.total_weeks }}</span>
            </template>
          </Column>
          
          <Column field="submission_rate" header="提交率" :sortable="true">
            <template #body="{ data }">
              <div class="progress-cell">
                <ProgressBar :value="data.submission_rate" :showValue="false" class="w-8rem" />
                <span class="rate-text">{{ data.submission_rate?.toFixed(1) || '0.0' }}%</span>
              </div>
            </template>
          </Column>
          
          <Column header="操作" :exportable="false" style="min-width: 8rem">
            <template #body="{ data }">
              <Button
                label="查看详情"
                icon="pi pi-eye"
                size="small"
                outlined
                @click="viewDetail(data)"
              />
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import DatePicker from 'primevue/datepicker'
import Dropdown from 'primevue/dropdown'
import Button from 'primevue/button'
import Avatar from 'primevue/avatar'
import ProgressBar from 'primevue/progressbar'
import { assessmentAPI } from '../api'
import { departmentAPI } from '../api'
import { showToast } from '../utils/toast'

const router = useRouter()

const startDate = ref(null)
const endDate = ref(null)
const selectedDepartment = ref(null)
const departments = ref([])
const assessments = ref([])
const loading = ref(false)

// 初始化默认时间范围（最近3个月）
onMounted(() => {
  const now = new Date()
  endDate.value = now
  
  const threeMonthsAgo = new Date()
  threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3)
  startDate.value = threeMonthsAgo
  
  loadDepartments()
  loadAssessments()
})

const loadDepartments = async () => {
  try {
    const res = await departmentAPI.list()
    departments.value = res.data.items || []
  } catch (error) {
    console.error('加载部门列表失败:', error)
  }
}

const loadAssessments = async () => {
  if (!startDate.value || !endDate.value) {
    showToast('请选择开始和结束日期', 'warn')
    return
  }
  
  loading.value = true
  try {
    const params = {
      start_date: formatDate(startDate.value),
      end_date: formatDate(endDate.value),
    }
    
    if (selectedDepartment.value) {
      params.department = selectedDepartment.value
    }
    
    const res = await assessmentAPI.list(params)
    assessments.value = res.data.items || []
  } catch (error) {
    console.error('加载考核列表失败:', error)
    showToast('加载考核列表失败', 'error')
  } finally {
    loading.value = false
  }
}

const resetFilters = () => {
  const now = new Date()
  endDate.value = now
  
  const threeMonthsAgo = new Date()
  threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3)
  startDate.value = threeMonthsAgo
  
  selectedDepartment.value = null
  loadAssessments()
}

const viewDetail = (data) => {
  router.push({
    name: 'AssessmentDetail',
    params: { personId: data.person_id },
    query: {
      start_date: formatDate(startDate.value),
      end_date: formatDate(endDate.value),
      author_name: data.author_name,
      department: data.department
    }
  })
}

const formatDate = (date) => {
  if (!date) return ''
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

const getScoreClass = (score) => {
  if (score >= 90) return 'score-excellent'
  if (score >= 80) return 'score-good'
  if (score >= 70) return 'score-average'
  return 'score-poor'
}
</script>

<style scoped>
.assessment-list {
  padding: 1.5rem;
}

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  margin: 0 0 0.5rem 0;
  font-size: 1.75rem;
  font-weight: 600;
  color: var(--text-primary);
}

.page-desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.95rem;
}

.filter-card {
  margin-bottom: 1.5rem;
}

.filter-row {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  min-width: 200px;
}

.filter-item label {
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
}

.filter-actions {
  display: flex;
  gap: 0.5rem;
}

.table-card {
  margin-bottom: 1.5rem;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.score-badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-weight: 600;
  font-size: 0.875rem;
}

.score-excellent {
  background: var(--green-100);
  color: var(--green-800);
}

.score-good {
  background: var(--blue-100);
  color: var(--blue-800);
}

.score-average {
  background: var(--orange-100);
  color: var(--orange-800);
}

.score-poor {
  background: var(--red-100);
  color: var(--red-800);
}

.progress-cell {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.rate-text {
  font-size: 0.875rem;
  color: var(--text-secondary);
  min-width: 3.5rem;
}
</style>
