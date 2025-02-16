<template>
  <div class="chart-container">
    <div v-if="selectedChannels.length === 0">
      <el-empty description="请选择通道" style="margin-top: 15vh;" />
    </div>
    <div v-else>
      <div class="chart-wrapper" v-for="(channel, index) in selectedChannels"
        :key="channel.channel_name + '_' + channel.shot_number">
        <div v-if="loadingStates[channel.channel_name + '_' + channel.shot_number] !== 100 ||
          renderingStates[channel.channel_name + '_' + channel.shot_number] !== 100" class="progress-wrapper">
          <div class="progress-title">
            <span>{{ `${channel.channel_name}#${channel.shot_number}` }} - {{ loadingStates[channel.channel_name + '_' +
              channel.shot_number] === 100 ? '图表渲染中' : '数据加载中' }}</span>
            <span class="progress-percentage">{{
              getProgressPercentage(channel.channel_name + '_' + channel.shot_number) }}%</span>
          </div>
          <el-progress :percentage="getProgressPercentage(channel.channel_name + '_' + channel.shot_number)"
            :stroke-width="10"
            :status="loadingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? '' : 'warning'"
            :color="loadingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? '#409EFF' : ''" />
        </div>
        <svg :id="'chart-' + channel.channel_name + '_' + channel.shot_number"
          :ref="el => channelSvgElementsRefs[index] = el" :style="{
            opacity: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 1 : 0,
            transition: 'opacity 0.5s ease'
          }"></svg>
        <div class="color-picker-container" :style="{
          opacity: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 1 : 0,
          visibility: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 'visible' : 'hidden',
          transition: 'opacity 0.5s ease'
        }" v-show="renderingStates[channel.channel_name + '_' + channel.shot_number] === 100">
          <ChannelColorPicker :color="channel.color" :predefineColors="predefineColors"
            @change="updateChannelColor(channel)" @update:color="channel.color = $event"
            :channelName="channel.channel_name" :shotNumber="channel.shot_number" />
        </div>
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
    <el-dialog v-if="showAnomalyForm && currentAnomaly.channelName" v-model="showAnomalyForm" title="编辑/修改异常信息">
      <el-form :model="currentAnomaly" label-width="auto">
        <el-form-item label="通道名">
          <el-input v-model="currentAnomaly.channelName" disabled />
        </el-form-item>
        <el-form-item label="异常类别">
          <el-input v-model="currentAnomaly.anomalyCategory" />
        </el-form-item>
        <el-form-item label="异常诊断名称">
          <el-input v-model="currentAnomaly.anomalyDiagnosisName" />
        </el-form-item>
        <el-form-item label="时间轴范围">
          <el-input :value="timeAxisRange" disabled />
        </el-form-item>
        <el-form-item label="异常描述">
          <el-input v-model="currentAnomaly.anomalyDescription" :rows="4" type="textarea" />
        </el-form-item>
      </el-form>
      <span slot="footer" class="dialog-footer">
        <el-button @click="closeAnomalyForm">取消</el-button>
        <el-button type="primary" @click="saveAnomaly">保存</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script setup>
import * as d3 from 'd3';
import debounce from 'lodash/debounce';
import ChannelColorPicker from '@/components/ChannelColorPicker.vue';
import { ref, reactive, watch, computed, onMounted, nextTick, onUnmounted, toRaw } from 'vue';
import { ElDialog, ElForm, ElFormItem, ElInput, ElButton, ElMessage } from 'element-plus';
import { useStore } from 'vuex';
import chartWorkerManager from '@/workers/chartWorkerManager';

const currentAnomaly = reactive({});
const showAnomalyForm = ref(false);
const overviewData = ref([]);
const xDomains = ref({ global: null });
const brush_begin = ref(0);
const brush_end = ref(0);
const predefineColors = ref(['#000000', '#4169E1', '#DC143C', '#228B22', '#FF8C00', '#800080', '#FF1493', '#40E0D0', '#FFD700', '#8B4513', '#2F4F4F', '#1E90FF', '#32CD32', '#FF6347', '#DA70D6', '#191970', '#FA8072', '#6B8E23', '#6A5ACD', '#FF7F50', '#4682B4']);
const store = useStore();
const selectedChannels = computed(() => store.state.selectedChannels);
const sampling = computed(() => store.state.sampling);
const smoothnessValue = computed(() => store.state.smoothness);
const sampleRate = ref(store.state.sampling);
const channelSvgElementsRefs = computed(() => store.state.channelSvgElementsRefs);
const isBoxSelect = computed(() => store.state.isBoxSelect);
const domains = computed(() => ({
  x: store.state.xDomains,
  y: store.state.yDomains
}));
const chartContainerWidth = ref(0);
const brushSelections = ref({ overview: null });
const matchedResults = computed(() => store.state.matchedResults);
const overviewBrushInstance = ref(null);
const overviewXScale = ref(null);
const updatingBrush = ref(false);
const channelDataCache = computed(() => store.state.channelDataCache);// 定义缓存对象
const loadingStates = reactive({});  // 用于存储每个通道的加载状态
const renderingStates = reactive({}); // 用于存储每个通道的渲染状态

// 添加一个变量来保存上一次的状态
const previousAnomalies = ref({});

const timeAxisRange = computed(() => {
  if (
    currentAnomaly &&
    currentAnomaly.startX !== undefined &&
    currentAnomaly.endX !== undefined
  ) {
    return `${currentAnomaly.startX.toFixed(3)} - ${currentAnomaly.endX.toFixed(3)}`;
  }
  return '';
});

// 修改监听函数
watch(() => store.state.anomalies, (newAnomalies) => {
  // 获取原始对象
  const rawNewAnomalies = toRaw(newAnomalies);
  const rawPreviousAnomalies = toRaw(previousAnomalies.value);

  // 遍历所有通道
  Object.keys(rawPreviousAnomalies).forEach(channelName => {
    const previousChannelAnomalies = rawPreviousAnomalies[channelName] || [];
    const newChannelAnomalies = rawNewAnomalies[channelName] || [];

    // 找出被删除的异常
    const deletedAnomalies = previousChannelAnomalies.filter(prevAnomaly => {
      const stillExists = newChannelAnomalies.some(newAnomaly => 
        newAnomaly.id === prevAnomaly.id
      );
      return !stillExists;
    });

    // 删除对应的 SVG 元素
    deletedAnomalies.forEach(anomaly => {
      
      // 如果正在编辑被删除的异常，关闭编辑表单
      if (showAnomalyForm.value && currentAnomaly.id === anomaly.id) {
        showAnomalyForm.value = false;
        Object.keys(currentAnomaly).forEach(key => {
          delete currentAnomaly[key];
        });
      }
      // 立即删除相关的 SVG 元素
      nextTick(() => {
        try {
          // 使用正确的选择器格式
          const selectors = [
            `.anomaly-rect-${anomaly.id}`,
            `.anomaly-group-${anomaly.id}`,
            `.anomaly-labels-group-${anomaly.id}`,
            `.anomaly-line-${anomaly.id}`,
            `.left-handle-${anomaly.id}`,
            `.right-handle-${anomaly.id}`,
            `.anomaly-buttons-${anomaly.id}`,
            `.left-label-${anomaly.id}`,
            `.right-label-${anomaly.id}`
          ];
          // 对每个通道的图表进行处理
          selectedChannels.value.forEach(channel => {
            const chartId = `#chart-${channel.channel_name}_${channel.shot_number}`;
            
            selectors.forEach(selector => {
              const element = d3.select(chartId).select(selector);
              if (element.node()) {
                element.remove();
              }
            });
          });
        } catch (error) {
          console.error('Error removing SVG elements:', error);
        }
      });
    });
  });

  // 更新上一次的状态
  previousAnomalies.value = JSON.parse(JSON.stringify(rawNewAnomalies));

  // 如果当前正在编辑的异常还存在，更新其数据
  if (showAnomalyForm.value && currentAnomaly.id) {
    const storedAnomalies = store.getters.getAnomaliesByChannel(currentAnomaly.channelName);
    const storedAnomaly = storedAnomalies?.find(a => a.id === currentAnomaly.id);
    
    if (storedAnomaly) {
      Object.assign(currentAnomaly, storedAnomaly);
    } else {
      // 如果找不到正在编辑的异常，说明它已被删除，关闭编辑表单
      showAnomalyForm.value = false;
      Object.keys(currentAnomaly).forEach(key => {
        delete currentAnomaly[key];
      });
    }
  }
}, { deep: true });

