<template>
  <div class="report-detail page-content">
    <div class="page-header">
      <div class="header-left">
        <Button icon="pi pi-arrow-left" text @click="$router.back()" />
        <div>
          <h1>周报详情</h1>
          <p class="page-subtitle">{{ report.author_name }} · 第{{ weekNum }}周 · {{ report.department || '未设置部门' }}
          </p>
        </div>
      </div>
      <div class="header-right">
        <Tag :value="statusLabel(report.status)" :severity="statusSeverity(report.status)" />
        <ScoreBadge v-if="report.total_score != null" :score="report.total_score" size="lg" />
        <GradeTag v-if="report.grade" :grade="report.grade" />
      </div>
    </div>

    <div v-if="loading" class="loading-state">加载中...</div>

    <div v-else class="detail-layout">
      <!-- 左：内容 -->
      <div class="content-panel">
        <Card class="detail-card" v-for="(section, sIdx) in parsedSections" :key="sIdx" :style="sIdx > 0 ? 'margin-top: 20px' : ''">
          <template #title>{{ section.title }}</template>
          <template #content>
            <div v-if="section.items.length" class="report-table-wrap">
              <table class="report-table">
                <thead>
                  <tr>
                    <th style="width:50px">#</th>
                    <th>工作事项</th>
                    <th style="width:100px">负责人</th>
                    <th style="width:180px">{{ section.type === 'last_week' ? '结果反馈' : '预期产出' }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, iIdx) in section.items" :key="iIdx">
                    <td class="item-num">{{ iIdx + 1 }}</td>
                    <td>
                      <div class="item-title">{{ item.title }}</div>
                      <div class="item-content">{{ item.content }}</div>
                    </td>
                    <td>{{ item.person || '-' }}</td>
                    <td class="item-result">{{ item.result || '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div v-else class="empty-hint">暂无内容</div>
          </template>
        </Card>
      </div>

      <!-- 右：评分 -->
      <div class="score-panel">
        <!-- 维度评分 -->
        <Card class="detail-card">
          <template #title><i class="pi pi-chart-bar" style="color:#4f6bff;margin-right:6px"></i>维度评分</template>
          <template #content>
            <div v-if="report.dimension_scores?.length" class="dim-scores">
              <div v-for="(dim, idx) in report.dimension_scores" :key="idx" class="dim-row">
                <div class="dim-header">
                  <span class="dim-name">{{ dim.name }}</span>
                  <span class="dim-score">{{ dim.score }}/{{ dim.max }}</span>
                </div>
                <div class="dim-bar">
                  <div class="dim-fill" :style="{ width: (dim.score / dim.max * 100) + '%' }"
                    :class="scoreLevel(dim.score / dim.max)">
                    <span class="dim-bar-label">{{ dim.score }}/{{ dim.max }}</span>
                  </div>
                </div>
                <p v-if="dim.comment" class="dim-comment">{{ dim.comment }}</p>
              </div>
            </div>
            <div v-else class="empty-hint">暂无评分数据</div>
          </template>
        </Card>

        <!-- 时间线 -->
        <Card class="detail-card" style="margin-top:16px">
          <template #title>时间线</template>
          <template #content>
            <div class="timeline">
              <div class="timeline-item">
                <div class="timeline-node">
                  <span class="timeline-dot draft"></span>
                  <div class="timeline-line"></div>
                </div>
                <div>
                  <span class="timeline-label">创建</span>
                  <span class="timeline-time">{{ formatBeijingTimeShort(report.created_at) }}</span>
                </div>
              </div>
              <div class="timeline-item" v-if="report.submit_time">
                <div class="timeline-node">
                  <span class="timeline-dot submitted"></span>
                  <div class="timeline-line"></div>
                </div>
                <div>
                  <span class="timeline-label">提交</span>
                  <span class="timeline-time">{{ formatBeijingTimeShort(report.submit_time) }}</span>
                </div>
              </div>
              <div class="timeline-item" v-if="report.score_time">
                <div class="timeline-node">
                  <span class="timeline-dot scored"></span>
                  <div class="timeline-line"></div>
                </div>
                <div>
                  <span class="timeline-label">评分完成</span>
                  <span class="timeline-time">{{ formatBeijingTimeShort(report.score_time) }}</span>
                </div>
              </div>
            </div>
          </template>
        </Card>

        <!-- 一周小结截图 -->
        <Card class="detail-card" style="margin-top:16px">
          <template #title><i class="pi pi-image" style="color:#4f6bff;margin-right:6px"></i>一周小结截图</template>
          <template #content>
            <div v-if="summaryLoading" class="empty-hint">加载中...</div>
            <template v-else-if="summaryInfo && summaryImageUrl">
              <div class="summary-meta">
                <span v-if="summaryInfo.work_session_count != null">工作次数 {{ summaryInfo.work_session_count }} 次</span>
                <span v-if="summaryInfo.total_minutes != null">总时长 {{ Math.round(summaryInfo.total_minutes / 60 * 10) / 10 }} 小时</span>
                <span v-if="summaryInfo.latest_time">最晚时间 {{ summaryInfo.latest_time }}</span>
              </div>
              <div class="summary-thumb" @click="previewVisible = true" title="点击放大查看">
                <img :src="summaryImageUrl" alt="一周小结截图" />
                <div class="summary-thumb-mask"><i class="pi pi-window-maximize"></i> 点击放大</div>
              </div>
            </template>
            <div v-else class="empty-hint">该员工本周未上传一周小结</div>
          </template>
        </Card>
      </div>
    </div>

    <!-- 一周小结放大预览 -->
    <Dialog v-model:visible="previewVisible" modal :style="{ width: '90vw', maxWidth: '1100px' }"
            :contentStyle="{ padding: '0' }" class="summary-preview-dialog">
      <template #header>
        <div class="preview-header">
          <i class="pi pi-image"></i>
          <span>一周小结 · {{ report.author_name }}（{{ report.week_start }} ~ {{ report.week_end }}）</span>
        </div>
      </template>
      <div class="preview-body" @click="previewVisible = false">
        <img :src="summaryImageUrl" alt="一周小结截图（放大）" @click.stop />
      </div>
      <template #footer>
        <div class="preview-footer-hint">点击空白处或按 ESC 关闭</div>
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { reportAPI, weeklySummaryAPI } from '../api'
import { formatBeijingTimeShort } from '../utils/timeUtil'
import Card from 'primevue/card'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import ScoreBadge from '../components/ui/ScoreBadge.vue'
import GradeTag from '../components/ui/GradeTag.vue'

const route = useRoute()
const loading = ref(true)
const report = ref({})

// 一周小结截图
const summaryLoading = ref(false)
const summaryInfo = ref(null)
const summaryImageUrl = ref('')
const previewVisible = ref(false)

/**
 * 解析周报内容为结构化表格数据
 * 支持格式：
 *   ## 上周工作内容 / ## 上周工作回顾
 *   ### 1. 事项标题
 *   - 工作内容：...
 *   - 汇报人：...
 *   - 结果反馈：... / - 预期产出：...
 */
const parsedSections = computed(() => {
  const content = report.value.content || ''
  if (!content) return []

  const sections = []

  // 按 ## 标题分割
  const sectionBlocks = content.split(/^##\s+/m).filter(Boolean)

  for (const block of sectionBlocks) {
    const lines = block.split('\n')
    const titleLine = lines[0].trim()
    // 识别"上周"或"本周"相关标题
    const isLastWeek = /上周|回顾/.test(titleLine)
    const isThisWeek = /本周|计划/.test(titleLine)
    if (!isLastWeek && !isThisWeek) continue

    const type = isLastWeek ? 'last_week' : 'this_week'
    const title = titleLine.replace(/\d+[、.]\s*/, '').trim() || (isLastWeek ? '上周工作内容' : '本周工作计划')

    const items = []
    let currentItem = null

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim()
      if (!line) continue

      // ### 开头 = 新事项
      if (line.startsWith('###')) {
        if (currentItem) items.push(currentItem)
        const itemTitle = line.replace(/^###\s*\d+[、.]*\s*/, '').trim()
        currentItem = { title: itemTitle, content: '', person: '', result: '' }
        continue
      }

      // - 开头 = 属性行
      if (line.startsWith('-') && currentItem) {
        const body = line.replace(/^-\s*/, '').trim()
        if (body.startsWith('工作内容：') || body.startsWith('工作内容:')) {
          currentItem.content = body.replace(/^工作内容[：:]\s*/, '')
        } else if (body.startsWith('汇报人：') || body.startsWith('汇报人:')) {
          currentItem.person = body.replace(/^汇报人[：:]\s*/, '')
        } else if (body.startsWith('结果反馈：') || body.startsWith('结果反馈:')) {
          currentItem.result = body.replace(/^结果反馈[：:]\s*/, '')
        } else if (body.startsWith('预期产出：') || body.startsWith('预期产出:')) {
          currentItem.result = body.replace(/^预期产出[：:]\s*/, '')
        }
      }
    }
    if (currentItem) items.push(currentItem)

    if (items.length) {
      sections.push({ type, title, items })
    }
  }

  return sections
})

const weekNum = computed(() => {
  if (!report.value.week_start) return '-'
  const d = new Date(report.value.week_start)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() + 3 - (d.getDay() + 6) % 7)
  const w1 = new Date(d.getFullYear(), 0, 4)
  return 1 + Math.round(((d - w1) / 86400000 - 3 + (w1.getDay() + 6) % 7) / 7)
})

function statusLabel(s) {
  return { draft: '草稿', submitted: '已提交', scored: '已评分' }[s] || s
}

function statusSeverity(s) {
  return { draft: 'secondary', submitted: 'warning', scored: 'success' }[s] || 'info'
}

function scoreLevel(ratio) {
  if (ratio >= 0.9) return 'excellent'
  if (ratio >= 0.7) return 'good'
  if (ratio >= 0.5) return 'fair'
  return 'poor'
}

async function loadReport() {
  loading.value = true
  try {
    const res = await reportAPI.get(route.params.id)
    if (!res || !res.data) return
    report.value = res.data
    // 周报加载完成后拉取该员工该周的一周小结截图
    loadSummary()
  } catch (e) {
    console.error('[ReportDetail] 加载失败:', e)
  } finally {
    loading.value = false
  }
}

/** 加载该员工该周的一周小结元数据与截图（blob → objectURL） */
async function loadSummary() {
  const { author_name, week_start } = report.value
  if (!author_name || !week_start) return
  summaryLoading.value = true
  try {
    const res = await weeklySummaryAPI.getByWeek(author_name, week_start)
    const summary = res?.data?.summary
    if (!summary || !summary.has_image) return

    const imgRes = await weeklySummaryAPI.getImage(summary.id)
    if (!imgRes || !imgRes.data) return
    // 释放旧的 objectURL，避免内存泄漏
    if (summaryImageUrl.value) URL.revokeObjectURL(summaryImageUrl.value)
    summaryImageUrl.value = URL.createObjectURL(imgRes.data)
    summaryInfo.value = summary
  } catch (e) {
    // 静默失败：小结缺失不影响周报详情展示
    console.warn('[ReportDetail] 一周小结加载失败:', e?.response?.status === 404 ? '本周无小结' : e)
  } finally {
    summaryLoading.value = false
  }
}

onMounted(loadReport)

onUnmounted(() => {
  if (summaryImageUrl.value) URL.revokeObjectURL(summaryImageUrl.value)
})
</script>

<style scoped>
/* ========== 头部 ========== */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--spacing-lg);
  padding: var(--spacing-lg) var(--spacing-xl);
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  margin-bottom: var(--spacing-xl);
  box-shadow: var(--shadow-sm);
}

