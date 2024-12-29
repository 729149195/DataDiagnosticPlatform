<template>
  <div class="chart-container">
    <div class="legend-container">
      <LegendComponent :channelsData="channelsData" @update-color="updateChannelColor" />
    </div>
    <div v-if="selectedChannels.length === 0">
      <el-empty description="请选择通道" style="margin-top: 15vh;" />
    </div>
    <div v-else>
      <div v-if="!renderingStates.completed" class="progress-wrapper">
        <div class="progress-title">
          <span>{{ !loadingStates.dataLoaded ? '数据加载中' : '图表渲染中' }}</span>
          <span class="progress-percentage">{{ getProgressPercentage }}%</span>
        </div>
        <el-progress :percentage="getProgressPercentage" :stroke-width="10"
          :status="!loadingStates.dataLoaded ? 'warning' : ''" :color="loadingStates.dataLoaded ? '#409EFF' : ''" />
      </div>
      <div class="chart-wrapper">
        <svg id="combined-chart" ref="channelsSvgRef" :style="{
          opacity: renderingStates.completed ? 1 : 0,
          transition: 'opacity 0.3s ease-in-out'
        }"></svg>
      </div>
      <div class="overview-container">
        <el-divider />
        <div class="overview-content">
          <span class="brush-controls-left">
            <el-tag type="info">总览条起点</el-tag>
            <el-input size="small" style="width: 80px;" v-model="brush_begin" @blur="handleInputBlur('begin')"
              @keyup.enter="handleInputBlur('begin')"></el-input>
          </span>
          <div class="overview-svg-container">
            <svg id="overview-chart" class="overview-svg"></svg>
          </div>
          <span class="brush-controls-right">
            <el-tag type="info">总览条终点</el-tag>
            <el-input size="small" style="width: 80px" v-model="brush_end" @blur="handleInputBlur('end')"
              @keyup.enter="handleInputBlur('end')"></el-input>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import * as d3 from 'd3';
import debounce from 'lodash/debounce';
import { ref, watch, computed, onMounted, nextTick, reactive, onUnmounted } from 'vue';
import { ElInput, ElMessage, ElEmpty, ElDivider, ElTag, ElProgress } from 'element-plus';
import { useStore } from 'vuex';
import axios from 'axios';
import LegendComponent from '@/components/LegendComponent.vue';
import {
  sampleData,
  sampleErrorSegment,
  findStartIndex,
  findEndIndex
} from '@/utils/dataProcessing';
import pLimit from 'p-limit';

// 归一化函数
const normalize = (yValues) => {
  const yAbsMax = d3.max(yValues, d => Math.abs(d));
  if (yAbsMax === 0) return yValues.map(() => 0);
  return yValues.map(y => y / yAbsMax);
};

// Reactive references
const overviewData = ref([]);
const xDomains = ref({ global: null });
const brush_begin = ref(0);
const brush_end = ref(0);
const brushSelections = ref({ overview: null });
const channelsData = ref([]);
const exposeData = ref([])
const dataCache = computed(() => store.state.dataCache); // 数据缓存
const channelsSvgRef = ref(null);
const resetProgress = () => {
  loadingStates.channels.clear();
  loadingStates.dataLoaded = false;
  renderingStates.channels.clear();
  renderingStates.completed = false;
  loadingStates.renderStarted = false;
};
defineExpose({
  channelsSvgRef: channelsSvgRef,
  channelsData: exposeData,
  resetProgress
})

const predefineColors = ref([
  '#000000', // Black
  '#4169E1', // Royal Blue
  '#DC143C', // Crimson
  '#228B22', // Forest Green
  '#FF8C00', // Dark Orange
  '#800080', // Purple
  '#FF1493', // Deep Pink
  '#40E0D0', // Turquoise
  '#FFD700', // Gold
  '#8B4513', // Saddle Brown
  '#2F4F4F', // Dark Slate Gray
  '#1E90FF', // Dodger Blue
  '#32CD32', // Lime Green
  '#FF6347', // Tomato
  '#DA70D6', // Orchid
  '#191970', // Midnight Blue
  '#FA8072', // Salmon
  '#6B8E23', // Olive Drab
  '#6A5ACD', // Slate Blue
  '#FF7F50', // Coral
  '#4682B4'  // Steel Blue
]);

const mainChartDimensions = ref({
  margin: { top: 110, right: 20, bottom: 150, left: 80 },
  width: 0,
  height: 550 - 80 - 50, // main chart height
});

const overviewChartDimensions = ref({
  margin: { top: 10, right: 45, bottom: 35, left: 45 },
  width: 0,
  height: 80 - 10 - 35, // overview chart height
});

// Vuex store
const store = useStore();
const selectedChannels = computed(() => store.state.selectedChannels);

const sampling = computed(() => store.state.sampling);
const smoothnessValue = computed(() => store.state.smoothness);
const sampleRate = ref(store.state.sampling);
const matchedResults = computed(() => store.getters.getMatchedResults);

