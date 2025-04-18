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
        <div id="overview-chart" class="overview-chart" @dblclick="handleDblClick"></div>
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
import { ref, computed, watch, onMounted, onUnmounted, nextTick, onBeforeUnmount } from 'vue';
import { useStore } from 'vuex';
import * as Highcharts from 'highcharts';
import 'highcharts/modules/boost';  // 使用官方的boost模块
import 'highcharts/modules/accessibility';  // 添加无障碍模块
import debounce from 'lodash/debounce';
import { ElMessage } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';
import overviewWorkerManager from '@/workers/overviewWorkerManager'; // 引入专用的Worker管理器

const store = useStore();
const chartContainer = ref(null);

// 响应式引用
const overviewData = ref([]);
const chartInstance = ref(null);
const updatingBrush = ref(false);
const originalDomains = ref({});
const isLoading = ref(false);
const extremes = ref(null);
const processedDataCache = ref({}); // 缓存处理后的数据

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
  if (overviewData.value && overviewData.value.length > 0 && chartInstance.value) {
    // 记住当前的刷选状态
    const currentExtreme = extremes.value;
    
    // 重新渲染图表
    chartInstance.value.reflow();
    
    // 如果原来有滑动块选择，重新设置
    if (currentExtreme) {
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
    checkDataAndRender();
  }, 500);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  
  // 销毁Highcharts实例
  if (chartInstance.value) {
    chartInstance.value.destroy();
    chartInstance.value = null;
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
      // 为Highcharts准备数据
      const seriesData = [];
      
      // 将X和Y值组合成Highcharts需要的格式
      for (let i = 0; i < data.X.length; i++) {
        seriesData.push([data.X[i], data.Y[i]]);
      }
      
      chartData.push({
        channelName: channelKey,
        name: channel.channel_name,
        data: seriesData,
        color: channel.color || '#7cb5ec',
        boostThreshold: 1000, // 启用boost的阈值
        turboThreshold: 0 // 禁用turboThreshold限制
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
  if (chartInstance.value) {
    chartInstance.value.destroy();
    chartInstance.value = null;
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
  
  // 如果已有图表实例，先销毁
  if (chartInstance.value) {
    chartInstance.value.destroy();
  }
  
  // 计算全局数据范围
  let xMin = Infinity;
  let xMax = -Infinity;
  let yMin = Infinity;
  let yMax = -Infinity;
  
  // 首先计算所有通道的数据范围
  overviewData.value.forEach(channel => {
    channel.data.forEach(point => {
      const x = point[0];
      const y = point[1];
      
      if (x < xMin) xMin = x;
      if (x > xMax) xMax = x;
      if (y < yMin) yMin = y;
      if (y > yMax) yMax = y;
    });
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
  
  // 创建Highcharts配置
  const options = {
    chart: {
      renderTo: 'overview-chart',
      height: 80,
      marginLeft: 15,
      marginRight: 15,
      marginTop: 5,
      marginBottom: 30,
      animation: false,
      zoomType: 'x',
      events: {
        selection: function(event) {
          if (event.xAxis) {
            const min = event.xAxis[0].min;
            const max = event.xAxis[0].max;
            updateBrush(min, max);
          }
          return false; // 阻止默认缩放行为
        }
      }
    },
    title: {
      text: null
    },
    credits: {
      enabled: false
    },
    xAxis: {
      min: xMin,
      max: xMax,
      lineWidth: 1,
      tickLength: 3,
      labels: {
        style: {
          fontSize: '10px',
          fontWeight: 'bold'
        }
      },
      plotBands: [{
        from: initialBrushBegin,
        to: initialBrushEnd,
        color: 'rgba(64, 158, 255, 0.1)',
        id: 'plot-band-selection'
      }]
    },
    yAxis: {
      min: yMin,
      max: yMax,
      visible: false
    },
    legend: {
      enabled: false
    },
    tooltip: {
      enabled: false
    },
    plotOptions: {
      series: {
        animation: false,
        lineWidth: 1.5,
        states: {
          hover: {
            enabled: false
          }
        },
        marker: {
          enabled: false
        },
        enableMouseTracking: false,
        stickyTracking: false,
        turboThreshold: 0, // 禁用turboThreshold限制
        boostThreshold: 1000 // 启用boost的阈值
      }
    },
    boost: {
      useGPUTranslations: true,
      usePreAllocated: true,
      seriesThreshold: 1 // 只要有一个系列就启用boost
    },
    accessibility: {
      enabled: false // 禁用无障碍功能，避免相关错误
    },
    series: overviewData.value
  };
  
  // 创建图表
  chartInstance.value = Highcharts.chart(options);
  
  // 更新brush值到store
  updatingBrush.value = true;
  brush_begin.value = initialBrushBegin.toFixed(4);
  brush_end.value = initialBrushEnd.toFixed(4);
  store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
  updatingBrush.value = false;
  
  // 保存初始极值
  extremes.value = { min: initialBrushBegin, max: initialBrushEnd };
  
  isLoading.value = false;
};

// 更新刷选区域
const updateBrush = (min, max) => {
  if (!chartInstance.value) return;
  
  try {
    // 更新plotBand
    chartInstance.value.xAxis[0].removePlotBand('plot-band-selection');
    chartInstance.value.xAxis[0].addPlotBand({
      from: min,
      to: max,
      color: 'rgba(64, 158, 255, 0.1)',
      id: 'plot-band-selection'
    });
    
    // 更新brush值
    updatingBrush.value = true;
    brush_begin.value = min.toFixed(4);
    brush_end.value = max.toFixed(4);
    store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
    updatingBrush.value = false;
    
    // 更新极值
    extremes.value = { min, max };
    
    // 不再自动更新所有通道的domain，而是让用户手动选择要同步的通道
    // 如果需要同步某个通道，用户可以通过双击该通道的图表来重置到总览范围
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

// 在组件销毁时确保清理图表实例
onBeforeUnmount(() => {
  if (chartInstance.value) {
    chartInstance.value.destroy();
    chartInstance.value = null;
  }
});
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