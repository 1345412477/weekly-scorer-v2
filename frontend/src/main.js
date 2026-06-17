import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import ToastService from 'primevue/toastservice'
import ConfirmService from 'primevue/confirmationservice'
import Toast from 'primevue/toast'
import ConfirmDialog from 'primevue/confirmdialog'
import Tooltip from 'primevue/tooltip'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import 'primeicons/primeicons.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(PrimeVue, {
  theme: { preset: Aura, options: { darkModeSelector: 'none' } }
})
app.use(ToastService)
app.use(ConfirmService)
app.component('Toast', Toast)
app.component('ConfirmDialog', ConfirmDialog)
app.directive('tooltip', Tooltip)
app.mount('#app')
