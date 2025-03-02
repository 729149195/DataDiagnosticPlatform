<template>
  <div class="overview-container">
    <el-divider />
    <div class="overview-content">
      <span class="brush-controls-left">
        <el-tag type="info">总览条起点</el-tag>
        <el-input size="small" style="width: 80px;" v-model="brush_begin" @blur="handleInputBlur('begin')"
          @keyup.enter="handleInputBlur('begin')"></el-input>
      </span>
      <div class="overview-svg-container" ref="chartContainer">
        <div v-if="isLoading" class="loading-overlay">
          <el-icon class="loading-icon"><Loading /></el-icon>
          <span>加载中...</span>
        </div>
        <svg id="overview-svg" class="overview-chart" @dblclick="handleDblClick"></svg>
      </div>
      <span class="brush-controls-right">
        <el-tag type="info">总览条终点</el-tag>
        <el-input size="small" style="width: 80px" v-model="brush_end" @blur="handleInputBlur('end')"
          @keyup.enter="handleInputBlur('end')"></el-input>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useStore } from 'vuex';
// 移除Highcharts
// import * as Highcharts from 'highcharts';
// import 'highcharts/modules/boost';  // 使用官方的boost模块
import debounce from 'lodash/debounce';
import { ElMessage } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';
import overviewWorkerManager from '@/workers/overviewWorkerManager'; // 引入专用的Worker管理器

const store = useStore();
const chartContainer = ref(null);

// 响应式引用
const overviewData = ref([]);
// 移除chartInstance
// const chartInstance = ref(null);
const updatingBrush = ref(false);
const originalDomains = ref({});
const isLoading = ref(false);
const extremes = ref(null);
const processedDataCache = ref({}); // 缓存处理后的数据
// 添加SVG相关引用
const svgElement = ref(null);
const maskRectLeft = ref(null);
const maskRectRight = ref(null);

// 从store获取数据
const brush_begin = computed({
  get: () => store.state.brush_begin,
  set: (value) => store.commit('updatebrush', { begin: value, end: brush_end.value })
});

const brush_end = computed({
  get: () => store.state.brush_end,
  set: (value) => store.commit('updatebrush', { begin: brush_begin.value, end: value })
});

const selectedChannels = computed(() => store.state.selectedChannels);
const channelDataCache = computed(() => store.state.channelDataCache);
const domains = computed(() => ({
  x: store.state.xDomains,
  y: store.state.yDomains
}));

// 处理窗口大小变化
const handleResize = debounce(() => {
  if (overviewData.value && overviewData.value.length > 0) {
    // 记住当前的刷选状态
    const currentExtreme = extremes.value;
    
    // 重新渲染图表
    renderChart(false);
    
    // 如果原来有滑动块选择，重新设置
    if (currentExtreme && svgElement.value) {
      nextTick(() => {
        try {
          updateBrush(currentExtreme.min, currentExtreme.max);
        } catch (error) {
          console.warn('窗口大小变化时更新遮罩区域出错:', error);
        }
      });
    }
  }
}, 300);

// 组件挂载和卸载
onMounted(() => {
  window.addEventListener('resize', handleResize);
  
  // 设置Worker消息处理函数
  setupWorkerHandler();
  
  // 延迟初始化以确保DOM渲染完成
  setTimeout(() => {
    svgElement.value = document.getElementById('overview-svg');
    checkDataAndRender();
  }, 500);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  
  // 移除双击事件监听
  const chartContainer = document.getElementById('overview-svg');
  if (chartContainer) {
    chartContainer.removeEventListener('dblclick', handleDblClick);
  }
  
  // 终止Worker
  overviewWorkerManager.terminate();
});

