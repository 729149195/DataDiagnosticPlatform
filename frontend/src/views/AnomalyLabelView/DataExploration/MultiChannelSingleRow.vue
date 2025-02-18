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
    </div>
  </div>
</template>

<script setup>
import * as d3 from 'd3';
import debounce from 'lodash/debounce';
import { ref, watch, computed, onMounted, nextTick, reactive, onUnmounted } from 'vue';
import { ElMessage, ElEmpty,ElProgress } from 'element-plus';
import { useStore } from 'vuex';
import LegendComponent from '@/components/LegendComponent.vue';
import chartWorkerManager from '@/workers/chartWorkerManager';


// Reactive references
const xDomains = ref({ global: null });
// 从store获取数据
const brush_begin = computed({
  get: () => store.state.brush_begin,
  set: (value) => store.commit('updatebrush', { begin: value, end: brush_end.value })
});

const brush_end = computed({
  get: () => store.state.brush_end,
  set: (value) => store.commit('updatebrush', { begin: brush_begin.value, end: value })
});
const channelsData = ref([]);
const exposeData = ref([])
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

const mainChartDimensions = ref({
  margin: { top: 50, right: 20, bottom: 60, left: 80 },
  width: 0,
  height: 500 - 50 - 60, // 调整主图表高度
});

// Vuex store
const store = useStore();
const selectedChannels = computed(() => store.state.selectedChannels);

const sampling = computed(() => store.state.sampling);
const smoothnessValue = computed(() => store.state.smoothness);
const sampleRate = ref(store.state.sampling);
const matchedResults = computed(() => store.getters.getMatchedResults);

const updateChannelColor = ({ channelKey, color }) => {
  const channel = selectedChannels.value.find(
    (ch) => `${ch.channel_name}_${ch.shot_number}` === channelKey
  );
  if (channel) {
    channel.color = color;
    // 更新 Vuex 存储
    store.commit('updateChannelColor', { channel_key: channelKey, color });

    // 只更新特定通道的主线条颜色
    d3.select('#combined-chart')
      .selectAll(`.channel-line, .smoothed-line-${channel.channel_name}`)
      .filter(d => {
        const lineIndex = channelsData.value.findIndex(
          cd => `${cd.channelName}_${cd.channelshotnumber}` === channelKey
        );
        return d === channelsData.value[lineIndex]?.Y_value;
      })
      .attr('stroke', color);

    // 更新数据中的颜色
    const channelDataIndex = channelsData.value.findIndex(
      d => `${d.channelName}_${d.channelshotnumber}` === channelKey
    );
    if (channelDataIndex !== -1) {
      channelsData.value[channelDataIndex].color = color;
    }
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
  channelsData.value = [];
  exposeData.value = []
  await Promise.all(selectedChannels.value.map(channel => fetchDataAndStore(channel)));

  if (!xDomains.value.global) {
    const allX = channelsData.value.flatMap(d => d.X_value);
    xDomains.value.global = d3.extent(allX);
  }

  await nextTick(); // 等待数据更新到 DOM
  drawCombinedChart();
}, 300);


// onMounted 生命周期钩子
onMounted(async () => {
  const container = document.querySelector('.chart-container');
  const containerWidth = container.offsetWidth;

  mainChartDimensions.value.width = containerWidth - mainChartDimensions.value.margin.left - mainChartDimensions.value.margin.right;

  if (selectedChannels.value.length > 0) {
    await renderCharts();
  }

  window.addEventListener('resize', handleResize);
});

// 在组件卸载时移除监听器
onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});

