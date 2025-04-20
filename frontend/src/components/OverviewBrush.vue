<template>
  <div class="overview-container">
    <el-divider />
    <div class="overview-content">
      <span class="brush-controls-left">
        <el-tag type="info">总览条起点</el-tag>
        <el-input size="small" style="width: 80px;" v-model="brush_begin" @blur="handleInputBlur('begin')" @keyup.enter="handleInputBlur('begin')"></el-input>
      </span>
      <div class="overview-svg-container" ref="chartContainer">
        <div v-if="isLoading" class="loading-overlay">
          <el-icon class="loading-icon">
            <Loading />
          </el-icon>
          <span>加载中...</span>
        </div>
        <div id="overview-chart" class="overview-chart" @dblclick="handleDblClick"></div>
      </div>
      <span class="brush-controls-right">
        <el-tag type="info">总览条终点</el-tag>
        <el-input size="small" style="width: 80px" v-model="brush_end" @blur="handleInputBlur('end')" @keyup.enter="handleInputBlur('end')"></el-input>
      </span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick, onBeforeUnmount } from 'vue';
import { useStore } from 'vuex';
import * as Highcharts from 'highcharts';
import debounce from 'lodash/debounce';
import { ElMessage } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';
import overviewWorkerManager from '@/workers/overviewWorkerManager'; // 引入专用的Worker管理器

// 设置Highcharts全局配置
Highcharts.setOptions({
  accessibility: {
    enabled: false // 禁用无障碍功能，避免相关错误
  }
});


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
const lastContainerWidth = ref(0); // 记录上次宽度

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
const handleResize = debounce(async () => {
  await nextTick();
  if (!chartContainer.value) return;
  const currentWidth = chartContainer.value.offsetWidth;
  if (currentWidth !== lastContainerWidth.value) {
    lastContainerWidth.value = currentWidth;
    // 宽度变化，销毁并重建图表
    renderChart(false);
  } else if (chartInstance.value) {
    chartInstance.value.reflow();
    // 重新设置brush遮罩
    const currentExtreme = extremes.value;
    if (currentExtreme) {
      try {
        updateBrush(currentExtreme.min, currentExtreme.max);
      } catch (error) {
        console.warn('窗口大小变化时更新遮罩区域出错:', error);
      }
    }
  }
}, 150);