// 设置Worker消息处理
const setupWorkerHandler = () => {
  overviewWorkerManager.onmessage = function(e) {
    const { type, data, error, channelKey } = e.data;
    
    if (error) {
      console.error('Worker error:', error);
      isLoading.value = false;
      return;
    }
    
    if (type === 'processedOverviewData') {
      // 缓存处理后的数据
      processedDataCache.value[channelKey] = data;
      
      // 检查是否所有通道数据都已处理完成
      const pendingChannels = selectedChannels.value.filter(channel => {
        const key = `${channel.channel_name}_${channel.shot_number}`;
        return !processedDataCache.value[key];
      });
      
      if (pendingChannels.length === 0) {
        // 所有通道数据已处理完成，准备渲染
        prepareDataForChart();
      }
    }
  };
};

// 监听选中通道的变化
watch(selectedChannels, (newChannels, oldChannels) => {
  if (!oldChannels) return;
  
  // 获取新旧通道的键集合
  const oldChannelKeys = new Set(oldChannels.map(ch => `${ch.channel_name}_${ch.shot_number}`));
  const newChannelKeys = new Set(newChannels.map(ch => `${ch.channel_name}_${ch.shot_number}`));
  
  // 获取被移除的通道键
  const removedChannelKeys = [...oldChannelKeys].filter(key => !newChannelKeys.has(key));
  
  // 从缓存中移除这些通道
  removedChannelKeys.forEach(key => {
    if (processedDataCache.value[key]) {
      delete processedDataCache.value[key];
    }
  });
  
  // 获取新添加的通道键
  const addedChannelKeys = [...newChannelKeys].filter(key => !oldChannelKeys.has(key));
  
  if (addedChannelKeys.length > 0 || removedChannelKeys.length > 0) {
    // 有通道添加或移除，重新加载数据
    checkDataAndRender();
  }
}, { deep: true });

// 监听通道数据缓存的变化
watch(channelDataCache, (newCache, oldCache) => {
  // 仅在有选中通道且当前无数据时才尝试重新获取
  if (selectedChannels.value.length > 0 && overviewData.value.length === 0) {
    checkDataAndRender();
  }
}, { deep: true });

// 检查数据是否准备好并渲染
const checkDataAndRender = () => {
  collectData();
};

// 并行处理所有通道数据
const collectData = async () => {
  // 检查是否有选中的通道
  if (!selectedChannels.value || selectedChannels.value.length === 0) {
    overviewData.value = [];
    clearChart();
    return;
  }
  
  isLoading.value = true;
  
  try {
    // 清空处理后的数据缓存
    processedDataCache.value = {};
    
    // 获取当前选中通道的键名列表
    const selectedChannelKeys = selectedChannels.value.map(channel => 
      `${channel.channel_name}_${channel.shot_number}`
    );
    
    // 并行处理每个通道的数据
    const promises = selectedChannels.value.map(async (channel) => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      
      try {
        // 使用store action获取数据
        const channelData = await store.dispatch('fetchChannelData', { channel });
        
        if (channelData && channelData.X_value && channelData.Y_value) {
          // 使用Worker处理数据 - 增加点数以提高细节显示
          overviewWorkerManager.processData({
            channelData: {
              X_value: [...channelData.X_value],
              Y_value: [...channelData.Y_value]
            },
            channelKey,
            downsample: true, // 启用降采样以提高性能
            maxPoints: 10000 // 大幅增加最大点数以显示更多细节
          });
        }
      } catch (error) {
        console.error(`获取通道 ${channelKey} 数据失败:`, error);
      }
    });
    
    // 等待所有请求完成
    await Promise.all(promises);
    // 如果在这个时候还没有数据处理完成，那么就需要等待Worker处理
    // Worker处理完成后会调用prepareDataForChart
    
    // 防止卡死，设置超时
    setTimeout(() => {
      if (isLoading.value) {
        isLoading.value = false;
        if (Object.keys(processedDataCache.value).length > 0) {
          prepareDataForChart();
        } else {
          console.warn('数据处理超时，尝试使用可用数据渲染');
          renderChart(true);
        }
      }
    }, 5000);
    
  } catch (error) {
    console.error('获取数据过程中发生错误:', error);
    isLoading.value = false;
  }
};

