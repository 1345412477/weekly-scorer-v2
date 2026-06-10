<template>
  <div class="write-report page-content" :class="{ 'public-page': isPublicMode, 'embedded-mode': embedded }">
    <div v-if="isPublicMode && !embedded" class="public-nav">
      <router-link to="/" class="brand">周报评分</router-link>
      <div class="public-links">
        <router-link to="/write">提交周报</router-link>
        <router-link to="/leaderboard">排行榜</router-link>
        <router-link to="/admin/login">管理员登录</router-link>
      </div>
    </div>
    <div class="page-header">
      <div>
        <h1>提交周报</h1>
        <p class="page-subtitle">下载模板填写后上传周报文件，支持 Excel / Word / PDF 格式</p>
      </div>
    </div>

    <div class="upload-layout">
      <div class="left-panel">
        <Card class="step-card">
          <template #title><span class="step-title"><span class="step-num">1</span>下载模板</span></template>
          <template #content>
            <p class="step-desc">下载 Excel 周报模板，在本地填写完成后上传</p>
            <Button label="下载 Excel 模板" icon="pi pi-download" @click="downloadTemplate" :loading="downloading" class="download-btn" />
          </template>
        </Card>

        <Card class="step-card" style="margin-top:16px">
          <template #title><span class="step-title"><span class="step-num">2</span>选择提交人</span></template>
          <template #content>
            <div class="select-group">
              <div class="select-field">
                <label>提交人 <span class="required">*</span></label>
                <Dropdown v-model="selectedPerson" :options="persons" optionLabel="name" placeholder="选择提交人" class="w-full" @change="onPersonChange" />
              </div>
              <div class="select-field">
                <label>部门</label>
                <div class="dept-display">
                  <InputText :modelValue="selectedPerson?.department_name || selectedDepartment?.name || ''" placeholder="选择提交人后自动填充" readonly class="w-full" />
                  <span v-if="selectedPerson?.department_name" class="auto-fill-hint">✓ 自动匹配</span>
                </div>
              </div>
            </div>
          </template>
        </Card>

        <Card class="step-card" style="margin-top:16px">
          <template #title><span class="step-title"><span class="step-num">3</span>上传周报</span></template>
          <template #content>
            <div
              class="upload-area"
              :class="{ 'drag-active': isDragOver }"
              @dragover.prevent="isDragOver = true"
              @dragleave.prevent="isDragOver = false"
              @drop.prevent="onDrop"
              @click="triggerFileInput"
            >
              <input ref="fileInput" type="file" :accept="acceptFormats" style="display:none" @change="onFileSelect" />
              <div v-if="!selectedFile" class="upload-placeholder">
                <div class="upload-icon-wrap">
                  <i class="pi pi-cloud-upload upload-icon" />
                </div>
                <p class="upload-text">点击或拖拽周报文件到此处</p>
                <span class="upload-hint">支持 .xlsx、.xls、.docx、.pdf 格式</span>
              </div>
              <div v-else class="upload-file-info">
                <i :class="fileIcon" style="font-size:36px;color:#22C55E"></i>
                <div>
                  <p class="file-name">{{ selectedFile.name }}</p>
                  <span class="file-size">{{ formatFileSize(selectedFile.size) }}</span>
                </div>
                <Button icon="pi pi-times" text rounded severity="danger" @click.stop="clearFile" />
              </div>
            </div>
            <Button label="上传并评分" icon="pi pi-send" @click="uploadReport" :loading="uploading" :disabled="!selectedFile || !selectedPerson" class="upload-btn" />
          </template>
        </Card>
      </div>

      <div class="right-panel">
        <Card class="preview-card">
          <template #title>上传结果</template>
          <template #content>
            <Transition name="result-fade" mode="out-in">
              <div v-if="!uploadResult" key="empty" class="app-empty-state compact-empty">
                <i class="pi pi-inbox"></i>
                <h3>等待上传</h3>
                <p>上传周报后，解析结果和评分信息将在这里展示。</p>
              </div>
              <div v-else key="result" class="result-content">
              <div class="result-header">
                <div class="result-info">
                  <Tag :value="uploadResult.message" :severity="resultSeverity" />
                  <div v-if="uploadResult.report_type === 'catch_up'" class="type-tag-row">
                    <Tag severity="warn" :value="`补周报（${uploadResult.week_diff}周前）`" />
                  </div>
                  <div v-else-if="uploadResult.report_type === 'normal'" class="type-tag-row">
                    <Tag severity="success" value="本周周报" />
                  </div>
                </div>
                <div v-if="uploadResult.total_score" class="score-display">
                  <span class="score-value">{{ uploadResult.total_score }}</span>
                  <span :class="['grade-tag', gradeClass(uploadResult.grade)]">{{ getGradeName(uploadResult.grade) }}</span>
                </div>
              </div>

              <div v-if="uploadResult.week_start" class="week-info">
                <i class="pi pi-calendar" style="margin-right:8px"></i>
                周报时间：{{ uploadResult.week_start }} ~ {{ uploadResult.week_end }}
              </div>

              <div v-if="uploadResult.classification_message" class="classification-msg">
                <i class="pi pi-info-circle" style="margin-right:8px"></i>
                {{ uploadResult.classification_message }}
              </div>

              <div v-if="uploadResult.scoring_error" class="scoring-error">
                <i class="pi pi-exclamation-triangle" style="margin-right:8px"></i>
                {{ uploadResult.scoring_error }}
              </div>

              <div v-if="uploadResult.needs_confirmation" class="confirm-section">
                <Divider />
                <p class="confirm-title">未能自动识别周报时间，请手动确认：</p>
                <div class="confirm-fields">
                  <div class="confirm-field">
                    <label>周报开始日期</label>
                    <InputText v-model="confirmWeekStart" type="date" class="w-full" />
                  </div>
                  <div class="confirm-field">
                    <label>周报结束日期</label>
                    <InputText v-model="confirmWeekEnd" type="date" class="w-full" />
                  </div>
                </div>
                <Button label="确认并重新上传" icon="pi pi-check" @click="reuploadWithConfirm" :loading="uploading" class="confirm-btn" />
              </div>

              <div v-if="uploadResult.content_preview" class="content-preview">
                <h4>解析内容预览</h4>
                <pre>{{ uploadResult.content_preview }}</pre>
              </div>
            </div>
            </Transition>
          </template>
        </Card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { reportAPI, personAPI, departmentAPI } from '../api'
