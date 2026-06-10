<template>
  <span :class="['grade-tag', gradeClass]">{{ displayGrade }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  grade: { type: String, default: '' },
})

const displayGrade = computed(() => props.grade || '-')
const gradeClass = computed(() => ({
  '优': 'grade-you',
  '良': 'grade-liang',
  '一般': 'grade-yiban',
  '差': 'grade-cha',
  S: 'grade-s',
  A: 'grade-a',
  B: 'grade-b',
  C: 'grade-c',
  D: 'grade-d',
}[props.grade] || ''))
</script>