.page-header h1 {
  font-size: var(--text-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-xs) 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex: 1;
  min-width: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  flex-shrink: 0;
}

.page-subtitle {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.6;
}

.loading-state {
  text-align: center;
  padding: 60px;
  color: var(--text-muted);
}

/* ========== 布局 ========== */
.detail-layout {
  display: grid;
  grid-template-columns: 1fr 380px;
  gap: var(--spacing-lg);
  align-items: start;
}

.content-panel,
.score-panel {
  min-width: 0;
}

.score-panel {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
  position: sticky;
  top: var(--spacing-lg);
}

/* ========== 卡片 ========== */
.detail-card :deep(.p-card-title) {
  color: var(--text-secondary) !important;
  font-size: var(--text-sm) !important;
}

/* ========== 内容 ========== */
.report-table-wrap {
  overflow-x: auto;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
}

.report-table thead th {
  background: var(--bg-dark);
  color: var(--text-secondary);
  font-weight: var(--font-semibold);
  padding: 10px 12px;
  text-align: left;
  border-bottom: 2px solid var(--border-light);
  white-space: nowrap;
}

.report-table tbody tr {
  border-bottom: 1px solid var(--border-light);
  transition: background 0.15s;
}

.report-table tbody tr:hover {
  background: var(--bg-dark);
}

