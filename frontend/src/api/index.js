import axios from 'axios'

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
  headers: {
    'Content-Type': 'application/json',
  },
})

const cache = new Map()
const CACHE_TTL = 60000

function getCacheKey(url, params) {
  return `${url}?${JSON.stringify(params)}`
}

api.interceptors.request.use(
  config => {
    if (config.method === 'get' && config.cache !== false) {
      const key = getCacheKey(config.url, config.params)
      const cached = cache.get(key)
      if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        // 标记为缓存命中，而不是取消请求
        config._cacheHit = true
        config._cachedData = cached.data
        return config
      }
    }
    return config
  },
  error => Promise.reject(error)
)

api.interceptors.response.use(
  res => {
    // 检查是否是缓存命中
    if (res.config._cacheHit) {
      return res.config._cachedData
    }
    
    if (res.config.method === 'get' && res.config.cache !== false) {
      const key = getCacheKey(res.config.url, res.config.params)
      cache.set(key, { timestamp: Date.now(), data: res })
    }
    return res
  },
  err => {
    // 忽略取消的请求（不再使用取消机制处理缓存）
    if (axios.isCancel(err)) {
      return Promise.resolve(null)
    }
    
    const status = err.response?.status
    const detail = err.response?.data?.detail
    const errors = err.response?.data?.errors
    
    let msg = '请求失败，请稍后重试'
    if (status === 400) {
      msg = errors ? errors.join('; ') : detail || '请求参数错误'
    } else if (status === 404) {
      msg = detail || '资源不存在'
    } else if (status === 503) {
      msg = detail || '服务暂时不可用'
    } else if (detail) {
      msg = detail
    } else if (!err.response) {
      // 网络错误或服务器无响应
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
    
    console.error('[API Error]', { status, msg, code: err.code, message: err.message })
    
    if (typeof window !== 'undefined' && window.showToast) {
      window.showToast(msg, 'error')
    }
    
    return Promise.reject({ ...err, userMessage: msg })
  }
)

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

export const configAPI = {
  get: () => api.get('/config', { cache: false }),
  save: (data) => api.put('/config', data),
  test: (data) => api.post('/config/test', data),
  aiStatus: () => api.get('/config/ai-status', { cache: false }),
  dataStatus: () => api.get('/config/data-status', { cache: false }),
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
  submit: (id) => api.post(`/reports/${id}/submit`),
  delete: (id) => api.delete(`/reports/${id}`),
  batchDelete: (ids) => api.delete('/reports/batch', { params: { report_ids: ids } }),
  download: (id) => api.get(`/reports/${id}/download`, { responseType: 'blob' }),
  export: (params) => api.get('/reports/export', { params, responseType: 'blob' }),
  downloadTemplate: () => api.get('/reports/template/download', { responseType: 'blob' }),
  upload: (formData) => uploadApi.post('/reports/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
}

export const leaderboardAPI = {
  get: (params) => api.get('/leaderboard', { params }),
  stats: () => api.get('/leaderboard/stats'),
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

export default api
