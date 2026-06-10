<template>
  <div class="app-container">
    <Toast ref="toastRef" position="top-right" />
    <MainLayout v-if="useAdminLayout">
      <router-view v-slot="{ Component, route: viewRoute }">
        <transition name="fade" mode="out-in">
          <keep-alive v-if="viewRoute.meta.keepAlive">
            <component :is="Component" />
          </keep-alive>
          <component v-else :is="Component" />
        </transition>
      </router-view>
    </MainLayout>
    <router-view v-else v-slot="{ Component, route: viewRoute }">
      <transition name="fade" mode="out-in">
        <keep-alive v-if="viewRoute.meta.keepAlive">
          <component :is="Component" />
        </keep-alive>
        <component v-else :is="Component" />
      </transition>
    </router-view>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import MainLayout from './layouts/MainLayout.vue'

const route = useRoute()
const toastRef = ref(null)
const useAdminLayout = computed(() => route.path.startsWith('/admin') && !route.meta.noLayout)

function showToast(message, severity = 'info') {
  if (toastRef.value) {
    toastRef.value.add({ severity, summary: message, life: 3000 })
  }
}

onMounted(() => {
  window.showToast = showToast
})
</script>
