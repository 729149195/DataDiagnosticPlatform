<template>
    <div class="login-page">
      <div class="login-container">
        <h2>用户登录</h2>
        <form @submit.prevent="handleLogin">
          <div class="form-group">
            <label for="username">用户名：</label>
            <input link id="username" v-model="username"/>
          </div>
          <div class="form-group">
            <label for="password">密码：</label>
            <input type="password" id="password" v-model="password" />
          </div>
          <button type="submit" class="login-button">登录</button>
        </form>
      </div>
    </div>
  </template>
  
  <script setup>
  import { stirlingS2 } from 'mathjs';
import { ref } from 'vue';
  import { useRouter } from 'vue-router';
  import { useStore } from 'vuex';

  const store = useStore()
  const username = ref('');
  const password = ref('');
  const router = useRouter();
  
  const handleLogin = () => {
    if (username.value && password.value) {
      store.commit("setperson", username.value);
      store.commit("authority", 999);
      router.push({ name: 'AnomalyLabelView' });
    } else {
      // alert('请输入用户名和密码');
      router.push({ name: 'AnomalyLabelView' });
    }
  };
  </script>
  
  <style scoped>
  /* 样式与之前代码相同 */
  .login-page {
    display: flex;
    justify-content: center;
    align-items: center;
    height: 100vh;
    background-color: #f0f2f5;
  }
  
  .login-container {
    width: 100%;
    max-width: 400px;
    padding: 40px;
    background-color: #ffffff;
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
    text-align: center;
  }
  
  h2 {
    font-size: 24px;
    color: #333;
    margin-bottom: 20px;
  }
  
  .form-group {
    margin-bottom: 20px;
    text-align: left;
  }
  
  label {
    display: block;
    margin-bottom: 5px;
    font-weight: bold;
    color: #555;
  }
  
  input {
    width: 100%;
    padding: 12px;
    border: 1px solid #ccc;
    border-radius: 4px;
    font-size: 16px;
    transition: border-color 0.3s;
  }
  
  input:focus {
    border-color: #007bff;
    outline: none;
  }
  
  .login-button {
    width: 100%;
    padding: 12px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 18px;
    font-weight: bold;
    cursor: pointer;
    transition: background-color 0.3s;
  }
  
  .login-button:hover {
    background-color: #0056b3;
  }
  </style>
  