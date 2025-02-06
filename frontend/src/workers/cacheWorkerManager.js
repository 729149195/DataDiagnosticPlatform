/**
 * 缓存Worker管理器
 * 用于管理通道数据的缓存操作
 */
class CacheWorkerManager {
  constructor() {
    this.worker = null;
    this.callbacks = new Map();
    this.messageId = 0;
  }

  /**
   * 获取Worker实例
   * @returns {Worker} Worker实例
   */
  getWorker() {
    if (!this.worker) {
      // 创建一个包含初始化代码的 Blob
      const workerCode = `
        self.__WS_TOKEN__ = null;
        importScripts('${new URL('./cacheWorker.js', import.meta.url)}');
      `;
      const blob = new Blob([workerCode], { type: 'application/javascript' });
      const workerUrl = URL.createObjectURL(blob);
      
      // 使用 Blob URL 创建 Worker
      this.worker = new Worker(workerUrl, {
        type: 'module'
      });

      // 清理 Blob URL
      URL.revokeObjectURL(workerUrl);

      this.worker.onmessage = (event) => {
        const { type, messageId, data, error } = event.data;
        const callback = this.callbacks.get(messageId);
        
        if (callback) {
          if (error) {
            callback.reject(new Error(error));
          } else {
            callback.resolve({
              type: type || 'channelData',
              data: data
            });
          }
          this.callbacks.delete(messageId);
        }
      };

      this.worker.onerror = (error) => {
        console.error('Cache Worker error:', error);
        this.callbacks.forEach((callback) => {
          callback.reject(error);
        });
        this.callbacks.clear();
      };
    }

    return this.worker;
  }

  /**
   * 设置通道数据到缓存
   * @param {string} channelKey - 通道键值
   * @param {Object} channelData - 通道数据
   * @returns {Promise} 操作结果
   */
  async setChannelData(channelKey, channelData) {
    return new Promise((resolve, reject) => {
      const messageId = this.messageId++;
      this.callbacks.set(messageId, { resolve, reject });

      this.getWorker().postMessage({
        type: 'setChannelData',
        messageId,
        data: { channelKey, channelData }
      });
    });
  }

  /**
   * 从缓存获取通道数据
   * @param {string} channelKey - 通道键值
   * @returns {Promise} 通道数据
   */
  async getChannelData(channelKey) {
    return new Promise((resolve, reject) => {
      const messageId = this.messageId++;
      this.callbacks.set(messageId, { resolve, reject });

      this.getWorker().postMessage({
        type: 'getChannelData',
        messageId,
        data: { channelKey }
      });
    });
  }

  /**
   * 清空缓存
   * @returns {Promise} 操作结果
   */
  async clearCache() {
    return new Promise((resolve, reject) => {
      const messageId = this.messageId++;
      this.callbacks.set(messageId, { resolve, reject });

      this.getWorker().postMessage({
        type: 'clearCache',
        messageId
      });
    });
  }

  /**
   * 清理过期缓存
   * @returns {Promise} 操作结果
   */
  async cleanup() {
    return new Promise((resolve, reject) => {
      const messageId = this.messageId++;
      this.callbacks.set(messageId, { resolve, reject });

      this.getWorker().postMessage({
        type: 'cleanup',
        messageId
      });
    });
  }

  /**
   * 终止Worker
   */
  terminate() {
    if (this.worker) {
      this.worker.terminate();
      this.worker = null;
      this.callbacks.clear();
    }
  }
}

// 创建单例实例
const cacheWorkerManager = new CacheWorkerManager();
export default cacheWorkerManager; 