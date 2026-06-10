<template>
  <div class="app-empty-state">
    <i v-if="icon" :class="icon"></i>
    <h3>{{ title }}</h3>
    <p v-if="description">{{ description }}</p>
    <div v-if="$slots.actions" class="app-empty-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  icon: { type: String, default: 'pi pi-inbox' },
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '' },
})
</script>