const updateChannelColor = (channel) => {
  // 更新 store 中的颜色
  store.commit('updateChannelColor', { channel_key: channel.channel_key, color: channel.color });
  const channelKey = `${channel.channel_name}_${channel.shot_number}`;
  // 更新主图表中的线条颜色
  const svg = d3.select(`#chart-${channelKey}`);
  if (svg.node()) {
    // 更新原始线条颜色
    svg.select('.original-line')
      .attr('stroke', channel.color);
    svg.select('.smoothed-line')
      .attr('stroke', channel.color);

    // 更新图例文本颜色
    svg.select('.legend-group text')
      .style('fill', channel.color);
  }
  // 更新概览图中的线条颜色
  const overviewSvg = d3.select('#overview-chart');
  if (overviewSvg.node()) {
    overviewSvg.selectAll('.overview-line')
      .filter(d => d.channelName === channelKey)
      .attr('stroke', channel.color);
  }
  // 更新 overviewData 中的颜色
  const existingIndex = overviewData.value.findIndex(d => d.channelName === channelKey);
  if (existingIndex !== -1) {
    overviewData.value[existingIndex].color = channel.color;
  }
};

// 添加Worker消息处理
chartWorkerManager.onmessage = function (e) {
  const { type, data, error } = e.data;

  if (error) {
    console.error('Worker error:', error);
    ElMessage.error(`数据处理错误: ${error}`);
    return;
  }

  switch (type) {
    case 'processedData': {
      try {
        const { processedData, channelKey, color, xUnit, yUnit, channelType, channelNumber, shotNumber } = data;

        // 验证处理后的数据
        if (!processedData || !processedData.X_value || !processedData.Y_value) {
          console.warn(`Invalid processed data for channel ${channelKey}`);
          return;
        }

        // 更新处理后的数据到overviewData
        if (processedData.X_value.length > 0 && processedData.Y_value.length > 0) {
          const existingIndex = overviewData.value.findIndex(d => d.channelName === channelKey);
          if (existingIndex !== -1) {
            overviewData.value[existingIndex] = {
              channelName: channelKey,
              X_value: processedData.X_value,
              Y_value: processedData.Y_value,
              color: color,
            };
          } else {
            overviewData.value.push({
              channelName: channelKey,
              X_value: processedData.X_value,
              Y_value: processedData.Y_value,
              color: color,
            });
          }
        }

        renderingStates[channelKey] = 75; // 更新渲染状态
        nextTick(() => {
          drawChart(processedData, [], channelKey, color, xUnit, yUnit, channelType, channelNumber, shotNumber)
            .then(() => {
              renderingStates[channelKey] = 100;
            })
            .catch(error => {
              console.error(`Error drawing chart for ${channelKey}:`, error);
              renderingStates[channelKey] = 100;
            });
        });
      } catch (error) {
        console.error('Error processing worker message:', error);
        renderingStates[channelKey] = 100;
      }
      break;
    }
    case 'processedErrorData': {
      const { channelKey, processedErrors } = data;
      if (!processedErrors || processedErrors.length === 0) return;

      // 获取当前图表的实例
      const svg = d3.select(`#chart-${channelKey}`);
      if (!svg.node()) return;

      // 更新错误数据显示
      processedErrors.forEach(error => {
        error.segments.forEach(segment => {
          // 绘制错误数据
          const errorLine = d3.line()
            .x(d => x(d))
            .y((d, i) => y(segment.Y[i]))
            .curve(d3.curveMonotoneX);

          svg.select('g')
            .append('path')
            .datum(segment.X)
            .attr('class', 'error-line')
            .attr('fill', 'none')
            .attr('stroke', error.color)
            .attr('stroke-width', 2)
            .attr('opacity', 0.8)
            .attr('transform', `translate(0,${error.person === 'machine' ? 6 : -6})`)
            .attr('d', errorLine)
            .attr('stroke-dasharray', error.person === 'machine' ? '5, 5' : null);
        });
      });
      break;
    }
  }
};

onUnmounted(() => {
  chartWorkerManager.terminate();
});

const processChannelData = async (data, channel) => {
  const channelKey = `${channel.channel_name}_${channel.shot_number}`;
  try {
    renderingStates[channelKey] = 0;
    // 准备数据
    const channelData = {
      X_value: [...data.X_value],
      Y_value: [...data.Y_value],
      originalFrequency: data.originalFrequency,
      originalDataPoints: data.X_value.length
    };
    renderingStates[channelKey] = 25;
    let errorDataResults = [];
    if (channel.errors && channel.errors.length > 0) {
      try {
        errorDataResults = await store.dispatch('fetchAllErrorData', channel);
      } catch (err) {
        console.warn('Failed to fetch error data:', err);
      }
    }
    renderingStates[channelKey] = 40;

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
      if (processedData.processedData.X_value.length > 0 && processedData.processedData.Y_value.length > 0) {
        const existingIndex = overviewData.value.findIndex(d => d.channelName === channelKey);
        if (existingIndex !== -1) {
          overviewData.value[existingIndex] = {
            channelName: channelKey,
            X_value: processedData.processedData.X_value,
            Y_value: processedData.processedData.Y_value,
            color: processedData.color,
          };
        } else {
          overviewData.value.push({
            channelName: channelKey,
            X_value: processedData.processedData.X_value,
            Y_value: processedData.processedData.Y_value,
            color: processedData.color,
          });
        }
      }

      // 更新 channelDataCache
      store.commit('updateChannelDataCache', {
        channelKey: channelKey, // 修正参数名称
        data: {
          ...processedData.processedData,
          errorsData: errorDataResults  // 添加错误数据到缓存
        }
      });

      renderingStates[channelKey] = 0;

      // 计算并更新全局 X 轴范围
      const allX = overviewData.value.flatMap(d => d.X_value);
      const xExtent = d3.extent(allX);
      // 更新所有通道的 domain
      selectedChannels.value.forEach((ch) => {
        const chKey = `${ch.channel_name}_${ch.shot_number}`;
        store.dispatch('updateDomains', {
          channelName: chKey,
          xDomain: xExtent,
          yDomain: domains.value.y[chKey]
        });

        // 如果不是当前正在处理的通道,则重新渲染该通道
        if (chKey !== channelKey) {
          const data = channelDataCache.value[chKey];
          if (data) {
            nextTick(() => {
              drawChart(data, data.errorsData, chKey, ch.color,
                data.X_unit, data.Y_unit, data.channel_type,
                data.channel_number, ch.shot_number)
                .catch(error => {
                  console.error(`Error redrawing chart for ${chKey}:`, error);
                });
            });
          }
        }
      });

      renderingStates[channelKey] = 75; // 更新渲染状态
      nextTick(() => {
        drawChart(processedData.processedData, errorDataResults, channelKey, processedData.color,
          processedData.xUnit, processedData.yUnit, processedData.channelType,
          processedData.channelNumber, processedData.shotNumber)
          .then(() => {
            renderingStates[channelKey] = 100;
          })
          .catch(error => {
            console.error(`Error drawing chart for ${channelKey}:`, error);
            renderingStates[channelKey] = 100;
          });
      });
    }

  } catch (error) {
    console.error(`Error processing channel data for ${channel.channel_name}:`, error);
    ElMessage.error(`处理通道数据错误: ${error.message}`);
    renderingStates[channelKey] = 100; // 确保错误时也更新状态
  }
};

// 专门负责数据获取的函数
const fetchChannelData = async (channel) => {
  try {
    if (!channel || !channel.channel_name || !channel.shot_number) {
      console.warn('Invalid channel data:', channel);
      return null;
    }

    const channelKey = `${channel.channel_name}_${channel.shot_number}`;

    // 初始化加载状态
    loadingStates[channelKey] = Number(0);

    const progressInterval = setInterval(() => {
      if (loadingStates[channelKey] < 90) {
        loadingStates[channelKey] = Math.min(Number(loadingStates[channelKey]) + 10, 90);
      }
    }, 100);

    try {
      // 使用 store action 获取数据
      const data = await store.dispatch('fetchChannelData', { channel });

      clearInterval(progressInterval);
      loadingStates[channelKey] = Number(100);

      return data;
    } catch (error) {
      clearInterval(progressInterval);
      console.error('Error fetching channel data:', error);
      loadingStates[channelKey] = Number(100);
      ElMessage.error(`加载通道 ${channelKey} 数据失败: ${error.message}`);
      return null;
    }
  } catch (error) {
    console.error('Error in fetchChannelData:', error);
    return null;
  }
};

