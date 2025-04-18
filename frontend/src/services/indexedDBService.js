// indexedDBService.js
// 用于持久化缓存数据到IndexedDB，通过Web Worker实现

class IndexedDBService {
  constructor() {
    this.worker = null;
    this.isInitialized = false;
    this.pendingRequests = new Map();
    this.requestId = 0;
    this.isSupported = this.checkSupport();
    this.initPromise = null;
    this.logListeners = [];
    this.errorListeners = [];
  }

  /**
   * 检查浏览器是否支持IndexedDB和Web Worker
   * @returns {boolean} 是否支持
   */
  checkSupport() {
    return typeof window !== 'undefined' && 
           'indexedDB' in window && 
           'Worker' in window;
  }

  /**
   * 初始化Worker
   * @returns {Promise} 初始化完成的Promise
   */
  init() {
    if (!this.isSupported) {
      return Promise.reject(new Error("浏览器不支持IndexedDB或Web Worker"));
    }

    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = new Promise((resolve, reject) => {
      try {
        // 创建Web Worker实例
        const workerUrl = new URL('../workers/indexedDBWorker.js', import.meta.url);
        this.worker = new Worker(workerUrl, { type: 'module' });
        
        // 设置消息处理
        this.worker.onmessage = this.handleWorkerMessage.bind(this);
        this.worker.onerror = (error) => {
          console.error('IndexedDB Worker错误:', error);
          reject(error);
          
          // 通知所有等待中的请求
          this.pendingRequests.forEach((callback, id) => {
            callback.reject(new Error('Worker错误: ' + (error.message || '未知错误')));
          });
          this.pendingRequests.clear();
        };
        
        // 发送初始化请求
        this.sendToWorker('init')
          .then(() => {
            this.isInitialized = true;
            resolve();
          })
          .catch(error => {
            console.error('初始化IndexedDB Worker失败:', error);
            reject(error);
          });
      } catch (error) {
        console.error('创建IndexedDB Worker失败:', error);
        reject(error);
      }
    });

    return this.initPromise;
  }

  /**
   * 处理Worker消息
   * @private
   */
  handleWorkerMessage(event) {
    const { id, type, success, result, error } = event.data;
    
    if (type === 'log') {
      // 处理日志消息
      console.log('IndexedDB Worker:', event.data.message);
      this.logListeners.forEach(listener => listener(event.data.message));
      return;
    }
    
    if (type === 'error' || type === 'warn') {
      // 处理错误/警告消息
      const method = type === 'error' ? console.error : console.warn;
      method('IndexedDB Worker:', event.data.operation, event.data.error);
      this.errorListeners.forEach(listener => 
        listener({
          type, 
          operation: event.data.operation,
          message: event.data.error
        })
      );
      return;
    }
    
    // 处理响应消息
    if (type === 'response' && id !== undefined) {
      const pendingRequest = this.pendingRequests.get(id);
      if (pendingRequest) {
        if (success) {
          pendingRequest.resolve(result);
        } else {
          pendingRequest.reject(new Error(error || '操作失败'));
        }
        this.pendingRequests.delete(id);
      }
    }
  }

  /**
   * 发送消息到Worker
   * @private
   */
  sendToWorker(action, params = {}) {
    return new Promise(async (resolve, reject) => {
      if (!this.isInitialized && action !== 'init') {
        try {
          await this.init();
        } catch (error) {
          return reject(error);
        }
      }
      
      const id = this.requestId++;
      this.pendingRequests.set(id, { resolve, reject });
      
      this.worker.postMessage({
        id,
        action,
        params
      });
    });
  }

  /**
   * 添加日志监听器
   * @param {Function} listener 日志监听函数
   */
  addLogListener(listener) {
    if (typeof listener === 'function') {
      this.logListeners.push(listener);
    }
  }

  /**
   * 添加错误监听器
   * @param {Function} listener 错误监听函数
   */
  addErrorListener(listener) {
    if (typeof listener === 'function') {
      this.errorListeners.push(listener);
    }
  }

