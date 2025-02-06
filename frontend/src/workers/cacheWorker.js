// 添加全局变量定义
self.__WS_TOKEN__ = null;

// Cache Worker for managing channel data cache
import { openDB } from 'idb';

// 初始化 IndexedDB
const initDB = async () => {
  return await openDB('channelCache', 1, {
    upgrade(db) {
      // 创建通道数据存储
      if (!db.objectStores.contains('channelData')) {
        const store = db.createObjectStore('channelData', { keyPath: 'channelKey' });
        store.createIndex('timestamp', 'timestamp');
      }
      // 创建元数据存储
      if (!db.objectStores.contains('metadata')) {
        db.createObjectStore('metadata', { keyPath: 'key' });
      }
    },
  });
};

let db;

// 缓存配置
const CACHE_SIZE_LIMIT = 500; // 最大缓存条目数
const CACHE_TIME_LIMIT = 30 * 60 * 1000; // 缓存过期时间（30分钟）

// 内存缓存
const memoryCache = new Map();

// 清理过期缓存
async function cleanupCache() {
  if (!db) return;

  const tx = db.transaction('channelData', 'readwrite');
  const store = tx.objectStore('channelData');
  const index = store.index('timestamp');

  // 删除过期数据
  const expiredTime = Date.now() - CACHE_TIME_LIMIT;
  let cursor = await index.openCursor();
  
  while (cursor) {
    if (cursor.value.timestamp < expiredTime) {
      await cursor.delete();
      memoryCache.delete(cursor.value.channelKey);
    }
    cursor = await cursor.continue();
  }

  // 如果缓存条目仍然过多，删除最旧的数据
  const count = await store.count();
  if (count > CACHE_SIZE_LIMIT) {
    const deleteCount = count - CACHE_SIZE_LIMIT;
    cursor = await index.openCursor();
    let deleted = 0;
    
    while (cursor && deleted < deleteCount) {
      await cursor.delete();
      memoryCache.delete(cursor.value.channelKey);
      deleted++;
      cursor = await cursor.continue();
    }
  }
}

// 处理消息
self.onmessage = async function(e) {
  if (!db) {
    db = await initDB();
  }

  const { type, data, messageId } = e.data;

  try {
    switch (type) {
      case 'setChannelData': {
        const { channelKey, channelData } = data;
        
        // 存储到内存缓存
        memoryCache.set(channelKey, {
          data: channelData,
          timestamp: Date.now()
        });

        // 存储到 IndexedDB
        await db.put('channelData', {
          channelKey,
          data: channelData,
          timestamp: Date.now()
        });

        // 清理过期缓存
        await cleanupCache();

        self.postMessage({ 
          type: 'success', 
          messageId,
          data: channelData 
        });
        break;
      }

      case 'getChannelData': {
        const { channelKey } = data;
        
        // 首先检查内存缓存
        const memoryData = memoryCache.get(channelKey);
        if (memoryData && Date.now() - memoryData.timestamp < CACHE_TIME_LIMIT) {
          self.postMessage({
            type: 'channelData',
            messageId,
            data: memoryData.data
          });
          return;
        }

        // 从 IndexedDB 获取数据
        const record = await db.get('channelData', channelKey);
        if (record && Date.now() - record.timestamp < CACHE_TIME_LIMIT) {
          // 更新内存缓存
          memoryCache.set(channelKey, {
            data: record.data,
            timestamp: record.timestamp
          });

          self.postMessage({
            type: 'channelData',
            messageId,
            data: record.data
          });
        } else {
          self.postMessage({
            type: 'notFound',
            messageId,
            data: null
          });
        }
        break;
      }

      case 'clearCache': {
        // 清空内存缓存
        memoryCache.clear();
        
        // 清空 IndexedDB
        await db.clear('channelData');
        
        self.postMessage({ 
          type: 'success', 
          messageId,
          data: null 
        });
        break;
      }

      case 'cleanup': {
        await cleanupCache();
        self.postMessage({ 
          type: 'success', 
          messageId,
          data: null 
        });
        break;
      }

      default:
        throw new Error(`Unknown message type: ${type}`);
    }
  } catch (error) {
    self.postMessage({
      type: 'error',
      messageId,
      error: error.message || 'Unknown error occurred',
      data: null
    });
  }
}; 