// 组件挂载和卸载
onMounted(() => {
  window.addEventListener('resize', handleResize);

  // 设置Worker消息处理函数
  setupWorkerHandler();

  // 使用requestAnimationFrame延迟初始化，确保DOM完全渲染
  requestAnimationFrame(() => {
    checkDataAndRender();
  });
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
  overviewWorkerManager.onmessage = function (e) {
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
          // 使用Worker处理数据 - 降采样点数为2000，防止触发boost
          overviewWorkerManager.processData({
            channelData: {
              X_value: [...channelData.X_value],
              Y_value: [...channelData.Y_value]
            },
            channelKey,
            downsample: true, // 启用降采样以提高性能
            maxPoints: 2000 // 降采样到2000点以内，防止boost
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
        // 优化处理逻辑，减少执行时间
        if (Object.keys(processedDataCache.value).length > 0) {
          // 使用requestAnimationFrame处理视觉相关任务
          requestAnimationFrame(() => {
            prepareDataForChart();
          });
        } else {
          console.warn('数据处理超时，尝试使用可用数据渲染');
          // 没有数据时直接渲染空图表
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

  // 改为使用预计算方式，避免在requestAnimationFrame中执行重复计算
  const globalYBounds = calculateGlobalYBounds();
  
  // 将剩余处理放入requestAnimationFrame中，更适合UI相关的任务
  requestAnimationFrame(() => {
    prepareChartDataInBatches(globalYBounds.min, globalYBounds.max);
  });
};

// 预计算Y轴全局边界，与渲染分离
const calculateGlobalYBounds = () => {
  let globalYMin = Infinity;
  let globalYMax = -Infinity;

  // 优化: 使用更高效的数组方法直接获取最值
  Object.values(processedDataCache.value).forEach(data => {
    if (data && data.Y && data.Y.length > 0) {
      // 采样计算，不需要遍历所有点
      const yValues = data.Y;
      const step = Math.max(1, Math.floor(yValues.length / 50)); // 只采样约50个点
      
      for (let i = 0; i < yValues.length; i += step) {
        const y = yValues[i];
        if (y < globalYMin) globalYMin = y;
        if (y > globalYMax) globalYMax = y;
      }
    }
  });

  // 增加边距
  const globalYRange = globalYMax - globalYMin;
  const globalYPadding = globalYRange * 0.05;
  
  return {
    min: globalYMin - globalYPadding,
    max: globalYMax + globalYPadding
  };
};

// 分批处理图表数据
const prepareChartDataInBatches = (globalYMin, globalYMax) => {
  const chartData = [];
  const channels = Object.entries(processedDataCache.value);
  let currentIndex = 0;
  const BATCH_SIZE = 5; // 每帧处理5个series

  // 处理完成时的回调
  const finishProcessing = () => {
    overviewData.value = chartData;
    if (chartData.length > 0) {
      requestAnimationFrame(() => {
        renderChart(false);
      });
    } else {
      isLoading.value = false;
      console.warn('没有有效数据用于渲染');
    }
  };

  // 每帧处理BATCH_SIZE个通道
  const processNext = () => {
    let processed = 0;
    while (currentIndex < channels.length && processed < BATCH_SIZE) {
      const [channelKey, data] = channels[currentIndex];
      const channel = selectedChannels.value.find(
        ch => `${ch.channel_name}_${ch.shot_number}` === channelKey
      );
      if (channel && data && data.points) {
        chartData.push({
          channelName: channelKey,
          name: channel.channel_name,
          data: data.points,
          color: channel.color || '#7cb5ec',
          turboThreshold: 0
        });
      }
      currentIndex++;
      processed++;
    }
    if (currentIndex < channels.length) {
      requestAnimationFrame(processNext);
    } else {
      finishProcessing();
    }
  };

  // 启动处理
  processNext();
};

// 渲染图表
const renderChart = async (forceRender = false) => {
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

  // 如果已有图表实例，先销毁并等待DOM清理
  if (chartInstance.value) {
    chartInstance.value.destroy();
    chartInstance.value = null;
    await nextTick();
  }

  // 使用优化的方式计算数据范围
  const dataRanges = calculateDataRanges();
  // 保存原始数据范围
  originalDomains.value = {
    x: [dataRanges.xMin, dataRanges.xMax],
    y: { min: dataRanges.yMin, max: dataRanges.yMax }
  };
  // 设置初始刷选范围
  const initialBrushBegin = dataRanges.xMin;
  const initialBrushEnd = dataRanges.xMax;

  // 创建Highcharts配置（不带series）
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
        selection: function (event) {
          if (event.xAxis) {
            const min = event.xAxis[0].min;
            const max = event.xAxis[0].max;
            updateBrush(min, max);
          }
          return false; // 阻止默认缩放行为
        }
      }
    },
    title: { text: null },
    credits: { enabled: false },
    exporting: { enabled: false },
    xAxis: {
      min: dataRanges.xMin,
      max: dataRanges.xMax,
      lineWidth: 1,
      tickLength: 3,
      labels: { style: { fontSize: '10px', fontWeight: 'bold' } },
      plotBands: [{
        from: initialBrushBegin,
        to: initialBrushEnd,
        color: 'rgba(64, 158, 255, 0.1)',
        id: 'plot-band-selection'
      }]
    },
    yAxis: {
      min: dataRanges.yMin,
      max: dataRanges.yMax,
      visible: false
    },
    legend: { enabled: false },
    tooltip: { enabled: false },
    plotOptions: {
      series: {
        animation: false,
        lineWidth: 1,
        states: { hover: { enabled: false } },
        marker: { enabled: false },
        enableMouseTracking: false,
        stickyTracking: false,
        turboThreshold: 0
      }
    },
    boost: { enabled: false }, // 禁用boost模块，防止报错
    series: [] // 先不传数据
  };

  chartInstance.value = Highcharts.chart(options);

  // 分批addSeries
  let idx = 0;
  const BATCH_SIZE = 1;
  function addSeriesBatch() {
    if (!chartInstance.value) return; // 防止已销毁还操作
    let count = 0;
    while (idx < overviewData.value.length && count < BATCH_SIZE) {
      try {
        chartInstance.value.addSeries(overviewData.value[idx], false);
      } catch (e) {
        console.warn('addSeries error:', e);
      }
      idx++;
      count++;
    }
    if (idx < overviewData.value.length) {
      requestAnimationFrame(addSeriesBatch);
    } else if (chartInstance.value) {
      chartInstance.value.redraw(); // 最后一次性重绘
      // 更新brush值到store
      updatingBrush.value = true;
      brush_begin.value = initialBrushBegin.toFixed(4);
      brush_end.value = initialBrushEnd.toFixed(4);
      store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
      updatingBrush.value = false;
      // 保存初始极值
      extremes.value = { min: initialBrushBegin, max: initialBrushEnd };
      isLoading.value = false;
    }
  }
  addSeriesBatch();

  // 记录最新宽度
  lastContainerWidth.value = chartContainer.value ? chartContainer.value.offsetWidth : 0;
};

// 优化计算数据范围的函数
const calculateDataRanges = () => {
  let xMin = Infinity;
  let xMax = -Infinity;
  let yMin = Infinity;
  let yMax = -Infinity;
  
  // 优化遍历，避免嵌套循环
  for (const channel of overviewData.value) {
    // 每个通道只检查部分点，提高性能
    const data = channel.data;
    const dataLength = data.length;
    
    // 抽样检查点数，最多检查100个点
    const sampleStep = Math.max(1, Math.floor(dataLength / 100));
    
    // 先检查首尾点
    if (dataLength > 0) {
      // 检查第一个点
      const firstPoint = data[0];
      if (firstPoint[0] < xMin) xMin = firstPoint[0];
      if (firstPoint[0] > xMax) xMax = firstPoint[0];
      if (firstPoint[1] < yMin) yMin = firstPoint[1];
      if (firstPoint[1] > yMax) yMax = firstPoint[1];
      
      // 检查最后一个点
      const lastPoint = data[dataLength - 1];
      if (lastPoint[0] < xMin) xMin = lastPoint[0];
      if (lastPoint[0] > xMax) xMax = lastPoint[0];
      if (lastPoint[1] < yMin) yMin = lastPoint[1];
      if (lastPoint[1] > yMax) yMax = lastPoint[1];
    }
    
    // 抽样检查中间点
    for (let i = sampleStep; i < dataLength - 1; i += sampleStep) {
      const point = data[i];
      if (point[0] < xMin) xMin = point[0];
      if (point[0] > xMax) xMax = point[0];
      if (point[1] < yMin) yMin = point[1];
      if (point[1] > yMax) yMax = point[1];
    }
  }
  
  // 添加边距到Y值范围
  const yRange = yMax - yMin;
  const yPadding = yRange * 0.05;
  
  return {
    xMin,
    xMax,
    yMin: yMin - yPadding,
    yMax: yMax + yPadding
  };
};

// 清空图表
const clearChart = () => {
  if (chartInstance.value) {
    chartInstance.value.destroy();
    chartInstance.value = null;
  }
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
  cursor: ew-resize;
  width: 100%; /* 保证宽度自适应 */
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
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
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
.el-input,
.el-input__inner {
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