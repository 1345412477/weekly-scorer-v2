/**
 * 时间处理工具函数
 * 用于处理 UTC 时间与北京时间的转换
 */

/**
 * 将时间字符串格式化为北京时间（YYYY-MM-DD HH:MM:SS）
 * @param {string} t - ISO 时间字符串
 * @returns {string} 格式化后的北京时间
 */
export function formatBeijingTime(t) {
  if (!t) return '-'
  try {
    const date = new Date(t)
    if (isNaN(date.getTime())) return '-'
    
    // 使用 toLocaleString 转换为北京时间
    return date.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).replace(/\//g, '-')
  } catch (e) {
    console.error('[TimeUtil] 时间格式化失败:', e)
    return '-'
  }
}

/**
 * 简化版本的时间格式化（仅到分钟）
 * @param {string} t - ISO 时间字符串
 * @returns {string} 格式化后的北京时间
 */
export function formatBeijingTimeShort(t) {
  if (!t) return '-'
  try {
    const date = new Date(t)
    if (isNaN(date.getTime())) return '-'
    
    return date.toLocaleString('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).replace(/\//g, '-')
  } catch (e) {
    console.error('[TimeUtil] 时间格式化失败:', e)
    return '-'
  }
}