  /**
   * 保存通道数据到IndexedDB
   * @param {string} key - 通道键值
   * @param {Object} data - 通道数据
   * @param {number} timestamp - 时间戳
   * @returns {Promise} 操作结果
   */
  async saveChannelData(key, data, timestamp = Date.now()) {
    if (!this.isSupported) {
      return Promise.resolve(false);
    }

    try {
      const result = await this.sendToWorker('saveChannelData', {
        key,
        data,
        timestamp
      });
      return result;
    } catch (error) {
      console.error('保存数据到IndexedDB失败:', error);
      return false;
    }
  }

  /**
   * 从IndexedDB获取通道数据
   * @param {string} key - 通道键值
   * @returns {Promise} 通道数据
   */
  async getChannelData(key) {
    if (!this.isSupported) {
      return Promise.resolve(null);
    }

    try {
      const result = await this.sendToWorker('getChannelData', { key });
      return result;
    } catch (error) {
      console.error('从IndexedDB获取数据失败:', error);
      return null;
    }
  }

  /**
   * 删除通道数据
   * @param {string} key - 通道键值
   * @returns {Promise} 操作结果
   */
  async deleteChannelData(key) {
    if (!this.isSupported) {
      return Promise.resolve(false);
    }

    try {
      const result = await this.sendToWorker('deleteChannelData', { key });
      return result;
    } catch (error) {
      console.error('从IndexedDB删除数据失败:', error);
      return false;
    }
  }

  /**
   * 清空所有通道数据
   * @returns {Promise} 操作结果
   */
  async clearAllChannelData() {
    if (!this.isSupported) {
      return Promise.resolve(false);
    }

    try {
      const result = await this.sendToWorker('clearAllChannelData');
      return result;
    } catch (error) {
      console.error('清空IndexedDB数据失败:', error);
      return false;
    }
  }

  /**
   * 获取所有通道数据的键
   * @returns {Promise<Array>} 键数组
   */
  async getAllKeys() {
    if (!this.isSupported) {
      return Promise.resolve([]);
    }

    try {
      const result = await this.sendToWorker('getAllKeys');
      return result;
    } catch (error) {
      console.error('从IndexedDB获取所有键失败:', error);
      return [];
    }
  }

  /**
   * 清理过期的通道数据
   * @param {number} maxAge - 最大缓存时间（毫秒）
   * @returns {Promise<number>} 清理的数据条数
   */
  async cleanupExpiredData(maxAge = 7 * 24 * 60 * 60 * 1000) {
    if (!this.isSupported) {
      return Promise.resolve(0);
    }

    try {
      const result = await this.sendToWorker('cleanupExpiredData', { maxAge });
      return result;
    } catch (error) {
      console.error('清理IndexedDB过期数据失败:', error);
      return 0;
    }
  }

  /**
   * 获取IndexedDB的存储使用情况
   * @returns {Promise<Object>} 存储使用情况
   */
  async getStorageUsage() {
    if (!this.isSupported) {
      return Promise.resolve({ count: 0, size: 0 });
    }

    try {
      const result = await this.sendToWorker('getStorageUsage');
      return result;
    } catch (error) {
      console.error('获取IndexedDB存储使用情况失败:', error);
      return { count: 0, size: 0 };
    }
  }

  /**
   * 终止Worker
   */
  terminate() {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
      this.pendingRequests.clear();
      this.isInitialized = false;
      this.initPromise = null;
    }
  }
}

// 创建单例实例
const indexedDBService = new IndexedDBService();

// 应用加载时预初始化Worker
if (typeof window !== 'undefined') {
  // 使用setTimeout延迟初始化，避免阻塞应用启动
  setTimeout(() => {
    indexedDBService.init().catch(err => {
      console.warn('IndexedDB Worker预初始化失败，将在首次使用时重试:', err);
    });
  }, 1000);
}

export default indexedDBService;
