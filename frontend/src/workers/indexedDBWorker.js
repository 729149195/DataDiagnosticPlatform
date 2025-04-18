// indexedDBWorker.js
// 专用于IndexedDB操作的Web Worker

const DB_NAME = "channelDataCache";
const DB_VERSION = 1;
const STORE_NAME = "channelData";

let db = null;
let isInitialized = false;

/**
 * 初始化数据库
 * @returns {Promise} 初始化完成的Promise
 */
async function initDB() {
  if (isInitialized) return;
  
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = (event) => {
      self.postMessage({
        type: 'error',
        operation: 'init',
        error: event.target.error.message
      });
      reject(event.target.error);
    };

    request.onsuccess = (event) => {
      db = event.target.result;
      isInitialized = true;
      self.postMessage({
        type: 'log',
        message: '数据库初始化成功'
      });
      resolve();
    };

    request.onupgradeneeded = (event) => {
      const db = event.target.result;

      // 创建对象存储空间
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "key" });
        // 创建索引
        store.createIndex("timestamp", "timestamp", { unique: false });
        self.postMessage({
          type: 'log',
          message: '创建数据存储空间成功'
        });
      }
    };
  });
}

/**
 * 保存通道数据到IndexedDB
 * @param {string} key - 通道键值
 * @param {Object} data - 通道数据
 * @param {number} timestamp - 时间戳
 * @returns {Promise} 操作结果
 */
async function saveChannelData(key, data, timestamp) {
  await initDB();

  // 深度克隆数据，移除不可序列化的内容
  const safeData = makeDataSafeForIndexedDB(data);

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], "readwrite");
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
        self.postMessage({
          type: 'error',
          operation: 'save',
          error: event.target.error.message
        });
        reject(event.target.error);
      };
    } catch (error) {
      self.postMessage({
        type: 'error',
        operation: 'save',
        error: error.message
      });
      reject(error);
    }
  });
}

/**
 * 使数据安全可序列化，移除循环引用和不可序列化的内容
 */
function makeDataSafeForIndexedDB(data) {
  try {
    // 尝试使用JSON序列化和反序列化来移除不可序列化的内容
    return JSON.parse(JSON.stringify(data));
  } catch (error) {
    self.postMessage({
      type: 'error',
      operation: 'serialize',
      error: error.message
    });
    
    // 如果JSON序列化失败，尝试手动清理
    return manuallyCleanData(data);
  }
}

/**
 * 手动清理数据，移除不可序列化的内容
 */
function manuallyCleanData(data) {
  if (data === null || data === undefined) {
    return data;
  }

  // 处理基本类型
  if (typeof data !== "object") {
    return data;
  }

  // 处理数组
  if (Array.isArray(data)) {
    return data.map((item) => manuallyCleanData(item));
  }

  // 处理对象
  const cleanedData = {};
  for (const key in data) {
    if (Object.prototype.hasOwnProperty.call(data, key)) {
      try {
        // 跳过函数、Symbol等不可序列化的属性
        const value = data[key];
        if (typeof value !== "function" && typeof value !== "symbol") {
          cleanedData[key] = manuallyCleanData(value);
        }
      } catch (error) {
        self.postMessage({
          type: 'warn',
          message: `清理属性 ${key} 时出错，已跳过`
        });
      }
    }
  }
  return cleanedData;
}

/**
 * 从IndexedDB获取通道数据
 */
async function getChannelData(key) {
  await initDB();

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], "readonly");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.get(key);

      request.onsuccess = (event) => {
        const result = event.target.result;
        resolve(result ? result : null);
      };

      request.onerror = (event) => {
        self.postMessage({
          type: 'error',
          operation: 'get',
          error: event.target.error.message
        });
        reject(event.target.error);
      };
    } catch (error) {
      self.postMessage({
        type: 'error',
        operation: 'get',
        error: error.message
      });
      reject(error);
    }
  });
}

/**
 * 删除通道数据
 */
async function deleteChannelData(key) {
  await initDB();

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.delete(key);

      request.onsuccess = () => {
        resolve(true);
      };

      request.onerror = (event) => {
        self.postMessage({
          type: 'error',
          operation: 'delete',
          error: event.target.error.message
        });
        reject(event.target.error);
      };
    } catch (error) {
      self.postMessage({
        type: 'error',
        operation: 'delete',
        error: error.message
      });
      reject(error);
    }
  });
}

