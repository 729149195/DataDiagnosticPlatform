// 新建缓存管理服务
import { CacheFactory } from 'cachefactory';

export const cacheFactory = new CacheFactory();

export const dataCache = cacheFactory.createCache('channelData', {
  maxEntries: 200,
  maxAge: 30 * 60 * 1000,
  deleteOnExpire: "passive",
  storageMode: 'memory',
  recycleFreq: 60 * 1000,
  onExpire: (key, value, reason) => {
    return true;
  }
});

// 添加isChannelSelected函数供外部使用
export function isChannelSelected(channelKey, selectedChannels) {
  if (!selectedChannels || !channelKey) return false;
  
  // 从channelKey中提取channel_name和shot_number
  // 格式通常是 `${channel.channel_name}_${channel.shot_number}`
  return selectedChannels.some(channel => {
    const currentChannelKey = `${channel.channel_name}_${channel.shot_number}`;
    return currentChannelKey === channelKey;
  });
}

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