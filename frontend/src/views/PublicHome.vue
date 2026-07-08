<template>
  <div class="public-home">
    <!-- 顶部栏 -->
    <header class="public-header fade-in-up" style="--delay: 0ms">
      <div class="brand">
        <span class="brand-icon"><i class="pi pi-chart-bar"></i></span>
        <span class="brand-text">周报评分系统</span>
      </div>
      <Button label="管理员登录" icon="pi pi-lock" outlined text severity="secondary"
        @click="$router.push('/admin/login')" />
    </header>

    <!-- Hero 区 -->
    <section class="hero-section fade-in-up" style="--delay: 120ms">
      <div class="hero-content">
        <h1>让周报评分<span class="accent">更智能</span></h1>
        <p class="hero-subtitle fade-in-up" style="--delay: 280ms">上传周报文件，AI 自动识别提交人并匹配部门，实时评分，查看团队排名</p>
      </div>
    </section>

    <!-- 主内容：上传 + 排行榜 横向排列（等高） -->
    <section class="main-content">
      <!-- 合并上传区：一个卡片两个 drop-zone + 一个「上传并评分」按钮 -->
      <div ref="uploadSectionRef" class="upload-section fade-in-up" style="--delay: 240ms">
        <div class="section-inner equal-height">
          <div class="sub-section">
            <div class="section-title-row fade-in-up" style="--delay: 320ms">
              <div>
                <h2>上传周报 + 一周小结</h2>
                <p class="section-desc">周报按文件名识别提交人姓名，并作为一周小结的统一员工姓名</p>
              </div>
            </div>

            <div class="upload-card" :class="{ 'is-scoring': uploading }">
              <!-- 周报 file drop zone -->
              <div class="drop-row fade-in-up" style="--delay: 380ms">
                <span class="drop-label">① 周报（.xlsx）</span>
                <div
                  class="drop-zone small-drop"
                  :class="{ 'drag-over': reportDragOver }"
                  @dragover.prevent="reportDragOver = true"
                  @dragleave.prevent="reportDragOver = false"
                  @drop.prevent="onReportDrop"
                  @click="triggerReportInput"
                >
                  <input ref="reportInput" type="file" accept=".xlsx" style="display:none" @change="onReportFileSelect" />
                  <template v-if="!selectedReport">
                    <i class="pi pi-file-excel drop-icon small"></i>
                    <h3>点击或拖拽周报文件</h3>
                    <p>仅支持 .xlsx；姓名-YYYY年MM月第N周周报YYYYMMDD.xlsx</p>
                  </template>
                  <template v-else>
                    <i class="pi pi-file file-icon"></i>
                    <div class="file-info">
                      <span class="file-name">{{ selectedReport.name }}</span>
                      <span class="file-size">{{ formatFileSize(selectedReport.size) }}</span>
                    </div>
                    <i v-if="!uploading" class="pi pi-times remove-icon" @click.stop="clearReport"></i>
                  </template>
                </div>
              </div>

              <!-- 一周小结 image drop zone -->
              <div class="drop-row fade-in-up" style="--delay: 460ms">
                <span class="drop-label">② 一周小结（图片）</span>
                <div
                  class="drop-zone small-drop"
                  :class="{ 'drag-over': summaryDragOver }"
                  @dragover.prevent="summaryDragOver = true"
                  @dragleave.prevent="summaryDragOver = false"
                  @drop.prevent="onSummaryDrop"
                  @click="triggerSummaryInput"
                >
                  <input ref="summaryInput" type="file" accept=".png,.jpg,.jpeg" style="display:none" @change="onSummaryFileSelect" />
                  <template v-if="!summaryFile">
                    <i class="pi pi-image drop-icon small"></i>
                    <h3>点击或拖拽一周小结图片</h3>
                    <p>仅支持 .png / .jpg / .jpeg</p>
                  </template>
                  <template v-else>
                    <i class="pi pi-image file-icon"></i>
                    <div class="file-info">
                      <span class="file-name">{{ summaryFile.name }}</span>
                      <span class="file-size">{{ formatFileSize(summaryFile.size) }}</span>
                    </div>
                    <i v-if="!uploading" class="pi pi-times remove-icon" @click.stop="clearSummary"></i>
                  </template>
                </div>
              </div>

              <div class="fade-in-up" style="--delay: 540ms">
                <Button label="提交材料" icon="pi pi-send" :loading="uploading"
                  :disabled="!selectedReport || !summaryFile" @click="uploadAll" class="submit-btn" size="large" />
              </div>

              <p v-if="uploading" class="scoring-hint fade-in-up" style="--delay: 580ms">
                <i class="pi pi-spin pi-spinner"></i>
                正在提交材料，请勿关闭页面...
              </p>
            </div>
          </div>
        </div>
      </div>

      <!-- 排行榜 -->
      <div class="board-section fade-in-up" style="--delay: 320ms">
        <div class="section-inner equal-height">
          <div class="section-title-row fade-in-up" style="--delay: 400ms">
            <div>
            <h2>上周排行榜</h2>
          </div>
          </div>

        <div class="ranking-list grow">
          <DataTable :value="rankings" :loading="loading" class="ranking-table" emptyMessage="暂无评分记录"
            :paginator="true" :rows="5" paginatorPosition="bottom">
            <Column field="rank" header="排名" style="width:80px">
              <template #body="{ data, index }">
                <span class="rank-num">#{{ index + 1 }}</span>
              </template>
            </Column>
            <Column field="author_name" header="姓名" />
            <Column field="department" header="部门" />
            <Column field="total_score" header="上周得分" style="width:120px">
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
      </div>
    </section>

    <footer class="public-footer fade-in-up" style="--delay: 600ms">
      <span>© {{ year }} 周报评分系统 · Powered by AI</span>
    </footer>

    <!-- 提交结果弹窗 -->
    <Dialog v-model:visible="showResult" header="提交成功" :closable="true" :dismissableMask="true"
      :closeOnEscape="true" :style="{ width: '440px' }" class="result-dialog">
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
            <Tag value="已提交" severity="success" class="detect-tag" />
          </div>
        </div>

        <div class="result-week">
          <i class="pi pi-calendar"></i>
          <span>周报周期：{{ resultData.week_start }} ~ {{ resultData.week_end }}</span>
        </div>

        <div class="success-info">
          <i class="pi pi-check-circle"></i>
          <div>
            <p class="success-title">材料已提交，等待管理员统一评分</p>
            <p class="success-desc">管理员在管理端完成评分后，本周排行榜将自动更新</p>
          </div>
        </div>

        <div class="result-footer">
          <Button label="继续提交" icon="pi pi-check" @click="showResult = false" />
        </div>
      </div>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { unifiedUploadAPI, leaderboardAPI } from '../api'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Tag from 'primevue/tag'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

