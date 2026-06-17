<template>
  <div :class="['workspace-page', { 'admin-workspace': isAdminMode }]">
    <PageHeader
      v-if="!isAdminMode"
      variant="public"
      title="轻松提交周报，实时查看评分"
      subtitle="选择提交人、上传周报文件、查看 AI 评分与团队排行榜，整个流程在一个页面完成。"
    >
      <template #actions>
        <Button label="管理员登录" icon="pi pi-lock" outlined @click="$router.push('/admin/login')" />
      </template>
    </PageHeader>

    <section v-if="!isAdminMode" class="workflow-strip">
      <div v-for="item in workflow" :key="item.title" class="workflow-item">
        <span class="workflow-icon"><i :class="item.icon"></i></span>
        <div>
          <strong>{{ item.title }}</strong>
          <p>{{ item.desc }}</p>
        </div>
      </div>
    </section>

    <main class="workspace-grid">
      <section class="workspace-section upload-section">
        <div class="workspace-section-heading">
          <span class="section-kicker">第一步</span>
          <h2>提交周报</h2>
          <p>先选择提交人并上传周报，评分完成后下方排行榜会同步刷新。</p>
        </div>
        <WriteReport embedded />
      </section>
      <section class="workspace-section ranking-section">
        <div class="workspace-section-heading ranking-heading">
          <span class="section-kicker">结果分析</span>
          <h2>团队排行与评分分布</h2>
          <p>集中查看本期评分记录、前三名和图表分析，保持在同一工作台内完成闭环。</p>
        </div>
        <Leaderboard embedded />
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import Button from 'primevue/button'
import PageHeader from '../components/ui/PageHeader.vue'
import WriteReport from './WriteReport.vue'
import Leaderboard from './Leaderboard.vue'

const route = useRoute()
const isAdminMode = computed(() => route.path.startsWith('/admin'))

const workflow = [
  { title: '选择身份', desc: '从人员列表中选择提交人并自动匹配部门', icon: 'pi pi-user' },
  { title: '上传文件', desc: '支持 Excel、Word、PDF 周报文件', icon: 'pi pi-cloud-upload' },
  { title: '查看结果', desc: '评分、等级、排行和图表实时更新', icon: 'pi pi-chart-bar' },
]
</script>

<style scoped>
.workspace-page {
  --workspace-max-width: 1480px;
  min-height: 100vh;
  padding: clamp(16px, 2.2vw, 28px);
  background: var(--public-bg-gradient);
}

.admin-workspace {
  min-height: auto;
  padding: 0;
  background: transparent;
}

.workspace-page :deep(.app-page-header),
.workflow-strip,
.workspace-grid {
  max-width: var(--workspace-max-width);
  margin-left: auto;
  margin-right: auto;
}

.workspace-page :deep(.app-page-header-public) {
  align-items: center;
  margin-bottom: var(--spacing-md);
  padding: clamp(16px, 2vw, 22px) clamp(18px, 2.4vw, 28px);
  border-color: rgba(255, 255, 255, 0.64);
  border-radius: var(--radius-xl);
  background: rgba(255, 255, 255, 0.66);
  box-shadow: var(--shadow-xs);
}

.workspace-page :deep(.app-page-header-public::before) {
  opacity: 0.46;
}

.workspace-page :deep(.app-page-header-public h1) {
  font-size: clamp(22px, 2.25vw, 32px);
  letter-spacing: -0.04em;
}

.workspace-page :deep(.app-page-header-public .app-page-subtitle) {
  max-width: 660px;
  margin-top: 6px;
  font-size: var(--text-sm);
  line-height: 1.55;
}

.workflow-strip {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md);
}

.workflow-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.58);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.46);
  box-shadow: none;
  backdrop-filter: blur(12px);
}

.workflow-icon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: var(--radius-md);
  background: rgba(79, 124, 255, 0.09);
  color: var(--primary);
  font-size: var(--text-sm);
}

