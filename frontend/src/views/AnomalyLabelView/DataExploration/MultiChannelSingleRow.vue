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
        <div id="combined-chart" ref="chartContainer" :style="{
          opacity: renderingStates.completed ? 1 : 0,
          transition: 'opacity 0.3s ease-in-out',
          width: '100%',
          height: '100%'
        }"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import * as d3 from 'd3';
import Highcharts from 'highcharts';
import debounce from 'lodash/debounce';
import { ref, watch, computed, onMounted, nextTick, reactive, onUnmounted } from 'vue';
import { ElMessage, ElEmpty, ElProgress } from 'element-plus';
import { useStore } from 'vuex';
import LegendComponent from '@/components/LegendComponent.vue';
import chartWorkerManager from '@/workers/chartWorkerManager';
import { DataSmoother } from '@/views/AnomalyLabelView/Sketch/data-smoother.js';

// 创建数据平滑处理实例
const dataSmoother = new DataSmoother();
// 平滑数据函数
const interpolateData = (data, smoothness) => {
  if (!data || data.length === 0) return [];
  
  // 将数据转换为 DataSmoother 需要的格式
  const formattedData = data.map((y, i) => ({ x: i, y, origX: i, origY: y }));
  
  // 使用 DataSmoother 进行平滑处理
  const smoothedData = dataSmoother.interpolateData(formattedData, smoothness);
  
  // 返回平滑后的 Y 值数组
  return smoothedData.map(point => point.y);
};

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
const chartContainer = ref(null);
const resetProgress = () => {
  loadingStates.channels.clear();
  loadingStates.dataLoaded = false;
  renderingStates.channels.clear();
  renderingStates.completed = false;
  loadingStates.renderStarted = false;
};
defineExpose({
  chartContainer: chartContainer,
  channelsData: exposeData,
  resetProgress
})

