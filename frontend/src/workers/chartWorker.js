// Web Worker for chart data processing

// 处理数据采样
function sampleData(data, sampleRate) {
  if (!data || !data.X_value || !data.Y_value) return null;
  
  const samplingInterval = Math.floor(1 / sampleRate);
  return {
    X_value: data.X_value.filter((_, i) => i % samplingInterval === 0),
    Y_value: data.Y_value.filter((_, i) => i % samplingInterval === 0),
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