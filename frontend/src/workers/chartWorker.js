// Web Worker for chart data processing

/**
 * MATLAB interp1 函数的 JavaScript 实现
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
 */
function calculateSamplingRate(X_value) {
  const deltaT = X_value[1] - X_value[0]; // 单位:s
  return 1 / (deltaT * 1000); // 转换为kHz
}

/**
 * 对数据进行重采样处理
 */
function sampleData(data, targetRate) {
  if (!data || !data.X_value || !data.Y_value) return null;

  // 计算原始采样频率
  const originalRate = calculateSamplingRate(data.X_value);
  
  // 如果原始频率接近目标频率(允许0.1%的误差),直接返回原始数据
  if (Math.abs(originalRate - targetRate) / targetRate < 0.001) {
    return {
      X_value: data.X_value,
      Y_value: data.Y_value,
      originalFrequency: data.originalFrequency,
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
        originalFrequency: data.originalFrequency,
        originalDataPoints: data.X_value.length
      };
    }
  } else {
    // 需要降采样
    const samplingInterval = Math.floor(originalRate / targetRate);
    return {
      X_value: data.X_value.filter((_, i) => i % samplingInterval === 0),
      Y_value: data.Y_value.filter((_, i) => i % samplingInterval === 0),
      originalFrequency: data.originalFrequency,
      originalDataPoints: data.X_value.length
    };
  }

  return {
    X_value: newX,
    Y_value: newY,
    originalFrequency: data.originalFrequency,
    originalDataPoints: data.X_value.length
  };
}

// 创建高斯核函数
function createGaussianKernel(sigma, size) {
  const kernel = [];
  const center = Math.floor(size / 2);
  const sigma2 = 2 * sigma * sigma;
  let sum = 0;

  for (let i = 0; i < size; i++) {
    const x = i - center;
    const value = Math.exp(-x * x / sigma2);
    kernel.push(value);
    sum += value;
  }

  return kernel.map(value => value / sum);
}

// 高斯平滑处理
function gaussianSmooth(data, sigma) {
  const kernelSize = Math.ceil(sigma * 6);
  const kernel = createGaussianKernel(sigma, kernelSize);
  const halfSize = Math.floor(kernelSize / 2);
  const smoothedData = [];

  for (let i = 0; i < data.length; i++) {
    let smoothedValue = 0;
    for (let j = 0; j < kernelSize; j++) {
      const dataIndex = i + j - halfSize;
      if (dataIndex >= 0 && dataIndex < data.length) {
        smoothedValue += data[dataIndex] * kernel[j];
      }
    }
    smoothedData.push(smoothedValue);
  }

  return smoothedData;
}

// 数据平滑插值
function interpolateData(data, t) {
  if (t === 0) return data;
  const sigma = t * 20;
  return gaussianSmooth(data, sigma);
}

// 处理异常数据段
function processErrorSegment(errorSegment, sampledData) {
  try {
    if (!errorSegment || !sampledData) return null;
    
    // 找到对应的起始和结束索引
    const startIndex = sampledData.X_value.findIndex(x => x >= errorSegment[0]);
    const endIndex = sampledData.X_value.findIndex(x => x >= errorSegment[errorSegment.length - 1]);
    
    if (startIndex === -1 || endIndex === -1) return null;

    return {
      X: errorSegment,
      Y: sampledData.Y_value.slice(startIndex, endIndex + 1)
    };
  } catch (error) {
    console.error('Error in processErrorSegment:', error);
    return null;
  }
}

// 主要的消息处理函数
self.onmessage = function(e) {
  try {
    const { type, data } = e.data;

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
          processedData = {
            ...sampledData,
            Y_value: interpolateData(sampledData.Y_value, smoothnessValue)
          };
        }

        // 确保所有必要的数据都存在
        if (!processedData.X_value || !processedData.Y_value) {
          throw new Error('Processed data is incomplete');
        }

        self.postMessage({
          type: 'processedData',
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
          data: {
            channelKey,
            processedErrors
          }
        });
        break;
      }
    }
  } catch (error) {
    self.postMessage({
      type: 'error',
      error: error.message
    });
  }
}; 