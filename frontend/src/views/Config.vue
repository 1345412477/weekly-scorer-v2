<template>
  <div class="config-page">
    <div class="config-header">
      <div class="header-info">
        <h1 class="page-title">配置管理</h1>
        <p class="page-desc">管理评分配置、人员信息和部门信息</p>
      </div>
      <div class="header-actions">
        <Button label="🔄 重置默认" severity="secondary" text @click="resetConfig" />
        <Button label="💾 保存配置" icon="pi pi-save" @click="saveConfig" :loading="saving" />
      </div>
    </div>

    <Card class="ai-status-card">
      <template #title>🤖 AI 模型状态</template>
      <template #content>
        <div class="ai-status-container">
          <div class="ai-status-grid">
            <div class="ai-status-item">
              <span class="ai-label">模型提供商</span>
              <Tag :value="providerName" severity="info" />
            </div>
            <div class="ai-status-item">
              <span class="ai-label">模型名称</span>
              <span class="ai-value">{{ aiStatus.model || '-' }}</span>
            </div>
            <div class="ai-status-item">
              <span class="ai-label">连接状态</span>
              <Tag v-if="aiStatus.success === true" value="已连接" severity="success" />
              <Tag v-else-if="aiStatus.success === false" value="连接失败" severity="danger" />
              <Tag v-else value="检测中..." severity="warn" />
            </div>
          </div>
          <div class="ai-status-actions">
            <Button label="测试连接" icon="pi pi-refresh" @click="checkAiStatus" :loading="checkingAi" size="small" />
          </div>
        </div>
        <div v-if="aiStatus.response || aiStatus.error" class="ai-status-detail">
          <div v-if="aiStatus.response">
            <span class="detail-label">测试响应：</span>
            <span class="detail-value">{{ aiStatus.response }}</span>
          </div>
          <div v-if="aiStatus.error" class="ai-error">
            <span class="detail-label">错误信息：</span>
            <span class="detail-value">{{ aiStatus.error }}</span>
          </div>
        </div>
      </template>
    </Card>

    <div class="main-content">
      <div class="left-panel">
        <Card class="section-card dimension-section">
          <template #title>📐 评分维度</template>
          <template #content>
            <div class="dimension-table-wrapper">
              <table class="dimension-table">
                <thead>
                  <tr>
                    <th class="col-name">维度名称 <span class="required">*</span></th>
                    <th class="col-score">最高分</th>
                    <th class="col-score">最低分</th>
                    <th class="col-score">满分 <span class="required">*</span></th>
                    <th class="col-content">考核内容</th>
                    <th class="col-action">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(dim, idx) in dimensions" :key="idx" class="dimension-row">
                    <td class="col-name">
                      <InputText
                        v-model="dim.name"
                        placeholder="维度名称"
                        :class="{ 'p-invalid': !dim.name?.trim() && validationTriggered }"
                        class="input-name"
                      />
                    </td>
                    <td class="col-score">
                      <InputNumber
                        v-model="dim.highest_score"
                        :min="0"
                        :max="dim.full_score || 100"
                        :showButtons="true"
                        :class="{ 'p-invalid': dim.highest_score !== null && dim.highest_score > (dim.full_score || 100) }"
                        size="small"
                      />
                    </td>
                    <td class="col-score">
                      <InputNumber
                        v-model="dim.lowest_score"
                        :min="0"
                        :max="dim.full_score || 100"
                        :showButtons="true"
                        :class="{ 'p-invalid': dim.lowest_score !== null && dim.lowest_score > (dim.full_score || 100) }"
                        size="small"
                      />
                    </td>
                    <td class="col-score">
                      <InputNumber
                        v-model="dim.full_score"
                        :min="1"
                        :max="100"
                        :class="{ 'p-invalid': !dim.full_score || dim.full_score <= 0 }"
                        size="small"
                      />
                    </td>
                    <td class="col-content">
                      <Textarea
                        v-model="dim.evaluation_content"
                        placeholder="考核内容..."
                        :rows="2"
                        class="input-content"
                      />
                    </td>
                    <td class="col-action">
                      <Button
                        icon="pi pi-trash"
                        severity="danger"
                        text
                        rounded
                        size="small"
                        @click="removeDim(idx)"
                        :disabled="dimensions.length <= 1"
                        :title="dimensions.length <= 1 ? '至少保留一个维度' : '删除'"
                      />
                    </td>
                  </tr>
                </tbody>
              </table>

              <div class="table-actions">
                <Button
                  label="添加维度"
                  icon="pi pi-plus"
                  severity="info"
                  text
                  class="btn-add"
                  @click="addDim"
                />
              </div>

              <div class="total-score-display">
                <span class="total-label">总满分：</span>
                <span class="total-value">{{ totalFullScore }}</span>
                <span class="total-unit">分</span>
              </div>
            </div>
          </template>
        </Card>

        <Card class="section-card prompt-section">
          <template #title>
            <div class="prompt-header">
              <span>🤖 AI 评分 Prompt</span>
              <Button label="生成默认模板" icon="pi pi-refresh" size="small" text @click="generateDefaultPrompt" />
            </div>
          </template>
          <template #content>
            <Textarea v-model="promptTemplate" rows="12" class="prompt-editor" placeholder="留空则使用系统默认提示词..." />
            <div class="prompt-variables">
              <span class="var-label">可用变量：</span>
              <div class="var-item">
                <Tag value="{content}" severity="info" />
                <span>周报内容</span>
              </div>
              <div class="var-item">
                <Tag value="{dimensions}" severity="info" />
                <span>评分维度</span>
              </div>
            </div>
          </template>
        </Card>
      </div>

      <div class="right-panel">
        <Card class="section-card threshold-section">
          <template #title>🏆 等级阈值（{{ totalFullScore }}分制）</template>
          <template #content>
            <div class="threshold-list">
              <div v-for="(val, key) in gradeThresholds" :key="key" :class="['threshold-item', getThresholdClass(key)]">
                <div class="threshold-grade">
                  <span :class="['grade-tag', getGradeClass(key)]">{{ gradeNames[key] || key }}</span>
                </div>
                <div class="threshold-range">
                  <span class="range-label">评分 ≥</span>
                  <InputNumber
                    v-model="gradeThresholds[key]"
                    :min="0"
                    :max="totalFullScore"
                    class="input-threshold"
                    size="small"
                  />
                  <span class="range-unit">分</span>
                </div>
              </div>
            </div>
          </template>
        </Card>

        <Card class="section-card test-section">
          <template #title>🧪 测试评分</template>
          <template #content>
            <div class="upload-area" @dragover.prevent @drop.prevent="onTestDrop" @click="triggerTestFileInput">
              <input ref="testFileInput" type="file" accept=".xlsx,.xls,.docx,.pdf" style="display:none" @change="onTestFileSelect" />
              <div v-if="!testFile" class="upload-placeholder">
                <i class="pi pi-cloud-upload upload-icon"></i>
                <p class="upload-title">点击或拖拽周报文件</p>
                <span class="upload-hint">支持 .xlsx、.xls、.docx、.pdf 格式</span>
              </div>
              <div v-else class="upload-selected">
                <i class="pi pi-file-excel file-icon"></i>
                <div class="file-info">
                  <p class="file-name">{{ testFile.name }}</p>
                  <span class="file-size">{{ formatFileSize(testFile.size) }}</span>
                </div>
                <Button icon="pi pi-times" text rounded severity="danger" @click.stop="clearTestFile" />
              </div>
            </div>
            <div class="test-actions">
              <Button label="上传并评分" icon="pi pi-play" @click="runTest" :loading="testing" :disabled="!testFile" />
              <Button label="清空" severity="secondary" text @click="resetTest" />
            </div>

            <div v-if="testResult" class="test-result">
              <Divider />
              <h4 class="result-title">测试结果</h4>
              <div class="result-breakdown">
                <div v-for="(item, idx) in testResult.dimension_scores" :key="idx" class="result-row">
                  <span class="result-name">{{ item.name }}</span>
                  <div class="result-bar-wrapper">
                    <div class="result-bar">
                      <div class="result-fill" :style="{ width: (item.score / item.max * 100) + '%' }"></div>
                    </div>
                  </div>
                  <span class="result-score">{{ item.score }}/{{ item.max }}</span>
                </div>
              </div>
              <div class="result-total">
                综合评分：<strong>{{ testResult.total_score }}</strong>
                <span :class="['grade-tag', getGradeClass(testResult.grade)]" style="margin-left: 8px;">{{ testResult.grade }}</span>
              </div>
              <div v-if="testResult.ai_comment" class="result-comment">
                <p class="comment-label">AI 评语：</p>
                <p class="comment-content">{{ testResult.ai_comment }}</p>
              </div>
              <div v-if="testResult.ai_suggestion" class="result-comment">
                <p class="comment-label">改进建议：</p>
                <p class="comment-content">{{ testResult.ai_suggestion }}</p>
              </div>
            </div>
          </template>
        </Card>
      </div>
    </div>

    <Divider class="section-divider" />

    <div class="management-section">
      <div class="section-header">
        <h2 class="section-title">👥 人员与部门管理</h2>
        <p class="section-desc">管理系统中的人员和部门信息</p>
      </div>

      <div class="management-grid">
        <Card class="section-card dept-section">
          <template #title>🏢 部门管理</template>
          <template #content>
            <div class="add-form">
              <InputText v-model="newDeptName" placeholder="部门名称" class="form-input" />
              <InputText v-model="newDeptDesc" placeholder="部门描述（可选）" class="form-input" />
              <Button label="添加" icon="pi pi-plus" @click="addDepartment" :disabled="!newDeptName.trim()" size="small" />
            </div>
            <div class="item-list">
              <div v-for="dept in departments" :key="dept.id" class="item-row">
                <template v-if="editingDeptId === dept.id">
                  <div class="edit-form">
                    <InputText v-model="editingDeptName" placeholder="部门名称" class="form-input" />
                    <InputText v-model="editingDeptDesc" placeholder="部门描述" class="form-input" />
                    <div class="edit-actions">
                      <Button icon="pi pi-check" size="small" @click="saveEditDepartment(dept.id)" :disabled="!editingDeptName.trim()" />
                      <Button icon="pi pi-times" size="small" severity="secondary" text @click="cancelEditDepartment" />
                    </div>
                  </div>
                </template>
                <template v-else>
                  <div class="item-info">
                    <span class="item-name">{{ dept.name }}</span>
                    <span class="item-desc">{{ dept.description || '无描述' }}</span>
                  </div>
                  <div class="item-actions">
                    <Button icon="pi pi-pencil" text rounded size="small" @click="startEditDepartment(dept)" />
                    <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="deleteDepartment(dept.id)" />
                  </div>
                </template>
              </div>
              <div v-if="!departments.length" class="empty-state">暂无部门</div>
            </div>
          </template>
        </Card>

        <Card class="section-card person-section">
          <template #title>👤 人员管理</template>
          <template #content>
            <div class="add-form">
              <InputText v-model="newPersonName" placeholder="姓名" class="form-input" />
              <Dropdown v-model="newPersonDept" :options="departments" optionLabel="name" placeholder="选择部门" showClear class="form-input" />
              <InputText v-model="newPersonPosition" placeholder="职位（可选）" class="form-input" />
              <Button label="添加" icon="pi pi-plus" @click="addPerson" :disabled="!newPersonName.trim()" size="small" />
            </div>
            <div class="item-list">
              <div v-for="person in persons" :key="person.id" class="item-row">
                <template v-if="editingPersonId === person.id">
                  <div class="edit-form">
                    <InputText v-model="editingPersonName" placeholder="姓名" class="form-input" />
                    <Dropdown v-model="editingPersonDept" :options="departments" optionLabel="name" placeholder="选择部门" showClear class="form-input" />
                    <InputText v-model="editingPersonPosition" placeholder="职位" class="form-input" />
                    <div class="edit-actions">
                      <Button icon="pi pi-check" size="small" @click="saveEditPerson(person.id)" :disabled="!editingPersonName.trim()" />
                      <Button icon="pi pi-times" size="small" severity="secondary" text @click="cancelEditPerson" />
                    </div>
                  </div>
                </template>
                <template v-else>
                  <div class="item-info">
                    <span class="item-name">{{ person.name }}</span>
                    <span class="item-desc">{{ person.department_name || '未分配部门' }}{{ person.position ? ' · ' + person.position : '' }}</span>
                  </div>
                  <div class="item-actions">
                    <Button icon="pi pi-pencil" text rounded size="small" @click="startEditPerson(person)" />
                    <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="deletePerson(person.id)" />
                  </div>
                </template>
              </div>
              <div v-if="!persons.length" class="empty-state">暂无人员</div>
            </div>
          </template>
        </Card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { configAPI, departmentAPI, personAPI, reportAPI, clearCache } from '../api'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import Textarea from 'primevue/textarea'