const overviewBrushInstance = ref(null);
const overviewXScale = ref(null);
const updatingBrush = ref(false);

const updateChannelColor = ({ channelKey, color }) => {
  // 更新 selectedChannels 中的颜色
  const channel = selectedChannels.value.find(
    (ch) => `${ch.channel_name}_${ch.shot_number}` === channelKey
  );
  if (channel) {
    channel.color = color;
    // 更新 Vuex 存储，如果需要
    store.commit('updateChannelColor', { channel_key: channelKey, color });
    // 重新制图表
    renderCharts();
  }
};

// 监听匹配结果并高亮
watch(matchedResults, (newResults) => {
  if (newResults.length > 0) {
    const resultsByChannel = newResults.reduce((acc, result) => {
      const { channel_name } = result;
      if (!acc[channel_name]) acc[channel_name] = [];
      acc[channel_name].push(result);
      return acc;
    }, {});

    Object.keys(resultsByChannel).forEach(channel_name => {
      drawHighlightRects(channel_name, resultsByChannel[channel_name]);
    });
  }
});

const drawHighlightRects = (channel_name, results) => {
  const svg = d3.select(`#combined-chart`);
  if (!svg.node()) return;

  const { margin, width, height } = mainChartDimensions.value;

  // 确保 xDomains.value.global 已经设置
  if (!xDomains.value.global) {
    console.warn(`xDomains.global 未设置，无法绘制高亮矩形。`);
    return;
  }

  const x = d3.scaleLinear()
    .domain(xDomains.value.global)
    .range([0, width]);

  // 移除之前的亮组
  svg.select(`.highlight-group-${channel_name}`).remove();

  const highlightGroup = svg.select('g')
    .append('g')
    .attr('class', `highlight-group-${channel_name}`);

  results.forEach(({ start_X, end_X }) => {
    // 检查 start_X 和 end_X 否为有效数字
    if (isNaN(start_X) || isNaN(end_X)) {
      console.warn(`Invalid start_X or end_X for channel ${channel_name}:`, start_X, end_X);
      return;
    }

    // 确保 start_X 和 end_X 在 xDomains.global 范围内
    const [xMin, xMax] = xDomains.value.global;
    const validStart_X = Math.max(start_X, xMin);
    const validEnd_X = Math.min(end_X, xMax);

    if (validStart_X >= validEnd_X) {
      console.warn(`start_X >= end_X after clamping for channel ${channel_name}:`, validStart_X, validEnd_X);
      return;
    }

    highlightGroup.append('rect')
      .attr('x', x(validStart_X))
      .attr('y', margin.top)
      .attr('width', x(validEnd_X) - x(validStart_X))
      .attr('height', height)
      .attr('fill', 'gray')
      .attr('opacity', 0.3)
      .datum({ start_X: validStart_X, end_X: validEnd_X });
  });
};


// 渲染图表，防抖以避免频繁调用
const renderCharts = debounce(async () => {
  overviewData.value = [];
  channelsData.value = [];
  exposeData.value = []
  await Promise.all(selectedChannels.value.map(channel => fetchDataAndStore(channel)));

  if (!xDomains.value.global) {
    const allX = channelsData.value.flatMap(d => d.X_value);
    xDomains.value.global = d3.extent(allX);
  }

  await nextTick(); // 等待数据更新到 DOM
  drawCombinedChart();
  drawOverviewChart();
}, 300);


// onMounted 生命周期钩子
onMounted(async () => {
  const container = document.querySelector('.chart-container');
  const containerWidth = container.offsetWidth;

  mainChartDimensions.value.width = containerWidth - mainChartDimensions.value.margin.left - mainChartDimensions.value.margin.right;
  overviewChartDimensions.value.width = containerWidth - overviewChartDimensions.value.margin.left - overviewChartDimensions.value.margin.right;

  if (selectedChannels.value.length > 0) {
    await renderCharts();
  }

  window.addEventListener('resize', handleResize);
});

// 在组件卸载时移除监听器
onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});

// 监听选中通道的变化
watch(selectedChannels, async (newChannels, oldChannels) => {
  if (JSON.stringify(newChannels) !== JSON.stringify(oldChannels)) {
    overviewData.value = [];
    channelsData.value = [];
    exposeData.value = []
    await nextTick();
    renderCharts();
    drawOverviewChart();
  }
}, { deep: true });

watch(sampling, () => {
  sampleRate.value = sampling.value;
  renderCharts();
});

watch(smoothnessValue, () => {
  renderCharts();
});

watch(
  () => selectedChannels.value.map(channel => channel.errors.map(error => error.color)),
  (newErrorColors, oldErrorColors) => {
    if (JSON.stringify(newErrorColors) !== JSON.stringify(oldErrorColors)) {
      renderCharts();
    }
  },
  { deep: true }
);


// 修改进度状态管理的部分
const loadingStates = reactive({
  channels: new Map(), // 存储每个通道的加载进度
  dataLoaded: false,
  renderStarted: false
});

const renderingStates = reactive({
  channels: new Map(), // 存储每个通道的渲染进度
  completed: false
});

