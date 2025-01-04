export class PatternMatcher {
  constructor(options = {
    distanceMetric: 'euclidean',
    matchThreshold: 3.0,
    windowSize: 1.5
  }) {
    this.options = options;
  }

  // 计算形状特征
  getShapeSignature(points) {
    const features = {
      slopes: [],
      trendChanges: 0,
      maxSlope: 0,
      variability: 0,
      yRange: 0
    };
    
    // 计算y值范围
    const minY = Math.min(...points.map(p => p.y));
    const maxY = Math.max(...points.map(p => p.y));
    features.yRange = maxY - minY;
    
    // 计算斜率和变化
    let prevSlope = null;
    let slopeSum = 0;
    let slopeSqSum = 0;
    
    for(let i = 1; i < points.length; i++) {
      const slope = (points[i].y - points[i-1].y) / 
                   Math.max(points[i].x - points[i-1].x, 0.001);
      
      features.slopes.push(slope);
      features.maxSlope = Math.max(features.maxSlope, Math.abs(slope));
      
      slopeSum += slope;
      slopeSqSum += slope * slope;
      
      if(prevSlope !== null) {
        // 计算趋势变化
        if((slope > 0.1 && prevSlope < -0.1) || (slope < -0.1 && prevSlope > 0.1)) {
          features.trendChanges++;
        }
      }
      prevSlope = slope;
    }
    
    // 计算斜率的变异系数
    const avgSlope = slopeSum / features.slopes.length;
    const slopeVariance = (slopeSqSum / features.slopes.length) - (avgSlope * avgSlope);
    features.variability = Math.sqrt(slopeVariance) / (Math.abs(avgSlope) + 0.001);
    
    return features;
  }

  // 比较两个形状的相似度
  compareShapes(shape1, shape2) {
    // 计算趋势变化的差异
    const trendDiff = Math.abs(shape1.trendChanges - shape2.trendChanges) / 
                     Math.max(Math.max(shape1.trendChanges, shape2.trendChanges), 1);
    
    // 计算变异性的差异
    const variabilityDiff = Math.abs(shape1.variability - shape2.variability) / 
                           Math.max(shape1.variability, shape2.variability, 1);
    
    // 计算最大斜率的差异
    const maxSlopeDiff = Math.abs(shape1.maxSlope - shape2.maxSlope) / 
                        Math.max(shape1.maxSlope, shape2.maxSlope, 0.1);
    
    // 如果一个是复杂曲线（多个趋势变化和高变异性），另一个接近水平线（低变异性和小斜率）
    const isComplex1 = shape1.trendChanges > 2 && shape1.variability > 1;
    const isComplex2 = shape2.trendChanges > 2 && shape2.variability > 1;
    const isFlat1 = shape1.maxSlope < 0.1 && shape1.variability < 0.5;
    const isFlat2 = shape2.maxSlope < 0.1 && shape2.variability < 0.5;
    
    if((isComplex1 && isFlat2) || (isComplex2 && isFlat1)) {
      return 1.0;  // 完全不匹配
    }
    
    // 综合评分
    return (trendDiff * 0.4 + variabilityDiff * 0.4 + maxSlopeDiff * 0.2);
  }

  // 归一化处理
  normalizeSequence(points) {
    const minY = Math.min(...points.map(p => p.y));
    const maxY = Math.max(...points.map(p => p.y));
    const range = maxY - minY || 1;

    return points.map(p => ({
      ...p,
      y: (p.y - minY) / range
    }));
  }

  // 计算DTW距离
  computeDTWDistance(queryPattern, dataSegment) {
    const m = queryPattern.length;
    const n = dataSegment.length;
    
    const dtw = Array(m + 1).fill(null).map(() => Array(n + 1).fill(Infinity));
    dtw[0][0] = 0;

    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        const cost = Math.abs(queryPattern[i-1].y - dataSegment[j-1].y);
        dtw[i][j] = cost + Math.min(
          dtw[i-1][j],
          dtw[i][j-1],
          dtw[i-1][j-1]
        );
      }
    }

    return dtw[m][n] / Math.max(m, n);
  }

  findPatterns(queryPattern, dataPoints, xValues) {
    const matches = [];
    if (!queryPattern || !queryPattern.length || !dataPoints || !dataPoints.length || !xValues || !xValues.length) {
      return matches;
    }

    // 计算查询模式的形状特征
    const queryShape = this.getShapeSignature(queryPattern);
    
    // 将数据点转换为正确的格式
    const normalizedDataPoints = dataPoints.map((y, index) => ({
      x: xValues[index],
      y: y,
      origX: xValues[index],
      origY: y
    }));

    // 对查询模式进行归一化
    const normalizedQuery = this.normalizeSequence(queryPattern);

    // 使用不同的窗口大小
    const windowSizes = [
      Math.floor(queryPattern.length * 0.5),
      Math.floor(queryPattern.length * 0.75),
      Math.floor(queryPattern.length * 1.0),
      Math.floor(queryPattern.length * 1.5),
      Math.floor(queryPattern.length * 2.0)
    ];

    for (const windowSize of windowSizes) {
      // 滑动窗口搜索
      for (let i = 0; i <= normalizedDataPoints.length - windowSize; i++) {
        const segment = normalizedDataPoints.slice(i, i + windowSize);
        
        // 计算形状特征
        const segmentShape = this.getShapeSignature(segment);
        
        // 计算形状差异
        const shapeDiff = this.compareShapes(queryShape, segmentShape);
        
        // 如果形状差异太大，跳过这个段
        if(shapeDiff > 0.8) {
          continue;
        }
        
        // 对数据段进行归一化
        const normalizedSegment = this.normalizeSequence(segment);

        // 计算DTW距离
        const distance = this.computeDTWDistance(normalizedQuery, normalizedSegment);
        
        // 综合考虑DTW距离和形状差异
        const finalDistance = distance * (1 + shapeDiff * 0.7);
        
        if (finalDistance < this.options.matchThreshold) {
          matches.push({
            range: [segment[0].origX, segment[segment.length - 1].origX],
            distance: finalDistance,
            confidence: 1 - (finalDistance / this.options.matchThreshold),
            shapeDiff: shapeDiff
          });
        }
      }
    }

    return this.mergeOverlappingMatches(matches);
  }

  mergeOverlappingMatches(matches) {
    if (matches.length <= 1) return matches;

    matches.sort((a, b) => a.range[0] - b.range[0]);
    const merged = [];
    let current = matches[0];

    for (let i = 1; i < matches.length; i++) {
      if (current.range[1] >= matches[i].range[0]) {
        // 合并重叠的匹配，选择形状更相似的
        if (matches[i].shapeDiff < current.shapeDiff) {
          current = matches[i];
        }
      } else {
        merged.push(current);
        current = matches[i];
      }
    }
    merged.push(current);

    return merged;
  }
}