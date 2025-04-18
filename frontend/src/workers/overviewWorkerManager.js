/**
 * Overview Worker 管理器
 * 用于管理和复用 overviewWorker 实例，专门用于处理 OverviewBrush 组件的数据
 * 经过优化，提供更快的渲染速度，满足粗糙概览的需求
 */
import { dataCache } from '../services/cacheManager';

class OverviewWorkerManager {
  constructor() {
    this.worker = null;
    this.callbacks = new Map();
    this.messageId = 0;
    this.onmessage = null; // 允许外部设置消息处理函数
    this.pendingTasks = new Map(); // 存储等待中的任务
    this.processingLimit = 2; // 限制同时处理的任务数，减少资源占用
    
    // 增强缓存设置
    this.cacheTimeToLive = 30 * 60 * 1000; // 缓存有效期30分钟
    this.cachedResults = new Map(); // 内存缓存，避免IndexedDB查询延迟
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
         * 对数据进行简化降采样，专为概览视图优化
         * 使用简单的均匀采样，大幅降低计算复杂度
         * @param {Object} data - 通道数据
         * @param {number} maxPoints - 最大点数，用于控制图表性能
         * @returns {Object} 降采样后的数据
         */
        function downsampleData(data, maxPoints = 200) {
          const { X_value, Y_value } = data;
          const totalPoints = X_value.length;
          
          // 如果数据点少于最大点数，直接返回
          if (totalPoints <= maxPoints) {
            return { X: [...X_value], Y: [...Y_value] };
          }
          
          // 计算采样间隔 - 简单均匀采样
          const step = Math.ceil(totalPoints / maxPoints);
          
          // 采样结果数组 - 预分配内存
          const sampledX = new Array(Math.ceil(totalPoints / step) + 2);
          const sampledY = new Array(Math.ceil(totalPoints / step) + 2);
          
          // 始终保留第一个点
          sampledX[0] = X_value[0];
          sampledY[0] = Y_value[0];
          
          // 简单均匀采样 - 大幅简化计算逻辑
          let sampleIndex = 1;
          for (let i = step; i < totalPoints - 1; i += step) {
            sampledX[sampleIndex] = X_value[i];
            sampledY[sampleIndex] = Y_value[i];
            sampleIndex++;
          }
          
          // 始终保留最后一个点
          if (totalPoints > 1) {
            sampledX[sampleIndex] = X_value[totalPoints - 1];
            sampledY[sampleIndex] = Y_value[totalPoints - 1];
            sampleIndex++;
          }
          
          // 调整数组大小为实际使用的长度
          return { 
            X: sampledX.slice(0, sampleIndex), 
            Y: sampledY.slice(0, sampleIndex) 
          };
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

      // 处理Worker返回的消息 - 简化处理流程
      this.worker.onmessage = (event) => {
        const { type, messageId, data, error, channelKey } = event.data;
        
        // 错误处理
        if (error) {
          this.handleWorkerError(messageId, error);
          return;
        }
        
        // 数据处理结果
        if (type === 'processedOverviewData' && data) {
          // 直接处理数据，避免多层嵌套和异步调用
          this.handleProcessedData(messageId, channelKey, data);
        }
        
        // 自定义消息处理
        if (this.onmessage) {
          this.onmessage(event);
        }
      };

      this.worker.onerror = (error) => {
        console.error('Overview Worker error:', error);
        // 在发生错误时通知所有等待中的回调
        this.callbacks.forEach((callback, id) => {
          callback(null, error.message || 'Worker error occurred');
          this.callbacks.delete(id);
        });
        
        // 清空待处理任务
        this.pendingTasks.clear();
      };
    }

    return this.worker;
  }

  /**
   * 处理Worker错误
   * @private
   */
  handleWorkerError(messageId, error) {
    const callback = this.callbacks.get(messageId);
    if (callback) {
      try {
        callback(null, error);
      } catch (err) {
        console.error('执行错误回调时出错:', err);
      } finally {
        this.callbacks.delete(messageId);
        this.processNextPendingTask();
      }
    }
  }

