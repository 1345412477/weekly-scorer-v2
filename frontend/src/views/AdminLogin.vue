<template>
  <div class="login-page">
    <section class="login-shell">
      <div class="login-hero">
        <span class="login-badge">Weekly Scorer</span>
        <h1>欢迎回到管理后台</h1>
        <p>统一管理周报提交、AI 评分、排行榜和系统配置，让团队周报质量更清晰。</p>
        <div class="login-points">
          <span><i class="pi pi-check-circle"></i> 数据看板</span>
          <span><i class="pi pi-check-circle"></i> 周报管理</span>
          <span><i class="pi pi-check-circle"></i> 评分配置</span>
        </div>
      </div>

      <Card class="login-card">
        <template #title>
          <div class="login-title">
            <span>管理员登录</span>
            <small>输入账号密码访问后台功能</small>
          </div>
        </template>
        <template #content>
          <form class="login-form" @submit.prevent="login">
            <div v-if="errorMessage" class="login-error" role="alert">
              <i class="pi pi-exclamation-triangle"></i>
              <span>{{ errorMessage }}</span>
            </div>
            <div class="field">
              <label>用户名</label>
              <InputText v-model="form.username" autocomplete="username" autofocus />
            </div>
            <div class="field">
              <label>密码</label>
              <Password v-model="form.password" autocomplete="current-password" toggleMask :feedback="false" />
            </div>
            <Button label="登录后台" icon="pi pi-lock-open" type="submit" :loading="loading" class="login-btn" />
            <Button label="返回普通用户入口" text @click="$router.push('/')" />
          </form>
        </template>
      </Card>
    </section>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import { authAPI } from '../api'
import { setAuth } from '../utils/auth'
import Card from 'primevue/card'
import Button from 'primevue/button'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'

const router = useRouter()
const toast = useToast()
const loading = ref(false)
const form = reactive({ username: 'admin', password: '' })
const errorMessage = ref('')

async function login() {
  errorMessage.value = ''
  if (!form.username?.trim()) {
    errorMessage.value = '请输入用户名'
    return
  }
  if (!form.password) {
    errorMessage.value = '请输入密码'
    return
  }
  loading.value = true
  try {
    const res = await authAPI.login({ username: form.username.trim(), password: form.password })
    setAuth(res.data.access_token, res.data.user)
    toast.add({ severity: 'success', summary: '登录成功，欢迎进入后台', life: 1800 })
    const redirect = router.currentRoute.value.query.redirect || '/admin/dashboard'
    router.replace(redirect)
  } catch (e) {
    errorMessage.value = e.userMessage || e.response?.data?.detail || '登录失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: var(--content-padding);
  background: var(--public-bg-gradient);
}

.login-shell {
  width: min(980px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1fr) 420px;
  gap: var(--spacing-xl);
  align-items: center;
}

.login-hero {
  padding: clamp(20px, 4vw, 42px);
}

.login-badge {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: var(--radius-full);
  background: var(--primary-bg);
  color: var(--primary-dark);
  font-size: var(--text-xs);
  font-weight: var(--font-bold);
}

.login-hero h1 {
  margin-top: var(--spacing-md);
  max-width: 520px;
  color: var(--text-primary);
  font-size: clamp(32px, 5vw, 58px);
  line-height: 1.05;
  letter-spacing: -0.06em;
}

.login-hero p {
  max-width: 520px;
  margin-top: var(--spacing-md);
  color: var(--text-secondary);
  font-size: var(--text-lg);
}

.login-points {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: var(--spacing-lg);
}

.login-points span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.68);
  color: var(--text-secondary);
  font-size: var(--text-sm);
  font-weight: var(--font-semibold);
}

.login-points i {
  color: var(--success);
}

.login-card {
  width: 100%;
  box-shadow: var(--shadow-lg);
}

.login-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.login-title small {
  color: var(--text-muted);
  font-size: var(--text-sm);
  font-weight: 400;
}

.login-form,
.field {
  display: grid;
  gap: 14px;
}

.field label {
  font-weight: var(--font-bold);
  color: var(--text-secondary);
}

.login-btn {
  margin-top: 8px;
}

/* PrimeVue Password 组件输入框撑满宽度 */
.field :deep(.p-password-input) {
  width: 100%;
}

.field :deep(input[type="text"]),
.field :deep(input[type="password"]) {
  width: 100%;
}

.login-error {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  margin-bottom: 16px;
  border-radius: var(--radius-md);
  background: #fff1f0;
  color: #cf1322;
  border: 1px solid #ffa39e;
  font-size: var(--text-sm);
  line-height: 1.5;
}

.login-error i {
  color: #cf1322;
  font-size: 16px;
  flex-shrink: 0;
}

@media (max-width: 860px) {
  .login-shell {
    grid-template-columns: 1fr;
  }

  .login-hero {
    padding: 0;
  }
}
</style>
