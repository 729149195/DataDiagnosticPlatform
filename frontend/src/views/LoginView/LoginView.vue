<template>
  <div class="login-page">
    <div class="background-shapes">
      <div class="shape"></div>
      <div class="shape"></div>
      <div class="shape"></div>
      <div class="shape"></div>
    </div>
    <div class="brand-logo">
      <div class="logo-text">DataDiagnostic</div>
    </div>
    <div class="login-container">
      <h2>欢迎登录</h2>
      <p class="subtitle">登录您的账号以继续使用</p>
      <form @submit.prevent="handleLogin">
        <div class="form-group" :class="{ 'has-error': formErrors.username }">
          <label for="username">用户名</label>
          <div class="input-wrapper">
            <span class="input-icon">👤</span>
            <input id="username" v-model="username" placeholder="请输入用户名" autocomplete="username"
              @focus="clearError('username')" />
            <span class="error-message" v-if="formErrors.username">{{ formErrors.username }}</span>
          </div>
        </div>
        <div class="form-group" :class="{ 'has-error': formErrors.password }">
          <label for="password">密码</label>
          <div class="input-wrapper">
            <span class="input-icon">🔒</span>
            <input :type="showPassword ? 'text' : 'password'" id="password" v-model="password" placeholder="请输入密码"
              autocomplete="current-password" @focus="clearError('password')" />
            <span v-if="password" class="password-toggle" @click="togglePassword">
              <svg v-if="showPassword" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24"
                fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <svg v-else xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path
                  d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            </span>
            <span class="error-message" v-if="formErrors.password">{{ formErrors.password }}</span>
          </div>
        </div>
        <button type="submit" class="login-button" :class="{ 'loading': isLoading }" :disabled="isLoading">
          <span>{{ isLoading ? '登录中' : '登录' }}</span>
          <div class="button-loader"></div>
        </button>
      </form>
    </div>
    <footer class="login-footer">
      <p>© 2025 DataDiagnostic Platform. All rights reserved.</p>
    </footer>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
  background: linear-gradient(145deg, rgba(245, 247, 250, 0.8) 0%, rgba(228, 231, 235, 0.8) 100%);
  position: relative;
  overflow: hidden;
  padding: 20px;
  backdrop-filter: blur(10px);
  user-select: none;
}

/* 添加动态背景网格 */
.login-page::before {
  content: '';
  position: absolute;
  width: 200%;
  height: 200%;
  top: -50%;
  left: -50%;
  background: linear-gradient(45deg,
      transparent 46%,
      rgba(26, 115, 232, 0.05) 47%,
      rgba(26, 115, 232, 0.05) 53%,
      transparent 54%);
  background-size: 60px 60px;
  animation: moveGrid 20s linear infinite;
  opacity: 0.4;
  backdrop-filter: blur(5px);
}

/* 修改浮动光效元素 */
.login-page::after {
  content: '';
  position: absolute;
  width: 120%;
  height: 120%;
  top: -10%;
  left: -10%;
  background:
    radial-gradient(circle at 20% 35%, rgba(26, 115, 232, 0.15) 0%, transparent 25%),
    radial-gradient(circle at 75% 44%, rgba(66, 133, 244, 0.12) 0%, transparent 20%),
    radial-gradient(circle at 40% 60%, rgba(219, 68, 55, 0.08) 0%, transparent 30%),
    radial-gradient(circle at 80% 70%, rgba(15, 157, 88, 0.08) 0%, transparent 25%);
  animation: floatBackground 15s ease-in-out infinite alternate;
  backdrop-filter: blur(8px);
}

/* 添加动态装饰元素 */
.background-shapes {
  position: absolute;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  overflow: hidden;
  pointer-events: none;
}

.shape {
  position: absolute;
  border-radius: 50%;
  background: linear-gradient(45deg, rgba(26, 115, 232, 0.15), rgba(66, 133, 244, 0.15));
  animation: float 10s ease-in-out infinite;
  backdrop-filter: blur(4px);
}

