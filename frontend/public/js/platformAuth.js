/**
 * 平台认证接口 - 供主平台调用的简化接口
 * 依赖于 authManager.js
 */

/**
 * 平台登入接口
 * @param {string} username - 用户名
 * @returns {Promise<boolean>} 登录是否成功
 */
async function login(username) {
  try {
    if (!username) {
      console.error('平台登入失败：用户名不能为空');
      return false;
    }

    // 调用认证管理器的登录函数
    if (!window.platformLogin) {
      console.error('平台登入失败：认证管理器未加载');
      return false;
    }

    const result = await window.platformLogin(username);
    
    if (result.success) {
      console.log('平台登入成功:', result.message);
      return true;
    } else {
      console.error('平台登入失败:', result.message);
      return false;
    }
  } catch (error) {
    console.error('平台登入异常:', error);
    return false;
  }
}

/**
 * 平台注销接口
 * @returns {Promise<boolean>} 注销是否成功
 */
async function logout() {
  try {
    // 调用认证管理器的注销函数
    if (!window.platformLogout) {
      console.error('平台注销失败：认证管理器未加载');
      return false;
    }

    const result = await window.platformLogout();
    
    if (result.success) {
      console.log('平台注销成功:', result.message);
      return true;
    } else {
      console.error('平台注销失败:', result.message);
      return false;
    }
  } catch (error) {
    console.error('平台注销异常:', error);
    return false;
  }
}

/**
 * 获取当前登录状态
 * @returns {object|null} 用户信息或null
 */
function getLoginStatus() {
  try {
    if (!window.AuthManager) {
      return null;
    }

    if (!window.AuthManager.isLoggedIn()) {
      return null;
    }

    return window.AuthManager.getCurrentUser();
  } catch (error) {
    console.error('获取登录状态异常:', error);
    return null;
  }
}

// 暴露给全局
window.DataDiagnosticAuth = {
  login,
  logout,
  getLoginStatus
};

// 导出模块（支持ES6模块）
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    login,
    logout,
    getLoginStatus
  };
} 