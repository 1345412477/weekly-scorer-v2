<template>
  <div class="wechat-upload page-content">

    <!-- 上传状态 -->
    <section class="status-panel">
      <div class="status-panel-header">
        <div class="status-panel-title">
          <i class="pi pi-calendar-check"></i>
          <span>数据上传状态</span>
        </div>
        <div class="status-panel-week">
          当前周：{{ currentWeekRange }}
          <button class="refresh-btn" @click="refreshStatus" title="刷新状态">
            <i class="pi pi-refresh"></i>
          </button>
        </div>
      </div>

      <div class="status-cards">
        <!-- 考勤状态 -->
        <div class="status-card" :class="{ 'has-data': attendanceStatus?.last_upload, 'no-data': !attendanceStatus?.last_upload, 'loading': statusLoading }">
          <div class="status-card-icon at-icon">
            <i class="pi pi-clock"></i>
          </div>
          <div class="status-card-body">
            <h3>考勤打卡数据</h3>
            <p class="status-card-state">
              <span v-if="statusLoading" class="loading-text">
                <i class="pi pi-spin pi-spinner"></i> 加载中...
              </span>
              <span v-else-if="attendanceStatus?.last_upload" class="ok">
                <i class="pi pi-check-circle"></i> 已上传
              </span>
              <span v-else class="warn">
                <i class="pi pi-exclamation-triangle"></i> 尚未上传
              </span>
            </p>
            <template v-if="attendanceStatus?.last_upload">
              <p class="status-card-info">
                覆盖周：{{ attendanceStatus.last_upload.week_start }} ~ {{ attendanceStatus.last_upload.week_end }}
              </p>
              <p class="status-card-info">
                覆盖员工：<strong>{{ attendanceStatus.employees_count ?? 0 }}</strong> 人，
                共 <strong>{{ attendanceStatus.records_count ?? 0 }}</strong> 条记录
              </p>
              <p class="status-card-meta">
                最近一次：{{ formatBeijingTimeShort(attendanceStatus.last_upload.uploaded_at) }} ·
                文件名：{{ attendanceStatus.last_upload.filename || '—' }}
                <span class="mode-tag" :class="attendanceStatus.last_upload.mode">
                  {{ attendanceStatus.last_upload.mode === 'replace' ? '覆盖上传' : '追加上传' }}
                </span>
              </p>
            </template>
          </div>
        </div>

        <!-- 聊天状态 -->
        <div class="status-card" :class="{ 'has-data': chatStatus?.last_upload, 'no-data': !chatStatus?.last_upload, 'loading': statusLoading }">
          <div class="status-card-icon chat-icon">
            <i class="pi pi-comments"></i>
          </div>
          <div class="status-card-body">
            <h3>聊天记录数据</h3>
            <p class="status-card-state">
              <span v-if="statusLoading" class="loading-text">
                <i class="pi pi-spin pi-spinner"></i> 加载中...
              </span>
              <span v-else-if="chatStatus?.last_upload" class="ok">
                <i class="pi pi-check-circle"></i> 已上传
              </span>
              <span v-else class="warn">
                <i class="pi pi-exclamation-triangle"></i> 尚未上传
              </span>
            </p>
            <template v-if="chatStatus?.last_upload">
              <p class="status-card-info">
                覆盖周：{{ chatStatus.last_upload.week_start }} ~ {{ chatStatus.last_upload.week_end }}
              </p>
              <p class="status-card-info">
                匹配员工：<strong>{{ chatStatus.employees_count ?? 0 }}</strong> 人 ·
                其他参与：<strong>{{ chatStatus.unmatched_employees_count ?? 0 }}</strong> 人 ·
                共 <strong>{{ chatStatus.last_upload?.record_count ?? chatStatus.records_count ?? 0 }}</strong> 条记录
              </p>
              <p class="status-card-meta">
                最近一次：{{ formatBeijingTimeShort(chatStatus.last_upload.uploaded_at) }} ·
                文件名：{{ chatStatus.last_upload.filename || '—' }}
                <span class="mode-tag" :class="chatStatus.last_upload.mode">
                  {{ chatStatus.last_upload.mode === 'replace' ? '覆盖上传' : '追加上传' }}
                </span>
              </p>
            </template>
          </div>
        </div>
      </div>
    </section>

    <!-- 文件上传区 -->
    <div class="card-grid">
      <!-- 考勤打卡 -->
      <div class="upload-card">
        <div class="card-header">
          <div class="card-icon at-icon">
            <i class="pi pi-clock"></i>
          </div>
          <div>
            <h2>考勤打卡数据</h2>
            <p class="card-desc">上传企业微信「上下班打卡日报」导出的 Excel 文件</p>
          </div>
        </div>

        <div
          class="drop-zone"
          :class="{ 'drag-over': attendanceDragOver }"
          @dragover.prevent="attendanceDragOver = true"
          @dragleave.prevent="attendanceDragOver = false"
          @drop.prevent="onAttendanceDrop"
          @click="triggerAttendanceInput"
        >
          <input ref="attendanceInput" type="file" accept=".xlsx,.xlsm" style="display:none" @change="onAttendanceFileSelect" />
          <template v-if="!attendanceFile">
            <i class="pi pi-file-excel drop-icon"></i>
            <h3>点击或拖拽 Excel 到此处</h3>
            <p>支持 .xlsx / .xlsm</p>
          </template>
          <template v-else>
            <i class="pi pi-file-excel file-icon"></i>
            <div class="file-info">
              <span class="file-name">{{ attendanceFile.name }}</span>
              <span class="file-size">{{ formatFileSize(attendanceFile.size) }}</span>
            </div>
            <i v-if="!attendanceUploading" class="pi pi-times remove-icon" @click.stop="attendanceFile = null"></i>
          </template>
        </div>

        <div class="btn-row">
          <Button
            v-if="!attendanceStatus?.last_upload"
            label="上传考勤文件"
            icon="pi pi-upload"
            :loading="attendanceUploading"
            :disabled="!attendanceFile"
            @click="uploadAttendance('append')"
            class="submit-btn"
            severity="primary"
          />
          <Button
            v-else
            label="覆盖上传考勤文件"
            icon="pi pi-refresh"
            :loading="attendanceUploading"
            :disabled="!attendanceFile"
            @click="uploadAttendance('replace')"
            class="submit-btn"
            severity="primary"
          />
          <Button
            label="取消上传"
            icon="pi pi-trash"
            :disabled="!attendanceStatus?.last_upload"
            :loading="attendanceCancelling"
            @click="cancelAttendance"
            class="submit-btn cancel-btn"
            severity="danger"
            outlined
          />
        </div>
        <p class="btn-hint">
          <template v-if="attendanceStatus?.last_upload">
            <i class="pi pi-info-circle"></i> 考勤数据已上传。如需修改请重新上传文件覆盖，如需清除请点击"取消上传"。
          </template>
          <template v-else>
            <i class="pi pi-info-circle"></i> 选择考勤 Excel 文件并点击"上传考勤文件"即可。
          </template>
        </p>

        <div v-if="attendanceResult" class="result-box" :class="attendanceResult.mode === 'replace' ? 'replace' : 'append'">
          <div><strong>{{ attendanceResult.message }}</strong></div>
          <div>覆盖周：{{ attendanceResult.week_start }} ~ {{ attendanceResult.week_end }}</div>
          <div>识别记录：{{ attendanceResult.total_records ?? '—' }} 条</div>
          <div>匹配员工：{{ attendanceResult.employees_matched ?? 0 }} 人</div>
          <div v-if="attendanceResult.mode === 'replace'" class="replace-info">
            已清理旧数据：{{ attendanceResult.replaced_old_count ?? 0 }} 条
          </div>
          <div v-if="attendanceResult.employees_unmatched?.length" class="unmatched">
            未匹配：{{ attendanceResult.employees_unmatched.join('、') }}
          </div>
        </div>
      </div>

      <!-- 聊天记录 -->
      <div class="upload-card">
        <div class="card-header">
          <div class="card-icon chat-icon">
            <i class="pi pi-comments"></i>
          </div>
          <div>
            <h2>聊天记录数据</h2>
            <p class="card-desc">上传企业微信聊天记录导出的 Excel 文件</p>
          </div>
        </div>

        <div
          class="drop-zone"
          :class="{ 'drag-over': chatDragOver }"
          @dragover.prevent="chatDragOver = true"
          @dragleave.prevent="chatDragOver = false"
          @drop.prevent="onChatDrop"
          @click="triggerChatInput"
        >
          <input ref="chatInput" type="file" accept=".xlsx,.xlsm" style="display:none" @change="onChatFileSelect" />
          <template v-if="!chatFile">
            <i class="pi pi-file-excel drop-icon"></i>
            <h3>点击或拖拽 Excel 到此处</h3>
            <p>支持 .xlsx / .xlsm</p>
          </template>
          <template v-else>
            <i class="pi pi-file-excel file-icon"></i>
            <div class="file-info">
              <span class="file-name">{{ chatFile.name }}</span>
              <span class="file-size">{{ formatFileSize(chatFile.size) }}</span>
            </div>
            <i v-if="!chatUploading" class="pi pi-times remove-icon" @click.stop="chatFile = null"></i>
          </template>
        </div>

        <div class="btn-row">
          <Button
            v-if="!chatStatus?.last_upload"
            label="上传聊天记录文件"
            icon="pi pi-upload"
            :loading="chatUploading"
            :disabled="!chatFile"
            @click="uploadChat('append')"
            class="submit-btn"
            severity="primary"
          />
          <Button
            v-else
            label="覆盖上传聊天记录"
            icon="pi pi-refresh"
            :loading="chatUploading"
            :disabled="!chatFile"
            @click="uploadChat('replace')"
            class="submit-btn"
            severity="primary"
          />
          <Button
            label="取消上传"
            icon="pi pi-trash"
            :disabled="!chatStatus?.last_upload"
            :loading="chatCancelling"
            @click="cancelChat"
            class="submit-btn cancel-btn"
            severity="danger"
            outlined
          />
        </div>
        <p class="btn-hint">
          <template v-if="chatStatus?.last_upload">
            <i class="pi pi-info-circle"></i> 聊天记录已上传。如需修改请重新上传文件覆盖，如需清除请点击"取消上传"。
          </template>
          <template v-else>
            <i class="pi pi-info-circle"></i> 选择聊天记录 Excel 文件并点击"上传聊天记录文件"即可。
          </template>
        </p>

        <div v-if="chatResult" class="result-box" :class="chatResult.mode === 'replace' ? 'replace' : 'append'">
          <div><strong>{{ chatResult.message }}</strong></div>
          <div>覆盖周：{{ chatResult.week_start }} ~ {{ chatResult.week_end }}</div>
          <div>识别记录：{{ chatResult.total_records ?? '—' }} 条
            <span v-if="chatResult.unmatched_records != null && chatResult.unmatched_records > 0" class="subtle">
              （其中 {{ chatResult.unmatched_records }} 条属于非员工）
            </span>
          </div>
          <div>匹配员工：{{ chatResult.employees_matched ?? 0 }} 人
            <span v-if="chatResult.employees_unmatched_count > 0" class="subtle">
              · 其他参与：{{ chatResult.employees_unmatched_count }} 人
            </span>
          </div>
          <div v-if="chatResult.mode === 'replace'" class="replace-info">
            已清理旧数据：{{ chatResult.replaced_old_count ?? 0 }} 条
          </div>
          <div v-if="chatResult.employees_unmatched?.length" class="unmatched">
            其他参与者（不参与评分）：{{ chatResult.employees_unmatched.join('、') }}
          </div>
        </div>
      </div>
    </div>

    <!-- 重新计算按钮（非本周数据上传后显示） -->
    <div v-if="showRecalculateBtn" class="recalculate-section">
      <div class="recalculate-info">
        <i class="pi pi-info-circle"></i>
        <span>已上传非本周数据，如需更新评分请点击"重新计算"</span>
      </div>
      <Button
        label="重新计算该周评分"
        icon="pi pi-refresh"
        :loading="recalculating"
        @click="recalculate"
        severity="warn"
        class="recalculate-btn"
      />
    </div>

    <!-- 定时评分提示 -->
    <div class="scoring-hint">
      <i class="pi pi-calendar-clock"></i>
      <span>员工提交的周报会立即 AI 评分，无需手动触发。系统每天在配置时间自动聚合考勤分与沟通分。</span>
    </div>

    <!-- 错误弹窗 -->
    <Dialog v-model:visible="showError" :closable="true" header="错误提示" :style="{ width: '460px' }">
      <div class="error-text">{{ errorMessage }}</div>
      <template #footer>
        <Button label="我知道了" icon="pi pi-check" @click="showError = false" />
      </template>
    </Dialog>

    <!-- 非本周确认弹窗 -->
    <Dialog v-model:visible="showWeekConfirm" header="确认上传" modal :style="{ width: '460px' }">
      <div class="confirm-text">
        <p>您即将上传的数据属于 <strong>{{ pendingUploadWeek }}</strong>，不是本周数据。</p>
        <p>上传后如需更新评分，请点击"重新计算该周评分"按钮。</p>
        <p>是否继续上传？</p>
      </div>
      <template #footer>
        <Button label="取消" icon="pi pi-times" text @click="showWeekConfirm = false" />
        <Button label="继续上传" icon="pi pi-check" @click="confirmUpload" severity="primary" />
      </template>
    </Dialog>

    <!-- 重新计算结果弹窗 -->
    <Dialog v-model:visible="showRecalcResult" header="重新计算结果" modal :style="{ width: '460px' }">
      <div class="recalc-result-text">
        <p>{{ recalcResultMessage }}</p>
      </div>
      <template #footer>
        <Button label="确定" icon="pi pi-check" @click="showRecalcResult = false" />
      </template>
    </Dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import Button from 'primevue/button'
