<template>
  <div class="config-page page-content">
    <!-- AI 模型状态 -->
    <section class="status-card">
      <div class="status-info">
        <div class="status-icon"><i class="pi pi-bolt"></i></div>
        <div class="status-text">
          <span class="status-eyebrow">AI 引擎状态</span>
          <span class="status-provider">{{ providerName }}</span>
          <span class="status-model">{{ aiStatus.model || '模型加载中...' }}</span>
        </div>
      </div>
      <div class="status-right">
        <Tag v-if="aiStatus.success === true" value="已连接" severity="success" class="status-tag" />
        <Tag v-else-if="aiStatus.success === false" value="连接失败" severity="danger" class="status-tag" />
        <Tag v-else value="检测中..." severity="warn" class="status-tag" />
        <Button label="刷新" icon="pi pi-refresh" text size="small" @click="checkAiStatus" />
      </div>
    </section>

    <!-- 保存操作栏 -->
    <div class="action-bar">
      <span class="action-hint">修改后请保存配置才能生效</span>
      <div class="action-buttons">
        <Button label="重置默认" severity="secondary" outlined @click="resetConfig" />
        <Button label="保存配置" icon="pi pi-save" @click="saveConfig" :loading="saving" />
      </div>
    </div>

    <!-- 两栏布局 -->
    <div class="grid-wrap">
      <!-- 左列：评分维度 -->
      <section class="panel-card">
        <header class="panel-header">
          <div>
            <span class="panel-eyebrow">核心配置</span>
            <h3>评分维度</h3>
          </div>
          <Button label="添加维度" icon="pi pi-plus" text size="small" @click="addDim" />
        </header>

        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th style="width: 22%">维度名称</th>
                <th style="width: 12%">最高分</th>
                <th style="width: 12%">最低分</th>
                <th style="width: 12%">满分</th>
                <th>考核内容</th>
                <th style="width: 48px"></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(dim, idx) in dimensions" :key="idx">
                <td>
                  <InputText v-model="dim.name" placeholder="请输入" class="cell-input" />
                </td>
                <td>
                  <InputNumber v-model="dim.highest_score" :min="0" :max="dim.full_score || 100" size="small" buttonLayout="horizontal" />
                </td>
                <td>
                  <InputNumber v-model="dim.lowest_score" :min="0" :max="dim.full_score || 100" size="small" buttonLayout="horizontal" />
                </td>
                <td>
                  <InputNumber v-model="dim.full_score" :min="1" :max="100" size="small" buttonLayout="horizontal" />
                </td>
                <td>
                  <InputText v-model="dim.evaluation_content" placeholder="描述考核要点" class="cell-input" />
                </td>
                <td class="action-cell">
                  <Button icon="pi pi-trash" severity="danger" text rounded size="small" @click="removeDim(idx)" :disabled="dimensions.length <= 1" />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="totals-row">
          <span class="totals-label">总满分</span>
          <span class="totals-value">{{ totalFullScore }} 分</span>
        </div>
      </section>

      <!-- 右列：等级阈值 + Prompt -->
      <section class="panel-card">
        <header class="panel-header">
          <div>
            <span class="panel-eyebrow">评级规则</span>
            <h3>等级阈值（{{ totalFullScore }}分制）</h3>
          </div>
        </header>

        <div class="threshold-grid">
          <div v-for="(val, key) in gradeThresholds" :key="key" :class="['threshold-item', 't-' + gradeIndex(key)]">
            <div class="th-grade">
              <span :class="['th-tag', 'g-' + gradeIndex(key)]">{{ key }}</span>
            </div>
            <div class="th-input">
              <span class="th-label">得分 ≥</span>
              <InputNumber v-model="gradeThresholds[key]" :min="0" :max="totalFullScore" size="small" buttonLayout="horizontal" />
            </div>
          </div>
        </div>

        <div class="section-divider"></div>

        <header class="panel-header">
          <div>
            <span class="panel-eyebrow">AI 提示词</span>
            <h3>评分 Prompt 模板</h3>
          </div>
          <Button label="生成默认" icon="pi pi-magic" text size="small" @click="generateDefaultPrompt" />
        </header>

        <Textarea v-model="promptTemplate" rows="8" class="prompt-area" placeholder="留空则使用系统默认提示词..." autoResize />
        <div class="prompt-vars">
          <Tag value="{content}" severity="info" />
          <span class="var-desc">周报内容</span>
          <Tag value="{dimensions}" severity="info" />
          <span class="var-desc">评分维度</span>
        </div>
      </section>
    </div>

    <!-- 测试评分 -->
    <section class="panel-card test-card">
      <header class="panel-header">
        <div>
          <span class="panel-eyebrow">功能验证</span>
          <h3>测试评分</h3>
          <p class="panel-desc">上传周报文件快速测试配置是否正确</p>
        </div>
      </header>

      <div class="test-layout">
        <div class="upload-box" @dragover.prevent @drop.prevent="onTestDrop" @click="triggerTestFileInput">
          <input ref="testFileInput" type="file" accept=".xlsx,.xls,.docx,.pdf" style="display:none" @change="onTestFileSelect" />
          <div v-if="!testFile" class="upload-empty">
            <i class="pi pi-cloud-upload upload-ic"></i>
            <span class="upload-title">点击或拖拽上传周报文件</span>
            <span class="upload-hint">支持 .xlsx / .xls / .docx / .pdf</span>
          </div>
          <div v-else class="upload-filled">
            <i class="pi pi-file-excel file-ic"></i>
            <div class="file-meta">
              <span class="file-name">{{ testFile.name }}</span>
              <span class="file-size">{{ formatFileSize(testFile.size) }}</span>
            </div>
            <Button icon="pi pi-times" text rounded severity="danger" @click.stop="clearTestFile" />
          </div>
        </div>

        <div class="test-actions">
          <Button label="清空" severity="secondary" outlined @click="resetTest" :disabled="!testFile && !testResult" />
          <Button label="上传并评分" icon="pi pi-play" @click="runTest" :loading="testing" :disabled="!testFile" />
        </div>
      </div>

      <div v-if="testResult" class="test-result-box">
        <div class="result-head">
          <div class="result-score-wrap">
            <span class="result-score">{{ testResult.total_score }}</span>
            <span class="result-sub">综合评分</span>
          </div>
          <Tag v-if="testResult.grade" :value="testResult.grade" :severity="gradeSeverity(testResult.grade)" class="grade-pill" />
        </div>

        <div v-if="testResult.dimension_scores?.length" class="result-dims">
          <div v-for="(d, idx) in testResult.dimension_scores" :key="idx" class="rd-row">
            <span class="rd-name">{{ d.name }}</span>
            <div class="rd-bar-bg"><div class="rd-bar" :style="{ width: Math.min(100, ((d.score || 0) / (d.max || 100)) * 100) + '%' }"></div></div>
            <span class="rd-val">{{ d.score }}/{{ d.max }}</span>
          </div>
        </div>

        <div v-if="testResult.ai_comment" class="result-comment">
          <span class="rc-label"><i class="pi pi-comments"></i> AI 评语</span>
          <p>{{ testResult.ai_comment }}</p>
        </div>

        <div v-if="testResult.ai_suggestion" class="result-suggestion">
          <span class="rc-label"><i class="pi pi-lightbulb"></i> 改进建议</span>
          <p>{{ testResult.ai_suggestion }}</p>
        </div>
      </div>
    </section>

    <!-- 人员与部门管理 -->
    <div class="grid-wrap">
      <section class="panel-card">
        <header class="panel-header">
          <div>
            <span class="panel-eyebrow">组织管理</span>
            <h3>部门管理</h3>
          </div>
        </header>

        <div class="add-row">
          <InputText v-model="newDeptName" placeholder="部门名称" class="grow-input" />
          <InputText v-model="newDeptDesc" placeholder="部门描述（可选）" class="grow-input" />
          <Button label="添加" icon="pi pi-plus" @click="addDepartment" :disabled="!newDeptName.trim()" />
        </div>

        <div class="item-list">
          <div v-if="!departments.length" class="empty-line">暂无部门数据</div>
          <div v-for="dept in departments" :key="dept.id" class="item-row">
            <template v-if="editingDeptId === dept.id">
              <InputText v-model="editingDeptName" placeholder="部门名称" class="grow-input" />
              <InputText v-model="editingDeptDesc" placeholder="部门描述" class="grow-input" />
              <Button icon="pi pi-check" @click="saveEditDepartment(dept.id)" size="small" :disabled="!editingDeptName.trim()" />
              <Button icon="pi pi-times" severity="secondary" text @click="cancelEditDepartment" size="small" />
            </template>
            <template v-else>
              <div class="item-info">
                <span class="item-title">{{ dept.name }}</span>
                <span class="item-sub">{{ dept.description || '无描述' }}</span>
              </div>
              <div class="item-actions">
                <Button icon="pi pi-pencil" text rounded size="small" @click="startEditDepartment(dept)" />
                <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="deleteDepartment(dept.id)" />
              </div>
            </template>
          </div>
        </div>
      </section>

      <section class="panel-card">
        <header class="panel-header">
          <div>
            <span class="panel-eyebrow">组织管理</span>
            <h3>人员管理</h3>
          </div>
        </header>

        <div class="add-row">
          <InputText v-model="newPersonName" placeholder="姓名" class="grow-input" />
          <Dropdown v-model="newPersonDept" :options="departments" optionLabel="name" placeholder="选择部门" showClear class="grow-input" />
          <InputText v-model="newPersonPosition" placeholder="职位（可选）" class="grow-input" />
          <Button label="添加" icon="pi pi-plus" @click="addPerson" :disabled="!newPersonName.trim()" />
        </div>

        <div class="item-list">
          <div v-if="!persons.length" class="empty-line">暂无人员数据</div>
          <div v-for="person in persons" :key="person.id" class="item-row">
            <template v-if="editingPersonId === person.id">
              <InputText v-model="editingPersonName" placeholder="姓名" class="grow-input" />
              <Dropdown v-model="editingPersonDept" :options="departments" optionLabel="name" placeholder="部门" showClear class="grow-input" />
              <InputText v-model="editingPersonPosition" placeholder="职位" class="grow-input" />
              <Button icon="pi pi-check" @click="saveEditPerson(person.id)" size="small" :disabled="!editingPersonName.trim()" />
              <Button icon="pi pi-times" severity="secondary" text @click="cancelEditPerson" size="small" />
            </template>
            <template v-else>
              <div class="item-info">
                <span class="item-title">{{ person.name }}</span>
                <span class="item-sub">{{ person.department_name || '未分配部门' }}{{ person.position ? ' · ' + person.position : '' }}</span>
              </div>
              <div class="item-actions">
                <Button icon="pi pi-pencil" text rounded size="small" @click="startEditPerson(person)" />
                <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="deletePerson(person.id)" />
              </div>
            </template>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { configAPI, departmentAPI, personAPI, reportAPI } from '../api'
