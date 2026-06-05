<template>
  <div class="app-container">
    <Toast ref="toastRef" position="top-right" />
    <MainLayout>
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <keep-alive>
            <component :is="Component" />
          </keep-alive>
        </transition>
      </router-view>
    </MainLayout>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import MainLayout from './layouts/MainLayout.vue'

const toastRef = ref(null)

function showToast(message, severity = 'info') {
  if (toastRef.value) {
    toastRef.value.add({ severity, summary: message, life: 3000 })
  }
}

onMounted(() => {
  window.showToast = showToast
})
</script>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