import Dialog from 'primevue/dialog'
import { attendanceAPI, chatAPI, aggregateAPI } from '../api'
import { useToast } from 'primevue/usetoast'
import { formatBeijingTimeShort, getBeijingNow } from '../utils/timeUtil.js'

const toast = useToast()

// 状态数据
const attendanceStatus = ref(null)
const chatStatus = ref(null)
const statusLoading = ref(false)

// 计算当前周的日期范围（周一~周日）
function getCurrentWeekRange() {
  const now = getBeijingNow()
  const day = now.getDay()
  const offset = day === 0 ? 6 : day - 1
  const monday = new Date(now)
  monday.setDate(now.getDate() - offset)
  const sunday = new Date(monday)
  sunday.setDate(monday.getDate() + 6)
  const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
  return `${fmt(monday)} ~ ${fmt(sunday)}`
}

const currentWeekRange = getCurrentWeekRange()

// 考勤上传
const attendanceInput = ref(null)
const attendanceFile = ref(null)
const attendanceDragOver = ref(false)
const attendanceUploading = ref(false)
const attendanceCancelling = ref(false)
const attendanceResult = ref(null)

// 聊天记录上传
const chatInput = ref(null)
const chatFile = ref(null)
const chatDragOver = ref(false)
const chatUploading = ref(false)
const chatCancelling = ref(false)
const chatResult = ref(null)