// 修改计算属性来处理总体进度百分比
const getProgressPercentage = computed(() => {
  if (selectedChannels.value.length === 0) return 0;

  let totalProgress = 0;
  const channelCount = selectedChannels.value.length;

  if (!loadingStates.dataLoaded) {
    // 数据加载阶段 (0-50%)
    selectedChannels.value.forEach(channel => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const progress = loadingStates.channels.get(channelKey) || 0;
      totalProgress += progress;
    });
    return Math.floor((totalProgress / channelCount) / 2);
  } else if (!renderingStates.completed) {
    // 渲染阶段 (50-100%)
    selectedChannels.value.forEach(channel => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const progress = renderingStates.channels.get(channelKey) || 0;
      totalProgress += progress;
    });
    return Math.floor(50 + (totalProgress / channelCount) / 2);
  }
  return 100;
});

// 创建并发限制器
const limit = pLimit(3); // 限制最大并发请求数为3

// 添加重试函数
const retryRequest = async (fn, retries = 3, delay = 1000) => {
  try {
    return await fn();
  } catch (err) {
    if (retries <= 0) throw err;
    await new Promise(resolve => setTimeout(resolve, delay));
    return retryRequest(fn, retries - 1, delay * 2);
  }
};

// 获取数据并存储到 channelsData，同时使用缓存避免重复请求
const fetchDataAndStore = async (channel) => {
  try {
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;

    // 初始化该通道的进度
    loadingStates.channels.set(channelKey, 0);
    renderingStates.channels.set(channelKey, 0);

    const cacheKey = `${channelKey}-sampling-${sampleRate.value}`;

    let data;
    if (dataCache.value.has(cacheKey)) {
      // 从缓存加载时快速更新进度
      const loadingInterval = setInterval(() => {
        const currentProgress = loadingStates.channels.get(channelKey) || 0;
        if (currentProgress < 100) {
          loadingStates.channels.set(channelKey, Math.min(currentProgress + 20, 100));
        }
      }, 50);

      const cached = dataCache.value.get(cacheKey);
      data = cached;

      clearInterval(loadingInterval);
      loadingStates.channels.set(channelKey, 100);
    } else {
      // 模拟进度更新
      const progressInterval = setInterval(() => {
        const currentProgress = loadingStates.channels.get(channelKey) || 0;
        if (currentProgress < 90) {
          loadingStates.channels.set(channelKey, Math.min(currentProgress + 10, 90));
        }
      }, 100);

      // 获取数据...
      const response = await limit(() => retryRequest(async () => {
        return await axios.get(`http://localhost:5000/api/channel-data/`, {
          params: {
            channel_key: channelKey,
            channel_type: channel.channel_type
          }
        });
      }));

      data = response.data;
      dataCache.value.set(cacheKey, data);

      clearInterval(progressInterval);
      loadingStates.channels.set(channelKey, 100);
    }

    // 检查是否所有通道都加载完成
    const allChannelsLoaded = Array.from(loadingStates.channels.values())
      .every(progress => progress === 100);

    if (allChannelsLoaded) {
      loadingStates.dataLoaded = true;
      loadingStates.renderStarted = true;
    }

    // 开始渲染进度
    const updateRenderProgress = () => {
      const currentProgress = renderingStates.channels.get(channelKey) || 0;
      if (currentProgress < 90 && !renderingStates.completed) {
        renderingStates.channels.set(channelKey, Math.min(currentProgress + 2, 90));
        requestAnimationFrame(updateRenderProgress);
      }
    };
    requestAnimationFrame(updateRenderProgress);

    // 处理数据并绘制图表
    await processChannelData(data, channel);

    // 更新渲染完成状态
    renderingStates.channels.set(channelKey, 100);

    // 检查是否所有通道都渲染完成
    const allChannelsRendered = Array.from(renderingStates.channels.values())
      .every(progress => progress === 100);

    if (allChannelsRendered) {
      renderingStates.completed = true;
    }

  } catch (error) {
    console.error('Error fetching channel data:', error);
    loadingStates.channels.set(channelKey, 100);
    renderingStates.channels.set(channelKey, 100);
    ElMessage.error(`Failed to load data for channel ${channel.channel_name}: ${error.message}`);
  }
};

