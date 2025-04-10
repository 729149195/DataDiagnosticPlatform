/**
 * Chart Worker 管理器
 * 用于管理和复用 chartWorker 实例
 */
import { dataCache } from '../services/cacheManager';

// chartWorkerManager.js
//
// 注意：从v2.0开始，前端不再负责数据采样处理工作。
// 采样处理已经交由后端API完成，前端仅处理渲染相关工作。
// 当前保留此文件是为了兼容性考虑，后续版本可能会移除相关功能。
//

class ChartWorkerManager {
  constructor() {
    this.worker = null;
    this.callbacks = new Map();
    this.messageId = 0;
  }

  /**
   * 获取 Worker 实例
   * @returns {Worker} Worker 实例
   */
  getWorker() {
    if (!this.worker) {
      this.worker = new Worker(new URL('./chartWorker.js', import.meta.url), {
        type: 'module',
        credentials: 'same-origin'
      });

      this.worker.onmessage = (event) => {
        const { type, data, messageId, error } = event.data;
        
        // 查找并执行对应的回调函数
        const callback = this.callbacks.get(messageId);
        if (callback) {
          if (type === 'error') {
            callback(null, error);
          } else {
            callback(data);
          }
          this.callbacks.delete(messageId);
        }
      };

      this.worker.onerror = (error) => {
        console.error('Chart Worker error:', error);
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
   * @param {Object} channelData - 通道数据
   * @param {number} sampleRate - 采样率
   * @param {number} smoothnessValue - 平滑度
   * @param {string} channelKey - 通道键值
   * @param {string} color - 颜色
   * @param {string} xUnit - X轴单位
   * @param {string} yUnit - Y轴单位
   * @param {string} channelType - 通道类型
   * @param {number} channelNumber - 通道编号
   * @param {number} shotNumber - 炮号
   * @returns {Promise} 处理结果的Promise
   */
  async processData(channelData, sampleRate, smoothnessValue, channelKey, color, xUnit, yUnit, channelType, channelNumber, shotNumber) {
    const cacheKey = `chartData-${channelKey}-${sampleRate}-${smoothnessValue}`;
    const cached = dataCache.get(cacheKey);
    if (cached) return cached.data;
    
    console.log(`processData: 跳过采样处理，${channelKey} 的采样处理已由后端完成`);
    
    // 直接格式化数据并返回，不再调用worker进行采样处理
    const processedData = {
      processedData: channelData,
      channelKey,
      color,
      xUnit,
      yUnit,
      channelType,
      channelNumber,
      shotNumber
    };
    
    // 缓存处理结果
    dataCache.put(cacheKey, {
      data: processedData,
      timestamp: Date.now()
    });
    
    return processedData;
  }

  /**
   * 处理错误数据
   * @param {Array} errorData - 错误数据
   * @param {Object} sampledData - 采样后的数据
   * @param {string} channelKey - 通道键值
   * @returns {Promise} 处理结果的Promise
   */
  processErrorData(errorData, sampledData, channelKey) {
    return new Promise((resolve, reject) => {
      const messageId = this.messageId++;
      
      this.callbacks.set(messageId, (data, error) => {
        if (error) {
          reject(new Error(error));
        } else {
          resolve(data);
        }
      });

      this.getWorker().postMessage({
        type: 'processErrorData',
        messageId,
        data: {
          errorData,
          sampledData,
          channelKey
        }
      });
    });
  }

  /**
   * 查找模式匹配
   * @param {Array} queryPattern - 查询模式
   * @param {Array} dataPoints - 数据点
   * @param {Array} xValues - X轴值
   * @returns {Promise} 处理结果的Promise
   */
  findPatterns(queryPattern, dataPoints, xValues) {
    return new Promise((resolve, reject) => {
      const messageId = this.messageId++;
      
      this.callbacks.set(messageId, (data, error) => {
        if (error) {
          reject(new Error(error));
        } else {
          resolve(data);
        }
      });

      this.getWorker().postMessage({
        type: 'findPatterns',
        messageId,
        data: {
          queryPattern,
          dataPoints,
          xValues
        }
      });
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
const chartWorkerManager = new ChartWorkerManager();
export default chartWorkerManager; 