import { emitDataChanged, DataEventType } from '../utils/dataEvents'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import InputText from 'primevue/inputtext'
import Tag from 'primevue/tag'
import Divider from 'primevue/divider'
import { useToast } from 'primevue/usetoast'

const props = defineProps({
  embedded: { type: Boolean, default: false },
})

const toast = useToast()
const route = useRoute()
const isPublicMode = computed(() => props.embedded || !route.path.startsWith('/admin'))

const fileInput = ref(null)
const selectedFile = ref(null)
const isDragOver = ref(false)
const downloading = ref(false)
const uploading = ref(false)
const uploadResult = ref(null)
const persons = ref([])
const departments = ref([])
const selectedPerson = ref(null)
const selectedDepartment = ref(null)
const confirmWeekStart = ref('')
const confirmWeekEnd = ref('')

const acceptFormats = '.xlsx,.xls,.docx,.pdf'

const fileIcon = computed(() => {
  if (!selectedFile.value) return 'pi pi-file'
  const name = selectedFile.value.name.toLowerCase()
  if (name.endsWith('.xlsx') || name.endsWith('.xls')) return 'pi pi-file-excel'
  if (name.endsWith('.docx')) return 'pi pi-file-word'
  if (name.endsWith('.pdf')) return 'pi pi-file-pdf'
  return 'pi pi-file'
})

const resultSeverity = computed(() => {
  if (!uploadResult.value) return 'info'
  if (uploadResult.value.total_score != null) return 'success'
  if (uploadResult.value.report_type === 'catch_up') return 'warn'
  return 'info'
})