// 准备图表数据
const prepareDataForChart = () => {
  if (Object.keys(processedDataCache.value).length === 0) {
    console.warn('没有处理好的数据可用');
    isLoading.value = false;
    return;
  }
  
  // 将处理后的数据转换为图表可用格式
  const chartData = [];
  
  // 首先计算全局数据范围，用于智能降采样
  let globalYMin = Infinity;
  let globalYMax = -Infinity;
  
  // 预处理：计算全局Y值范围
  Object.entries(processedDataCache.value).forEach(([channelKey, data]) => {
    if (data && data.Y) {
      for (let i = 0; i < data.Y.length; i++) {
        const y = data.Y[i];
        if (y < globalYMin) globalYMin = y;
        if (y > globalYMax) globalYMax = y;
      }
    }
  });
  
  // 添加一些边距到Y值范围
  const globalYRange = globalYMax - globalYMin;
  const globalYPadding = globalYRange * 0.05;
  globalYMin = globalYMin - globalYPadding;
  globalYMax = globalYMax + globalYPadding;
  
  Object.entries(processedDataCache.value).forEach(([channelKey, data]) => {
    const channel = selectedChannels.value.find(
      ch => `${ch.channel_name}_${ch.shot_number}` === channelKey
    );
    
    if (channel && data && data.X && data.Y) {
      // 保留更多数据点以显示更多细节
      let X = data.X;
      let Y = data.Y;
      
      // 如果数据点超过1000个，进行简单的降采样
      if (X.length > 1000) {
        const step = Math.ceil(X.length / 1000);
        const sampledX = [];
        const sampledY = [];
        
        // 使用更智能的降采样算法，保留关键点
        let prevY = null;
        let prevSlope = null;
        
        for (let i = 0; i < X.length; i += step) {
          // 始终保留第一个点
          if (i === 0) {
            sampledX.push(X[i]);
            sampledY.push(Y[i]);
            prevY = Y[i];
            continue;
          }
          
          // 计算当前斜率
          const currentSlope = i > 0 ? (Y[i] - Y[i-1]) / (X[i] - X[i-1]) : 0;
          
          // 如果斜率变化明显，保留这个点（捕捉曲线变化）
          if (prevSlope !== null && Math.abs(currentSlope - prevSlope) > 0.1) {
            sampledX.push(X[i]);
            sampledY.push(Y[i]);
            prevY = Y[i];
            prevSlope = currentSlope;
            continue;
          }
          
          // 如果Y值变化明显，保留这个点
          if (prevY !== null && Math.abs(Y[i] - prevY) > (globalYMax - globalYMin) * 0.01) {
            sampledX.push(X[i]);
            sampledY.push(Y[i]);
            prevY = Y[i];
            prevSlope = currentSlope;
            continue;
          }
          
          // 常规采样
          if (i % step === 0) {
            sampledX.push(X[i]);
            sampledY.push(Y[i]);
            prevY = Y[i];
            prevSlope = currentSlope;
          }
        }
        
        // 确保包含最后一个点
        if (sampledX[sampledX.length - 1] !== X[X.length - 1]) {
          sampledX.push(X[X.length - 1]);
          sampledY.push(Y[Y.length - 1]);
        }
        
        X = sampledX;
        Y = sampledY;
      }
      
      chartData.push({
        channelName: channelKey,
        X_value: X,
        Y_value: Y,
        color: channel.color || '#7cb5ec'
      });
    }
  });
  
  overviewData.value = chartData;
  
  // 渲染图表
  if (chartData.length > 0) {
    renderChart(false);
  } else {
    isLoading.value = false;
    console.warn('没有有效数据用于渲染');
  }
};

// 清空图表
const clearChart = () => {
  if (svgElement.value) {
    svgElement.value.innerHTML = '';
  }
  isLoading.value = false;
};