// 专门负责绘制图表的函数
const drawChannelChart = async (channel, data) => {
  try {
    if (!data) return;

    const channelKey = `${channel.channel_name}_${channel.shot_number}`;
    renderingStates[channelKey] = 0; // 重置渲染状态

    await processChannelData(data, channel);
  } catch (error) {
    console.error('Error in drawChannelChart:', error);
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;
    renderingStates[channelKey] = 100;
    ElMessage.error(`绘制通道 ${channelKey} 图表失败: ${error.message}`);
  }
};

const renderCharts = debounce(async () => {
  try {
    performance.mark('Total Render Time-start');
    overviewData.value = [];

    // 确保有选中的通道
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      console.warn('No channels selected');
      return;
    }
    // 先获取所有需要的数据
    const fetchPromises = selectedChannels.value.map(channel => fetchChannelData(channel));
    const channelsData = await Promise.all(fetchPromises);

    // 过滤掉无效的数据
    const validChannelsData = channelsData.filter(data => data !== null);
    if (validChannelsData.length === 0) {
      console.warn('No valid channel data fetched');
      return;
    }

    // 然后绘制所有图表
    for (let i = 0; i < selectedChannels.value.length; i++) {
      const channel = selectedChannels.value[i];
      const data = channelsData[i];
      if (data) {
        try {
          await processChannelData(data, channel);
        } catch (error) {
          console.error(`Error processing channel ${channel.channel_name}:`, error);
          continue;
        }
      }
    }

    // 等待所有数据处理完成
    await new Promise(resolve => setTimeout(resolve, 100));

    // 验证是否有有效数据
    if (overviewData.value.length === 0) {
      console.warn('No valid data collected for overview');
      return;
    }

    // 只有在有数据时才绘制概览图
    drawOverviewChart();

    performance.mark('Total Render Time-end');
    performance.measure('Total Render Time',
      'Total Render Time-start',
      'Total Render Time-end');

    window.dataLoaded = true;
  } catch (error) {
    console.error('Error in renderCharts:', error);
    ElMessage.error(`渲染图表错误: ${error.message}`);
  }
}, 200);

// 修改 selectedChannels 的 watch
watch(selectedChannels, async (newChannels, oldChannels) => {
  // 避免不必要的深度比较
  const hasStructuralChanges = newChannels.length !== oldChannels.length ||
    newChannels.some((newCh, index) => {
      const oldCh = oldChannels[index];
      return newCh.channel_key !== oldCh.channel_key;
    });

  const hasColorChanges = !hasStructuralChanges &&
    newChannels.some((newCh, index) => {
      const oldCh = oldChannels[index];
      return newCh.color !== oldCh.color;
    });

  const hasErrorChanges = !hasStructuralChanges &&
    newChannels.some((newCh, index) => {
      const oldCh = oldChannels[index];
      return JSON.stringify(newCh.errors) !== JSON.stringify(oldCh.errors);
    });

  try {
    if (hasStructuralChanges) {
      // 通道结构发生变化，需要完全重绘
      overviewData.value = [];
      await nextTick();
      if (newChannels && newChannels.length > 0) {
        await renderCharts();
        if (overviewData.value && overviewData.value.length > 0) {
          drawOverviewChart();
        }
      }
    } else if (hasColorChanges || hasErrorChanges) {
      // 只有颜色或错误数据变化，只更新受影响的图表
      for (const channel of newChannels) {
        const data = channelDataCache.value[`${channel.channel_name}_${channel.shot_number}`];
        if (data) {
          await drawChannelChart(channel, data);
        }
      }
    }
  } catch (error) {
    console.error('Error in selectedChannels watch:', error);
  }
}, { deep: true });

// 优化采样和平滑度的监听器
const debouncedRenderCharts = debounce(renderCharts, 300);

watch([sampling, smoothnessValue], ([newSampling, newSmoothness], [oldSampling, oldSmoothness]) => {
  if (newSampling !== oldSampling) {
    sampleRate.value = newSampling;
  }
  debouncedRenderCharts();
});

// 添加窗口大小变化的处理函数
const handleResize = debounce(() => {
  if (overviewData.value && overviewData.value.length > 0) {
    drawOverviewChart();
  }
}, 200);

// 在组件挂载时添加监听器
onMounted(async () => {
  try {
    const container = document.querySelector('.chart-container');
    if (container) {
      chartContainerWidth.value = container.offsetWidth;
    }

    // 确保 selectedChannels 有且 overviewData 已初始化后再绘制
    if (selectedChannels.value && selectedChannels.value.length > 0) {
      await renderCharts();
      // 只有在有数据时才绘制概览图
      if (overviewData.value && overviewData.value.length > 0) {
        drawOverviewChart();
      }
    }

    window.addEventListener('resize', handleResize);
  } catch (error) {
    console.error('Error in mounted hook:', error);
  }
});

// 在组件卸载时移除监听器
onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});

watch(sampling, () => {
  sampleRate.value = sampling.value;
  renderCharts();
});

watch(smoothnessValue, () => {
  renderCharts();
});

const drawHighlightRects = (channelName, results) => {
  const svg = d3.select(`#chart-${channelName}`);
  if (!svg.node()) return;

  const margin = { top: 20, right: 30, bottom: 50, left: 65 };
  const width = svg.node().getBoundingClientRect().width - margin.left - margin.right;
  const height = 230 - margin.top - margin.bottom;

  // 获取当前图表的x比例尺
  const x = d3.scaleLinear()
    .domain(domains.value.x[channelName] || [-2, 6])
    .range([0, width]);

  // 获取当前通道的数据并进行采样和平处理
  const channelData = channelDataCache.value[channelName];
  if (!channelData) return;

  // 进行采样
  const samplingInterval = Math.floor(1 / sampling.value);
  const sampledData = {
    X_value: channelData.X_value.filter((_, i) => i % samplingInterval === 0),
    Y_value: channelData.Y_value.filter((_, i) => i % samplingInterval === 0)
  };

  // 应用滑理
  let smoothedYValue = sampledData.Y_value;
  if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
    smoothedYValue = interpolateData(sampledData.Y_value, smoothnessValue.value);
  }

  // 使用与绘制曲线相同的 Y 轴范围
  const yExtent = d3.extent(smoothedYValue);
  const yRangePadding = (yExtent[1] - yExtent[0]) * 0.2;
  const yMin = yExtent[0] - yRangePadding;
  const yMax = yExtent[1] + yRangePadding;

  // 创建与主图表相同的y比例尺
  const y = d3.scaleLinear()
    .domain([yMin, yMax])
    .range([height, 0]);

  // 移除之前的高亮区域
  svg.select(`.highlight-group-${channelName}`).remove();

  // 创建新的高亮区域
  const highlightGroup = svg.select('g')
    .append('g')
    .attr('class', `highlight-group-${channelName}`);

  // 获取时间边界值约束
  const timeBegin = store.state.time_begin;
  const timeEnd = store.state.time_end;
  const timeDuring = store.state.time_during;
  const upperBound = store.state.upper_bound;
  const lowerBound = store.state.lower_bound;
  const scopeBound = store.state.scope_bound;

  // 为每个匹配结果创建高亮矩形
  results.forEach(result => {
    if (result.confidence > 0.75) {
      const [startX, endX] = result.range;

      // 1. 时间范围过滤
      if (startX < timeBegin || endX > timeEnd) {
        return;
      }

      // 2. 持续时间过滤
      const duration = endX - startX;
      if (duration < timeDuring) {
        return;
      }

      // 使用平滑后的数据获取区间内的值
      const startIndex = sampledData.X_value.findIndex(x => x >= startX);
      const endIndex = sampledData.X_value.findIndex(x => x > endX);
      const rangeData = {
        X: sampledData.X_value.slice(startIndex, endIndex),
        Y: smoothedYValue.slice(startIndex, endIndex)
      };

      if (rangeData.Y.length === 0) return;

      const minY = Math.min(...rangeData.Y);
      const maxY = Math.max(...rangeData.Y);

      // Y值范围和幅度过滤保持不变
      if (minY < lowerBound || maxY > upperBound) return;
      const yRange = Math.abs(maxY - minY);
      if (yRange < scopeBound) return;

      // 修改 padding 为范围的 5%
      const padding = yRange * 0.05 + 0.2;
      const rectY = y(maxY + padding);
      const rectHeight = y(minY - padding) - y(maxY + padding);

      highlightGroup.append('rect')
        .attr('x', x(startX))
        .attr('y', rectY)
        .attr('width', x(endX) - x(startX))
        .attr('height', rectHeight)
        .attr('fill', 'rgba(255, 165, 0, 0.2)')
        .attr('stroke', 'rgba(255, 140, 0, 0.8)')
        .attr('stroke-width', 2)
        .attr('opacity', result.confidence)
        .style('filter', 'drop-shadow(2px 2px 2px rgba(0,0,0,0.2))')
        .on('mouseover', function (event) {
          const tooltip = d3.select('body')
            .append('div')
            .attr('class', 'custom-tooltip')
            .style('position', 'absolute')
            .style('background-color', 'rgba(50, 50, 50, 0.9)')
            .style('color', 'white')
            .style('padding', '8px 12px')
            .style('border-radius', '4px')
            .style('font-size', '12px')
            .style('box-shadow', '0 2px 12px 0 rgba(0,0,0,0.3)')
            .style('z-index', 9999)
            .style('pointer-events', 'none')
            .style('transition', 'opacity 0.3s');

          tooltip.html(
            `<div style="border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 4px; margin-bottom: 4px;">
                            <span style="color: #67C23A;">置信度:</span> ${(result.confidence * 100).toFixed(2)}%
                        </div>
                        <div style="border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 4px; margin-bottom: 4px;">
                            <span style="color: #E6A23C;">持续时间:</span> ${duration.toFixed(3)}
                        </div>
                        <div style="border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 4px; margin-bottom: 4px;">
                            <span style="color: #409EFF;">Y值范围:</span> ${minY.toFixed(3)} - ${maxY.toFixed(3)}
                        </div>
                        <div>
                            <span style="color: #F56C6C;">Y值幅度:</span> ${yRange.toFixed(3)}
                        </div>`
          );

          // 设提示框位置
          const tooltipWidth = tooltip.node().getBoundingClientRect().width;
          const tooltipHeight = tooltip.node().getBoundingClientRect().height;
          const mouseX = event.pageX;
          const mouseY = event.pageY;

          tooltip
            .style('left', `${mouseX - tooltipWidth / 2}px`)
            .style('top', `${mouseY - tooltipHeight - 10}px`);
        })
        .on('mouseout', function () {
          d3.selectAll('.custom-tooltip').remove();
        });
    }
  });
};