const showError = ref(false)
const errorMessage = ref('')

// 非本周确认
const showWeekConfirm = ref(false)
const pendingUploadType = ref('') // 'attendance' or 'chat'
const pendingUploadMode = ref('append')
const pendingUploadWeek = ref('')

// 重新计算
const showRecalculateBtn = computed(() => {
  const atNotCurrent = attendanceStatus.value?.last_upload && !attendanceStatus.value?.is_current_week
  const chatNotCurrent = chatStatus.value?.last_upload && !chatStatus.value?.is_current_week
  return atNotCurrent || chatNotCurrent
})
const recalculating = ref(false)
const showRecalcResult = ref(false)
const recalcResultMessage = ref('')

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

async function refreshStatus() {
  statusLoading.value = true
  try {
    const [atRes, chatRes] = await Promise.all([
      attendanceAPI.status(),
      chatAPI.status(),
    ])
    attendanceStatus.value = atRes.data
    chatStatus.value = chatRes.data
  } catch (e) {
    // 状态接口失败时静默处理
  } finally {
    statusLoading.value = false
  }
}

// ---------- 考勤 ----------
function triggerAttendanceInput() { attendanceInput.value?.click() }
function onAttendanceFileSelect(e) {
  const f = e.target.files?.[0]
  if (f) { attendanceFile.value = f; attendanceDragOver.value = false }
}
function onAttendanceDrop(e) {
  attendanceDragOver.value = false
  const f = e.dataTransfer.files?.[0]
  if (f) {
    if (/\.(xlsx|xlsm)$/i.test(f.name)) {
      attendanceFile.value = f
    } else {
      toast.add({ severity: 'warn', summary: '仅支持 .xlsx / .xlsm', life: 2500 })
    }
  }
}

