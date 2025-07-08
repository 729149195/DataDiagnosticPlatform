import './assets/main.css'

import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import store from './store' // 确保导入 store

const app = createApp(App)
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(key, component)
  }

app.use(router)
app.use(ElementPlus)
app.use(store)

// 暴露store和router给全局，供authManager使用
window.vueStore = store
window.vueRouter = router

// 检查是否有cookie登录状态，如果有则自动登录
if (window.autoLoginCheck && window.autoLoginCheck()) {
  console.log('自动登录成功')
  // 如果当前在登录页面且已登录，跳转到主页面
  if (router.currentRoute.value.path === '/') {
    router.push({ name: 'AnomalyLabelView' })
  }
}

app.mount('#app')
