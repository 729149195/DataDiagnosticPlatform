// indexedDBService.js
// 用于持久化缓存数据到IndexedDB

const DB_NAME = "channelDataCache";
const DB_VERSION = 1;
const STORE_NAME = "channelData";

class IndexedDBService {
  constructor() {
    this.db = null;
    this.isInitialized = false;
    this.initPromise = null;
    this.isSupported = this.checkSupport();
  }

  /**
   * 检查浏览器是否支持IndexedDB
   * @returns {boolean} 是否支持
   */
  checkSupport() {
    return window && "indexedDB" in window;
  }

  /**
   * 初始化数据库
   * @returns {Promise} 初始化完成的Promise
   */
  init() {
    if (!this.isSupported) {
      return Promise.reject(new Error("浏览器不支持IndexedDB"));
    }

    if (this.initPromise) {
      return this.initPromise;
    }

    this.initPromise = new Promise((resolve, reject) => {
      if (!window.indexedDB) {
        console.error("您的浏览器不支持IndexedDB");
        reject(new Error("浏览器不支持IndexedDB"));
        return;
      }

      const request = window.indexedDB.open(DB_NAME, DB_VERSION);

      request.onerror = (event) => {
        console.error("打开数据库失败:", event.target.error);
        reject(event.target.error);
      };

      request.onsuccess = (event) => {
        this.db = event.target.result;
        this.isInitialized = true;
        console.log("数据库初始化成功");
        resolve(this.db);
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;

        // 创建对象存储空间
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          const store = db.createObjectStore(STORE_NAME, { keyPath: "key" });

          // 创建索引
          store.createIndex("timestamp", "timestamp", { unique: false });
          console.log("创建数据存储空间成功");
        }
      };
    });

    return this.initPromise;
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
      await this.init();

      // 深度克隆数据，移除不可序列化的内容
      const safeData = this.makeDataSafeForIndexedDB(data);

