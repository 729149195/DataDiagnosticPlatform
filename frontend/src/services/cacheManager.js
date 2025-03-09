// 新建缓存管理服务
import { CacheFactory } from 'cachefactory/CacheFactory.js';

export const cacheFactory = new CacheFactory();

export const dataCache = cacheFactory.createCache('channelData', {
  maxEntries: 100,
  maxAge: 30 * 60 * 1000,
  storageMode: 'memory',
  onExpire: (key, value) => {
    // 添加自定义过期处理
    console.log(`Cache expired: ${key}`);
  }
});

// 内存监控方法
export const monitorMemoryUsage = () => {
  if (window.performance && window.performance.memory) {
    const { usedJSHeapSize, jsHeapSizeLimit } = window.performance.memory;
    const usage = usedJSHeapSize / jsHeapSizeLimit;
    if (usage > 0.7) {
      dataCache.removeExpired();
      console.warn('High memory usage, triggering cache cleanup');
    }
  }
};

// 定时内存监控
setInterval(monitorMemoryUsage, 60 * 1000); 