  /**
   * 处理Worker处理后的数据
   * @private
   */
  handleProcessedData(messageId, channelKey, data) {
    const callback = this.callbacks.get(messageId);
    if (callback) {
      try {
        // 执行回调
        callback(data);
        
        // 缓存数据
        if (channelKey && data) {
          const cacheKey = `overviewData-${channelKey}-${data.X.length}`;
          
          // 更新内存缓存
          this.cachedResults.set(cacheKey, {
            data,
            timestamp: Date.now()
          });
          
          // 更新全局缓存
          dataCache.put(cacheKey, { data, timestamp: Date.now() });
        }
      } catch (err) {
        console.error('处理数据时出错:', err);
      } finally {
        this.callbacks.delete(messageId);
        this.processNextPendingTask();
      }
    }
  }

  /**
   * 处理等待队列中的下一个任务
   * @private
   */
  processNextPendingTask() {
    if (this.pendingTasks.size === 0 || this.callbacks.size >= this.processingLimit) {
      return;
    }
    
    // 获取下一个待处理任务
    const [key, task] = this.pendingTasks.entries().next().value;
    this.pendingTasks.delete(key);
    
    // 直接处理任务
    this.actuallyProcessData(task.options, task.resolve, task.reject);
  }

  /**
   * 实际执行数据处理
   * @private
   */
  actuallyProcessData(options, resolve, reject) {
    const { channelData, channelKey, downsample = true, maxPoints = 200 } = options;
    const cacheKey = `overviewData-${channelKey}-${maxPoints}`;
    
    // 1. 首先检查内存缓存
    const memCached = this.cachedResults.get(cacheKey);
    if (memCached && (Date.now() - memCached.timestamp < this.cacheTimeToLive)) {
      resolve(memCached.data);
      return;
    }
    
    // 2. 检查dataCache缓存
    const cached = dataCache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp < this.cacheTimeToLive)) {
      // 更新内存缓存
      this.cachedResults.set(cacheKey, {
        data: cached.data,
        timestamp: Date.now()
      });
      resolve(cached.data);
      return;
    }
    
    // 生成新的消息ID
    const currentMessageId = this.messageId++;
    
    // 添加回调
    this.callbacks.set(currentMessageId, (data, error) => {
      if (error) {
        reject(error);
      } else {
        resolve(data);
      }
    });
    
    // 发送消息到Worker处理
    this.getWorker().postMessage({
      type: 'processData',
      messageId: currentMessageId,
      data: {
        channelData,
        channelKey,
        downsample,
        maxPoints
      }
    });
  }

  /**
   * 处理数据
   * @param {Object} options - 处理选项
   * @param {Object} options.channelData - 通道数据
   * @param {string} options.channelKey - 通道键值
   * @param {boolean} options.downsample - 是否降采样
   * @param {number} options.maxPoints - 最大点数，默认降低为200
   * @returns {Promise} 处理结果的Promise
   */
  processData(options) {
    // 确保maxPoints有合理默认值
    if (!options.maxPoints) {
      options.maxPoints = 200; // 降低默认点数以提高性能
    }
    
    return new Promise((resolve, reject) => {
      const { channelKey } = options;
      const taskKey = `task-${channelKey}-${Date.now()}`;
      
      // 检查当前处理中的任务数
      if (this.callbacks.size < this.processingLimit) {
        // 直接处理
        this.actuallyProcessData(options, resolve, reject);
      } else {
        // 加入等待队列
        this.pendingTasks.set(taskKey, { options, resolve, reject });
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
      this.pendingTasks.clear();
      this.cachedResults.clear();
    }
  }
}

// 创建单例实例
const overviewWorkerManager = new OverviewWorkerManager();
export default overviewWorkerManager; 