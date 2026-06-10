<template>
  <Card :class="['section-card', `section-card-${variant}`, { 'section-card-flush': flush }]">
    <template v-if="title || subtitle || $slots.actions" #title>
      <div class="section-card-header">
        <div>
          <h2 v-if="title">{{ title }}</h2>
          <p v-if="subtitle">{{ subtitle }}</p>
        </div>
        <div v-if="$slots.actions" class="section-card-actions">
          <slot name="actions" />
        </div>
      </div>
    </template>
    <template #content>
      <slot />
      <div v-if="$slots.footer" class="section-card-footer">
        <slot name="footer" />
      </div>
    </template>
  </Card>
</template>

<script setup>
import Card from 'primevue/card'

defineProps({
  title: { type: String, default: '' },
  subtitle: { type: String, default: '' },
  flush: { type: Boolean, default: false },
  variant: { type: String, default: 'default' },
})
</script>
