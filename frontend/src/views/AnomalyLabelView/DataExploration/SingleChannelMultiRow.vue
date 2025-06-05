<template>
  <div class="chart-container">
    <div>
      <div class="chart-wrapper" v-for="(channel, index) in selectedChannels" :key="channel.channel_name + '_' + channel.shot_number">
        <div :id="'chart-' + channel.channel_name + '_' + channel.shot_number" :ref="el => channelSvgElementsRefs[index] = el" :style="{
          opacity: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 1 : 0,
          transition: 'opacity 0.5s ease',
          position: 'relative',
          height: '250px'
        }"></div>

        <!-- 简约环形进度条，放置在图表中心 -->
        <div v-show="loadingStates[channel.channel_name + '_' + channel.shot_number] !== 100 ||
          renderingStates[channel.channel_name + '_' + channel.shot_number] !== 100" class="circular-progress-wrapper">
          <el-progress type="circle" :percentage="getProgressPercentage(channel.channel_name + '_' + channel.shot_number)" :width="80" :stroke-width="6" :format="percent => `${percent}%`" :status="loadingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? '' : 'warning'" :color="loadingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? '#409EFF' : ''" />
          <div class="loading-stage-text">
            {{ getLoadingStageText(channel.channel_name + '_' + channel.shot_number) }}
          </div>
        </div>

        <!-- 添加耗时显示 -->
        <!-- <div v-if="renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 && 
                  channelTimings[channel.channel_name + '_' + channel.shot_number]?.duration" 
             class="timing-info">
          处理耗时: {{ channelTimings[channel.channel_name + '_' + channel.shot_number].duration }}秒
        </div> -->

        <div class="color-picker-container" :style="{
          opacity: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 1 : 0,
          visibility: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 'visible' : 'hidden',
          transition: 'opacity 0.5s ease'
        }" v-show="renderingStates[channel.channel_name + '_' + channel.shot_number] === 100">
          <ChannelColorPicker :key="channel.channel_name + '_' + channel.shot_number + '_' + channel.color" :color="channel.color" :predefineColors="predefineColors" @change="updateChannelColor(channel)" @update:color="updateChartColor(channel, $event)" :channelName="channel.channel_name" :shotNumber="channel.shot_number" />
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
import 'highcharts/modules/accessibility';
import debounce from 'lodash/debounce';
import { ref, reactive, watch, computed, onMounted, nextTick, onUnmounted, toRaw, onActivated, onDeactivated } from 'vue';
import { ElDialog, ElForm, ElFormItem, ElInput, ElButton, ElMessage } from 'element-plus';
import { useStore } from 'vuex';
import ChannelColorPicker from '@/components/ChannelColorPicker.vue';
import { dataCache } from '@/services/cacheManager';

// 设置Highcharts全局配置
Highcharts.setOptions({
  accessibility: {
    enabled: false // 禁用无障碍功能，避免相关错误
  }
});


// 添加预定义颜色数组
const predefineColors = [
  '#000000', '#4169E1', '#DC143C', '#228B22', '#FF8C00',
  '#800080', '#FF1493', '#40E0D0', '#FFD700', '#8B4513',
  '#2F4F4F', '#1E90FF', '#32CD32', '#FF6347', '#DA70D6',
  '#191970', '#FA8072', '#6B8E23', '#6A5ACD', '#FF7F50',
  '#4682B4',
];

const currentAnomaly = reactive({});
const showAnomalyForm = ref(false);
const store = useStore();
const selectedChannels = computed(() => store.state.selectedChannels);
const sampling = computed(() => store.state.sampling);
const smoothnessValue = computed(() => store.state.smoothness);
const channelSvgElementsRefs = computed(() => store.state.channelSvgElementsRefs);
const isBoxSelect = computed(() => store.state.isBoxSelect);
// 添加FFT显示状态的计算属性
const showFFT = computed(() => store.state.showFFT);
const domains = computed(() => ({
  x: store.state.xDomains,
  y: store.state.yDomains
}));
const chartContainerWidth = ref(0);
const matchedResults = computed(() => store.state.matchedResults);
const visibleMatchedResultIds = computed(() => store.state.visibleMatchedResultIds);
// 只显示被选中的匹配结果
const filteredMatchedResults = computed(() => {
  if (!visibleMatchedResultIds.value || visibleMatchedResultIds.value.length === 0) {
    return [];
  }
  
  // 从ID中解析出原始索引
  const selectedOriginalIndices = visibleMatchedResultIds.value.map(id => {
    const parts = id.split('_');
    // 获取最后一部分作为原始索引
    return parseInt(parts[parts.length - 1], 10);
  });
  
  // 使用原始索引过滤匹配结果
  return matchedResults.value.filter((result, idx) => 
    selectedOriginalIndices.includes(idx)
  );
});
const matchedResultsCleared = computed(() => store.state.matchedResultsCleared);
// 添加一个标记，用于忽略初始化时的变化
const initialMatchedResultsClearedValue = ref(store.state.matchedResultsCleared);

// 添加FFT切换状态标记，避免重复处理
const isFFTSwitching = ref(false);

// 存储原始的显示范围
const originalDomains = ref({});
const channelDataCache = computed(() => store.state.channelDataCache);// 定义缓存对象