// 渲染图表
const renderChart = (forceRender = false) => {
  if (overviewData.value.length === 0 && !forceRender) {
    console.warn('无数据可渲染');
    clearChart();
    isLoading.value = false;
    return;
  }
  
  // 确保容器存在
  if (!chartContainer.value) {
    console.error('图表容器不存在');
    isLoading.value = false;
    return;
  }
  
  // 确保SVG元素存在
  if (!svgElement.value) {
    svgElement.value = document.getElementById('overview-svg');
    if (!svgElement.value) {
      console.error('找不到SVG元素');
      isLoading.value = false;
      return;
    }
  }
  
  // 清空SVG
  svgElement.value.innerHTML = '';
  
  // 获取SVG尺寸
  const svgWidth = svgElement.value.clientWidth;
  const svgHeight = svgElement.value.clientHeight;
  
  // 设置图表边距
  const margin = {
    top: 5,
    right: 15,
    bottom: 20, // 为X轴留出空间
    left: 15
  };
  
  // 计算图表实际绘图区域
  const chartWidth = svgWidth - margin.left - margin.right;
  const chartHeight = svgHeight - margin.top - margin.bottom;
  
  // 计算全局数据范围
  let xMin = Infinity;
  let xMax = -Infinity;
  let yMin = Infinity;
  let yMax = -Infinity;
  
  // 首先计算所有通道的数据范围
  overviewData.value.forEach(channel => {
    for (let i = 0; i < channel.X_value.length; i++) {
      const x = channel.X_value[i];
      const y = channel.Y_value[i];
      
      if (x < xMin) xMin = x;
      if (x > xMax) xMax = x;
      if (y < yMin) yMin = y;
      if (y > yMax) yMax = y;
    }
  });
  
  // 添加一些边距到Y值范围
  const yRange = yMax - yMin;
  const yPadding = yRange * 0.05;
  yMin = yMin - yPadding;
  yMax = yMax + yPadding;
  
  // 保存原始数据范围
  originalDomains.value = {
    x: [xMin, xMax],
    y: { min: yMin, max: yMax }
  };
  
  // 设置初始刷选范围
  const initialBrushBegin = xMin;
  const initialBrushEnd = xMax;
  
  // 计算比例尺
  const xScale = chartWidth / (xMax - xMin);
  const yScale = chartHeight / (yMax - yMin);
  
  // 创建主绘图组
  const mainGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  mainGroup.setAttribute('transform', `translate(${margin.left}, ${margin.top})`);
  svgElement.value.appendChild(mainGroup);
  
  // 创建X轴组
  const xAxisGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
  xAxisGroup.setAttribute('transform', `translate(${margin.left}, ${margin.top + chartHeight})`);
  svgElement.value.appendChild(xAxisGroup);
  
  // 绘制X轴线
  const xAxisLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  xAxisLine.setAttribute('x1', 0);
  xAxisLine.setAttribute('y1', 0);
  xAxisLine.setAttribute('x2', chartWidth);
  xAxisLine.setAttribute('y2', 0);
  xAxisLine.setAttribute('stroke', '#999');
  xAxisLine.setAttribute('stroke-width', '1');
  xAxisGroup.appendChild(xAxisLine);
  
  // 绘制X轴刻度
  const tickCount = 5; // 刻度数量
  const tickStep = chartWidth / (tickCount - 1);
  const valueStep = (xMax - xMin) / (tickCount - 1);
  
  for (let i = 0; i < tickCount; i++) {
    const x = i * tickStep;
    const value = xMin + i * valueStep;
    
    // 绘制刻度线
    const tick = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    tick.setAttribute('x1', x);
    tick.setAttribute('y1', 0);
    tick.setAttribute('x2', x);
    tick.setAttribute('y2', 3);
    tick.setAttribute('stroke', '#999');
    tick.setAttribute('stroke-width', '1');
    xAxisGroup.appendChild(tick);
    
    // 绘制刻度值
    const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    text.setAttribute('x', x);
    text.setAttribute('y', 15);
    text.setAttribute('text-anchor', 'middle');
    text.setAttribute('font-size', '10px');
    text.setAttribute('font-weight', 'bold');
    text.textContent = value.toFixed(2);
    xAxisGroup.appendChild(text);
  }
  
  // 创建遮罩填充颜色
  const maskFill = 'rgba(64, 158, 255, 0.1)';
  
  // 创建左侧遮罩
  maskRectLeft.value = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  maskRectLeft.value.setAttribute('x', 0);
  maskRectLeft.value.setAttribute('y', 0);
  maskRectLeft.value.setAttribute('width', 0);
  maskRectLeft.value.setAttribute('height', chartHeight);
  maskRectLeft.value.setAttribute('fill', maskFill);
  mainGroup.appendChild(maskRectLeft.value);
  
  // 创建右侧遮罩
  maskRectRight.value = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  maskRectRight.value.setAttribute('x', chartWidth);
  maskRectRight.value.setAttribute('y', 0);
  maskRectRight.value.setAttribute('width', 0);
  maskRectRight.value.setAttribute('height', chartHeight);
  maskRectRight.value.setAttribute('fill', maskFill);
  mainGroup.appendChild(maskRectRight.value);
  
  // 创建选择框
  const selectionRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
  selectionRect.setAttribute('x', 0);
  selectionRect.setAttribute('y', 0);
  selectionRect.setAttribute('width', 0);
  selectionRect.setAttribute('height', chartHeight);
  selectionRect.setAttribute('fill', 'rgba(64, 158, 255, 0.25)');
  selectionRect.setAttribute('stroke', '#409EFF');
  selectionRect.setAttribute('stroke-width', '1');
  selectionRect.setAttribute('visibility', 'hidden');
  selectionRect.setAttribute('pointer-events', 'none'); // 确保选择框不会干扰鼠标事件
  mainGroup.appendChild(selectionRect);
  
  // 为每个通道绘制路径
  overviewData.value.forEach((channel, index) => {
    // 创建路径元素
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    
    // 构建路径数据
    let pathData = '';
    
    // 使用更高效的路径构建方法
    if (channel.X_value.length > 0) {
      // 开始路径
      const startX = (channel.X_value[0] - xMin) * xScale;
      const startY = chartHeight - (channel.Y_value[0] - yMin) * yScale;
      pathData = `M ${startX} ${startY}`;
      
      // 添加线段
      for (let i = 1; i < channel.X_value.length; i++) {
        const x = (channel.X_value[i] - xMin) * xScale;
        const y = chartHeight - (channel.Y_value[i] - yMin) * yScale;
        
        // 只有当点的位置变化足够大时才添加到路径中，避免过多的微小线段
        const prevX = (channel.X_value[i-1] - xMin) * xScale;
        const prevY = chartHeight - (channel.Y_value[i-1] - yMin) * yScale;
        
        // 如果点之间的距离太小，可以跳过一些点以提高性能
        if (Math.abs(x - prevX) > 0.5 || Math.abs(y - prevY) > 0.5) {
          pathData += ` L ${x} ${y}`;
        }
      }
    }
    
    // 设置路径属性
    path.setAttribute('d', pathData);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', channel.color);
    path.setAttribute('stroke-width', '1.5');
    path.setAttribute('vector-effect', 'non-scaling-stroke');
    
    // 添加到主绘图组
    mainGroup.appendChild(path);
  });
  
  // 添加鼠标事件处理
  let isDragging = false;
  let startX = 0;
  let currentMin = initialBrushBegin;
  let currentMax = initialBrushEnd;
  
  // 鼠标按下事件
  svgElement.value.addEventListener('mousedown', (e) => {
    // 计算相对于主绘图区的坐标
    const rect = svgElement.value.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - margin.left;
    
    // 确保点击在绘图区域内
    if (mouseX >= 0 && mouseX <= chartWidth) {
      isDragging = true;
      startX = mouseX;
      
      // 显示选择框
      selectionRect.setAttribute('x', startX);
      selectionRect.setAttribute('width', 0);
      selectionRect.setAttribute('visibility', 'visible');
    }
  });
  
  // 鼠标移动事件
  svgElement.value.addEventListener('mousemove', (e) => {
    if (!isDragging) return;
    
    // 计算相对于主绘图区的坐标
    const rect = svgElement.value.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - margin.left;
    
    // 限制在绘图区域内
    const currentX = Math.max(0, Math.min(mouseX, chartWidth));
    
    // 更新选择框
    if (currentX < startX) {
      selectionRect.setAttribute('x', currentX);
      selectionRect.setAttribute('width', startX - currentX);
    } else {
      selectionRect.setAttribute('x', startX);
      selectionRect.setAttribute('width', currentX - startX);
    }
  });
  
  // 鼠标释放事件
  window.addEventListener('mouseup', (e) => {
    if (!isDragging) return;
    isDragging = false;
    
    // 计算相对于主绘图区的坐标
    const rect = svgElement.value.getBoundingClientRect();
    const mouseX = e.clientX - rect.left - margin.left;
    
    // 限制在绘图区域内
    const currentX = Math.max(0, Math.min(mouseX, chartWidth));
    
    // 隐藏选择框
    selectionRect.setAttribute('visibility', 'hidden');
    
    // 如果选择范围太小，则忽略
    if (Math.abs(currentX - startX) < 5) return;
    
    // 计算当前位置对应的数据值
    const startValue = xMin + (startX / chartWidth) * (xMax - xMin);
    const currentValue = xMin + (currentX / chartWidth) * (xMax - xMin);
    
    // 更新刷选范围
    if (currentX < startX) {
      currentMin = currentValue;
      currentMax = startValue;
    } else {
      currentMin = startValue;
      currentMax = currentValue;
    }
    
    // 更新遮罩
    updateBrush(currentMin, currentMax);
  });
  
  // 更新brush值到store
  updatingBrush.value = true;
  brush_begin.value = initialBrushBegin.toFixed(4);
  brush_end.value = initialBrushEnd.toFixed(4);
  store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
  updatingBrush.value = false;
  
  // 保存初始极值
  extremes.value = { min: initialBrushBegin, max: initialBrushEnd };
  
  // 设置初始遮罩
  updateBrush(initialBrushBegin, initialBrushEnd);
  
  isLoading.value = false;
};

