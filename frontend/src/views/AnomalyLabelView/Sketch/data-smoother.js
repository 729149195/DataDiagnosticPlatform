// 数据平滑处理类
export class DataSmoother {
  constructor(parameters = {
    SMOOTH_MAXIMUM_ATTEMPTS: 10,
    DIVIDE_SECTION_MIN_HEIGHT_DATA: 0.1
  }) {
    this.parameters = parameters;
  }

  // 创建高斯核
  createGaussianKernel(sigma, size) {
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

  // 高斯平滑
  gaussianSmooth(data, sigma) {
    const kernelSize = Math.ceil(sigma * 6); // 核大小(通常为 6 * sigma)
    const kernel = this.createGaussianKernel(sigma, kernelSize);
    const halfSize = Math.floor(kernelSize / 2);
    const smoothedData = [];

    for (let i = 0; i < data.length; i++) {
      let smoothedValue = 0;
      for (let j = 0; j < kernelSize; j++) {
        const dataIndex = i + j - halfSize;
        if (dataIndex >= 0 && dataIndex < data.length) {
          smoothedValue += data[dataIndex].y * kernel[j];
        }
      }
      smoothedData.push({
        x: data[i].x,
        y: smoothedValue,
        origX: data[i].origX,
        origY: data[i].origY
      });
    }

    return smoothedData;
  }

  // 平滑插值
  interpolateData(data, smoothness) {
    if (smoothness === 0) {
      return data; // 不平滑直接返回
    }

    const sigma = smoothness * 20; // 根据 smoothness 调整平滑强度
    return this.gaussianSmooth(data, sigma);
  }

  // 计算切线
  tangent(p1, p2, flipY = false) {
    return (flipY ? (p1.y - p2.y) : (p2.y - p1.y)) / (p2.x - p1.x);
  }

  // 计算符号变化次数
  countSignVariations(data) {
    if (data.length < 2) return 0;
    
    let variations = 0;
    let lastTgSign = Math.sign(this.tangent(data[0], data[1]));
    
    for (let i = 1; i < data.length; i++) {
      const currTgSign = Math.sign(this.tangent(data[i-1], data[i]));
      if (lastTgSign != currTgSign && currTgSign !== 0) variations++;
      lastTgSign = currTgSign;
    }
    return variations;
  }

  // 平滑数据处理
  smoothData(dataArray, smoothness = 0.0) {
    if (!dataArray || dataArray.length === 0) {
      return [];
    }

    // 使用新的平滑逻辑
    if (smoothness > 0 && smoothness <= 1) {
      return this.interpolateData(dataArray, smoothness);
    }

    return dataArray; // 如果 smoothness 无效则返回原始数据
  }

  // 检查平滑后的数据是否满足要求
  checkSmoothedData(smoothedData, currentSignVariationNum, options) {
    return currentSignVariationNum >= options.minimumSignVarations &&
           currentSignVariationNum >= options.variationRatio * this.initialSignVariationNum;
  }
} 