import { useDataRefresh, getConfigEvents } from '../composables/useDataRefresh'
import { useDataOperation } from '../composables/useDataOperation'
import { DataEventType, emitDataChanged } from '../utils/dataEvents'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Dropdown from 'primevue/dropdown'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const { execute } = useDataOperation()

const saving = ref(false)
const testing = ref(false)
const aiStatus = ref({ provider: '', model: '', success: null })
const dimensions = ref([
  { name: '工作反馈深度', full_score: 14, highest_score: null, lowest_score: null, evaluation_content: '问题发现+分析+解决方案' },
  { name: '进度节点明确', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '项目是否有明确进度/节点' },
  { name: '计划可行性', full_score: 10, highest_score: null, lowest_score: null, evaluation_content: '下周计划是否具体可执行' },
  { name: '工作连续性', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '是否承接上周计划且有闭环' },
])
const gradeThresholds = ref({ '优': 45, '良': 38, '一般': 33, '差': 28 })
const promptTemplate = ref('')
const testFile = ref(null)
const testFileInput = ref(null)
const testResult = ref(null)

const departments = ref([])
const persons = ref([])
const newDeptName = ref('')
const newDeptDesc = ref('')
const newPersonName = ref('')
const newPersonDept = ref(null)
const newPersonPosition = ref('')