// 绘制概览图表
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
      `0 0 ${svgWidth} ${height + margin.top + margin.bottom}`
    )
    .attr('preserveAspectRatio', 'xMidYMid meet');

  const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

  // 计算所有数据的范围
  const allX = overviewData.value.flatMap((d) => d.X_value);
  const allY = overviewData.value.flatMap((d) => d.Y_value);
  const xExtent = d3.extent(allX);
  const yExtent = d3.extent(allY);

  // 更新所有通道的 domain
  selectedChannels.value.forEach((channel) => {
    const channelName = `${channel.channel_name}_${channel.shot_number}`;
    store.dispatch('updateDomains', {
      channelName,
      xDomain: xExtent,
      yDomain: domains.value.y[channelName]
    });

    // 重新渲染每个通道的图表以更新显示范围
    const data = channelDataCache.value[channelName];
    if (data) {
      nextTick(() => {
        drawChannelChart(channel, data);
      });
    }
  });

  // 更新 brush_begin 和 brush_end 到当前数据范围
  updatingBrush.value = true;
  brush_begin.value = xExtent[0].toFixed(4);
  brush_end.value = xExtent[1].toFixed(4);
  store.commit("updatebrush", { begin: brush_begin.value, end: brush_end.value });
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
    .call(d3.axisBottom(x))
    .style("font-size", "1em")
    .style("font-weight", "bold");

  // 添加刷子功能
  const brush = d3.brushX()
    .extent([
      [0, 0],
      [width, height]
    ])
    .on('brush', brushed)
    .on('end', brushed);

  overviewBrushInstance.value = brush;

  const brushG = g.append('g').attr('class', 'brush').call(brush);

  // 设置初始刷选范围为当前数据范围
  const initialSelection = xExtent.map(x);
  brushG.call(brush.move, initialSelection);
  brushSelections.value.overview = initialSelection;

  function brushed(event) {
    if (updatingBrush.value) return;

    // 当点击空白处时，恢复到完整范围
    const selection = event.selection || initialSelection;
    const newDomain = selection.map(x.invert, x);

    updatingBrush.value = true;
    brush_begin.value = newDomain[0].toFixed(4);
    brush_end.value = newDomain[1].toFixed(4);
    store.commit("updatebrush", { begin: brush_begin.value, end: brush_end.value });
    updatingBrush.value = false;

    // 如果是点击空白处，手动设置刷选框
    if (!event.selection) {
      brushG.call(brush.move, initialSelection);
      brushSelections.value.overview = initialSelection;
    } else {
      brushSelections.value.overview = selection;
    }

    // 更新所有图表的 domain
    selectedChannels.value.forEach((channel) => {
      const channelName = `${channel.channel_name}_${channel.shot_number}`;
      store.dispatch('updateDomains', {
        channelName,
        xDomain: newDomain,
        yDomain: domains.value.y[channelName]
      });
    });

    // 重新渲染所有通道图表
    selectedChannels.value.forEach((channel) => {
      const data = channelDataCache.value[`${channel.channel_name}_${channel.shot_number}`];
      if (data) {
        drawChannelChart(channel, data);
      }
    });
  }
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

  // 更新刷选区域
  const selection = [x(start), x(end)];
  updatingBrush.value = true;
  d3.select('#overview-chart').select('.brush').call(brush.move, selection);
  updatingBrush.value = false;

  // 更新图表
  selectedChannels.value.forEach((channel) => {
    const channelName = `${channel.channel_name}_${channel.shot_number}`;
    xDomains.value[channelName] = [start, end];
  });

  // 重新渲染图表
  selectedChannels.value.forEach((channel) => {
    const data = channelDataCache.value[`${channel.channel_name}_${channel.shot_number}`];
    if (data) {
      drawChannelChart(channel, data);
    }
  });
};

// 修改 watch 函数，添加对 brush_begin 和 brush_end 的监听
watch([brush_begin, brush_end], ([newBegin, newEnd]) => {
  if (updatingBrush.value) return;
  if (!selectedChannels.value || selectedChannels.value.length === 0) return;

  const start = parseFloat(newBegin);
  const end = parseFloat(newEnd);

  if (isNaN(start) || isNaN(end)) return;

  // 更新所有通道的 domain
  selectedChannels.value.forEach((channel) => {
    const channelName = `${channel.channel_name}_${channel.shot_number}`;
    store.dispatch('updateDomains', {
      channelName,
      xDomain: [start, end],
      yDomain: domains.value.y[channelName]
    });

    // 重新渲染该通道的图表
    const data = channelDataCache.value[channelName];
    if (data) {
      nextTick(() => {
        drawChannelChart(channel, data);
      });
    }
  });
}, { immediate: true });

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

// 应斯滑
const gaussianSmooth = (data, sigma) => {
  const kernelSize = Math.ceil(sigma * 6); // 核大小（通常为 6 * sigma）
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
    return data; // 不平直接返回
  }

  const sigma = t * 20; // 根据 t 调整平滑强度
  return gaussianSmooth(data, sigma);
};

const originalDomains = ref({}); // 存储原始的显示范围