// 绘制总览图表
const drawOverviewChart = () => {
  if (overviewData.value.length === 0) {
    return;
  }

  const svg = d3.select('#overview-chart');
  svg.selectAll('*').remove();

  // 获取实际可用宽度
  const svgNode = svg.node();
  const svgWidth = svgNode.getBoundingClientRect().width;

  const margin = { top: 10, right: 45, bottom: 35, left: 45 };
  const width = svgWidth - margin.left - margin.right;
  const height = 80 - margin.top - margin.bottom;

  svg
    .attr(
      'viewBox',
      `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`
    )
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .attr('width', '100%');

  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  // 计算所有数据的范围
  const allX = overviewData.value.flatMap((d) => d.X_value);
  const allY = overviewData.value.flatMap((d) => d.Y_value);
  const xExtent = d3.extent(allX);
  const yExtent = d3.extent(allY);

  // 更新全局 X 域
  xDomains.value.global = xExtent;

  // 更新 brush_begin 和 brush_end 到当前数据范围
  updatingBrush.value = true;
  brush_begin.value = xExtent[0].toFixed(4);
  brush_end.value = xExtent[1].toFixed(4);
  store.commit("updatebrush", {begin: brush_begin.value, end: brush_end.value});
  updatingBrush.value = false;

  const x = d3.scaleLinear().domain(xExtent).range([0, width]);
  overviewXScale.value = x;

  const y = d3.scaleLinear().domain(yExtent).range([height, 0]);

  // 绘制总览数据线条
  const lines = g.selectAll('.overview-line')
    .data(overviewData.value, d => `${d.channelName}_${d.channelshotnumber}`);

  // 进入
  lines.enter()
    .append('path')
    .attr('class', 'overview-line')
    .attr('fill', 'none')
    .attr('stroke', d => d.color || 'steelblue')
    .attr('stroke-width', 1)
    .attr('d', d => d3.line()
      .x((v, i) => x(d.X_value[i]))
      .y((v, i) => y(v))
      .curve(d3.curveMonotoneX)(d.Y_value)
    );

  // 更新
  lines
    .attr('stroke', d => d.color || 'steelblue')
    .attr('d', d => d3.line()
      .x((v, i) => x(d.X_value[i]))
      .y((v, i) => y(v))
      .curve(d3.curveMonotoneX)(d.Y_value)
    );

  // 退出
  lines.exit().remove();

  // 绘制坐标轴
  g.append('g')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(x)).style("font-size", "1em")
    .style("font-weight", "bold");

  // 添加刷子功能
  const brush = d3.brushX()
    .extent([
      [0, 0],
      [width, height],
    ])
    .on('brush end', debounce((event) => {
      if (updatingBrush.value) return;

      // 当点击空白处时，恢复到完整范围
      const selection = event.selection || initialSelection;
      const newDomain = selection.map(x.invert, x);

      updatingBrush.value = true;
      brush_begin.value = newDomain[0].toFixed(4);
      brush_end.value = newDomain[1].toFixed(4);
      store.commit("updatebrush", {begin: brush_begin.value, end: brush_end.value});
      updatingBrush.value = false;

      // 如果是点击空白处，手动设置刷选框
      if (!event.selection) {
        brushG.call(brush.move, initialSelection);
        brushSelections.value.overview = initialSelection;
      } else {
        brushSelections.value.overview = selection;
      }

      // 更新全局 X 域
      xDomains.value.global = newDomain;

      // 重新绘制组合图表
      drawCombinedChart();

      // 高亮匹配结果
      selectedChannels.value.forEach((channel) => {
        const channelMatchedResults = matchedResults.value.filter(
          (r) => r.channel_name === channel.channel_name
        );
        channelMatchedResults.forEach((result) => {
          drawHighlightRects(channel.channel_name, [result]);
        });
      });
    }, 150));

  overviewBrushInstance.value = brush;

  const brushG = g.append('g').attr('class', 'brush').call(brush);

  // 设置初始刷选范围为当前数据范围
  const initialSelection = xExtent.map(x);
  brushG.call(brush.move, initialSelection);
  brushSelections.value.overview = initialSelection;
};


// 添加输入处理函数
const handleInputBlur = (type) => {
  if (updatingBrush.value) return;
  if (!overviewXScale.value || !overviewBrushInstance.value) return;

  const x = overviewXScale.value;
  const brush = overviewBrushInstance.value;
  const currentExtent = x.domain();

  let start = parseFloat(brush_begin.value);
  let end = parseFloat(brush_end.value);

  // 验证输入值
  if (isNaN(start) || isNaN(end)) {
    ElMessage.warning('请输入有效的数字');
    brush_begin.value = currentExtent[0].toFixed(4);
    brush_end.value = currentExtent[1].toFixed(4);
    return;
  }

  // 确保起点小于终点
  if (start >= end) {
    ElMessage.warning('起点必须小于终点');
    brush_begin.value = currentExtent[0].toFixed(4);
    brush_end.value = currentExtent[1].toFixed(4);
    return;
  }

  // 获取数据的实际范围
  const allX = overviewData.value.flatMap((d) => d.X_value);
  const dataExtent = d3.extent(allX);
  const epsilon = 0.0001; // 添加容差值

  // 确保在有效范围内，使用容差值进行比较
  if (start < dataExtent[0] - epsilon || end > dataExtent[1] + epsilon) {
    ElMessage.warning(`输入值必须在 ${dataExtent[0].toFixed(4)} 到 ${dataExtent[1].toFixed(4)} 之间`);
    brush_begin.value = currentExtent[0].toFixed(4);
    brush_end.value = currentExtent[1].toFixed(4);
    return;
  }

  // 格式化输入值
  brush_begin.value = start.toFixed(4);
  brush_end.value = end.toFixed(4);

  // 更新 store 中的值
  store.commit("updatebrush", { begin: brush_begin.value, end: brush_end.value });

  // 更新刷选区域和图表
  const selection = [x(start), x(end)];
  updatingBrush.value = true;
  d3.select('#overview-chart').select('.brush').call(brush.move, selection);
  updatingBrush.value = false;

  // 更新全局 X 域
  xDomains.value.global = [start, end];

  // 重新绘制图表
  drawCombinedChart();

  // 更新原始域
  originalDomains.value.global = {
    x: [start, end],
    y: y.domain()
  };
};

