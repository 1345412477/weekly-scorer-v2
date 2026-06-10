<template>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <span class="logo-icon"><i class="pi pi-chart-line"></i></span>
          <div>
            <span class="logo-text">周报评分</span>
            <span class="logo-subtitle">Admin Console</span>
          </div>
        </div>
      </div>

      <nav class="sidebar-nav">
        <router-link v-for="item in navItems" :key="item.path" :to="item.path"
          :class="['nav-item', { active: isActive(item.path) }]">
          <span class="nav-icon"><i :class="item.icon"></i></span>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="footer-info">
          <span class="footer-avatar">{{ (adminUser.username || '管')[0] }}</span>
          <div>
            <span class="footer-name">{{ adminUser.username || '管理员' }}</span>
            <span class="footer-role">系统管理</span>
          </div>
        </div>
        <Button label="退出" icon="pi pi-sign-out" text size="small" class="logout-btn" @click="logout" />
      </div>
    </aside>

    <section class="layout-body">
      <header class="topbar">
        <div>
          <span class="topbar-eyebrow">{{ currentMeta }}</span>
          <h1>{{ currentTitle }}</h1>
        </div>
        <div class="topbar-actions">
          <router-link to="/" class="public-entry">公共工作台</router-link>
          <Button icon="pi pi-sign-out" label="退出登录" outlined size="small" @click="logout" />
        </div>
      </header>

      <main class="main-content">
        <slot />
      </main>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Button from 'primevue/button'
import { clearAuth, getAdminUser } from '../utils/auth'

const route = useRoute()
const router = useRouter()
const adminUser = getAdminUser()

const navItems = [
  { path: '/admin/dashboard', label: '仪表盘', icon: 'pi pi-chart-pie' },
  { path: '/admin/reports', label: '周报列表', icon: 'pi pi-list' },
  { path: '/admin/config', label: '系统设置', icon: 'pi pi-cog' },
]

const currentTitle = computed(() => route.meta.title || '管理后台')
const currentMeta = computed(() => '管理后台')

function isActive(path) {
  return route.path === path || route.path.startsWith(path + '/')
}

function logout() {
  clearAuth()
  router.push('/admin/login')
}
</script>

<style scoped>
.layout {
  display: flex;
  min-height: 100vh;
  background: radial-gradient(circle at top right, rgba(79, 124, 255, 0.1), transparent 34%), var(--bg-body);
}

.sidebar {
  width: var(--sidebar-width);
  background: var(--bg-sidebar);
  backdrop-filter: blur(18px);
  border-right: 1px solid rgba(226, 232, 242, 0.78);
  display: flex;
  flex-direction: column;
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 100;
  box-shadow: 10px 0 32px rgba(23, 32, 51, 0.04);
}

.sidebar-header {
  padding: 24px 20px 18px;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-lg);
  background: linear-gradient(135deg, var(--primary), var(--accent));
  color: white;
  box-shadow: 0 14px 28px rgba(79, 124, 255, 0.25);
}

.logo-text,
.logo-subtitle,
.footer-name,
.footer-role {
  display: block;
}

.logo-text {
  color: var(--text-primary);
  font-size: var(--text-lg);
  font-weight: var(--font-bold);
  letter-spacing: -0.04em;
}

.logo-subtitle,
.footer-role {
  color: var(--text-muted);
  font-size: var(--text-xs);
}

.sidebar-nav {
  flex: 1;
  padding: 8px 14px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 46px;
  padding: 9px 12px;
  border-radius: var(--radius-lg);
  color: var(--text-secondary);
  font-size: var(--text-base);
  font-weight: var(--font-semibold);
  transition: background var(--transition-fast), color var(--transition-fast), transform var(--transition-fast);
}

.nav-icon {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: var(--radius-md);
  background: var(--surface-soft);
  color: var(--text-muted);
}

.nav-item:hover {
  background: rgba(79, 124, 255, 0.08);
  color: var(--text-primary);
  transform: translateX(2px);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(79, 124, 255, 0.14), rgba(32, 199, 181, 0.1));
  color: var(--primary-dark);
}

.nav-item.active .nav-icon {
  background: var(--primary);
  color: white;
}

.sidebar-footer {
  margin: 14px;
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-xl);
  background: rgba(255, 255, 255, 0.72);
}

.footer-info {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.footer-avatar {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-full);
  background: var(--primary-bg);
  color: var(--primary-dark);
  font-weight: var(--font-bold);
}

.footer-name {
  color: var(--text-primary);
  font-size: var(--text-sm);
  font-weight: var(--font-bold);
}

.logout-btn {
  width: 100%;
  justify-content: center;
}

.layout-body {
  width: calc(100% - var(--sidebar-width));
  margin-left: var(--sidebar-width);
  min-height: 100vh;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-md);
  min-height: 82px;
  padding: 18px var(--content-padding);
  border-bottom: 1px solid rgba(226, 232, 242, 0.74);
  background: rgba(245, 248, 252, 0.82);
  backdrop-filter: blur(18px);
}

.topbar-eyebrow {
  color: var(--text-muted);
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
}

.topbar h1 {
  color: var(--text-primary);
  font-size: var(--text-2xl);
  line-height: 1.1;
  letter-spacing: -0.05em;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.public-entry {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  background: white;
  color: var(--text-secondary);
  border: 1px solid var(--border-light);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
}

.main-content {
  padding: var(--content-padding);
}

@media (max-width: 1024px) {
  .layout {
    flex-direction: column;
  }

  .sidebar {
    position: sticky;
    top: 0;
    width: 100%;
    height: auto;
    inset: auto;
    border-right: 0;
    border-bottom: 1px solid var(--border-light);
  }

  .sidebar-header,
  .sidebar-footer {
    display: none;
  }

  .sidebar-nav {
    flex-direction: row;
    padding: 10px 12px;
    overflow-x: auto;
  }

  .nav-item {
    flex: 0 0 auto;
    min-height: 40px;
  }

  .layout-body {
    width: 100%;
    margin-left: 0;
  }
}

@media (max-width: 720px) {
  .topbar {
    align-items: flex-start;
    flex-direction: column;
    min-height: auto;
  }

  .topbar-actions {
    width: 100%;
    overflow-x: auto;
  }

  .public-entry {
    flex: 0 0 auto;
  }
}
</style>
