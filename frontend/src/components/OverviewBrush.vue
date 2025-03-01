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
        <svg id="overview-chart" class="overview-svg"></svg>
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
import * as d3 from 'd3';
import debounce from 'lodash/debounce';
import { ElMessage } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';

const store = useStore();
const chartContainer = ref(null);

// 响应式引用
const overviewData = ref([]);
const overviewBrushInstance = ref(null);
const overviewXScale = ref(null);
const updatingBrush = ref(false);
const brushSelections = ref({ overview: null });
const originalDomains = ref({});
const renderCount = ref(0);
const initialDataLoaded = ref(false);
const isLoading = ref(false);
const retryCount = ref(0);


// 追加一个强制渲染标志，用于确保至少绘制一次
const forceRender = ref(false);

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
    const currentBrushExtent = brushSelections.value.overview;
    const preserveCurrentSelection = currentBrushExtent && overviewXScale.value;
    
    // 重新渲染图表
    renderChart();
    
    // 如果原来有滑动块选择但没有应用，重新设置
    if (preserveCurrentSelection) {
      nextTick(() => {
        const brush = overviewBrushInstance.value;
        const x = overviewXScale.value;
        if (brush && x) {
          // 恢复刷选区域
          d3.select('#overview-chart').select('.brush').call(brush.move, currentBrushExtent);
        }
      });
    }
  }
}, 200);

// 组件挂载和卸载
onMounted(() => {
  window.addEventListener('resize', handleResize);
  
  // 延迟初始化以确保DOM渲染完成
  setTimeout(() => {
    checkDataAndRender();
  }, 500);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});

// 监听选中通道的变化
watch(selectedChannels, () => {
  forceRender.value = false; // 重置强制渲染标记
  checkDataAndRender();
}, { deep: true });

// 监听通道数据缓存的变化
watch(channelDataCache, () => {
  // 仅在有选中通道且当前无数据时才尝试重新获取
  if (selectedChannels.value.length > 0 && overviewData.value.length === 0) {
    collectData();
  }
}, { deep: true });

// 检查数据是否准备好并渲染
const checkDataAndRender = () => {
  retryCount.value = 0;
  // 直接获取数据，不需要先做检查
  collectData();
};

// 采集数据
const collectData = async (forcedRender = false) => {
  // 检查是否有选中的通道
  if (!selectedChannels.value || selectedChannels.value.length === 0) {
    overviewData.value = [];
    return;
  }
  
  // 保存现有数据
  const existingData = [...overviewData.value];
  
  // 使用直接获取数据的方式，而不是依赖channelDataCache
  isLoading.value = true;
  
  try {
    const dataPromises = selectedChannels.value.map(async (channel) => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      
      // 避免重复处理已经有数据的通道
      if (existingData.some(d => d.channelName === channelKey) && !forcedRender) {
        return null;
      }
      
      try {
        // 直接使用store action获取数据，不依赖channelDataCache
        const channelData = await store.dispatch('fetchChannelData', { channel });
        
        if (channelData && channelData.X_value && channelData.Y_value &&
            Array.isArray(channelData.X_value) && Array.isArray(channelData.Y_value) &&
            channelData.X_value.length > 0 && channelData.Y_value.length > 0) {
        
          
          // 返回处理后的数据对象
          return {
            channelName: channelKey,
            X_value: [...channelData.X_value],
            Y_value: [...channelData.Y_value],
            color: channel.color || '#7cb5ec'
          };
        } else {
          console.warn(`通道 ${channelKey} 返回的数据无效`);
          return null;
        }
      } catch (error) {
        console.error(`获取通道 ${channelKey} 数据失败:`, error);
        return null;
      }
    });
    
    // 等待所有数据请求完成
    const results = await Promise.all(dataPromises);
    
    // 过滤掉null和undefined结果
    const newChannelsData = results.filter(Boolean);
    
    // 合并现有数据和新数据，避免重复
    if (newChannelsData.length > 0) {
      const merged = [...existingData];
      
      newChannelsData.forEach(newData => {
        // 检查是否已存在
        const existingIndex = merged.findIndex(item => item.channelName === newData.channelName);
        if (existingIndex >= 0) {
          // 更新现有数据
          merged[existingIndex] = newData;
        } else {
          // 添加新数据
          merged.push(newData);
        }
      });
      
      overviewData.value = merged;
    } else if (existingData.length === 0) {
      overviewData.value = [];
    }
    
    // 绘制图表
    if (overviewData.value.length > 0) {
      initialDataLoaded.value = true;
      renderChart();
    } else {
      console.warn('没有收集到任何有效数据');
      clearChart();
      
      // 添加一个简单的提示到图表
      const svg = d3.select('#overview-chart')
        .attr('width', '100%')
        .attr('height', '100%');
        
      svg.append('text')
        .attr('x', '50%')
        .attr('y', '50%')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .attr('fill', '#999999')
        .text('等待数据加载中...');
    }
  } catch (error) {
    console.error('获取数据过程中发生错误:', error);
  } finally {
    isLoading.value = false;
  }
};