// 修改 watch 函数，移除即时格式化
watch([brush_begin, brush_end], ([newBegin, newEnd], [oldBegin, oldEnd]) => {
  // 仅在输入框失焦或按下回车时处理
}, { immediate: false });


// 数据插值平滑
const createGaussianKernel = (sigma, size) => {
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
};

// 应用高斯平滑
const gaussianSmooth = (data, sigma) => {
  const kernelSize = Math.ceil(sigma * 6); // 核（通常为 6 * sigma）
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
};

// 平滑插值函数
const interpolateData = (data, t) => {
  if (t === 0) {
    return data; // 不平滑直接返回
  }

  const sigma = t * 20; // 根据 t 调整平滑强度
  return gaussianSmooth(data, sigma);
};

// 绘制综合图表
const drawCombinedChart = () => {
  if (channelsData.value.length === 0) {
    return; // 数据为空，暂时不绘制组合图表
  }
  const svg = d3.select('#combined-chart');
  svg.selectAll('*').remove(); // 清空之前的内容

  const { margin, width, height } = mainChartDimensions.value;

  // 设置 SVG
  svg
    .attr(
      'viewBox',
      `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`
    )
    .attr('preserveAspectRatio', 'xMidYMid meet')
    .attr('width', '100%');

  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  // 定义 clipPath
  g.append("defs").append("clipPath")
    .attr("id", "clip")
    .append("rect")
    .attr("width", width)
    .attr("height", height);

  // 创建数据绘图并应用 clipPath
  const dataGroup = g.append("g")
    .attr("clip-path", "url(#clip)");

  // 计算所有数据的范围
  const allX = channelsData.value.flatMap(d => d.X_value);
  const allY = channelsData.value.flatMap(d => d.Y_value);
  const xExtent = xDomains.value.global || d3.extent(allX);
  
  // 修改这里：使用存储的 Y 轴范围或默认范围
  let yExtent;
  if (originalDomains.value.global && originalDomains.value.global.y) {
    yExtent = originalDomains.value.global.y;
  } else {
    yExtent = [-1, 1]; // 默认归一化范围
    // 保存初始 Y 轴范围
    if (!originalDomains.value.global) {
      originalDomains.value.global = {
        x: xExtent,
        y: yExtent
      };
    }
  }

  const yRangePadding = (yExtent[1] - yExtent[0]) * 0.1;
  const yMin = yExtent[0] - yRangePadding;
  const yMax = yExtent[1] + yRangePadding;

  const x = d3.scaleLinear()
    .domain(xExtent)
    .range([0, width]);

  const y = d3.scaleLinear()
    .domain([yMin, yMax])
    .range([height, 0]);

  // 添加坐标轴（不在 dataGroup 内，避免被裁剪）
  g.selectAll('.x-axis').remove(); // 移除旧的坐标轴
  g.selectAll('.y-axis').remove(); // 移除旧的坐标轴

  g.append('g')
    .attr('class', 'x-axis')
    .attr('transform', `translate(0,${height})`)
    .call(d3.axisBottom(x)).style("font-size", "1.2em") // 增大字体大小
    .attr("font-weight", "bold"); // 加粗字体;

  g.append('g')
    .attr('class', 'y-axis')
    .call(d3.axisLeft(y)
      .tickFormat(d => (d >= -1 && d <= 1) ? d : '') // 仅在 -1 到 1 之间显示标签
    ).style("font-size", "1em") // 增大字体大小
    .attr("font-weight", "bold");

  // 绘制格线（不在 dataGroup 内，避免被裁剪）
  g.selectAll('.grid').remove(); // 移除旧的网格线

  g.append('g')
    .attr('class', 'grid')
    .call(
      d3.axisLeft(y)
        .tickSize(-width)
        .tickFormat('')
    )
    .selectAll('line')
    .style('stroke', '#ccc')
    .style('stroke-dasharray', '3,3');

  g.append('g')
    .attr('class', 'grid')
    .attr('transform', `translate(0,${height})`)
    .call(
      d3.axisBottom(x)
        .tickSize(-height)
        .tickFormat('')
    )
    .selectAll('line')
    .style('stroke', '#ccc')
    .style('stroke-dasharray', '3,3');

  // 定义颜色例尺（可，确保每个通道颜色唯一）
  const colorScale = d3.scaleOrdinal(d3.schemeCategory10)
    .domain(channelsData.value.map(d => d.channelName));

  // 绘制每个通道的主线
  channelsData.value.forEach((data, index) => {
    let smoothedYValue = data.Y_value;
    if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
      smoothedYValue = interpolateData(data.Y_value, smoothnessValue.value);
    }

    const lineGenerator = d3.line()
      .x((v, i) => x(data.X_value[i]))
      .y((v, i) => y(v))
      .curve(d3.curveMonotoneX);

    // 绘制初始曲线
    dataGroup.append('path')
      .datum(data.Y_value)
      .attr('class', 'channel-line')
      .attr('fill', 'none')
      .attr('stroke', data.color) // 使用最新的通道色
      .attr('stroke-width', 1.5)
      .attr('opacity', smoothnessValue.value > 0 ? 0.3 : 1)
      .attr('d', lineGenerator);


    // 绘制错误数据
    data.errorsData.forEach((errorData, errorIndex) => {
      errorData.X_value_error.forEach((X_value_error, idx) => {
        const Y_value_error = errorData.Y_value_error[idx];

        const errorLine = d3.line()
          .x((v, i) => x(X_value_error[i]))
          .y((v, i) => y(v))
          .curve(d3.curveMonotoneX);

        const yOffset = errorData.person === 'machine' ? 6 : -6;
        const isMachine = errorData.person === 'machine';

        dataGroup.append('path')
          .datum(Y_value_error)
          .attr('class', `error-line-${errorIndex}-${data.channelName}`)
          .attr('fill', 'none')
          .attr('stroke', errorData.color) // 使用最新的异常颜色
          .attr('stroke-width', 2)
          .attr('opacity', 0.8)
          .attr('transform', `translate(0,${yOffset})`)
          .attr('d', errorLine)
          .attr('stroke-dasharray', isMachine ? '5,5' : null); // Dashed or solid
      });
    });


    // 绘制平滑后的线
    if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
      const smoothedLineGenerator = d3.line()
        .x((v, i) => x(data.X_value[i]))
        .y((v, i) => y(v))
        .curve(d3.curveMonotoneX);

      dataGroup.append('path')
        .datum(smoothedYValue)
        .attr('class', `smoothed-line-${data.channelName}`)
        .attr('fill', 'none')
        .attr('stroke', data.color || colorScale(data.channelName))
        .attr('stroke-width', 1.5)
        .attr('d', smoothedLineGenerator);
    }
  });

  // 添加标签
  svg.selectAll('.x-label').remove();
  svg.selectAll('.y-label').remove();

  svg.append('text')
    .attr('class', 'x-label')
    .attr('x', mainChartDimensions.value.margin.left + width + 15)
    .attr('y', mainChartDimensions.value.margin.top + height + 8)
    .attr('text-anchor', 'middle')
    .attr('font-size', '1.4em').style('font-weight', 'bold')
    .attr('fill', '#000')
    .text('s')

  svg.append('text')
    .attr('class', 'y-label')
    .attr('transform', `translate(${mainChartDimensions.value.margin.left - 60}, ${mainChartDimensions.value.margin.top + height / 2}) rotate(-90)`)
    .attr('text-anchor', 'middle')
    .attr('alignment-baseline', 'middle')
    .attr('font-size', '1.4em').style('font-weight', 'bold')
    .attr('fill', '#000')
    .text('normalization');

  // 实现缩放功能，禁用鼠标滚轮缩放
  const zoom = d3.zoom()
    .scaleExtent([1, 10])
    .translateExtent([[0, 0], [width, height]])
    .extent([[0, 0], [width, height]])
    .filter(function (event) {
      return event.type !== 'wheel' && event.type !== 'dblclick';
    })
    .on('zoom', zoomed);

  svg.call(zoom);

  function zoomed(event) {
    const transform = event.transform;
    const newX = transform.rescaleX(x);
    const newY = transform.rescaleY(y);

    // 更新坐标轴
    g.select('.x-axis').call(d3.axisBottom(newX));
    g.select('.y-axis').call(d3.axisLeft(newY));

    // 更新所有主曲线
    dataGroup.selectAll('.channel-line')
      .attr('d', function (d, i) {
        const channel = channelsData.value[i];
        const lineGenerator = d3.line()
          .x((v, idx) => newX(channel.X_value[idx]))
          .y((v, idx) => newY(v))
          .curve(d3.curveMonotoneX);
        return lineGenerator(d);
      });

    // 更新所有错误数据线条
    dataGroup.selectAll('[class^="error-line-"]')
      .attr('d', function (d, i, nodes) {
        const parentClass = d3.select(this).attr('class');
        const match = parentClass.match(/error-line-\d+-(.+)/);
        const channelName = match ? match[1] : null;
        const channel = channelsData.value.find(c => c.channelName === channelName);
        if (!channel) return null;
        const parts = parentClass.split('-');
        const errorIndex = parseInt(parts[2]);
        const errorData = channel.errorsData[errorIndex];
        if (!errorData) return null;
        const X_value_error = errorData.X_value_error[i];
        const Y_value_error = errorData.Y_value_error[i];
        const errorLine = d3.line()
          .x((v, idx) => newX(X_value_error[idx]))
          .y((v, idx) => newY(v))
          .curve(d3.curveMonotoneX);
        return errorLine(Y_value_error);
      });

    // 更新所有平滑后的曲线
    dataGroup.selectAll('[class^="smoothed-line-"]')
      .attr('d', function (d, i, nodes) {
        const parentClass = d3.select(this).attr('class');
        const match = parentClass.match(/smoothed-line-(.+)/);
        const channelName = match ? match[1] : null;
        const channel = channelsData.value.find(c => c.channelName === channelName);
        if (!channel) return null;
        const smoothedYValue = interpolateData(channel.Y_value, smoothnessValue.value);
        const smoothedLineGenerator = d3.line()
          .x((v, idx) => newX(channel.X_value[idx]))
          .y((v, idx) => newY(v))
          .curve(d3.curveMonotoneX);
        return smoothedLineGenerator(smoothedYValue);
      });
  }

  // 在绘制完主要内容后，添加缩放brush
  const zoomBrush = d3.brush()
    .extent([[0, 0], [width, height]])
    .on('end', zoomBrushed);

  const zoomBrushG = g.append('g')
    .attr('class', 'zoom-brush')
    .call(zoomBrush);

  function zoomBrushed(event) {
    if (!event.sourceEvent) return;
    if (!event.selection) {
      // 点击空白处，恢复到总览条的范围
      if (brush_begin.value && brush_end.value) {
        // 恢复到总览条的范围
        xDomains.value.global = [parseFloat(brush_begin.value), parseFloat(brush_end.value)];
        // 重置 Y 轴到默认范围
        originalDomains.value.global = {
          x: [parseFloat(brush_begin.value), parseFloat(brush_end.value)],
          y: [-1, 1]
        };
        drawCombinedChart();
      }
      return;
    }

    // 获取选择的范围
    const [[x0, y0], [x1, y1]] = event.selection;

    // 计算新的显示范围
    const newXDomain = [x.invert(x0), x.invert(x1)];
    const newYDomain = [y.invert(y1), y.invert(y0)];

    // 更新全局域
    xDomains.value.global = newXDomain;
    // 更新存储的 Y 轴范围
    originalDomains.value.global = {
      x: newXDomain,
      y: newYDomain
    };

    // 清除选择
    d3.select(this).call(zoomBrush.move, null);

    // 重新绘制图表
    drawCombinedChart();

    // 重新绘制高亮区域
    selectedChannels.value.forEach((channel) => {
      const channelMatchedResults = matchedResults.value.filter(
        (r) => r.channel_name === channel.channel_name
      );
      channelMatchedResults.forEach((result) => {
        drawHighlightRects(channel.channel_name, [result]);
      });
    });
  }
};

