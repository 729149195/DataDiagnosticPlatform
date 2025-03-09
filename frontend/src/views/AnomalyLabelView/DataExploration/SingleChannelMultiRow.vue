<template>
  <div class="chart-container">
    <div v-if="selectedChannels.length === 0">
      <el-empty description="请选择通道" style="margin-top: 15vh;" />
    </div>
    <div v-else>
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

        <div class="color-picker-container" :style="{
          opacity: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 1 : 0,
          visibility: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 'visible' : 'hidden',
          transition: 'opacity 0.5s ease'
        }" v-show="renderingStates[channel.channel_name + '_' + channel.shot_number] === 100">
          <ChannelColorPicker 
            :key="channel.channel_name + '_' + channel.shot_number + '_' + channel.color"
            :color="channel.color" 
            :predefineColors="predefineColors"
            @change="updateChannelColor(channel)" 
            @update:color="updateChartColor(channel, $event)"
            :channelName="channel.channel_name" 
            :shotNumber="channel.shot_number" 
          />
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
import { ref, reactive, watch, computed, onMounted, nextTick, onUnmounted, toRaw } from 'vue';
import { ElDialog, ElForm, ElFormItem, ElInput, ElButton, ElMessage } from 'element-plus';
import { useStore } from 'vuex';
import chartWorkerManager from '@/workers/chartWorkerManager';
import ChannelColorPicker from '@/components/ChannelColorPicker.vue';

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
        chart.xAxis[0].removePlotBand(`band-end-${anomaly.id}`);

        // 移除高亮线条
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

        // 重绘图表
        chart.redraw();
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

const processChannelData = async (data, channel) => {
  const channelKey = `${channel.channel_name}_${channel.shot_number}`;
  try {
    renderingStates[channelKey] = 0;
    // 准备数据
    const channelData = {
      X_value: [...data.X_value],
      Y_value: [...data.Y_value],
      originalFrequency: data.originalFrequency || 1.0,
      originalDataPoints: data.originalDataPoints || data.X_value.length,
      channel_number: data.channel_number || channel.channel_name
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
        data.X_unit || 's',
        data.Y_unit || 'Y',
        data.channel_type || channel.channel_type,
        channelData.channel_number,
        channel.shot_number
      ),
      errorDataPromise
    ]);

    if (processedData) {
      renderingStates[channelKey] = 75; // 更新渲染状态

      // 只渲染当前通道，不重新渲染其他通道
      await nextTick();
      await drawChart(
        processedData.processedData,
        errorDataResults,
        channelKey,
        channel.color,
        processedData.xUnit,
        processedData.yUnit,
        processedData.channelType,
        processedData.shotNumber
      );

      renderingStates[channelKey] = 100;
      
      // 在渲染完成后，确保再次调整颜色选择器位置
      const chart = window.chartInstances?.[channelKey];
      if (chart) {
        // 使用两次调用，确保有足够时间让DOM更新
        adjustColorPickerPosition(chart, channel);
        setTimeout(() => adjustColorPickerPosition(chart, channel), 100);
      }
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

const renderCharts = debounce(async (forceRenderAll = false) => {
  try {
    performance.mark('Total Render Time-start');
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      console.warn('No channels selected');
      return;
    }
    let channelsToRender;
    if (forceRenderAll) {
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
    
    // 渲染完成后，延迟200ms再次调整所有颜色选择器的位置
    setTimeout(() => {
      selectedChannels.value.forEach(channel => {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        const chart = window.chartInstances?.[channelKey];
        if (chart) {
          adjustColorPickerPosition(chart, channel);
        }
      });
    }, 200);
  } catch (error) {
    console.error('Error in renderCharts:', error);
    ElMessage.error(`渲染图表错误: ${error.message}`);
  }
}, 200);

// 监听selectedChannels的变化，处理移除的通道
watch(selectedChannels, (newChannels, oldChannels) => {
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
});

// 添加对domains的监听，当domains变化时更新图表的显示范围，但只更新y轴，不影响x轴
watch(() => domains.value, (newDomains, oldDomains) => {
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

        // 更新异常高亮线条
        updateAnomalyHighlights(chart, channelKey);

        chart.redraw();
      }
    }
  });
});