// 更新刷选区域
const updateBrush = (min, max) => {
  if (!svgElement.value) return;
  
  try {
    // 获取SVG尺寸
    const svgWidth = svgElement.value.clientWidth;
    const svgHeight = svgElement.value.clientHeight;
    
    // 设置图表边距
    const margin = {
      top: 5,
      right: 5,
      bottom: 20,
      left: 5
    };
    
    // 计算图表实际绘图区域
    const chartWidth = svgWidth - margin.left - margin.right;
    
    // 获取X轴范围
    const xMin = originalDomains.value.x[0];
    const xMax = originalDomains.value.x[1];
    
    // 计算像素位置
    const xScale = chartWidth / (xMax - xMin);
    const minPx = (min - xMin) * xScale;
    const maxPx = (max - xMin) * xScale;
    
    // 更新左侧遮罩
    if (maskRectLeft.value) {
      maskRectLeft.value.setAttribute('width', minPx);
    }
    
    // 更新右侧遮罩
    if (maskRectRight.value) {
      maskRectRight.value.setAttribute('x', maxPx);
      maskRectRight.value.setAttribute('width', chartWidth - maxPx);
    }
    
    // 更新brush值
    updatingBrush.value = true;
    brush_begin.value = min.toFixed(4);
    brush_end.value = max.toFixed(4);
    store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
    updatingBrush.value = false;
    
    // 更新极值
    extremes.value = { min, max };
    
    // 更新所有通道的domain
    selectedChannels.value.forEach(channel => {
      const channelName = `${channel.channel_name}_${channel.shot_number}`;
      store.dispatch('updateDomains', {
        channelName,
        xDomain: [min, max],
        yDomain: domains.value.y[channelName]
      });
    });
  } catch (error) {
    console.warn('更新遮罩区域时出错:', error);
  }
};