const editingDeptId = ref(null)
const editingDeptName = ref('')
const editingDeptDesc = ref('')
const editingPersonId = ref(null)
const editingPersonName = ref('')
const editingPersonDept = ref(null)
const editingPersonPosition = ref('')

const totalFullScore = computed(() => dimensions.value.reduce((s, d) => s + (d.full_score || 0), 0))

const providerName = computed(() => {
  const p = aiStatus.value.provider
  if (p === 'mimo') return '小米 MiMo'
  if (p === 'ark') return '豆包 (火山引擎)'
  if (p === 'deepseek') return 'DeepSeek'
  return p || '待检测'
})

function gradeIndex(g) {
  return { '优': 0, '良': 1, '一般': 2, '差': 3 }[g] ?? 0
}

function gradeSeverity(g) {
  if (g === '优') return 'success'
  if (g === '良') return 'info'
  if (g === '一般') return 'warn'
  return 'danger'
}

function addDim() {
  dimensions.value.push({ name: '', full_score: 10, highest_score: null, lowest_score: null, evaluation_content: '' })
}

function removeDim(idx) {
  dimensions.value.splice(idx, 1)
}

function resetConfig() {
  dimensions.value = [
    { name: '工作反馈深度', full_score: 14, highest_score: null, lowest_score: null, evaluation_content: '问题发现+分析+解决方案' },
    { name: '进度节点明确', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '项目是否有明确进度/节点' },
    { name: '计划可行性', full_score: 10, highest_score: null, lowest_score: null, evaluation_content: '下周计划是否具体可执行' },
    { name: '工作连续性', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '是否承接上周计划且有闭环' },
  ]
  gradeThresholds.value = { '优': 45, '良': 38, '一般': 33, '差': 28 }
  promptTemplate.value = ''
  toast.add({ severity: 'info', summary: '已重置为默认配置', life: 2000 })
}