/**
 * 清空所有通道数据
 */
async function clearAllChannelData() {
  await initDB();

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], "readwrite");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.clear();

      request.onsuccess = () => {
        resolve(true);
      };

      request.onerror = (event) => {
        self.postMessage({
          type: 'error',
          operation: 'clear',
          error: event.target.error.message
        });
        reject(event.target.error);
      };
    } catch (error) {
      self.postMessage({
        type: 'error',
        operation: 'clear',
        error: error.message
      });
      reject(error);
    }
  });
}

/**
 * 获取所有通道数据的键
 */
async function getAllKeys() {
  await initDB();

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], "readonly");
      const store = transaction.objectStore(STORE_NAME);
      const request = store.getAllKeys();

      request.onsuccess = (event) => {
        resolve(event.target.result);
      };

      request.onerror = (event) => {
        self.postMessage({
          type: 'error',
          operation: 'getAllKeys',
          error: event.target.error.message
        });
        reject(event.target.error);
      };
    } catch (error) {
      self.postMessage({
        type: 'error',
        operation: 'getAllKeys',
        error: error.message
      });
      reject(error);
    }
  });
}

/**
 * 清理过期的通道数据
 */
async function cleanupExpiredData(maxAge) {
  await initDB();

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], "readwrite");
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
          self.postMessage({
            type: 'log',
            message: `清理了 ${deleteCount} 条过期数据`
          });
          resolve(deleteCount);
        }
      };

      request.onerror = (event) => {
        self.postMessage({
          type: 'error',
          operation: 'cleanup',
          error: event.target.error.message
        });
        reject(event.target.error);
      };
    } catch (error) {
      self.postMessage({
        type: 'error',
        operation: 'cleanup',
        error: error.message
      });
      reject(error);
    }
  });
}

/**
 * 获取IndexedDB的存储使用情况
 */
async function getStorageUsage() {
  await initDB();

  return new Promise((resolve, reject) => {
    try {
      const transaction = db.transaction([STORE_NAME], "readonly");
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
          self.postMessage({
            type: 'error',
            operation: 'getAll',
            error: event.target.error.message
          });
          // 仍然返回计数
          resolve({ count, size: 0 });
        };
      };

      countRequest.onerror = (event) => {
        self.postMessage({
          type: 'error',
          operation: 'count',
          error: event.target.error.message
        });
        reject(event.target.error);
      };
    } catch (error) {
      self.postMessage({
        type: 'error',
        operation: 'getStorageUsage',
        error: error.message
      });
      reject(error);
    }
  });
}

// Worker消息处理
self.onmessage = async function(event) {
  const { id, action, params } = event.data;
  
  try {
    let result;
    
    switch (action) {
      case 'init':
        await initDB();
        result = { success: true };
        break;
        
      case 'saveChannelData':
        result = await saveChannelData(params.key, params.data, params.timestamp);
        break;
        
      case 'getChannelData':
        result = await getChannelData(params.key);
        break;
        
      case 'deleteChannelData':
        result = await deleteChannelData(params.key);
        break;
        
      case 'clearAllChannelData':
        result = await clearAllChannelData();
        break;
        
      case 'getAllKeys':
        result = await getAllKeys();
        break;
        
      case 'cleanupExpiredData':
        result = await cleanupExpiredData(params.maxAge);
        break;
        
      case 'getStorageUsage':
        result = await getStorageUsage();
        break;
        
      default:
        throw new Error(`未知操作: ${action}`);
    }
    
    // 发送成功响应
    self.postMessage({
      id,
      type: 'response',
      success: true,
      result
    });
  } catch (error) {
    // 发送错误响应
    self.postMessage({
      id,
      type: 'response',
      success: false,
      error: error.message || '未知错误'
    });
  }
};

// 定期清理过期数据（每天一次）
setInterval(() => {
  cleanupExpiredData(7 * 24 * 60 * 60 * 1000).catch(error => {
    self.postMessage({
      type: 'error',
      operation: 'scheduled-cleanup',
      error: error.message
    });
  });
}, 24 * 60 * 60 * 1000); 