const loadingStates = reactive({});  // 用于存储每个通道的加载状态
const renderingStates = reactive({}); // 用于存储每个通道的渲染状态
// 用于跟踪已经渲染过的通道
const renderedChannels = ref(new Set());
// 添加一个用于存储通道加载和渲染耗时的对象
const channelTimings = reactive({});

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
        chart.xAxis[0].removePlotBand(`band-end-${anomaly.id}`);
        
        // 移除高亮系列
        const highlightSeries = chart.series.find(s => s.options.id === `anomaly-highlight-${anomaly.id}`);
        if (highlightSeries) {
          highlightSeries.remove(false);
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

// 引入Web Worker
let channelDataWorker = null;
if (window.Worker) {
  if (!window._channelDataWorkerInstance) {
    window._channelDataWorkerInstance = new Worker(new URL('@/workers/SingleChannelMultiRowDataWorker.js', import.meta.url), { type: 'module' });
  }
  channelDataWorker = window._channelDataWorkerInstance;
}

// 用Web Worker处理数据部分
function processChannelDataWithWorker(data, channel) {
  return new Promise((resolve, reject) => {
    if (!channelDataWorker) {
      // 不支持worker时，直接返回原始数据
      resolve({ ...data });
      return;
    }
    const handleMessage = (e) => {
      channelDataWorker.removeEventListener('message', handleMessage);
      if (e.data && !e.data.error) {
        resolve(e.data);
      } else {
        reject(e.data.error || 'Worker error');
      }
    };
    channelDataWorker.addEventListener('message', handleMessage);
    // 这里做深拷贝，去除响应式/Proxy
    const plainData = JSON.parse(JSON.stringify(data));
    const plainChannel = JSON.parse(JSON.stringify(channel));
    channelDataWorker.postMessage({ data: plainData, channel: plainChannel });
  });
}

// 修改processChannelData，数据处理部分用worker
const processChannelData = async (data, channel) => {
  const channelKey = `${channel.channel_name}_${channel.shot_number}`;
  try {
    renderingStates[channelKey] = 0;
    // 标记渲染开始
    renderingStates[channelKey] = 25;

    // 并行获取错误数据 - 不阻塞其他处理
    const errorDataPromise = channel.errors && channel.errors.length > 0
      ? store.dispatch('fetchAllErrorData', channel).catch(err => {
        console.warn('Failed to fetch error data:', err);
        return [];
      })
      : Promise.resolve([]);

    renderingStates[channelKey] = 40;

    // 用worker处理数据
    const processedData = await processChannelDataWithWorker(data, channel);

    // 获取错误数据
    const errorDataResults = await errorDataPromise;

    renderingStates[channelKey] = 75; // 更新渲染状态

    // 绘制图表，直接使用worker处理好的数据
    await nextTick();
    await drawChart(
      {
        X_value: processedData.X_value,
        Y_value: processedData.Y_value,
        originalFrequency: processedData.originalFrequency,
        stats: processedData.stats,
        is_digital: processedData.is_digital,
        Y_normalized: processedData.Y_normalized,
        channel_type: processedData.channel_type,
        // 添加FFT相关字段
        freq: processedData.freq,
        amplitude: processedData.amplitude
      },
      errorDataResults,
      channelKey,
      channel.color,
      processedData.X_unit || 's',
      processedData.Y_unit || 'Y',
      processedData.channel_type || channel.channel_type,
      channel.shot_number
    );

    renderingStates[channelKey] = 100;

    // 记录结束时间和计算耗时
    channelTimings[channelKey].endTime = performance.now();
    channelTimings[channelKey].duration = ((channelTimings[channelKey].endTime - channelTimings[channelKey].startTime) / 1000).toFixed(2);
    // 在渲染完成后，确保再次调整颜色选择器位置
    const chart = window.chartInstances?.[channelKey];
    if (chart) {
      adjustColorPickerPosition(chart, channel);
      requestAnimationFrame(() => adjustColorPickerPosition(chart, channel));
    }
  } catch (error) {
    console.error(`Error processing channel data for ${channel.channel_name}:`, error);
    ElMessage.error(`处理通道数据错误: ${error.message}`);
    renderingStates[channelKey] = 100;
    if (channelTimings[channelKey]) {
      channelTimings[channelKey].endTime = performance.now();
      channelTimings[channelKey].duration = ((channelTimings[channelKey].endTime - channelTimings[channelKey].startTime) / 1000).toFixed(2);
    }
  }
};

// 专门负责数据获取的函数
const fetchChannelData = async (channel, forceRefresh = false) => {
  try {
    if (!channel || !channel.channel_name || !channel.shot_number) {
      console.warn('Invalid channel data:', channel);
      return null;
    }
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;

    // 开始计时
    channelTimings[channelKey] = {
      startTime: performance.now(),
      endTime: null,
      duration: null
    };

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
      // console.log(`正在获取通道数据: ${channelKey}, 采样率: ${sampling.value} KHz, 强制刷新: ${forceRefresh}`);

      // 使用 store action 获取数据，传递forceRefresh参数
      const data = await store.dispatch('fetchChannelData', {
        channel,
        forceRefresh: forceRefresh // 传递强制刷新参数
      });

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

// keep-alive激活标志
const isActive = ref(true);
// 新增：记录激活时是否需要补渲染
const needRenderOnActivate = ref(false);

// 保存上一次的selectedChannels和sampling快照
const lastSelectedChannels = ref(JSON.stringify(toRaw(selectedChannels.value)));
const lastSampling = ref(sampling.value);

const samplingVersion = computed(() => store.state.samplingVersion);
const lastSamplingVersion = ref(samplingVersion.value);

onActivated(() => {
  if (samplingVersion.value !== lastSamplingVersion.value) {
    nextTick(() => {
      renderCharts();
    });
    lastSamplingVersion.value = samplingVersion.value;
    // 这里也可以顺便更新lastSelectedChannels
    lastSelectedChannels.value = JSON.stringify(toRaw(selectedChannels.value));
    lastSampling.value = sampling.value;
  }
  isActive.value = true;
  // 只有当selectedChannels或sampling发生变化时才重绘
  const currentChannels = JSON.stringify(toRaw(selectedChannels.value));
  const currentSampling = sampling.value;
  if (currentChannels !== lastSelectedChannels.value || currentSampling !== lastSampling.value) {
    nextTick(() => {
      renderCharts();
    });
    lastSelectedChannels.value = currentChannels;
    lastSampling.value = currentSampling;
  } else {
    // 只做reflow
    nextTick(() => {
      if (window.chartInstances) {
        Object.values(window.chartInstances).forEach(chart => {
          if (chart && typeof chart.reflow === 'function') {
            chart.reflow();
          }
        });
      }
    });
  }
  nextTick(() => {
    selectedChannels.value.forEach(channel => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const chart = window.chartInstances?.[channelKey];
      if (chart) {
        // 获取当前曲线颜色
        const currentColor = chart.series.find(s => s.options.id === 'original')?.color;
        // 如果颜色不一致，强制刷新
        if (currentColor && currentColor !== channel.color) {
          updateChartColor(channel, channel.color);
        }
      }
    });
  });
});
onDeactivated(() => {
  isActive.value = false;
});

// 监听selectedChannels的变化，处理移除的通道
watch(selectedChannels, (newChannels, oldChannels) => {
  if (!isActive.value) {
    // 只有有新通道时才设置 needRenderOnActivate
    const oldChannelKeys = new Set((oldChannels || []).map(ch => `${ch.channel_name}_${ch.shot_number}`));
    const newChannelKeys = new Set(newChannels.map(ch => `${ch.channel_name}_${ch.shot_number}`));
    const added = [...newChannelKeys].filter(k => !oldChannelKeys.has(k));
    if (added.length > 0) {
      needRenderOnActivate.value = true;
    }
    return;
  }
  if (!oldChannels) { return; }
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

  // 检查颜色变化的通道
  const colorChangedChannels = newChannels.filter(newCh => {
    const oldCh = oldChannels.find(ch =>
      ch.channel_name === newCh.channel_name &&
      ch.shot_number === newCh.shot_number
    );
    return oldCh && oldCh.color !== newCh.color;
  });

  // 处理颜色变化的通道
  colorChangedChannels.forEach(channel => {
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;
    // 如果图表已经渲染，直接更新颜色
    if (renderedChannels.value.has(channelKey)) {
      updateChartColor(channel, channel.color);
    }
  });

  // 只对新增通道或颜色变更的通道进行处理，每个通道独立处理
  if (addedChannelKeys.length > 0) {
    // 找出所有新增的通道
    const newAddedChannels = newChannels.filter(ch => {
      const key = `${ch.channel_name}_${ch.shot_number}`;
      return addedChannelKeys.includes(key);
    });
    // 并发渲染新增通道，每个通道单独处理，计时独立
    newAddedChannels.forEach(channel => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      loadingStates[channelKey] = 0;
      renderingStates[channelKey] = 0;
      (async () => {
        try {
          // 记录fetch开始时间
          channelTimings[channelKey] = channelTimings[channelKey] || {};
          channelTimings[channelKey].fetchStartTime = performance.now();

          const data = await fetchChannelData(channel);

          channelTimings[channelKey].fetchEndTime = performance.now();
          channelTimings[channelKey].fetchDuration = ((channelTimings[channelKey].fetchEndTime - channelTimings[channelKey].fetchStartTime) / 1000).toFixed(2);

          if (!data) return;

          // 记录process开始时间
          channelTimings[channelKey].processStartTime = performance.now();

          await processChannelData(data, channel);

          channelTimings[channelKey].processEndTime = performance.now();
          channelTimings[channelKey].processDuration = ((channelTimings[channelKey].processEndTime - channelTimings[channelKey].processStartTime) / 1000).toFixed(2);

          // 总耗时
          channelTimings[channelKey].totalDuration = ((channelTimings[channelKey].processEndTime - channelTimings[channelKey].fetchStartTime) / 1000).toFixed(2);

          renderedChannels.value.add(channelKey);
        } catch (error) {
          console.error(`Error rendering channel ${channelKey}:`, error);
        }
      })();
    });
    return;
  }
});

// 添加对domains的监听，当domains变化时更新图表的显示范围，但只更新y轴，不影响x轴
watch(() => domains.value, (newDomains, oldDomains) => {
  if (!isActive.value) return;
  // 遍历所有图表实例
  Object.keys(window.chartInstances || {}).forEach(channelKey => {
    const chart = window.chartInstances[channelKey];
    if (chart) {
      // 获取该通道的显示范围
      const yDomain = newDomains.y[channelKey];
      const oldYDomain = oldDomains?.y?.[channelKey];

      // 只有当当前通道的y轴domain发生变化时才更新图表
      const yDomainChanged = !oldYDomain ||
        yDomain?.[0] !== oldYDomain?.[0] ||
        yDomain?.[1] !== oldYDomain?.[1];

      // 如果有新的y轴显示范围且发生了变化，则更新图表
      if (yDomain && yDomainChanged) {
        // 只更新y轴，不影响x轴
        chart.yAxis[0].setExtremes(yDomain[0], yDomain[1], false);
        chart.redraw();
      }
    }
  });
});

// 添加对采样率的监听，当采样率变化时重新渲染所有图表
watch(() => sampling.value, (newSamplingRate, oldSamplingRate) => {
  if (!isActive.value) return;
  // console.log(`[重要] 采样率从 ${oldSamplingRate} 变更为 ${newSamplingRate} KHz，正在准备刷新图表`);

  // 更彻底的清理图表实例和缓存
  if (window.chartInstances) {
    Object.keys(window.chartInstances).forEach(key => {
      const chart = window.chartInstances[key];
      if (chart) {
        try {
          // 销毁图表实例
          chart.destroy();
          // console.log(`已销毁图表实例: ${key}`);
        } catch (e) {
          console.warn(`销毁图表实例失败: ${key} - ${e.message}`);
        }
      }
      delete window.chartInstances[key];
    });
  }

  // 清空已渲染标记
  renderedChannels.value.clear();
  // console.log('已清空渲染缓存标记，即将重新渲染所有图表');

  // 使用更长的延迟确保store中的数据已更新
  setTimeout(() => {
    // 强制重新渲染所有通道图表
    window.chartInstances = {}; // 重新初始化图表实例对象
    renderCharts(true);
    // console.log('已触发强制重新渲染');
  }, 500);
});

// 添加对channelDataCache的监听，当缓存数据发生变化时重新渲染图表
watch(() => channelDataCache.value, () => {
  if (!isActive.value) return;
  // 仅当已经有通道被选择时才重新渲染
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    // console.log('数据缓存已更新，重新渲染图表');
    // 清空已渲染标记，以便所有通道都能重新渲染
    renderedChannels.value.clear();
    // 使用timeout以确保状态已完全更新
    setTimeout(() => {
      renderCharts(true);
    }, 300);
  }
}, { deep: true });

// 添加对brush_begin和brush_end的监听，当它们变化时更新所有图表的横坐标范围
watch([brush_begin, brush_end], ([newBegin, newEnd]) => {
  if (!isActive.value) return;
  // 解析为数值
  const beginValue = parseFloat(newBegin);
  const endValue = parseFloat(newEnd);
  // 遍历所有图表实例，更新横坐标范围
  Object.keys(window.chartInstances || {}).forEach(channelKey => {
    const chart = window.chartInstances[channelKey];
    if (chart) {
      // 只更新横坐标，不影响纵坐标
      chart.xAxis[0].setExtremes(beginValue, endValue, false);
      // 保存当前的横坐标范围到store
      store.dispatch('updateDomains', {
        channelName: channelKey,
        xDomain: [beginValue, endValue],
      });

      // 更新匹配高亮线条
      updateMatchedHighlights(chart, channelKey);

      chart.redraw();
    }
  });
});

// 在组件挂载时添加监听器
onMounted(async () => {
  const container = document.querySelector('.chart-container');
  if (container) {
    chartContainerWidth.value = container.offsetWidth;
  }

  // 添加窗口大小变化的监听器
  window.addEventListener('resize', handleResize);

  nextTick(() => {
    if (selectedChannels.value && selectedChannels.value.length > 0) {
      renderCharts();
    }
  });
});

// 在组件卸载时移除监听器
onUnmounted(() => {
  // 移除窗口大小变化的监听器
  window.removeEventListener('resize', handleResize);
});

// 处理窗口大小变化
const handleResize = debounce(() => {
  // 获取当前容器宽度
  const container = document.querySelector('.chart-container');
  if (container) {
    chartContainerWidth.value = container.offsetWidth;
  }

  // 重新调整所有颜色选择器的位置（立即调整一次）
  selectedChannels.value.forEach(channel => {
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;
    const chart = window.chartInstances?.[channelKey];
    if (chart) {
      adjustColorPickerPosition(chart, channel);
    }
  });

  // 短暂延迟后再次调整，确保DOM已完全更新
  setTimeout(() => {
    selectedChannels.value.forEach(channel => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const chart = window.chartInstances?.[channelKey];
      if (chart) {
        adjustColorPickerPosition(chart, channel);
      }
    });
  }, 100);
}, 100); // 减少去抖时间，使响应更快速