const drawChart = async (
  data,
  errorsData,
  channelName,
  color,
  xUnit,
  yUnit,
  channelType,
  channelNumber,
  shotNumber
) => {
  return new Promise((resolve, reject) => {
    try {
      // 添加防抖检查
      const chartKey = `${channelName}-${color}-${sampling.value}-${smoothnessValue.value}`;
      if (chartKey === drawChart.lastDrawnChart) {
        resolve();
        return;
      }
      drawChart.lastDrawnChart = chartKey;

      performance.mark(`Draw Chart ${channelName}-start`);

      const container = d3.select('.chart-container');
      const containerWidth = container.node().getBoundingClientRect().width;

      const svg = d3.select(`#chart-${channelName}`);
      // 修改边距，增加底部空间
      const margin = { top: 15, right: 20, bottom: 50, left: 60 };

      const width = containerWidth - margin.left - margin.right;
      const height = 230 - margin.top - margin.bottom;

      svg.selectAll('*').remove();

      svg
        .attr(
          'viewBox',
          `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`
        )
        .attr('preserveAspectRatio', 'xMidYMid meet')
        .attr('width', '100%')
        .style('overflow', 'visible'); // 添加这行，允许内容超出 SVG 边界

      const yExtent = d3.extent(data.Y_value);
      const yRangePadding = (yExtent[1] - yExtent[0]) * 0.2;
      const yMin = yExtent[0] - yRangePadding;
      const yMax = yExtent[1] + yRangePadding;

      const x = d3
        .scaleLinear()
        .domain(domains.value.x[channelName])
        .range([0, width]);

      const y = d3.scaleLinear()
        .domain(domains.value.y[channelName] || [yMin, yMax])
        .range([height, 0]);

      let smoothedYValue = data.Y_value;
      if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
        smoothedYValue = interpolateData(data.Y_value, smoothnessValue.value);
      }

      const line = d3
        .line()
        .x((d, i) => x(data.X_value[i]))
        .y((d, i) => y(d))
        .curve(d3.curveMonotoneX);

      const g = svg
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

      g.append('defs')
        .append('clipPath')
        .attr('id', `clip-${channelName}`)
        .append('rect')
        .attr('width', width)
        .attr('height', height);

      const clipGroup = g
        .append('g')
        .attr('clip-path', `url(#clip-${channelName})`);

      // 修改横坐标标签
      g.append('g')
        .attr('class', 'x-axis')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(x))
        .selectAll("text")
        .style("font-size", "1.1em")
        .style("font-weight", "bold");

      // 添加统一的横坐标标签
      g.append('text')
        .attr('class', 'x-label')
        .attr('x', width / 2)
        .attr('y', height + 30)
        .attr('text-anchor', 'middle')
        .style('font-size', '1.1em')
        .style('font-weight', 'bold')
        .text('Time(s)');  // 移除了 (s)

      // 修改Y轴刻度
      g.append('g')
        .attr('class', 'y-axis')
        .call(d3.axisLeft(y).ticks(8))  // 设置Y轴刻度数量为4
        .style("font-size", "1em")
        .style("font-weight", "bold");

      // 修改网格线
      g.append('g')
        .attr('class', 'grid')
        .call(
          d3
            .axisLeft(y)
            .ticks(8)  // 保持与Y轴刻度数量一致
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
          d3
            .axisBottom(x)
            .tickSize(-height)
            .tickFormat('')
        )
        .selectAll('line')
        .style('stroke', '#ccc')
        .style('stroke-dasharray', '3,3');

      // 添加X轴单位标签
      svg
        .append('text')
        .attr('x', width + margin.left + 15)
        .attr('y', height + margin.top + 20)
        .attr('text-anchor', 'end')
        .style('font-size', '1.1em')
        .style('font-weight', 'bold')
        .attr('fill', '#000')
        .text('');  // 移除 xUnit，不显示单位

      // 添加Y轴单位标签
      svg
        .append('text')
        .attr('transform', `translate(${margin.left - 50}, ${margin.top + height / 2}) rotate(-90)`)
        .attr('text-anchor', 'middle')
        .style('font-size', '1.1em')
        .style('font-weight', 'bold')
        .attr('alignment-baseline', 'middle')
        .attr('fill', '#000')
        .text(yUnit);

      // 修改通道信息显示位置和样式，将其移动到右上角并与颜色选择器组合
      const legendGroup = g.append('g')
        .attr('class', 'legend-group')
        .attr('transform', `translate(${width - 280}, -10)`);  // 调整位置

      // 添加通道信息文本
      legendGroup.append('text')
        .attr('x', -60)
        .attr('y', 30)
        .attr('text-anchor', 'start')
        .style('font-size', '1.0em')
        .style('font-weight', 'bold')
        .style('fill', color || 'steelblue')  // 添加这行，使用与图表相同的颜色
        .text(`${channelNumber} | ${shotNumber} (${data.originalFrequency.toFixed(2)}KHz -> ${(sampling.value).toFixed(2)}KHz)`);

      // 绘制每个通道的主线
      clipGroup
        .append('path')
        .datum(data.Y_value)
        .attr('class', 'original-line')
        .attr('fill', 'none')
        .attr('stroke', color)  // 直接使用传入的颜色
        .attr('stroke-width', 1.5)
        .attr('opacity', smoothnessValue.value > 0 ? 0.3 : 1)
        .attr('d', line);

      // 处理错误数据
      if (errorsData) {

        // 遍历所有错误数据组
        errorsData.forEach(errorGroup => {
          // 解构每组中的人工标注和机器识别的错误数据
          const [manualErrors, machineErrors] = [errorGroup[0], errorGroup[1]];

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
                    clipGroup
                      .append('path')
                      .datum(errorPoints)
                      .attr('class', 'error-line')
                      .attr('fill', 'none')
                      .attr('stroke', error.color || 'rgba(220, 20, 60, 0.3)')
                      .attr('stroke-width', 10)
                      .attr('stroke-linecap', 'round')
                      .attr('stroke-linejoin', 'round')
                      .attr('opacity', 0.8)
                      .attr('d', d3.line()
                        .x(d => x(d.x))
                        .y(d => y(d.y))
                        .curve(d3.curveMonotoneX)
                      )
                      .style('vector-effect', 'non-scaling-stroke');
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
                    clipGroup
                      .append('path')
                      .datum(errorPoints)
                      .attr('class', 'error-line')
                      .attr('fill', 'none')
                      .attr('stroke', error.color || 'rgba(220, 20, 60, 0.3)')
                      .attr('stroke-width', 10)
                      .attr('stroke-linecap', 'round')
                      .attr('stroke-linejoin', 'round')
                      .attr('opacity', 0.8)
                      .attr('stroke-dasharray', '5, 5')
                      .attr('d', d3.line()
                        .x(d => x(d.x))
                        .y(d => y(d.y))
                        .curve(d3.curveMonotoneX)
                      )
                      .style('vector-effect', 'non-scaling-stroke');
                  }
                });
              }
            });
          }
        });
      }

      // 移除旧的错误数据处理代码，因为已经在上面处理过了
      if (errorsData && Array.isArray(errorsData)) {
        errorsData.forEach((errorData) => {
          if (errorData && errorData.X_value_error && Array.isArray(errorData.X_value_error)) {
            errorData.X_value_error.forEach((X_value_error, index) => {
              if (errorData.Y_value_error && Array.isArray(errorData.Y_value_error)) {
                const Y_value_error = errorData.Y_value_error[index];
                if (Y_value_error && Array.isArray(Y_value_error)) {
                  const errorLine = d3
                    .line()
                    .x((d, i) => x(X_value_error[i]))
                    .y((d, i) => y(d))
                    .curve(d3.curveMonotoneX);

                  const yOffset = errorData.person === 'machine' ? 6 : -6;
                  const isMachine = errorData.person === 'machine';

                  clipGroup
                    .append('path')
                    .datum(Y_value_error)
                    .attr('class', `error-line-${index}-${channelName}`)
                    .attr('fill', 'none')
                    .attr('stroke', errorData.color || 'rgba(0,0,0,0)')
                    .attr('stroke-width', 2)
                    .attr('opacity', 0.8)
                    .attr('transform', `translate(0,${yOffset})`)
                    .attr('d', errorLine)
                    .attr('stroke-dasharray', isMachine ? '5, 5' : null);
                }
              }
            });
          }
        });
      }

      if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
        clipGroup
          .append('path')
          .datum(smoothedYValue)
          .attr('class', 'smoothed-line')
          .attr('fill', 'none')
          .attr('stroke', color)  // 直接使用传入的颜色
          .attr('stroke-width', 1.5)
          .attr('d', line);
      }

      const selectionBrush = d3
        .brushX()
        .extent([
          [0, 0],
          [width, height],
        ])
        .on('end', selectionBrushed);

      const zoomBrush = d3
        .brush()
        .extent([
          [0, 0],
          [width, height],
        ])
        .on('end', zoomBrushed);

      // 创建两个不同的brush组
      const selectionBrushG = g.append('g')
        .attr('class', 'selection-brush')
        .style('display', isBoxSelect.value ? null : 'none')
        .call(selectionBrush);

      const zoomBrushG = g.append('g')
        .attr('class', 'zoom-brush')
        .style('display', isBoxSelect.value ? 'none' : null)
        .call(zoomBrush);

      // 创建anomaliesGroup
      const anomaliesGroup = g.append('g').attr('class', 'anomalies-group');

      // 加载已有的异常标注
      const channelAnomalies = store.getters.getAnomaliesByChannel(channelName);
      channelAnomalies.forEach((anomaly) => {
        drawAnomalyElements(anomaly, anomaliesGroup, true);
      });

      function selectionBrushed(event) {
        if (!event.sourceEvent) return;
        if (!event.selection) return;
        if (!isBoxSelect.value) return;

        const [x0, x1] = event.selection;
        const [startX, endX] = [x.invert(x0), x.invert(x1)];

        // 格式化当前时间
        const now = new Date();
        const formattedTime = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

        const anomaly = {
          id: `${store.state.person}_${Date.now()}`, // 添加时间戳确保ID唯一
          person: store.state.person,
          channelName: channelName,
          startX: startX,
          endX: endX,
          anomalyCategory: '',
          anomalyDiagnosisName: '',
          anomalyDescription: '',
          annotationTime: formattedTime,
          isStored: false  // 添加 isStored 字段,初始为 false
        };

        d3.select(this).call(selectionBrush.move, null);
        
        // 添加到store
        store.dispatch('addAnomaly', {
          channelName: channelName,
          anomaly: anomaly
        });
        
        // 绘制新标注
        drawAnomalyElements(anomaly, anomaliesGroup, false);
      }

      function zoomBrushed(event) {
        if (!event.sourceEvent) return;
        if (!event.selection) {
          // 点击空白处，恢复到 brush 总览条的范围
          if (brush_begin.value && brush_end.value) {
            const newXDomain = [parseFloat(brush_begin.value), parseFloat(brush_end.value)];
            store.dispatch('updateDomains', {
              channelName,
              xDomain: newXDomain,
              yDomain: originalDomains.value[channelName]?.y || y.domain()
            });
            const targetChannel = selectedChannels.value.find(ch => `${ch.channel_name}_${ch.shot_number}` === channelName);
            if (targetChannel) {
              const data = channelDataCache.value[`${targetChannel.channel_name}_${targetChannel.shot_number}`];
              if (data) {
                drawChannelChart(targetChannel, data);
              }
            }
          }
          return;
        }

        if (isBoxSelect.value) return;

        // 获取选择的范围
        const [[x0, y0], [x1, y1]] = event.selection;

        // 保存原始范围（如果还没有保存）
        if (!originalDomains.value[channelName]) {
          originalDomains.value[channelName] = {
            x: [parseFloat(brush_begin.value), parseFloat(brush_end.value)],
            y: y.domain()
          };
        }

        // 更新显示范围
        const newXDomain = [x.invert(x0), x.invert(x1)];
        const newYDomain = [y.invert(y1), y.invert(y0)];

        // 更新 store 中的范围
        store.dispatch('updateDomains', {
          channelName,
          xDomain: newXDomain,
          yDomain: newYDomain
        });

        // 清除选择
        d3.select(this).call(zoomBrush.move, null);

        // 重新绘制图表
        const targetChannel = selectedChannels.value.find(ch => `${ch.channel_name}_${ch.shot_number}` === channelName);
        if (targetChannel) {
          const data = channelDataCache.value[`${targetChannel.channel_name}_${targetChannel.shot_number}`];
          if (data) {
            drawChannelChart(targetChannel, data);
          }
        }
      }

      function drawAnomalyElements(anomaly, anomaliesGroup, isStored = false) {
        const anomalyGroup = anomaliesGroup
          .append('g')
          .attr('class', `anomaly-group-${anomaly.id}`); // 使用唯一ID

        const anomalyLabelsGroup = g
          .append('g')
          .attr('class', `anomaly-labels-group-${anomaly.id}`); // 使用唯一ID

        anomalyLabelsGroup
          .append('text')
          .attr('class', `left-label-${anomaly.id}`)
          .attr('x', x(anomaly.startX))
          .attr('y', -5)
          .style('font-size', '1em')
          .style('font-weight', 'bold')
          .attr('text-anchor', 'middle')
          .attr('fill', 'black')
          .text(anomaly.startX.toFixed(3));

        anomalyLabelsGroup
          .append('text')
          .attr('class', `right-label-${anomaly.id}`)
          .attr('x', x(anomaly.endX))
          .attr('y', -5)
          .style('font-size', '1em')
          .style('font-weight', 'bold')
          .attr('text-anchor', 'middle')
          .attr('fill', 'black')
          .text(anomaly.endX.toFixed(3));

        if (!isStored) {
          const anomalyRect = anomalyGroup
            .append('rect')
            .attr('class', `anomaly-rect-${anomaly.id}`)
            .attr('x', x(anomaly.startX))
            .attr('y', 0)
            .attr('width', x(anomaly.endX) - x(anomaly.startX))
            .attr('height', height)
            .attr('fill', 'orange')
            .attr('fill-opacity', 0.1)
            .attr('stroke', 'orange')
            .attr('stroke-width', 1)
            .attr('cursor', isBoxSelect.value ? 'move' : 'not-allowed')
            .attr('pointer-events', isBoxSelect.value ? 'all' : 'none')
            .call(
              d3.drag()
                .on('start', function (event) {
                  if (!isBoxSelect.value) return;
                  anomaly.initialX = event.x;
                })
                .on('drag', function (event) {
                  if (!isBoxSelect.value) return;
                  const dx = x.invert(event.x) - x.invert(anomaly.initialX);
                  anomaly.initialX = event.x;

                  let newStartX = anomaly.startX + dx;
                  let newEndX = anomaly.endX + dx;

                  const domain = x.domain();
                  if (newStartX < domain[0]) {
                    newStartX = domain[0];
                    newEndX = newStartX + (anomaly.endX - anomaly.startX);
                  } else if (newEndX > domain[1]) {
                    newEndX = domain[1];
                    newStartX = newEndX - (anomaly.endX - anomaly.startX);
                  }

                  anomaly.startX = newStartX;
                  anomaly.endX = newEndX;

                  updateAnomalyElements(anomaly, isStored);
                })
                .on('end', function () {
                  if (!isBoxSelect.value) return;
                  const index = store.getters.getAnomaliesByChannel(channelName).findIndex(
                    (a) => a.id === anomaly.id
                  );
                  if (index !== -1) {
                    store.dispatch('updateAnomaly', {
                      channelName: channelName,
                      anomaly: {
                        ...anomaly,
                        startX: anomaly.startX,
                        endX: anomaly.endX
                      }
                    });
                  }
                })
            );

          // 修改左侧拖动手柄
          anomalyGroup
            .append('rect')
            .attr('class', `left-handle-${anomaly.id}`)
            .attr('x', x(anomaly.startX) - 5)
            .attr('y', 0)
            .attr('width', 10)
            .attr('height', height)
            .attr('fill', 'transparent')
            .attr('cursor', isBoxSelect.value ? 'ew-resize' : 'not-allowed')
            .attr('pointer-events', isBoxSelect.value ? 'all' : 'none')
            .call(
              d3.drag()
                .on('drag', function (event) {
                  if (!isBoxSelect.value) return;
                  const newX = x.invert(event.x);
                  if (newX < anomaly.endX && newX >= x.domain()[0]) {
                    anomaly.startX = newX;
                    updateAnomalyElements(anomaly, isStored);
                  }
                })
                .on('end', function () {
                  if (!isBoxSelect.value) return;
                  const index = store.getters.getAnomaliesByChannel(channelName).findIndex(
                    (a) => a.id === anomaly.id
                  );
                  if (index !== -1) {
                    store.dispatch('updateAnomaly', {
                      channelName: channelName,
                      anomaly: {
                        ...anomaly,
                        startX: anomaly.startX,
                        endX: anomaly.endX
                      }
                    });
                  }
                })
            );

          // 修改右侧拖动手柄
          anomalyGroup
            .append('rect')
            .attr('class', `right-handle-${anomaly.id}`)
            .attr('x', x(anomaly.endX) - 5)
            .attr('y', 0)
            .attr('width', 10)
            .attr('height', height)
            .attr('fill', 'transparent')
            .attr('cursor', isBoxSelect.value ? 'ew-resize' : 'not-allowed')
            .attr('pointer-events', isBoxSelect.value ? 'all' : 'none')
            .call(
              d3.drag()
                .on('drag', function (event) {
                  if (!isBoxSelect.value) return;
                  const newX = x.invert(event.x);
                  if (newX > anomaly.startX && newX <= x.domain()[1]) {
                    anomaly.endX = newX;
                    updateAnomalyElements(anomaly, isStored);
                  }
                })
                .on('end', function () {
                  if (!isBoxSelect.value) return;
                  const index = store.getters.getAnomaliesByChannel(channelName).findIndex(
                    (a) => a.id === anomaly.id
                  );
                  if (index !== -1) {
                    store.dispatch('updateAnomaly', {
                      channelName: channelName,
                      anomaly: {
                        ...anomaly,
                        startX: anomaly.startX,
                        endX: anomaly.endX
                      }
                    });
                  }
                })
            );
        } else {
          // 已保存的异常标注显示红色矩形
          anomalyGroup
            .append('rect')
            .attr('class', `anomaly-rect-${anomaly.id}`)
            .attr('x', x(anomaly.startX))
            .attr('y', 0)
            .attr('width', x(anomaly.endX) - x(anomaly.startX))
            .attr('height', height)
            .attr('fill', 'red')
            .attr('fill-opacity', 0.1)
            .attr('stroke', 'red')
            .attr('stroke-width', 1)
            .style('pointer-events', 'none');
        }

        // 修改按钮组实现
        const buttonGroup = anomalyGroup
          .append('g')
          .attr('class', `anomaly-buttons-${anomaly.id}`)
          .attr('transform', `translate(${x(anomaly.endX) - 40}, ${height - 20})`);

        // 删除按钮
        const deleteButton = buttonGroup
          .append('g')
          .attr('class', 'delete-button')
          .style('cursor', 'pointer');

        const deleteRect = deleteButton
          .append('rect')
          .attr('width', 16)
          .attr('height', 16)
          .attr('fill', '#f56c6c')
          .attr('rx', 3)
          .style('pointer-events', 'all');

        deleteButton
          .append('text')
          .attr('x', 8)
          .attr('y', 12)
          .attr('text-anchor', 'middle')
          .attr('fill', 'white')
          .attr('font-size', '12px')
          .attr('font-weight', 'bold')
          .style('pointer-events', 'none')
          .text('×');

        // 编辑按钮
        const editButton = buttonGroup
          .append('g')
          .attr('class', 'edit-button')
          .attr('transform', 'translate(20, 0)')
          .style('cursor', 'pointer');

        const editRect = editButton
          .append('rect')
          .attr('width', 16)
          .attr('height', 16)
          .attr('fill', '#409eff')
          .attr('rx', 3)
          .style('pointer-events', 'all');

        editButton
          .append('text')
          .attr('x', 8)
          .attr('y', 12)
          .attr('text-anchor', 'middle')
          .attr('fill', 'white')
          .attr('font-size', '12px')
          .attr('font-weight', 'bold')
          .style('pointer-events', 'none')
          .text('✒️');

        // 添加点击事件到矩形上
        deleteRect.on('click', () => {
          if (isStored) {
            store.dispatch('deleteAnomaly', {
              channelName: anomaly.channelName,
              anomalyId: anomaly.id,
            });
          } else {
            store.dispatch('deleteAnomaly', {
              channelName: anomaly.channelName,
              anomalyId: anomaly.id,
            });
          }
          removeAnomalyElements(anomaly.id, channelName);
        });

        editRect.on('click', () => {
          // 从store中获取最新的异常数据
          const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
          const storedAnomaly = storedAnomalies.find(a => a.id === anomaly.id);
          
          if (storedAnomaly) {
            // 使用store中的数据更新currentAnomaly
            Object.assign(currentAnomaly, {
              ...storedAnomaly,
              channelName: channelName
            });
          } else {
            // 如果在store中找不到,使用当前anomaly数据
            Object.assign(currentAnomaly, {
              ...anomaly,
              channelName: channelName
            });
          }
          
          showAnomalyForm.value = true;
        });

        const startIndex = data.X_value.findIndex(
          (xVal) => xVal >= anomaly.startX
        );
        const endIndex = data.X_value.findIndex(
          (xVal) => xVal >= anomaly.endX
        );
        const anomalyXValues = data.X_value.slice(
          startIndex,
          endIndex + 1
        );
        const anomalyYValues = data.Y_value.slice(
          startIndex,
          endIndex + 1
        );

        anomalyGroup
          .append('path')
          .datum(anomalyYValues)
          .attr('class', `anomaly-line-${anomaly.id}`)
          .attr('fill', 'none')
          .attr('stroke', isStored ? 'red' : 'orange')
          .attr('stroke-width', 3)
          .attr(
            'd',
            d3
              .line()
              .x((d, i) => x(anomalyXValues[i]))
              .y((d, i) => y(d))
          );

        if (isStored) {
          anomalyGroup
            .select(`.anomaly-rect-${anomaly.id}`)
            .style('pointer-events', 'none');
          anomalyGroup
            .selectAll(
              `.left-handle-${anomaly.id}, .right-handle-${anomaly.id}`
            )
            .remove();
        }
      }

      function updateAnomalyElements(anomaly, isStored = false) {
        const anomalyGroup = d3.select(`#chart-${anomaly.channelName}`)
          .select('.anomalies-group')
          .select(`.anomaly-group-${anomaly.id}`); // 使用唯一ID

        // 更新矩形位置和大小
        anomalyGroup
          .select(`.anomaly-rect-${anomaly.id}`)
          .attr('x', x(anomaly.startX))
          .attr('width', x(anomaly.endX) - x(anomaly.startX))
          .attr('fill', isStored ? 'red' : 'orange')
          .attr('stroke', isStored ? 'red' : 'orange');

        // 更新左侧手柄位置
        anomalyGroup
          .select(`.left-handle-${anomaly.id}`)
          .attr('x', x(anomaly.startX) - 5);

        // 更新右侧手柄位置
        anomalyGroup
          .select(`.right-handle-${anomaly.id}`)
          .attr('x', x(anomaly.endX) - 5);

        // 更新按钮组位置
        const buttonGroup = anomalyGroup.select(`.anomaly-buttons-${anomaly.id}`);
        buttonGroup.attr('transform', `translate(${x(anomaly.endX) - 40}, ${height - 20})`);

        // 更新标签位置和文本
        g.select(`.anomaly-labels-group-${anomaly.id} .left-label-${anomaly.id}`)
          .attr('x', x(anomaly.startX))
          .text(anomaly.startX.toFixed(3));

        g.select(`.anomaly-labels-group-${anomaly.id} .right-label-${anomaly.id}`)
          .attr('x', x(anomaly.endX))
          .text(anomaly.endX.toFixed(3));

        // 更新高亮曲线
        const startIndex = data.X_value.findIndex(xVal => xVal >= anomaly.startX);
        const endIndex = data.X_value.findIndex(xVal => xVal >= anomaly.endX);
        const anomalyXValues = data.X_value.slice(startIndex, endIndex + 1);
        const anomalyYValues = data.Y_value.slice(startIndex, endIndex + 1);

        anomalyGroup
          .select(`.anomaly-line-${anomaly.id}`)
          .datum(anomalyYValues)
          .attr('d', d3.line()
            .x((d, i) => x(anomalyXValues[i]))
            .y((d, i) => y(d))
          )
          .attr('stroke', isStored ? 'red' : 'orange');
      }

      function removeAnomalyElements(anomalyId, channelName) {
        // 从store中删除异常数据
        store.dispatch('deleteAnomaly', {
          channelName: channelName,
          anomalyId: anomalyId
        });

        // 移除相关的DOM元素
        d3.selectAll([
          `.anomaly-group-${anomalyId}`,
          `.anomaly-labels-group-${anomalyId}`,
          `.anomaly-buttons-${anomalyId}`
        ].join(',')).remove();

        // 恢复刷选功能
        const g = d3.select(`#chart-${channelName}`).select('g');
        g.select('.selection-brush .overlay').style('pointer-events', 'all');
        g.select('.selection-brush .selection').style('display', null);
      }

      performance.mark(`Draw Chart ${channelName}-end`);
      performance.measure(`Draw Chart ${channelName}`,
        `Draw Chart ${channelName}-start`,
        `Draw Chart ${channelName}-end`);

      // 在图表绘制完成后，检查是否有匹配结果需要高亮
      const channelMatchedResults = matchedResults.value.filter(
        r => r.channelName === channelName.split('_')[0] &&
          r.shotNumber === channelName.split('_')[1]
      );

      if (channelMatchedResults.length > 0) {
        drawHighlightRects(channelName, channelMatchedResults);
      }

      resolve();
    } catch (error) {
      console.error('Error in drawChart:', error);
      reject(error);
    }
  });
};

