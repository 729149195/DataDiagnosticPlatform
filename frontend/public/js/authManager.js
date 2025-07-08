/**
 * 认证管理器 - 处理cookie登录状态
 * 用于与主平台集成的登录管理
 */

// Cookie 管理工具
const CookieManager = {
  // 设置 cookie
  set(name, value, days = 7) {
    let expires = "";
    if (days) {
      const date = new Date();
      date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
      expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/; SameSite=Lax";
  },

  // 获取 cookie
  get(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) === ' ') c = c.substring(1, c.length);
      if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
  },

  // 删除 cookie
  remove(name) {
    document.cookie = name + "=; expires=Thu, 01 Jan 1970 00:00:01 GMT; path=/; SameSite=Lax";
  }
};

// 认证管理器
const AuthManager = {
  // 登录状态检查
  isLoggedIn() {
    const username = CookieManager.get('platform_username');
    const loginTime = CookieManager.get('platform_login_time');
    
    if (!username || !loginTime) {
      return false;
    }
    
    // 检查登录是否过期（7天）
    const now = Date.now();
    const loginTimestamp = parseInt(loginTime);
    const sevenDays = 7 * 24 * 60 * 60 * 1000;
    
    if (now - loginTimestamp > sevenDays) {
      this.clearAuthData();
      return false;
    }
    
    return true;
  },

  // 获取当前用户信息
  getCurrentUser() {
    if (!this.isLoggedIn()) {
      return null;
    }
    
    return {
      username: CookieManager.get('platform_username'),
      authority: parseInt(CookieManager.get('platform_authority') || '0'),
      loginTime: CookieManager.get('platform_login_time')
    };
  },

  // 设置认证数据
  setAuthData(username, authority = 0) {
    const now = Date.now().toString();
    
    CookieManager.set('platform_username', username, 7);
    CookieManager.set('platform_authority', authority.toString(), 7);
    CookieManager.set('platform_login_time', now, 7);
  },

  // 清除认证数据
  clearAuthData() {
    CookieManager.remove('platform_username');
    CookieManager.remove('platform_authority');
    CookieManager.remove('platform_login_time');
  },

  // 用户验证（查询用户列表）
  async verifyUser(username) {
    try {
      const response = await fetch('http://192.168.20.49:5000/api/verify-username', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        credentials: 'include',
        mode: 'cors',
        body: JSON.stringify({ username: username })
      });

      const data = await response.json();
      return data;
    } catch (error) {
      console.error('用户验证失败:', error);
      return { success: false, message: '验证失败，请重试' };
    }
  }
};

// 导出的主要功能函数

/**
 * 登入函数 - 供主平台调用
 * @param {string} username - 主平台传入的用户名
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function platformLogin(username) {
  try {
    if (!username) {
      return { success: false, message: '用户名不能为空' };
    }

    // 验证用户是否存在
    const verifyResult = await AuthManager.verifyUser(username);
    
    if (!verifyResult.success) {
      return { success: false, message: verifyResult.message || '用户验证失败' };
    }

    // 设置cookie登录状态
    AuthManager.setAuthData(username, verifyResult.authority || 0);

    // 如果当前在Vue应用中，更新store状态
    if (window.vueStore) {
      window.vueStore.commit('setperson', username);
      window.vueStore.commit('setauthority', verifyResult.authority || 0);
      window.vueStore.commit('setUserMessage', verifyResult.message || '');
    }

    // 如果当前在登录页面，跳转到主页面
    if (window.vueRouter && window.location.pathname === '/') {
      window.vueRouter.push({ name: 'AnomalyLabelView' });
    }

    return { 
      success: true, 
      message: '登录成功',
      user: {
        username: username,
        authority: verifyResult.authority || 0
      }
    };
  } catch (error) {
    console.error('登录过程出错:', error);
    return { success: false, message: '登录失败，请重试' };
  }
}

/**
 * 注销函数 - 供主平台调用
 * @returns {Promise<{success: boolean, message: string}>}
 */
async function platformLogout() {
  try {
    // 清除cookie登录状态
    AuthManager.clearAuthData();

    // 如果当前在Vue应用中，清除store状态
    if (window.vueStore) {
      window.vueStore.commit('setperson', '');
      window.vueStore.commit('setauthority', 0);
      window.vueStore.commit('setUserMessage', '');
    }

    // 跳转到登录页面
    if (window.vueRouter) {
      window.vueRouter.push('/');
    } else {
      // 如果router不可用，直接刷新页面到根路径
      window.location.href = '/';
    }

    return { success: true, message: '注销成功' };
  } catch (error) {
    console.error('注销过程出错:', error);
    return { success: false, message: '注销失败' };
  }
}

/**
 * 自动登录检查 - 页面加载时调用
 * @returns {boolean} 是否已自动登录
 */
function autoLoginCheck() {
  if (!AuthManager.isLoggedIn()) {
    return false;
  }

  const user = AuthManager.getCurrentUser();
  if (!user) {
    return false;
  }

  // 如果当前在Vue应用中，恢复store状态
  if (window.vueStore) {
    window.vueStore.commit('setperson', user.username);
    window.vueStore.commit('setauthority', user.authority);
    window.vueStore.commit('setUserMessage', '自动登录成功');
  }

  return true;
}

// 暴露给全局使用
window.platformLogin = platformLogin;
window.platformLogout = platformLogout;
window.autoLoginCheck = autoLoginCheck;
window.AuthManager = AuthManager;

// 导出模块（支持ES6模块）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    platformLogin,
    platformLogout,
    autoLoginCheck,
    AuthManager
  };
} 