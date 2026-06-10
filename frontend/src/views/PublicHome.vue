<template>
  <div class="public-home">
    <!-- 顶部栏 -->
    <header class="public-header">
      <div class="brand">
        <span class="brand-icon">📊</span>
        <span class="brand-text">周报评分系统</span>
      </div>
      <Button label="管理员登录" icon="pi pi-lock" outlined text severity="secondary"
        @click="$router.push('/admin/login')" />
    </header>

    <!-- Hero 区 -->
    <section class="hero-section">
      <div class="hero-content">
        <h1>让周报评分<span class="accent">更智能</span></h1>
        <p class="hero-subtitle">上传周报文件，AI 自动识别提交人并匹配部门，实时评分，查看团队排名</p>

        <div class="action-row">
          <Button label="立即上传周报" icon="pi pi-cloud-upload" size="large" @click="scrollToUpload" />
          <Button label="查看排行榜" icon="pi pi-trophy" outlined severity="secondary" size="large"
            @click="scrollToBoard" />
        </div>
      </div>
    </section>

    <!-- 上传区 -->
    <section ref="uploadSectionRef" class="upload-section">
      <div class="section-inner">
        <div class="section-title-row">
          <div>
            <span class="eyebrow">第一步</span>
            <h2>上传周报</h2>
            <p class="section-desc">支持 Excel / Word / PDF 格式，系统将自动识别提交人并匹配部门</p>
          </div>
        </div>

        <div class="upload-card" :class="{ 'is-scoring': uploading }">
          <div
            class="drop-zone"
            :class="{ 'drag-over': isDragOver }"
            @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false"
            @drop.prevent="onDrop"
            @click="triggerFileInput"
          >
            <input ref="fileInput" type="file" :accept="acceptFormats" style="display:none" @change="onFileSelect" />
            <template v-if="!selectedFile">
              <i class="pi pi-cloud-upload drop-icon"></i>
              <h3>点击或拖拽文件到此处</h3>
              <p>支持 .xlsx、.xls、.docx、.pdf 格式</p>
            </template>
            <template v-else>
              <i class="pi pi-file file-icon"></i>
              <div class="file-info">
                <span class="file-name">{{ selectedFile.name }}</span>
                <span class="file-size">{{ formatFileSize(selectedFile.size) }}</span>
              </div>
              <i v-if="!uploading" class="pi pi-times remove-icon" @click.stop="clearFile"></i>
            </template>
          </div>

          <Button label="上传并评分" icon="pi pi-send" :loading="uploading" :disabled="!selectedFile"
            @click="uploadReport" class="submit-btn" size="large" />

          <p v-if="uploading" class="scoring-hint">
            <i class="pi pi-spin pi-spinner"></i>
            正在识别提交人并评分，请勿关闭页面...
          </p>
        </div>
      </div>
    </section>

    <!-- 排行榜 -->
    <section ref="boardSectionRef" class="board-section">
      <div class="section-inner">
        <div class="section-title-row">
          <div>
            <span class="eyebrow">团队排名</span>
            <h2>本周排行榜</h2>
            <p class="section-desc">按本周得分排序，趋势箭头对比上周</p>
          </div>
          <div class="toolbar-right">
            <SelectButton v-model="period" :options="periodOptions" optionLabel="label" optionValue="value" />
          </div>
        </div>

        <div class="ranking-list">
          <!-- 前三名徽章 -->
          <div v-if="topThree.length" class="top-three">
            <div v-for="(item, idx) in topThree" :key="item.author_name" :class="['top-item', `rank-${idx + 1}`]">
              <span class="top-badge">{{ idx === 0 ? '🥇' : idx === 1 ? '🥈' : '🥉' }}</span>
              <span class="top-name">{{ item.author_name }}</span>
              <span class="top-dept">{{ item.department || '—' }}</span>
              <span class="top-score">{{ item.total_score }} 分</span>
              <span v-if="item.trend !== null" :class="['trend-chip', trendClass(item.trend)]">
                <i :class="trendIcon(item.trend)"></i>
                {{ item.trend > 0 ? '+' : '' }}{{ item.trend }}
              </span>
            </div>
          </div>

          <!-- 表格 -->
          <DataTable :value="rankings.slice(3)" :loading="loading" class="ranking-table" emptyMessage="暂无评分记录">
            <Column field="rank" header="排名" style="width:80px">
              <template #body="{ data, index }">
                <span class="rank-num">#{{ index + 4 }}</span>
              </template>
            </Column>
            <Column field="author_name" header="姓名" />
            <Column field="department" header="部门" />
            <Column field="total_score" header="本周得分" style="width:120px">
              <template #body="{ data }">
                <span class="score-cell">{{ data.total_score }}</span>
              </template>
            </Column>
            <Column header="趋势" style="width:110px">
              <template #body="{ data }">
                <span v-if="data.trend !== null" :class="['trend-chip', trendClass(data.trend)]">
                  <i :class="trendIcon(data.trend)"></i>
                  {{ data.trend > 0 ? '+' : '' }}{{ data.trend }}
                </span>
                <span v-else class="trend-chip trend-neutral">—</span>
              </template>
            </Column>
            <Column field="latest_grade" header="等级" style="width:80px">
              <template #body="{ data }">
                <Tag v-if="data.latest_grade" :value="data.latest_grade" :severity="gradeSeverity(data.latest_grade)" />
                <span v-else class="text-muted">—</span>
              </template>
            </Column>
          </DataTable>
        </div>
      </div>
    </section>

    <footer class="public-footer">
      <span>© {{ year }} 周报评分系统 · Powered by AI</span>
    </footer>

    <!-- 评分结果弹窗 -->
    <Dialog v-model:visible="showResult" :header="'评分完成 🎉'" :closable="true" :dismissableMask="true"
      :closeOnEscape="true" :style="{ width: '520px' }" class="result-dialog">
      <div v-if="resultData" class="result-body">
        <div class="result-header">
          <div class="result-info">
            <div class="result-author">
              <i class="pi pi-user result-avatar"></i>
              <div>
                <span class="author-name">{{ resultData.author_name }}</span>
                <span class="author-dept">{{ resultData.department || '未匹配部门' }}</span>
              </div>
            </div>
            <Tag v-if="resultData.auto_detected" value="自动识别" severity="success" class="detect-tag" />
          </div>
          <div class="result-score-box">
            <span class="score-number">{{ resultData.total_score ?? '—' }}</span>
            <Tag v-if="resultData.grade" :value="resultData.grade" :severity="gradeSeverity(resultData.grade)" class="grade-tag" />
          </div>
        </div>

        <div class="result-week">
          <i class="pi pi-calendar"></i>
          <span>周报周期：{{ resultData.week_start }} ~ {{ resultData.week_end }}</span>
        </div>

        <div v-if="resultData.dimension_scores && resultData.dimension_scores.length" class="dim-block">
          <h4>各维度得分</h4>
          <div class="dim-list">
            <div v-for="(d, idx) in resultData.dimension_scores.slice(0, 6)" :key="idx" class="dim-row">
              <span class="dim-name">{{ d.name || '维度' + (idx + 1) }}</span>
              <div class="dim-bar-wrap">
                <div class="dim-bar" :style="{ width: Math.min(100, ((d.score || 0) / (d.max || 100)) * 100) + '%' }"></div>
              </div>
              <span class="dim-score">{{ d.score }}/{{ d.max }}</span>
            </div>
          </div>
        </div>

        <div v-if="resultData.ai_comment" class="comment-block">
          <h4><i class="pi pi-comments"></i> AI 评语</h4>
          <p>{{ resultData.ai_comment }}</p>
        </div>

        <div v-if="resultData.ai_suggestion" class="suggestion-block">
          <h4><i class="pi pi-lightbulb"></i> 改进建议</h4>
          <p>{{ resultData.ai_suggestion }}</p>
        </div>

        <div v-if="resultData.scoring_error" class="error-block">
          <i class="pi pi-exclamation-triangle"></i>
          <span>{{ resultData.scoring_error }}</span>
        </div>

        <div class="result-footer">
          <Button label="查看排行榜" icon="pi pi-list" outlined severity="secondary" @click="closeAndScrollToBoard" />
          <Button label="继续上传" icon="pi pi-check" @click="showResult = false" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { reportAPI, leaderboardAPI } from '../api'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import SelectButton from 'primevue/selectbutton'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

