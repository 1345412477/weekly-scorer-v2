/**
 * 时间处理工具函数 - 全项目统一使用北京时间 (Asia/Shanghai / UTC+8)
 * 注意：后端存储的 DATETIME 已经是北京时间（无时区信息），因此前端拿到的
 * "YYYY-MM-DD HH:MM:SS" 字符串本身就是北京时间，应按本地时间语义直接解析，
 * 不要做额外时区换算。仅当字符串带 "Z" 或 "+08:00" 时按带时区解析。
 */

const TZ = 'Asia/Shanghai'

function _parseBeijingTime(t) {
  if (!t) return null
  // 若为 Date 对象直接用
  if (t instanceof Date && !isNaN(t.getTime())) return t
  // 若为时间戳(数字或纯数字字符串)
  if (typeof t === 'number' || /^\d{10,13}$/.test(String(t))) {
    const ms = String(t).length <= 10 ? Number(t) * 1000 : Number(t)
    return new Date(ms)
  }
  // 字符串：YYYY-MM-DD HH:MM:SS 或 YYYY-MM-DDTHH:MM:SS（无 Z / 无 + 偏移）
  // 直接 new Date 在不同浏览器可能被解析为本地时间，因此手动拆字段
  const s = String(t).trim()
  // 带 Z 的 UTC 时间 → new Date 自动处理
  if (s.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(s)) {
    return new Date(s)
  }
  // YYYY-MM-DD HH:MM:SS / YYYY-MM-DDTHH:MM:SS → 按北京时间本地解析
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})(?::(\d{2}))?/)
  if (m) {
    return new Date(
      Number(m[1]), Number(m[2]) - 1, Number(m[3]),
      Number(m[4]), Number(m[5]), Number(m[6] || 0)
    )
  }
  // 纯日期 YYYY-MM-DD
  const d = s.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (d) {
    return new Date(Number(d[1]), Number(d[2]) - 1, Number(d[3]))
  }
  return new Date(s)
}

function _fmtParts(date, opts) {
  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: TZ,
    hour12: false,
    ...opts,
  }).formatToParts(date)
  const map = {}
  parts.forEach(p => { map[p.type] = p.value })
  return map
}

function pad2(n) { return String(n).padStart(2, '0') }

/**
 * 格式化为北京时间（YYYY-MM-DD HH:MM:SS）
 */
export function formatBeijingTime(t) {
  const d = _parseBeijingTime(t)
  if (!d || isNaN(d.getTime())) return '-'
  const p = _fmtParts(d, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' })
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}`
}

/**
 * 简化版本（仅到分钟，不含秒）
 */
export function formatBeijingTimeShort(t) {
  const d = _parseBeijingTime(t)
  if (!d || isNaN(d.getTime())) return '-'
  const p = _fmtParts(d, { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`
}

/**
 * 仅日期（YYYY-MM-DD）
 */
export function formatBeijingDate(t) {
  const d = _parseBeijingTime(t)
  if (!d || isNaN(d.getTime())) return '-'
  const p = _fmtParts(d, { year: 'numeric', month: '2-digit', day: '2-digit' })
  return `${p.year}-${p.month}-${p.day}`
}

/**
 * 仅时间（HH:MM）
 */
export function formatBeijingHM(t) {
  const d = _parseBeijingTime(t)
  if (!d || isNaN(d.getTime())) return '-'
  const p = _fmtParts(d, { hour: '2-digit', minute: '2-digit' })
  return `${p.hour}:${p.minute}`
}

/**
 * 简化时间（月-日 时:分，用于列表紧凑显示）
 */
export function formatBeijingCompact(t) {
  const d = _parseBeijingTime(t)
  if (!d || isNaN(d.getTime())) return '-'
  const p = _fmtParts(d, { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  return `${p.month}-${p.day} ${p.hour}:${p.minute}`
}

/**
 * 获取当前北京时间的 Date 对象
 */
export function getBeijingNow() {
  const now = new Date()
  // 将当前 UTC 时间按北京时区解读
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: TZ,
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
    hour12: false,
  }).formatToParts(now)
  const map = {}
  parts.forEach(p => { map[p.type] = p.value })
  return new Date(
    Number(map.year), Number(map.month) - 1, Number(map.day),
    Number(map.hour), Number(map.minute), Number(map.second)
  )
}

/**
 * 获取当前北京时间的 ISO 日期字符串（YYYY-MM-DD）
 */
export function getBeijingTodayISO() {
  const d = getBeijingNow()
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`
}

/**
 * 获取当前北京时间的 YYYYMMDD 字符串（用于文件名）
 */
export function getBeijingDateFilename() {
  const d = getBeijingNow()
  return `${d.getFullYear()}${pad2(d.getMonth() + 1)}${pad2(d.getDate())}`
}

export default {
  formatBeijingTime,
  formatBeijingTimeShort,
  formatBeijingDate,
  formatBeijingHM,
  formatBeijingCompact,
  getBeijingNow,
  getBeijingTodayISO,
  getBeijingDateFilename,
}
