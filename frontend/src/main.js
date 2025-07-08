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

// 检查是否有cookie登录状态，如果有则自动登录（但不在登录页面执行，避免冲突）
router.isReady().then(() => {
  const currentPath = router.currentRoute.value.path;
  
  // 只在非登录页面执行cookie自动登录检查
  if (currentPath !== '/' && window.autoLoginCheck && window.autoLoginCheck()) {
    console.log('Cookie自动登录成功');
  }
  
  // 如果在登录页面，让LoginView组件处理自动登录逻辑
  if (currentPath === '/') {
    console.log('在登录页面，由LoginView处理自动登录');
  }
});

app.mount('#app')