// 清空图表
const clearChart = () => {
  const svg = d3.select('#overview-chart');
  svg.selectAll('*').remove();
};

// 渲染图表
const renderChart = () => {
  renderCount.value++;
  
  if (overviewData.value.length === 0) {
    console.warn('无数据可渲染');
    clearChart();
    return;
  }
  
  // 确保容器存在
  if (!chartContainer.value) {
    console.error('图表容器不存在');
    return;
  }
  
  // 清空现有图表
  clearChart();
  
  // 获取容器尺寸
  const containerRect = chartContainer.value.getBoundingClientRect();
  const width = containerRect.width;
  const height = containerRect.height;
    
  if (width <= 0 || height <= 0) {
    console.error('容器尺寸无效');
    return;
  }
  
  // 设置边距
  const margin = { top: 10, right: 20, bottom: 30, left: 20 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = height - margin.top - margin.bottom;
  
  // 获取SVG元素
  const svg = d3.select('#overview-chart')
    .attr('width', width)
    .attr('height', height);
  
  // 创建主图层
  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);
  
  // 计算X和Y值的范围
  let allX = [];
  let allY = [];
  
  overviewData.value.forEach(channel => {
    allX = allX.concat(channel.X_value);
    allY = allY.concat(channel.Y_value);
  });
  
  const xExtent = d3.extent(allX);
  const yExtent = d3.extent(allY);
  
  // 添加一些边距到Y值范围
  const yRange = yExtent[1] - yExtent[0];
  const yPadding = yRange * 0.05;
  const yMin = yExtent[0] - yPadding;
  const yMax = yExtent[1] + yPadding;
    
  // 创建比例尺
  const x = d3.scaleLinear()
    .domain(xExtent)
    .range([0, innerWidth]);
  
  const y = d3.scaleLinear()
    .domain([yMin, yMax])
    .range([innerHeight, 0]);
  
  // 保存X比例尺供其他函数使用
  overviewXScale.value = x;
  
  // 保存原始数据范围
  originalDomains.value = {
    x: [...xExtent],
    y: { min: yMin, max: yMax }
  };
  
  // 添加坐标轴
  g.append('g')
    .attr('class', 'x-axis')
    .attr('transform', `translate(0,${innerHeight})`)
    .call(d3.axisBottom(x).ticks(5));
  
  // 绘制网格线
  g.append('g')
    .attr('class', 'grid x-grid')
    .attr('transform', `translate(0,${innerHeight})`)
    .style('stroke', '#e0e0e0')
    .style('stroke-opacity', 0.7)
    .call(
      d3.axisBottom(x)
        .tickSize(-innerHeight)
        .tickFormat('')
    );
  
  // 绘制每个通道的数据线
  overviewData.value.forEach((channel, i) => {
    try {
      // 创建线条生成器
      const line = d3.line()
        .x((_, i) => x(channel.X_value[i]))
        .y(d => y(d))
        .curve(d3.curveMonotoneX);
      
      // 绘制线条
      g.append('path')
        .datum(channel.Y_value)
        .attr('class', `line-${i}`)
        .attr('fill', 'none')
        .attr('stroke', channel.color)
        .attr('stroke-width', 1.5)
        .attr('d', line);
    } catch (error) {
      console.error(`绘制通道 ${channel.channelName} 出错:`, error);
    }
  });
  
  // 创建刷选功能
  const brush = d3.brushX()
    .extent([[0, 0], [innerWidth, innerHeight]])
    .on('start', () => { updatingBrush.value = true; })
    .on('brush', brushed)
    .on('end', brushEnded);
  
  // 保存刷选实例
  overviewBrushInstance.value = brush;
  
  // 添加刷选层
  const brushG = g.append('g')
    .attr('class', 'brush')
    .call(brush);
  
  // 设置初始刷选范围为整个数据范围（最左侧到最右侧）
  const initialBrushBegin = xExtent[0];
  const initialBrushEnd = xExtent[1];
  
  // 更新brush值到store
  updatingBrush.value = true;
  brush_begin.value = initialBrushBegin.toFixed(4);
  brush_end.value = initialBrushEnd.toFixed(4);
  store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
  updatingBrush.value = false;
  
  // 设置刷选范围
  const initialSelection = [x(initialBrushBegin), x(initialBrushEnd)];
  brushG.call(brush.move, initialSelection);
  brushSelections.value.overview = initialSelection;
    
  // 刷选事件处理函数
  function brushed(event) {
    if (!event.selection) return;
    
    brushSelections.value.overview = event.selection;
    const [x0, x1] = event.selection.map(x.invert);
    
    updatingBrush.value = true;
    brush_begin.value = x0.toFixed(4);
    brush_end.value = x1.toFixed(4);
    // 在刷选过程中不立即更新store，提高性能
  }
  
  function brushEnded(event) {
    if (!event.selection) {
      // 用户点击空白处，恢复上一次选择
      if (brushSelections.value.overview) {
        brushG.call(brush.move, brushSelections.value.overview);
      }
      return;
    }
    
    const [x0, x1] = event.selection.map(x.invert);
    
    // 更新store
    store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
    
    // 更新所有通道的domain
    selectedChannels.value.forEach(channel => {
      const channelName = `${channel.channel_name}_${channel.shot_number}`;
      store.dispatch('updateDomains', {
        channelName,
        xDomain: [x0, x1],
        yDomain: domains.value.y[channelName]
      });
    });
    
    updatingBrush.value = false;
  }
};