import Button from 'primevue/button'
import Dropdown from 'primevue/dropdown'
import Divider from 'primevue/divider'
import Tag from 'primevue/tag'
import { useToast } from 'primevue/usetoast'

const toast = useToast()
const saving = ref(false)
const testing = ref(false)
const checkingAi = ref(false)
const aiStatus = ref({ provider: '', model: '', success: null })
const validationTriggered = ref(false)

const dimensions = ref([
  { name: '工作反馈深度', full_score: 14, highest_score: null, lowest_score: null, evaluation_content: '问题发现+分析+解决方案' },
  { name: '进度节点明确', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '项目是否有明确进度/节点' },
  { name: '计划可行性', full_score: 10, highest_score: null, lowest_score: null, evaluation_content: '下周计划是否具体可执行' },
  { name: '工作连续性', full_score: 13, highest_score: null, lowest_score: null, evaluation_content: '是否承接上周计划且有闭环' },
])
const gradeThresholds = ref({ '优': 45, '良': 38, '一般': 33, '差': 28 })
const gradeNames = { '优': '优', '良': '良', '一般': '一般', '差': '差' }
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
  return p || '-'
})

function getGradeClass(g) {
  return { '优': 'grade-you', '良': 'grade-liang', '一般': 'grade-yiban', '差': 'grade-cha' }[g] || ''
}