// 添加解码函数
const decodeChineseText = (text) => {
  if (!text) return '';
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
    store.dispatch('updateAnomaly', payload);
    const chart = window.chartInstances?.[payload.channelName];
    if (chart) {
      // 更新plotBand
      const plotBand = chart.xAxis[0].plotLinesAndBands.find(band => band.id === `band-${currentAnomaly.id}`);
      if (plotBand) {
        plotBand.options.events = {};
        chart.xAxis[0].removePlotBand(`band-${currentAnomaly.id}`);
        chart.xAxis[0].addPlotBand({
          id: `band-${currentAnomaly.id}`,
          from: currentAnomaly.startX,
          to: currentAnomaly.endX,
          color: 'rgba(255, 0, 0, 0.2)',
          borderColor: 'red',
          borderWidth: 1,
          zIndex: 5,
          label: {
            text: `${currentAnomaly.startX.toFixed(3)}`,
            align: 'left',
            verticalAlign: 'top',
            y: -25,
            style: {
              color: '#606060',
              fontWeight: 'bold',
              fontSize: '10px'
            }
          }
        });
      }

      // 更新高亮线条
      const highlightSeries = chart.series.find(s => s.options.id === `anomaly-highlight-${currentAnomaly.id}`);
      if (highlightSeries) {
        highlightSeries.remove(false);
      }

      // 获取异常区域内的数据点
      const data = channelDataCache.value[payload.channelName];
      if (data) {
        const pointsInRange = [];
        const startX = currentAnomaly.startX;
        const endX = currentAnomaly.endX;

        // 找到区间内的所有点
        for (let i = 0; i < data.X_value.length; i++) {
          if (data.X_value[i] >= startX && data.X_value[i] <= endX) {
            pointsInRange.push([data.X_value[i], data.Y_value[i]]);
          }
        }

        // 如果没有足够点，添加区间端点
        if (pointsInRange.length < 2) {
          // 找到最接近区间边界的点
          let startIdx = -1;
          let endIdx = -1;
          let minStartDiff = Infinity;
          let minEndDiff = Infinity;

          for (let i = 0; i < data.X_value.length; i++) {
            const startDiff = Math.abs(data.X_value[i] - startX);
            const endDiff = Math.abs(data.X_value[i] - endX);

            if (startDiff < minStartDiff) {
              minStartDiff = startDiff;
              startIdx = i;
            }

            if (endDiff < minEndDiff) {
              minEndDiff = endDiff;
              endIdx = i;
            }
          }

          if (startIdx !== -1) {
            pointsInRange.push([startX, data.Y_value[startIdx]]);
          }

          if (endIdx !== -1) {
            pointsInRange.push([endX, data.Y_value[endIdx]]);
          }
        }

        // 确保点按X轴排序
        pointsInRange.sort((a, b) => a[0] - b[0]);

        // 添加高亮线条
        if (pointsInRange.length > 0) {
          chart.addSeries({
            id: `anomaly-highlight-${currentAnomaly.id}`,
            name: `异常区域-${currentAnomaly.id}`,
            data: pointsInRange,
            color: 'rgba(255, 0, 0, 0)',
            lineWidth: 2,
            zIndex: 10,
            marker: {
              enabled: false
            },
            states: {
              hover: {
                lineWidthPlus: 0
              }
            },
            enableMouseTracking: false,
            showInLegend: false
          });
        }
      }

      chart.redraw();
    }
    // 关闭编辑框
    showAnomalyForm.value = false;
    ElMessage.success('异常标注信息已保存');
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
    const chart = window.chartInstances?.[currentAnomaly.channelName];
    if (chart) {
      // 删除高亮线条
      const highlightSeries = chart.series.find(s => s.options.id === `anomaly-highlight-${currentAnomaly.id}`);
      if (highlightSeries) {
        highlightSeries.remove(false);
      }
    }

    store.dispatch('deleteAnomaly', {
      channelName: currentAnomaly.channelName,
      anomalyId: currentAnomaly.id
    });
    showAnomalyForm.value = false;
    ElMessage.success('异常标注已删除');
    Object.keys(currentAnomaly).forEach((key) => {
      delete currentAnomaly[key];
    });
  }
};

// 添加进度百分比计算函数
const getProgressPercentage = (channelKey) => {
  const loadingTotal = Number(loadingStates[channelKey]) || 0;
  const renderingTotal = Number(renderingStates[channelKey]) || 0;
  if (loadingTotal === 100) {
    if (renderingTotal === 0) {
      return 50;
    }
    return 50 + renderingTotal / 2;
  }
  return loadingTotal / 2;
};

