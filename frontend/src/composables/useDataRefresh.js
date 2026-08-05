/**
 * 数据自动刷新 Composable
 * 提供组件级别的数据变更订阅和自动刷新能力
 */
import { ref, onMounted, onUnmounted, getCurrentInstance } from 'vue'
import { onDataChanged, DataEventType, dataOperationState } from '../utils/dataEvents'

/**
 * 创建数据自动刷新 hook
 * @param {object} options
 * @param {Function} options.loadFn - 数据加载函数
 * @param {string|string[]} options.watchEvents - 需要监听的数据变更事件类型
 * @param {number} [options.debounceMs=300] - 防抖延迟（毫秒）
 * @param {boolean} [options.autoLoad=true] - 是否在挂载时自动加载
 * @returns {object}
 */
export function useDataRefresh(options = {}) {
  const {
    loadFn,
    watchEvents = [],
    debounceMs = 300,
    autoLoad = true,
  } = options

  const loading = ref(false)
  const lastRefreshTime = ref(null)
  const refreshError = ref(null)
  const refreshCount = ref(0)

  const eventTypes = Array.isArray(watchEvents) ? watchEvents : [watchEvents]

  let unsubscribers = []
  let debounceTimer = null

  /**
   * 执行数据加载
   */
  async function refresh() {
    if (!loadFn) return

    loading.value = true
    refreshError.value = null

    try {
      await loadFn()
      lastRefreshTime.value = new Date()
      refreshCount.value++
    } catch (e) {
      refreshError.value = e
      console.error('[useDataRefresh] 数据刷新失败:', e)
    } finally {
      loading.value = false
    }
  }

  /**
   * 监听数据变更事件并自动刷新
   */
  function handleDataChanged(event) {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }

    debounceTimer = setTimeout(() => {
      refresh()
    }, debounceMs)
  }

  /**
   * 手动触发刷新
   */
  async function forceRefresh() {
    if (debounceTimer) {
      clearTimeout(debounceTimer)
    }
    await refresh()
  }

  // 注册事件监听
  const instance = getCurrentInstance()
  if (instance) {
    eventTypes.forEach(eventType => {
      if (eventType) {
        const unsub = onDataChanged(eventType, handleDataChanged)
        unsubscribers.push(unsub)
      }
    })

    // 在 onUnmounted 中注销监听
    onUnmounted(() => {
      unsubscribers.forEach(fn => fn())
      unsubscribers = []
      if (debounceTimer) {
        clearTimeout(debounceTimer)
      }
    })
  }

  // 挂载时自动加载
  if (autoLoad && instance) {
    onMounted(() => {
      refresh()
    })
  }

  return {
    loading,
    lastRefreshTime,
    refreshError,
    refreshCount,
    refresh: forceRefresh,
    dataOperationState,
  }
}

export function getDashboardEvents() {
  return [DataEventType.REPORTS_CHANGED, DataEventType.CONFIG_CHANGED, DataEventType.ALL_CHANGED]
}

export function getConfigEvents() {
  return [DataEventType.DEPARTMENTS_CHANGED, DataEventType.PERSONS_CHANGED]
}

export { DataEventType }