const mainChartDimensions = ref({
  margin: { top: 50, right: 20, bottom: 60, left: 80 },
  width: 0,
  height: 0, // 将会动态计算
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

    // 获取当前图表实例
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (chart) {
      // 更新特定通道的线条颜色
      chart.series.forEach(series => {
        if (series.name === channelKey || series.name === `${channelKey}_smoothed`) {
          series.update({
            color: color
          }, false); // 不立即重绘
        }
      });
      chart.redraw(); // 一次性重绘图表
    }

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
  // 获取当前图表实例
  const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
  if (!chart) return;

  // 确保 xDomains.value.global 已经设置
  if (!xDomains.value.global) {
    console.warn(`xDomains.global 未设置，无法绘制高亮矩形。`);
    return;
  }

  // 移除之前的高亮区域
  chart.series.forEach(series => {
    if (series.name && series.name.startsWith(`highlight-${channel_name}`)) {
      series.remove(false); // 不重绘
    }
  });

  // 添加新的高亮区域
  results.forEach((result, index) => {
    const { start_X, end_X } = result;
    
    // 检查 start_X 和 end_X 是否为有效数字
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

    // 使用 Highcharts 的 plotBands 添加高亮区域
    chart.xAxis[0].addPlotBand({
      id: `highlight-${channel_name}-${index}`,
      from: validStart_X,
      to: validEnd_X,
      color: 'rgba(128, 128, 128, 0.3)',
      zIndex: 0
    });
  });

  // 重绘图表以显示高亮区域
  chart.redraw();
};


// 渲染图表，防抖以避免频繁调用
const renderCharts = debounce(async () => {
  channelsData.value = [];
  exposeData.value = []
  await Promise.all(selectedChannels.value.map(channel => fetchDataAndStore(channel)));

  if (!xDomains.value.global) {
    const allX = channelsData.value.flatMap(d => d.X_value);
    xDomains.value.global = [Math.min(...allX), Math.max(...allX)];
  }

  await nextTick(); // 等待数据更新到 DOM
  drawCombinedChart();
}, 300);


// onMounted 生命周期钩子
onMounted(async () => {
  const container = document.querySelector('.chart-container');
  const containerWidth = container.offsetWidth;
  
  // 计算适当的图表高度
  calculateChartHeight();

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

  // 计算所有数据的范围
  const allX = channelsData.value.flatMap(d => d.X_value);
  const xExtent = xDomains.value.global || [Math.min(...allX), Math.max(...allX)];

  // 使用存储的 Y 轴范围或默认范围
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

  // 准备 Highcharts 的数据系列
  const series = [];
  
  // 为每个通道创建数据系列
  channelsData.value.forEach((data, index) => {
    // 创建主线数据
    const mainLineSeries = {
      name: `${data.channelName}_${data.channelshotnumber}`,
      data: data.X_value.map((x, i) => [x, data.Y_value[i]]),
      color: data.color,
      lineWidth: 1.5,
      opacity: smoothnessValue.value > 0 ? 0.3 : 1,
      zIndex: 1,
      marker: {
        enabled: false
      },
      states: {
        hover: {
          lineWidthPlus: 0
        }
      },
      enableMouseTracking: false
    };
    series.push(mainLineSeries);

    // 如果有平滑值，添加平滑线
    if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
      let smoothedYValue = data.Y_value;
      smoothedYValue = interpolateData(data.Y_value, smoothnessValue.value);
      
      const smoothedLineSeries = {
        name: `${data.channelName}_${data.channelshotnumber}_smoothed`,
        data: data.X_value.map((x, i) => [x, smoothedYValue[i]]),
        color: data.color,
        lineWidth: 1.5,
        zIndex: 2,
        marker: {
          enabled: false
        },
        states: {
          hover: {
            lineWidthPlus: 0
          }
        },
        enableMouseTracking: false
      };
      series.push(smoothedLineSeries);
    }

    // 处理错误数据
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
              points.push([x, data.Y_value[i]]);
            }
          });

          return points;
        };

        // 处理人工标注的错误
        if (manualErrors && manualErrors.length > 0) {
          manualErrors.forEach((error, errorIndex) => {
            if (error.X_error && error.X_error.length > 0) {
              error.X_error.forEach((xRange, rangeIndex) => {
                const errorPoints = getDataPointsInRange(xRange);
                if (errorPoints.length > 0) {
                  // 创建错误标记系列
                  const errorSeries = {
                    name: `${data.channelName}_manual_error_${errorIndex}_${rangeIndex}`,
                    data: errorPoints,
                    color: error.color || 'rgba(220, 20, 60, 0.3)',
                    lineWidth: 10,
                    zIndex: 3,
                    marker: {
                      enabled: false
                    },
                    states: {
                      hover: {
                        lineWidthPlus: 0
                      }
                    },
                    enableMouseTracking: false
                  };
                  series.push(errorSeries);
                }
              });
            }
          });
        }

        // 处理机器识别的错误
        if (machineErrors && machineErrors.length > 0) {
          machineErrors.forEach((error, errorIndex) => {
            if (error.X_error && error.X_error.length > 0) {
              error.X_error.forEach((xRange, rangeIndex) => {
                const errorPoints = getDataPointsInRange(xRange);
                if (errorPoints.length > 0) {
                  // 创建错误标记系列
                  const errorSeries = {
                    name: `${data.channelName}_machine_error_${errorIndex}_${rangeIndex}`,
                    data: errorPoints,
                    color: error.color || 'rgba(220, 20, 60, 0.3)',
                    lineWidth: 10,
                    dashStyle: 'ShortDash', // 机器识别使用虚线
                    zIndex: 3,
                    marker: {
                      enabled: false
                    },
                    states: {
                      hover: {
                        lineWidthPlus: 0
                      }
                    },
                    enableMouseTracking: false
                  };
                  series.push(errorSeries);
                }
              });
            }
          });
        }
      });
    }
  });

  // 创建 Highcharts 图表
  Highcharts.chart('combined-chart', {
    chart: {
      type: 'line',
      zoomType: 'xy',
      panning: true,
      panKey: 'shift',
      animation: false,
      events: {
        selection: function(event) {
          if (event.resetSelection) {
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
          } else if (event.xAxis) {
            // 获取选择的范围
            const newXDomain = [event.xAxis[0].min, event.xAxis[0].max];
            const newYDomain = [event.yAxis[0].max, event.yAxis[0].min]; // 注意 y 轴是反转的

            // 更新全局域
            xDomains.value.global = newXDomain;
            // 更新存储的 Y 轴范围
            originalDomains.value.global = {
              x: newXDomain,
              y: newYDomain
            };

            // 重新绘制图表
            drawCombinedChart();

            // 重新绘制高亮区域
            selectedChannels.value.forEach((channel) => {
              const channelMatchedResults = matchedResults.value.filter(
                (r) => r.channel_name === channel.channel_name
              );
              if (channelMatchedResults.length > 0) {
                drawHighlightRects(channel.channel_name, channelMatchedResults);
              }
            });
          }
          return false; // 阻止默认缩放行为
        }
      }
    },
    title: {
      text: null
    },
    xAxis: {
      min: xExtent[0],
      max: xExtent[1],
      title: {
        text: 'Time(s)',
        style: {
          fontSize: '1.4em',
          fontWeight: 'bold'
        }
      },
      gridLineWidth: 1,
      gridLineDashStyle: 'ShortDash',
      gridLineColor: '#ccc',
      labels: {
        style: {
          fontSize: '1.2em',
          fontWeight: 'bold'
        }
      }
    },
    yAxis: {
      min: yMin,
      max: yMax,
      title: {
        text: 'normalization',
        style: {
          fontSize: '1.4em',
          fontWeight: 'bold'
        }
      },
      gridLineWidth: 1,
      gridLineDashStyle: 'ShortDash',
      gridLineColor: '#ccc',
      labels: {
        style: {
          fontSize: '1em',
          fontWeight: 'bold'
        },
        formatter: function() {
          return (this.value >= -1 && this.value <= 1) ? this.value : '';
        }
      }
    },
    tooltip: {
      enabled: false
    },
    legend: {
      enabled: false
    },
    plotOptions: {
      series: {
        animation: false,
        states: {
          inactive: {
            opacity: 1
          }
        }
      }
    },
    credits: {
      enabled: false
    },
    series: series,
    exporting: {
      enabled: false
    }
  });

  // 绘制高亮区域
  selectedChannels.value.forEach((channel) => {
    const channelMatchedResults = matchedResults.value.filter(
      (r) => r.channel_name === channel.channel_name
    );
    if (channelMatchedResults.length > 0) {
      drawHighlightRects(channel.channel_name, channelMatchedResults);
    }
  });
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
      const yValues = processedData.processedData.Y_value;
      const yAbsMax = Math.max(...yValues.map(d => Math.abs(d)));
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

