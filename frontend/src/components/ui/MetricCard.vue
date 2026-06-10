<template>
  <article class="metric-card" :style="styleVars">
    <div class="metric-icon">
      <i :class="icon"></i>
    </div>
    <div class="metric-content">
      <span class="metric-label">{{ label }}</span>
      <strong class="metric-value">{{ value }}</strong>
      <span v-if="trend" class="metric-trend">{{ trend }}</span>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], default: '-' },
  icon: { type: String, default: 'pi pi-chart-line' },
  color: { type: String, default: 'var(--primary)' },
  bg: { type: String, default: 'var(--primary-bg)' },
  trend: { type: String, default: '' },
})

const styleVars = computed(() => ({
  '--metric-color': props.color,
  '--metric-bg': props.bg,
}))
</script>
