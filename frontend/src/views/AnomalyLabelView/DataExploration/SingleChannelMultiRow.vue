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
        <div :id="'chart-' + channel.channel_name + '_' + channel.shot_number"
          :ref="el => channelSvgElementsRefs[index] = el" :style="{
            opacity: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 1 : 0,
            transition: 'opacity 0.5s ease'
          }"></div>
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
      <template #footer>
        <span class="dialog-footer">
        <el-button @click="closeAnomalyForm">取消</el-button>
        <el-button type="primary" @click="saveAnomaly">保存</el-button>
          <el-button type="danger" @click="deleteAnomaly">删除</el-button>
      </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import Highcharts from 'highcharts';
import 'highcharts/modules/boost';
import debounce from 'lodash/debounce';
import ChannelColorPicker from '@/components/ChannelColorPicker.vue';
import { ref, reactive, watch, computed, onMounted, nextTick, onUnmounted, toRaw } from 'vue';
import { ElDialog, ElForm, ElFormItem, ElInput, ElButton, ElMessage } from 'element-plus';
import { useStore } from 'vuex';
import chartWorkerManager from '@/workers/chartWorkerManager';

const currentAnomaly = reactive({});
const showAnomalyForm = ref(false);
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
const matchedResults = computed(() => store.state.matchedResults);
// 存储原始的显示范围
const originalDomains = ref({});
const channelDataCache = computed(() => store.state.channelDataCache);// 定义缓存对象
// 获取异常标记数据
const anomalies = computed(() => store.state.anomalies);
const loadingStates = reactive({});  // 用于存储每个通道的加载状态
const renderingStates = reactive({}); // 用于存储每个通道的渲染状态
// 用于跟踪已经渲染过的通道
const renderedChannels = ref(new Set());

const brush_begin = computed({
  get: () => store.state.brush_begin,
  set: (value) => store.commit('updatebrush', { begin: value, end: brush_end.value })
});