.shape:nth-child(1) {
  width: 150px;
  height: 150px;
  top: 15%;
  left: 10%;
  animation-delay: 0s;
}

.shape:nth-child(2) {
  width: 100px;
  height: 100px;
  top: 20%;
  right: 15%;
  animation-delay: -2s;
  background: linear-gradient(45deg, rgba(219, 68, 55, 0.1), rgba(244, 180, 0, 0.1));
}

.shape:nth-child(3) {
  width: 80px;
  height: 80px;
  bottom: 20%;
  left: 20%;
  animation-delay: -4s;
  background: linear-gradient(45deg, rgba(15, 157, 88, 0.1), rgba(66, 133, 244, 0.1));
}

.shape:nth-child(4) {
  width: 120px;
  height: 120px;
  bottom: 15%;
  right: 20%;
  animation-delay: -6s;
  background: linear-gradient(45deg, rgba(244, 180, 0, 0.1), rgba(219, 68, 55, 0.1));
}

@keyframes moveGrid {
  0% {
    transform: translate(0, 0) rotate(0deg);
  }

  100% {
    transform: translate(-60px, -60px) rotate(3deg);
  }
}

@keyframes floatBackground {
  0% {
    transform: translate(0, 0) rotate(0deg);
  }

  100% {
    transform: translate(20px, 20px) rotate(1deg);
  }
}

@keyframes float {

  0%,
  100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }

  25% {
    transform: translate(10px, -10px) rotate(2deg) scale(1.02);
  }

  50% {
    transform: translate(-5px, 15px) rotate(-1deg) scale(0.98);
  }

  75% {
    transform: translate(-10px, -5px) rotate(1deg) scale(1.01);
  }
}

/* 保持原有样式 */
.brand-logo {
  margin-bottom: 2.5rem;
  text-align: center;
  position: relative;
  z-index: 1;
}

