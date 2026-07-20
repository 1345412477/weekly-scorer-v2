import { createRouter, createWebHistory } from 'vue-router'
import { isAdminLoggedIn } from '../utils/auth'

const routes = [
  { path: '/', name: 'Home', component: () => import('../views/PublicHome.vue'), meta: { title: '智友辰周任务汇总系统', public: true, noLayout: true } },
  { path: '/admin/login', name: 'AdminLogin', component: () => import('../views/AdminLogin.vue'), meta: { title: '管理员登录', public: true, noLayout: true } },
  { path: '/admin', redirect: '/admin/dashboard', meta: { requiresAdmin: true } },
  { path: '/admin/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '仪表盘', requiresAdmin: true } },
  { path: '/admin/business-dashboard', name: 'BusinessDashboard', component: () => import('../views/BusinessDashboard.vue'), meta: { title: '业务盘', requiresAdmin: true } },
  { path: '/admin/config', name: 'Config', component: () => import('../views/Config.vue'), meta: { title: '系统设置', requiresAdmin: true } },
  { path: '/admin/reports', name: 'Reports', component: () => import('../views/ReportList.vue'), meta: { title: '周评列表', requiresAdmin: true } },
  { path: '/admin/reports/:id', name: 'ReportDetail', component: () => import('../views/ReportDetail.vue'), meta: { title: '周报详情', requiresAdmin: true } },
  { path: '/admin/wechat', name: 'WeChatData', component: () => import('../views/WeChatDataUpload.vue'), meta: { title: '企业微信数据上传', requiresAdmin: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.requiresAdmin && !isAdminLoggedIn()) {
    return { path: '/admin/login', query: { redirect: to.fullPath } }
  }
  if (to.path === '/admin/login' && isAdminLoggedIn()) {
    return '/admin/dashboard'
  }
})

export default router