// 添加解码函数
const decodeChineseText = (text) => {
  if (!text) return '';
  try {
    if (typeof text === 'string' && /^[\u4e00-\u9fa5]+$/.test(text)) { return text; }
    if (typeof text === 'string' && /[\u0080-\uffff]/.test(text)) {
      try {
        const decodedText = decodeURIComponent(escape(text));
        return decodedText;
      } catch (e) {
        console.warn('Failed to decode text:', text, e);
        return text;
      }
    }
    return text;
  } catch (err) {
    console.warn('Error decoding text:', err);
    return text;
  }
};

// 修改 saveAnomaly 函数，在更新颜色的同时禁用拖拽功能
const saveAnomaly = () => {
  if (currentAnomaly) {
    const payload = {
      channelName: currentAnomaly.channelName,
      anomaly: {
        ...currentAnomaly,
        anomalyCategory: decodeChineseText(currentAnomaly.anomalyCategory),
        anomalyDiagnosisName: decodeChineseText(currentAnomaly.anomalyDiagnosisName),
        anomalyDescription: decodeChineseText(currentAnomaly.anomalyDescription),
        isStored: true
      },
    };

    // 更新store中的异常数据
    store.dispatch('updateAnomaly', payload);

    // 立即更新视觉状态
    const svg = d3.select(`#chart-${payload.channelName}`);
    const anomalyGroup = svg.select(`.anomaly-group-${currentAnomaly.id}`);
    
    // 更新矩形颜色并禁用拖拽
    anomalyGroup.select(`.anomaly-rect-${currentAnomaly.id}`)
      .attr('fill', 'red')
      .attr('fill-opacity', 0.1)
      .attr('stroke', 'red')
      .attr('cursor', 'not-allowed')
      .attr('pointer-events', 'none');

    // 更新线条颜色
    anomalyGroup.select(`.anomaly-line-${currentAnomaly.id}`)
      .attr('stroke', 'red');

    // 移除拖动手柄
    anomalyGroup.selectAll(`.left-handle-${currentAnomaly.id}, .right-handle-${currentAnomaly.id}`)
      .remove();

    // 关闭编辑框
    showAnomalyForm.value = false;

    ElMessage.success('异常标注信息已保存');

    // 清空当前异常数据
    Object.keys(currentAnomaly).forEach((key) => {
      delete currentAnomaly[key];
    });
  }
};