async function uploadAttendance(mode) {
  if (!attendanceFile.value) return
  attendanceUploading.value = true
  try {
    const res = await attendanceAPI.upload(attendanceFile.value, mode)
    const weekStart = res.data.week_start
    const currentWeekStart = attendanceStatus.value?.current_week_start
    const isCurrentWeek = weekStart === currentWeekStart

    attendanceResult.value = {
      message: res.data.message || '上传成功',
      mode: res.data.mode || mode,
      week_start: weekStart,
      week_end: res.data.week_end,
      total_records: res.data.total_records ?? '—',
      employees_matched: res.data.employees_matched ?? 0,
      employees_unmatched: res.data.employees_unmatched ?? [],
      replaced_old_count: res.data.replaced_old_count ?? 0,
    }

    if (!isCurrentWeek) {
      // 非本周数据，弹窗提示
      pendingUploadWeek.value = `${weekStart} ~ ${res.data.week_end}`
      showWeekConfirm.value = true
    } else {
      toast.add({
        severity: 'success',
        summary: mode === 'replace' ? '考勤数据已覆盖' : '考勤数据上传成功',
        life: 3000,
      })
    }

    attendanceFile.value = null
    refreshStatus()
  } catch (e) {
    errorMessage.value = e.response?.data?.detail || '考勤数据上传失败，请检查文件格式'
    showError.value = true
  } finally {
    attendanceUploading.value = false
  }
}