// 处理通道数据并绘制图表
const processChannelData = async (data, channel) => {
  try {
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;

    // 采样数据
    const sampledData = sampleData(data, sampleRate.value);

    // 存储归一化前的 Y 值
    sampledData.Y_original = sampledData.Y_value.slice();

    // 归一化 Y_value
    sampledData.Y_value = normalize(sampledData.Y_value);

    let errorsData = [];
    // 处理错误数据
    for (const [errorIndex, error] of channel.errors.entries()) {
      const error_name = error.error_name;
      const error_color = error.color;

      // 构建用于缓存的 errorCacheKey
      const errorCacheKey = `${channelKey}-error-${error_name}-${errorIndex}-sampling-${sampleRate.value}`;
      let errorResponseData;

      // 检查错误数据缓存
      if (dataCache.value.has(errorCacheKey)) {
        errorResponseData = dataCache.value.get(errorCacheKey);
      } else {
        const errorParams = {
          channel_key: channelKey,
          channel_type: channel.channel_type,
          error_name: error_name,
          error_index: errorIndex,
        };

        try {
          // 使用重试机制和并发限制获取错误数据
          if(error_name === "NO ERROR")
            continue;
          const errorResponse = await limit(() => retryRequest(async () => {
            return await axios.get(`http://localhost:5000/api/error-data/`, { params: errorParams });
          }));
          errorResponseData = errorResponse.data;
          dataCache.value.set(errorCacheKey, errorResponseData);
        } catch (err) {
          console.warn(`Failed to fetch error data for ${errorCacheKey}:`, err);
          continue; // 跳过这个错误数据，继续处理其他
        }
      }

      // 处理人工标注和机器识别的异常数据
      const [manualErrors, machineErrors] = errorResponseData;

      // 处理机器识别的异常
      for(const machineError of machineErrors) {
        if(!machineError.X_error || machineError.X_error.length === 0 || machineError.X_error[0].length === 0) {
          continue; // 跳过空的错误数据
        }

        const processedErrorSegments = machineError.X_error.map(
          (errorSegment) => {
            return sampleErrorSegment(errorSegment, sampledData, findStartIndex, findEndIndex);
          }
        );

        const sampledErrorData = {
          X_value_error: processedErrorSegments.map((seg) => seg.X),
          Y_value_error: processedErrorSegments.map((seg) => seg.Y),
          color: error_color,
          person: machineError.person,
        };

        errorsData.push(sampledErrorData);
      }

      // 处理人工标注的异常
      for(const manualError of manualErrors) {
        if(!manualError.X_error || manualError.X_error.length === 0 || manualError.X_error[0].length === 0) {
          continue; // 跳过空的错误数据
        }

        const processedErrorSegments = manualError.X_error.map(
          (errorSegment) => {
            return sampleErrorSegment(errorSegment, sampledData, findStartIndex, findEndIndex);
          }
        );

        const sampledErrorData = {
          X_value_error: processedErrorSegments.map((seg) => seg.X),
          Y_value_error: processedErrorSegments.map((seg) => seg.Y),
          color: error_color,
          person: manualError.person,
        };

        errorsData.push(sampledErrorData);
      }
    }

    // 更新图表数据
    channelsData.value.push({
      channelName: channel.channel_name,
      channelshotnumber: channel.shot_number,
      X_value: sampledData.X_value,
      Y_value: sampledData.Y_value,
      Y_original: sampledData.Y_original,
      color: channel.color,
      errorsData: errorsData,
      xUnit: data.X_unit,
      yUnit: data.Y_unit,
      channelType: data.channel_type,
      channelNumber: data.channel_number,
      shotNumber: channel.shot_number
    });

    // 更新导出数据
    exposeData.value.push({
      channel_type: data.channel_type,
      channel_name: channel.channel_name,
      X_value: sampledData.X_value,
      X_unit: data.X_unit,
      Y_value: sampledData.Y_original,
      Y_unit: data.Y_unit,
      errorsData: errorsData,
      shot_number: channel.shot_number
    });

    // 更新总览数据
    overviewData.value.push({
      channelName: channel.channel_name,
      X_value: sampledData.X_value,
      Y_value: sampledData.Y_value,
      color: channel.color,
    });

  } catch (error) {
    console.error('Error in processChannelData:', error);
    throw error;
  }
};

