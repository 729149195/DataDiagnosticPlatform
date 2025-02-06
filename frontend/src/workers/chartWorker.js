// Web Worker for chart data processing
import { DataSmoother } from '../views/AnomalyLabelView/Sketch/data-smoother.js';
import { PatternMatcher } from '../views/AnomalyLabelView/Sketch/pattern-matcher.js';

/**
 * MATLAB interp1 函数的 JavaScript 实现
 *@param {Array} x - 原始x值数组(必须严格单调递增)
 * @param {Array} y - 原始y值数组 
 * @param {Array} xNew - 需要插值的新x点
 * @param {string} method - 插值方法 ('linear', 'nearest', 'spline', etc.)
 * @returns {Array} 插值后的y值数组
 */
function interp1(x, y, xNew, method = 'linear') {
  // 输入验证
  if (x.length !== y.length || x.length < 2) {
    throw new Error('MATLAB:interp1:NotEnoughPts');
  }

  // 验证x是否严格单调递增
  for (let i = 1; i < x.length; i++) {
    if (x[i] <= x[i-1]) {
      throw new Error('MATLAB:interp1:XNotUnique');
    }
  }

  const yNew = new Array(xNew.length);

  switch (method.toLowerCase()) {
    case 'linear':
      for (let i = 0; i < xNew.length; i++) {
        const xi = xNew[i];
        
        // 超出范围返回NaN
        if (xi < x[0] || xi > x[x.length - 1]) {
          yNew[i] = NaN;
          continue;
        }
        
        // 二分查找区间
        let low = 0;
        let high = x.length - 1;
        
        while (high - low > 1) {
          const mid = Math.floor((low + high) / 2);
          if (x[mid] <= xi) {
            low = mid;
          } else {
            high = mid;
          }
        }
        
        // 处理刚好等于某个点的情况
        if (xi === x[low]) {
          yNew[i] = y[low];
        } else if (xi === x[high]) {
          yNew[i] = y[high];
        } else {
          // 线性插值
          const t = (xi - x[low]) / (x[high] - x[low]);
          yNew[i] = y[low] + t * (y[high] - y[low]);
        }
      }
      break;

    default:
      throw new Error('MATLAB:interp1:InvalidMethod');
  }
  
  return yNew;
}

/**
 * 计算数据的原始采样频率(kHz)
 * @param {Array} X_value - 时间序列数据(单位:s)
 * @returns {number} 采样频率(kHz)
 */
function calculateSamplingRate(X_value) {
  const deltaT = X_value[1] - X_value[0]; // 单位:s
  return 1 / (deltaT * 1000); // 转换为kHz
}

/**
 * 对数据进行重采样处理
 * @param {Object} data - 包含 X_value 和 Y_value 的数据对象
 * @param {number} targetRate - 目标采样频率(kHz)
 * @returns {Object} 重采样后的数据对象
 */
function sampleData(data, targetRate) {
  // 计算原始采样频率
  const originalRate = calculateSamplingRate(data.X_value);
  
  // 如果原始频率接近目标频率(允许0.1%的误差),直接返回原始数据
  if (Math.abs(originalRate - targetRate) / targetRate < 0.001) {
    return {
      X_value: data.X_value,
      Y_value: data.Y_value,
      originalFrequency: originalRate,
      originalDataPoints: data.X_value.length
    };
  }

  // 计算新的时间点
  const startTime = data.X_value[0];
  const endTime = data.X_value[data.X_value.length - 1];
  const deltaT = 1 / (targetRate * 1000); // 转换为秒
  const numPoints = Math.floor((endTime - startTime) / deltaT) + 1;
  
  // 生成新的等间隔时间点
  const newX = Array.from({length: numPoints}, (_, i) => startTime + i * deltaT);

  let newY;
  if (originalRate < targetRate) {
    // 需要插值增加采样率
    try {
      newY = interp1(data.X_value, data.Y_value, newX, 'linear');
      
      // 处理可能的NaN值
      for (let i = 0; i < newY.length; i++) {
        if (isNaN(newY[i])) {
          if (i === 0) {
            newY[i] = data.Y_value[0];
          } else if (i === newY.length - 1) {
            newY[i] = data.Y_value[data.Y_value.length - 1];
          } else {
            // 使用临近的有效值
            let j = i - 1;
            while (j >= 0 && isNaN(newY[j])) j--;
            if (j >= 0) {
              newY[i] = newY[j];
            } else {
              j = i + 1;
              while (j < newY.length && isNaN(newY[j])) j++;
              newY[i] = j < newY.length ? newY[j] : data.Y_value[0];
            }
          }
        }
      }
    } catch (error) {
      console.error('Interpolation failed:', error);
      return {
        X_value: data.X_value,
        Y_value: data.Y_value,
        originalFrequency: originalRate,
        originalDataPoints: data.X_value.length
      };
    }
  } else {
    // 需要降采样
    const samplingInterval = Math.floor(originalRate / targetRate);
    return {
      X_value: data.X_value.filter((_, i) => i % samplingInterval === 0),
      Y_value: data.Y_value.filter((_, i) => i % samplingInterval === 0),
      originalFrequency: originalRate,
      originalDataPoints: data.X_value.length
    };
  }

  return {
    X_value: newX,
    Y_value: newY,
    originalFrequency: originalRate,
    originalDataPoints: data.X_value.length
  };
}

/**
 * 二分查找起始索引
 * @param {Array} array - 要搜索的数组
 * @param {number} startX - 要查找的值
 * @returns {number} 找到的索引
 */