.report-table td {
  padding: 10px 12px;
  vertical-align: top;
  color: var(--text-primary);
}

.item-num {
  color: var(--text-muted);
  font-weight: var(--font-semibold);
  text-align: center;
  font-size: var(--text-xs);
}

.item-title {
  font-weight: var(--font-semibold);
  color: var(--primary);
  margin-bottom: 4px;
  font-size: var(--text-sm);
}

.item-content {
  color: var(--text-secondary);
  line-height: 1.6;
  font-size: var(--text-xs);
}

.item-result {
  color: var(--text-secondary);
  font-size: var(--text-xs);
  line-height: 1.5;
}

/* ========== 维度评分 ========== */
.dim-scores {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.dim-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.dim-name {
  color: var(--text-primary);
  font-weight: var(--font-medium);
  font-size: var(--text-sm);
}

.dim-score {
  color: var(--primary);
  font-weight: var(--font-semibold);
  font-size: var(--text-sm);
}

.dim-bar {
  height: 8px;
  background: var(--bg-dark);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.dim-fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.6s ease;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  min-width: 0;
  position: relative;
}

.dim-bar-label {
  font-size: 11px;
  font-weight: var(--font-semibold);
  color: #fff;
  padding-right: 8px;
  white-space: nowrap;
  text-shadow: 0 1px 2px rgba(0,0,0,0.2);
}

.dim-fill.excellent { background: var(--success); }
.dim-fill.good { background: var(--info); }
.dim-fill.fair { background: var(--warning); }
.dim-fill.poor { background: var(--danger); }

.dim-comment {
  margin-top: 4px;
  font-size: var(--text-xs);
  color: var(--text-muted);
  line-height: 1.5;
}

.empty-hint {
  text-align: center;
  color: var(--text-muted);
  padding: var(--spacing-lg);
  font-size: var(--text-sm);
}

/* ========== 时间线 ========== */
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.timeline-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  padding-bottom: var(--spacing-lg);
  position: relative;
}