// 修改 selectedChannels 的监听器
watch(selectedChannels, async (newChannels, oldChannels) => {
  // 检查是否只是颜色发生变化
  const isOnlyColorChange = newChannels.length === oldChannels.length &&
    newChannels.every(newCh => {
      const oldCh = oldChannels.find(
        old => `${old.channel_name}_${old.shot_number}` === `${newCh.channel_name}_${newCh.shot_number}`
      );
      return oldCh &&
        oldCh.color !== newCh.color &&
        JSON.stringify({ ...oldCh, color: newCh.color }) === JSON.stringify(newCh);
    });

  if (isOnlyColorChange) {
    // 只处理颜色变化的通道，复用 updateChannelColor 函数
    newChannels.forEach(newCh => {
      const oldCh = oldChannels.find(
        old => `${old.channel_name}_${old.shot_number}` === `${newCh.channel_name}_${newCh.shot_number}`
      );
      if (oldCh && oldCh.color !== newCh.color) {
        updateChannelColor({
          channelKey: `${newCh.channel_name}_${newCh.shot_number}`,
          color: newCh.color
        });
      }
    });
  } else {
    // 如果不是仅颜色变化，则执行完整的重新渲染
    channelsData.value = [];
    exposeData.value = [];
    await nextTick();
    renderCharts();
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

    // 模拟进度更新
    const progressInterval = setInterval(() => {
      const currentProgress = loadingStates.channels.get(channelKey) || 0;
      if (currentProgress < 90) {
        loadingStates.channels.set(channelKey, Math.min(currentProgress + 10, 90));
      }
    }, 100);

    // 使用 store action 获取数据
    const data = await store.dispatch('fetchChannelData', { channel });

    clearInterval(progressInterval);
    loadingStates.channels.set(channelKey, 100);

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

    // 绘制错误数据
    if (data.errorsData && data.errorsData.length > 0) {
      data.errorsData.forEach(errorData => {
        // 解构人工标注和机器识别的错误数据
        const [manualErrors, machineErrors] = errorData;


        // 辅助函数：根据时间范围获取对应的数据点
        const getDataPointsInRange = (xRange) => {
          const startTime = xRange[0];
          const endTime = xRange[1];
          const points = [];

          // 找到对应时间范围内的数据点
          data.X_value.forEach((x, i) => {
            if (x >= startTime && x <= endTime) {
              points.push({
                x: x,
                y: data.Y_value[i]
              });
            }
          });

          return points;
        };

        // 处理人工标注的错误
        if (manualErrors && manualErrors.length > 0) {
          manualErrors.forEach(error => {
            if (error.X_error && error.X_error.length > 0) {
              error.X_error.forEach(xRange => {
                const errorPoints = getDataPointsInRange(xRange);
                if (errorPoints.length > 0) {
                  // 创建错误标记
                  dataGroup
                    .append('path')
                    .datum(errorPoints)
                    .attr('class', 'error-line')
                    .attr('fill', 'none')
                    .attr('stroke', error.color || 'rgba(220, 20, 60, 0.3)')  // 使用错误定义的颜色
                    .attr('stroke-width', 10)  // 使用较粗的线条
                    .attr('stroke-linecap', 'round')  // 使线条端点圆滑
                    .attr('stroke-linejoin', 'round')  // 使线条连接处圆滑
                    .attr('opacity', 0.8)
                    .attr('d', d3.line()
                      .x(d => x(d.x))
                      .y(d => y(d.y))
                      .curve(d3.curveMonotoneX)
                    )
                    .style('vector-effect', 'non-scaling-stroke');  // 保持描边宽度不随缩放变化
                }
              });
            }
          });
        }

        // 处理机器识别的错误
        if (machineErrors && machineErrors.length > 0) {
          machineErrors.forEach(error => {
            if (error.X_error && error.X_error.length > 0) {
              error.X_error.forEach(xRange => {
                const errorPoints = getDataPointsInRange(xRange);
                if (errorPoints.length > 0) {
                  // 创建错误标记
                  dataGroup
                    .append('path')
                    .datum(errorPoints)
                    .attr('class', 'error-line')
                    .attr('fill', 'none')
                    .attr('stroke', error.color || 'rgba(220, 20, 60, 0.3)')  // 使用错误定义的颜色
                    .attr('stroke-width', 10)  // 使用较粗的线条
                    .attr('stroke-linecap', 'round')  // 使线条端点圆滑
                    .attr('stroke-linejoin', 'round')  // 使线条连接处圆滑
                    .attr('opacity', 0.8)
                    .attr('stroke-dasharray', '5, 5')  // 机器识别使用虚线
                    .attr('d', d3.line()
                      .x(d => x(d.x))
                      .y(d => y(d.y))
                      .curve(d3.curveMonotoneX)
                    )
                    .style('vector-effect', 'non-scaling-stroke');  // 保持描边宽度不随缩放变化
                }
              });
            }
          });
        }
      });
    }

    // 绘制初始曲线
    dataGroup.append('path')
      .datum(data.Y_value)
      .attr('class', 'channel-line')
      .attr('fill', 'none')
      .attr('stroke', data.color) // 使用最新的通道色
      .attr('stroke-width', 1.5)
      .attr('opacity', smoothnessValue.value > 0 ? 0.3 : 1)
      .attr('d', lineGenerator);

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
    .attr('x', mainChartDimensions.value.margin.left + width / 2)
    .attr('y', mainChartDimensions.value.margin.top + height + 40)
    .attr('text-anchor', 'middle')
    .attr('font-size', '1.4em')
    .style('font-weight', 'bold')
    .attr('fill', '#000')
    .text('Time(s)')

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
    renderingStates[channelKey] = 25; // 开始处理数据

    // 准备数据
    const channelData = {
      X_value: [...data.X_value],
      Y_value: [...data.Y_value],
      originalFrequency: data.originalFrequency,
      originalDataPoints: data.X_value.length
    };

    // 获取错误数据
    let errorDataResults = [];
    if (channel.errors && channel.errors.length > 0) {
      try {
        // 使用store中的方法获取异常数据
        errorDataResults = await store.dispatch('fetchAllErrorData', channel);
      } catch (err) {
        console.warn('Failed to fetch error data:', err);
      }
    }

    renderingStates[channelKey] = 50; // 数据准备完成

    // 使用 chartWorkerManager 处理数据
    const processedData = await chartWorkerManager.processData(
      channelData,
      sampleRate.value,
      smoothnessValue.value,
      channelKey,
      channel.color,
      data.X_unit,
      data.Y_unit,
      data.channel_type,
      data.channel_number,
      channel.shot_number
    );

    if (processedData) {
      // 归一化 Y 值
      const yAbsMax = d3.max(processedData.processedData.Y_value, d => Math.abs(d));
      const normalizedY = yAbsMax === 0 ?
        processedData.processedData.Y_value.map(() => 0) :
        processedData.processedData.Y_value.map(y => y / yAbsMax);

      // 更新图表数据
      channelsData.value.push({
        channelName: channel.channel_name,
        channelshotnumber: channel.shot_number,
        X_value: processedData.processedData.X_value,
        Y_value: normalizedY,
        Y_original: processedData.processedData.Y_value,
        color: channel.color,
        errorsData: errorDataResults,  // 添加错误数据
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
        X_value: processedData.processedData.X_value,
        X_unit: data.X_unit,
        Y_value: processedData.processedData.Y_value,
        Y_unit: data.Y_unit,
        errorsData: errorDataResults,  // 添加错误数据
        shot_number: channel.shot_number
      });

      renderingStates[channelKey] = 75; // 更新渲染状态
      nextTick(() => {
        try {
          drawCombinedChart();
          renderingStates[channelKey] = 100;
        } catch (error) {
          console.error(`Error drawing chart for ${channelKey}:`, error);
          renderingStates[channelKey] = 100;
        }
      });
    }

  } catch (error) {
    console.error(`Error processing channel data for ${channel.channel_name}:`, error);
    ElMessage.error(`处理通道数据错误: ${error.message}`);
    renderingStates[channelKey] = 100; // 确保错误时也更新状态
  }
};

// 添加窗口大小变化的处理函数
const handleResize = debounce(() => {
  if (channelsData.value && channelsData.value.length > 0) {
    drawCombinedChart();
  }
}, 200);

// 在 script setup 部分添加原始域存储
const originalDomains = ref({}); // 存储原始的显示范围

// 在组件卸载时终止 Worker
onUnmounted(() => {
  chartWorkerManager.terminate();
});
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

.legend-container {
  position: absolute;
  top: 60px;
  right: 50px;
  z-index: 999;
  min-width: 100px;
  max-width: 200px;
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

/* 去除颜色选择器里面的箭头 */
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

/* 将下拉面板中的选色区域的选框变为圆形 */
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