async function cancelAttendance() {
  attendanceCancelling.value = true
  try {
    const res = await attendanceAPI.cancel()
    toast.add({
      severity: 'info',
      summary: `考勤上传已取消（共清除 ${res.data.deleted_records} 条记录）`,
      life: 3000,
    })
    attendanceResult.value = null
    attendanceFile.value = null
    refreshStatus()
  } catch (e) {
    errorMessage.value = e.response?.data?.detail || '取消考勤上传失败，请稍后重试'
    showError.value = true
  } finally {
    attendanceCancelling.value = false
  }
}

// ---------- 聊天记录 ----------
function triggerChatInput() { chatInput.value?.click() }
function onChatFileSelect(e) {
  const f = e.target.files?.[0]
  if (f) { chatFile.value = f; chatDragOver.value = false }
}
function onChatDrop(e) {
  chatDragOver.value = false
  const f = e.dataTransfer.files?.[0]
  if (f) {
    if (/\.(xlsx|xlsm)$/i.test(f.name)) {
      chatFile.value = f
    } else {
      toast.add({ severity: 'warn', summary: '仅支持 .xlsx / .xlsm', life: 2500 })
    }
  }
}

async function uploadChat(mode) {
  if (!chatFile.value) return
  chatUploading.value = true
  try {
    const res = await chatAPI.upload(chatFile.value, mode)
    const weekStart = res.data.week_start
    const currentWeekStart = chatStatus.value?.current_week_start
    const isCurrentWeek = weekStart === currentWeekStart

    chatResult.value = {
      message: res.data.message || '上传成功',
      mode: res.data.mode || mode,
      week_start: weekStart,
      week_end: res.data.week_end,
      total_records: res.data.total_records ?? '—',
      matched_records: res.data.matched_records ?? 0,
      unmatched_records: res.data.unmatched_records ?? 0,
      employees_matched: res.data.employees_matched ?? 0,
      employees_unmatched_count: res.data.employees_unmatched_count ?? 0,
      employees_unmatched: res.data.employees_unmatched ?? [],
      replaced_old_count: res.data.replaced_old_count ?? 0,
    }

    if (!isCurrentWeek) {
      // 非本周数据，弹窗提示
      pendingUploadWeek.value = `${weekStart} ~ ${res.data.week_end}`
      showWeekConfirm.value = true
    } else {
      toast.add({
        severity: 'success',
        summary: mode === 'replace' ? '聊天记录已覆盖' : '聊天记录上传成功',
        life: 3000,
      })
    }

    chatFile.value = null
    refreshStatus()
  } catch (e) {
    errorMessage.value = e.response?.data?.detail || '聊天记录上传失败，请检查文件格式'
    showError.value = true
  } finally {
    chatUploading.value = false
  }
}

async function cancelChat() {
  chatCancelling.value = true
  try {
    const res = await chatAPI.cancel()
    toast.add({
      severity: 'info',
      summary: `聊天记录上传已取消（共清除 ${res.data.deleted_records} 条记录）`,
      life: 3000,
    })
    chatResult.value = null
    chatFile.value = null
    refreshStatus()
  } catch (e) {
    errorMessage.value = e.response?.data?.detail || '取消聊天记录上传失败，请稍后重试'
    showError.value = true
  } finally {
    chatCancelling.value = false
  }
}