      return new Promise((resolve, reject) => {
        try {
          const transaction = this.db.transaction([STORE_NAME], "readwrite");
          const store = transaction.objectStore(STORE_NAME);

          const record = {
            key,
            data: safeData,
            timestamp,
          };

          const request = store.put(record);

          request.onsuccess = () => {
            resolve(true);
          };

          request.onerror = (event) => {
            console.error("保存数据失败:", event.target.error);
            reject(event.target.error);
          };
        } catch (error) {
          console.error("保存数据出错:", error);
          reject(error);
        }
      });
    } catch (error) {
      console.error("保存数据到IndexedDB失败:", error);
      return false;
    }
  }

  /**
   * 使数据安全可序列化，移除循环引用和不可序列化的内容
   * @param {Object} data - 原始数据
   * @returns {Object} 安全的可序列化数据
   */
  makeDataSafeForIndexedDB(data) {
    try {
      // 尝试使用JSON序列化和反序列化来移除不可序列化的内容
      return JSON.parse(JSON.stringify(data));
    } catch (error) {
      console.error("数据序列化失败，尝试手动清理:", error);

      // 如果JSON序列化失败，尝试手动清理
      return this.manuallyCleanData(data);
    }
  }

  /**
   * 手动清理数据，移除不可序列化的内容
   * @param {any} data - 需要清理的数据
   * @returns {any} 清理后的数据
   */
  manuallyCleanData(data) {
    if (data === null || data === undefined) {
      return data;
    }

    // 处理基本类型
    if (typeof data !== "object") {
      return data;
    }

    // 处理数组
    if (Array.isArray(data)) {
      return data.map((item) => this.manuallyCleanData(item));
    }

    // 处理对象
    const cleanedData = {};
    for (const key in data) {
      if (Object.prototype.hasOwnProperty.call(data, key)) {
        try {
          // 跳过函数、Symbol等不可序列化的属性
          const value = data[key];
          if (typeof value !== "function" && typeof value !== "symbol") {
            // 检查是否为Vue的响应式对象
            if (value && typeof value === "object" && value.__v_isRef) {
              cleanedData[key] = this.manuallyCleanData(value.value);
            } else if (
              value &&
              typeof value === "object" &&
              value.__v_isReactive
            ) {
              cleanedData[key] = this.manuallyCleanData({ ...value });
            } else {
              cleanedData[key] = this.manuallyCleanData(value);
            }
          }
        } catch (error) {
          console.warn(`清理属性 ${key} 时出错，已跳过:`, error);
        }
      }
    }
    return cleanedData;
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
      await this.init();

      return new Promise((resolve, reject) => {
        try {
          const transaction = this.db.transaction([STORE_NAME], "readonly");
          const store = transaction.objectStore(STORE_NAME);
          const request = store.get(key);

          request.onsuccess = (event) => {
            const result = event.target.result;
            resolve(result ? result : null);
          };

          request.onerror = (event) => {
            console.error("获取数据失败:", event.target.error);
            reject(event.target.error);
          };
        } catch (error) {
          console.error("获取数据出错:", error);
          reject(error);
        }
      });
    } catch (error) {
      console.error("从IndexedDB获取数据失败:", error);
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
      await this.init();

      return new Promise((resolve, reject) => {
        try {
          const transaction = this.db.transaction([STORE_NAME], "readwrite");
          const store = transaction.objectStore(STORE_NAME);
          const request = store.delete(key);

          request.onsuccess = () => {
            resolve(true);
          };

          request.onerror = (event) => {
            console.error("删除数据失败:", event.target.error);
            reject(event.target.error);
          };
        } catch (error) {
          console.error("删除数据出错:", error);
          reject(error);
        }
      });
    } catch (error) {
      console.error("从IndexedDB删除数据失败:", error);
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
      await this.init();

      return new Promise((resolve, reject) => {
        try {
          const transaction = this.db.transaction([STORE_NAME], "readwrite");
          const store = transaction.objectStore(STORE_NAME);
          const request = store.clear();

          request.onsuccess = () => {
            resolve(true);
          };

          request.onerror = (event) => {
            console.error("清空数据失败:", event.target.error);
            reject(event.target.error);
          };
        } catch (error) {
          console.error("清空数据出错:", error);
          reject(error);
        }
      });
    } catch (error) {
      console.error("清空IndexedDB数据失败:", error);
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
      await this.init();

      return new Promise((resolve, reject) => {
        try {
          const transaction = this.db.transaction([STORE_NAME], "readonly");
          const store = transaction.objectStore(STORE_NAME);
          const request = store.getAllKeys();

          request.onsuccess = (event) => {
            resolve(event.target.result);
          };

          request.onerror = (event) => {
            console.error("获取所有键失败:", event.target.error);
            reject(event.target.error);
          };
        } catch (error) {
          console.error("获取所有键出错:", error);
          reject(error);
        }
      });
    } catch (error) {
      console.error("从IndexedDB获取所有键失败:", error);
      return [];
    }
  }

  /**
   * 清理过期的通道数据
   * @param {number} maxAge - 最大缓存时间（毫秒）
   * @returns {Promise<number>} 清理的数据条数
   */
  async cleanupExpiredData(maxAge = 7 * 24 * 60 * 60 * 1000) {
    // 默认7天
    if (!this.isSupported) {
      return Promise.resolve(0);
    }

    try {
      await this.init();

      return new Promise((resolve, reject) => {
        try {
          const transaction = this.db.transaction([STORE_NAME], "readwrite");
          const store = transaction.objectStore(STORE_NAME);
          const index = store.index("timestamp");

          const now = Date.now();
          const range = IDBKeyRange.upperBound(now - maxAge);

          let deleteCount = 0;
          const request = index.openCursor(range);

          request.onsuccess = (event) => {
            const cursor = event.target.result;
            if (cursor) {
              cursor.delete();
              deleteCount++;
              cursor.continue();
            } else {
              console.log(`清理了 ${deleteCount} 条过期数据`);
              resolve(deleteCount);
            }
          };

          request.onerror = (event) => {
            console.error("清理过期数据失败:", event.target.error);
            reject(event.target.error);
          };
        } catch (error) {
          console.error("清理过期数据出错:", error);
          reject(error);
        }
      });
    } catch (error) {
      console.error("清理IndexedDB过期数据失败:", error);
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
      await this.init();

      return new Promise((resolve, reject) => {
        try {
          const transaction = this.db.transaction([STORE_NAME], "readonly");
          const store = transaction.objectStore(STORE_NAME);
          const countRequest = store.count();

          countRequest.onsuccess = () => {
            const count = countRequest.result;

            // 估算大小
            const getAllRequest = store.getAll();
            getAllRequest.onsuccess = () => {
              const items = getAllRequest.result;
              let totalSize = 0;

              // 使用JSON.stringify来估算每个项目的大小
              items.forEach((item) => {
                try {
                  const jsonSize = JSON.stringify(item).length;
                  totalSize += jsonSize;
                } catch (e) {
                  // 忽略无法序列化的项目
                }
              });

              resolve({
                count,
                size: totalSize,
                sizeInMB: (totalSize / (1024 * 1024)).toFixed(2),
              });
            };

            getAllRequest.onerror = (event) => {
              console.error("获取所有数据失败:", event.target.error);
              // 仍然返回计数
              resolve({ count, size: 0 });
            };
          };

          countRequest.onerror = (event) => {
            console.error("获取数据计数失败:", event.target.error);
            reject(event.target.error);
          };
        } catch (error) {
          console.error("获取存储使用情况出错:", error);
          reject(error);
        }
      });
    } catch (error) {
      console.error("获取IndexedDB存储使用情况失败:", error);
      return { count: 0, size: 0 };
    }
  }
}

// 创建单例实例
const indexedDBService = new IndexedDBService();

// 定期清理过期数据（每天一次）
setInterval(() => {
  indexedDBService.cleanupExpiredData().catch((err) => {
    console.error("定期清理过期数据失败:", err);
  });
}, 24 * 60 * 60 * 1000);

export default indexedDBService;
