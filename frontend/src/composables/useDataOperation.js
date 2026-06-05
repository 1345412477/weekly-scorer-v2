/**
 * 数据操作 Composable
 * 提供带状态反馈的数据操作能力
 */
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { emitDataChanged } from '../utils/dataEvents'

/**
 * 创建数据操作 hook
 * @returns {object}
 */
export function useDataOperation() {
  const toast = useToast()

  const operationInProgress = ref(false)
  const currentOperation = ref(null) // { type, message, eventType }

  /**
   * 执行数据操作，自动处理 loading 状态、错误提示和数据变更事件
   * @param {Function} operationFn - 异步操作函数
   * @param {object} options
   * @param {string} options.name - 操作名称（用于错误提示）
   * @param {string|string[]} options.eventTypes - 操作成功后触发的事件类型
   * @param {string} [options.successMsg] - 成功提示消息
   * @param {string} [options.errorMsg] - 失败提示消息
   * @returns {Promise<{success: boolean, data: any, error: any}>}
   */
  async function execute(operationFn, options = {}) {
    const { name = '操作', eventTypes = [], successMsg, errorMsg } = options

    operationInProgress.value = true
    currentOperation.value = { name, eventTypes }

    try {
      const result = await operationFn()

      // 触发数据变更事件
      const events = Array.isArray(eventTypes) ? eventTypes : [eventTypes]
      events.forEach(eventType => {
        if (eventType) {
          emitDataChanged(eventType, { source: name })
        }
      })

      if (successMsg) {
        toast.add({
          severity: 'success',
          summary: successMsg,
          life: 2000,
        })
      }

      return { success: true, data: result, error: null }
    } catch (e) {
      const message = e?.userMessage || errorMsg || `${name}失败`

      toast.add({
        severity: 'error',
        summary: message,
        detail: e?.response?.data?.detail || '',
        life: 4000,
      })

      return { success: false, data: null, error: e }
    } finally {
      operationInProgress.value = false
      currentOperation.value = null
    }
  }

  return {
    operationInProgress,
    currentOperation,
    execute,
  }
}