const closeAnomalyForm = () => {
  showAnomalyForm.value = false;
  Object.keys(currentAnomaly).forEach((key) => {
    delete currentAnomaly[key];
  });
};

// 添加进度百分比计算函数
const getProgressPercentage = (channelKey) => {
  const loadingTotal = Number(loadingStates[channelKey]) || 0;
  const renderingTotal = Number(renderingStates[channelKey]) || 0;

  // 如果数据已经加载完成（包括从缓存读取的情况）
  if (loadingTotal === 100) {
    // 如果渲染还没开始，返回50%，表示数据已加载完成但还未开始渲染
    if (renderingTotal === 0) {
      return 50;
    }
    // 如果正在渲染或渲染完成，返回50%加上渲染进度的一半
    return 50 + renderingTotal / 2;
  }
  // 如果还在加载数据，返回加载进度的一半
  return loadingTotal / 2;
};

// 添加对isBoxSelect的监听
watch(isBoxSelect, (newValue) => {
  // 只更新所有图表中brush的显示状态
  selectedChannels.value.forEach(channel => {
    const channelName = `${channel.channel_name}_${channel.shot_number}`;
    const svg = d3.select(`#chart-${channelName}`);

    // 更新selection-brush的显示状态
    svg.select('.selection-brush')
      .style('display', newValue ? null : 'none');

    // 更新zoom-brush的显示状态
    svg.select('.zoom-brush')
      .style('display', newValue ? 'none' : null);
  });
});

