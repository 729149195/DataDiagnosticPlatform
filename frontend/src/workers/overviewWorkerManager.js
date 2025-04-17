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
    this.pendingTasks = new Map(); // 存储等待中的任务
    this.processingLimit = 4; // 同时处理的最大任务数
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
          
          // 优化的降采样算法
          // 始终保留第一个和最后一个点
          sampledX.push(X_value[0]);
          sampledY.push(Y_value[0]);
          
          // 分桶采样 - 处理大型数据集时分批进行以避免长时间计算
          const batchSize = 1000;
          const batches = Math.ceil((totalPoints - 2) / batchSize);
          
          for (let batchIndex = 0; batchIndex < batches; batchIndex++) {
            const startIdx = batchIndex * batchSize + 1;
            const endIdx = Math.min(startIdx + batchSize, totalPoints - 1);
            
            for (let i = startIdx; i < endIdx; i += step) {
              // 对当前桶内的数据找出Y值范围最大的点
              let maxRangeIndex = i;
              let maxRange = 0;
              
              const bucketEnd = Math.min(i + step, endIdx);
              for (let j = i; j < bucketEnd; j++) {
                // 找出局部变化最大的点 - 优化计算逻辑
                const prevJ = Math.max(0, j - 1);
                const nextJ = Math.min(totalPoints - 1, j + 1);
                // 使用绝对值差作为变化指标
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
              
              // 每处理50个点检查一次是否需要让出线程
              if (sampledX.length % 50 === 0) {
                // 使用setTimeout(0)让出线程时间，比Atomics更安全兼容
                setTimeout(() => {}, 0);
              }
            }
          }
          
          // 添加最后一个点(如果尚未添加)
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
                  // 启动处理通知
                  self.postMessage({
                    type: 'processingStarted',
                    messageId,
                    channelKey
                  });
                  
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
        
        // 避免在渲染帧中处理过多任务
        if (window.requestIdleCallback) {
          // 使用requestIdleCallback而不是requestAnimationFrame，更适合后台处理
          window.requestIdleCallback(() => this.handleWorkerMessage(event), { timeout: 500 });
        } else {
          // 降级使用setTimeout
          setTimeout(() => this.handleWorkerMessage(event), 0);
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
    
    // 防止积压，每次处理最多批量启动2个任务
    const batchProcess = () => {
      // 延迟执行，避免连续处理多个任务导致阻塞
      setTimeout(() => {
        this.actuallyProcessData(task.options, task.resolve, task.reject);
        
        // 如果队列中还有任务且处理中任务少于限制，继续处理下一个
        if (this.pendingTasks.size > 0 && this.callbacks.size < this.processingLimit) {
          const [nextKey, nextTask] = this.pendingTasks.entries().next().value;
          this.pendingTasks.delete(nextKey);
          setTimeout(() => {
            this.actuallyProcessData(nextTask.options, nextTask.resolve, nextTask.reject);
          }, 50); // 小延迟，避免同时启动太多任务
        }
      }, 0);
    };
    
    // 使用requestIdleCallback来调度任务处理
    if (window.requestIdleCallback) {
      window.requestIdleCallback(batchProcess, { timeout: 200 });
    } else {
      batchProcess();
    }
  }

  /**
   * 实际执行数据处理
   * @private
   */
  actuallyProcessData(options, resolve, reject) {
    const { channelData, channelKey, downsample = true, maxPoints = 500 } = options;
    const cacheKey = `overviewData-${channelKey}-${maxPoints}`;
    
    // 尝试从缓存中获取数据
    const cached = dataCache.get(cacheKey);
    if (cached) {
      resolve(cached.data);
      // 更新缓存时间戳但保持数据不变
      dataCache.put(cacheKey, { ...cached, timestamp: Date.now() });
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
   * @param {number} options.maxPoints - 最大点数
   * @returns {Promise} 处理结果的Promise
   */
  processData(options) {
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
    }
  }

  /**
   * 处理Worker消息
   * @private
   */
  handleWorkerMessage(event) {
    const { type, messageId, data, error, channelKey } = event.data;
    
    // 先执行任何自定义消息处理
    if (this.onmessage) {
      this.onmessage(event);
    }
    
    if (type === 'processingStarted') {
      // 处理已开始，不执行回调
      return;
    }
    
    // 查找并执行对应的回调函数
    const callback = this.callbacks.get(messageId);
    if (callback) {
      try {
        if (error) {
          callback(null, error);
        } else {
          // 如果数据很大，考虑使用缓存策略
          if (data && channelKey) {
            const cacheKey = `overviewData-${channelKey}-${data.X.length}`;
            dataCache.put(cacheKey, { data, timestamp: Date.now() });
          }
          callback(data);
        }
      } catch (err) {
        console.error('处理Worker响应时出错:', err);
      } finally {
        this.callbacks.delete(messageId);
        // 处理完一个任务后，尝试处理等待队列
        this.processNextPendingTask();
      }
    }
  }
}

// 创建单例实例
const overviewWorkerManager = new OverviewWorkerManager();
export default overviewWorkerManager; 