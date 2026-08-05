import axios from 'axios'
import { clearAuth, getToken } from '../utils/auth'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
  headers: {
    'Content-Type': 'application/json',
  },
})

const uploadApi = axios.create({
  baseURL: '/api/v1',
  timeout: 120000,
})

// 统一评分专用：AI 评分 + OCR + 聚合可能耗时较长，设置 10 分钟超时
const scoringApi = axios.create({
  baseURL: '/api/v1',
  timeout: 600000,
  headers: {
    'Content-Type': 'application/json',
  },
})

const cache = new Map()
const CACHE_TTL = 60000

function getCacheKey(url, params) {
  return `${url}?${JSON.stringify(params)}`
}

function attachAuth(config) {
  // 登录接口不需要 Authorization 头，避免带上旧/无效 token 导致 FastAPI 返回 401 时被误认为登录态问题
  const url = (config.url || '').toLowerCase()
  if (url.includes('/auth/login')) return config

  const token = getToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}

function handleResponse(res) {
  if (res.config._cacheHit) {
    return res.config._cachedData
  }

  if (res.config.method === 'get' && res.config.cache === true) {
    const key = getCacheKey(res.config.url, res.config.params)
    // 限制缓存条目，避免内存无限增长
    if (cache.size >= 100) {
      const firstKey = cache.keys().next().value
      if (firstKey) cache.delete(firstKey)
    }
    cache.set(key, { timestamp: Date.now(), data: res })
  }
  return res
}

function handleError(err) {
  if (axios.isCancel(err)) {
    return Promise.resolve(null)
  }

  const status = err.response?.status
  const detail = err.response?.data?.detail
  const url = err.config?.url || ''

  // 解析 FastAPI/Pydantic 的错误详情
  // 可能是字符串: "用户名或密码错误"
  // 可能是数组: [{type:"missing",loc:["body","password"],msg:"Field required",input:null}]
  // 可能是对象: {code:"xxx",msg:"..."}
  function parseDetail(d) {
    if (d == null) return null
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      return d.map(item => {
        if (!item) return ''
        const loc = item.loc ? item.loc.join('.') : ''
        const fieldName = loc.startsWith('body.') ? loc.slice(5) : loc
        const inputHint = (item.input === null || item.input === undefined || item.input === '') ? '（不能为空）' : ''
        return fieldName ? `${fieldName}: ${item.msg}${inputHint}` : (item.msg || '')
      }).filter(Boolean).join('; ')
    }
    if (typeof d === 'object') {
      return d.msg || d.message || d.detail || JSON.stringify(d)
    }
    return String(d)
  }

  let msg = '请求失败，请稍后重试'
  // 登录请求失败时完全不弹 toast，由页面内的红色横幅统一提示
  const isLoginRequest = url.toLowerCase().includes('/auth/login')
  const isLoginPage = typeof window !== 'undefined' && window.location.pathname === '/admin/login'
  // 静默请求：页面用 _silent=true 标记表示失败不应在前端日志和 UI 中喧嚣
  const isSilent = err.config?._silent === true

  if (status === 401) {
    if (isLoginRequest) {
      msg = parseDetail(detail) || '用户名或密码错误'
    } else {
      clearAuth()
      msg = parseDetail(detail) || '登录已失效，请重新登录'
      if (typeof window !== 'undefined' && !isLoginPage && window.location.pathname.startsWith('/admin')) {
        window.location.href = '/admin/login'
      }
    }
  } else if (status === 403) {
    // require_admin 在“用户不存在/角色不符”时返回 403，同样视为登录态失效
    msg = parseDetail(detail) || '登录状态已失效，请重新登录'
    if (!isLoginRequest) {
      clearAuth()
      if (typeof window !== 'undefined' && !isLoginPage && window.location.pathname.startsWith('/admin')) {
        window.location.href = '/admin/login'
      }
    }
  } else if (status === 400) {
    msg = parseDetail(detail) || '请求参数错误'
  } else if (status === 404) {
    msg = parseDetail(detail) || '资源不存在'
  } else if (status === 409) {
    // 保留结构化 detail（week_mismatch / duplicate），前端需要读取 type 字段
    if (detail && typeof detail === 'object' && detail.type) {
      msg = detail.message || parseDetail(detail)
    } else {
      msg = parseDetail(detail) || '操作冲突，请刷新页面后重试'
    }
  } else if (status === 413) {
    msg = parseDetail(detail) || '文件过大，请压缩后重试'
  } else if (status === 503) {
    msg = parseDetail(detail) || '服务暂时不可用'
  } else if (status === 500) {
    msg = parseDetail(detail) || '服务器内部错误，请稍后重试'
  } else if (detail) {
    msg = parseDetail(detail)
  } else if (!err.response) {
    if (err.code === 'ECONNREFUSED') {
      msg = '无法连接到服务器，请检查后端服务是否运行'
    } else if (err.code === 'ETIMEDOUT') {
      msg = '请求超时，请稍后重试'
    } else if (err.message?.includes('Network Error')) {
      msg = '网络连接失败，请检查网络设置'
    } else if (err.code === 'ERR_NETWORK') {
      msg = '网络错误，请检查网络连接'
    } else {
      msg = `网络请求失败: ${err.message || '未知错误'}`
    }
  }

  // 静默模式：不打 console.error，不弹 toast，直接 reject
  if (isSilent) {
    return Promise.reject({ ...err, userMessage: msg })
  }

  console.error('[API Error]', {
    status: status ?? 'N/A',
    msg,
    code: err.code,
    url: url || err.config?.url,
    message: err.message,
  })

  // 登录请求失败时不弹 toast，完全由页面内横幅提示
  // 结构化 409 响应（week_mismatch / duplicate）不弹 toast，由组件自行处理
  const isStructured409 = status === 409 && detail && typeof detail === 'object' && detail.type
  if (!isLoginRequest && !isStructured409 && typeof window !== 'undefined' && window.showToast) {
    window.showToast(msg, 'error')
  }

  return Promise.reject({ ...err, userMessage: msg })
}

