<template>
  <div class="public-home">
    <!-- 顶部栏 -->
    <header class="public-header fade-in-up" style="--delay: 0ms">
      <div class="brand">
        <span class="brand-icon"><i class="pi pi-chart-bar"></i></span>
        <span class="brand-text">智友辰评分系统</span>
      </div>
      <Button label="管理员登录" icon="pi pi-lock" outlined text severity="secondary"
        @click="$router.push('/admin/login')" />
    </header>

    <!-- 主内容：操作说明(左70%) + 上传区(右30%) -->
    <section class="main-content">
      <!-- 左侧：操作指南 -->
      <div class="guide-section fade-in-up" style="--delay: 200ms">
        <div class="section-inner equal-height">
          <div class="section-title-row">
            <div>
              <h2>操作指南</h2>
              <p class="section-desc">按照以下步骤完成周报和一周小结的提交</p>
            </div>
            <Button label="下载周报模板" icon="pi pi-download" severity="info" outlined
              :loading="downloading" @click="downloadTemplate" />
          </div>

          <!-- 周报上传说明 -->
          <div class="guide-block fade-in-up" style="--delay: 280ms">
            <h3 class="guide-title"><i class="pi pi-file-excel guide-icon-excel"></i> 周报上传</h3>
            <ol class="guide-steps">
              <li>按规范命名文件：<strong>姓名-YYYY年MM月第N周周报YYYYMMDD.xlsx</strong></li>
              <li>在右侧上传区点击或拖拽周报文件</li>
              <li>系统自动识别提交人姓名并匹配部门</li>
            </ol>
            <div class="screenshot-wrapper" @click="openLightbox('/example/weekly_paper.png')">
              <img src="/example/weekly_paper.png" alt="周报操作截图" class="screenshot-img" />
              <span class="zoom-hint"><i class="pi pi-search"></i></span>
            </div>
          </div>

          <!-- 一周小结说明 -->
          <div class="guide-block fade-in-up" style="--delay: 360ms">
            <h3 class="guide-title"><i class="pi pi-image guide-icon-image"></i> 一周小结</h3>
            <ol class="guide-steps">
              <li>打开企业微信「一周小结」功能</li>
              <li>截图保存一周小结页面（支持 .png / .jpg / .jpeg）</li>
              <li>在右侧上传区点击或拖拽截图文件</li>
            </ol>
            <div class="screenshot-grid">
              <div class="screenshot-wrapper" @click="openLightbox('/example/weekly_settle_1.jpg')">
                <img src="/example/weekly_settle_1.jpg" alt="步骤一截图" class="screenshot-img" />
                <span class="zoom-hint"><i class="pi pi-search"></i></span>
              </div>
              <div class="screenshot-wrapper" @click="openLightbox('/example/weekly_settle_2.jpg')">
                <img src="/example/weekly_settle_2.jpg" alt="步骤二截图" class="screenshot-img" />
                <span class="zoom-hint"><i class="pi pi-search"></i></span>
              </div>
              <div class="screenshot-wrapper" @click="openLightbox('/example/weekly_settle_3.jpg')">
                <img src="/example/weekly_settle_3.jpg" alt="步骤三截图" class="screenshot-img" />
                <span class="zoom-hint"><i class="pi pi-search"></i></span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：上传区 -->
      <div ref="uploadSectionRef" class="upload-section fade-in-up" style="--delay: 240ms">
        <div class="section-inner equal-height">
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
                :disabled="!selectedReport || !summaryFile" @click="uploadAll" class="submit-btn" />
            </div>

            <p v-if="uploading" class="scoring-hint fade-in-up" style="--delay: 580ms">
              <i class="pi pi-spin pi-spinner"></i>
              正在提交材料，请勿关闭页面...
            </p>
          </div>
        </div>
      </div>
    </section>

    <footer class="public-footer fade-in-up" style="--delay: 600ms">
      <span>© {{ year }} 智友辰评分系统 · Powered by AI</span>
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

    <!-- 图片放大查看 -->
    <div v-if="lightboxSrc" class="lightbox-overlay" @click.self="closeLightbox">
      <div class="lightbox-content">
        <button class="lightbox-close" @click="closeLightbox"><i class="pi pi-times"></i></button>
        <img :src="lightboxSrc" alt="放大查看" class="lightbox-img" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { reportAPI, unifiedUploadAPI } from '../api'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { useToast } from 'primevue/usetoast'

const toast = useToast()

const downloading = ref(false)

// 周报上传
const reportInput = ref(null)
const selectedReport = ref(null)
const reportDragOver = ref(false)

// 一周小结上传
const summaryInput = ref(null)
const summaryFile = ref(null)
const summaryDragOver = ref(false)

const uploading = ref(false)

const showResult = ref(false)
const resultData = ref(null)

// 图片放大
const lightboxSrc = ref(null)
function openLightbox(src) { lightboxSrc.value = src }
function closeLightbox() { lightboxSrc.value = null }