const toast = useToast()

const fileInput = ref(null)
const selectedFile = ref(null)
const isDragOver = ref(false)
const uploading = ref(false)

const uploadSectionRef = ref(null)
const boardSectionRef = ref(null)

const rankings = ref([])
const period = ref('week')
const loading = ref(false)

const showResult = ref(false)
const resultData = ref(null)

const acceptFormats = '.xlsx,.xls,.docx,.pdf'

const year = new Date().getFullYear()

const periodOptions = [
  { label: '本周', value: 'week' },
  { label: '本月', value: 'month' },
  { label: '全部', value: 'all' },
]

const topThree = computed(() => rankings.value.slice(0, 3))

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function triggerFileInput() {
  fileInput.value?.click()
}

function onFileSelect(e) {
  const f = e.target.files[0]
  if (f) {
    selectedFile.value = f
    isDragOver.value = false
  }
}

function onDrop(e) {
  isDragOver.value = false
  const f = e.dataTransfer.files[0]
  if (f) {
    const ext = f.name.toLowerCase()
    if (/\.(xlsx|xls|docx|pdf)$/.test(ext)) {
      selectedFile.value = f
    } else {
      toast.add({ severity: 'warn', summary: '请上传支持的文件格式', life: 2000 })
    }
  }
}

function clearFile() {
  selectedFile.value = null
  if (fileInput.value) fileInput.value.value = ''
}

