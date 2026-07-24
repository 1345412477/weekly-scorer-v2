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
  theme: { preset: Aura, options: { darkModeSelector: 'none' } },
  locale: {
    startsWith: '始于',
    contains: '包含',
    notContains: '不包含',
    endsWith: '终于',
    equals: '等于',
    notEquals: '不等于',
    noFilter: '无筛选',
    lt: '小于',
    lte: '小于等于',
    gt: '大于',
    gte: '大于等于',
    dateIs: '日期等于',
    dateIsNot: '日期不等于',
    dateBefore: '日期早于',
    dateAfter: '日期晚于',
    clear: '清除',
    apply: '应用',
    matchAll: '全匹配',
    matchAny: '任意匹配',
    addRule: '添加规则',
    removeRule: '移除规则',
    accept: '是',
    reject: '否',
    choose: '选择',
    upload: '上传',
    cancel: '取消',
    completed: '已完成',
    pending: '待处理',
    fileSizeTypes: ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB'],
    dayNames: ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'],
    dayNamesShort: ['周日', '周一', '周二', '周三', '周四', '周五', '周六'],
    dayNamesMin: ['日', '一', '二', '三', '四', '五', '六'],
    monthNames: ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'],
    monthNamesShort: ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月'],
    chooseYear: '选择年份',
    chooseMonth: '选择月份',
    chooseDate: '选择日期',
    prevDecade: '上一个十年',
    nextDecade: '下一个十年',
    prevYear: '上一年',
    nextYear: '下一年',
    prevMonth: '上个月',
    nextMonth: '下个月',
    prevHour: '上一小时',
    nextHour: '下一小时',
    prevMinute: '上一分钟',
    nextMinute: '下一分钟',
    prevSecond: '上一秒',
    nextSecond: '下一秒',
    am: '上午',
    pm: '下午',
    today: '今天',
    weekHeader: '周',
    firstDayOfWeek: 1,
    dateFormat: 'yy-mm-dd',
    emptyMessage: '没有可用选项',
    emptyFilterMessage: '没有找到匹配项',
  }
})
app.use(ToastService)
app.use(ConfirmService)
app.component('Toast', Toast)
app.component('ConfirmDialog', ConfirmDialog)
app.directive('tooltip', Tooltip)
app.mount('#app')
