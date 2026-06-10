<template>
  <span :class="['status-pill', `status-${variant}`]">{{ label }}</span>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  variant: { type: String, default: 'info' },
})
</script>
