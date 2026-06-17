<template>
  <span :class="['score-badge', `score-badge-${size}`, { 'score-badge-zero': isZero }]">{{ displayScore }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: { type: [Number, String], default: '-' },
  size: { type: String, default: 'md' },
})

const numericScore = computed(() => {
  if (props.score === null || props.score === undefined || props.score === '' || props.score === '-') return null
  const n = Number(props.score)
  return isNaN(n) ? null : n
})

const isZero = computed(() => numericScore.value === 0)

const displayScore = computed(() => {
  if (numericScore.value === null) return '-'
  return Math.round(numericScore.value)
})
</script>
