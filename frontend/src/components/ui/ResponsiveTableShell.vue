<template>
  <section class="responsive-table-shell">
    <div v-if="$slots.header" class="responsive-table-header">
      <slot name="header" />
    </div>
    <div class="responsive-table-scroll">
      <slot />
    </div>
  </section>
</template>
