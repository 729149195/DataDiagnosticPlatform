// Web Worker for chart data processing
import { PatternMatcher } from '../views/AnomalyLabelView/Sketch/pattern-matcher.js';

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
 * 对异常数据段进行处理
 * @param {Object} errorSegment - 错误数据段
 * @param {Array} sampledData - 采样后的数据
 * @returns {Object} 处理后的错误数据段
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

// 主要的消息处理函数
self.onmessage = function(e) {
  try {
    const { type, data, messageId } = e.data;

    switch (type) {
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
    console.error('Worker error:', error);
    self.postMessage({
      type: 'error',
      messageId: e.data.messageId,
      error: error.message || 'Unknown error occurred'
    });
  }
}; 