// ---------- 非本周确认 ----------
function confirmUpload() {
  // 数据已经上传完成，弹窗只是提示用户
  // 关闭弹窗并刷新状态
  showWeekConfirm.value = false
  refreshStatus()
  toast.add({
    severity: 'info',
    summary: '非本周数据已上传，如需更新评分请点击"重新计算该周评分"按钮',
    life: 5000,
  })
}

// ---------- 重新计算 ----------
async function recalculate() {
  // 获取需要重新计算的周（优先考勤，其次聊天）
  let weekStart = null
  if (attendanceStatus.value?.last_upload && !attendanceStatus.value?.is_current_week) {
    weekStart = attendanceStatus.value.last_upload.week_start
  } else if (chatStatus.value?.last_upload && !chatStatus.value?.is_current_week) {
    weekStart = chatStatus.value.last_upload.week_start
  }

  if (!weekStart) {
    toast.add({ severity: 'warn', summary: '没有需要重新计算的非本周数据', life: 3000 })
    return
  }

  recalculating.value = true
  try {
    const res = await aggregateAPI.recalculate(weekStart)
    recalcResultMessage.value = res.data.message || '重新计算完成'
    showRecalcResult.value = true
    toast.add({
      severity: 'success',
      summary: '重新计算完成',
      life: 3000,
    })
  } catch (e) {
    errorMessage.value = e.response?.data?.detail || '重新计算失败，请稍后重试'
    showError.value = true
  } finally {
    recalculating.value = false
  }
}

onMounted(() => {
  refreshStatus()
})
</script>

<style scoped>
.wechat-upload {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* ---- 上传状态 ---- */
.status-panel {
  background: #fff;
  border-radius: 14px;
  border: 1px solid #eef1f9;
  padding: 18px 22px;
  box-shadow: 0 2px 10px rgba(79, 107, 255, 0.04);
}

.status-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
  padding-bottom: 14px;
  border-bottom: 1px solid #eef1f9;
}

.status-panel-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 16px;
  font-weight: 700;
  color: #1e2335;
}

.status-panel-title .pi {
  color: #4f6bff;
  font-size: 20px;
}

.status-panel-week {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: #5a6481;
}

.refresh-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid #dde5ff;
  background: #f4f7ff;
  color: #4f6bff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.refresh-btn:hover {
  background: #4f6bff;
  color: #fff;
  border-color: #4f6bff;
}

.refresh-btn:active {
  transform: scale(0.95);
}

