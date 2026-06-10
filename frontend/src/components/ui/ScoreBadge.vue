<template>
  <span :class="['score-badge', `score-badge-${size}`]">{{ displayScore }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  score: { type: [Number, String], default: '-' },
  size: { type: String, default: 'md' },
})

const displayScore = computed(() => {
  if (props.score === null || props.score === undefined || props.score === '') return '-'
  return props.score
})
</script>