function getThresholdClass(g) {
  return { '优': 'threshold-you', '良': 'threshold-liang', '一般': 'threshold-yiban', '差': 'threshold-cha' }[g] || ''
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
}

async function loadConfig() {
  try {
    const res = await configAPI.get()
    const d = res.data
    if (d.dimensions?.length) dimensions.value = d.dimensions
    if (d.grade_thresholds) gradeThresholds.value = d.grade_thresholds
    if (d.prompt_template) promptTemplate.value = d.prompt_template
  } catch (e) { console.error(e) }
}

function validateDimensions() {
  validationTriggered.value = true
  
  for (const dim of dimensions.value) {
    if (!dim.name?.trim()) {
      toast.add({ severity: 'warn', summary: '请填写所有维度名称', life: 3000 })
      return false
    }
    if (!dim.full_score || dim.full_score <= 0) {
      toast.add({ severity: 'warn', summary: `维度 "${dim.name || '未命名'}" 的满分必须大于0`, life: 3000 })
      return false
    }
    if (dim.highest_score !== null && dim.highest_score > dim.full_score) {
      toast.add({ severity: 'warn', summary: `维度 "${dim.name}" 的最高分不能超过满分`, life: 3000 })
      return false
    }
    if (dim.lowest_score !== null && dim.lowest_score > dim.full_score) {
      toast.add({ severity: 'warn', summary: `维度 "${dim.name}" 的最低分不能超过满分`, life: 3000 })
      return false
    }
    if (dim.highest_score !== null && dim.lowest_score !== null && dim.lowest_score > dim.highest_score) {
      toast.add({ severity: 'warn', summary: `维度 "${dim.name}" 的最低分不能大于最高分`, life: 3000 })
      return false
    }
  }
  
  const categories = dimensions.value
    .map(dim => dim.dimension_category?.trim())
    .filter(cat => cat && cat.length > 0)
  const uniqueCategories = new Set(categories)
  if (uniqueCategories.size < categories.length) {
    toast.add({ severity: 'warn', summary: '评分维度类别不能重复', life: 3000 })
    return false
  }
  
  return true
}