onMounted(() => {
  document.addEventListener('keydown', handleKeydown)
})
onUnmounted(() => {
  document.removeEventListener('keydown', handleKeydown)
})
function handleKeydown(e) {
  if (e.key === 'Escape') closeLightbox()
}

const year = new Date().getFullYear()

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function downloadTemplate() {
  downloading.value = true
  try {
    const res = await reportAPI.downloadTemplate()
    const url = window.URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    const now = new Date()
    const ds = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${String(now.getDate()).padStart(2,'0')}`
    a.download = `周报模板_${ds}.xlsx`
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

</script>

<style scoped>
.public-home {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
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
  width: 100%;
  padding: 16px 28px;
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

/* Sections - 两栏布局（操作说明 + 上传区） */
.main-content {
  display: flex;
  gap: 20px;
  width: 100%;
  margin: 16px auto 0;
  padding: 16px 24px;
  align-items: stretch;
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
}

.guide-section {
  flex: 1 1 70%;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.upload-section {
  flex: 1 1 30%;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.guide-section .section-inner,
.upload-section .section-inner {
  flex: 1;
  display: flex;
  flex-direction: column;
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
  width: 100%;
}

.section-inner.equal-height .grow {
  min-height: 0;
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

.small-drop {
  padding: 16px 14px !important;
}

.drop-icon.small {
  font-size: 28px !important;
  margin-bottom: 6px !important;
}

/* Upload card */
.upload-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.drop-zone {
  border: 2px dashed #d8e0f4;
  border-radius: 16px;
  padding: 48px 16px;
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

.submit-btn { width: 100%; }

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

/* Guide section */
.guide-block {
  margin-bottom: 24px;
  display: flex;
  flex-direction: column;
}

.guide-block:last-child {
  margin-bottom: 0;
  flex: 1;
}

.guide-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #1e2335;
  margin: 0 0 14px;
}

.guide-icon-excel {
  color: #16a875;
  font-size: 20px;
}

.guide-icon-image {
  color: #4f6bff;
  font-size: 20px;
}

.guide-steps {
  margin: 0 0 16px;
  padding-left: 20px;
  color: #5a6481;
  font-size: 14px;
  line-height: 1.8;
}

.guide-steps li {
  margin-bottom: 4px;
}

.guide-steps strong {
  color: #1e2335;
  font-weight: 600;
}

.screenshot-wrapper {
  border: 1px solid #eef1f9;
  border-radius: 10px;
  background: #fff;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.screenshot-wrapper:hover {
  border-color: #c8d4fa;
  box-shadow: 0 4px 16px rgba(79, 107, 255, 0.10);
}

/* 周报操作截图 — 宽屏图，限制宽度 */
.guide-block:nth-child(2) .screenshot-wrapper {
  max-width: 560px;
}

/* 一周小结三步截图 — 手机竖屏截图 */
.screenshot-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
}

.screenshot-grid .screenshot-wrapper {
  min-height: 180px;
}

.screenshot-img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  display: block;
  border-radius: 6px;
}

/* 周报截图 — 宽屏图按宽度缩放 */
.guide-block:nth-child(2) .screenshot-img {
  max-width: 560px;
  max-height: 280px;
}

/* 一周小结截图 — 手机竖屏图按高度缩放 */
.screenshot-grid .screenshot-img {
  max-height: 320px;
}

/* 放大镜提示 */
.screenshot-wrapper {
  cursor: zoom-in;
  position: relative;
}

.zoom-hint {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: rgba(79, 107, 255, 0.85);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  opacity: 0;
  transition: opacity 0.25s ease;
  pointer-events: none;
}

.screenshot-wrapper:hover .zoom-hint {
  opacity: 1;
}

/* Lightbox 放大查看 */
.lightbox-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.75);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.lightbox-content {
  position: relative;
  max-width: 90vw;
  max-height: 90vh;
  animation: zoomIn 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes zoomIn {
  from { transform: scale(0.85); opacity: 0; }
  to { transform: scale(1); opacity: 1; }
}

.lightbox-img {
  max-width: 90vw;
  max-height: 85vh;
  object-fit: contain;
  border-radius: 8px;
  box-shadow: 0 8px 40px rgba(0, 0, 0, 0.4);
}

.lightbox-close {
  position: absolute;
  top: -14px;
  right: -14px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  border: none;
  background: #fff;
  color: #333;
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  transition: transform 0.2s ease, background 0.2s ease;
  z-index: 1;
}

.lightbox-close:hover {
  transform: scale(1.1);
  background: #f5f5f5;
}

/* Footer */
.public-footer {
  width: 100%;
  margin-top: auto;
  padding: 20px 28px 32px;
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
  .guide-section, .upload-section { flex: none; width: 100%; }
  .screenshot-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 768px) {
  .main-content { padding: 14px; }
  .section-inner { padding: 18px; }
  .screenshot-grid { grid-template-columns: 1fr; }
}
</style>