const brush_end = computed({
  get: () => store.state.brush_end,
  set: (value) => store.commit('updatebrush', { begin: brush_begin.value, end: value })
});

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

    // 删除对应的组件
    deletedAnomalies.forEach(anomaly => {
      // 如果正在编辑被删除的异常，关闭编辑表单
      if (showAnomalyForm.value && currentAnomaly.id === anomaly.id) {
        showAnomalyForm.value = false;
        Object.keys(currentAnomaly).forEach(key => {
          delete currentAnomaly[key];
        });
      }
      
      // 从图表中移除异常相关元素
      const chart = window.chartInstances?.[channelName];
      if (chart) {
        // 移除plotBand
        chart.xAxis[0].removePlotBand(`band-${anomaly.id}`);
        
        // 移除异常线条
        const anomalySeries = chart.get(`anomaly-${anomaly.id}`);
        if (anomalySeries) {
          anomalySeries.remove();
        }
        
        // 移除按钮
        const deleteButton = document.querySelector(`.delete-button-${anomaly.id}`);
        if (deleteButton) {
          deleteButton.remove();
        }
        
        const editButton = document.querySelector(`.edit-button-${anomaly.id}`);
        if (editButton) {
          editButton.remove();
        }
      }
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
  
  // 获取Highcharts图表实例
  const chart = window.chartInstances?.[channelKey];
  if (chart) {
    // 更新原始线条颜色
    const originalSeries = chart.get('original');
    if (originalSeries) {
      originalSeries.update({
        color: channel.color
      }, false);
    }

    // 更新平滑线条颜色
    const smoothedSeries = chart.get('smoothed');
    if (smoothedSeries) {
      smoothedSeries.update({
        color: channel.color
      }, false);
    }

    // 更新图例文字颜色
    chart.renderer.text(
      `${channel.channel_name} | ${channel.shot_number} (${chart.series[0].name.split('(')[1]}`,
      60,
      15
    )
    .css({
      color: channel.color,
      fontSize: '1.0em',
      fontWeight: 'bold'
    })
    .add();

    // 重绘图表
    chart.redraw();
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

    // 并行获取错误数据 - 不阻塞其他处理
    const errorDataPromise = channel.errors && channel.errors.length > 0
      ? store.dispatch('fetchAllErrorData', channel).catch(err => {
          console.warn('Failed to fetch error data:', err);
          return [];
        })
      : Promise.resolve([]);

    renderingStates[channelKey] = 40;

    // 并行处理 - 同时进行数据处理和错误数据获取
    const [processedData, errorDataResults] = await Promise.all([
      // 使用 chartWorkerManager 处理数据
      chartWorkerManager.processData(
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
      ),
      errorDataPromise
    ]);

    if (processedData) {
      // 更新 channelDataCache
      store.commit('updateChannelDataCache', {
        channelKey: channelKey,
        data: {
          ...processedData.processedData,
          errorsData: errorDataResults
        }
      });

      renderingStates[channelKey] = 75; // 更新渲染状态

      // 只渲染当前通道，不重新渲染其他通道
      await nextTick();
      await drawChart(
        processedData.processedData,
        errorDataResults,
        channelKey,
        processedData.color,
        processedData.xUnit,
        processedData.yUnit,
        processedData.channelType,
        processedData.channelNumber,
        processedData.shotNumber
      );

      renderingStates[channelKey] = 100;
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

    // 确保立即更新初始加载状态
    loadingStates[channelKey] = Number(0);
    // 强制更新视图
    await nextTick();

    // 创建进度更新定时器
    const progressInterval = setInterval(() => {
      if (loadingStates[channelKey] < 90) {
        loadingStates[channelKey] = Math.min(Number(loadingStates[channelKey]) + 5, 90);
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

const renderCharts = debounce(async (forceRenderAll = false) => {
  try {
    performance.mark('Total Render Time-start');

    // 确保有选中的通道
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      console.warn('No channels selected');
      return;
    }

    // 决定需要渲染的通道
    let channelsToRender;
    if (forceRenderAll) {
      // 如果强制重新渲染，则渲染所有选定的通道
      channelsToRender = [...selectedChannels.value];
    } else {
      // 否则只渲染新添加的通道
      channelsToRender = selectedChannels.value.filter(channel => {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        return !renderedChannels.value.has(channelKey);
      });
    }

    // 初始化要渲染的通道的加载状态
    channelsToRender.forEach(channel => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      loadingStates[channelKey] = 0;
      renderingStates[channelKey] = 0;
    });

    // 完全并行获取和渲染每个通道，不等待其他通道完成
    const renderPromises = channelsToRender.map(async (channel) => {
      try {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;

        // 获取通道数据
        const data = await fetchChannelData(channel);
        if (!data) return;

        // 处理数据并渲染图表 (不等待其他通道)
        await processChannelData(data, channel);

        // 标记通道已渲染
        renderedChannels.value.add(channelKey);
      } catch (error) {
        console.error(`Error rendering channel ${channel.channel_name}:`, error);
      }
    });

    // 等待所有通道并行渲染完成
    await Promise.all(renderPromises);

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

// 监听selectedChannels的变化，处理移除的通道
watch(selectedChannels, (newChannels, oldChannels) => {
  if (!oldChannels) {
    // 初始化情况，不需要处理
    return;
  }

  // 获取新旧通道的键集合
  const oldChannelKeys = new Set(oldChannels.map(ch => `${ch.channel_name}_${ch.shot_number}`));
  const newChannelKeys = new Set(newChannels.map(ch => `${ch.channel_name}_${ch.shot_number}`));

  // 获取被移除的通道键
  const removedChannelKeys = [...oldChannelKeys].filter(key => !newChannelKeys.has(key));

  // 从renderedChannels中移除这些通道
  removedChannelKeys.forEach(key => {
    renderedChannels.value.delete(key);
  });

  // 获取新添加的通道键
  const addedChannelKeys = [...newChannelKeys].filter(key => !oldChannelKeys.has(key));

  // 只对新增通道或颜色变更的通道进行处理，每个通道独立处理
  if (addedChannelKeys.length > 0) {
    // 找出所有新增的通道
    const newAddedChannels = newChannels.filter(ch => {
      const key = `${ch.channel_name}_${ch.shot_number}`;
      return addedChannelKeys.includes(key);
    });

    // 并行渲染新增通道，每个通道单独处理，不互相等待
    newAddedChannels.forEach(channel => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;

      // 初始化加载状态
      loadingStates[channelKey] = 0;
      renderingStates[channelKey] = 0;

      // 立即开始异步加载和渲染，不等待其他通道
      (async () => {
        try {
          // 获取通道数据
          const data = await fetchChannelData(channel);
          if (!data) return;

          // 处理通道数据并渲染
          await processChannelData(data, channel);

          // 标记为已渲染
          renderedChannels.value.add(channelKey);
        } catch (error) {
          console.error(`Error rendering channel ${channelKey}:`, error);
        }
      })();
    });

    return;
  }

  // 如果只是颜色变化，只更新颜色不重新渲染整个图表
  if (newChannels.length === oldChannels.length && addedChannelKeys.length === 0 && removedChannelKeys.length === 0) {
    const colorChangedChannels = newChannels.filter(newCh => {
      const oldCh = oldChannels.find(
        old => `${old.channel_name}_${old.shot_number}` === `${newCh.channel_name}_${newCh.shot_number}`
      );
      return oldCh && oldCh.color !== newCh.color;
    });

    if (colorChangedChannels.length > 0) {
      // 只更新颜色变更的通道
      colorChangedChannels.forEach(channel => {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;

        // 直接更新SVG中的颜色，而不重新渲染整个图表
        const svg = d3.select(`#chart-${channelKey}`);
        if (svg.node()) {
          svg.select('.original-line').attr('stroke', channel.color);
          svg.select('.smoothed-line').attr('stroke', channel.color);
          svg.select('.legend-group text').style('fill', channel.color);
        }
      });
    }
  }
}, { deep: true });


watch([sampling, smoothnessValue], ([newSampling, newSmoothness], [oldSampling, oldSmoothness]) => {
  if (newSampling !== oldSampling) {
    sampleRate.value = newSampling;
  }

  // 不再清空已渲染通道的跟踪记录，而是并行更新每个通道
  // 并行处理所有通道的更新
  selectedChannels.value.forEach(channel => {
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;
    const cachedData = channelDataCache.value[channelKey];

    if (cachedData) {
      // 初始化渲染状态
      renderingStates[channelKey] = 25;

      // 立即开始异步处理，不等待其他通道
      (async () => {
        try {
          // 准备数据
          const channelData = {
            X_value: [...cachedData.X_value],
            Y_value: [...cachedData.Y_value],
            originalFrequency: cachedData.originalFrequency,
            originalDataPoints: cachedData.X_value.length
          };

          // 获取并处理数据
          const processedData = await chartWorkerManager.processData(
            channelData,
            newSampling,
            newSmoothness,
            channelKey,
            channel.color,
            cachedData.X_unit,
            cachedData.Y_unit,
            cachedData.channel_type,
            cachedData.channel_number,
            channel.shot_number
          );

          if (processedData) {
            // 更新缓存
            store.commit('updateChannelDataCache', {
              channelKey: channelKey,
              data: {
                ...processedData.processedData,
                errorsData: cachedData.errorsData
              }
            });

            renderingStates[channelKey] = 75;

            // 渲染单个通道，不影响其他通道
            await nextTick();
            await drawChart(
              processedData.processedData,
              cachedData.errorsData,
              channelKey,
              processedData.color,
              processedData.xUnit,
              processedData.yUnit,
              processedData.channelType,
              processedData.channelNumber,
              processedData.shotNumber
            );

            renderingStates[channelKey] = 100;
          }
        } catch (error) {
          console.error(`Error updating channel ${channelKey}:`, error);
          renderingStates[channelKey] = 100;
        }
      })();
    }
  });
});

// 在组件挂载时添加监听器
onMounted(async () => {
  try {
    const container = document.querySelector('.chart-container');
    if (container) {
      chartContainerWidth.value = container.offsetWidth;
    }

    // 添加初始渲染逻辑，确保组件挂载后能正确渲染图表
    nextTick(() => {
      if (selectedChannels.value && selectedChannels.value.length > 0) {
        renderCharts();
      }
    });
  } catch (error) {
    console.error('Error in mounted hook:', error);
  }
});

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
    const chart = window.chartInstances?.[payload.channelName];
    if (chart) {
      // 更新异常区域颜色
      const plotBand = chart.xAxis[0].plotLinesAndBands.find(band => band.id === `band-${currentAnomaly.id}`);
      if (plotBand) {
        // 移除事件监听器，禁用拖拽
        plotBand.options.events = {};
        
        // 更新颜色为红色
        chart.xAxis[0].removePlotBand(`band-${currentAnomaly.id}`);
        chart.xAxis[0].addPlotBand({
          id: `band-${currentAnomaly.id}`,
          from: currentAnomaly.startX,
          to: currentAnomaly.endX,
          color: 'rgba(255, 0, 0, 0.1)',
          borderColor: 'red',
          borderWidth: 1,
          zIndex: 1,
          label: {
            y: -5,
            style: {
              color: '#606060',
              fontWeight: 'bold',
              fontSize: '10px'
            },
            formatter: function() {
              return `${currentAnomaly.startX.toFixed(3)} - ${currentAnomaly.endX.toFixed(3)}`;
            }
          }
        });
      }
      
      // 更新异常线条
      const anomalySeries = chart.get(`anomaly-${currentAnomaly.id}`);
      if (anomalySeries) {
        anomalySeries.update({
          color: 'red'
        }, false);
      }
      
      // 重绘图表
      chart.redraw();
    }

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

// 添加deleteAnomaly函数
const deleteAnomaly = () => {
  if (currentAnomaly && currentAnomaly.id) {
    // 从store中删除异常
    store.dispatch('deleteAnomaly', {
      channelName: currentAnomaly.channelName,
      anomalyId: currentAnomaly.id
    });
    
    // 关闭编辑表单
    showAnomalyForm.value = false;
    
    // 显示成功消息
    ElMessage.success('异常标注已删除');
    
    // 清空当前异常数据
    Object.keys(currentAnomaly).forEach((key) => {
      delete currentAnomaly[key];
    });
  }
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
  // 更新所有图表的设置
  Object.values(window.chartInstances || {}).forEach(chart => {
    if (chart) {
      // 更新图表的缩放类型
      chart.update({
        chart: {
          zoomType: newValue ? 'x' : 'xy'
        }
      }, false);
      
      // 更新plotBands的交互
      chart.xAxis[0].plotLinesAndBands.forEach(band => {
        if (band.id && band.id.startsWith('band-')) {
          const anomalyId = band.id.replace('band-', '');
          const anomaly = chart.series.find(s => s.options.id === `anomaly-${anomalyId}`);
          
          if (anomaly && !anomaly.options.custom?.isStored) {
            band.options.events = newValue ? {
              click: function() {
                const channelName = chart.series[0].name.split(' | ')[0];
                const shotNumber = chart.series[0].name.split(' | ')[1].split(' ')[0];
                const fullChannelName = `${channelName}_${shotNumber}`;
                
                const storedAnomalies = store.getters.getAnomaliesByChannel(fullChannelName);
                const storedAnomaly = storedAnomalies.find(a => a.id === anomalyId);
                
                if (storedAnomaly) {
                  Object.assign(currentAnomaly, {
                    ...storedAnomaly,
                    channelName: fullChannelName
                  });
                }
                
                showAnomalyForm.value = true;
              }
            } : {};
          }
        }
      });
      
      chart.redraw();
    }
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

      // 获取容器宽度
      const container = document.querySelector('.chart-container');
      const containerWidth = container.getBoundingClientRect().width;

      // 构建图表配置
      const chartContainer = document.getElementById(`chart-${channelName}`);
      if (!chartContainer) {
        reject(new Error(`Chart container for ${channelName} not found`));
        return;
      }

      // 准备数据
      let originalData = [];
      for (let i = 0; i < data.X_value.length; i++) {
        originalData.push([data.X_value[i], data.Y_value[i]]);
      }

      // 计算平滑后的数据
      let smoothedData = [];
      if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
        const smoothedYValue = interpolateData(data.Y_value, smoothnessValue.value);
        for (let i = 0; i < data.X_value.length; i++) {
          smoothedData.push([data.X_value[i], smoothedYValue[i]]);
        }
      }

      // 获取Y轴范围，保持与原实现一致
      const yExtent = [
        Math.min(...data.Y_value),
        Math.max(...data.Y_value)
      ];
      const yRangePadding = (yExtent[1] - yExtent[0]) * 0.2;
      const yMin = yExtent[0] - yRangePadding;
      const yMax = yExtent[1] + yRangePadding;

      // 设置X轴和Y轴范围
      const xDomain = domains.value.x[channelName] || [Math.min(...data.X_value), Math.max(...data.X_value)];
      const yDomain = domains.value.y[channelName] || [yMin, yMax];

      // 高亮异常数据点函数
      const getAnomalyData = (anomaly) => {
        // 找到对应区间的数据点
        const startIndex = data.X_value.findIndex(x => x >= anomaly.startX);
        const endIndex = data.X_value.findIndex(x => x >= anomaly.endX);
        const anomalyData = [];
        
        for (let i = startIndex; i <= (endIndex !== -1 ? endIndex : data.X_value.length - 1); i++) {
          anomalyData.push([data.X_value[i], data.Y_value[i]]);
        }
        
        return anomalyData;
      };

      // 处理错误数据
      const errorSeries = [];
      if (errorsData && Array.isArray(errorsData)) {
        errorsData.forEach((errorGroup, groupIndex) => {
          if (Array.isArray(errorGroup)) {
            // 分别处理人工和机器错误
            errorGroup.forEach((errors, personIndex) => {
              const isPerson = personIndex === 0; // 0是人工，1是机器
              
              if (errors && Array.isArray(errors)) {
                errors.forEach((error, errorIndex) => {
                  if (error.X_error && Array.isArray(error.X_error)) {
                    error.X_error.forEach((xRange, rangeIndex) => {
                      // 找到时间范围内的数据点
                      const dataPoints = [];
            const startTime = xRange[0];
            const endTime = xRange[1];

            data.X_value.forEach((x, i) => {
              if (x >= startTime && x <= endTime) {
                          dataPoints.push([x, data.Y_value[i]]);
                        }
                      });
                      
                      if (dataPoints.length > 0) {
                        errorSeries.push({
                          name: `${isPerson ? '人工' : '机器'}错误 ${errorIndex+1}-${rangeIndex+1}`,
                          data: dataPoints,
                          color: error.color || (isPerson ? 'rgba(220, 20, 60, 0.8)' : 'rgba(220, 20, 60, 0.6)'),
                          lineWidth: 10,
                          states: { hover: { lineWidth: 10 } }, linkedTo: ':previous', marker: { enabled: false }, dashStyle: isPerson ? 'Solid' : 'Dash', enableMouseTracking: false, showInLegend: false, boostThreshold: 1 });
                  }
                });
              }
            });
          }
            });
                  }
                });
              }

      // 获取通道对应的已标注异常
      const channelAnomalies = store.getters.getAnomaliesByChannel(channelName);
      const anomalySeries = [];
      
      if (channelAnomalies && channelAnomalies.length > 0) {
        channelAnomalies.forEach(anomaly => {
          const anomalyData = getAnomalyData(anomaly);
          if (anomalyData.length > 0) {
            anomalySeries.push({
              id: `anomaly-${anomaly.id}`,
              name: anomaly.anomalyCategory || '未命名异常',
              data: anomalyData,
              color: anomaly.isStored ? 'red' : 'orange',
              lineWidth: 3,
              linkedTo: ':previous',
              enableMouseTracking: true,
              showInLegend: false,
              zIndex: 10,
              boostThreshold: 1,
              custom: { anomalyId: anomaly.id, isStored: anomaly.isStored }
            });
          }
        });
      }

      // 创建高亮矩形函数
      const getPlotBands = () => {
        const plotBands = [];
        
        // 异常区域绘制为plotBands
        if (channelAnomalies && channelAnomalies.length > 0) {
          channelAnomalies.forEach(anomaly => {
            plotBands.push({
              id: `band-${anomaly.id}`,
              from: anomaly.startX,
              to: anomaly.endX,
              color: anomaly.isStored ? 'rgba(255, 0, 0, 0.1)' : 'rgba(255, 165, 0, 0.1)',
              borderColor: anomaly.isStored ? 'red' : 'orange',
              borderWidth: 1,
              zIndex: 5,
              label: {
                text: `${anomaly.startX.toFixed(3)}`, 
                align: 'left',
                verticalAlign: 'top',
                y: -25,
                style: {
                  color: '#606060',
                  fontWeight: 'bold',
                  fontSize: '10px'
                }
              },
              events: {
                click: function() {
                  // 重绘图表以显示新添加的元素
                  chart.redraw();
                  
                  // 立即打开编辑表单
                  Object.assign(currentAnomaly, {
                    ...anomaly,
                    channelName: channelName
                  });
                  
                  // 确保表单显示
                  showAnomalyForm.value = true;
                }
              }
            });
            
            // 添加第二个标签显示结束值
            plotBands.push({
              id: `band-end-${anomaly.id}`,
              from: anomaly.endX,
              to: anomaly.endX,
              color: 'transparent',
              zIndex: 5,
              label: {
                text: `${anomaly.endX.toFixed(3)}`,
                align: 'right',
                verticalAlign: 'top',
                y: -25,
                x: -5,
                style: {
                  color: '#606060',
                  fontWeight: 'bold',
                  fontSize: '10px'
                }
              }
            });
          });
        }
        
        // 同时添加匹配结果高亮
        const channelMatchedResults = matchedResults.value.filter(
          r => r.channelName === channelName.split('_')[0] &&
            r.shotNumber === channelName.split('_')[1]
        );
        
        if (channelMatchedResults.length > 0) {
          channelMatchedResults.forEach((result, index) => {
            if (result.confidence > 0.75) {
              const [startX, endX] = result.range;
              
              // 应用过滤条件
              const timeBegin = store.state.time_begin;
              const timeEnd = store.state.time_end;
              const timeDuring = store.state.time_during;
              const upperBound = store.state.upper_bound;
              const lowerBound = store.state.lower_bound;
              const scopeBound = store.state.scope_bound;
              
              // 时间范围过滤
              if (startX < timeBegin || endX > timeEnd) {
                return;
              }
              
              // 持续时间过滤
              const duration = endX - startX;
              if (duration < timeDuring) {
                return;
              }
              
              // 获取区间内的数据点
              const startIndex = data.X_value.findIndex(x => x >= startX);
              const endIndex = data.X_value.findIndex(x => x > endX);
              
              const rangeData = {
                X: data.X_value.slice(startIndex, endIndex),
                Y: data.Y_value.slice(startIndex, endIndex)
              };
              
              if (rangeData.Y.length === 0) return;
              
              const minY = Math.min(...rangeData.Y);
              const maxY = Math.max(...rangeData.Y);
              
              // Y值范围和幅度过滤
              if (minY < lowerBound || maxY > upperBound) return;
              const yRange = Math.abs(maxY - minY);
              if (yRange < scopeBound) return;
              
              // 添加匹配结果高亮
              plotBands.push({
                id: `match-${index}`,
                from: startX,
                to: endX,
                color: 'rgba(255, 165, 0, 0.2)',
                borderColor: 'rgba(255, 140, 0, 0.8)',
                borderWidth: 2,
                zIndex: 0,
                events: {
                  mouseOver: function() {
                    const tooltip = document.createElement('div');
                    tooltip.className = 'custom-tooltip';
                    tooltip.style.position = 'absolute';
                    tooltip.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                    tooltip.style.color = '#333';
                    tooltip.style.padding = '2px 5px';
                    tooltip.style.borderRadius = '4px';
                    tooltip.style.fontSize = '12px';
                    tooltip.style.boxShadow = '0 1px 4px rgba(0,0,0,0.2)';
                    tooltip.style.zIndex = '9999';
                    tooltip.style.pointerEvents = 'none';
                    tooltip.style.border = '1px solid #ccc';
                    
                    tooltip.textContent = `( ${startX.toFixed(4)}, ${endX.toFixed(4)} )`;
                    
                    document.body.appendChild(tooltip);
                    
                    // 设置提示框位置
                    const event = window.event;
                    const tooltipWidth = tooltip.getBoundingClientRect().width;
                    const tooltipHeight = tooltip.getBoundingClientRect().height;
                    const mouseX = event.pageX;
                    const mouseY = event.pageY;
                    
                    tooltip.style.left = `${mouseX - tooltipWidth / 2}px`;
                    tooltip.style.top = `${mouseY - tooltipHeight - 10}px`;
                    
                    this.tooltip = tooltip;
                  },
                  mouseOut: function() {
                    if (this.tooltip) {
                      document.body.removeChild(this.tooltip);
                      this.tooltip = null;
                    }
                  }
                }
              });
            }
          });
        }
        
        return plotBands;
      };

      // 创建图表
      const chart = Highcharts.chart(`chart-${channelName}`, {
        chart: {
          height: 230,
          zoomType: isBoxSelect.value ? 'x' : 'xy',
          animation: false,
          events: {
            selection: function(event) {
              if (event.resetSelection) {
                // 重置选区
                return;
              }

              // 确保在框选模式下只处理框选，不处理缩放
              if (isBoxSelect.value) {
                // 处理框选
                if (event.xAxis) {
                  const [x0, x1] = [event.xAxis[0].min, event.xAxis[0].max];
                  
                  // 格式化当前时间
                  const now = new Date();
                  const formattedTime = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;
                  
                  const anomaly = {
                    id: `${store.state.person}_${Date.now()}`,
                    person: store.state.person,
                    channelName: channelName,
                    startX: x0,
                    endX: x1,
                    anomalyCategory: '',
                    anomalyDiagnosisName: '',
                    anomalyDescription: '',
                    annotationTime: formattedTime,
                    isStored: false
                  };
                  
                  // 添加到store
                  store.dispatch('addAnomaly', {
                    channelName: channelName,
                    anomaly: anomaly
                  });
                  
                  // 立即添加plotBand
                  chart.xAxis[0].addPlotBand({
                    id: `band-${anomaly.id}`,
                    from: anomaly.startX,
                    to: anomaly.endX,
                    color: 'rgba(255, 165, 0, 0.1)',
                    borderColor: 'orange',
                    borderWidth: 1,
                    zIndex: 5,
                    label: {
                      text: `${anomaly.startX.toFixed(3)}`, 
                      align: 'left',
                      verticalAlign: 'top',
                      y: -25,
                      style: {
                        color: '#606060',
                        fontWeight: 'bold',
                        fontSize: '10px'
                      }
                    },
                    events: {
                      click: function() {
                        const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
                        const storedAnomaly = storedAnomalies.find(a => a.id === anomaly.id);
                        
                        if (storedAnomaly) {
                          Object.assign(currentAnomaly, {
                            ...storedAnomaly,
                            channelName: channelName
                          });
                        } else {
                          Object.assign(currentAnomaly, {
                        ...anomaly,
                            channelName: channelName
                          });
                        }
                        
                        showAnomalyForm.value = true;
                      }
                    }
                  });
                  
                  // 添加结束标签
                  chart.xAxis[0].addPlotBand({
                    id: `band-end-${anomaly.id}`,
                    from: anomaly.endX,
                    to: anomaly.endX,
                    color: 'transparent',
                    zIndex: 5,
                    label: {
                      text: `${anomaly.endX.toFixed(3)}`,
                      align: 'right',
                      verticalAlign: 'top',
                      y: -25,
                      x: -5,
                      style: {
                        color: '#606060',
                        fontWeight: 'bold',
                        fontSize: '10px'
                      }
                    }
                  });
                  
                  // 立即添加异常数据系列
                  const anomalyData = [];
                  const startIndex = data.X_value.findIndex(x => x >= anomaly.startX);
                  const endIndex = data.X_value.findIndex(x => x >= anomaly.endX);
                  
                  for (let i = startIndex; i <= (endIndex !== -1 ? endIndex : data.X_value.length - 1); i++) {
                    anomalyData.push([data.X_value[i], data.Y_value[i]]);
                  }
                  
                  if (anomalyData.length > 0) {
                    chart.addSeries({
                      id: `anomaly-${anomaly.id}`,
                      name: anomaly.anomalyCategory || '未命名异常',
                      data: anomalyData,
                      color: 'orange',
                      lineWidth: 3,
                      linkedTo: ':previous',
                      enableMouseTracking: true,
                      showInLegend: false,
                      zIndex: 10,
                      boostThreshold: 1,
                      custom: { anomalyId: anomaly.id, isStored: anomaly.isStored }
                    }, false);
                  }
                  
                  // 立即添加编辑和删除按钮
                  const startX = chart.xAxis[0].toPixels(anomaly.startX);
                  const endX = chart.xAxis[0].toPixels(anomaly.endX);
                  const y = chart.yAxis[0].toPixels(yDomain[0]);
                  
                  // 添加删除按钮 - 放在下方
                  const deleteButton = chart.renderer.button(
                    '×',
                    endX - 25,
                    y - 3,
                    function() {
                      // 删除异常
                      store.dispatch('deleteAnomaly', {
                        channelName: anomaly.channelName || channelName,
                        anomalyId: anomaly.id,
                      });
                      
                      // 移除按钮和绘图元素
                      this.destroy();
                      const editBtn = document.querySelector(`.edit-button-${anomaly.id}`);
                      if (editBtn) {
                        editBtn.remove();
                      }
                      chart.xAxis[0].removePlotBand(`band-${anomaly.id}`);
                      chart.xAxis[0].removePlotBand(`band-end-${anomaly.id}`);
                      const anomalySeries = chart.get(`anomaly-${anomaly.id}`);
                      if (anomalySeries) {
                        anomalySeries.remove();
                      }
                    },
                    {
                      fill: '#f56c6c',
                      style: {
                        color: 'white',
                        fontWeight: 'bold',
                        fontSize: '10px',
                        textAlign: 'center',
                        lineHeight: '6px',
                        paddingTop: '0px',
                        paddingLeft: '0px'
                      },
                      r: 5,
                      width: 6,
                      height: 6,
                      zIndex: 10
                    }
                  )
                  .attr({
                    'class': `delete-button-${anomaly.id}`,
                    'zIndex': 10
                  })
                  .css({
                    cursor: 'pointer'
                  })
                  .add();
                  
                  // 添加编辑按钮 - 放在上方
                  const editButton = chart.renderer.button(
                    '✎',
                    endX - 25,
                    y - 28,
                    function() {
                      const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
                      const storedAnomaly = storedAnomalies.find(a => a.id === anomaly.id);
                      
                      if (storedAnomaly) {
                        Object.assign(currentAnomaly, {
                          ...storedAnomaly,
                          channelName: channelName
                        });
                      } else {
                        Object.assign(currentAnomaly, {
                          ...anomaly,
                          channelName: channelName
                        });
                      }
                      
                      showAnomalyForm.value = true;
                    },
                    {
                      fill: '#409eff',
                      style: {
                        color: 'white',
                        fontWeight: 'bold',
                        fontSize: '10px',
                        textAlign: 'center',
                        lineHeight: '6px',
                        paddingTop: '0px',
                        paddingLeft: '0px'
                      },
                      r: 5,
                      width: 6,
                      height: 6,
                      zIndex: 10
                    }
                  )
                  .attr({
                    'class': `edit-button-${anomaly.id}`,
                    'zIndex': 10
                  })
                  .css({
                    cursor: 'pointer'
                  })
                  .add();
                  
                  // 确保按钮在最顶层
                  deleteButton.toFront();
                  editButton.toFront();
                  
                  // 重绘图表以显示新添加的元素
                  chart.redraw();
                  
                  // 立即打开编辑表单
                  Object.assign(currentAnomaly, {
                    ...anomaly,
                    channelName: channelName
                  });
                  
                  // 确保表单显示
                  showAnomalyForm.value = true;
                }
                return false; // 阻止默认缩放行为
              }
              else if (!isBoxSelect.value) {
                // 处理缩放
                if (event.xAxis) {
                  const [xMin, xMax] = [event.xAxis[0].min, event.xAxis[0].max];
                  const [yMin, yMax] = [event.yAxis[0].min, event.yAxis[0].max];

                  // 保存原始范围（如果还没有保存）
                  if (!originalDomains.value[channelName]) {
                    originalDomains.value[channelName] = {
                      x: [parseFloat(brush_begin.value), parseFloat(brush_end.value)],
                      y: [yMin, yMax]
                    };
                  }
                  
                  // 更新store中的范围
                  store.dispatch('updateDomains', {
                    channelName,
                    xDomain: [xMin, xMax],
                    yDomain: [yMin, yMax]
                  });

                  // 重新绘制图表
                  nextTick(() => {
                    const targetChannel = selectedChannels.value.find(ch => `${ch.channel_name}_${ch.shot_number}` === channelName);
                    if (targetChannel) {
                      const data = channelDataCache.value[`${targetChannel.channel_name}_${targetChannel.shot_number}`];
                      if (data) {
                        drawChannelChart(targetChannel, data);
                      }
                    }
                  });
                }
                return false; // 阻止默认缩放行为
              }
            }
          }
        },
        title: {
          text: '',
          style: {
            display: 'none'
          }
        },
        credits: {
          enabled: false
        },
        boost: {
          useGPUTranslations: true,
          usePreallocated: true,
          seriesThreshold: 1
        },
        xAxis: {
          min: xDomain[0],
          max: xDomain[1],
          plotBands: getPlotBands(),
          title: {
            text: 'Time(s)',
            style: {
              fontSize: '1.1em',
              fontWeight: 'bold'
            }
          },
          labels: {
            style: {
              fontSize: '1.1em',
              fontWeight: 'bold'
            }
          },
          gridLineWidth: 1,
          gridLineDashStyle: 'Dash',
          gridLineColor: '#ccc'
        },
        yAxis: {
          min: yDomain[0],
          max: yDomain[1],
          title: {
            text: yUnit,
            style: {
              fontSize: '1.05em',
              fontWeight: 'bold'
            }
          },
          labels: {
            style: {
              fontSize: '1em',
              fontWeight: 'bold'
            }
          },
          gridLineWidth: 1,
          gridLineDashStyle: 'Dash',
          gridLineColor: '#ccc'
        },
        legend: {
          enabled: false
        },
        tooltip: {
          enabled: true,
          formatter: function() {
            return `(${this.x.toFixed(3)}, ${this.y.toFixed(3)})`;
          },
          positioner: function(labelWidth, labelHeight, point) {
            return {
              x: point.plotX + this.chart.plotLeft - labelWidth / 2,
              y: point.plotY + this.chart.plotTop - labelHeight - 10
            };
          },
          backgroundColor: 'rgba(255, 255, 255, 0.8)',
          borderWidth: 1,
          borderColor: '#ccc',
          shadow: false,
          style: {
            fontSize: '10px',
            padding: '2px 5px'
          }
        },
        plotOptions: {
          series: {
            animation: false,
            turboThreshold: 0,
            states: {
              hover: {
                enabled: true,
                lineWidth: 2
              }
            },
            point: {
              events: {}
            }
          }
        },
        series: [
          // 原始数据线
          {
            name: `${channelNumber} | ${shotNumber} (${data.originalFrequency.toFixed(2)}KHz -> ${(sampling.value).toFixed(2)}KHz)`,
            id: 'original',
            type: 'line',
            data: originalData,
            color: color,
            lineWidth: 1.5,
            opacity: smoothnessValue.value > 0 ? 0.3 : 1,
            marker: { enabled: false },
            boostThreshold: 1,
            enableMouseTracking: true,
          },
          // 平滑数据线
          ...(smoothnessValue.value > 0 ? [{
            name: '平滑线',
            id: 'smoothed',
            type: 'line',
            data: smoothedData,
            color: color,
            lineWidth: 1.5,
            marker: { enabled: false },
            boostThreshold: 1,
            enableMouseTracking: true,
          }] : []),
          // 错误数据线
          ...errorSeries,
          // 异常标注线
          ...anomalySeries
        ]
      });

      // 设置自定义按钮
      channelAnomalies.forEach(anomaly => {
        // 添加编辑和删除按钮
        if (chart && chart.renderer) {
          const startX = chart.xAxis[0].toPixels(anomaly.startX);
          const endX = chart.xAxis[0].toPixels(anomaly.endX);
          const y = chart.yAxis[0].toPixels(yDomain[0]);
          
          // 添加删除按钮 - 放在下方
          const deleteButton = chart.renderer.button(
            '×',
            endX - 25,
            y - 3,
            function() {
              // 删除异常
              store.dispatch('deleteAnomaly', {
                channelName: anomaly.channelName || channelName,
                anomalyId: anomaly.id,
              });
              
              // 移除按钮和绘图元素
              this.destroy();
              const editBtn = document.querySelector(`.edit-button-${anomaly.id}`);
              if (editBtn) {
                editBtn.remove();
              }
              chart.xAxis[0].removePlotBand(`band-${anomaly.id}`);
              chart.xAxis[0].removePlotBand(`band-end-${anomaly.id}`);
              const anomalySeries = chart.get(`anomaly-${anomaly.id}`);
              if (anomalySeries) {
                anomalySeries.remove();
              }
            },
            {
              fill: '#f56c6c',
              style: {
                color: 'white',
                fontWeight: 'bold',
                fontSize: '10px',
                textAlign: 'center',
                lineHeight: '6px',
                paddingTop: '0px',
                paddingLeft: '0px'
              },
              r: 5,
              width: 6,
              height: 6,
              zIndex: 10
            }
          )
          .attr({
            'class': `delete-button-${anomaly.id}`,
            'zIndex': 10
          })
          .css({
            cursor: 'pointer'
          })
          .add();
          
          // 添加编辑按钮 - 放在上方
          const editButton = chart.renderer.button(
            '✎',
            endX - 25,
            y - 28,
            function() {
              const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
              const storedAnomaly = storedAnomalies.find(a => a.id === anomaly.id);
              
              if (storedAnomaly) {
                Object.assign(currentAnomaly, {
                  ...storedAnomaly,
                  channelName: channelName
                });
              } else {
                Object.assign(currentAnomaly, {
                  ...anomaly,
                  channelName: channelName
                });
              }
              
              showAnomalyForm.value = true;
            },
            {
              fill: '#409eff',
              style: {
                color: 'white',
                fontWeight: 'bold',
                fontSize: '10px',
                textAlign: 'center',
                lineHeight: '6px',
                paddingTop: '0px',
                paddingLeft: '0px'
              },
              r: 5,
              width: 6,
              height: 6,
              zIndex: 10
            }
          )
          .attr({
            'class': `edit-button-${anomaly.id}`,
            'zIndex': 10
          })
          .css({
            cursor: 'pointer'
          })
          .add();
          
          // 确保按钮在最顶层
          deleteButton.toFront();
          editButton.toFront();
          
          // 重绘图表以显示新添加的元素
          chart.redraw();
          
          // 立即打开编辑表单
          Object.assign(currentAnomaly, {
            ...anomaly,
            channelName: channelName
          });
          
          // 确保表单显示
          showAnomalyForm.value = true;
        }
      });

      // 添加图例文字
      if (chart && chart.renderer) {
        chart.renderer.text(
          `${channelNumber} | ${shotNumber} (${data.originalFrequency.toFixed(2)}KHz -> ${(sampling.value).toFixed(2)}KHz)`,
          110,
          30
        )
        .css({
          color: color,
          fontSize: '1.0em',
          fontWeight: 'bold'
        })
        .add();
      }

      performance.mark(`Draw Chart ${channelName}-end`);
      performance.measure(`Draw Chart ${channelName}`,
        `Draw Chart ${channelName}-start`,
        `Draw Chart ${channelName}-end`);

      // 存储图表实例
      window.chartInstances = window.chartInstances || {};
      window.chartInstances[channelName] = chart;

      resolve();
    } catch (error) {
      console.error('Error in drawChart:', error);
      reject(error);
    }
  });
};

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
  left: 60px;
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