async function saveConfig() {
  if (!validateDimensions()) return
  
  saving.value = true
  try {
    await configAPI.save({
      dimensions: dimensions.value,
      grade_thresholds: gradeThresholds.value,
      prompt_template: promptTemplate.value,
    })
    clearCache()
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
  
  const totalLowestScore = dimensions.value.reduce((s, d) => s + (d.lowest_score || 0), 0)
  const totalHighestScore = dimensions.value.reduce((s, d) => s + (d.highest_score || d.full_score), 0)
  
  promptTemplate.value = `# 周报评分系统提示词\n\n## 角色设定\n你是一位专业、客观的工作报告评审专家。请根据以下评分维度对员工周报进行综合评估。\n\n## 评分原则\n1. 客观公正：基于周报内容进行评价，避免主观臆断\n2. 鼓励量化：对有数据支撑、可量化成果的内容给予更高评价\n3. 关注闭环：重视"计划→执行→结果"的完整闭环\n4. 提供建设性：评语和建议应具体、可操作\n\n## 评分维度\n${dims || '（请先配置评分维度）'}\n\n## 评分标准\n- 每个维度独立打分，不超过该维度满分\n- 综合评分 = 各维度分数直接相加（${totalLowestScore}-${totalHighestScore}分）\n- 等级划分：${gradeText}\n\n## 输出要求\n请以 JSON 格式返回评分结果，包含：\n- dimension_scores: 各维度得分及评语（含name、score、max、comment）\n- total_score: 综合得分（${totalLowestScore}-${totalHighestScore}分）\n- grade: 等级（优/良/一般/差）\n- comment: 总体评语（100字以内）\n- suggestion: 改进建议（具体可执行）\n\n## 周报内容\n{content}`
  
  toast.add({ severity: 'success', summary: '已生成默认模板', life: 2000 })
}

async function runTest() {
  if (!testFile.value) {
    toast.add({ severity: 'warn', summary: '请选择周报文件', life: 2000 })
    return
  }
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
      toast.add({ severity: 'success', summary: uploadData.message || '评分完成', life: 3000 })
    } else {
      toast.add({ severity: 'warn', summary: uploadData.message || '上传成功但未获取到评分', life: 3000 })
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
  } catch (e) { console.error(e) }
}