async function uploadReport() {
  if (!selectedFile.value) return
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    const res = await reportAPI.upload(formData)
    resultData.value = res.data
    showResult.value = true
    await loadLeaderboard()
    toast.add({ severity: 'success', summary: res.data.message || '上传并评分成功', life: 3000 })
  } catch (e) {
    const msg = e.response?.data?.detail || '上传失败，请重试'
    toast.add({ severity: 'error', summary: msg, life: 4000 })
  } finally {
    uploading.value = false
    clearFile()
  }
}

async function loadLeaderboard() {
  loading.value = true
  try {
    const res = await leaderboardAPI.get({ period: period.value })
    rankings.value = res.data.rankings || []
  } catch (e) {
    rankings.value = []
  } finally {
    loading.value = false
  }
}

function trendClass(t) {
  if (t === null || t === undefined) return 'trend-neutral'
  if (t > 0) return 'trend-up'
  if (t < 0) return 'trend-down'
  return 'trend-neutral'
}

function trendIcon(t) {
  if (t > 0) return 'pi pi-arrow-up'
  if (t < 0) return 'pi pi-arrow-down'
  return 'pi pi-minus'
}

function gradeSeverity(g) {
  if (g === '优' || g === '良') return 'success'
  if (g === '一般') return 'warn'
  if (g === '差') return 'danger'
  return 'info'
}