// 处理输入框
const handleInputBlur = (type) => {
  if (updatingBrush.value) return;

  const originalDomain = originalDomains.value.x;

  let start = parseFloat(brush_begin.value);
  let end = parseFloat(brush_end.value);

  // 验证输入值
  if (isNaN(start) || isNaN(end)) {
    ElMessage.warning('请输入有效的数字');
    if (extremes.value) {
      brush_begin.value = extremes.value.min.toFixed(4);
      brush_end.value = extremes.value.max.toFixed(4);
    } else {
      brush_begin.value = originalDomain[0].toFixed(4);
      brush_end.value = originalDomain[1].toFixed(4);
    }
    return;
  }

  // 确保起点小于终点
  if (start >= end) {
    ElMessage.warning('起点必须小于终点');
    if (extremes.value) {
      brush_begin.value = extremes.value.min.toFixed(4);
      brush_end.value = extremes.value.max.toFixed(4);
    } else {
      brush_begin.value = originalDomain[0].toFixed(4);
      brush_end.value = originalDomain[1].toFixed(4);
    }
    return;
  }

  // 确保在有效范围内
  const epsilon = 0.0001; // 添加容差值
  if (start < originalDomain[0] - epsilon) {
    start = originalDomain[0];
    brush_begin.value = start.toFixed(4);
  }
  if (end > originalDomain[1] + epsilon) {
    end = originalDomain[1];
    brush_end.value = end.toFixed(4);
  }

  // 更新 store 中的值
  store.commit("updatebrush", { begin: brush_begin.value, end: brush_end.value });

  // 更新遮罩区域
  updateBrush(start, end);
};