async function loadPersons() {
  try {
    const res = await personAPI.list()
    persons.value = res.data || []
  } catch (e) { console.error(e) }
}

async function addDepartment() {
  if (!newDeptName.value.trim()) return
  try {
    await departmentAPI.create({ name: newDeptName.value, description: newDeptDesc.value })
    newDeptName.value = ''
    newDeptDesc.value = ''
    toast.add({ severity: 'success', summary: '部门添加成功', life: 2000 })
    loadDepartments()
  } catch (e) {
    toast.add({ severity: 'error', summary: e.response?.data?.detail || '添加失败', life: 2000 })
  }
}

async function deleteDepartment(id) {
  try {
    await departmentAPI.delete(id)
    toast.add({ severity: 'success', summary: '部门已删除', life: 2000 })
    loadDepartments()
  } catch (e) {
    toast.add({ severity: 'error', summary: '删除失败', life: 2000 })
  }
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
  try {
    await departmentAPI.update(id, {
      name: editingDeptName.value.trim(),
      description: editingDeptDesc.value.trim(),
    })
    toast.add({ severity: 'success', summary: '部门更新成功', life: 2000 })
    cancelEditDepartment()
    loadDepartments()
  } catch (e) {
    toast.add({ severity: 'error', summary: e.response?.data?.detail || '更新失败', life: 2000 })
  }
}

async function addPerson() {
  if (!newPersonName.value.trim()) return
  try {
    const data = {
      name: newPersonName.value,
      position: newPersonPosition.value,
    }
    if (newPersonDept.value) {
      data.department_id = newPersonDept.value.id
      data.department_name = newPersonDept.value.name
    }
    await personAPI.create(data)
    newPersonName.value = ''
    newPersonDept.value = null
    newPersonPosition.value = ''
    toast.add({ severity: 'success', summary: '人员添加成功', life: 2000 })
    loadPersons()
  } catch (e) {
    toast.add({ severity: 'error', summary: e.response?.data?.detail || '添加失败', life: 2000 })
  }
}