.workflow-item strong {
  display: block;
  color: var(--text-primary);
  font-size: var(--text-sm);
}

.workflow-item p {
  margin-top: 1px;
  color: var(--text-muted);
  font-size: var(--text-xs);
  line-height: 1.45;
}

.workspace-grid {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(520px, 0.96fr) minmax(620px, 1.04fr);
  gap: clamp(18px, 2vw, 28px);
  align-items: stretch;
}

.workspace-section {
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: clamp(18px, 2vw, 26px);
  border: 1px solid rgba(255, 255, 255, 0.76);
  border-radius: var(--radius-2xl);
  background: rgba(255, 255, 255, 0.62);
  box-shadow: var(--shadow-xs);
  backdrop-filter: blur(14px);
}

.workspace-section-heading {
  margin-bottom: var(--spacing-md);
}

.workspace-section-heading h2 {
  margin: 2px 0 4px;
  color: var(--text-primary);
  font-size: var(--text-2xl);
  line-height: 1.15;
  letter-spacing: -0.04em;
}

.workspace-section-heading p {
  color: var(--text-secondary);
  font-size: var(--text-sm);
  line-height: 1.6;
}

.section-kicker {
  color: var(--primary);
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
}

.ranking-section {
  margin-top: 0;
}

.ranking-heading {
  margin-bottom: var(--spacing-sm);
}

.workspace-section > :deep(.write-report),
.workspace-section > :deep(.leaderboard) {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.workspace-section > :deep(.write-report .upload-layout),
.workspace-section > :deep(.leaderboard .content-layout) {
  flex: 1;
}

.workspace-section :deep(.upload-layout),
.workspace-section :deep(.content-layout),
.workspace-section :deep(.filter-bar) {
  width: 100%;
}

.workspace-section :deep(.upload-layout),
.workspace-section :deep(.content-layout) {
  grid-template-columns: minmax(0, 1fr);
}

.workspace-section :deep(.upload-layout) {
  gap: var(--spacing-lg);
}

.workspace-section :deep(.left-panel) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--spacing-md);
}

.workspace-section :deep(.left-panel .step-card:nth-child(3)) {
  grid-column: 1 / -1;
}

.workspace-section :deep(.step-card[style]),
.workspace-section :deep(.chart-card[style]) {
  margin-top: 0 !important;
}

.workspace-section :deep(.step-card .p-card-body),
.workspace-section :deep(.preview-card .p-card-body),
.workspace-section :deep(.side-card .p-card-body) {
  padding: var(--spacing-md);
}

.workspace-section :deep(.upload-area) {
  min-height: 146px;
}

.workspace-section :deep(.side-panel) {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--spacing-md);
}

.workspace-section :deep(.chart-container) {
  height: 150px;
  min-height: 136px;
}

.workspace-section :deep(.chart-empty-hint) {
  min-height: 70px;
}

.admin-workspace :deep(.app-page-header-public) {
  display: none;
}

@media (max-width: 1180px) {
  .workspace-grid {
    grid-template-columns: minmax(0, 1fr);
    align-items: start;
  }

  .workspace-section {
    height: auto;
  }
}

@media (max-width: 960px) {
  .workflow-strip {
    grid-template-columns: 1fr;
  }

  .workspace-section :deep(.left-panel),
  .workspace-section :deep(.side-panel) {
    grid-template-columns: 1fr;
  }

  .workspace-section :deep(.left-panel .step-card:nth-child(3)) {
    grid-column: auto;
  }
}

@media (max-width: 768px) {
  .workspace-page {
    padding: 14px;
  }

  .admin-workspace {
    padding: 0;
  }

  .workspace-page :deep(.app-page-header-public) {
    align-items: flex-start;
    padding: var(--spacing-md);
  }

  .workspace-grid {
    gap: var(--spacing-md);
  }

  .workspace-section {
    padding: var(--spacing-md);
  }

  .ranking-section {
    margin-top: 0;
  }
}
</style>