function scrollToUpload() {
  uploadSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function scrollToBoard() {
  boardSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function closeAndScrollToBoard() {
  showResult.value = false
  setTimeout(scrollToBoard, 200)
}

onMounted(() => {
  loadLeaderboard()
})
</script>

<style scoped>
.public-home {
  min-height: 100vh;
  background: linear-gradient(180deg, #eef3ff 0%, #f8f9ff 40%, #ffffff 100%);
}

/* Header */
.public-header {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 18px;
  color: #1e2335;
}

.brand-icon { font-size: 24px; }

/* Hero */
.hero-section {
  max-width: 1200px;
  margin: 20px auto 0;
  padding: 40px 28px 20px;
  text-align: center;
}

.hero-content h1 {
  font-size: 48px;
  font-weight: 800;
  color: #1e2335;
  letter-spacing: -1px;
  margin: 0;
}

.accent {
  color: #4f6bff;
}

.hero-subtitle {
  margin: 16px auto 28px;
  font-size: 16px;
  color: #5a6481;
  max-width: 600px;
}

.action-row {
  display: inline-flex;
  gap: 12px;
}

/* Sections */
.upload-section,
.board-section {
  max-width: 1200px;
  margin: 30px auto 0;
  padding: 20px 28px;
}

.section-inner {
  background: #ffffff;
  border-radius: 20px;
  padding: 28px;
  box-shadow: 0 2px 20px rgba(79, 107, 255, 0.06);
  border: 1px solid #eef1f9;
}

.section-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 14px;
}

.eyebrow {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(79, 107, 255, 0.1);
  color: #4f6bff;
  font-weight: 600;
  font-size: 12px;
  margin-bottom: 8px;
}

h2 {
  margin: 0;
  font-size: 24px;
  color: #1e2335;
}

.section-desc {
  margin: 6px 0 0;
  color: #5a6481;
  font-size: 14px;
}

/* Upload card */
.upload-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.drop-zone {
  border: 2px dashed #d8e0f4;
  border-radius: 16px;
  padding: 36px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s ease;
  background: #f8faff;
}

.drop-zone:hover, .drop-zone.drag-over {
  border-color: #4f6bff;
  background: rgba(79, 107, 255, 0.05);
}

.drop-icon {
  font-size: 42px;
  color: #4f6bff;
  margin-bottom: 12px;
}

.drop-zone h3 {
  margin: 0 0 6px;
  font-size: 17px;
  color: #1e2335;
}

.drop-zone p {
  margin: 0;
  font-size: 13px;
  color: #5a6481;
}

.file-icon {
  font-size: 38px;
  color: #4f6bff;
}

.file-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
  max-width: 420px;
  margin-left: 16px;
  text-align: left;
}

.file-name {
  font-size: 15px;
  font-weight: 600;
  color: #1e2335;
  word-break: break-all;
}

.file-size {
  font-size: 12px;
  color: #5a6481;
}

.remove-icon {
  font-size: 18px;
  color: #a6adc4;
  padding: 6px;
  cursor: pointer;
}

.remove-icon:hover { color: #ef4444; }

.submit-btn { align-self: center; min-width: 220px; }

.scoring-hint {
  text-align: center;
  color: #4f6bff;
  font-size: 13px;
  margin: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

/* Ranking */
.ranking-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.top-three {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.top-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 20px 14px;
  border-radius: 16px;
  gap: 8px;
  text-align: center;
  position: relative;
}

.top-item.rank-1 {
  background: linear-gradient(135deg, #fff8e1 0%, #ffecb3 100%);
  border: 1px solid #ffd966;
}

.top-item.rank-2 {
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e7ef 100%);
  border: 1px solid #d3d8e4;
}

.top-item.rank-3 {
  background: linear-gradient(135deg, #fdf0e6 0%, #fadcc5 100%);
  border: 1px solid #f0b97a;
}

.top-badge { font-size: 28px; }
.top-name { font-size: 16px; font-weight: 700; color: #1e2335; }
.top-dept { font-size: 12px; color: #5a6481; }
.top-score { font-size: 18px; font-weight: 700; color: #4f6bff; margin-top: 4px; }

.trend-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.trend-up { background: rgba(22, 168, 117, 0.12); color: #16a875; }
.trend-down { background: rgba(239, 68, 68, 0.12); color: #ef4444; }
.trend-neutral { background: #eef1f9; color: #7a819a; }

.ranking-table {
  background: transparent;
}

.ranking-table :deep(.p-datatable-thead > tr > th) {
  background: #f8faff !important;
  color: #5a6481 !important;
  font-weight: 600 !important;
  font-size: 13px !important;
  border: none !important;
  border-bottom: 1px solid #eef1f9 !important;
}

.ranking-table :deep(.p-datatable-tbody > tr > td) {
  border-bottom: 1px solid #f3f5fb !important;
  color: #1e2335 !important;
  font-size: 14px !important;
}

.rank-num { color: #7a819a; font-weight: 600; }
.score-cell { font-weight: 700; color: #4f6bff; }
.text-muted { color: #a6adc4; }

/* Footer */
.public-footer {
  max-width: 1200px;
  margin: 50px auto 0;
  padding: 24px 28px 40px;
  text-align: center;
  color: #7a819a;
  font-size: 13px;
}

/* Result Dialog */
.result-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
}

.result-info {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.result-author {
  display: flex;
  align-items: center;
  gap: 12px;
}

.result-avatar {
  font-size: 20px;
  background: rgba(79, 107, 255, 0.1);
  color: #4f6bff;
  padding: 10px;
  border-radius: 50%;
}

.author-name {
  font-size: 17px;
  font-weight: 700;
  color: #1e2335;
  display: block;
}

.author-dept {
  font-size: 13px;
  color: #5a6481;
}

.detect-tag {
  align-self: flex-start;
}

.result-score-box {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}

.score-number {
  font-size: 40px;
  font-weight: 800;
  color: #4f6bff;
  line-height: 1;
}

.grade-tag {
  font-size: 13px !important;
  padding: 4px 12px !important;
}

.result-week {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f8faff;
  border-radius: 10px;
  color: #5a6481;
  font-size: 13px;
}

.dim-block h4, .comment-block h4, .suggestion-block h4 {
  margin: 0 0 10px;
  font-size: 14px;
  color: #1e2335;
  display: flex;
  align-items: center;
  gap: 6px;
}

.dim-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dim-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.dim-name {
  min-width: 100px;
  font-size: 13px;
  color: #5a6481;
}

.dim-bar-wrap {
  flex: 1;
  height: 6px;
  background: #eef1f9;
  border-radius: 3px;
  overflow: hidden;
}

.dim-bar {
  height: 100%;
  background: linear-gradient(90deg, #4f6bff, #6ed0ff);
  border-radius: 3px;
  transition: width 0.3s ease;
}

.dim-score {
  min-width: 60px;
  text-align: right;
  font-size: 13px;
  font-weight: 600;
  color: #1e2335;
}

.comment-block, .suggestion-block {
  padding: 12px 14px;
  background: #f8faff;
  border-radius: 10px;
}

.comment-block p, .suggestion-block p {
  margin: 0;
  font-size: 13px;
  color: #3a4059;
  line-height: 1.6;
}

.error-block {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: rgba(239, 68, 68, 0.08);
  border-radius: 10px;
  color: #ef4444;
  font-size: 13px;
}

.result-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 6px;
}

@media (max-width: 768px) {
  .hero-content h1 { font-size: 32px; }
  .top-three { grid-template-columns: 1fr; }
  .action-row { flex-direction: column; align-items: center; }
  .upload-section, .board-section { padding: 14px; }
  .section-inner { padding: 18px; }
}
</style>