api.interceptors.request.use(
  config => {
    attachAuth(config)
    if (config.method === 'get' && config.cache === true) {
      const key = getCacheKey(config.url, config.params)
      const cached = cache.get(key)
      if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        config._cacheHit = true
        config._cachedData = cached.data
        return config
      }
    }
    return config
  },
  error => Promise.reject(error)
)

uploadApi.interceptors.request.use(
  config => attachAuth(config),
  error => Promise.reject(error)
)

scoringApi.interceptors.request.use(
  config => attachAuth(config),
  error => Promise.reject(error)
)

api.interceptors.response.use(handleResponse, handleError)
uploadApi.interceptors.response.use(handleResponse, handleError)
scoringApi.interceptors.response.use(handleResponse, handleError)

export function clearCache() {
  cache.clear()
}

export function clearCacheByUrl(url) {
  for (const key of cache.keys()) {
    if (key.startsWith(url)) {
      cache.delete(key)
    }
  }
}

export const authAPI = {
  login: (data) => api.post('/auth/login', data),
  me: () => api.get('/auth/me'),
}

export const configAPI = {
  get: () => api.get('/config'),
  save: (data) => api.put('/config', data),
  test: (data) => api.post('/config/test', data),
  aiStatus: (force = false) => api.get(`/config/ai-status${force ? '?force=true' : ''}`),
  dataStatus: () => api.get('/config/data-status'),
  backup: () => api.post('/config/backup'),
}

export const templateAPI = {
  list: () => api.get('/templates'),
  get: (id) => api.get(`/templates/${id}`),
  create: (data) => api.post('/templates', data),
  update: (id, data) => api.put(`/templates/${id}`, data),
  delete: (id) => api.delete(`/templates/${id}`),
}

export const reportAPI = {
  create: (data) => api.post('/reports', data),
  list: (params) => api.get('/reports', { params }),
  get: (id) => api.get(`/reports/${id}`),
  getPublic: (id) => api.get(`/reports/public/${id}`),
  submit: (id) => api.post(`/reports/${id}/submit`),
  delete: (id) => api.delete(`/reports/${id}`),
  batchDelete: (ids) => api.post('/reports/batch-delete', ids),
  clearAll: () => api.post('/reports/clear-all'),
  download: (id) => api.get(`/reports/${id}/download`, { responseType: 'blob' }),
  export: (ids) => api.post('/reports/export', ids, { responseType: 'blob' }),
  downloadTemplate: () => api.get('/reports/template/download', { responseType: 'blob' }),
  upload: (formData) => uploadApi.post('/reports/upload', formData),
}

// 员工首页：一周小结图片上传（仅图片，不含文本/姓名兜底）
export const weeklySummaryAPI = {
  upload: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return uploadApi.post('/weeklysummary/upload', formData)
  },
}

// 员工首页：周报 + 一周小结 联合上传；统一用周报文件名识别员工
export const unifiedUploadAPI = {
  uploadUnified: (reportFile, summaryFile, forceSubmit = false, overwriteSummary = false) => {
    const formData = new FormData()
    formData.append('report', reportFile)
    if (summaryFile) {
      formData.append('summary', summaryFile)
    }
    if (forceSubmit) {
      formData.append('force_submit', 'true')
    }
    if (overwriteSummary) {
      formData.append('overwrite_summary', 'true')
    }
    return uploadApi.post('/upload/unified', formData)
  },
}