// 添加窗口大小变化的处理函数
const handleResize = debounce(() => {
  if (overviewData.value && overviewData.value.length > 0) {
    drawOverviewChart();
  }
}, 200);

// 在 script setup 部分添加原始域存储
const originalDomains = ref({}); // 存储原始的显示范围
</script>


<style scoped>
.el-divider--horizontal {
  margin: 0px !important;
  border-top: 3px var(--el-border-color) var(--el-border-style);
}

.chart-container {
  width: 98.8%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.chart-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
}

svg {
  width: 100%;
  position: relative;
}

.overview-container {
  width: 100%;
  position: absolute;
  bottom: 10px;
  top: 83%;
  background-color: white;
  z-index: 999;
}

.overview-content {
  position: relative;
  width: 100%;
  height: 100%;
  padding: 0 10px;
  display: flex;
  gap: 5px;
}

.overview-svg-container {
  flex: 1;
  min-width: 0;
  position: relative;
  height: 80px;
}

.overview-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
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

.edit-button {
  z-index: 999;
}

.legend text {
  font-size: 12px;
}


/* 去除颜色选择里面的箭头 */
:deep(.is-icon-arrow-down) {
  display: none !important;
}

/* 去除颜色选择器最外层的边框 */
:deep(.el-color-picker__trigger) {
  border: none;
}