const toast = useToast()

// 周报上传
const reportInput = ref(null)
const selectedReport = ref(null)
const reportDragOver = ref(false)

// 一周小结上传
const summaryInput = ref(null)
const summaryFile = ref(null)
const summaryDragOver = ref(false)

const uploading = ref(false)

const rankings = ref([])
const loading = ref(false)

const showResult = ref(false)
const resultData = ref(null)

const year = new Date().getFullYear()

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

// 周报相关
function triggerReportInput() { reportInput.value?.click() }
function onReportFileSelect(e) {
  const f = e.target.files[0]
  if (f) { selectedReport.value = f; reportDragOver.value = false }
}
function onReportDrop(e) {
  reportDragOver.value = false
  const f = e.dataTransfer.files[0]
  if (f) {
    if (/\.xlsx$/i.test(f.name)) {
      selectedReport.value = f
    } else {
      toast.add({ severity: 'warn', summary: '周报仅支持 .xlsx 格式', life: 2500 })
    }
  }
}
function clearReport() {
  selectedReport.value = null
  if (reportInput.value) reportInput.value.value = ''
}

// 一周小结相关
function triggerSummaryInput() { summaryInput.value?.click() }
function onSummaryFileSelect(e) {
  const f = e.target.files[0]
  if (f) { summaryFile.value = f; summaryDragOver.value = false }
}
function onSummaryDrop(e) {
  summaryDragOver.value = false
  const f = e.dataTransfer.files[0]
  if (f) {
    if (/\.(png|jpg|jpeg)$/i.test(f.name)) {
      summaryFile.value = f
    } else {
      toast.add({ severity: 'warn', summary: '一周小结仅支持 .png/.jpg/.jpeg 图片', life: 2500 })
    }
  }
}
function clearSummary() {
  summaryFile.value = null
  if (summaryInput.value) summaryInput.value.value = ''
}