async function loadConfig() {
  try {
    const res = await configAPI.get()
    const d = res.data
    if (d.dimensions?.length) dimensions.value = d.dimensions
    if (d.grade_thresholds) gradeThresholds.value = d.grade_thresholds
    if (d.prompt_template) promptTemplate.value = d.prompt_template
  } catch (e) { console.error('[Config] 加载失败:', e) }
}

async function saveConfig() {
  for (const dim of dimensions.value) {
    if (!dim.name?.trim()) {
      toast.add({ severity: 'warn', summary: '请填写所有维度名称', life: 2000 })
      return
    }
    if (!dim.full_score || dim.full_score <= 0) {
      toast.add({ severity: 'warn', summary: `维度 "${dim.name}" 的满分必须大于 0`, life: 2000 })
      return
    }
  }
  saving.value = true
  try {
    await configAPI.save({
      dimensions: dimensions.value,
      grade_thresholds: gradeThresholds.value,
      prompt_template: promptTemplate.value,
    })
    emitDataChanged(DataEventType.CONFIG_CHANGED, { source: 'saveConfig' })
    toast.add({ severity: 'success', summary: '配置保存成功', life: 2000 })
  } catch (e) {
    toast.add({ severity: 'error', summary: '保存失败', life: 2000 })
  } finally {
    saving.value = false
  }
}

function triggerTestFileInput() {
  testFileInput.value?.click()
}

function onTestFileSelect(e) {
  const file = e.target.files[0]
  if (file) testFile.value = file
}