// 添加获取加载阶段文本的函数
const getLoadingStageText = (channelKey) => {
  const loadingTotal = Number(loadingStates[channelKey]) || 0;
  const renderingTotal = Number(renderingStates[channelKey]) || 0;
  const channelName = channelKey.split('_')[0];
  const shotNumber = channelKey.split('_')[1];
  
  // 如果渲染完成，显示耗时
  if (renderingTotal === 100 && channelTimings[channelKey] && channelTimings[channelKey].duration) {
    return `加载完成 (耗时 ${channelTimings[channelKey].duration}秒)`;
  }
  
  if (loadingTotal < 100) {
    return `正在加载通道 ${channelName}|${shotNumber}`;
  } else if (renderingTotal === 0) {
    return `准备处理通道 ${channelName}|${shotNumber}`;
  } else if (renderingTotal === 25) {
    return `正在准备数据`;
  } else if (renderingTotal === 40) {
    return `正在处理数据`;
  } else if (renderingTotal === 75) {
    return `正在渲染图表`;
  } else if (renderingTotal === 100) {
    return `加载完成`;
  } else {
    return `处理中 ${renderingTotal}%`;
  }
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
      chart.xAxis[0].plotLinesAndBands.forEach(band => {
        if (band.id && band.id.startsWith('band-')) {
          const anomalyId = band.id.replace('band-', '');
          const anomaly = chart.series.find(s => s.options.id === `anomaly-${anomalyId}`);

          if (anomaly && !anomaly.options.custom?.isStored) {
            band.options.events = newValue ? {
              click: function () {
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

const drawChart = (data, errorsData, channelName, color, xUnit, yUnit, channelType, shotNumber) => {
  return new Promise((resolve, reject) => {
    try {

      // 保持原始频率值不变
      const freqValue = data.originalFrequency;
      // console.log(`通道 ${channelName} 的最终频率值:`, freqValue);

      // 添加防抖检查
      const chartKey = `${channelName}-${color}-${sampling.value}-${smoothnessValue.value}`;
      if (chartKey === drawChart.lastDrawnChart) {
        resolve();
        return;
      }
      drawChart.lastDrawnChart = chartKey;

      performance.mark(`Draw Chart ${channelName}-start`);

      // 构建图表配置
      const chartContainer = document.getElementById(`chart-${channelName}`);
      if (!chartContainer) {
        reject(new Error(`Chart container for ${channelName} not found`));
        return;
      }

      // 准备数据，过滤无效数据点
      const originalData = [];
      for (let i = 0; i < data.X_value.length; i++) {
        if (isFinite(data.X_value[i]) && isFinite(data.Y_value[i])) {
          originalData.push([data.X_value[i], data.Y_value[i]]);
        }
      }

      // 使用后端提供的统计数据设置Y轴范围
      const stats = data.stats || {};

      // 使用后端计算的Y轴范围 (如果有)，否则计算默认值
      // 使用安全的方式计算Y值范围，避免栈溢出
      const safeYMin = data.Y_value.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
      const safeYMax = data.Y_value.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
      const finalYMin = isFinite(safeYMin) ? safeYMin : 0;
      const finalYMax = isFinite(safeYMax) ? safeYMax : 1;
      const yRange = finalYMax - finalYMin;
      
      const yMin = stats.y_axis_min !== undefined ? stats.y_axis_min :
        finalYMin - yRange * 0.2;
      const yMax = stats.y_axis_max !== undefined ? stats.y_axis_max :
        finalYMax + yRange * 0.2;

      // 设置X轴和Y轴范围
      let xDomain, yDomain;
      let originalTimeDomain, originalFreqDomain;
      
      if (showFFT.value && data.freq && data.amplitude) {
        // FFT模式下使用频率范围
        // 使用安全的方式计算最小值和最大值，避免栈溢出
        const safeFreqMin = data.freq.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
        const safeFreqMax = data.freq.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
        const finalFreqMin = isFinite(safeFreqMin) ? safeFreqMin : 0;
        const finalFreqMax = isFinite(safeFreqMax) ? safeFreqMax : 1000;
        
        xDomain = domains.value.x[channelName] || [finalFreqMin, finalFreqMax];
        
        // FFT幅值处理：确保合理的Y轴范围
        const safeAmpMax = data.amplitude.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
        const safeAmpMin = data.amplitude.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
        const ampMax = isFinite(safeAmpMax) ? safeAmpMax : 1;
        const ampMin = isFinite(safeAmpMin) ? safeAmpMin : 0;
        
        let yMin_fft = Math.max(0, ampMin); // FFT通常从0开始
        let yMax_fft = ampMax;
        
        // 如果最大值很小，调整范围
        if (ampMax < 1e-6) {
          yMax_fft = ampMax * 2;
        } else if (ampMax < 0.001) {
          yMax_fft = ampMax * 1.2;
        } else {
          yMax_fft = ampMax * 1.1;
        }
        
        // 如果有负值（理论上FFT幅值不应该有负值，但为了安全起见）
        if (ampMin < 0) {
          yMin_fft = ampMin * 1.1;
        }
        
        // 确保Y轴范围是有效的
        if (!isFinite(yMin_fft) || !isFinite(yMax_fft) || yMin_fft >= yMax_fft) {
          yMin_fft = 0;
          yMax_fft = 1;
        }
        
        yDomain = domains.value.y[channelName] || [yMin_fft, yMax_fft];
        
        // 保存FFT模式的原始范围
        originalFreqDomain = {
          x: [finalFreqMin, finalFreqMax],
          y: [yMin_fft, yMax_fft]
        };
        
        // 保存时域原始范围（用于模式切换）
        const safeXMin = data.X_value.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
        const safeXMax = data.X_value.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
        const finalXMin = isFinite(safeXMin) ? safeXMin : (stats.x_min !== undefined ? stats.x_min : 0);
        const finalXMax = isFinite(safeXMax) ? safeXMax : (stats.x_max !== undefined ? stats.x_max : 1);
        
        originalTimeDomain = {
          x: stats.x_min !== undefined && stats.x_max !== undefined ?
            [stats.x_min, stats.x_max] : [finalXMin, finalXMax],
          y: [yMin, yMax]
        };
      } else {
        // 原始数据模式
        // 使用安全的方式计算最小值和最大值
        const safeXMin = data.X_value.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
        const safeXMax = data.X_value.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
        const finalXMin = isFinite(safeXMin) ? safeXMin : (stats.x_min !== undefined ? stats.x_min : 0);
        const finalXMax = isFinite(safeXMax) ? safeXMax : (stats.x_max !== undefined ? stats.x_max : 1);
        
        xDomain = domains.value.x[channelName] ||
          (stats.x_min !== undefined && stats.x_max !== undefined ?
            [stats.x_min, stats.x_max] : [finalXMin, finalXMax]);
        yDomain = domains.value.y[channelName] || [yMin, yMax];
        
        // 保存时域原始范围
        originalTimeDomain = {
          x: stats.x_min !== undefined && stats.x_max !== undefined ?
            [stats.x_min, stats.x_max] : [finalXMin, finalXMax],
          y: [yMin, yMax]
        };
        
        // 如果有FFT数据，也保存FFT原始范围
        if (data.freq && data.amplitude) {
          const safeAmpMax = data.amplitude.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
          const safeAmpMin = data.amplitude.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
          const ampMax = isFinite(safeAmpMax) ? safeAmpMax : 1;
          const ampMin = isFinite(safeAmpMin) ? safeAmpMin : 0;
          let yMin_fft = Math.max(0, ampMin);
          let yMax_fft = ampMax * 1.1;
          
          const safeFreqMin = data.freq.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
          const safeFreqMax = data.freq.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
          const finalFreqMin = isFinite(safeFreqMin) ? safeFreqMin : 0;
          const finalFreqMax = isFinite(safeFreqMax) ? safeFreqMax : 1000;
          
          // 确保FFT Y轴范围是有效的
          if (!isFinite(yMin_fft) || !isFinite(yMax_fft) || yMin_fft >= yMax_fft) {
            yMin_fft = 0;
            yMax_fft = 1;
          }
          
          originalFreqDomain = {
            x: [finalFreqMin, finalFreqMax],
            y: [yMin_fft, yMax_fft]
          };
        }
      }

      // 使用后端判断是否为数字信号
      const isDigitalSignal = data.is_digital === true;

      // 处理错误数据
      const errorRanges = []; // 存储所有错误区间
      const errorPlotLines = []; // 存储所有错误区间边界线配置
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
                      const startTime = xRange[0];
                      const endTime = xRange[1];
                      // 保存错误区间
                      errorRanges.push([startTime, endTime, isPerson]);

                      // Highcharts 支持的虚线样式: 'Solid', 'ShortDash', 'ShortDot', 'ShortDashDot', 

                      const leftBorderLine = {
                        id: `error-line-start-${groupIndex}-${personIndex}-${errorIndex}-${rangeIndex}`,
                        value: startTime,
                        color: 'rgba(255, 0, 0, 0)',
                        width: 1,
                        dashStyle: isPerson ? 'Solid' : 'ShortDot', // 使用 'Dot' 样式
                        zIndex: 1,
                        label: {
                          text: '',
                          style: {
                            color: 'transparent'
                          }
                        }
                      };

                      const rightBorderLine = {
                        id: `error-line-end-${groupIndex}-${personIndex}-${errorIndex}-${rangeIndex}`,
                        value: endTime,
                        color: 'rgba(255, 0, 0, 0)',
                        width: 1,
                        dashStyle: isPerson ? 'Solid' : 'ShortDot', // 使用 'Dot' 样式
                        zIndex: 1,
                        label: {
                          text: '',
                          style: {
                            color: 'transparent'
                          }
                        }
                      };

                      // 保存边界线配置，稍后添加到 plotLines
                      errorPlotLines.push(leftBorderLine, rightBorderLine);
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

      // 创建高亮矩形函数
      const getPlotBands = () => {
        const plotBands = [];

        // 异常区域绘制为plotBands
        if (channelAnomalies && channelAnomalies.length > 0) {
          channelAnomalies.forEach(anomaly => {
            // 为每个异常添加背景区域
            plotBands.push({
              id: `band-${anomaly.id}`,
              from: anomaly.startX,
              to: anomaly.endX,
              color: anomaly.isStored ? 'rgba(255, 0, 0, 0.2)' : 'rgba(255, 165, 0, 0.2)',
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
                click: function () {
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

        // 添加错误区间高亮（只添加填充区域，边界线通过 plotLines 添加）
        if (errorRanges && errorRanges.length > 0) {
          errorRanges.forEach((range, index) => {
            const startTime = range[0];
            const endTime = range[1];
            const isPerson = range[2];

            // 添加填充区域
            plotBands.push({
              id: `error-band-${index}`,
              from: startTime,
              to: endTime,
              color: 'rgba(255, 0, 0, 0.1)',
              zIndex: 1, // 确保在异常区域下方
            });
          });
        }

        return plotBands;
      };

      // 创建图表
      const chart = Highcharts.chart(`chart-${channelName}`, {
        chart: {
          height: 260,
          zoomType: isBoxSelect.value ? 'x' : 'xy', // 允许FFT模式下的缩放，只在框选模式下限制为x轴
          animation: false,
          spacing: [0, 15, 10, 10], // 添加统一的内部间距 [top, right, bottom, left]
          marginLeft: 120, // 增大左边距，防止Y轴标签溢出
          resetZoomButton: {
            enabled: false,
            theme: {
              style: {
                display: 'none'
              }
            },
            position: {
              x: -9999,
              y: -9999
            }
          },
          events: {
            selection: function (event) {
              // 确保在框选模式下只处理框选，不处理缩放
              if (isBoxSelect.value) {
                // FFT模式下禁用异常标注功能，但允许缩放
                if (showFFT.value) {
                  // FFT模式下只允许缩放，不允许异常标注
                  if (event.xAxis) {
                    const [xMin, xMax] = [event.xAxis[0].min, event.xAxis[0].max];
                    const [yMin, yMax] = event.yAxis ? [event.yAxis[0].min, event.yAxis[0].max] : [chart.yAxis[0].min, chart.yAxis[0].max];

                    // 保存FFT模式的原始范围（如果还没有保存）
                    if (!originalDomains.value[channelName]) {
                      originalDomains.value[channelName] = {};
                    }
                    if (!originalDomains.value[channelName].freq) {
                      // 从图表获取当前的完整范围作为原始FFT范围
                      const fullXMin = chart.xAxis[0].dataMin;
                      const fullXMax = chart.xAxis[0].dataMax;
                      const fullYMin = chart.yAxis[0].dataMin;
                      const fullYMax = chart.yAxis[0].dataMax;
                      originalDomains.value[channelName].freq = {
                        x: [fullXMin, fullXMax],
                        y: [fullYMin, fullYMax]
                      };
                    }

                    // 更新store中的范围
                    store.dispatch('updateDomains', {
                      channelName,
                      xDomain: [xMin, xMax],
                      yDomain: [yMin, yMax]
                    });
                    
                    // 允许默认的缩放行为
                    return true;
                  }
                  return false;
                }
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
                      click: function () {
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

                  // 添加高亮线条，使异常区域更加精确
                  const pointsInRange = [];
                  const startX = anomaly.startX;
                  const endX = anomaly.endX;

                  // 获取当前通道的数据
                  const dbSuffixPart = store.state.currentDbSuffix ? `_db_${store.state.currentDbSuffix}` : '';
                  const cacheKey = `${channelName}${dbSuffixPart}`;
                  const cached = dataCache.get(cacheKey);
                  const channelData = cached?.data;
                  if (channelData && channelData.X_value && channelData.Y_value) {
                    // 找到区间内的所有点
                    for (let i = 0; i < channelData.X_value.length; i++) {
                      if (channelData.X_value[i] >= startX && channelData.X_value[i] <= endX) {
                        pointsInRange.push([channelData.X_value[i], channelData.Y_value[i]]);
                      }
                    }

                    // 如果没有足够点，添加区间端点
                    if (pointsInRange.length < 2) {
                      // 找到最接近区间边界的点
                      let startIdx = -1;
                      let endIdx = -1;
                      let minStartDiff = Infinity;
                      let minEndDiff = Infinity;

                      for (let i = 0; i < channelData.X_value.length; i++) {
                        const startDiff = Math.abs(channelData.X_value[i] - startX);
                        const endDiff = Math.abs(channelData.X_value[i] - endX);

                        if (startDiff < minStartDiff) {
                          minStartDiff = startDiff;
                          startIdx = i;
                        }

                        if (endDiff < minEndDiff) {
                          minEndDiff = endDiff;
                          endIdx = i;
                        }
                      }

                      if (startIdx !== -1) {
                        pointsInRange.push([startX, channelData.Y_value[startIdx]]);
                      }

                      if (endIdx !== -1) {
                        pointsInRange.push([endX, channelData.Y_value[endIdx]]);
                      }
                    }

                    // 确保点按X轴排序
                    pointsInRange.sort((a, b) => a[0] - b[0]);

                    // 添加高亮线条
                    if (pointsInRange.length > 0) {
                      chart.addSeries({
                        id: `anomaly-highlight-${anomaly.id}`,
                        name: `异常区域-${anomaly.id}`,
                        data: pointsInRange,
                        color: 'rgba(255, 165, 0, 0.8)',
                        lineWidth: 2,
                        zIndex: 10,
                        marker: {
                          enabled: false
                        },
                        states: {
                          hover: {
                            lineWidthPlus: 0
                          }
                        },
                        enableMouseTracking: false,
                        showInLegend: false
                      });
                    }
                  }

                  const anomalyEndX = chart.xAxis[0].toPixels(anomaly.endX);
                  const buttonWidth = 6;
                  const buttonX = anomalyEndX - buttonWidth - 5;
                  const deleteButton = chart.renderer.button(
                    '×',
                    buttonX,
                    163,
                    function () {
                      // 删除异常
                      store.dispatch('deleteAnomaly', {
                        channelName: anomaly.channelName || channelName,
                        anomalyId: anomaly.id,
                      });
                      this.destroy();
                      const editBtn = document.querySelector(`.edit-button-${anomaly.id}`);
                      if (editBtn) {
                        editBtn.remove();
                      }
                      // 只移除plotBands，不再有系列需要移除
                      chart.xAxis[0].removePlotBand(`band-${anomaly.id}`);
                      chart.xAxis[0].removePlotBand(`band-end-${anomaly.id}`);

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
                      width: buttonWidth,
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
                    buttonX,
                    188,
                    function () {
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
                      width: buttonWidth,
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

                  chart.redraw();

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
                  const [yMin, yMax] = event.yAxis ? [event.yAxis[0].min, event.yAxis[0].max] : [chart.yAxis[0].min, chart.yAxis[0].max];

                  // 保存原始范围（如果还没有保存）
                  if (!originalDomains.value[channelName]) {
                    originalDomains.value[channelName] = {};
                  }
                  
                  if (showFFT.value) {
                    // FFT模式下保存频域原始范围
                    if (!originalDomains.value[channelName].freq) {
                      const fullXMin = chart.xAxis[0].dataMin;
                      const fullXMax = chart.xAxis[0].dataMax;
                      const fullYMin = chart.yAxis[0].dataMin;
                      const fullYMax = chart.yAxis[0].dataMax;
                      originalDomains.value[channelName].freq = {
                        x: [fullXMin, fullXMax],
                        y: [fullYMin, fullYMax]
                      };
                    }
                  } else {
                    // 时域模式下保存时域原始范围
                    if (!originalDomains.value[channelName].time) {
                      const fullXMin = chart.xAxis[0].dataMin;
                      const fullXMax = chart.xAxis[0].dataMax;
                      const fullYMin = chart.yAxis[0].dataMin;
                      const fullYMax = chart.yAxis[0].dataMax;
                      originalDomains.value[channelName].time = {
                        x: [fullXMin, fullXMax],
                        y: [fullYMin, fullYMax]
                      };
                    }
                  }

                  // 更新store中的范围
                  store.dispatch('updateDomains', {
                    channelName,
                    xDomain: [xMin, xMax],
                    yDomain: [yMin, yMax]
                  });
                  // 允许默认的缩放行为
                  return true;
                }
              }
            },
            // 添加双击事件处理
            click: function (event) {
              // 检查是否是双击（计算两次点击之间的时间间隔）
              const now = new Date().getTime();
              const lastClick = this.lastClickTime || 0;
              this.lastClickTime = now;

              if (now - lastClick < 300) { // 如果两次点击间隔小于300毫秒，认为是双击
                // 根据当前FFT状态选择正确的原始范围
                const currentOriginalDomains = originalDomains.value[channelName];
                let targetDomain;
                
                if (showFFT.value) {
                  // FFT模式下恢复到频域范围
                  targetDomain = currentOriginalDomains?.freq;
                  // 如果没有保存的频域范围，使用图表的数据范围
                  if (!targetDomain) {
                    targetDomain = {
                      x: [this.xAxis[0].dataMin, this.xAxis[0].dataMax],
                      y: [this.yAxis[0].dataMin, this.yAxis[0].dataMax]
                    };
                  }
                } else {
                  // 时域模式下恢复到时域范围
                  targetDomain = currentOriginalDomains?.time;
                  // 如果没有保存的时域范围，使用图表的数据范围
                  if (!targetDomain) {
                    targetDomain = {
                      x: [this.xAxis[0].dataMin, this.xAxis[0].dataMax],
                      y: [this.yAxis[0].dataMin, this.yAxis[0].dataMax]
                    };
                  }
                }
                
                if (targetDomain) {
                  // 恢复到对应模式的范围
                  const [xMin, xMax] = targetDomain.x;
                  const [yMin, yMax] = targetDomain.y;

                  // 设置坐标轴范围
                  this.xAxis[0].setExtremes(xMin, xMax);
                  this.yAxis[0].setExtremes(yMin, yMax);

                  // 更新store中的范围
                  store.dispatch('updateDomains', {
                    channelName,
                    xDomain: [xMin, xMax],
                    yDomain: [yMin, yMax]
                  });
                }
              }
            },
          },
          accessibility: {
            enabled: false // 禁用无障碍功能，避免相关错误
          },
        },
        // 添加自定义属性，存储原始频率信息
        custom: {
          originalFrequency: freqValue,
          channelName: channelName,
          shotNumber: shotNumber,
          color: color
        },
        title: {
          text: showFFT.value ? 
            `${channelName || channelName.split('_')[0]} - FFT` :
            `${channelName || channelName.split('_')[0]} (${freqValue ? freqValue.toFixed(2) : '?'}KHz -> ${(sampling.value).toFixed(2)}KHz)`,
          align: 'right',
          x: -10, // 向左偏移10像素，使其位于右上角
          y: 60,  // 向下偏移20像素，确保在图表内部
          style: {
            color: color,
            fontSize: '1.0em',
            fontWeight: 'medium'
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
            text: showFFT.value ? 'Frequency (Hz)' : '',
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
          gridLineColor: '#ccc',
        },
        yAxis: {
          min: yDomain[0],
          max: yDomain[1],
          // 添加刻度控制，避免重复标签
          tickAmount: 6, // 限制刻度数量
          minTickInterval: (() => {
            const range = yDomain[1] - yDomain[0];
            if (range < 0.001) {
              return range / 10;
            } else if (range < 0.1) {
              return range / 20;
            } else if (range < 10) {
              return range / 20;
            } else {
              return range / 20;
            }
          })(), // 动态设置最小刻度间隔
          allowDecimals: true,
          startOnTick: false,
          endOnTick: false,
          title: {
            text: showFFT.value ? 'Amplitude' : yUnit,
            align: 'middle', // 居中对齐
            margin: 15, // 增加标题与轴的距离
            style: {
              fontSize: '1.05em',
              fontWeight: 'bold'
            }
          },
          labels: {
            align: 'right', // 右对齐
            x: -10, // 向左偏移10像素
            y: 4, // 微调垂直位置
            style: {
              fontSize: '1em',
              fontWeight: 'bold',
              textAlign: 'right' // 确保文本右对齐
            },
            reserveSpace: true, // 保留固定空间
            padding: 5, // 添加内边距
            formatter: function () {
              const value = this.value;
              const absValue = Math.abs(value);
              
              // 处理极小值和零值
              if (absValue === 0) {
                return '0';
              }
              
              // 使用科学计数法表示非常小的数值
              if (absValue < 0.001) {
                return value.toExponential(1);
              }
              
              // 根据数值大小选择不同的精度
              if (absValue < 0.1) {
                return value.toFixed(3);
              } else if (absValue < 1) {
                return value.toFixed(2);
              } else if (absValue < 10) {
                return value.toFixed(1);
              } else if (absValue < 100) {
                return value.toFixed(1);
              } else if (absValue < 1000) {
                return value.toFixed(0);
              } else {
                return value.toExponential(2);
              }
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
          formatter: function () {
            return `( ${this.x.toFixed(3)}, ${this.y.toFixed(3)} )`;
          },
          positioner: function (labelWidth, labelHeight, point) {
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
            fontSize: '12px',
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
        exporting: {
          enabled: false
        },
        series: [
          {
            id: 'original',
            type: 'line',
            data: (() => {
              if (showFFT.value && data.freq && data.amplitude) {
                // FFT模式：过滤无效数据点
                const validFFTData = [];
                for (let i = 0; i < data.freq.length; i++) {
                  if (isFinite(data.freq[i]) && isFinite(data.amplitude[i])) {
                    validFFTData.push([data.freq[i], data.amplitude[i]]);
                  }
                }
                return validFFTData;
              } else {
                // 时域模式：使用已过滤的原始数据
                return originalData;
              }
            })(),
            color: color,
            lineWidth: 1.5,
            marker: { enabled: false },
            boostThreshold: 1,
            enableMouseTracking: true,
          }
        ]
      });

      // 在图表创建后添加 plotLines
      errorPlotLines.forEach(plotLine => {
        chart.xAxis[0].addPlotLine(plotLine);
      });

      // 设置自定义按钮
      channelAnomalies.forEach(anomaly => {
        // 添加编辑和删除按钮
        if (chart && chart.renderer) {
          const endX = chart.xAxis[0].toPixels(anomaly.endX);
          const buttonWidth = 6;
          const buttonX = endX - buttonWidth - 5; // 右侧边缘向左偏移按钮宽度+5像素的边距
          // 添加删除按钮 - 放在右下角
          const deleteButton = chart.renderer.button(
            '×', buttonX, 163,
            function () {
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
                paddingLeft: '0px',
                position: 'absolute',
                top: 0,
                right: 0
              },
              r: 5,
              width: buttonWidth,
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

          // 添加编辑按钮 - 放在右上角
          const editButton = chart.renderer.button(
            '✎', buttonX, 188,
            function () {
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
              width: buttonWidth,
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
        }
      });

      // 添加图例文字
      if (chart && chart.renderer) {
        // 不再需要添加图例文字，因为我们已经在图表配置中设置了title

        // 在图表渲染完成后，调整颜色选择器的位置
        // 创建一个临时channel对象，包含调整颜色选择器所需的属性
        const channelObj = {
          channel_name: channelName.split('_')[0],
          shot_number: shotNumber,
          color: color
        };
        adjustColorPickerPosition(chart, channelObj);
      }

      // 为异常区域添加高亮线条，使其更加精确
      if (channelAnomalies && channelAnomalies.length > 0) {
        channelAnomalies.forEach(anomaly => {
          // 获取异常区域内的数据点
          const pointsInRange = [];
          const startX = anomaly.startX;
          const endX = anomaly.endX;

          // 找到区间内的所有点
          for (let i = 0; i < data.X_value.length; i++) {
            if (data.X_value[i] >= startX && data.X_value[i] <= endX) {
              pointsInRange.push([data.X_value[i], data.Y_value[i]]);
            }
          }

          // 如果没有足够点，添加区间端点
          if (pointsInRange.length < 2) {
            // 找到最接近区间边界的点
            let startIdx = -1;
            let endIdx = -1;
            let minStartDiff = Infinity;
            let minEndDiff = Infinity;

            for (let i = 0; i < data.X_value.length; i++) {
              const startDiff = Math.abs(data.X_value[i] - startX);
              const endDiff = Math.abs(data.X_value[i] - endX);

              if (startDiff < minStartDiff) {
                minStartDiff = startDiff;
                startIdx = i;
              }

              if (endDiff < minEndDiff) {
                minEndDiff = endDiff;
                endIdx = i;
              }
            }

            if (startIdx !== -1) {
              pointsInRange.push([startX, data.Y_value[startIdx]]);
            }

            if (endIdx !== -1) {
              pointsInRange.push([endX, data.Y_value[endIdx]]);
            }
          }

          // 确保点按X轴排序
          pointsInRange.sort((a, b) => a[0] - b[0]);

          // 添加高亮线条
          if (pointsInRange.length > 0) {
            chart.addSeries({
              id: `anomaly-highlight-${anomaly.id}`,
              name: `异常区域-${anomaly.id}`,
              data: pointsInRange,
              color: anomaly.isStored ? 'rgba(255, 0, 0, 0.8)' : 'rgba(255, 165, 0, 0.8)',
              lineWidth: 2,
              zIndex: 10,
              marker: {
                enabled: false
              },
              states: {
                hover: {
                  lineWidthPlus: 0
                }
              },
              enableMouseTracking: false,
              showInLegend: false
            });
          }
        });
      }

      // 保存原始显示范围，用于双击重置，分别保存时域和频域
      if (!originalDomains.value[channelName]) {
        originalDomains.value[channelName] = {};
      }
      
      // 等待图表渲染完成后获取实际的数据范围
      requestAnimationFrame(() => {
        if (chart && chart.xAxis && chart.yAxis) {
          if (showFFT.value) {
            // FFT模式下保存频域范围
            if (!originalDomains.value[channelName].freq) {
              originalDomains.value[channelName].freq = {
                x: [chart.xAxis[0].dataMin, chart.xAxis[0].dataMax],
                y: [chart.yAxis[0].dataMin, chart.yAxis[0].dataMax]
              };
            }
            // 如果还没有时域范围，也保存一份
            if (!originalDomains.value[channelName].time) {
              originalDomains.value[channelName].time = originalTimeDomain;
            }
          } else {
            // 时域模式下保存时域范围
            if (!originalDomains.value[channelName].time) {
              originalDomains.value[channelName].time = {
                x: [chart.xAxis[0].dataMin, chart.xAxis[0].dataMax],
                y: [chart.yAxis[0].dataMin, chart.yAxis[0].dataMax]
              };
            }
            // 如果还没有频域范围且有FFT数据，也保存一份
            if (!originalDomains.value[channelName].freq && originalFreqDomain) {
              originalDomains.value[channelName].freq = originalFreqDomain;
            }
          }
        }
      });

      performance.mark(`Draw Chart ${channelName}-end`);
      performance.measure(`Draw Chart ${channelName}`,
        `Draw Chart ${channelName}-start`,
        `Draw Chart ${channelName}-end`);

      // 存储图表实例
      window.chartInstances = window.chartInstances || {};
      window.chartInstances[channelName] = chart;

      // 重绘图表
      chart.redraw();

      // 图表初始化完成后，添加匹配高亮
      updateMatchedHighlights(chart, channelName);
      
      // 确保颜色选择器位置正确
      const channelObj = {
        channel_name: channelName.split('_')[0],
        shot_number: shotNumber,
        color: color
      };
      setTimeout(() => {
        adjustColorPickerPosition(chart, channelObj);
      }, 100);

      resolve();
    } catch (error) {
      console.error('Error in drawChart:', error);
      reject(error);
    }
  });
};

// 添加更新通道颜色的函数
const updateChannelColor = (channel) => {
  if (!channel || !channel.color) return;

  // console.log(`updateChannelColor: 更新通道 ${channel.channel_name}_${channel.shot_number} 的颜色为 ${channel.color}`);

  const channelKey = `${channel.channel_name}_${channel.shot_number}`;

  // 更新 Vuex 存储
  store.commit('updateChannelColor', { channel_key: channelKey, color: channel.color });

  // 强制更新视图
  nextTick(() => {
    // 确保颜色选择器能够正确接收颜色变化
    const index = selectedChannels.value.findIndex(ch =>
      ch.channel_name === channel.channel_name &&
      ch.shot_number === channel.shot_number
    );

    if (index !== -1) {
      // 更新选中通道的颜色
      selectedChannels.value[index].color = channel.color;
    }
  });
};

// 添加新函数，用于实时更新图表颜色
const updateChartColor = (channel, newColor) => {
  if (!channel || !newColor) return;

  // console.log(`更新通道 ${channel.channel_name}_${channel.shot_number} 的颜色为 ${newColor}`);

  // 更新本地数据
  channel.color = newColor;

  const channelKey = `${channel.channel_name}_${channel.shot_number}`;

  // 获取当前图表实例
  const chart = window.chartInstances?.[channelKey];
  if (!chart) {
    console.warn(`找不到通道 ${channelKey} 的图表实例`);
    return;
  }

  try {
    // 更新特定通道的线条颜色
    chart.series.forEach(series => {
      if (series.options.id === 'original') {
        series.update({
          color: newColor
        }, false); // 不立即重绘
      }
    });

    // 更新图例文字颜色
    try {
      // 使用chart.setTitle方法来更新图例文字的颜色
      chart.setTitle({
        style: {
          color: newColor,
          fontSize: '1.0em',
          fontWeight: 'medium'
        }
      }, null, false); // 不立即重绘

      // 更新图表自定义属性中的颜色
      if (chart.options.custom) {
        chart.options.custom.color = newColor;
      }

      // 在图表重绘后，重新调整颜色选择器的位置
      adjustColorPickerPosition(chart, channel);
    } catch (error) {
      console.warn('更新图例文字颜色时出错:', error);
    }

    // 一次性重绘图表
    chart.redraw();

    // 确保 Vuex 存储中的颜色也被更新
    store.commit('updateChannelColor', { channel_key: channelKey, color: newColor });
  } catch (error) {
    console.error(`更新通道 ${channelKey} 的颜色时出错:`, error);
  }
};

// 辅助函数：调整颜色选择器的位置
const adjustColorPickerPosition = (chart, channel) => {
  // 使用requestAnimationFrame确保在DOM完全渲染后执行
  requestAnimationFrame(() => {
    try {
      if (!chart || !chart.container) {
        console.warn('图表或容器不存在，无法调整颜色选择器位置');
        return;
      }

      // 获取title元素
      const titleElement = chart.container.querySelector('.highcharts-title');
      if (!titleElement) {
        console.warn('找不到图表标题元素');
        return;
      }

      // 获取title的位置信息
      const titleRect = titleElement.getBoundingClientRect();
      const chartRect = chart.container.getBoundingClientRect();

      if (titleRect.width === 0 || chartRect.width === 0) {
        // 如果尺寸为0，说明DOM还没完全渲染，延迟执行
        setTimeout(() => adjustColorPickerPosition(chart, channel), 100);
        return;
      }

      // 计算title左边界相对于图表的位置
      const titleLeftPosition = titleRect.left - chartRect.left;

      // 获取颜色选择器容器
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const colorPickerContainer = chart.container.closest('.chart-wrapper')?.querySelector('.color-picker-container');

      if (colorPickerContainer) {
        // 设置颜色选择器的位置，使其位于title的左侧，添加一些间距
        const rightPosition = Math.max(10, chartRect.width - titleLeftPosition + 10);
        colorPickerContainer.style.right = `${rightPosition}px`;
        
        // 确保可见度和透明度相应更新
        if (renderingStates[channelKey] === 100) {
          colorPickerContainer.style.opacity = '1';
          colorPickerContainer.style.visibility = 'visible';
        }
      } else {
        console.warn(`找不到通道 ${channelKey} 的颜色选择器容器`);
      }
    } catch (error) {
      console.warn('调整颜色选择器位置时出错:', error);
    }
  });
};

// 添加对matchedResults的监听
watch(filteredMatchedResults, (newMatchedResults) => {
  // 先清除所有高亮
  forceClearAllHighlights();
  
  // 处理新的匹配结果
  if (newMatchedResults && newMatchedResults.length > 0) {
    // 使用requestAnimationFrame代替setTimeout，更适合处理视觉更新
    requestAnimationFrame(() => {
      // 创建需要处理的任务队列
      const tasks = [];
      
      // 预先收集所有需要执行的任务
      newMatchedResults.forEach((matchResult) => {
        // 获取通道名称和炮号
        const { channelName, shotNumber, range, confidence } = matchResult;
        const channelKey = `${channelName}_${shotNumber}`;

        // 查找此匹配结果在原始数组中的索引
        const originalIndex = matchedResults.value.findIndex(item => 
          item.channelName === channelName && 
          item.shotNumber === shotNumber && 
          item.smoothLevel === matchResult.smoothLevel &&
          JSON.stringify(item.range) === JSON.stringify(range)
        );

        // 使用原始索引(如果找到)，否则使用其它唯一值
        const indexToUse = originalIndex !== -1 ? originalIndex : Date.now();

        // 获取匹配区域的范围
        if (range && range.length > 0) {
          // 获取对应的图表实例
          const chart = window.chartInstances?.[channelKey];
          if (chart) {
            // 遍历匹配区域的范围，收集任务
            range.forEach((rangeItem, rangeIndex) => {
              tasks.push(() => {
                const startTime = rangeItem[0];
                const endTime = rangeItem[1];
                
                // 根据置信度计算透明度
                const alpha = Math.max(0.1, Math.min(0.8, confidence)/2);
                
                // 使用唯一的ID确保不重复
                const uniqueBandId = `match-band-${indexToUse}-${rangeIndex}`;
                const uniqueSeriesId = `match-highlight-${indexToUse}-${rangeIndex}`;
                
                // 添加高亮区域
                chart.xAxis[0].addPlotBand({
                  id: uniqueBandId,
                  from: startTime,
                  to: endTime,
                  color: `rgba(255, 255, 0, ${alpha})`,
                  zIndex: 3,
                  borderColor: 'rgba(255, 215, 0, 0.4)',
                  borderWidth: 1
                });
                
                // 获取当前通道的数据
                const channelData = channelDataCache.value[channelKey];
                if (channelData && channelData.X_value && channelData.Y_value) {
                  // 预先筛选区间内的所有点
                  const pointsInRange = [];
                  for (let i = 0; i < channelData.X_value.length; i++) {
                    if (channelData.X_value[i] >= startTime && channelData.X_value[i] <= endTime) {
                      pointsInRange.push([channelData.X_value[i], channelData.Y_value[i]]);
                    }
                  }
                  
                  // 确保点按X轴排序
                  pointsInRange.sort((a, b) => a[0] - b[0]);
                  
                  // 添加高亮线条
                  if (pointsInRange.length > 0) {
                    chart.addSeries({
                      id: uniqueSeriesId,
                      name: `匹配区域-${indexToUse}-${rangeIndex}`,
                      data: pointsInRange,
                      color: `rgba(255, 215, 0, ${alpha + 0.2})`,
                      lineWidth: 2,
                      zIndex: 4,
                      marker: {
                        enabled: false
                      },
                      states: {
                        hover: {
                          lineWidthPlus: 0
                        }
                      },
                      enableMouseTracking: false,
                      showInLegend: false
                    });
                  }
                }
                
                return chart; // 返回chart用于后续重绘
              });
            });
          }
        }
      });
      
      // 使用批量更新策略，避免频繁重绘
      // 使用批处理执行任务，每次处理少量任务，避免长时间阻塞主线程
      const batchSize = 5; // 每批处理5个任务
      const chartSet = new Set(); // 记录需要重绘的chart
      
      const processBatch = (startIndex) => {
        if (startIndex >= tasks.length) {
          // 所有任务处理完毕，统一重绘图表
          chartSet.forEach(chart => chart.redraw());
          return;
        }
        
        // 处理当前批次的任务
        const endIndex = Math.min(startIndex + batchSize, tasks.length);
        for (let i = startIndex; i < endIndex; i++) {
          const chart = tasks[i]();
          if (chart) chartSet.add(chart);
        }
        
        // 使用requestAnimationFrame安排下一批任务，给UI留出响应时间
        requestAnimationFrame(() => processBatch(endIndex));
      };
      
      // 开始处理第一批任务
      processBatch(0);
    });
  }
}, { deep: true });

// 在drawChart函数中的updateAnomalyHighlights后添加处理匹配结果的函数
const updateMatchedHighlights = (chart, channelKey) => {
  if (!chart || !filteredMatchedResults.value) return;

  // 移除现有的匹配高亮区域
  chart.xAxis[0].plotLinesAndBands.forEach(band => {
    if (band.id && band.id.startsWith('match-band-')) {
      chart.xAxis[0].removePlotBand(band.id);
    }
  });

  // 移除现有的匹配高亮系列
  chart.series.forEach(series => {
    if (series.options.id && series.options.id.startsWith('match-highlight-')) {
      series.remove(false);
    }
  });

  // 处理匹配结果
  filteredMatchedResults.value.forEach((matchResult, arrayIndex) => {
    // 获取通道名称和炮号
    const { channelName, shotNumber, range, confidence } = matchResult;
    const matchChannelKey = `${channelName}_${shotNumber}`;

    // 查找此匹配结果在原始数组中的索引
    const originalIndex = matchedResults.value.findIndex(item => 
      item.channelName === channelName && 
      item.shotNumber === shotNumber && 
      item.smoothLevel === matchResult.smoothLevel &&
      JSON.stringify(item.range) === JSON.stringify(range)
    );

    // 只处理当前通道的匹配结果
    if (matchChannelKey === channelKey && range && range.length > 0) {
      // 遍历匹配区域的范围
      range.forEach((rangeItem, rangeIndex) => {
        const startTime = rangeItem[0];
        const endTime = rangeItem[1];

        // 根据置信度计算透明度
        const alpha = Math.max(0.1, Math.min(0.8, confidence)/2);

        // 使用原始索引(如果找到)或数组索引创建唯一ID
        const indexToUse = originalIndex !== -1 ? originalIndex : arrayIndex;

        // 添加高亮区域
        chart.xAxis[0].addPlotBand({
          id: `match-band-${indexToUse}-${rangeIndex}`,
          from: startTime,
          to: endTime,
          color: `rgba(255, 255, 0, ${alpha})`,
          zIndex: 3,
          borderColor: 'rgba(255, 215, 0, 0.4)',
          borderWidth: 1
        });

        // 获取当前通道的数据，使用正确的缓存键
        const dbSuffixPart = store.state.currentDbSuffix ? `_db_${store.state.currentDbSuffix}` : '';
        const cacheKey = `${channelKey}${dbSuffixPart}`;
        const cached = dataCache.get(cacheKey);
        const channelData = cached?.data;
        if (channelData && channelData.X_value && channelData.Y_value) {
          // 找到区间内的所有点
          const pointsInRange = [];
          for (let i = 0; i < channelData.X_value.length; i++) {
            if (channelData.X_value[i] >= startTime && channelData.X_value[i] <= endTime) {
              pointsInRange.push([channelData.X_value[i], channelData.Y_value[i]]);
            }
          }

          // 确保点按X轴排序
          pointsInRange.sort((a, b) => a[0] - b[0]);

          // 添加高亮线条
          if (pointsInRange.length > 0) {
            chart.addSeries({
              id: `match-highlight-${indexToUse}-${rangeIndex}`,
              name: `匹配区域-${indexToUse}-${rangeIndex}`,
              data: pointsInRange,
              color: `rgba(255, 215, 0, ${alpha + 0.2})`,
              lineWidth: 2,
              zIndex: 4,
              marker: {
                enabled: false
              },
              states: {
                hover: {
                  lineWidthPlus: 0
                }
              },
              enableMouseTracking: false,
              showInLegend: false
            });
          }
        }
      });
    }
  });
};

// 添加对matchedResultsCleared标记的监听
watch(matchedResultsCleared, (newValue, oldValue) => {
  // 忽略初始化时的变化或值未变化的情况
  if (!newValue || newValue === oldValue || newValue === initialMatchedResultsClearedValue.value) {
    return;
  }
  
  // 确保只有当matchedResults为空数组时才执行清除（说明是真正的清除操作）
  if (matchedResults.value.length === 0) {
    forceClearAllHighlights();
  }
});

// 提取清除高亮的函数，以便复用
const forceClearAllHighlights = () => {
  // 获取当前已选中的通道key列表
  const selectedChannelKeys = selectedChannels.value.map(
    channel => `${channel.channel_name}_${channel.shot_number}`
  );
  
  // 只清除当前显示的通道的高亮，而不是所有图表实例
  selectedChannelKeys.forEach(channelKey => {
    const chart = window.chartInstances?.[channelKey];
    if (chart) {
      // 移除现有的匹配高亮区域
      if (chart.xAxis && chart.xAxis[0]) {
        const bandsToRemove = [];
        
        // 先收集需要删除的plotBand的ID
        (chart.xAxis[0].plotLinesAndBands || []).forEach(band => {
          if (band && band.id && band.id.startsWith('match-band-')) {
            bandsToRemove.push(band.id);
          }
        });
        
        // 然后删除这些plotBand
        bandsToRemove.forEach(bandId => {
          chart.xAxis[0].removePlotBand(bandId);
        });
      }

      // 移除现有的匹配高亮系列
      if (chart.series) {
        const seriesToRemove = [];
        
        chart.series.forEach(series => {
          if (series && series.options && series.options.id && 
              series.options.id.startsWith('match-highlight-')) {
            seriesToRemove.push(series);
          }
        });
        
        seriesToRemove.forEach(series => {
          series.remove(false);
        });
      }
      
      // 强制重绘
      chart.redraw();
    }
  });
};

// 修改renderCharts函数，增加isActive判断
const renderCharts = debounce(async (forceRenderAll = false) => {
  try {
    performance.mark('Total Render Time-start');
    if (!isActive.value) return;
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      console.warn('No channels selected');
      return;
    }

    // 如果强制重新渲染，清除现有图表实例
    if (forceRenderAll) {
      if (window.chartInstances) {
        Object.keys(window.chartInstances).forEach(key => {
          const chart = window.chartInstances[key];
          if (chart) {
            try {
              chart.destroy();
            } catch (e) {
              console.warn(`销毁图表实例失败: ${e.message}`);
            }
          }
          delete window.chartInstances[key];
        });
      }
      renderedChannels.value.clear();
      window.chartInstances = {};
    }

    let channelsToRender;
    if (forceRenderAll) {
      channelsToRender = [...selectedChannels.value];
    } else {
      channelsToRender = selectedChannels.value.filter(channel => {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        return !renderedChannels.value.has(channelKey);
      });
    }

    // 请求池/批量并发机制，最大并发数
    const maxConcurrent = 8;
    let activeCount = 0;
    const queue = [...channelsToRender];
    const pendingRenderQueue = [];
    let fetchCompletedCount = 0;

    function nextFetch() {
      if (queue.length === 0) return;
      while (activeCount < maxConcurrent && queue.length > 0) {
        const channel = queue.shift();
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        loadingStates[channelKey] = 0;
        renderingStates[channelKey] = 0;
        // 记录通道总耗时开始时间
        channelTimings[channelKey] = channelTimings[channelKey] || {};
        channelTimings[channelKey].startTime = performance.now();
        channelTimings[channelKey].fetchStartTime = channelTimings[channelKey].startTime;
        activeCount++;
        fetchChannelData(channel, forceRenderAll).then(data => {
          channelTimings[channelKey].fetchEndTime = performance.now();
          channelTimings[channelKey].fetchDuration = ((channelTimings[channelKey].fetchEndTime - channelTimings[channelKey].fetchStartTime) / 1000).toFixed(2);
          fetchCompletedCount++;
          if (data) {
            pendingRenderQueue.push({ channel, data });
          }
        }).finally(() => {
          activeCount--;
          nextFetch(); // 补发下一个
        });
      }
    }
    nextFetch();

    // 分帧批量渲染
    const batchSize = 2;
    function renderNextBatch() {
      let count = 0;
      while (pendingRenderQueue.length > 0 && count < batchSize) {
        const { channel, data } = pendingRenderQueue.shift();
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        // 记录process开始时间
        channelTimings[channelKey].processStartTime = performance.now();
        processChannelData(data, channel).then(() => {
          channelTimings[channelKey].processEndTime = performance.now();
          channelTimings[channelKey].processDuration = ((channelTimings[channelKey].processEndTime - channelTimings[channelKey].processStartTime) / 1000).toFixed(2);
          // 记录通道总耗时结束时间
          channelTimings[channelKey].endTime = performance.now();
          channelTimings[channelKey].totalDuration = ((channelTimings[channelKey].endTime - channelTimings[channelKey].startTime) / 1000).toFixed(2);
          renderedChannels.value.add(channelKey);
          // 在渲染完成后调整颜色选择器位置（延迟确保图表完全渲染）
          setTimeout(() => {
            const chart = window.chartInstances?.[channelKey];
            if (chart) {
              adjustColorPickerPosition(chart, channel);
            }
          }, 150);
        });
        count++;
      }
      if (pendingRenderQueue.length > 0 || fetchCompletedCount < channelsToRender.length) {
        requestAnimationFrame(renderNextBatch);
      }
    }
    renderNextBatch();

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

// ========== 监听FFT显示状态变化 ===========
watch(showFFT, async (newShowFFT) => {
  if (!isActive.value || isFFTSwitching.value) return;
  
  // 设置切换标记，避免重复处理
  isFFTSwitching.value = true;
  
  try {
    // 当FFT显示状态改变时，更新现有图表的数据系列，而不是完全重新渲染
    if (selectedChannels.value && selectedChannels.value.length > 0) {
    // 批量更新现有图表的数据，而不是销毁重建
    for (const channel of selectedChannels.value) {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const chart = window.chartInstances?.[channelKey];
      
      if (chart) {
        try {
          // 更新图表缩放类型，保持缩放功能
          chart.update({
            chart: {
              zoomType: isBoxSelect.value ? 'x' : 'xy'
            }
          }, false);
          
          // 生成正确的缓存键（与store.js中的逻辑完全一致）
          const currentSampling = store.state.sampling;
          const dbSuffixPart = store.state.currentDbSuffix ? `_db_${store.state.currentDbSuffix}` : '';
          // 默认使用downsample模式的缓存键（与store.js中fetchChannelData保持一致）
          const cacheKey = `${channelKey}${dbSuffixPart}`;
          
          // 使用dataCache.get()方法获取缓存数据
          const cached = dataCache.get(cacheKey);
          let cachedData = null;
          
          if (cached && cached.data) {
            // 检查缓存是否在有效期内（30分钟）
            if (Date.now() - cached.timestamp < 30 * 60 * 1000) {
              cachedData = cached.data;
            }
          }
          
          // 如果缓存中没有数据或已过期，尝试从store获取
          if (!cachedData) {
            try {
              cachedData = await store.dispatch('fetchChannelData', { 
                channel, 
                forceRefresh: false,
                db_suffix: store.state.currentDbSuffix
              });
            } catch (error) {
              console.error(`获取通道数据失败: ${channelKey}`, error);
              cachedData = null;
            }
          }
          
          if (cachedData && cachedData.X_value && cachedData.Y_value) {
            // 准备新的数据系列
            let newData;
            let newTitle;
            let xAxisTitle;
            let yAxisTitle;
            
            if (newShowFFT && cachedData.freq && cachedData.amplitude) {
              // FFT模式：使用频率和幅值数据
              // 过滤无效数据点以避免显示问题
              const validIndices = [];
              for (let i = 0; i < cachedData.freq.length; i++) {
                if (isFinite(cachedData.freq[i]) && isFinite(cachedData.amplitude[i])) {
                  validIndices.push(i);
                }
              }
              newData = validIndices.map(i => [cachedData.freq[i], cachedData.amplitude[i]]);
              newTitle = `${channel.channel_name} - FFT`;
              xAxisTitle = 'Frequency (Hz)';
              yAxisTitle = 'Amplitude';
            } else {
              // 时域模式：使用原始数据
              // 过滤无效数据点
              const validIndices = [];
              for (let i = 0; i < cachedData.X_value.length; i++) {
                if (isFinite(cachedData.X_value[i]) && isFinite(cachedData.Y_value[i])) {
                  validIndices.push(i);
                }
              }
              newData = validIndices.map(i => [cachedData.X_value[i], cachedData.Y_value[i]]);
              const freqValue = cachedData.originalFrequency || '?';
              newTitle = `${channel.channel_name} (${freqValue.toFixed ? freqValue.toFixed(2) : freqValue}KHz -> ${currentSampling.toFixed(2)}KHz)`;
              xAxisTitle = '';
              yAxisTitle = cachedData.Y_unit || 'Y';
            }
            
            // 更新图表标题
            chart.setTitle({
              text: newTitle,
              align: 'right',
              x: -10,
              y: 60,
              style: {
                color: channel.color,
                fontSize: '1.0em',
                fontWeight: 'medium'
              }
            });
            
            // 更新坐标轴标题
            chart.xAxis[0].setTitle({ text: xAxisTitle });
            chart.yAxis[0].setTitle({ text: yAxisTitle });
            
            // 更新数据系列
            const originalSeries = chart.series.find(s => s.options.id === 'original');
            if (originalSeries) {
              originalSeries.setData(newData, false);
            }
            
            // 在标题更新后，重新调整颜色选择器位置
            // 使用延迟确保标题已完全更新
            setTimeout(() => {
              adjustColorPickerPosition(chart, channel);
            }, 50);
            
            // 设置坐标轴范围和保存原始范围
            if (newShowFFT && cachedData.freq && cachedData.amplitude) {
              // 使用安全的方式计算频率和幅值范围
              const safeFreqMin = cachedData.freq.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
              const safeFreqMax = cachedData.freq.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
              const freqMin = isFinite(safeFreqMin) ? safeFreqMin : 0;
              const freqMax = isFinite(safeFreqMax) ? safeFreqMax : 1000;
              
              const safeAmpMax = cachedData.amplitude.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
              const safeAmpMin = cachedData.amplitude.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
              const ampMax = isFinite(safeAmpMax) ? safeAmpMax : 1;
              const ampMin = isFinite(safeAmpMin) ? safeAmpMin : 0;
              
              // 计算合理的FFT Y轴范围
              let yMin_fft = Math.max(0, ampMin);
              let yMax_fft = ampMax;
              
              if (ampMax < 1e-6) {
                yMax_fft = ampMax * 2;
              } else if (ampMax < 0.001) {
                yMax_fft = ampMax * 1.2;
              } else {
                yMax_fft = ampMax * 1.1;
              }
              
              // 确保Y轴范围是有效的
              if (!isFinite(yMin_fft) || !isFinite(yMax_fft) || yMin_fft >= yMax_fft) {
                yMin_fft = 0;
                yMax_fft = 1;
              }
              
              chart.xAxis[0].setExtremes(freqMin, freqMax, false);
              chart.yAxis[0].setExtremes(yMin_fft, yMax_fft, false);
              
              // 确保保存FFT模式的原始范围
              if (!originalDomains.value[channelKey]) {
                originalDomains.value[channelKey] = {};
              }
              if (!originalDomains.value[channelKey].freq) {
                originalDomains.value[channelKey].freq = {
                  x: [freqMin, freqMax],
                  y: [yMin_fft, yMax_fft]
                };
              }
            } else {
              // 恢复时域范围
              const originalDomain = originalDomains.value[channelKey];
              if (originalDomain?.time) {
                chart.xAxis[0].setExtremes(originalDomain.time.x[0], originalDomain.time.x[1], false);
                chart.yAxis[0].setExtremes(originalDomain.time.y[0], originalDomain.time.y[1], false);
              } else if (cachedData && cachedData.X_value && cachedData.Y_value) {
                // 如果没有保存的时域范围，计算默认范围
                const safeXMin = cachedData.X_value.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
                const safeXMax = cachedData.X_value.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
                const safeYMin = cachedData.Y_value.reduce((min, val) => (!isFinite(val) ? min : Math.min(min, val)), Infinity);
                const safeYMax = cachedData.Y_value.reduce((max, val) => (!isFinite(val) ? max : Math.max(max, val)), -Infinity);
                
                const xMin = isFinite(safeXMin) ? safeXMin : 0;
                const xMax = isFinite(safeXMax) ? safeXMax : 1;
                const yMin = isFinite(safeYMin) ? safeYMin : 0;
                const yMax = isFinite(safeYMax) ? safeYMax : 1;
                const yRange = yMax - yMin;
                const yMinWithMargin = yMin - yRange * 0.1;
                const yMaxWithMargin = yMax + yRange * 0.1;
                
                chart.xAxis[0].setExtremes(xMin, xMax, false);
                chart.yAxis[0].setExtremes(yMinWithMargin, yMaxWithMargin, false);
                
                // 保存计算的时域范围
                if (!originalDomains.value[channelKey]) {
                  originalDomains.value[channelKey] = {};
                }
                originalDomains.value[channelKey].time = {
                  x: [xMin, xMax],
                  y: [yMinWithMargin, yMaxWithMargin]
                };
              }
            }
            
            // 更新Y轴配置以匹配新的数据范围
            const currentYRange = chart.yAxis[0].max - chart.yAxis[0].min;
            chart.yAxis[0].update({
              tickAmount: 6,
              minTickInterval: (() => {
                if (currentYRange < 0.001) {
                  return currentYRange / 10;
                } else if (currentYRange < 0.1) {
                  return currentYRange / 20;
                } else if (currentYRange < 10) {
                  return currentYRange / 20;
                } else {
                  return currentYRange / 20;
                }
              })(),
              allowDecimals: true,
              startOnTick: false,
              endOnTick: false
            }, false);
            
            // 一次性重绘图表
            chart.redraw();
            
            // 在图表重绘后，再次调整颜色选择器位置
            requestAnimationFrame(() => {
              adjustColorPickerPosition(chart, channel);
            });
          } else {
            // 如果缓存中没有数据，重新加载数据（但避免重复加载）
            if (!loadingStates[channelKey] || loadingStates[channelKey] === 100) {
              console.log(`通道 ${channelKey} 缓存为空，重新加载数据`);
              try {
                const data = await fetchChannelData(channel, false);
                if (data) {
                  await processChannelData(data, channel);
                }
              } catch (loadError) {
                console.error(`重新加载通道 ${channelKey} 数据失败:`, loadError);
              }
            }
          }
        } catch (error) {
          console.error(`更新图表 ${channelKey} 时出错:`, error);
          // 如果更新失败，回退到完全重新渲染，但不阻塞其他图表的更新
          if (!loadingStates[channelKey] || loadingStates[channelKey] === 100) {
            console.log(`回退到重新渲染图表 ${channelKey}`);
            try {
              // 标记该通道需要重新渲染
              renderedChannels.value.delete(channelKey);
              // 异步重新渲染该通道，不阻塞其他通道
              nextTick(async () => {
                try {
                  const data = await fetchChannelData(channel, true);
                  if (data) {
                    await processChannelData(data, channel);
                    renderedChannels.value.add(channelKey);
                    // 在重新渲染后调整颜色选择器位置
                    const chart = window.chartInstances?.[channelKey];
                    if (chart) {
                      requestAnimationFrame(() => {
                        adjustColorPickerPosition(chart, channel);
                      });
                    }
                  }
                } catch (retryError) {
                  console.error(`重新渲染图表 ${channelKey} 也失败了:`, retryError);
                }
              });
            } catch (fallbackError) {
              console.error(`回退渲染 ${channelKey} 时出错:`, fallbackError);
            }
          }
        }
      } else {
        // 如果图表实例不存在，说明图表还没有渲染，重新渲染
        if (!loadingStates[channelKey] || loadingStates[channelKey] === 100) {
          console.log(`图表实例 ${channelKey} 不存在，重新渲染`);
          try {
            // 标记该通道需要重新渲染
            renderedChannels.value.delete(channelKey);
            const data = await fetchChannelData(channel, false);
            if (data) {
              await processChannelData(data, channel);
              renderedChannels.value.add(channelKey);
              // 在重新渲染后调整颜色选择器位置
              const chart = window.chartInstances?.[channelKey];
              if (chart) {
                requestAnimationFrame(() => {
                  adjustColorPickerPosition(chart, channel);
                });
              }
            }
          } catch (renderError) {
            console.error(`渲染图表 ${channelKey} 失败:`, renderError);
          }
        }
      }
    }
  }
  
  // 单独更新没有图表实例的图表的缩放类型
  Object.values(window.chartInstances || {}).forEach(chart => {
    if (chart) {
      chart.update({
        chart: {
          zoomType: isBoxSelect.value ? 'x' : 'xy'
        }
      }, false);
      chart.redraw();
    }
  });
  
  } finally {
    // 重置切换标记
    setTimeout(() => {
      isFFTSwitching.value = false;
    }, 100);
  }
});

// ========== 监听 errorNamesVersion，只刷新指定通道的 error plotBand ===========
watch(
  () => store.state.errorNamesVersion,
  async (newVal, oldVal) => {
    if (!newVal || !newVal.channels || newVal.channels.length === 0) return;
    for (const channelKey of newVal.channels) {
      // 找到当前通道对象
      const channel = selectedChannels.value.find(
        ch => `${ch.channel_name}_${ch.shot_number}` === channelKey
      );
      if (!channel) continue;
      // 拉取最新error data
      let errorDataResults = [];
      try {
        errorDataResults = await store.dispatch('fetchAllErrorData', channel);
      } catch (e) {
        errorDataResults = [];
      }
      // 获取当前图表实例
      const chart = window.chartInstances?.[channelKey];
      if (!chart) continue;
      
      // 清除所有error plotBand的更可靠方法
      const axis = chart.xAxis[0];
      // 1. 首先获取所有plotBand的ID
      const errorBandIds = [];
      (axis.plotLinesAndBands || []).forEach(band => {
        if (band.id && band.id.startsWith('error-band-')) {
          errorBandIds.push(band.id);
        }
      });
      
      // 2. 然后一个个移除，确保所有ID都被处理
      // 使用axis.update来批量处理plotBand的移除，避免多次触发重绘
      axis.update({}, false); // 先禁用自动重绘
      errorBandIds.forEach(id => {
        axis.removePlotBand(id);
      });
      
      // 重新添加 error plotBand
      let errorRanges = [];
      if (Array.isArray(errorDataResults)) {
        errorDataResults.forEach((errorGroup, groupIndex) => {
          if (Array.isArray(errorGroup)) {
            errorGroup.forEach((errors, personIndex) => {
              if (errors && Array.isArray(errors)) {
                errors.forEach((error, errorIndex) => {
                  if (error.X_error && Array.isArray(error.X_error)) {
                    error.X_error.forEach((xRange, rangeIndex) => {
                      const startTime = xRange[0];
                      const endTime = xRange[1];
                      errorRanges.push([startTime, endTime]);
                    });
                  }
                });
              }
            });
          }
        });
      }
      
      // 3. 批量添加新的plotBands
      // 使用一次axis.update来添加所有plotBand，而不是逐个添加
      const plotBands = errorRanges.map((range, idx) => ({
        id: `error-band-${idx}`,
        from: range[0],
        to: range[1],
        color: 'rgba(255, 0, 0, 0.1)',
        zIndex: 1
      }));
      
      // 一次性更新所有plotBands，只触发一次重绘
      axis.update({
        plotBands: plotBands
      }, true); // 最后一次更新时才触发重绘
    }
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
  padding-bottom: 2vh;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

:deep(.highcharts-reset-zoom),
:deep(.highcharts-button) {
  display: none !important;
}

.chart-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  width: 100%;
  position: relative;
  min-height: 200px;
  overflow: hidden;
  padding: 5px 0;
  margin-bottom: -10px;
  /* 调整图表之间的间距为15px，既不过于拥挤也不过于分散 */
}

svg {
  width: 100%;
  position: relative;
}

/* 添加耗时显示样式 */
.timing-info {
  position: absolute;
  top: 10px;
  right: 10px;
  background-color: rgba(255, 255, 255, 0.8);
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
  color: #666;
  z-index: 10;
  border: 1px solid #e4e7ed;
}

.color-picker-container {
  position: absolute;
  top: 45px;
  right: 250px;
  /* 初始位置，会被动态调整 */
  display: flex;
  align-items: center;
  gap: 5px;
  background-color: transparent;
  padding: 2px 5px;
  transition: right 0.3s ease;
  /* 添加平滑过渡效果 */
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
  display: none;
}

.progress-title {
  display: none;
}

.progress-percentage {
  display: none;
}

/* 自定进度条样式 */
:deep(.el-progress-bar__outer) {
  display: none;
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

.circular-progress-wrapper {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 100;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

/* 添加加载阶段文本样式 */
.loading-stage-text {
  margin-top: 10px;
  font-size: 14px;
  color: #606266;
  text-align: center;
  white-space: nowrap;
  font-weight: 500;
  padding: 2px 8px;
}

/* 自定义环形进度条样式 */
:deep(.el-progress-circle__track) {
  stroke: rgba(240, 242, 245, 0.8);
  stroke-width: 6px;
}

:deep(.el-progress-circle__path) {
  stroke-linecap: round;
  transition: stroke-dasharray 0.6s ease, stroke 0.6s ease;
  stroke-width: 6px;
}

:deep(.el-progress__text) {
  font-size: 14px !important;
  font-weight: bold;
  color: #303133;
}

:deep(.el-progress.is-warning .el-progress__text) {
  color: #E6A23C;
}

:deep(.el-progress.is-success .el-progress__text) {
  color: #67C23A;
}

.progress-info,
.channel-name,
.progress-status {
  display: none;
}
</style>