// 计算图表高度的函数
const calculateChartHeight = () => {
  // 获取视窗高度
  const viewportHeight = window.innerHeight;
  // 总览条高度，从OverviewBrush.vue可知约为110px
  const overviewBrushHeight = 200;
  // 为页面其他元素预留空间（头部、边距等）
  const otherElementsHeight = 280; // 根据实际情况调整
  
  // 计算图表可用高度，确保留出足够空间给总览条
  const availableHeight = viewportHeight - otherElementsHeight - overviewBrushHeight;
  
  // 设置图表高度，减去上下边距
  mainChartDimensions.value.height = Math.max(300, availableHeight) - mainChartDimensions.value.margin.top - mainChartDimensions.value.margin.bottom;
};

// 添加窗口大小变化的处理函数
const handleResize = debounce(() => {
  // 重新计算图表高度
  calculateChartHeight();
  
  const container = document.querySelector('.chart-container');
  if (container) {
    const containerWidth = container.offsetWidth;
    mainChartDimensions.value.width = containerWidth - mainChartDimensions.value.margin.left - mainChartDimensions.value.margin.right;
  }
  
  if (channelsData.value && channelsData.value.length > 0) {
    // 获取当前图表实例
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (chart) {
      chart.reflow(); // 让 Highcharts 自动调整大小
    } else {
      drawCombinedChart(); // 如果图表不存在，重新绘制
    }
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
  height: 100%;
}

.chart-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  height: 100%;
  position: relative;
}

#combined-chart {
  width: 100%;
  height: 100%;
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