// 添加对brush_begin和brush_end的监听，当它们变化时更新所有图表的横坐标范围
watch([brush_begin, brush_end], ([newBegin, newEnd]) => {
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

      // 更新异常高亮线条
      updateAnomalyHighlights(chart, channelKey);

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
  // 终止chartWorkerManager
  chartWorkerManager.terminate();
  
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
            color: 'rgba(255, 0, 0, 0.8)',
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

      // 准备数据
      const originalData = [];
      for (let i = 0; i < data.X_value.length; i++) {
        originalData.push([data.X_value[i], data.Y_value[i]]);
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
                        color: 'rgba(255, 0, 0, 0.5)',
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
                        color: 'rgba(255, 0, 0, 0.5)',
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
          zoomType: isBoxSelect.value ? 'x' : 'xy',
          animation: false,
          spacing: [10, 15, 10, 10], // 添加统一的内部间距 [top, right, bottom, left]
          marginLeft: 90, // 增加左边距，确保有足够空间显示Y轴标签
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
                  const channelData = channelDataCache.value[channelName];
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
                    originalDomains.value[channelName] = {
                      x: [parseFloat(brush_begin.value), parseFloat(brush_end.value)],
                      y: [yMin, yMax]
                    };
                  }

                  // 更新store中的范围，只更新x轴，保持y轴不变
                  store.dispatch('updateDomains', {
                    channelName,
                    xDomain: [xMin, xMax],
                    // 不再更新yDomain，保持y轴不变
                  });

                  // 更新异常高亮线条
                  updateAnomalyHighlights(chart, channelName);

                  // 允许默认的缩放行为，不再重新绘制整个图表
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
                // 获取初始绘制时保存的原始范围
                const originalDomain = originalDomains.value[channelName];
                if (originalDomain) {
                  // 恢复到初始绘制时的范围
                  const [xMin, xMax] = originalDomain.x;
                  const [yMin, yMax] = originalDomain.y;

                  // 设置坐标轴范围
                  this.xAxis[0].setExtremes(xMin, xMax);
                  this.yAxis[0].setExtremes(yMin, yMax);

                  // 更新store中的范围
                  store.dispatch('updateDomains', {
                    channelName,
                    xDomain: [xMin, xMax],
                    yDomain: [yMin, yMax]
                  });

                  // 更新异常高亮线条
                  updateAnomalyHighlights(chart, channelName);
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
          originalFrequency: data.originalFrequency || 1.0,
          channelName: channelName,
          shotNumber: shotNumber,
          color: color
        },
        title: {
          text: `${channelType || channelName.split('_')[0]} | ${shotNumber} (${(data.originalFrequency || 1.0).toFixed(2)}KHz -> ${(sampling.value).toFixed(2)}KHz)`,
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
          title: {
            text: yUnit,
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
              const absValue = Math.abs(this.value);
              if (absValue < 0.01 && absValue != 0) {
                return this.value.toExponential(1); // 使用科学计数法
              } else if (absValue < 10) {
                return this.value.toFixed(1); // 小数点后3位
              } else if (absValue < 100) {
                return this.value.toFixed(1); // 小数点后2位
              } else if (absValue < 1000) {
                return this.value.toFixed(1); // 小数点后1位
              } else {
                return Math.round(this.value); // 整数
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
            data: originalData,
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

      // 保存原始显示范围，用于双击重置
      if (!originalDomains.value[channelName]) {
        originalDomains.value[channelName] = {
          x: [xDomain[0], xDomain[1]],
          y: [yDomain[0], yDomain[1]]
        };
      }

      performance.mark(`Draw Chart ${channelName}-end`);
      performance.measure(`Draw Chart ${channelName}`,
        `Draw Chart ${channelName}-start`,
        `Draw Chart ${channelName}-end`);

      // 存储图表实例
      window.chartInstances = window.chartInstances || {};
      window.chartInstances[channelName] = chart;

      // 重绘图表
      chart.redraw();

      resolve();
    } catch (error) {
      console.error('Error in drawChart:', error);
      reject(error);
    }
  });
};

// 添加更新异常高亮线条的函数
const updateAnomalyHighlights = (chart, channelKey) => {
  if (!chart) return;

  // 获取当前通道的异常
  const channelAnomalies = store.getters.getAnomaliesByChannel(channelKey);
  if (!channelAnomalies || channelAnomalies.length === 0) return;

  // 获取当前通道的数据
  const channelData = channelDataCache.value[channelKey];
  if (!channelData || !channelData.X_value || !channelData.Y_value) return;

  // 获取当前图表的显示范围
  const xMin = chart.xAxis[0].min;
  const xMax = chart.xAxis[0].max;

  // 遍历所有异常
  channelAnomalies.forEach(anomaly => {
    // 检查异常是否在当前显示范围内
    if (anomaly.endX < xMin || anomaly.startX > xMax) return;

    // 移除旧的高亮线条
    const oldHighlightSeries = chart.series.find(s => s.options.id === `anomaly-highlight-${anomaly.id}`);
    if (oldHighlightSeries) {
      oldHighlightSeries.remove(false);
    }

    // 获取异常区域内的数据点
    const pointsInRange = [];
    const startX = anomaly.startX;
    const endX = anomaly.endX;

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
  // 使用setTimeout确保在DOM完全渲染后执行
  setTimeout(() => {
    try {
      // 获取title元素
      const titleElement = chart.container.querySelector('.highcharts-title');
      if (titleElement) {
        // 获取title的宽度和位置
        const titleRect = titleElement.getBoundingClientRect();
        const chartRect = chart.container.getBoundingClientRect();
        
        // 计算title左边界相对于图表的位置
        const titleLeftPosition = titleRect.left - chartRect.left;
        
        // 获取颜色选择器容器
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        const colorPickerContainer = chart.container.closest('.chart-wrapper')?.querySelector('.color-picker-container');
        
        if (colorPickerContainer) {
          // 设置颜色选择器的位置，使其位于title的左侧
          const rightPosition = chartRect.width - titleLeftPosition;
          colorPickerContainer.style.right = `${rightPosition}px`;
          // 确保可见度和透明度相应更新
          if (renderingStates[channelKey] === 100) {
            colorPickerContainer.style.opacity = '1';
            colorPickerContainer.style.visibility = 'visible';
          }
        }
      }
    } catch (error) {
      console.warn('调整颜色选择器位置时出错:', error);
    }
  }, 50); // 短暂延迟确保DOM更新
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
  margin-bottom: -10px; /* 调整图表之间的间距为15px，既不过于拥挤也不过于分散 */
}

svg {
  width: 100%;
  position: relative;
}

.color-picker-container {
  position: absolute;
  top: 55px;
  right: 250px; /* 初始位置，会被动态调整 */
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 5px;
  background-color: transparent;
  padding: 2px 5px;
  transition: right 0.3s ease; /* 添加平滑过渡效果 */
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