async function deletePerson(id) {
  try {
    await personAPI.delete(id)
    toast.add({ severity: 'success', summary: '人员已删除', life: 2000 })
    loadPersons()
  } catch (e) {
    toast.add({ severity: 'error', summary: '删除失败', life: 2000 })
  }
}

function startEditPerson(person) {
  editingPersonId.value = person.id
  editingPersonName.value = person.name
  editingPersonPosition.value = person.position || ''
  if (person.department_id) {
    editingPersonDept.value = departments.value.find(d => d.id === person.department_id) || null
  } else {
    editingPersonDept.value = null
  }
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
  try {
    const data = {
      name: editingPersonName.value.trim(),
      position: editingPersonPosition.value.trim(),
    }
    if (editingPersonDept.value) {
      data.department_id = editingPersonDept.value.id
      data.department_name = editingPersonDept.value.name
    } else {
      data.department_id = ''
      data.department_name = ''
    }
    await personAPI.update(id, data)
    toast.add({ severity: 'success', summary: '人员信息更新成功', life: 2000 })
    cancelEditPerson()
    loadPersons()
  } catch (e) {
    toast.add({ severity: 'error', summary: e.response?.data?.detail || '更新失败', life: 2000 })
  }
}

async function checkAiStatus() {
  checkingAi.value = true
  try {
    const res = await configAPI.aiStatus()
    aiStatus.value = res.data
  } catch (e) {
    aiStatus.value = { success: false, provider: 'unknown', model: '', error: '无法获取状态' }
  } finally {
    checkingAi.value = false
  }
}

onMounted(() => {
  loadConfig()
  loadDepartments()
  loadPersons()
  checkAiStatus()
})
</script>

<style scoped>
.config-page {
  min-height: 100vh;
  padding: 24px;
  max-width: 1800px;
  margin: 0 auto;
}

.config-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
  flex-wrap: wrap;
  gap: 16px;
}

.header-info {
  flex: 1;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: #1A1D26;
  margin: 0;
  letter-spacing: -0.3px;
}