// 处理双击事件
const handleDblClick = () => {
  try {
    // 获取原始数据范围
    const xMin = originalDomains.value.x[0];
    const xMax = originalDomains.value.x[1];
    
    // 更新遮罩区域
    updateBrush(xMin, xMax);
  } catch (error) {
    console.warn('双击重置时出错:', error);
  }
};
</script>

<style scoped>
.overview-container {
  width: 100%;
  position: absolute;
  bottom: -18px;
  background-color: white;
  min-height: 130px;
  box-shadow: 0 -2px 6px rgba(0, 0, 0, 0.05);
}

.overview-content {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  gap: 5px;
  align-items: center;
  padding: 0 5px;
}

.overview-svg-container {
  flex: 1;
  min-width: 0;
  position: relative;
  height: 80px;
  overflow: visible;
  box-shadow: inset 0 0 3px rgba(0, 0, 0, 0.05);
  cursor: ew-resize; /* 添加指针样式提示可点击 */
}

.overview-svg-container::after {
  content: "双击重置";
  position: absolute;
  top: 2px;
  right: 5px;
  font-size: 10px;
  color: #333;
  opacity: 0.6;
  z-index: 9999;
  pointer-events: none; /* 确保文字不会干扰点击事件 */
}

.overview-chart {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.7);
  z-index: 10;
}

.loading-icon {
  font-size: 20px;
  color: #409EFF;
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.brush-controls-left,
.brush-controls-right {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
  position: relative;
  z-index: 999;
  background-color: white;
  padding: 5px 2px;
}

.el-divider--horizontal {
  margin: 0px !important;
  border-top: 3px var(--el-border-color) var(--el-border-style);
}

/* 让输入框内的文字可以选中 */
.el-input, .el-input__inner {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 为plotBands添加样式 */
:deep(.highcharts-plot-band) {
  fill-opacity: 0.1;
}

:deep(.highcharts-plot-line) {
  stroke-width: 1px;
  stroke: #606266;
}

/* 为线图添加样式 */
:deep(.highcharts-graph) {
  stroke-width: 1.5px;
}

/* 为选择区域添加样式 */
:deep(.highcharts-selection-marker) {
  fill: rgba(64, 158, 255, 0.25);
  stroke: #409EFF;
  stroke-width: 1px;
}
</style> 