const gradeNames = { '优': '优', '良': '良', '一般': '一般', '差': '差' }

function gradeClass(g) {
  return { '优': 'grade-you', '良': 'grade-liang', '一般': 'grade-yiban', '差': 'grade-cha' }[g] || ''
}

function getGradeName(g) {
  return gradeNames[g] || g
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function onPersonChange() {
  if (selectedPerson.value) {
    const dept = departments.value.find(d => d.id === selectedPerson.value.department_id)
    selectedDepartment.value = dept || null
  } else {
    selectedDepartment.value = null
  }
}

async function downloadTemplate() {
  downloading.value = true
  try {
    const res = await reportAPI.downloadTemplate()
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = `周报模板_${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    toast.add({ severity: 'success', summary: '模板下载成功', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: '模板下载失败', life: 2000 })
  } finally {
    downloading.value = false
  }
}

function triggerFileInput() {
  fileInput.value?.click()
}

function onFileSelect(e) {
  const file = e.target.files[0]
  if (file) {
    selectedFile.value = file
    uploadResult.value = null
  }
}

function onDrop(e) {
  isDragOver.value = false
  const file = e.dataTransfer.files[0]
  if (file) {
    const ext = file.name.toLowerCase()
    if (ext.endsWith('.xlsx') || ext.endsWith('.xls') || ext.endsWith('.docx') || ext.endsWith('.pdf')) {
      selectedFile.value = file
      uploadResult.value = null
    } else {
      toast.add({ severity: 'warn', summary: '请上传 Excel / Word / PDF 文件', life: 2000 })
    }
  }
}

function clearFile() {
  selectedFile.value = null
  uploadResult.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function doUpload(weekStart, weekEnd) {
  if (!selectedFile.value) {
    toast.add({ severity: 'warn', summary: '请先选择文件', life: 2000 })
    return
  }
  if (!selectedPerson.value) {
    toast.add({ severity: 'warn', summary: '请先选择提交人', life: 2000 })
    return
  }

  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('person_id', selectedPerson.value.id)
    formData.append('author_name', selectedPerson.value.name)
    if (selectedPerson.value.department_id) {
      formData.append('department_id', selectedPerson.value.department_id)
    }
    if (selectedPerson.value.department_name) {
      formData.append('department', selectedPerson.value.department_name)
    }
    if (weekStart) formData.append('confirmed_week_start', weekStart)
    if (weekEnd) formData.append('confirmed_week_end', weekEnd)

    const res = await reportAPI.upload(formData)
    uploadResult.value = res.data

    if (res.data.report_type === 'future') {
      toast.add({ severity: 'error', summary: '无法提交未来时间的周报', life: 5000 })
    } else if (res.data.report_type === 'catch_up') {
      toast.add({ severity: 'warn', summary: `补周报上传成功（${res.data.week_diff}周前）`, life: 3000 })
      emitDataChanged(DataEventType.REPORTS_CHANGED, { source: 'upload' })
    } else {
      toast.add({ severity: 'success', summary: '上传成功', life: 3000 })
      emitDataChanged(DataEventType.REPORTS_CHANGED, { source: 'upload' })
    }
  } catch (e) {
    const msg = e.response?.data?.detail || '上传失败'
    uploadResult.value = { message: msg, needs_confirmation: false }
    toast.add({ severity: 'error', summary: msg, life: 5000 })
  } finally {
    uploading.value = false
  }
}

async function uploadReport() {
  await doUpload()
}

async function reuploadWithConfirm() {
  if (!confirmWeekStart.value || !confirmWeekEnd.value) {
    toast.add({ severity: 'warn', summary: '请填写完整的日期', life: 2000 })
    return
  }
  uploadResult.value = null
  await doUpload(confirmWeekStart.value, confirmWeekEnd.value)
}

async function loadData() {
  try {
    const [personsRes, deptsRes] = await Promise.all([
      personAPI.list(),
      departmentAPI.list(),
    ])
    persons.value = personsRes.data || []
    departments.value = deptsRes.data || []
  } catch (e) {
    console.error(e)
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.public-page {
  min-height: 100vh;
  padding: 24px;
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
.public-page .upload-layout {
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
.embedded-mode.public-page .upload-layout {
  max-width: none;
}

.embedded-mode .page-header {
  display: none;
}

.embedded-mode .upload-layout {
  gap: var(--spacing-md);
}

/* ========== 布局 ========== */
.upload-layout {
  display: grid;
  grid-template-columns: minmax(360px, 0.92fr) minmax(420px, 1.08fr);
  gap: var(--spacing-lg);
  align-items: start;
}

.left-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  min-width: 0; /* 防止 grid 子项溢出 */
}

/* ========== 步骤卡片 ========== */
.step-card :deep(.p-card-title) {
  color: var(--text-secondary) !important;
  font-size: var(--text-sm) !important;
}

.step-title {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-weight: var(--font-semibold);
  font-size: var(--text-base);
  color: var(--text-primary);
}

.step-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
  flex-shrink: 0;
  line-height: 1;
}

.step-desc {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  margin-bottom: var(--spacing-md);
}

.download-btn {
  width: 100%;
}

/* ========== 上传区域 ========== */
.upload-area {
  border: 2px dashed var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  text-align: center;
  cursor: pointer;
  transition: all var(--transition-normal);
  min-height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.upload-area:hover {
  border-color: var(--primary);
  background: var(--primary-bg);
  animation: dash-pulse 1.2s ease-in-out infinite;
}

.upload-area.drag-active {
  border-color: var(--primary);
  background: var(--primary-bg);
  animation: dash-pulse 0.8s ease-in-out infinite;
  box-shadow: 0 0 0 3px rgba(91, 95, 199, 0.15);
  transform: scale(1.02);
}

@keyframes dash-pulse {
  0%, 100% { border-color: var(--primary); }
  50% { border-color: var(--primary-dark); }
}

.upload-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upload-icon-wrap {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--primary-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--spacing-sm);
  transition: transform var(--transition-normal);
}

.upload-area:hover .upload-icon-wrap,
.upload-area.drag-active .upload-icon-wrap {
  transform: scale(1.1);
  background: rgba(91, 95, 199, 0.12);
}

.upload-icon {
  font-size: 32px;
  color: var(--primary);
}

.upload-text {
  color: var(--text-primary);
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  margin: 0;
}

.upload-hint {
  color: var(--text-muted);
  font-size: var(--text-xs);
  margin-top: var(--spacing-xs);
}

.upload-file-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  width: 100%;
}

.file-name {
  color: var(--text-primary);
  font-weight: var(--font-medium);
  word-break: break-all;
}

.file-size {
  color: var(--text-muted);
  font-size: var(--text-xs);
}

/* ========== 选择区域 ========== */
.select-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.select-field label {
  display: block;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  margin-bottom: var(--spacing-xs);
}

.required {
  color: var(--danger);
}

.dept-display {
  position: relative;
}

.dept-display :deep(input) {
  background: var(--bg-dark) !important;
  color: var(--text-secondary) !important;
}

.auto-fill-hint {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--success);
  font-size: var(--text-xs);
}

.upload-btn {
  width: 100%;
  margin-top: var(--spacing-md);
}

/* ========== 预览卡片 ========== */
.preview-card {
  position: sticky;
  top: var(--spacing-lg);
}

.preview-card :deep(.p-card-body) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 120px);
}

.embedded-mode .preview-card :deep(.p-card-body) {
  max-height: none;
}

.preview-card :deep(.p-card-content) {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

.preview-card :deep(.p-card-title) {
  color: var(--text-secondary) !important;
  font-size: var(--text-sm) !important;
}

/* ========== 结果过渡动画 ========== */
.result-fade-enter-active {
  transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
}

.result-fade-leave-active {
  transition: all 0.2s ease-in;
}

.result-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}

.result-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ========== 空状态 ========== */
.compact-empty {
  min-height: 132px;
  padding: var(--spacing-lg) var(--spacing-md);
}

.embedded-mode .compact-empty {
  min-height: 118px;
  padding: var(--spacing-md);
}

.empty-state {
  text-align: center;
  padding: var(--spacing-xl) 0;
  color: var(--text-muted);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 150px;
}

.compact-empty h3 {
  margin: var(--spacing-xs) 0 0;
  font-size: var(--text-base);
}

.compact-empty p {
  max-width: 360px;
  margin-top: var(--spacing-xs);
}

.empty-state p {
  margin-top: var(--spacing-md);
  font-size: var(--text-sm);
}

/* ========== 结果内容 ========== */
.result-content {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.result-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-md);
  flex-wrap: wrap;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  flex: 1;
  min-width: 0;
}

.type-tag-row {
  margin-top: 4px;
}

.score-display {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-shrink: 0;
}

.score-value {
  font-size: var(--text-2xl);
  font-weight: var(--font-bold);
  color: var(--primary-light);
}

/* ========== 信息块 ========== */
.week-info {
  background: var(--bg-dark);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  word-break: break-word;
  display: flex;
  align-items: center;
}

.classification-msg {
  background: var(--primary-bg);
  border: 1px solid rgba(91, 95, 199, 0.2);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  color: var(--primary);
  font-size: var(--text-sm);
  word-break: break-word;
  display: flex;
  align-items: flex-start;
  line-height: 1.5;
}

.scoring-error {
  background: var(--danger-bg);
  border: 1px solid var(--danger);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  color: var(--danger);
  font-size: var(--text-sm);
  word-break: break-word;
  display: flex;
  align-items: flex-start;
  line-height: 1.5;
}

/* ========== 确认区域 ========== */
.confirm-section {
  margin-top: var(--spacing-md);
}

.confirm-title {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
  margin-bottom: var(--spacing-md);
}

.confirm-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.confirm-field label {
  display: block;
  color: var(--text-secondary);
  font-size: var(--text-xs);
  margin-bottom: 4px;
}

.confirm-btn {
  width: 100%;
}

/* ========== 内容预览 ========== */
.content-preview {
  background: var(--bg-dark);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: var(--spacing-md);
  overflow: hidden;
}

.content-preview h4 {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  margin-bottom: var(--spacing-sm);
  font-weight: var(--font-semibold);
}

.content-preview pre {
  color: var(--text-primary);
  font-size: var(--text-xs);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  word-wrap: break-word;
  max-height: 300px;
  overflow-y: auto;
  overflow-x: hidden;
  margin: 0;
  padding: var(--spacing-sm);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

/* ========== 响应式断点 ========== */

/* 平板端 (< 1200px) */
@media (max-width: 1200px) {
  .upload-layout {
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }

  .left-panel {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: var(--spacing-md);
  }

  .step-card[style] {
    margin-top: 0 !important;
  }

  .right-panel {
    width: 100%;
  }
  
  .preview-card {
    position: static;
  }
  
  .preview-card :deep(.p-card-body) {
    max-height: none;
  }
}

/* 移动端 (< 640px) */
@media (max-width: 640px) {
  .write-report.public-page {
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

  .upload-layout {
    gap: var(--spacing-md);
  }

  .left-panel {
    grid-template-columns: 1fr;
  }
  
  .upload-area {
    padding: var(--spacing-md);
    min-height: 112px;
  }

  .upload-icon-wrap {
    width: 52px;
    height: 52px;
  }

  .upload-icon {
    font-size: 26px;
  }

  .upload-file-info {
    align-items: flex-start;
    gap: var(--spacing-sm);
  }
  
  .result-header {
    flex-direction: column;
  }
  
  .score-display {
    align-self: flex-start;
  }
  
  .confirm-fields {
    grid-template-columns: 1fr;
  }
  
  .content-preview pre {
    max-height: 200px;
  }
}
</style>
