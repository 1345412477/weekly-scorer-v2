<template>
  <div class="layout">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <div class="sidebar-header">
        <div class="logo">
          <span class="logo-icon">📊</span>
          <span class="logo-text">周报评分</span>
        </div>
        <span class="version-tag">v2</span>
      </div>

      <nav class="sidebar-nav">
        <router-link v-for="item in navItems" :key="item.path" :to="item.path"
          :class="['nav-item', { active: isActive(item.path) }]">
          <i :class="item.icon"></i>
          <span>{{ item.label }}</span>
          <span v-if="isActive(item.path)" class="nav-indicator"></span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <div class="footer-info">
          <span class="footer-dot"></span>
          <span>AI 评分引擎运行中</span>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="main-content">
      <slot />
    </main>
  </div>
</template>

<script setup>
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { path: '/dashboard', label: '仪表盘', icon: 'pi pi-chart-pie' },
  { path: '/write', label: '提交周报', icon: 'pi pi-upload' },
  { path: '/reports', label: '周报列表', icon: 'pi pi-list' },
  { path: '/leaderboard', label: '排行榜', icon: 'pi pi-trophy' },
  { path: '/config', label: '配置管理', icon: 'pi pi-cog' },
]

function isActive(path) {
  return route.path === path || route.path.startsWith(path + '/')
}
</script>

<style scoped>
/* ========== 布局 ========== */
.layout {
  display: flex;
  min-height: 100vh;
  background: var(--bg-body);
}

/* ========== 侧边栏 ========== */
.sidebar {
  width: 240px;
  background: var(--bg-sidebar);
  border-right: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
  transition: width var(--transition-normal), transform var(--transition-normal);
  box-shadow: 1px 0 0 rgba(0, 0, 0, 0.02);
}

.sidebar-header {
  padding: 24px 20px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-light);
}

.logo {
  display: flex;
  align-items: center;
  gap: 10px;
}

.logo-icon {
  font-size: 24px;
  line-height: 1;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.version-tag {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  background: var(--primary-bg);
  color: var(--primary);
  font-weight: 600;
  border: 1px solid rgba(91, 95, 199, 0.12);
}

/* ========== 导航 ========== */
.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 11px 16px;
  border-radius: var(--radius-md);
  color: var(--text-secondary);
  text-decoration: none;
  font-size: var(--text-base);
  font-weight: var(--font-medium);
  transition: all var(--transition-fast);
  white-space: nowrap;
  position: relative;
}

.nav-item:hover {
  background: var(--bg-card-hover);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--primary-bg);
  color: var(--primary);
  font-weight: var(--font-semibold);
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: var(--primary);
  border-radius: 0 4px 4px 0;
}

.nav-item i {
  font-size: 18px;
  width: 20px;
  text-align: center;
  flex-shrink: 0;
}

/* ========== 底部 ========== */
.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border-light);
}

.footer-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.footer-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--success);
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
  flex-shrink: 0;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ========== 主内容 ========== */
.main-content {
  flex: 1;
  margin-left: 240px;
  padding: var(--spacing-xl);
  min-height: 100vh;
  min-width: 0;
  max-width: 1600px;
}

/* ========== 响应式断点 ========== */
@media (max-width: 1024px) {
  .sidebar {
    width: 200px;
  }

  .main-content {
    margin-left: 200px;
    padding: var(--spacing-lg);
  }

  .nav-item {
    padding: 10px 12px;
    font-size: var(--text-sm);
  }

  .nav-item span:not(.logo-text) {
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

@media (max-width: 768px) {
  .sidebar {
    transform: translateX(-100%);
    width: 280px;
    box-shadow: var(--shadow-xl);
  }

  .sidebar.open {
    transform: translateX(0);
  }

  .main-content {
    margin-left: 0;
    padding: var(--spacing-md);
    padding-top: 60px;
  }

  .layout::before {
    content: '';
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    height: 56px;
    background: var(--bg-sidebar);
    border-bottom: 1px solid var(--border-light);
    z-index: 90;
  }
}
</style>