// 处理输入框
const handleInputBlur = (type) => {
  if (updatingBrush.value) return;
  if (!overviewXScale.value || !overviewBrushInstance.value) return;

  const x = overviewXScale.value;
  const brush = overviewBrushInstance.value;
  const originalDomain = originalDomains.value.x;

  let start = parseFloat(brush_begin.value);
  let end = parseFloat(brush_end.value);

  // 验证输入值
  if (isNaN(start) || isNaN(end)) {
    ElMessage.warning('请输入有效的数字');
    if (brushSelections.value.overview) {
      const [x0, x1] = brushSelections.value.overview.map(x.invert);
      brush_begin.value = x0.toFixed(4);
      brush_end.value = x1.toFixed(4);
    } else {
      brush_begin.value = originalDomain[0].toFixed(4);
      brush_end.value = originalDomain[1].toFixed(4);
    }
    return;
  }

  // 确保起点小于终点
  if (start >= end) {
    ElMessage.warning('起点必须小于终点');
    if (brushSelections.value.overview) {
      const [x0, x1] = brushSelections.value.overview.map(x.invert);
      brush_begin.value = x0.toFixed(4);
      brush_end.value = x1.toFixed(4);
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

  // 更新刷选区域
  const selection = [x(start), x(end)];
  updatingBrush.value = true;
  d3.select('#overview-chart').select('.brush').call(brush.move, selection);
  brushSelections.value.overview = selection;
  updatingBrush.value = false;

  // 更新所有通道的 domain
  selectedChannels.value.forEach((channel) => {
    const channelName = `${channel.channel_name}_${channel.shot_number}`;
    store.dispatch('updateDomains', {
      channelName,
      xDomain: [start, end],
      yDomain: domains.value.y[channelName]
    });
  });
};
</script>

<style scoped>
.overview-container {
  width: 100%;
  position: absolute;
  bottom: -18px;
  background-color: white;
  min-height: 110px;
}

.overview-content {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  gap: 5px;
  align-items: center;
}

.overview-svg-container {
  flex: 1;
  min-width: 0;
  position: relative;
  height: 60px;
  border: 1px solid #e0e0e0;
  background-color: #ffffff;
  overflow: visible;
}

.overview-svg {
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

/* 添加刷选区域样式 */
:deep(.brush .selection) {
  fill: rgba(100, 150, 250, 0.25);
  stroke: #3a8ee6;
  stroke-width: 1px;
}

/* 添加刷选手柄样式 */
:deep(.brush .handle) {
  fill: #3a8ee6;
  stroke: #3a8ee6;
  stroke-width: 1px;
}

/* 样式化坐标轴 */
:deep(.x-axis) path,
:deep(.x-axis) line {
  stroke: #999;
  stroke-width: 1px;
}

:deep(.x-axis) text {
  font-size: 10px;
  font-weight: bold;
}

:deep(.grid) line {
  stroke: #e0e0e0;
  stroke-width: 0.5px;
}

:deep(.grid) path {
  stroke-width: 0;
}
</style> 