// 管理员端：企业微信数据上传
export const attendanceAPI = {
  preview: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return uploadApi.post('/attendance/preview', formData)
  },
  upload: (file, mode = 'append') => {
    const formData = new FormData()
    formData.append('file', file)
    return uploadApi.post(`/attendance/upload?mode=${mode}`, formData)
  },
  cancel: () => api.post('/attendance/cancel'),
  list: (params) => api.get('/attendance', { params }),
  status: () => api.get('/attendance/status', { _silent: true }),
}

export const chatAPI = {
  preview: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return uploadApi.post('/chat/preview', formData)
  },
  upload: (file, mode = 'append') => {
    const formData = new FormData()
    formData.append('file', file)
    return uploadApi.post(`/chat/upload?mode=${mode}`, formData)
  },
  cancel: () => api.post('/chat/cancel'),
  list: (params) => api.get('/chat', { params }),
  status: () => api.get('/chat/status', { _silent: true }),
}

// 管理员端：统一评分（对所有已提交材料进行 AI 评分与聚合）
export const scoringAPI = {
  run: () => scoringApi.post('/scoring/run'),
}

// 周评列表（含综合得分），管理员可修改分数
export const aggregateAPI = {
  list: (params) => api.get('/weekly-aggregates', { params }),
  update: (id, data) => api.put(`/weekly-aggregates/${id}`, data),
  restoreAI: (id) => api.post(`/weekly-aggregates/${id}/restore-ai`),
  delete: (id) => api.delete(`/weekly-aggregates/${id}`),
  batchDelete: (ids) => api.post('/weekly-aggregates/batch-delete', { ids }),
  downloadReport: (id) => api.get(`/weekly-aggregates/${id}/download-report`, { responseType: 'blob' }),
  export: (payload) => api.post('/weekly-aggregates/export', payload, { responseType: 'blob' }),
  getSchedule: () => api.get('/weekly-aggregates/schedule'),
  saveSchedule: (data) => api.post('/weekly-aggregates/schedule', data),
  scoringStatus: () => api.get('/weekly-aggregates/status', { _silent: true }),
  triggerScoring: () => api.post('/weekly-aggregates/status/trigger'),
  recalculate: (weekStart) => scoringApi.post('/weekly-aggregates/recalculate', { week_start: weekStart }),
}

export const leaderboardAPI = {
  get: (params) => api.get('/leaderboard', { params }),
  stats: () => api.get('/leaderboard/stats'),
  dashboard: () => api.get('/leaderboard/dashboard'),
}

export const departmentAPI = {
  list: () => api.get('/departments'),
  get: (id) => api.get(`/departments/${id}`),
  create: (data) => api.post('/departments', data),
  update: (id, data) => api.put(`/departments/${id}`, data),
  delete: (id) => api.delete(`/departments/${id}`),
}

export const personAPI = {
  list: (params) => api.get('/persons', { params }),
  get: (id) => api.get(`/persons/${id}`),
  create: (data) => api.post('/persons', data),
  update: (id, data) => api.put(`/persons/${id}`, data),
  delete: (id) => api.delete(`/persons/${id}`),
}

// 业务盘 API
export const businessAPI = {
  list: (params) => api.get('/business-dashboard', { params }),
  get: (deptId, params) => api.get(`/business-dashboard/${deptId}`, { params }),
  generateAll: (params) => scoringApi.post('/business-dashboard/generate', null, { params }),
  generateDept: (deptId, params) => scoringApi.post(`/business-dashboard/${deptId}/generate`, null, { params }),
  updateHighlight: (deptId, data) => api.patch(`/business-dashboard/${deptId}/highlight`, data),
}

// AI 模型管理 API
export const aiModelAPI = {
  list: () => api.get('/ai-models'),
  get: (id) => api.get(`/ai-models/${id}`),
  create: (data) => api.post('/ai-models', data),
  update: (id, data) => api.put(`/ai-models/${id}`, data),
  delete: (id) => api.delete(`/ai-models/${id}`),
  activate: (id) => api.post(`/ai-models/${id}/activate`),
  test: (data) => api.post('/ai-models/test', data),
}

// 内部考核 API
export const assessmentAPI = {
  list: (params) => api.get('/assessment/list', { params }),
  getDetail: (personId, params) => api.get(`/assessment/${personId}`, { params }),
}

export default api