function onTestDrop(e) {
  const file = e.dataTransfer.files[0]
  if (file) testFile.value = file
}

function clearTestFile() {
  testFile.value = null
  if (testFileInput.value) testFileInput.value.value = ''
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function generateDefaultPrompt() {
  const dims = dimensions.value.map((d, i) => {
    let line = `  ${i + 1}. ${d.name}（满分${d.full_score}分`
    if (d.highest_score != null) line += `，最高分${d.highest_score}分`
    if (d.lowest_score != null) line += `，最低分${d.lowest_score}分`
    line += `，考核内容：${d.evaluation_content || '待补充'}）`
    return line
  }).join('\n')

  const gradeText = Object.entries(gradeThresholds.value)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `${k}(≥${v})`)
    .join('、')

  promptTemplate.value = `# 周报评分系统提示词\n\n## 角色设定\n你是一位专业、客观的工作报告评审专家。请根据以下评分维度对员工周报进行综合评估。\n\n## 评分原则\n1. 客观公正：基于周报内容进行评价，避免主观臆断\n2. 鼓励量化：对有数据支撑、可量化成果的内容给予更高评价\n3. 关注闭环：重视"计划→执行→结果"的完整闭环\n4. 提供建设性：评语和建议应具体、可操作\n\n## 评分维度\n${dims || '（请先配置评分维度）'}\n\n## 评分标准\n- 每个维度独立打分，不超过该维度满分\n- 综合评分 = 各维度分数直接相加（${totalFullScore.value}分制）\n- 等级划分：${gradeText}\n\n## 输出要求\n请以 JSON 格式返回评分结果，包含：\n- dimension_scores: 各维度得分及评语（含name、score、max、comment）\n- total_score: 综合得分\n- grade: 等级（优/良/一般/差）\n- comment: 总体评语（100字以内）\n- suggestion: 改进建议（具体可执行）\n\n## 周报内容\n{content}`

  toast.add({ severity: 'success', summary: '已生成默认模板', life: 2000 })
}

async function runTest() {
  if (!testFile.value) return
  testing.value = true
  testResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', testFile.value)
    const uploadRes = await reportAPI.upload(formData)
    const uploadData = uploadRes.data
    if (uploadData.report_id) {
      const detailRes = await reportAPI.get(uploadData.report_id)
      const detail = detailRes.data
      testResult.value = {
        total_score: detail.total_score || uploadData.total_score,
        grade: detail.grade || uploadData.grade,
        dimension_scores: detail.dimension_scores || [],
        ai_comment: detail.ai_comment || '',
        ai_suggestion: detail.ai_suggestion || '',
      }
      toast.add({ severity: 'success', summary: '评分完成', life: 2000 })
      try { await reportAPI.delete(uploadData.report_id) } catch { /* 清理失败不阻塞 */ }
    } else {
      toast.add({ severity: 'warn', summary: uploadData.message || '上传成功但未获取评分', life: 3000 })
    }
  } catch (e) {
    const msg = e.response?.data?.detail || '测试失败'
    toast.add({ severity: 'error', summary: msg, life: 3000 })
  } finally {
    testing.value = false
  }
}

function resetTest() {
  testFile.value = null
  testResult.value = null
  if (testFileInput.value) testFileInput.value.value = ''
}

async function loadDepartments() {
  try {
    const res = await departmentAPI.list()
    departments.value = res.data || []
  } catch (e) { console.error('[Config] 加载部门失败:', e) }
}

async function loadPersons() {
  try {
    const res = await personAPI.list()
    persons.value = res.data || []
  } catch (e) { console.error('[Config] 加载人员失败:', e) }
}

async function loadManagementData() {
  await Promise.all([loadDepartments(), loadPersons()])
}