function findStartIndex(array, startX) {
  let low = 0;
  let high = array.length - 1;
  let result = -1;
  while (low <= high) {
    let mid = Math.floor((low + high) / 2);
    if (array[mid] >= startX) {
      result = mid;
      high = mid - 1;
    } else {
      low = mid + 1;
    }
  }
  return result;
}

/**
 * 二分查找结束索引
 * @param {Array} array - 要搜索的数组
 * @param {number} endX - 要查找的值
 * @returns {number} 找到的索引
 */
function findEndIndex(array, endX) {
  let low = 0;
  let high = array.length - 1;
  let result = -1;
  while (low <= high) {
    let mid = Math.floor((low + high) / 2);
    if (array[mid] <= endX) {
      result = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return result;
}

/**
 * 对异常数据段进行采样处理
 * @param {Object} errorSegment - 错误数据段
 * @param {Array} sampledData - 采样后的数据
 * @returns {Object} 采样后的错误数据段
 */
function processErrorSegment(errorSegment, sampledData) {
  if (errorSegment.length === 0) return { X: [], Y: [] };

  const startX = errorSegment[0];
  const endX = errorSegment[errorSegment.length - 1];

  const startIndex = findStartIndex(sampledData.X_value, startX);
  const endIndex = findEndIndex(sampledData.X_value, endX);

  if (startIndex === -1 || endIndex === -1 || startIndex > endIndex) {
    return { X: [], Y: [] };
  }

  const sampledX = sampledData.X_value
    .slice(startIndex, endIndex + 1)
    .filter(x => x >= startX && x <= endX);
  const sampledY = sampledData.Y_value
    .slice(startIndex, endIndex + 1)
    .filter((_, i) => sampledX.includes(sampledData.X_value[startIndex + i]));

  return { X: sampledX, Y: sampledY };
}

function compressData(data) {
  return {
    X: compressArray(data.X_value),
    Y: compressArray(data.Y_value),
    meta: data.meta
  };
}

function compressArray(arr) {
  // 使用delta encoding + TypedArray压缩
  const deltas = new Float32Array(arr.length);
  let prev = arr[0];
  deltas[0] = prev;
  for (let i = 1; i < arr.length; i++) {
    deltas[i] = arr[i] - prev;
    prev = arr[i];
  }
  return deltas;
}

// 主要的消息处理函数
self.onmessage = function(e) {
  console.log('Worker received:', e.data.type); // 调试日志
  try {
    const { type, data, messageId } = e.data;

    switch (type) {
      case 'processData': {
        const { channelData, sampleRate, smoothnessValue, channelKey, color, xUnit, yUnit, channelType, channelNumber, shotNumber } = data;
        
        // 采样数据
        const sampledData = sampleData(channelData, sampleRate);
        if (!sampledData) {
          throw new Error('Failed to sample data');
        }
        
        // 平滑处理
        let processedData = sampledData;
        if (smoothnessValue > 0 && smoothnessValue <= 1) {
          const dataSmoother = new DataSmoother();
          processedData = {
            ...sampledData,
            Y_value: dataSmoother.interpolateData(sampledData.Y_value.map((y, i) => ({
              x: sampledData.X_value[i],
              y: y,
              origX: sampledData.X_value[i],
              origY: y
            })), smoothnessValue).map(p => p.y)
          };
        }

        // 确保所有必要的数据都存在
        if (!processedData.X_value || !processedData.Y_value) {
          throw new Error('Processed data is incomplete');
        }

        self.postMessage({
          type: 'processedData',
          messageId,
          data: {
            processedData,
            channelKey,
            color,
            xUnit,
            yUnit,
            channelType,
            channelNumber,
            shotNumber,
            errorsData: [] // 初始化为空数组，错误数据会通过单独的消息更新
          }
        });
        break;
      }

      case 'processErrorData': {
        const { errorData, sampledData, channelKey } = data;
        
        if (!Array.isArray(errorData)) {
          throw new Error('Error data must be an array');
        }

        const processedErrors = errorData.map(error => {
          if (!error.X_error || !Array.isArray(error.X_error)) return null;
          
          const segments = error.X_error
            .map(segment => processErrorSegment(segment, sampledData))
            .filter(segment => segment !== null);

          return {
            color: error.color,
            person: error.person,
            segments
          };
        }).filter(error => error !== null && error.segments.length > 0);

        self.postMessage({
          type: 'processedErrorData',
          messageId,
          data: {
            channelKey,
            processedErrors
          }
        });
        break;
      }

      case 'findPatterns': {
        const { queryPattern, dataPoints, xValues } = data;
        const patternMatcher = new PatternMatcher({
          distanceMetric: 'euclidean',
          matchThreshold: 1.0,
          windowSize: 1.5
        });

        // 将数据点转换为正确的格式
        const normalizedDataPoints = dataPoints.map((y, index) => ({
          x: xValues[index],
          y: y,
          origX: xValues[index],
          origY: y
        }));

        const matches = patternMatcher.findPatterns(queryPattern, normalizedDataPoints.map(p => p.y), normalizedDataPoints.map(p => p.x));

        self.postMessage({
          type: 'patternMatches',
          messageId,
          data: matches
        });
        break;
      }

      default:
        throw new Error(`Unknown message type: ${type}`);
    }
  } catch (error) {
    // 确保错误消息中包含 messageId
    self.postMessage({
      type: 'error',
      messageId: e.data.messageId,
      error: error.message || 'Unknown error occurred'
    });
  }
  console.log('Worker processed:', result); // 调试日志
}; 