async function uploadAll() {
  if (!selectedReport.value || !summaryFile.value) return
  uploading.value = true
  try {
    const res = await unifiedUploadAPI.uploadUnified(selectedReport.value, summaryFile.value)
    const data = res.data
    resultData.value = {
      author_name: data.author_name,
      department: data.department,
      week_start: data.week_start,
      week_end: data.week_end,
    }
    showResult.value = true
    toast.add({ severity: 'success', summary: '材料提交成功', life: 3000 })
  } catch (e) {
    const msg = e.response?.data?.detail || '提交失败，请重试'
    toast.add({ severity: 'error', summary: msg, life: 4000 })
  } finally {
    uploading.value = false
    clearReport()
    clearSummary()
  }
}

async function loadLeaderboard() {
  loading.value = true
  try {
    // 计算上周周一日期
    const today = new Date()
    const dayOfWeek = today.getDay() || 7 // 周日=7
    const thisMonday = new Date(today)
    thisMonday.setDate(today.getDate() - dayOfWeek + 1)
    const lastMonday = new Date(thisMonday)
    lastMonday.setDate(thisMonday.getDate() - 7)
    const weekStart = lastMonday.toISOString().split('T')[0]

    const res = await leaderboardAPI.get({ period: 'week', week_start: weekStart })
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

onMounted(() => {
  loadLeaderboard()
})
</script>

<style scoped>
.public-home {
  min-height: 100vh;
  background: linear-gradient(180deg, #eef3ff 0%, #f8f9ff 40%, #ffffff 100%);
  position: relative;
  overflow-x: hidden;
}

/* 背景柔光装饰 */
.public-home::before,
.public-home::after {
  content: '';
  position: absolute;
  border-radius: 50%;
  filter: blur(80px);
  opacity: 0.55;
  pointer-events: none;
  z-index: 0;
  animation: softFloat 12s ease-in-out infinite;
}

.public-home::before {
  width: 420px;
  height: 420px;
  background: radial-gradient(circle, rgba(79, 107, 255, 0.35), transparent 70%);
  top: -120px;
  left: -80px;
}

.public-home::after {
  width: 520px;
  height: 520px;
  background: radial-gradient(circle, rgba(32, 199, 181, 0.25), transparent 70%);
  top: 60px;
  right: -140px;
  animation-delay: -4s;
}

@keyframes softFloat {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(20px, 30px) scale(1.08); }
}

/* 统一入场动画 */
.fade-in-up {
  opacity: 0;
  transform: translateY(18px);
  animation: fadeInUp 700ms cubic-bezier(0.22, 1, 0.36, 1) forwards;
  animation-delay: var(--delay, 0ms);
  will-change: transform, opacity;
}

@keyframes fadeInUp {
  0% {
    opacity: 0;
    transform: translateY(18px);
  }
  100% {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Header */
.public-header {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: relative;
  z-index: 1;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 18px;
  color: #1e2335;
}

.brand-icon { font-size: 20px; color: #4f6bff; display: inline-flex; }

/* Hero */
.hero-section {
  max-width: 1200px;
  margin: 20px auto 0;
  padding: 40px 28px 20px;
  text-align: center;
  position: relative;
  z-index: 1;
}

.hero-content h1 {
  font-size: 48px;
  font-weight: 800;
  color: #1e2335;
  letter-spacing: -1px;
  margin: 0;
  line-height: 1.15;
}

.accent {
  background: linear-gradient(120deg, #4f6bff, #20c7b5);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  display: inline-block;
  transition: transform 0.4s ease;
}

.hero-content h1:hover .accent {
  transform: translateY(-2px);
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

/* Sections - 左右布局（等高） */
.main-content {
  display: flex;
  gap: 24px;
  max-width: 1400px;
  margin: 30px auto 0;
  padding: 20px 28px;
  align-items: stretch;
  position: relative;
  z-index: 1;
}

.upload-section {
  flex: 0 0 420px;
  max-width: 420px;
  display: flex;
}

.board-section {
  flex: 1;
  min-width: 0;
  display: flex;
}

.section-inner {
  background: #ffffff;
  border-radius: 20px;
  padding: 28px;
  box-shadow: 0 4px 28px rgba(79, 107, 255, 0.08);
  border: 1px solid #eef1f9;
  transition: transform 0.35s cubic-bezier(0.22, 1, 0.36, 1),
              box-shadow 0.35s cubic-bezier(0.22, 1, 0.36, 1),
              border-color 0.35s ease;
}

.section-inner:hover {
  transform: translateY(-3px);
  box-shadow: 0 14px 42px rgba(79, 107, 255, 0.12);
  border-color: #dde5ff;
}

/* 等高布局 */
.section-inner.equal-height {
  display: flex;
  flex-direction: column;
  width: 100%;
  min-height: 480px;
}

.section-inner.equal-height .grow {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 排行榜表格占满可用高度 */
.ranking-table {
  flex: 1;
}

.section-title-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 14px;
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

/* Sub-section 容器 */
.sub-section {
  margin-bottom: 18px;
}
.sub-section:last-child {
  margin-bottom: 0;
}

.summary-input-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 8px;
}

.input-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.input-row label {
  font-size: 13px;
  color: #5a6481;
  font-weight: 500;
}

.small-drop {
  padding: 20px 14px !important;
}

.drop-icon.small {
  font-size: 32px !important;
  margin-bottom: 8px !important;
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
  transition: all 0.28s cubic-bezier(0.22, 1, 0.36, 1);
  background: #f8faff;
  position: relative;
  overflow: hidden;
}

.drop-zone::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, rgba(79, 107, 255, 0.05), rgba(32, 199, 181, 0.04));
  opacity: 0;
  transition: opacity 0.3s ease;
}

.drop-zone:hover::before, .drop-zone.drag-over::before {
  opacity: 1;
}

.drop-zone:hover, .drop-zone.drag-over {
  border-color: #4f6bff;
  background: rgba(79, 107, 255, 0.04);
  transform: translateY(-2px);
}

.drop-zone.drag-over {
  border-style: solid;
  transform: translateY(-4px) scale(1.01);
}

.drop-icon {
  font-size: 42px;
  color: #4f6bff;
  margin-bottom: 12px;
  transition: transform 0.3s ease;
}

.drop-zone:hover .drop-icon {
  transform: translateY(-3px) scale(1.08);
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
  transition: transform 0.3s ease;
}

.drop-zone:hover .file-icon {
  transform: scale(1.1);
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
  transition: color 0.2s ease, transform 0.2s ease;
}

.remove-icon:hover {
  color: #ef4444;
  transform: rotate(90deg) scale(1.1);
}

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

.top-badge {
  font-size: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.top-badge.rank-badge-1 { color: #d97706; }
.top-badge.rank-badge-2 { color: #64748b; }
.top-badge.rank-badge-3 { color: #b45309; }
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
  transition: transform 0.2s ease;
}

.trend-chip:hover {
  transform: translateY(-1px);
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
  transition: background 0.2s ease;
}

.ranking-table :deep(.p-datatable-tbody > tr) {
  transition: background 0.2s ease;
}

.ranking-table :deep(.p-datatable-tbody > tr:hover) {
  background: #f8faff !important;
}

.ranking-table :deep(.p-datatable-tbody > tr > td) {
  border-bottom: 1px solid #f3f5fb !important;
  color: #1e2335 !important;
  font-size: 14px !important;
}

.rank-num { color: #7a819a; font-weight: 600; }
.score-cell { font-weight: 700; color: #4f6bff; font-variant-numeric: tabular-nums; }
.text-muted { color: #a6adc4; }

/* Footer */
.public-footer {
  max-width: 1200px;
  margin: 50px auto 0;
  padding: 24px 28px 40px;
  text-align: center;
  color: #7a819a;
  font-size: 13px;
  position: relative;
  z-index: 1;
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

.success-info {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  background: #e8f5ee;
  border-radius: 12px;
}

.success-info .pi-check-circle {
  font-size: 20px;
  color: #16a875;
  margin-top: 2px;
}

.success-title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 600;
  color: #1e2335;
}

.success-desc {
  margin: 0;
  font-size: 13px;
  color: #5a6481;
  line-height: 1.5;
}

.result-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding-top: 6px;
}

@media (max-width: 960px) {
  .main-content { flex-direction: column; }
  .upload-section, .board-section { flex: none; max-width: none; width: 100%; }
}

@media (max-width: 768px) {
  .hero-content h1 { font-size: 32px; }
  .main-content { padding: 14px; }
  .section-inner { padding: 18px; }
}
</style>