// 添加一个新的 watch 来监听每个通道的颜色变化
watch(() => selectedChannels.value.map(ch => ({ key: ch.channel_key, color: ch.color })),
  (newVal, oldVal) => {
    if (!oldVal) return;

    // 找出颜色发生变化的通道
    newVal.forEach((channel, index) => {
      if (oldVal[index] && channel.color !== oldVal[index].color) {
        const targetChannel = selectedChannels.value[index];
        const channelKey = `${targetChannel.channel_name}_${targetChannel.shot_number}`;

        // 更新主图表中的线条颜色
        const svg = d3.select(`#chart-${channelKey}`);
        if (svg.node()) {
          // 更新原始线条颜色
          svg.select('.original-line')
            .attr('stroke', channel.color);

          // 更新平滑线条颜色(如果存在)
          svg.select('.smoothed-line')
            .attr('stroke', channel.color);

          // 更新图例文本颜色
          svg.select('.legend-group text')
            .style('fill', channel.color);
        }

        // 更新概览图中的线条颜色
        const overviewSvg = d3.select('#overview-chart');
        if (overviewSvg.node()) {
          overviewSvg.selectAll('.overview-line')
            .filter(d => d.channelName === channelKey)
            .attr('stroke', channel.color);
        }

        // 更新 overviewData 中的颜色
        const existingIndex = overviewData.value.findIndex(d => d.channelName === channelKey);
        if (existingIndex !== -1) {
          overviewData.value[existingIndex].color = channel.color;
        }
      }
    });
  },
  { deep: true }
);

// 移除原有的 watch，因为它会导致不必要的重绘
watch(() => selectedChannels.value.map(channel => channel.errors.map(error => error.color)),
  () => {
    // 当异常颜色发生变化时，重新渲染所有图表
    selectedChannels.value.forEach(channel => {
      const data = channelDataCache.value[`${channel.channel_name}_${channel.shot_number}`];
      if (data) {
        drawChannelChart(channel, data);
      }
    });
  },
  { deep: true }
);
</script>

<style scoped>
.el-divider--horizontal {
  margin: 0px !important;
  border-top: 3px var(--el-border-color) var(--el-border-style);
}

.chart-container {
  display: flex;
  flex-direction: column;
  padding-bottom: 10vh;
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
  margin-bottom: -8px;
  position: relative;
}

svg {
  width: 100%;
  position: relative;
}

.color-picker-container {
  position: absolute;
  top: 16px;
  right: 17px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 5px;
  background-color: transparent;
  padding: 2px 5px;
}

/* 添加新的图例样式 */
.legend-group {
  pointer-events: none;
}


/* 去除颜色选择器里面的箭头 */
:deep(.is-icon-arrow-down) {
  display: none !important;
}

/* 去除颜色选择器最外层的边框 */
:deep(.el-color-picker__trigger) {
  border: none;
  padding: 2px;
  height: 24px !important;
  width: 24px !important;
}

/* 将颜色色块变为圆形并调整大小 */
:deep(.el-color-picker__color) {
  border-radius: 50%;
  width: 20px !important;
  height: 20px !important;
}

/* 调整颜色选择器下拉面板的位置 */
:deep(.el-color-dropdown.el-color-picker__panel) {
  transform: translateX(-50%) !important;
}

.divider {
  width: 100%;
  height: 8px;
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
  z-index: 99999;
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

/* 自定进度条样式 */
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

/* 输入框内的文字可以选中 */
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

/* 让对话框中的输入框文字可选中 */
.el-dialog .el-input {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}
</style>
