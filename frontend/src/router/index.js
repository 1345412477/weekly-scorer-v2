import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', name: 'Dashboard', component: () => import('../views/Dashboard.vue'), meta: { title: '仪表盘' } },
  { path: '/config', name: 'Config', component: () => import('../views/Config.vue'), meta: { title: '配置管理' } },
  { path: '/write', name: 'WriteReport', component: () => import('../views/WriteReport.vue'), meta: { title: '提交周报' } },
  { path: '/reports', name: 'Reports', component: () => import('../views/ReportList.vue'), meta: { title: '周报列表' } },
  { path: '/reports/:id', name: 'ReportDetail', component: () => import('../views/ReportDetail.vue'), meta: { title: '周报详情' } },
  { path: '/leaderboard', name: 'Leaderboard', component: () => import('../views/Leaderboard.vue'), meta: { title: '排行榜' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