async function addDepartment() {
  if (!newDeptName.value.trim()) return
  const { success } = await execute(
    () => departmentAPI.create({ name: newDeptName.value, description: newDeptDesc.value }),
    { name: '添加部门', eventTypes: DataEventType.DEPARTMENTS_CHANGED, successMsg: '部门添加成功' }
  )
  if (success) {
    newDeptName.value = ''
    newDeptDesc.value = ''
    loadDepartments()
  }
}

async function deleteDepartment(id) {
  const { success } = await execute(
    () => departmentAPI.delete(id),
    { name: '删除部门', eventTypes: DataEventType.DEPARTMENTS_CHANGED, successMsg: '部门已删除' }
  )
  if (success) loadDepartments()
}

function startEditDepartment(dept) {
  editingDeptId.value = dept.id
  editingDeptName.value = dept.name
  editingDeptDesc.value = dept.description || ''
}

function cancelEditDepartment() {
  editingDeptId.value = null
  editingDeptName.value = ''
  editingDeptDesc.value = ''
}

async function saveEditDepartment(id) {
  if (!editingDeptName.value.trim()) {
    toast.add({ severity: 'warn', summary: '部门名称不能为空', life: 2000 })
    return
  }
  const { success } = await execute(
    () => departmentAPI.update(id, { name: editingDeptName.value.trim(), description: editingDeptDesc.value.trim() }),
    { name: '更新部门', eventTypes: DataEventType.DEPARTMENTS_CHANGED, successMsg: '部门更新成功' }
  )
  if (success) {
    cancelEditDepartment()
    loadDepartments()
  }
}

async function addPerson() {
  if (!newPersonName.value.trim()) return
  const data = { name: newPersonName.value, position: newPersonPosition.value }
  if (newPersonDept.value) {
    data.department_id = newPersonDept.value.id
    data.department_name = newPersonDept.value.name
  }
  const { success } = await execute(
    () => personAPI.create(data),
    { name: '添加人员', eventTypes: DataEventType.PERSONS_CHANGED, successMsg: '人员添加成功' }
  )
  if (success) {
    newPersonName.value = ''
    newPersonDept.value = null
    newPersonPosition.value = ''
    loadPersons()
  }
}

async function deletePerson(id) {
  const { success } = await execute(
    () => personAPI.delete(id),
    { name: '删除人员', eventTypes: DataEventType.PERSONS_CHANGED, successMsg: '人员已删除' }
  )
  if (success) loadPersons()
}

function startEditPerson(person) {
  editingPersonId.value = person.id
  editingPersonName.value = person.name
  editingPersonPosition.value = person.position || ''
  editingPersonDept.value = person.department_id ? departments.value.find(d => d.id === person.department_id) || null : null
}

function cancelEditPerson() {
  editingPersonId.value = null
  editingPersonName.value = ''
  editingPersonDept.value = null
  editingPersonPosition.value = ''
}

async function saveEditPerson(id) {
  if (!editingPersonName.value.trim()) {
    toast.add({ severity: 'warn', summary: '姓名不能为空', life: 2000 })
    return
  }
  const data = { name: editingPersonName.value.trim(), position: editingPersonPosition.value.trim() }
  if (editingPersonDept.value) {
    data.department_id = editingPersonDept.value.id
    data.department_name = editingPersonDept.value.name
  } else {
    data.department_id = ''
    data.department_name = ''
  }
  const { success } = await execute(
    () => personAPI.update(id, data),
    { name: '更新人员', eventTypes: DataEventType.PERSONS_CHANGED, successMsg: '人员信息更新成功' }
  )
  if (success) {
    cancelEditPerson()
    loadPersons()
  }
}

async function checkAiStatus() {
  try {
    const res = await configAPI.aiStatus()
    aiStatus.value = res.data
  } catch (e) {
    aiStatus.value = { success: false, provider: 'unknown', model: '', error: '无法获取状态' }
  }
}

onMounted(() => {
  loadConfig()
  loadManagementData()
  checkAiStatus()
})

useDataRefresh({
  loadFn: loadManagementData,
  watchEvents: getConfigEvents(),
  debounceMs: 300,
  autoLoad: false,
})
</script>