.logo-text {
  font-size: 36px;
  font-weight: 900;
  background: linear-gradient(300deg,
      #1a73e8 0%,
      #4285f4 30%,
      #34a853 70%,
      #1a73e8 100%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  letter-spacing: -0.5px;
  user-select: none;
  animation: shine 8s linear infinite;
  text-shadow: 0 0 15px rgba(26, 115, 232, 0.1);
  filter: drop-shadow(0 0 3px rgba(52, 168, 83, 0.15));
  position: relative;
}

.logo-text::after {
  content: 'DataDiagnostic';
  position: absolute;
  left: 0;
  top: 0;
  z-index: -1;
  background: none;
  -webkit-text-fill-color: transparent;
  filter: blur(6px) brightness(150%);
  opacity: 0.2;
}

@keyframes shine {
  to {
    background-position: 200% center;
  }
}

.login-container {
  width: 100%;
  max-width: 400px;
  padding: 48px;
  background: rgba(255, 255, 255, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-radius: 20px;
  box-shadow:
    0 10px 25px rgba(0, 0, 0, 0.05),
    0 20px 48px rgba(0, 0, 0, 0.05),
    0 1px 4px rgba(0, 0, 0, 0.1);
  text-align: center;
  position: relative;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  z-index: 1;
  animation: containerAppear 0.6s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.login-container:hover {
  transform: translateY(-2px);
  box-shadow:
    0 16px 32px rgba(0, 0, 0, 0.06),
    0 32px 64px rgba(0, 0, 0, 0.06),
    0 1px 4px rgba(0, 0, 0, 0.1);
}

h2 {
  font-size: 28px;
  color: #202124;
  margin-bottom: 12px;
  font-weight: 600;
  user-select: none;
}

.subtitle {
  color: #5f6368;
  font-size: 15px;
  margin-bottom: 36px;
  user-select: none;
}

.form-group {
  position: relative;
  margin-bottom: 28px;
  text-align: left;
}

label {
  display: block;
  margin-bottom: 10px;
  font-weight: 500;
  color: #202124;
  font-size: 14px;
  transition: all 0.3s ease;
  user-select: none;
}

.input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.input-icon {
  position: absolute;
  left: 16px;
  color: #5f6368;
  font-size: 16px;
  opacity: 0.8;
  z-index: 2;
  transition: all 0.3s ease;
  pointer-events: none;
}

.form-group:focus-within .input-icon {
  color: #1a73e8;
  opacity: 1;
  transform: scale(1.1);
}

input {
  width: 100%;
  padding: 14px 16px 14px 48px;
  border: 1px solid #dadce0;
  border-radius: 12px;
  font-size: 16px;
  color: #202124;
  background: #ffffff;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  transform-origin: top;
  position: relative;
  z-index: 1;
  user-select: text;
}

input:hover {
  border-color: #1a73e8;
  box-shadow: 0 1px 2px rgba(26, 115, 232, 0.1);
}

input:focus {
  border-color: #1a73e8;
  box-shadow: 0 0 0 2px rgba(26, 115, 232, 0.2);
  outline: none;
  transform: scale(1.01);
}

input::placeholder {
  color: #80868b;
}

.login-button {
  width: 100%;
  padding: 14px 24px;
  margin-top: 12px;
  background: #1a73e8;
  color: white;
  border: none;
  border-radius: 12px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  position: relative;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  box-shadow: 0 2px 4px rgba(26, 115, 232, 0.2);
  overflow: hidden;
}

.login-button:hover {
  background: #1557b0;
  box-shadow: 0 4px 8px rgba(26, 115, 232, 0.3);
  transform: translateY(-1px);
}

.login-button:active {
  background: #174ea6;
  transform: translateY(1px);
  box-shadow: 0 2px 4px rgba(26, 115, 232, 0.2);
}

.button-loader {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.5);
  border-radius: 50%;
  border-top-color: #ffffff;
  display: none;
  animation: spin 0.8s linear infinite;
}

.login-button.loading {
  background: linear-gradient(45deg, #1557b0, #1a73e8);
}

.login-button.loading .button-loader {
  display: block;
}

.login-button.loading span {
  opacity: 0;
}

.login-footer {
  margin-top: 2.5rem;
  color: #5f6368;
  font-size: 13px;
  text-align: center;
  position: relative;
  z-index: 2;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 添加响应式设计 */
@media (max-width: 480px) {
  .login-container {
    padding: 36px 24px;
  }

  .logo-text {
    font-size: 28px;
  }

  h2 {
    font-size: 24px;
  }

  .subtitle {
    font-size: 14px;
  }
}

.logo-subtitle {
  font-size: 16px;
  color: #5f6368;
  margin-top: 8px;
  opacity: 0.8;
  font-weight: 500;
  user-select: none;
}

.form-group.has-error input {
  border-color: #d93025;
  background-color: #fff8f7;
}

.form-group.has-error input:focus {
  border-color: #d93025;
  box-shadow: 0 0 0 2px rgba(217, 48, 37, 0.2);
}

.error-message {
  position: absolute;
  left: 0;
  bottom: -20px;
  font-size: 12px;
  color: #d93025;
  animation: fadeIn 0.2s ease-in-out;
}

.login-button::after {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 120%;
  height: 120%;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.2) 0%, transparent 60%);
  transform: translate(-50%, -50%) scale(0);
  opacity: 0;
  transition: transform 0.5s ease-out, opacity 0.3s ease-out;
}

.login-button:hover::after {
  transform: translate(-50%, -50%) scale(2);
  opacity: 1;
}

.login-button:disabled {
  background: #ccc;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 添加输入框聚焦时的标签动画 */
.form-group:focus-within label {
  color: #1a73e8;
  transform: translateX(4px);
}

@keyframes containerAppear {
  from {
    opacity: 0;
    transform: translateY(20px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.form-group.has-error .input-icon {
  color: #d93025;
  opacity: 1;
}

.password-toggle {
  position: absolute;
  right: 16px;
  color: #5f6368;
  cursor: pointer;
  opacity: 0.6;
  z-index: 2;
  transition: all 0.2s ease;
  user-select: none;
  display: flex;
  align-items: center;
  padding: 4px;
}

.password-toggle:hover {
  opacity: 1;
}

.form-group:focus-within .password-toggle {
  color: #1a73e8;
}

input[type="password"] {
  letter-spacing: 0.1em;
}
</style>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useStore } from 'vuex';

const store = useStore();
const username = ref('qidongkai');
const password = ref('123');
const router = useRouter();
const isLoading = ref(false);
const showPassword = ref(false);
const formErrors = reactive({
  username: '',
  password: ''
});

const togglePassword = () => {
  showPassword.value = !showPassword.value;
};

const clearError = (field) => {
  formErrors[field] = '';
};

const validateForm = () => {
  let isValid = true;

  if (!username.value) {
    formErrors.username = '请输入用户名';
    isValid = false;
  }

  if (!password.value) {
    formErrors.password = '请输入密码';
    isValid = false;
  }

  return isValid;
};

const handleLogin = async () => {
  if (!validateForm()) return;

  isLoading.value = true;
  try {
    const response = await fetch('http://192.168.20.49:5000/api/verify-user', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      credentials: 'include',
      mode: 'cors',
      body: JSON.stringify({
        username: username.value,
        password: password.value,
      }),
    });

    const data = await response.json();

    if (data.success) {
      // 登录成功后设置cookie
      if (window.AuthManager) {
        window.AuthManager.setAuthData(username.value, data.authority || 0);
      }
      
      store.commit("setperson", username.value);
      store.commit("setUserMessage", data.message);
      store.commit("setauthority", data.authority || 0);
      router.push({ name: 'AnomalyLabelView' });
    } else {
      formErrors.password = data.message || '登录失败，请重试';
    }
  } catch (error) {
    formErrors.password = '登录失败，请重试';
  } finally {
    isLoading.value = false;
  }
};

// 组件挂载时检查登录状态
onMounted(async () => {
  // 1. 首先检查URL参数
  const urlParams = new URLSearchParams(window.location.search);
  const urlUsername = urlParams.get('username') || urlParams.get('user');
  const action = urlParams.get('action');
  
  // 如果是注销操作
  if (action === 'logout') {
    console.log('检测到注销操作，执行注销...');
    if (window.platformLogout) {
      await window.platformLogout();
    } else if (window.AuthManager) {
      window.AuthManager.clearAuthData();
      store.commit('setperson', '');
      store.commit('setauthority', 0);
      store.commit('setUserMessage', '');
    }
    // 清除URL参数
    const newUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
    window.history.replaceState({}, document.title, newUrl);
    console.log('注销操作完成');
    return;
  }
  
  // 2. 检查URL参数是否有用户名（主平台跳转登录）
  if (urlUsername) {
    console.log('检测到URL参数用户名:', urlUsername);
    // 使用URL参数中的用户名自动登录
    if (window.platformLogin) {
      isLoading.value = true;
      try {
        const result = await window.platformLogin(urlUsername);
        if (result.success) {
          console.log('URL参数自动登录成功');
          // 清除URL中的参数，避免刷新时重复登录
          const newUrl = window.location.protocol + "//" + window.location.host + window.location.pathname;
          window.history.replaceState({}, document.title, newUrl);
          return; // 登录成功后直接返回，不再检查cookie
        } else {
          console.error('URL参数自动登录失败:', result.message);
          formErrors.username = result.message || '自动登录失败';
        }
      } catch (error) {
        console.error('URL参数自动登录异常:', error);
        formErrors.username = '自动登录失败，请手动登录';
      } finally {
        isLoading.value = false;
      }
    }
     } else {
     // 3. 如果没有URL参数，检查是否已有cookie登录状态
    if (window.AuthManager && window.AuthManager.isLoggedIn()) {
      const user = window.AuthManager.getCurrentUser();
      if (user) {
        // 已登录，直接跳转
        store.commit("setperson", user.username);
        store.commit("setauthority", user.authority);
        store.commit("setUserMessage", "自动登录成功");
        router.push({ name: 'AnomalyLabelView' });
      }
    }
  }
});
</script>
