import { nextTick, onBeforeUnmount, shallowRef } from 'vue'
import * as echarts from 'echarts'

export function useEChart() {
  const chart = shallowRef(null)
  let resizeHandler = null

  async function render(elRef, option) {
    await nextTick()
    const el = elRef?.value || elRef
    if (!el) return

    if (!chart.value) {
      chart.value = echarts.init(el)
      resizeHandler = () => chart.value?.resize()
      window.addEventListener('resize', resizeHandler)
    }

    chart.value.setOption(option, true)
    chart.value.resize()
  }

  function resize() {
    chart.value?.resize()
  }

  function dispose() {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
    chart.value?.dispose()
    chart.value = null
  }

  onBeforeUnmount(dispose)

  return { chart, render, resize, dispose }
}
