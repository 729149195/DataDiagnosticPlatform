/**
 * Overview Worker 管理器
 * 用于管理和复用 overviewWorker 实例，专门用于处理 OverviewBrush 组件的数据
 */
import { dataCache } from '../services/cacheManager';

class OverviewWorkerManager {
  constructor() {
    this.worker = null;
    this.callbacks = new Map();
    this.messageId = 0;
    this.onmessage = null; // 允许外部设置消息处理函数
  }

  /**
   * 获取 Worker 实例
   * @returns {Worker} Worker 实例
   */
  getWorker() {
    if (!this.worker) {
      // 使用内联Worker实现，避免创建额外文件
      const workerBlob = new Blob([`
        // 内联的 overviewWorker 核心逻辑
        
        /**
         * 对数据进行降采样，专门针对总览视图优化
         * @param {Object} data - 通道数据
         * @param {number} maxPoints - 最大点数，用于控制图表性能
         * @returns {Object} 降采样后的数据
         */
        function downsampleData(data, maxPoints = 500) {
          const { X_value, Y_value } = data;
          const totalPoints = X_value.length;
          
          // 如果数据点少于最大点数，直接返回
          if (totalPoints <= maxPoints) {
            return { X: [...X_value], Y: [...Y_value] };
          }
          
          // 计算采样间隔
          const step = Math.ceil(totalPoints / maxPoints);
          
          // 采样结果
          const sampledX = [];
          const sampledY = [];
          
          // LTTB算法 (Largest Triangle Three Buckets)
          // 实现高效的可视化降采样
          
          // 始终保留第一个和最后一个点
          sampledX.push(X_value[0]);
          sampledY.push(Y_value[0]);
          
          // 分桶采样
          for (let i = 1; i < totalPoints - 1; i += step) {
            // 对当前桶内的数据找出Y值范围最大的点
            let maxRangeIndex = i;
            let maxRange = 0;
            
            const bucketEnd = Math.min(i + step, totalPoints - 1);
            for (let j = i; j < bucketEnd; j++) {
              // 找出局部变化最大的点
              const prevJ = Math.max(0, j - 1);
              const nextJ = Math.min(totalPoints - 1, j + 1);
              const range = Math.abs(Y_value[j] - Y_value[prevJ]) + 
                           Math.abs(Y_value[nextJ] - Y_value[j]);
              
              if (range > maxRange) {
                maxRangeIndex = j;
                maxRange = range;
              }
            }
            
            // 添加选中的点
            sampledX.push(X_value[maxRangeIndex]);
            sampledY.push(Y_value[maxRangeIndex]);
          }
          
          // 添加最后一个点
          if (sampledX[sampledX.length - 1] !== X_value[totalPoints - 1]) {
            sampledX.push(X_value[totalPoints - 1]);
            sampledY.push(Y_value[totalPoints - 1]);
          }
          
          return { X: sampledX, Y: sampledY };
        }
        
        // 主要的消息处理函数
        self.onmessage = function(e) {
          try {
            const { type, data, messageId } = e.data;
        
            switch (type) {
              case 'processData': {
                const { channelData, channelKey, downsample, maxPoints } = data;
                
                // 检查数据有效性
                if (!channelData || !channelData.X_value || !channelData.Y_value) {
                  throw new Error('无效的数据格式');
                }
                
                // 对数据进行降采样处理
                let processedData;
                if (downsample) {
                  processedData = downsampleData(channelData, maxPoints);
                } else {
                  // 不降采样时直接复制数据
                  processedData = {
                    X: [...channelData.X_value],
                    Y: [...channelData.Y_value]
                  };
                }
                
                // 发送处理结果
                self.postMessage({
                  type: 'processedOverviewData',
                  messageId,
                  channelKey,
                  data: processedData
                });
                break;
              }
              
              default:
                throw new Error(\`不支持的操作类型: \${type}\`);
            }
          } catch (error) {
            self.postMessage({
              type: 'error',
              messageId,
              error: error.message || '处理数据时发生错误'
            });
          }
        };
      `], { type: 'application/javascript' });

      const workerUrl = URL.createObjectURL(workerBlob);
      this.worker = new Worker(workerUrl, { type: 'module' });
      URL.revokeObjectURL(workerUrl); // 释放URL

      // 处理Worker返回的消息
      this.worker.onmessage = (event) => {
        const { type, messageId, data, error, channelKey } = event.data;
        
        // 使用微任务来处理消息回调，避免长时间阻塞主线程
        queueMicrotask(() => {
          if (this.onmessage) {
            // 如果设置了外部消息处理函数，直接转发
            this.onmessage(event);
          }
          
          // 查找并执行对应的回调函数
          const callback = this.callbacks.get(messageId);
          if (callback) {
            if (error) {
              callback(null, error);
            } else {
              callback(data);
            }
            this.callbacks.delete(messageId);
          }
        });
      };

      this.worker.onerror = (error) => {
        console.error('Overview Worker error:', error);
        // 在发生错误时通知所有等待中的回调
        this.callbacks.forEach((callback, id) => {
          callback(null, error.message || 'Worker error occurred');
          this.callbacks.delete(id);
        });
      };
    }

    return this.worker;
  }

  /**
   * 处理数据
   * @param {Object} options - 处理选项
   * @param {Object} options.channelData - 通道数据
   * @param {string} options.channelKey - 通道键值
   * @param {boolean} options.downsample - 是否降采样
   * @param {number} options.maxPoints - 最大点数
   * @returns {Promise} 处理结果的Promise
   */
  processData(options) {
    const { channelData, channelKey, downsample = true, maxPoints = 500 } = options;
    const cacheKey = `overviewData-${channelKey}-${maxPoints}`;
    
    // 尝试从缓存中获取数据
    const cached = dataCache.get(cacheKey);
    if (cached) return Promise.resolve(cached.data);
    
    // 发送消息到Worker处理
    this.getWorker().postMessage({
      type: 'processData',
      messageId: this.messageId++,
      data: {
        channelData,
        channelKey,
        downsample,
        maxPoints
      }
    });
  }

  /**
   * 终止 Worker
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
const overviewWorkerManager = new OverviewWorkerManager();
export default overviewWorkerManager; 