.page-desc {
  font-size: 13px;
  color: #6C7086;
  margin-top: 4px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.ai-status-card {
  margin-bottom: 24px;
  width: 1142px;
}

.ai-status-card :deep(.p-card-body) {
  width: 100%;
  background: linear-gradient(135deg, #F0F1F5 0%, #FFFFFF 100%);
}

.ai-status-card :deep(.p-card-content) {
  width: 100%;
}

.ai-status-card :deep(.p-card-title) {
  font-size: 13px;
  color: #3D4150;
}

.ai-status-container {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}

.ai-status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 16px;
  flex: 1;
}

.ai-status-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-label {
  color: #6C7086;
  font-size: 13px;
  min-width: 80px;
}

.ai-value {
  color: #1A1D26;
  font-size: 13px;
}

.ai-status-actions {
  flex-shrink: 0;
}

.ai-status-detail {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #E2E4E9;
}

.detail-label {
  color: #6C7086;
  font-size: 13px;
}

.detail-value {
  color: #1A1D26;
  font-size: 13px;
}

.ai-error .detail-value {
  color: #EF4444;
  word-break: break-all;
  max-width: 400px;
}

.main-content {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
  margin-bottom: 32px;
}

.left-panel,
.right-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.section-card {
  background: #FFFFFF;
  border: 1px solid #ECEEF2;
  border-radius: 16px;
}

.section-card :deep(.p-card-title) {
  font-size: 13px;
  color: #3D4150;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.section-card :deep(.p-card-content) {
  padding-top: 16px;
}

.dimension-table-wrapper {
  overflow-x: auto;
}

.dimension-table {
  width: 100%;
  border-collapse: collapse;
  min-width: 700px;
}

.dimension-table th,
.dimension-table td {
  padding: 12px 16px;
  text-align: left;
  border-bottom: 1px solid #ECEEF2;
}

.dimension-table th {
  background: #EAECF0;
  font-weight: 600;
  font-size: 13px;
  color: #3D4150;
  white-space: nowrap;
}

.dimension-table .required {
  color: #DC2626;
}

.dimension-row:hover {
  background: #F0F1F5;
}

.col-name {
  width: 20%;
}

.col-score {
  width: 12%;
}

.col-content {
  width: 28%;
}

.col-action {
  width: 10%;
  text-align: center;
}

.input-name :deep(.p-inputtext) {
  width: 100%;
}

.input-content :deep(textarea) {
  width: 100%;
  min-height: 60px;
  resize: vertical;
}

.table-actions {
  margin-top: 16px;
}

.btn-add {
  width: 100%;
  justify-content: center;
}

.total-score-display {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 4px;
  margin-top: 16px;
  padding: 16px 24px;
  background: linear-gradient(135deg, rgba(91, 95, 199, 0.08), #EAECF0);
  border-radius: 12px;
  border: 1px solid rgba(91, 95, 199, 0.2);
}

.total-label {
  color: #6C7086;
  font-size: 14px;
}

.total-value {
  color: #5B5FC7;
  font-size: 20px;
  font-weight: 700;
}

.total-unit {
  color: #5B5FC7;
  font-size: 14px;
}

.threshold-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.threshold-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  background: #EAECF0;
  border-radius: 12px;
  border-left: 3px solid transparent;
  transition: all 0.25s ease;
}

.threshold-item:hover {
  background: #FFFFFF;
  border-color: #5B5FC7;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.threshold-you { border-left-color: #D97706; }
.threshold-liang { border-left-color: #16A34A; }
.threshold-yiban { border-left-color: #2563EB; }
.threshold-cha { border-left-color: #DC2626; }

.threshold-grade {
  width: 48px;
}

.grade-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  height: 28px;
  padding: 0 8px;
  border-radius: 8px;
  font-weight: 700;
  font-size: 13px;
}

.grade-you {
  background: rgba(217, 119, 6, 0.08);
  color: #D97706;
  border: 1px solid rgba(217, 119, 6, 0.2);
}

.grade-liang {
  background: rgba(22, 163, 74, 0.08);
  color: #16A34A;
  border: 1px solid rgba(22, 163, 74, 0.2);
}

.grade-yiban {
  background: rgba(37, 99, 235, 0.08);
  color: #2563EB;
  border: 1px solid rgba(37, 99, 235, 0.2);
}

.grade-cha {
  background: rgba(220, 38, 38, 0.08);
  color: #DC2626;
  border: 1px solid rgba(220, 38, 38, 0.2);
}

.threshold-range {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  flex-wrap: nowrap;
}

.range-label {
  color: #3D4150;
  font-size: 13px;
  white-space: nowrap;
  flex-shrink: 0;
}

.input-threshold {
  width: 64px;
}

.input-threshold :deep(.p-inputtext) {
  width: 100%;
  display: block;
  text-align: center;
}

.range-unit {
  color: #6C7086;
  font-size: 13px;
}

.prompt-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.prompt-editor {
  width: 100%;
  min-height: 240px;
  resize: vertical;
  background: #EAECF0;
  border-color: #E2E4E9;
  font-family: 'Consolas', monospace;
  font-size: 13px;
}

.prompt-variables {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
  padding: 8px 16px;
  background: #EAECF0;
  border-radius: 12px;
  flex-wrap: wrap;
}

.var-label {
  color: #6C7086;
  font-size: 12px;
}

.var-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #3D4150;
  font-size: 12px;
}

.upload-area {
  border: 2px dashed #E2E4E9;
  border-radius: 12px;
  padding: 32px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  background: #EAECF0;
}

.upload-area:hover {
  border-color: #5B5FC7;
  background: rgba(99, 102, 241, 0.05);
}

.upload-icon {
  font-size: 36px;
  color: #7B7FD7;
}

.upload-title {
  color: #1A1D26;
  font-size: 14px;
  margin: 8px 0 4px;
}

.upload-hint {
  color: #6C7086;
  font-size: 12px;
}

.upload-selected {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 12px;
}

.file-icon {
  font-size: 28px;
  color: #22C55E;
}

.file-info {
  flex: 1;
}

.file-name {
  color: #1A1D26;
  font-size: 14px;
  font-weight: 500;
  margin: 0;
}

.file-size {
  color: #6C7086;
  font-size: 12px;
}

.test-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.test-result {
  margin-top: 24px;
}

.result-title {
  color: #1A1D26;
  font-size: 16px;
  margin-bottom: 16px;
}

.result-breakdown {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.result-name {
  color: #3D4150;
  font-size: 13px;
  min-width: 100px;
}

.result-bar-wrapper {
  flex: 1;
}

.result-bar {
  height: 6px;
  background: #EAECF0;
  border-radius: 3px;
  overflow: hidden;
}

.result-fill {
  height: 100%;
  background: linear-gradient(90deg, #5B5FC7, #7B7FD7);
  border-radius: 3px;
}

.result-score {
  color: #1A1D26;
  font-weight: 600;
  font-size: 13px;
  min-width: 60px;
  text-align: right;
}

.result-total {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #E2E4E9;
  color: #1A1D26;
  font-size: 16px;
}

.result-total strong {
  color: #7B7FD7;
  font-size: 24px;
}

.result-comment {
  margin-top: 16px;
  padding: 16px;
  background: #EAECF0;
  border-radius: 12px;
}

.comment-label {
  color: #3D4150;
  font-size: 13px;
  margin-bottom: 4px;
}

.comment-content {
  color: #3D4150;
  font-size: 13px;
  line-height: 1.6;
  margin: 0;
}

.section-divider {
  margin: 32px 0;
}

.management-section {
  margin-top: 24px;
}

.section-header {
  margin-bottom: 24px;
}

.section-title {
  font-size: 20px;
  font-weight: 700;
  color: #1A1D26;
  margin: 0;
}

.section-desc {
  color: #6C7086;
  font-size: 13px;
  margin-top: 4px;
}

.management-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 24px;
}

.add-form {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.form-input {
  flex: 1;
  min-width: 120px;
}

.item-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.item-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: #EAECF0;
  border-radius: 12px;
}

.item-info {
  display: flex;
  flex-direction: column;
}

.item-name {
  color: #1A1D26;
  font-weight: 500;
  font-size: 14px;
}

.item-desc {
  color: #6C7086;
  font-size: 12px;
  margin-top: 2px;
}

.item-actions {
  display: flex;
  gap: 4px;
}

.edit-form {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
  width: 100%;
}

.edit-actions {
  display: flex;
  gap: 4px;
}

.empty-state {
  text-align: center;
  color: #6C7086;
  padding: 24px;
  font-size: 13px;
}

@media (min-width: 1200px) {
  .main-content {
    grid-template-columns: 1fr 1fr;
    gap: 32px;
  }

  .management-grid {
    grid-template-columns: 1fr 1fr;
    gap: 32px;
  }
}

@media (max-width: 1024px) {
  .config-page {
    padding: 16px;
  }

  .page-title {
    font-size: 20px;
  }

  .dimension-table th,
  .dimension-table td {
    padding: 8px 12px;
    font-size: 12px;
  }
}

@media (max-width: 768px) {
  .config-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .ai-status-container {
    flex-direction: column;
    align-items: flex-start;
  }

  .ai-status-grid {
    width: 100%;
  }

  .threshold-item {
    flex-wrap: wrap;
    gap: 8px;
  }

  .threshold-grade {
    width: auto;
  }

  .prompt-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }

  .prompt-variables {
    flex-wrap: wrap;
  }

  .add-form {
    flex-direction: column;
  }

  .form-input {
    width: 100%;
  }
}

@media (max-width: 640px) {
  .config-page {
    padding: 12px;
  }

  .section-card :deep(.p-card-content) {
    padding: 12px;
  }

  .upload-area {
    padding: 24px 16px;
  }

  .upload-icon {
    font-size: 28px;
  }
}
</style>