/* 将颜色色块变为圆形 */
:deep(.el-color-picker__color) {
  border-radius: 50%;
}

/* 将下拉面板中的选色区域的选变为圆形 */
:deep(.el-color-dropdown__main-wrapper .el-color-alpha-slider__thumb,
  .el-color-dropdown__main-wrapper .el-color-hue-slider__thumb) {
  width: 14px;
  height: 14px;
  border-radius: 50%;
}

/* 将下拉面板中的预设颜色方块变为圆形 */
:deep(.el-color-predefine__color-selector) {
  border-radius: 50%;
}

:deep(.el-color-picker__color-inner) {
  border-radius: 50%;
}

:deep(.el-color-predefine__color-selector)::before {
  border-radius: 50%;
}

.legend-container {
  position: absolute;
  top: 0;
  width: 100%;
  z-index: 999;
}

.progress-wrapper {
  margin: 5px 0;
  padding: 0 10px;
}

.progress-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  font-size: 13px;
  color: #606266;
}

.progress-percentage {
  font-weight: bold;
  color: #409EFF;
}

/* 自定义进度条式 */
:deep(.el-progress-bar__outer) {
  background-color: #f0f2f5;
  border-radius: 4px;
}

:deep(.el-progress-bar__inner) {
  transition: width 0.3s ease;
  border-radius: 4px;
}

:deep(.el-progress--line) {
  margin-bottom: 0;
}

:deep(.el-progress-bar__innerText) {
  font-size: 12px;
  margin: 0 5px;
  color: #fff;
}

/* 让输入框内的文字可以选中 */
.el-input {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让输入框内的文字可以选中 */
.el-input__inner {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}
</style>
