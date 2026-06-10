<template>
  <header :class="['app-page-header', `app-page-header-${variant}`, { compact }]">
    <div class="app-page-header-main">
      <span v-if="eyebrow" class="app-page-eyebrow">{{ eyebrow }}</span>
      <h1>{{ title }}</h1>
      <p v-if="subtitle" class="app-page-subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="app-page-actions">
      <slot name="actions" />
    </div>
  </header>
</template>

<script setup>
defineProps({
  eyebrow: { type: String, default: '' },
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  variant: { type: String, default: 'default' },
})
</script>
