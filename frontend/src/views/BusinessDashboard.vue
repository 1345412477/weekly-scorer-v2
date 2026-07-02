<template>
  <div class="business-dashboard">
    <div class="page-header">
      <h1>业务盘</h1>
      <div class="header-actions">
        <DatePicker
          v-model="selectedWeek"
          view="week"
          showIcon
          iconDisplay="input"
          placeholder="选择周次"
          dateFormat="yy-mm-dd"
          @dateChange="onWeekChange"
        />
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

    <div v-else-if="departments.length === 0" class="empty-state">
      <i class="pi pi-inbox"></i>
      <p>暂无部门数据</p>
      <p class="sub-text">请先在部门管理中添加部门</p>
    </div>

    <div v-else class="department-grid">
      <div
        v-for="dept in departments"
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
              上周工作回顾
            </div>
            <div class="summary-list">
              <div
                v-for="(item, idx) in dept.last_week_summary"
                :key="idx"
                class="summary-item"
                :class="{ highlighted: item.highlight }"
                @click.stop="toggleItemHighlight(dept, 'last_week', idx, item)"
              >
                <i
                  v-if="item.highlight"
                  class="pi pi-star-fill star-icon"
                ></i>
                <span class="item-content">{{ item.content }}</span>
              </div>
              <div v-if="!dept.last_week_summary?.length" class="empty-text">
                暂无数据
              </div>
            </div>
          </div>

          <div class="summary-section">
            <div class="section-title">
              <i class="pi pi-calendar-plus"></i>
              本周工作重点
            </div>
            <div class="summary-list">
              <div
                v-for="(item, idx) in dept.this_week_summary"
                :key="idx"
                class="summary-item"
                :class="{ highlighted: item.highlight }"
                @click.stop="toggleItemHighlight(dept, 'this_week', idx, item)"
              >
                <i
                  v-if="item.highlight"
                  class="pi pi-star-fill star-icon"
                ></i>
                <span class="item-content">{{ item.content }}</span>
              </div>
              <div v-if="!dept.this_week_summary?.length" class="empty-text">
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

    <!-- 部门详情抽屉 -->
    <Drawer
      v-model:visible="drawerVisible"
      position="right"
      :style="{ width: '50%' }"
      header="部门详情"
    >
      <div v-if="selectedDepartment" class="drawer-content">
        <h2>{{ selectedDepartment.department_name }}</h2>

        <div class="detail-section">
          <h3>
            <i class="pi pi-calendar"></i>
            上周工作回顾
          </h3>
          <div class="detail-list">
            <div
              v-for="(item, idx) in selectedDepartment.last_week_summary"
              :key="idx"
              class="detail-item"
            >
              <div class="item-header">
                <span class="item-content">{{ item.content }}</span>
              </div>
              <div class="item-persons" v-if="item.persons?.length">
                <Tag
                  v-for="person in item.persons"
                  :key="person"
                  :value="person"
                  severity="info"
                  class="person-tag"
                />
              </div>
            </div>
            <div v-if="!selectedDepartment.last_week_summary?.length" class="empty-text">
              暂无数据
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h3>
            <i class="pi pi-calendar-plus"></i>
            本周工作重点
          </h3>
          <div class="detail-list">
            <div
              v-for="(item, idx) in selectedDepartment.this_week_summary"
              :key="idx"
              class="detail-item"
            >
              <div class="item-header">
                <span class="item-content">{{ item.content }}</span>
              </div>
              <div class="item-persons" v-if="item.persons?.length">
                <Tag
                  v-for="person in item.persons"
                  :key="person"
                  :value="person"
                  severity="info"
                  class="person-tag"
                />
              </div>
            </div>
            <div v-if="!selectedDepartment.this_week_summary?.length" class="empty-text">
              暂无数据
            </div>
          </div>
        </div>

        <div class="detail-section" v-if="persons.length > 0">
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

        <div class="drawer-actions">
          <Button
            label="重新生成"
            icon="pi pi-refresh"
            :loading="generatingDept"
            @click="generateDept"
            severity="primary"
          />
        </div>
      </div>
    </Drawer>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { businessAPI } from '../api'
import { useToast } from 'primevue/usetoast'
import DatePicker from 'primevue/datepicker'
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
const drawerVisible = ref(false)
const selectedDepartment = ref(null)
const persons = ref([])

const loadDepartments = async () => {
  loading.value = true
  try {
    const weekStart = formatDate(selectedWeek.value)
    const res = await businessAPI.list({ week_start: weekStart })
    departments.value = res.data.items || []
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

const onWeekChange = () => {
  loadDepartments()
}

const generateAll = async () => {
  generating.value = true
  try {
    const weekStart = formatDate(selectedWeek.value)
    await businessAPI.generateAll({ week_start: weekStart })
    toast.add({
      severity: 'success',
      summary: '生成成功',
      detail: '所有部门总结已生成',
      life: 3000,
    })
    await loadDepartments()
  } catch (error) {
    console.error('生成失败:', error)
    toast.add({
      severity: 'error',
      summary: '生成失败',
      detail: error.message || '无法生成部门总结',
      life: 3000,
    })
  } finally {
    generating.value = false
  }
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
      severity: 'success',
      summary: '生成成功',
      detail: '部门总结已重新生成',
      life: 3000,
    })
    await loadDepartments()
    // 更新抽屉中的数据
    await loadDepartmentDetail(selectedDepartment.value.department_id)
  } catch (error) {
    console.error('生成失败:', error)
    toast.add({
      severity: 'error',
      summary: '生成失败',
      detail: error.message || '无法生成部门总结',
      life: 3000,
    })
  } finally {
    generatingDept.value = false
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
    selectedDepartment.value = res.data
    persons.value = res.data.persons || []
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

const formatDate = (date) => {
  if (!date) return ''
  const d = new Date(date)
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
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

onMounted(() => {
  loadDepartments()
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

.summary-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.summary-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #f8fafc;
  border: 1px solid transparent;
}

.summary-item:hover {
  background: #f1f5f9;
  border-color: #e2e8f0;
}

.summary-item.highlighted {
  background: #fffbeb;
  border-color: #fde68a;
}

.star-icon {
  color: #f59e0b;
  font-size: 13px;
  margin-top: 3px;
  flex-shrink: 0;
}

.item-content {
  font-size: 14px;
  line-height: 1.6;
  color: #334155;
}

.summary-item.highlighted .item-content {
  font-weight: 700;
  color: #1e293b;
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

.drawer-actions {
  margin-top: 28px;
  padding-top: 24px;
  border-top: 1px solid #f1f5f9;
}
</style>
