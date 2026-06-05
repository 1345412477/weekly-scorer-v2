/**
 * 数据变更事件系统
 * 用于在数据操作完成后通知各组件刷新数据
 */
import { ref } from 'vue'

// 数据变更事件类型
export const DataEventType = {
  REPORTS_CHANGED: 'reports:changed',
  CONFIG_CHANGED: 'config:changed',
  DEPARTMENTS_CHANGED: 'departments:changed',
  PERSONS_CHANGED: 'persons:changed',
  LEADERBOARD_CHANGED: 'leaderboard:changed',
  ALL_CHANGED: 'all:changed',
}

// 事件监听器映射
const listeners = new Map()

/**
 * 订阅数据变更事件
 * @param {string} eventType - 事件类型
 * @param {Function} callback - 回调函数，接收 { event, source, timestamp } 参数
 * @returns {Function} 取消订阅函数
 */
export function onDataChanged(eventType, callback) {
  if (!listeners.has(eventType)) {
    listeners.set(eventType, new Set())
  }
  listeners.get(eventType).add(callback)

  return () => {
    const set = listeners.get(eventType)
    if (set) {
      set.delete(callback)
    }
  }
}

/**
 * 触发数据变更事件
 * @param {string} eventType - 事件类型
 * @param {object} [payload={}] - 事件负载数据
 */
export function emitDataChanged(eventType, payload = {}) {
  const event = {
    event: eventType,
    timestamp: Date.now(),
    ...payload,
  }

  // 通知特定事件类型的监听器
  const specificListeners = listeners.get(eventType)
  if (specificListeners) {
    specificListeners.forEach(cb => {
      try {
        cb(event)
      } catch (e) {
        console.error(`[DataEvents] 事件处理错误 (${eventType}):`, e)
      }
    })
  }

  // 同时通知 ALL_CHANGED 监听器
  if (eventType !== DataEventType.ALL_CHANGED) {
    const allListeners = listeners.get(DataEventType.ALL_CHANGED)
    if (allListeners) {
      allListeners.forEach(cb => {
        try {
          cb(event)
        } catch (e) {
          console.error('[DataEvents] all:changed 事件处理错误:', e)
        }
      })
    }
  }
}

/**
 * 数据操作状态（用于全局反馈）
 */
export const dataOperationState = ref({
  active: false,
  message: '',
  type: null, // 'create' | 'update' | 'delete'
  progress: null, // 0-100
})

/**
 * 包裹数据操作，自动设置状态和触发事件
 * @param {Function} operationFn - 异步数据操作函数
 * @param {object} options
 * @param {string} options.message - 操作进行中的提示消息
 * @param {string} options.eventType - 操作成功后触发的事件类型
 * @param {string} [options.source] - 操作来源标识
 * @returns {Promise<any>} 操作结果
 */
export async function withDataOperation(operationFn, options = {}) {
  const { message = '数据更新中...', eventType, source } = options

  dataOperationState.value = {
    active: true,
    message,
    type: null,
    progress: null,
  }

  try {
    const result = await operationFn()

    if (eventType) {
      emitDataChanged(eventType, { source })
    }

    return result
  } finally {
    dataOperationState.value = {
      active: false,
      message: '',
      type: null,
      progress: null,
    }
  }
}

export default {
  DataEventType,
  onDataChanged,
  emitDataChanged,
  dataOperationState,
  withDataOperation,
}