<style scoped>
.config-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding-top: 4px;
}

/* 顶部状态卡片 */
.status-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 22px;
  background: linear-gradient(135deg, #f4f7ff 0%, #ffffff 80%);
  border: 1px solid #dde5ff;
  border-radius: 16px;
}

.status-info {
  display: flex;
  align-items: center;
  gap: 14px;
}

.status-icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: linear-gradient(135deg, #4f6bff, #6ed0ff);
  color: #fff;
  font-size: 20px;
}

.status-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.status-eyebrow {
  font-size: 12px;
  color: #7a819a;
  font-weight: 600;
}

.status-provider {
  font-size: 16px;
  color: #1e2335;
  font-weight: 700;
}

.status-model {
  font-size: 12px;
  color: #5a6481;
}

.status-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.status-tag {
  font-weight: 600;
  font-size: 12px;
}

/* 操作栏 */
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  background: #fff;
  border: 1px solid #eef1f9;
  border-radius: 14px;
}

.action-hint {
  font-size: 13px;
  color: #7a819a;
}

.action-buttons {
  display: flex;
  gap: 10px;
}

/* 两栏网格 */
.grid-wrap {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

/* 通用面板 */
.panel-card {
  background: #fff;
  border: 1px solid #eef1f9;
  border-radius: 16px;
  padding: 22px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.panel-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.panel-eyebrow {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  background: #eef3ff;
  color: #4f6bff;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 6px;
}

.panel-header h3 {
  margin: 0;
  font-size: 16px;
  color: #1e2335;
  font-weight: 700;
}

.panel-desc {
  margin: 4px 0 0;
  font-size: 12px;
  color: #7a819a;
}

.section-divider {
  height: 1px;
  background: #eef1f9;
  margin: 4px 0;
}

/* 数据表格 */
.table-wrap {
  overflow-x: auto;
  border: 1px solid #eef1f9;
  border-radius: 12px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.data-table thead th {
  padding: 10px 14px;
  text-align: left;
  background: #f8faff;
  color: #5a6481;
  font-weight: 600;
  font-size: 12px;
  border-bottom: 1px solid #eef1f9;
}

.data-table tbody td {
  padding: 10px 14px;
  border-bottom: 1px solid #f3f5fb;
  color: #1e2335;
}

.data-table tbody tr:hover {
  background: #f8faff;
}

.cell-input :deep(.p-inputtext) {
  width: 100%;
  font-size: 13px;
}

.action-cell {
  text-align: center;
}

.totals-row {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, rgba(79, 107, 255, 0.06), #fff);
  border-radius: 10px;
  border: 1px solid #dde5ff;
}

.totals-label {
  font-size: 13px;
  color: #5a6481;
}

.totals-value {
  font-size: 18px;
  font-weight: 700;
  color: #4f6bff;
}

/* 等级阈值 */
.threshold-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.threshold-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #eef1f9;
  background: #f8faff;
}

.threshold-item.t-0 { border-color: rgba(22, 168, 117, 0.3); background: rgba(22, 168, 117, 0.05); }
.threshold-item.t-1 { border-color: rgba(79, 107, 255, 0.3); background: rgba(79, 107, 255, 0.05); }
.threshold-item.t-2 { border-color: rgba(217, 119, 6, 0.3); background: rgba(217, 119, 6, 0.05); }
.threshold-item.t-3 { border-color: rgba(239, 68, 68, 0.3); background: rgba(239, 68, 68, 0.05); }

.th-grade { flex-shrink: 0; }

.th-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 28px;
  border-radius: 8px;
  font-weight: 700;
  font-size: 13px;
}

.th-tag.g-0 { background: rgba(22, 168, 117, 0.12); color: #16a875; }
.th-tag.g-1 { background: rgba(79, 107, 255, 0.12); color: #4f6bff; }
.th-tag.g-2 { background: rgba(217, 119, 6, 0.12); color: #d97706; }
.th-tag.g-3 { background: rgba(239, 68, 68, 0.12); color: #ef4444; }

.th-input {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.th-label {
  font-size: 12px;
  color: #5a6481;
  flex-shrink: 0;
}

/* Prompt */
.prompt-area :deep(textarea) {
  font-family: 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.7;
}

.prompt-vars {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #7a819a;
}

.var-desc {
  margin-right: 8px;
}

/* 测试卡片 */
.test-card {
  grid-column: 1 / -1;
}

.test-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.upload-box {
  display: flex;
  align-items: center;
  padding: 20px;
  border: 2px dashed #dde5ff;
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s;
  background: #f8faff;
}

.upload-box:hover {
  border-color: #4f6bff;
  background: rgba(79, 107, 255, 0.04);
}

.upload-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.upload-ic {
  font-size: 28px;
  color: #4f6bff;
  margin-bottom: 4px;
}

.upload-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.upload-hint {
  font-size: 12px;
  color: #7a819a;
}

.upload-filled {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 14px;
}

.file-ic {
  font-size: 28px;
  color: #16a875;
}

.file-meta {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.file-name {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.file-size {
  font-size: 12px;
  color: #7a819a;
}

.test-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.test-result-box {
  margin-top: 8px;
  padding: 20px;
  background: linear-gradient(135deg, #f8faff 0%, #fff 100%);
  border: 1px solid #eef1f9;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 14px;
  border-bottom: 1px solid #eef1f9;
}

.result-score-wrap {
  display: flex;
  flex-direction: column;
}

.result-score {
  font-size: 36px;
  font-weight: 800;
  color: #4f6bff;
  line-height: 1;
}

.result-sub {
  font-size: 12px;
  color: #7a819a;
  margin-top: 4px;
}

.grade-pill {
  font-size: 14px;
  font-weight: 700;
  padding: 6px 16px;
}

.result-dims {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rd-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.rd-name {
  font-size: 13px;
  color: #5a6481;
  min-width: 140px;
}

.rd-bar-bg {
  flex: 1;
  height: 6px;
  background: #eef1f9;
  border-radius: 3px;
  overflow: hidden;
}

.rd-bar {
  height: 100%;
  background: linear-gradient(90deg, #4f6bff, #6ed0ff);
  border-radius: 3px;
  transition: width 0.3s;
}

.rd-val {
  font-size: 13px;
  font-weight: 600;
  color: #1e2335;
  min-width: 60px;
  text-align: right;
}

.result-comment,
.result-suggestion {
  padding: 12px 14px;
  background: #fff;
  border: 1px solid #eef1f9;
  border-radius: 10px;
}

.rc-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #5a6481;
  font-weight: 600;
  margin-bottom: 6px;
}

.result-comment p,
.result-suggestion p {
  margin: 0;
  font-size: 13px;
  color: #3a4059;
  line-height: 1.7;
}

/* 添加行 + 列表 */
.add-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.grow-input {
  flex: 1;
  min-width: 120px;
}

.grow-input :deep(.p-inputtext),
.grow-input :deep(.p-dropdown) {
  width: 100%;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 320px;
  overflow-y: auto;
  padding: 4px;
}

.item-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: #f8faff;
  border-radius: 10px;
  transition: background 0.2s;
}

.item-row:hover {
  background: #eef3ff;
}

.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.item-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e2335;
}

.item-sub {
  font-size: 12px;
  color: #7a819a;
}

.item-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
}

.empty-line {
  text-align: center;
  padding: 20px;
  font-size: 13px;
  color: #a6adc4;
}

/* 响应式 */
@media (max-width: 1100px) {
  .grid-wrap { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .action-bar {
    flex-direction: column;
    align-items: stretch;
    gap: 10px;
  }
  .action-buttons { justify-content: flex-end; }
  .threshold-grid { grid-template-columns: 1fr; }
  .status-card { flex-direction: column; align-items: flex-start; gap: 12px; }
}
</style>