.status-cards {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.status-card {
  background: #f8faff;
  border-radius: 12px;
  border: 1px solid #e3e9fa;
  padding: 16px 18px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.2s ease;
}

.status-card.loading {
  opacity: 0.7;
}

.status-card.no-data {
  background: linear-gradient(135deg, #fffbea 0%, #fff 80%);
  border-color: #ffe0a3;
}

.status-card.has-data {
  background: linear-gradient(135deg, #f1fff6 0%, #fff 80%);
  border-color: #c8f2d9;
}

.status-card-icon {
  width: 46px;
  height: 46px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  color: #fff;
  flex-shrink: 0;
}
.at-icon { background: linear-gradient(135deg, #4f6bff, #6ed0ff); }
.chat-icon { background: linear-gradient(135deg, #16a875, #7be0a8); }

.status-card-body {
  flex: 1;
  min-width: 0;
}

.status-card h3 {
  margin: 0 0 4px;
  font-size: 15px;
  color: #1e2335;
  font-weight: 700;
}

.status-card-state {
  margin: 0 0 8px;
  font-size: 14px;
}

.status-card-state .ok {
  color: #16a875;
  font-size: 15px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-card-state .warn {
  color: #d97706;
  font-size: 15px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-card-state .loading-text {
  color: #6e7aa8;
  font-size: 14px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-card-info {
  margin: 0;
  font-size: 12px;
  color: #5a6481;
}

.status-card-meta {
  margin: 4px 0 0;
  font-size: 12px;
  color: #8a92a8;
  line-height: 1.5;
}

.mode-tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 8px;
  font-size: 11px;
  margin-left: 6px;
  font-weight: 600;
}
.mode-tag.append { background: #e6efff; color: #4f6bff; }
.mode-tag.replace { background: #fff3e6; color: #d97706; }

/* ---- 文件上传卡片 ---- */
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(420px, 1fr));
  gap: 20px;
}

.upload-card {
  background: #fff;
  border-radius: 14px;
  padding: 22px;
  border: 1px solid #eef1f9;
  display: flex;
  flex-direction: column;
  gap: 14px;
  box-shadow: 0 2px 10px rgba(79, 107, 255, 0.04);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 14px;
}

.card-icon {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #fff;
  flex-shrink: 0;
}

.upload-card h2 {
  font-size: 15px;
  color: #1e2335;
  margin: 0;
  font-weight: 700;
}

.card-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #7a819a;
}

.drop-zone {
  border: 2px dashed #d8e0f4;
  border-radius: 12px;
  padding: 26px 20px;
  text-align: center;
  cursor: pointer;
  background: #f8faff;
  transition: all 0.2s ease;
}
.drop-zone.drag-over {
  border-color: #4f6bff;
  background: rgba(79, 107, 255, 0.06);
}

.drop-icon {
  font-size: 40px;
  color: #4f6bff;
  margin-bottom: 10px;
}

.drop-zone h3 {
  font-size: 15px;
  color: #1e2335;
  margin: 0 0 6px;
  font-weight: 600;
}

.drop-zone p {
  margin: 0;
  font-size: 12px;
  color: #7a819a;
}

.file-icon { font-size: 36px; color: #16a875; }

.file-info {
  margin: 8px 0 0;
}

.file-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e2335;
  word-break: break-all;
  display: block;
}

.file-size { font-size: 12px; color: #7a819a; }

.remove-icon {
  margin-top: 10px;
  color: #a6adc4;
  font-size: 16px;
  cursor: pointer;
}

/* ---- 按钮区 ---- */
.btn-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.btn-row .submit-btn {
  flex: 1;
  min-width: 160px;
  justify-content: center;
}

.btn-row .cancel-btn {
  flex: 0 0 auto;
  min-width: 140px;
}

.btn-hint {
  margin: 0;
  padding: 10px 12px;
  background: #f8faff;
  border-radius: 8px;
  font-size: 12px;
  color: #5a6481;
  line-height: 1.5;
}

.btn-hint .pi {
  color: #4f6bff;
  margin-right: 4px;
}

/* ---- 结果区 ---- */
.result-box {
  padding: 14px 16px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.8;
  color: #3a4059;
}

.result-box.append {
  background: rgba(22, 168, 117, 0.08);
  border: 1px solid rgba(22, 168, 117, 0.2);
  color: #0f7e54;
}

.result-box.replace {
  background: rgba(217, 119, 6, 0.08);
  border: 1px solid rgba(217, 119, 6, 0.25);
  color: #924a07;
}

.replace-info {
  font-weight: 600;
}

.unmatched { color: #c6572c; }

/* ---- 重新计算区域 ---- */
.recalculate-section {
  background: linear-gradient(135deg, #fff8f0 0%, #fff 80%);
  border: 1px solid #ffd6a5;
  border-radius: 12px;
  padding: 16px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.recalculate-info {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  color: #d97706;
}

.recalculate-info .pi {
  font-size: 18px;
}

.recalculate-btn {
  flex-shrink: 0;
}

/* ---- 定时评分提示 ---- */
.scoring-hint {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: linear-gradient(135deg, #f4f7ff 0%, #fff 80%);
  border: 1px solid #dde5ff;
  border-radius: 12px;
  font-size: 13px;
  color: #3a4059;
  line-height: 1.6;
}
.scoring-hint .pi {
  font-size: 18px;
  color: #4f6bff;
  flex-shrink: 0;
}

/* ---- 错误弹窗 ---- */
.error-text {
  color: #3a4059;
  font-size: 14px;
  line-height: 1.6;
}

.confirm-text {
  color: #3a4059;
  font-size: 14px;
  line-height: 1.8;
}

.confirm-text p {
  margin: 0 0 12px 0;
}

.confirm-text p:last-child {
  margin-bottom: 0;
}

.recalc-result-text {
  color: #3a4059;
  font-size: 14px;
  line-height: 1.6;
}

/* ---- 响应式 ---- */
@media (max-width: 960px) {
  .status-cards { grid-template-columns: 1fr; }
  .status-panel-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
}

@media (max-width: 640px) {
  .card-grid { grid-template-columns: 1fr; }
  .upload-card { padding: 18px; }
  .btn-row { flex-direction: column; }
  .btn-row .submit-btn { width: 100%; }
  .recalculate-section {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