.timeline-item:last-child {
  padding-bottom: 0;
}

.timeline-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 10px;
  min-height: 100%;
}

.timeline-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
  z-index: 1;
}

.timeline-line {
  width: 2px;
  flex: 1;
  min-height: 20px;
  margin-top: 6px;
  background: var(--border-light);
  border-radius: 1px;
}

.timeline-item:last-child .timeline-line {
  display: none;
}

.timeline-dot.draft { background: var(--text-muted); }
.timeline-dot.submitted { background: var(--warning); }
.timeline-dot.scored { background: var(--success); }

.timeline-label {
  display: block;
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: var(--font-medium);
}

.timeline-time {
  display: block;
  color: var(--text-muted);
  font-size: var(--text-xs);
}

/* ========== 等级标签 ========== */
.score-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary);
  color: #fff;
  border-radius: var(--radius-md);
  font-weight: var(--font-bold);
  font-size: var(--text-lg);
  padding: 4px 14px;
  line-height: 1;
}

.score-badge-zero {
  background: linear-gradient(135deg, #ef4444, #c0392b) !important;
}

.grade-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  font-weight: var(--font-bold);
}

.grade-you {
  background: var(--warning-bg);
  color: var(--warning);
  border: 1px solid rgba(217, 119, 6, 0.2);
}

.grade-liang {
  background: var(--success-bg);
  color: var(--success);
  border: 1px solid rgba(22, 163, 74, 0.2);
}

.grade-yiban {
  background: var(--info-bg);
  color: var(--info);
  border: 1px solid rgba(37, 99, 235, 0.2);
}

.grade-cha {
  background: var(--danger-bg);
  color: var(--danger);
  border: 1px solid rgba(220, 38, 38, 0.2);
}

/* ========== 一周小结截图 ========== */
.summary-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm) var(--spacing-lg);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-md);
}

.summary-meta span::before {
  content: '•';
  margin-right: 4px;
  color: var(--primary);
}

.summary-thumb {
  position: relative;
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-light);
  cursor: zoom-in;
  background: #000;
}

.summary-thumb img {
  display: block;
  width: 100%;
  max-height: 320px;
  object-fit: contain;
  transition: opacity 0.15s;
}

.summary-thumb-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  font-size: var(--text-sm);
  opacity: 0;
  transition: opacity 0.2s;
}

.summary-thumb:hover .summary-thumb-mask {
  opacity: 1;
}

.summary-thumb:hover img {
  opacity: 0.75;
}

/* 放大预览 */
.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.preview-body {
  display: flex;
  justify-content: center;
  background: #0f1117;
  cursor: zoom-out;
  max-height: 78vh;
  overflow: auto;
}

.preview-body img {
  display: block;
  max-width: 100%;
  height: auto;
}

.preview-footer-hint {
  font-size: var(--text-xs);
  color: var(--text-muted);
  text-align: center;
}

/* ========== 响应式断点 ========== */

@media (max-width: 1024px) {
  .detail-layout {
    grid-template-columns: 1fr;
  }
  
  .score-panel {
    position: static;
  }
}

@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--spacing-md);
  }
  
  .header-right {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
