<template>
  <div class="chart-container">
    <div class="legend-container">
      <!-- 移除 LegendComponent，改为直接使用 ChannelColorPicker -->
      <div class="legend" id="channelLegendContainer">
        <div class="legend-item" v-for="(channel, index) in selectedChannels" :key="`${channel.channel_name}_${channel.shot_number}`">
          <ChannelColorPicker 
            :color="channel.color" 
            :predefineColors="predefineColors"
            @change="updateChannelColor({ channelKey: `${channel.channel_name}_${channel.shot_number}`, color: $event })"
            @update:color="updateChartColor(channel, $event)"
            :channelName="channel.channel_name"
            :shotNumber="channel.shot_number"
          />
          <span :style="{ color: channel.color }" class="legend-text" :data-channel="`${channel.channel_name}_${channel.shot_number}`">
            {{ channel.shot_number }}_{{ channel.channel_name }}
          </span>
        </div>
      </div>
    </div>
    <div v-if="selectedChannels.length === 0">
      <el-empty description="请选择通道" style="margin-top: 15vh;" />
    </div>
    <div v-else>
      <div v-if="!renderingState.completed" class="progress-container" :style="{
        opacity: 1,
        transition: 'opacity 0.5s ease-in-out'
      }">
        <div class="progress-circle-wrapper">
          <el-progress type="circle" :percentage="getProgressPercentage" :stroke-width="6" :status="loadingState.isLoading ? 'warning' : ''" :color="!loadingState.isLoading ? '#409EFF' : ''">
            <template #default>
              <div class="progress-info">
                <div class="progress-text">{{ !loadingState.isLoading ? '图表渲染中' : '数据加载中' }}</div>
                <div class="progress-percentage">{{ getProgressPercentage }}%</div>
              </div>
            </template>
          </el-progress>
        </div>
      </div>
      <div class="chart-wrapper" :style="{
        opacity: renderingState.completed ? 1 : 0.3,
        transition: 'opacity 0.3s ease-in-out',
        position: 'relative'
      }">
        <div id="combined-chart" ref="chartContainer" style="width: 100%; height: 100%;"></div>
      </div>
    </div>
    <el-dialog v-if="showAnomalyForm" v-model="showAnomalyForm" title="编辑/修改异常信息">
      <el-form :model="currentAnomaly" label-width="auto">
        <el-form-item label="选择通道" required>
          <el-select v-model="selectedChannelForAnnotation" placeholder="选择要标注的通道" style="width: 100%;">
            <el-option v-for="channel in selectedChannels" :key="`${channel.channel_name}_${channel.shot_number}`" :label="`${channel.channel_name} | ${channel.shot_number}`" :value="`${channel.channel_name}_${channel.shot_number}`">
            </el-option>
          </el-select>
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
          <el-button type="danger" @click="deleteAnomaly" v-if="currentAnomaly.id">删除</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import Highcharts from 'highcharts';
import 'highcharts/modules/accessibility';
import debounce from 'lodash/debounce';
import { ref, watch, computed, onMounted, nextTick, reactive, onUnmounted, toRaw } from 'vue';
import { ElMessage, ElEmpty, ElProgress, ElDialog, ElForm, ElFormItem, ElInput, ElButton, ElSelect, ElOption } from 'element-plus';
import { useStore } from 'vuex';
import chartWorkerManager from '@/workers/chartWorkerManager';
import { DataSmoother } from '@/views/AnomalyLabelView/Sketch/data-smoother.js';
import ChannelColorPicker from '@/components/ChannelColorPicker.vue';

// 添加预定义颜色数组
const predefineColors = [
  '#000000', '#4169E1', '#DC143C', '#228B22', '#FF8C00',
  '#800080', '#FF1493', '#40E0D0', '#FFD700', '#8B4513',
  '#2F4F4F', '#1E90FF', '#32CD32', '#FF6347', '#DA70D6',
  '#191970', '#FA8072', '#6B8E23', '#6A5ACD', '#FF7F50',
  '#4682B4',
];

// 设置Highcharts全局配置
Highcharts.setOptions({
  // ... existing code ...
  accessibility: {
    enabled: false // 禁用无障碍功能，避免相关错误
  }
});
// ... existing code ...

// 平滑数据函数
const interpolateData = (data, factor) => {
  if (!data || !Array.isArray(data) || data.length < 2) {
    return [...data]; // 返回原始数据的副本
  }

  try {
    // 如果平滑因子为0或不在有效范围内，返回原始数据
    if (factor <= 0 || factor > 1) {
      return [...data];
    }

    const result = [...data]; // 创建数据副本
    const windowSize = Math.ceil(data.length * factor * 0.1); // 根据平滑因子计算窗口大小

    if (windowSize < 2) {
      return result; // 窗口过小，不执行平滑
    }

    // 使用简单的移动平均算法
    for (let i = 0; i < data.length; i++) {
      let sum = 0;
      let count = 0;

      // 计算当前点周围的窗口范围
      const start = Math.max(0, i - windowSize);
      const end = Math.min(data.length - 1, i + windowSize);

      // 对窗口内的所有点求和
      for (let j = start; j <= end; j++) {
        // 只考虑有效数值
        if (typeof data[j] === 'number' && !isNaN(data[j])) {
          sum += data[j];
          count++;
        }
      }

      // 计算平均值
      if (count > 0) {
        result[i] = sum / count;
      }
    }

    return result;
  } catch (error) {
    console.error('数据平滑处理出错:', error);
    return [...data]; // 出错时返回原始数据的副本
  }
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
  // 清除现有的进度更新定时器
  if (loadingState.progressInterval) {
    clearInterval(loadingState.progressInterval);
    loadingState.progressInterval = null;
  }

  loadingState.progress = 0;
  loadingState.error = null;
  renderingState.completed = false;
  loadingState.isLoading = false;
};
defineExpose({
  chartContainer: chartContainer,
  channelsData: exposeData,
  resetProgress
})

const mainChartDimensions = ref({
  margin: { top: 30, right: 10, bottom: 80, left: 80 },
  width: 0,
  height: 0, // 将会动态计算
});

// Vuex store
const store = useStore();
const selectedChannels = computed(() => store.state.selectedChannels);
const channelDataCache = computed(() => store.state.channelDataCache); // 添加channelDataCache

const sampling = computed(() => store.state.sampling);
const smoothnessValue = computed(() => store.state.smoothness);
const sampleRate = ref(store.state.sampling);
const matchedResults = computed(() => store.getters.getMatchedResults);

const updateChannelColor = ({ channelKey, color }) => {
  const channel = selectedChannels.value.find(
    (ch) => `${ch.channel_name}_${ch.shot_number}` === channelKey
  );
  if (channel) {
    // 更新本地数据
    channel.color = color;
    
    // 更新 Vuex 存储
    store.commit('updateChannelColor', { channel_key: channelKey, color });

    // 获取当前图表实例
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (chart) {
      // 更新特定通道的线条颜色，但不重绘整个图表
      chart.series.forEach(series => {
        if (series.name === channelKey || series.name === `${channelKey}_smoothed`) {
          // 直接更新颜色属性，而不是调用 series.update
          series.color = color;
          
          // 更新线条的颜色，但不触发重绘
          if (series.graph) {
            series.graph.attr({
              stroke: color
            });
          }
          
          // 更新区域填充颜色（如果有）
          if (series.area) {
            series.area.attr({
              fill: color
            });
          }
          
          // 更新标记点颜色（如果有）
          if (series.markerGroup) {
            series.markerGroup.attr({
              fill: color,
              stroke: color
            });
          }
          
          // 更新内部选项
          series.options.color = color;
        }
      });
      
      // 不调用 chart.redraw()，避免重绘整个图表
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

// 添加 updateChartColor 函数，直接更新图表颜色而不触发重绘
const updateChartColor = (channel, newColor) => {
  if (!channel || !newColor) return;
  
  console.log(`更新通道 ${channel.channel_name}_${channel.shot_number} 的颜色为 ${newColor}`);
  
  // 更新本地数据
  channel.color = newColor;
  
  const channelKey = `${channel.channel_name}_${channel.shot_number}`;
  
  // 获取当前图表实例
  const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
  if (!chart) {
    console.warn(`找不到图表实例`);
    return;
  }
  
  try {
    // 更新特定通道的线条颜色
    chart.series.forEach(series => {
      if (series.name === channelKey || series.name === `${channelKey}_smoothed`) {
        // 直接更新颜色属性
        series.color = newColor;
        
        // 更新线条的颜色
        if (series.graph) {
          series.graph.attr({
            stroke: newColor
          });
        }
        
        // 更新区域填充颜色（如果有）
        if (series.area) {
          series.area.attr({
            fill: newColor
          });
        }
        
        // 更新标记点颜色（如果有）
        if (series.markerGroup) {
          series.markerGroup.attr({
            fill: newColor,
            stroke: newColor
          });
        }
        
        // 更新内部选项
        series.options.color = newColor;
      }
    });
    
    // 更新图例文字颜色
    const legendText = document.querySelector(`.legend-text[data-channel="${channelKey}"]`);
    if (legendText) {
      legendText.style.color = newColor;
    }
    
    // 不调用 chart.redraw()，避免重绘整个图表
    
    // 确保 Vuex 存储中的颜色也被更新
    store.commit('updateChannelColor', { channel_key: channelKey, color: newColor });
  } catch (error) {
    console.error(`更新通道 ${channelKey} 的颜色时出错:`, error);
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

// 添加 drawHighlightRects 函数
const drawHighlightRects = (channelName, matchedResults) => {
  try {
    // 找到当前图表实例
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (!chart) {
      console.warn('未找到图表实例，无法绘制高亮区域');
      return;
    }

    // 先清除之前为该通道绘制的所有高亮区域
    const existingRects = chart.annotations || [];
    const channelRects = existingRects.filter(rect =>
      rect && rect.options && rect.options.id && rect.options.id.startsWith(`highlight-${channelName}-`)
    );
    channelRects.forEach(rect => {
      if (rect) {
        try {
          rect.destroy();
        } catch (error) {
          console.warn(`删除高亮区域时出错: ${error.message}`);
        }
      }
    });

    // 清除之前的匹配高亮系列
    chart.series.forEach(series => {
      if (series && series.name && series.name.startsWith(`highlight-${channelName}-`)) {
        series.remove(false); // 不立即重绘
      }
    });

    // 确保xDomains.value.global是有效的范围
    if (!xDomains.value.global || !Array.isArray(xDomains.value.global) || xDomains.value.global.length !== 2) {
      console.warn('无效的X轴范围，无法绘制高亮区域');
      return;
    }

    // 获取当前图表的显示范围
    const xMin = chart.xAxis[0].min || xDomains.value.global[0];
    const xMax = chart.xAxis[0].max || xDomains.value.global[1];

    // 获取Y轴范围
    const yMin = chart.yAxis[0].min;
    const yMax = chart.yAxis[0].max;

    // 计算当前可见区域的宽度
    const visibleWidth = xMax - xMin;

    // 过滤出当前通道的匹配结果
    const channelResults = matchedResults.filter(r => r.channel_name === channelName);

    // 为每个匹配的区域添加高亮
    channelResults.forEach((result, resultIndex) => {
      if (!result.tbegin || !result.tend) {
        return; // 跳过无效区域
      }

      const tbegin = parseFloat(result.tbegin);
      const tend = parseFloat(result.tend);

      // 跳过完全在可见区域外的区域
      if (tend < xMin || tbegin > xMax) {
        return;
      }

      // 确保区域在可见范围内
      const visibleBegin = Math.max(tbegin, xMin);
      const visibleEnd = Math.min(tend, xMax);

      // 计算区域宽度占比
      const widthRatio = (visibleEnd - visibleBegin) / visibleWidth;

      // 只绘制足够宽的区域，避免过小的区域影响性能
      if (widthRatio < 0.001 && (visibleEnd - visibleBegin) < 0.01) {
        return; // 跳过太小的区域
      }

      // 决定区域颜色 - 使用预定义颜色或默认颜色
      const colorMap = {
        'matched': 'rgba(255, 215, 0, 0.9)', // 金色，匹配区域
        'manual': 'rgba(220, 20, 60, 0.9)',  // 红色，人工标注
        'machine': 'rgba(0, 128, 0, 0.9)'    // 绿色，机器识别
      };

      // 根据标签类型决定颜色
      const colorKey = result.match_type || (result.is_manual ? 'manual' : 'machine');
      const highlightColor = colorMap[colorKey] || 'rgba(0, 0, 255, 0.9)'; // 默认蓝色

      // 创建唯一ID
      const seriesId = `highlight-${channelName}-${resultIndex}-${Date.now()}`;

      // 找到相应通道的数据系列
      const channelSeries = chart.series.find(s => s.name === `${channelName}_${result.shot_number}` ||
        s.name === `${channelName}_${result.shot_number}_smoothed`);

      if (channelSeries) {
        // 获取区域内的数据点
        const pointsInRange = [];
        // 找到区间内数据点
        const allX = channelsData.value.find(d => d.channelName === channelName)?.X_value || [];
        const allY = channelsData.value.find(d => d.channelName === channelName)?.Y_value || [];

        if (allX.length > 0 && allY.length > 0) {
          // 找到区间内的所有点
          for (let i = 0; i < allX.length; i++) {
            if (allX[i] >= visibleBegin && allX[i] <= visibleEnd) {
              pointsInRange.push([allX[i], allY[i]]);
            }
          }

          // 如果没有足够点，添加区间端点
          if (pointsInRange.length < 2) {
            // 添加区间端点
            const yValueBegin = allY[allX.findIndex(x => x >= visibleBegin)] || 0;
            const yValueEnd = allY[allX.findIndex(x => x >= visibleEnd)] || 0;

            pointsInRange.push([visibleBegin, yValueBegin]);
            pointsInRange.push([visibleEnd, yValueEnd]);
          }

          // 添加高亮系列 - 使用细线高亮贴合原始信号
          if (pointsInRange.length > 0) {
            chart.addSeries({
              name: seriesId,
              data: pointsInRange,
              color: highlightColor,
              lineWidth: 2,  // 使用细线条
              zIndex: 998,    // 确保在其它线条上方，但在错误线下方
              dashStyle: null, // 所有类型都使用实线，不再区分
              marker: {
                enabled: false
              },
              states: {
                hover: {
                  lineWidthPlus: 0
                }
              },
              enableMouseTracking: false
            }, false);  // 不立即重绘
          }

          // 添加标签
          if (result.label_name) {
            const labelX = visibleBegin + (visibleEnd - visibleBegin) / 2;
            const labelY = Math.max(...pointsInRange.map(p => p[1])) + 0.05;

            chart.addAnnotation({
              id: `label-${seriesId}`,
              labels: [{
                text: result.label_name,
                align: 'center',
                verticalAlign: 'top',
                x: labelX,
                y: labelY,
                backgroundColor: 'rgba(255, 255, 255, 0.8)',
                borderColor: 'silver',
                borderWidth: 1,
                borderRadius: 3,
                padding: 3,
                style: {
                  fontSize: '11px',
                  fontWeight: 'bold'
                }
              }],
              zIndex: 999,
              events: {
                click: function (e) {
                  // 记录点击的区域
                  selectedAnomaly.value = result;
                }
              }
            });
          }
        }
      } else {
        console.warn(`找不到对应的通道系列: ${channelName}_${result.shot_number}`);
      }
    });

    // 一次性重绘图表
    chart.redraw();
  } catch (error) {
    console.error(`绘制高亮区域时出错: ${error.message}`);
  }
};

// 重构状态管理部分，将原来的 loadingStates 和 renderingStates 简化
const loadingState = reactive({
  isLoading: false,
  progress: 0,
  error: null,
  progressInterval: null // 添加一个变量来存储进度更新的定时器
});

// 替换原来的渲染状态
const renderingState = reactive({
  isRendering: false,
  completed: false
});

// 使用与 OverviewBrush 类似的数据缓存机制
const processedDataCache = ref(new Map());

// 重构的 renderCharts 函数
const renderCharts = debounce(async () => {
  try {
    // 重置状态
    resetProgress();
    loadingState.isLoading = true;
    renderingState.isRendering = false;
    renderingState.completed = false;
    processedDataCache.value.clear();

    console.log(`开始渲染图表，当前采样率: ${sampling.value} kHz`);

    // 清除可能存在的旧图表
    const existingChart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (existingChart) {
      existingChart.destroy();
      console.log('已销毁旧图表实例');
    }

    // 确保有选中的通道
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      console.warn('No channels selected');
      loadingState.isLoading = false;
      renderingState.completed = true;
      return;
    }

    // 创建进度更新定时器，模拟平滑进度
    loadingState.progressInterval = setInterval(() => {
      if (loadingState.isLoading && loadingState.progress < 50) {
        // 在数据加载阶段，进度最多到50%
        loadingState.progress = Math.min(loadingState.progress + 0.5, 50);
      } else if (!loadingState.isLoading && renderingState.isRendering && loadingState.progress < 95) {
        // 在图表渲染阶段，进度从50%到95%
        // 计算渲染阶段的增量，使其平滑过渡
        const renderingIncrement = (95 - 50) / 90; // 分90步完成剩余的45%
        loadingState.progress = Math.min(loadingState.progress + renderingIncrement, 95);
      }
    }, 100);

    // 顺序处理通道数据，而不是并行处理
    const totalChannels = selectedChannels.value.length;
    const progressStep = 50 / totalChannels; // 数据处理阶段占50%进度
    
    console.log(`开始加载 ${totalChannels} 个通道的数据，采样率: ${sampling.value} kHz`);
    
    for (let i = 0; i < totalChannels; i++) {
      const channel = selectedChannels.value[i];
      try {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        console.log(`正在加载通道 ${channelKey} 的数据，采样率: ${sampling.value} kHz`);
        
        // 获取通道数据，添加 forceRefresh 参数确保在采样率变化时获取新数据
        const data = await store.dispatch('fetchChannelData', { 
          channel,
          forceRefresh: true // 强制刷新数据，确保使用当前采样率
        });
        
        if (!data) {
          throw new Error(`Failed to fetch data for channel ${channelKey}`);
        }
        
        console.log(`已成功加载通道 ${channelKey} 的数据，数据点数: ${data.X_value?.length || 0}`);
        
        // 处理通道数据
        const processedData = await processChannelDataAsync(data, channel);
        processedDataCache.value.set(channelKey, processedData);
        
        // 更新进度
        loadingState.progress = (i + 1) * progressStep;
        
        // 让UI线程有机会更新
        await new Promise(resolve => setTimeout(resolve, 0));
      } catch (error) {
        console.error(`Error processing data for channel ${channel.channel_name}:`, error);
        // 继续处理其他通道，不要因为一个通道失败而中断整个过程
      }
    }

    // 更新加载进度到50%（数据处理阶段完成）
    loadingState.progress = 50;
    console.log('所有通道数据加载完成，准备渲染图表');

    // 准备渲染图表
    try {
      await prepareAndRenderChart();
    } catch (error) {
      console.error('Error in prepareAndRenderChart:', error);
      ElMessage.error(`准备渲染图表时出错: ${error.message}`);
      loadingState.isLoading = false;
      loadingState.error = error.message;
      
      // 清除进度更新定时器
      if (loadingState.progressInterval) {
        clearInterval(loadingState.progressInterval);
        loadingState.progressInterval = null;
      }
      
      // 平滑过渡到100%
      const finalizeProgress = () => {
        const currentProgress = loadingState.progress;
        if (currentProgress < 100) {
          loadingState.progress = Math.min(currentProgress + 1, 100);
          if (loadingState.progress < 100) {
            setTimeout(finalizeProgress, 20);
          }
        }
      };
      
      finalizeProgress();
    }
  } catch (error) {
    console.error('Error rendering charts:', error);
    ElMessage.error(`加载图表时出错: ${error.message}`);
    loadingState.isLoading = false;
    loadingState.error = error.message;
    renderingState.completed = true;

    // 清除进度更新定时器
    if (loadingState.progressInterval) {
      clearInterval(loadingState.progressInterval);
      loadingState.progressInterval = null;
    }

    // 平滑过渡到100%
    const finalizeProgress = () => {
      const currentProgress = loadingState.progress;
      if (currentProgress < 100) {
        loadingState.progress = Math.min(currentProgress + 1, 100);
        if (loadingState.progress < 100) {
          setTimeout(finalizeProgress, 20);
        }
      }
    };

    finalizeProgress();
  }
}, 300);

// 新增的异步数据处理函数
const processChannelDataAsync = async (data, channel) => {
  if (!data || !data.X_value || !data.Y_value) {
    throw new Error(`Invalid data for channel ${channel.channel_name}`);
  }

  const channelKey = `${channel.channel_name}_${channel.shot_number}`;

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

  // 直接使用后端已经处理好的数据
  // 后端提供的归一化Y值，如果没有则使用默认处理方式
  let finalY = data.Y_normalized || [];
  let xValues = data.X_value;

  // 处理数字信号，使用后端判断或自行判断
  const isDigital = data.is_digital === true || 
    (data.channel_type === 'DIGITAL') || 
    (Math.min(...finalY) >= 0 && Math.max(...finalY) <= 1 && 
     finalY.every(y => Math.abs(y) < 0.1 || Math.abs(y - 1) < 0.1));

  // 对于数字信号，确保值只有0和1，避免中间值
  if (isDigital) {
    finalY = finalY.map(y => y > 0.5 ? 1 : 0);

    // 为数字信号添加额外的点，确保方波形状
    const enhancedX = [];
    const enhancedY = [];

    for (let i = 0; i < xValues.length; i++) {
      if (i > 0) {
        // 如果当前点与前一点的值不同，添加一个过渡点
        if (finalY[i] !== finalY[i - 1]) {
          // 在两点之间添加一个极小偏移的点，确保垂直线段
          const transitionX = xValues[i] - 0.0000001;
          enhancedX.push(transitionX);
          enhancedY.push(finalY[i - 1]); // 使用前一点的值
        }
      }
      enhancedX.push(xValues[i]);
      enhancedY.push(finalY[i]);
    }

    xValues = enhancedX;
    finalY = enhancedY;
  }

  // 返回处理后的数据，尽可能使用后端提供的统计值
  return {
    channelName: channel.channel_name,
    channelshotnumber: channel.shot_number,
    X_value: xValues,
    Y_value: finalY,
    Y_original: data.Y_value,
    color: channel.color,
    errorsData: errorDataResults,
    xUnit: data.X_unit || 's',
    yUnit: data.Y_unit || 'Y',
    // 使用后端提供的通道类型，如果没有则使用前端判断
    channelType: data.channel_type || (isDigital ? 'DIGITAL' : 'ANALOG'),
    channelNumber: data.channel_number || channel.channel_name,
    shotNumber: channel.shot_number,
    originalFrequency: data.originalFrequency || 0,
    // 使用后端提供的统计数据
    stats: data.stats || {
      y_min: Math.min(...data.Y_value),
      y_max: Math.max(...data.Y_value),
      y_mean: data.Y_value.reduce((a, b) => a + b, 0) / data.Y_value.length,
      y_median: [...data.Y_value].sort((a, b) => a - b)[Math.floor(data.Y_value.length / 2)],
      y_std: Math.sqrt(data.Y_value.reduce((a, b) => a + Math.pow(b - (data.Y_value.reduce((a, b) => a + b, 0) / data.Y_value.length), 2), 0) / data.Y_value.length),
      x_min: Math.min(...data.X_value),
      x_max: Math.max(...data.X_value)
    },
    is_digital: isDigital
  };
};

// 新增准备并渲染图表的函数
const prepareAndRenderChart = async () => {
  try {
    renderingState.isRendering = true;
    // 更新加载状态，表示进入图表渲染阶段
    loadingState.isLoading = false;

    // 确保进度至少为50%，表示数据加载阶段已完成
    if (loadingState.progress < 50) {
      loadingState.progress = 50;
    }

    // 清空数据数组，避免重复添加
    channelsData.value = [];
    exposeData.value = [];

    // 创建一个函数来按顺序一个一个处理通道数据
    const processChannelsSequentially = async () => {
      // 将 Map 转换为数组以便按顺序处理
      const channelEntries = Array.from(processedDataCache.value.entries());
      
      // 设置进度范围
      const progressStart = 50;
      const progressEnd = 95;
      const progressStep = (progressEnd - progressStart) / (channelEntries.length || 1);
      
      // 按顺序处理每个通道
      for (let i = 0; i < channelEntries.length; i++) {
        const [channelKey, processedData] = channelEntries[i];
        
        // 将处理后的数据添加到数组中
        channelsData.value.push(processedData);

        // 更新导出数据
        exposeData.value.push({
          channel_type: processedData.channelType,
          channel_name: processedData.channelName,
          X_value: processedData.X_value,
          X_unit: processedData.xUnit,
          Y_value: processedData.Y_original,
          Y_unit: processedData.yUnit,
          errorsData: processedData.errorsData,
          shot_number: processedData.shotNumber
        });
        
        // 更新进度
        loadingState.progress = progressStart + (i + 1) * progressStep;
        
        // 每处理完一个通道后，等待一小段时间，避免阻塞主线程
        await new Promise(resolve => setTimeout(resolve, 0));
      }
    };

    // 按顺序处理通道数据
    await processChannelsSequentially();

    // 计算全局X轴范围
    if (!xDomains.value.global && channelsData.value.length > 0) {
      const allX = channelsData.value.flatMap(d => d.X_value);
      if (allX.length > 0) {
        xDomains.value.global = [Math.min(...allX), Math.max(...allX)];
      }
    }

    // 等待数据更新到 DOM
    await nextTick();

    // 直接调用 drawCombinedChart 函数，不要使用 await
    // 这里不需要 await，因为 drawCombinedChart 内部已经处理了异步操作
    drawCombinedChart();
  } catch (error) {
    console.error('Error preparing chart data:', error);
    ElMessage.error(`准备图表数据时出错: ${error.message}`);
    renderingState.isRendering = false;
    renderingState.completed = true;
    // 确保在出错时也更新加载状态
    loadingState.isLoading = false;

    // 清除进度更新定时器
    if (loadingState.progressInterval) {
      clearInterval(loadingState.progressInterval);
      loadingState.progressInterval = null;
    }

    // 平滑过渡到100%
    const finalizeProgress = () => {
      const currentProgress = loadingState.progress;
      if (currentProgress < 100) {
        loadingState.progress = Math.min(currentProgress + 1, 100);
        if (loadingState.progress < 100) {
          setTimeout(finalizeProgress, 20);
        }
      }
    };

    finalizeProgress();
  }
};

// 计算图表高度的函数，减少debounce时间
const calculateChartHeight = () => {
  // 获取容器元素
  const container = document.querySelector('.chart-container');
  if (!container) return;

  // 获取容器的实际高度
  const containerHeight = container.clientHeight;

  // 设置图表高度为容器高度减去上下边距，不再使用固定的减去值
  // 移除了Math.max(300, containerHeight)中的300限制，允许高度随容器变化
  const newHeight = containerHeight - mainChartDimensions.value.margin.top - mainChartDimensions.value.margin.bottom;

  // 仅当高度有明显变化时才更新，降低阈值以提高响应性
  if (Math.abs(newHeight - mainChartDimensions.value.height) > 2) {
    mainChartDimensions.value.height = newHeight;

    // 更新已存在的图表高度
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (chart) {
      chart.setSize(null, newHeight);
      chart.redraw();
    }
  }
};

// 添加窗口大小变化的处理函数，减少debounce时间提高响应速度
const handleResize = debounce(() => {
  // 重新计算图表高度
  calculateChartHeight();

  const container = document.querySelector('.chart-container');
  if (container) {
    const containerWidth = container.offsetWidth;
    const newWidth = containerWidth - mainChartDimensions.value.margin.left - mainChartDimensions.value.margin.right + 70; // 增加额外宽度

    // 更新宽度
    mainChartDimensions.value.width = newWidth;

    // 更新已存在的图表
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (chart) {
      chart.setSize(newWidth, mainChartDimensions.value.height);
      chart.redraw();
    } else if (channelsData.value && channelsData.value.length > 0) {
      drawCombinedChart(); // 如果图表不存在，重新绘制
    }
  }
}, 50); // 进一步降低debounce时间以提高响应速度

// 创建一个ResizeObserver来监听容器大小变化
const resizeObserver = ref(null);

// onMounted 生命周期钩子
onMounted(async () => {
  // 设置Highcharts全局配置
  Highcharts.setOptions({
    chart: {
      reflow: true, // 确保所有图表都会重新计算尺寸
      animation: false // 禁用动画以提高性能
    }
  });

  // 延迟一下以确保DOM完全渲染
  setTimeout(() => {
    const container = document.querySelector('.chart-container');
    if (container) {
      const containerWidth = container.offsetWidth;

      // 计算适当的图表高度
      calculateChartHeight();

      mainChartDimensions.value.width = containerWidth - mainChartDimensions.value.margin.left - mainChartDimensions.value.margin.right + 10; // 增加额外宽度
    }

    if (selectedChannels.value.length > 0) {
      renderCharts();
    }
  }, 100);

  // 添加窗口大小变化监听
  window.addEventListener('resize', handleResize);

  // 初始化ResizeObserver，使用更积极的触发策略
  resizeObserver.value = new ResizeObserver(entries => {
    // 立即触发resize处理
    handleResize();
  });

  // 监听容器大小变化
  const container = document.querySelector('.chart-container');
  if (container) {
    resizeObserver.value.observe(container);
  }
  
  // 监听chart-wrapper的大小变化
  const chartWrapper = document.querySelector('.chart-wrapper');
  if (chartWrapper) {
    resizeObserver.value.observe(chartWrapper);
  }

  // 初始化异常数据
  previousAnomalies.value = JSON.parse(JSON.stringify(toRaw(store.state.anomalies)));

  // 添加键盘事件监听，用于取消框选
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isBoxSelect.value) {
      // 取消当前的框选操作
      const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
      if (chart && chart.pointer) {
        chart.pointer.drop();
      }
    }
  });
});

// 在组件卸载时移除监听器
onUnmounted(() => {
  window.removeEventListener('resize', handleResize);

  // 断开ResizeObserver连接
  if (resizeObserver.value) {
    resizeObserver.value.disconnect();
  }

  // 移除键盘事件监听
  window.removeEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isBoxSelect.value) {
      const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
      if (chart && chart.pointer) {
        chart.pointer.drop();
      }
    }
  });

  // 终止Worker
  chartWorkerManager.terminate();
});

// 监听selectedChannels变化，当通道列表变化时，可能需要重新选择标注通道
watch(selectedChannels, (newChannels, oldChannels) => {
  // 如果当前选择的标注通道不在新的通道列表中，清空选择
  if (selectedChannelForAnnotation.value) {
    const channelExists = newChannels.some(channel =>
      `${channel.channel_name}_${channel.shot_number}` === selectedChannelForAnnotation.value
    );

    if (!channelExists) {
      selectedChannelForAnnotation.value = '';

      // 如果当前是框选模式，提示用户重新选择通道
      if (isBoxSelect.value) {
        ElMessage.warning('您选择的标注通道已被移除，请重新选择');
        showChannelSelectDialog.value = true;
      }
    }
  }

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
    // 只处理颜色变化的通道，直接更新DOM元素颜色，不触发重绘
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (chart) {
      newChannels.forEach(newCh => {
        const oldCh = oldChannels.find(
          old => `${old.channel_name}_${old.shot_number}` === `${newCh.channel_name}_${newCh.shot_number}`
        );
        if (oldCh && oldCh.color !== newCh.color) {
          const channelKey = `${newCh.channel_name}_${newCh.shot_number}`;
          const color = newCh.color;
          
          // 更新 Vuex 存储
          store.commit('updateChannelColor', { channel_key: channelKey, color });
          
          // 直接更新图表中的颜色，不调用updateChannelColor函数
          chart.series.forEach(series => {
            if (series.name === channelKey || series.name === `${channelKey}_smoothed`) {
              // 直接更新颜色属性
              series.color = color;
              
              // 更新线条的颜色
              if (series.graph) {
                series.graph.attr({
                  stroke: color
                });
              }
              
              // 更新区域填充颜色（如果有）
              if (series.area) {
                series.area.attr({
                  fill: color
                });
              }
              
              // 更新标记点颜色（如果有）
              if (series.markerGroup) {
                series.markerGroup.attr({
                  fill: color,
                  stroke: color
                });
              }
              
              // 更新内部选项
              series.options.color = color;
            }
          });
          
          // 更新数据中的颜色
          const channelDataIndex = channelsData.value.findIndex(
            d => `${d.channelName}_${d.channelshotnumber}` === channelKey
          );
          if (channelDataIndex !== -1) {
            channelsData.value[channelDataIndex].color = color;
          }
        }
      });
    }
  } else {
    // 如果不是仅颜色变化，则执行完整的重新渲染
    channelsData.value = [];
    exposeData.value = [];
    nextTick().then(() => {
      renderCharts();
    });
  }
}, { deep: true });

watch(sampling, (newSamplingRate, oldSamplingRate) => {
  console.log(`[重要] 采样率从 ${oldSamplingRate} kHz 变更为 ${newSamplingRate} kHz，准备刷新数据和图表`);
  sampleRate.value = newSamplingRate;
  
  // 清空处理后的数据缓存
  processedDataCache.value.clear();
  
  // 重置进度状态
  resetProgress();
  
  // 销毁现有图表，避免重叠渲染
  const existingChart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
  if (existingChart) {
    existingChart.destroy();
    console.log('已销毁现有图表，准备重新渲染');
  }
  
  // 使用 store 的全局采样率更新机制，这会触发所有选中通道的数据刷新
  store.dispatch('updateSampling', newSamplingRate).then(() => {
    console.log('所有通道数据已更新，准备重新渲染图表');
    // 在数据更新后触发图表重新渲染
    // 由于添加了对 channelDataCache 的监听，图表会自动重新渲染
    // 但为确保可靠性，这里仍然手动调用渲染函数
    setTimeout(() => {
      renderCharts();
    }, 500);
  }).catch(error => {
    console.error('更新采样率数据时出错:', error);
    ElMessage.error(`更新采样率数据时出错: ${error.message}`);
    // 即使出错也尝试渲染
    renderCharts();
  });
});

watch(smoothnessValue, () => {
  renderCharts();
});

// 监听 channelDataCache 变化，当通道数据缓存更新时重新渲染图表
watch(channelDataCache, () => {
  console.log('通道数据缓存已更新，重新渲染图表');
  // 清空已处理的数据缓存
  processedDataCache.value.clear();
  // 使用setTimeout确保状态完全更新后再渲染
  setTimeout(() => {
    renderCharts();
  }, 300);
}, { deep: true });

watch(
  () => selectedChannels.value.map(channel => channel.errors.map(error => error.color)),
  (newErrorColors, oldErrorColors) => {
    if (JSON.stringify(newErrorColors) !== JSON.stringify(oldErrorColors)) {
      renderCharts();
    }
  },
  { deep: true }
);

// 添加对 brush_begin 和 brush_end 的监听
const updateChartRangeDebounced = debounce(() => {
  // 解析 brush 范围
  const beginValue = parseFloat(brush_begin.value);
  const endValue = parseFloat(brush_end.value);

  // 验证值的有效性
  if (isNaN(beginValue) || isNaN(endValue) || beginValue >= endValue) {
    console.warn('无效的 brush 范围:', beginValue, endValue);
    return;
  }
  try {
    xDomains.value.global = [beginValue, endValue];
    if (originalDomains.value.global) {
      originalDomains.value.global.x = [beginValue, endValue];
    } else {
      originalDomains.value.global = {
        x: [beginValue, endValue],
        y: [-1, 1]
      };
    }

    // 销毁现有图表
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (chart) {
      // 先记住当前的Y轴范围
      const yMin = chart.yAxis[0].min;
      const yMax = chart.yAxis[0].max;

      // 保存Y轴范围
      if (originalDomains.value.global) {
        originalDomains.value.global.y = [yMin, yMax];
      }

      // 完全销毁图表
      chart.destroy();

      // 重新绘制图表（确保使用新的范围）
      nextTick(() => {
        // 直接调用 drawCombinedChart，不要使用 await
        drawCombinedChart(); // 这将使用更新后的范围重新绘制图表
      });
    }
  } catch (err) {
    console.error('更新图表范围时出错:', err);
  }
}, 300);

// 监听 brush_begin 和 brush_end 的变化
watch([brush_begin, brush_end], () => {
  // 只有在图表已经加载并且渲染完成的情况下才应用范围更新
  if (renderingState.completed && channelsData.value.length > 0) {
    updateChartRangeDebounced();
  }
});

// 修改计算属性 getProgressPercentage
const getProgressPercentage = computed(() => {
  // 直接返回当前进度值，由定时器控制平滑增长
  return Math.round(loadingState.progress);
});

// 在 script setup 部分添加原始域存储
const originalDomains = ref({}); // 存储原始的显示范围

// 添加异常标注相关的状态
const currentAnomaly = reactive({});
const showAnomalyForm = ref(false);
const selectedChannelForAnnotation = ref('');
const showChannelSelectDialog = ref(false);
const isBoxSelect = computed(() => store.state.isBoxSelect);
const previousAnomalies = ref({});

// 添加时间轴范围计算属性
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

// 添加关闭异常表单的函数
const closeAnomalyForm = () => {
  showAnomalyForm.value = false;
};

// 添加保存异常的函数
const saveAnomaly = () => {
  if (!selectedChannelForAnnotation.value) {
    ElMessage.error('请选择一个通道后再保存异常标注');
    return;
  }

  if (currentAnomaly) {
    // 获取选择的通道
    const channelParts = selectedChannelForAnnotation.value.split('_');
    const channelName = channelParts[0];
    const shotNumber = channelParts[1];
    const fullChannelName = selectedChannelForAnnotation.value;

    // 先移除临时选框
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (chart) {
      chart.xAxis[0].removePlotBand(`temp-band-${currentAnomaly.id}`);

      // 移除临时选区的按钮
      if (currentAnomaly.id && currentAnomaly.id.startsWith('temp_')) {
        const deleteButton = document.querySelector(`.delete-button-${currentAnomaly.id}`);
        if (deleteButton) {
          deleteButton.remove();
        }

        const editButton = document.querySelector(`.edit-button-${currentAnomaly.id}`);
        if (editButton) {
          editButton.remove();
        }
      }
    }

    // 格式化当前时间
    const now = new Date();
    const formattedTime = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

    // 保存旧ID，用于后续检查是否是新创建
    const isNewAnomaly = !currentAnomaly.id || currentAnomaly.id.startsWith('temp_');
    const oldId = currentAnomaly.id;

    // 如果是新创建的异常，需要添加ID和时间
    if (isNewAnomaly) {
      currentAnomaly.id = `${store.state.person}_${Date.now()}`;
      currentAnomaly.person = store.state.person;
      currentAnomaly.annotationTime = formattedTime;
    }

    const payload = {
      channelName: fullChannelName,
      anomaly: {
        ...currentAnomaly,
        channelName: fullChannelName, // 确保异常对象也有channelName
        anomalyCategory: decodeChineseText(currentAnomaly.anomalyCategory),
        anomalyDiagnosisName: decodeChineseText(currentAnomaly.anomalyDiagnosisName),
        anomalyDescription: decodeChineseText(currentAnomaly.anomalyDescription),
        isStored: true
      },
    };

    // 如果是新创建的异常，添加到store
    if (isNewAnomaly) {
      store.dispatch('addAnomaly', payload);
    } else {
      // 否则更新异常
      store.dispatch('updateAnomaly', payload);
    }

    // 立即在图表上添加或更新异常显示
    addAnomalyToChart(fullChannelName, payload.anomaly);

    // 关闭编辑框
    showAnomalyForm.value = false;
    ElMessage.success('异常标注信息已保存');
    Object.keys(currentAnomaly).forEach((key) => {
      delete currentAnomaly[key];
    });
  }
};

// 添加删除异常的函数
const deleteAnomaly = () => {
  if (currentAnomaly && currentAnomaly.id) {
    // 先移除图表上的选框
    removeAnomalyFromChart(currentAnomaly.channelName, currentAnomaly.id);

    // 然后从store中删除
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

// 更新异常在图表中的显示
const updateAnomalyDisplay = (channelName, anomalyId) => {
  const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
  if (!chart) return;

  // 获取异常数据
  const anomalies = store.getters.getAnomaliesByChannel(channelName);
  const anomaly = anomalies.find(a => a.id === anomalyId);
  if (!anomaly) return;

  // 移除旧的高亮
  removeAnomalyFromChart(channelName, anomalyId);

  // 添加新的高亮
  addAnomalyToChart(channelName, anomaly);
};

// 从图表中移除异常显示
const removeAnomalyFromChart = (channelName, anomalyId) => {
  const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
  if (!chart) return;

  // 移除高亮线条
  const highlightSeries = chart.series.find(s => s.options.id === `anomaly-highlight-${anomalyId}`);
  if (highlightSeries) {
    highlightSeries.remove(false);
  }

  // 移除plotBand
  chart.xAxis[0].removePlotBand(`band-${anomalyId}`);
  chart.xAxis[0].removePlotBand(`band-end-${anomalyId}`);

  // 移除按钮
  const deleteButton = document.querySelector(`.delete-button-${anomalyId}`);
  if (deleteButton) {
    deleteButton.remove();
  }

  const editButton = document.querySelector(`.edit-button-${anomalyId}`);
  if (editButton) {
    editButton.remove();
  }

  chart.redraw();
};

// 向图表添加异常显示
const addAnomalyToChart = (channelName, anomaly) => {
  try {
    const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (!chart) return;

    // 添加plotBand
    chart.xAxis[0].addPlotBand({
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
          const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
          const storedAnomaly = storedAnomalies.find(a => a.id === anomaly.id);

          if (storedAnomaly) {
            Object.assign(currentAnomaly, {
              ...storedAnomaly,
              channelName: channelName
            });
            selectedChannelForAnnotation.value = channelName;
            showAnomalyForm.value = true;
          }
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

    // 添加高亮线条
    const data = channelDataCache.value[channelName];
    let pointsInRange = []; // 定义pointsInRange变量

    if (data && data.X_value && data.Y_value) {
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
        // 查找对应通道的系列
        const channelSeries = chart.series.find(s =>
          s.name === `${channelName}` ||
          s.name === `${channelName}_smoothed`
        );

        const color = channelSeries ? channelSeries.color : (anomaly.isStored ? 'rgba(255, 0, 0, 0.8)' : 'rgba(255, 165, 0, 0.8)');

        chart.addSeries({
          id: `anomaly-highlight-${anomaly.id}`,
          name: `异常区域-${anomaly.id}`,
          data: pointsInRange,
          color: color,
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
        }, false); // 不立即重绘
      }
    }

    // 计算按钮位置 - 修改为基于异常区域的位置
    const anomalyEndX = chart.xAxis[0].toPixels(anomaly.endX);
    const buttonWidth = 12; // 增加按钮尺寸
    const buttonHeight = 12; // 增加按钮尺寸
    const buttonX = anomalyEndX - buttonWidth - 5;

    // 计算Y轴位置 - 使用异常区域的Y值
    let buttonY;

    // 找到异常区域内的最大Y值和最小Y值
    if (pointsInRange && pointsInRange.length > 0) {
      const yValues = pointsInRange.map(p => p[1]);
      const maxY = Math.max(...yValues);

      // 将按钮放在异常区域的上方
      const yPixelMax = chart.yAxis[0].toPixels(maxY);

      // 放在异常区域上方15个像素的位置
      buttonY = yPixelMax - buttonHeight - 15;

      // 确保按钮不会超出图表顶部
      buttonY = Math.max(buttonY, 10);
    } else {
      // 如果没有找到点，放在图表中间位置
      buttonY = chart.chartHeight / 10; // 放在上部1/3处
    }

    // 删除按钮
    const deleteButton = chart.renderer.button(
      '×',
      buttonX - 2,
      buttonY - buttonWidth * 2.8,
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
        // 移除plotBands和高亮线条
        removeAnomalyFromChart(channelName, anomaly.id);
      },
      {
        fill: '#f56c6c',
        style: {
          color: 'white',
          fontWeight: 'bold',
          fontSize: '16px', // 增加字体大小
          textAlign: 'center',
          lineHeight: '24px', // 调整行高
          paddingTop: '0px',
          paddingLeft: '0px'
        },
        r: 6, // 增加圆角
        width: buttonWidth,
        height: buttonHeight,
        zIndex: 999
      }
    )
      .attr({
        'class': `delete-button-${anomaly.id}`,
        'zIndex': 999
      })
      .css({
        cursor: 'pointer',
        boxShadow: '0 2px 4px rgba(0,0,0,0.2)' // 添加阴影
      })
      .add();

    // 编辑按钮
    const editButton = chart.renderer.button(
      '✎',
      buttonX - 2,
      buttonY,
      function () {
        const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
        const storedAnomaly = storedAnomalies.find(a => a.id === anomaly.id);

        if (storedAnomaly) {
          Object.assign(currentAnomaly, {
            ...storedAnomaly,
            channelName: channelName
          });
          selectedChannelForAnnotation.value = channelName;
          showAnomalyForm.value = true;
        }
      },
      {
        fill: '#409eff',
        style: {
          color: 'white',
          fontWeight: 'bold',
          fontSize: '16px', // 增加字体大小
          textAlign: 'center',
          lineHeight: '24px', // 调整行高
          paddingTop: '0px',
          paddingLeft: '0px'
        },
        r: 6, // 增加圆角
        width: buttonWidth,
        height: buttonHeight,
        zIndex: 999
      }
    )
      .attr({
        'class': `edit-button-${anomaly.id}`,
        'zIndex': 999
      })
      .css({
        cursor: 'pointer',
        boxShadow: '0 2px 4px rgba(0,0,0,0.2)' // 添加阴影
      })
      .add();

    chart.redraw();
  } catch (error) {
    console.error('添加异常到图表时出错:', error);
  }
};

// 监听异常数据变化
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
      removeAnomalyFromChart(channelName, anomaly.id);
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

// 监听isBoxSelect变化
watch(isBoxSelect, (newValue) => {
  const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
  if (chart) {
    // 更新图表的缩放类型，但不触发重绘
    chart.options.chart.zoomType = newValue ? 'x' : 'xy';
    
    // 直接更新内部属性，而不是调用 chart.update
    if (chart.pointer) {
      chart.pointer.zoomX = newValue;
      chart.pointer.zoomY = !newValue;
    }

    // 如果开启框选模式，但没有选择通道，显示提示
    if (newValue && selectedChannels.value.length === 0) {
      ElMessage.warning('请先选择至少一个通道');
      // 自动关闭框选模式
      store.dispatch('updateIsBoxSelect', false);
    } else if (newValue) {
      // 已开启框选模式，显示提示
      ElMessage.info('已开启框选模式，请在图表上框选区域进行标注');
    }
    
    // 不调用 chart.redraw()，避免重绘整个图表
  }
});

// 修改drawCombinedChart函数，添加框选异常标注功能
const drawCombinedChart = () => {
  try {
    renderingState.isRendering = true;

    if (channelsData.value.length === 0) {
      renderingState.completed = true;

      // 清除进度更新定时器
      if (loadingState.progressInterval) {
        clearInterval(loadingState.progressInterval);
        loadingState.progressInterval = null;
      }

      // 平滑过渡到100%
      const finalizeProgress = () => {
        const currentProgress = loadingState.progress;
        if (currentProgress < 100) {
          loadingState.progress = Math.min(currentProgress + 1, 100);
          if (loadingState.progress < 100) {
            setTimeout(finalizeProgress, 20);
          }
        }
      };

      finalizeProgress();
      return; // 数据为空，不绘制图表
    }

    // 计算所有数据的范围
    const allX = channelsData.value.flatMap(d => d.X_value);
    if (allX.length === 0) {
      console.warn('没有有效的X轴数据点');
      renderingState.completed = true;

      // 清除进度更新定时器
      if (loadingState.progressInterval) {
        clearInterval(loadingState.progressInterval);
        loadingState.progressInterval = null;
      }

      // 平滑过渡到100%
      const finalizeProgress = () => {
        const currentProgress = loadingState.progress;
        if (currentProgress < 100) {
          loadingState.progress = Math.min(currentProgress + 1, 100);
          if (loadingState.progress < 100) {
            setTimeout(finalizeProgress, 20);
          }
        }
      };

      finalizeProgress();
      return;
    }

    const xExtent = xDomains.value.global || [Math.min(...allX), Math.max(...allX)];

    // 检查xExtent是否有效
    if (!Array.isArray(xExtent) || xExtent.length !== 2 ||
      isNaN(xExtent[0]) || isNaN(xExtent[1]) || xExtent[0] >= xExtent[1]) {
      console.warn('无效的X轴范围:', xExtent);
      renderingState.completed = true;
      return;
    }

    // 检查是否有任何通道提供了统计数据
    const hasStats = channelsData.value.some(channel => channel.stats && 
      channel.stats.y_min !== undefined && channel.stats.y_max !== undefined);

    // 如果至少有一个通道提供了统计数据，使用归一化的-1到1范围
    const padding = 0.05;
    // 定义yExtent变量
    let yExtent;
    
    if (!hasStats) {
      // 默认归一化范围为-1到1，增加5%的上下空白用于视觉效果
      yExtent = [-1 - padding, 1 + padding]; // 范围为 -1.05 到 1.05，但刻度只显示-1到1
    } else {
      yExtent = [-1 - padding, 1 + padding]; // 仍然使用标准归一化范围，因为所有通道都已归一化
    }

    // 如果存在原始域设置，保存Y轴范围
    if (!originalDomains.value.global) {
      originalDomains.value.global = {
        x: xExtent,
        y: yExtent
      };
    }

    // 使用保存的范围
    const yMin = yExtent[0];
    const yMax = yExtent[1];

    // 创建一个批量准备数据系列的函数
    const prepareSeries = () => {
      // 准备 Highcharts 的数据系列
      const series = [];
      
      // 为每个通道创建数据系列
      channelsData.value.forEach((data) => {
        // 确保X和Y数组长度一致
        if (!data.X_value || !data.Y_value || data.X_value.length !== data.Y_value.length) {
          console.warn(`Channel ${data.channelName} data arrays length mismatch or undefined: X=${data.X_value?.length}, Y=${data.Y_value?.length}`);
          return;
        }

        // 创建完整的数据点数组
        const pointsData = data.X_value.map((x, i) => ([x, data.Y_value[i]]));

        // 创建主线数据
        const mainLineSeries = {
          name: `${data.channelName}_${data.channelshotnumber}`,
          data: pointsData,
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
          connectNulls: true, // 连接空值点
          step: data.is_digital || data.channelType === 'DIGITAL' ? 'left' : false, // 使用后端判断的数字信号类型
          turboThreshold: 0 // 禁用 turboThreshold 以允许大量数据点
        };
        series.push(mainLineSeries);

        // 如果有平滑值，添加平滑线
        if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
          let smoothedYValue = [];
          try {
            smoothedYValue = interpolateData(data.Y_value, smoothnessValue.value);
          } catch (error) {
            console.error(`平滑处理数据出错: ${error.message}`);
            smoothedYValue = [...data.Y_value]; // 出错时使用原始数据
          }

          // 确保平滑后的Y值数组长度与X值数组一致
          if (smoothedYValue.length !== data.X_value.length) {
            console.warn(`Smoothed Y array length (${smoothedYValue.length}) does not match X array length (${data.X_value.length})`);
            if (smoothedYValue.length > data.X_value.length) {
              smoothedYValue = smoothedYValue.slice(0, data.X_value.length);
            } else {
              // 填充缺失值
              while (smoothedYValue.length < data.X_value.length) {
                smoothedYValue.push(smoothedYValue[smoothedYValue.length - 1] || 0);
              }
            }
          }

          const smoothedPointsData = data.X_value.map((x, i) => ([x, smoothedYValue[i]]));

          const smoothedLineSeries = {
            name: `${data.channelName}_${data.channelshotnumber}_smoothed`,
            data: smoothedPointsData,
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
            connectNulls: true, // 连接空值点
            enableMouseTracking: false,
            step: data.is_digital || data.channelType === 'DIGITAL' ? 'left' : false, // 使用后端判断的数字信号类型
            turboThreshold: 0 // 禁用 turboThreshold 以允许大量数据点
          };
          series.push(smoothedLineSeries);
        }

        // 处理错误数据 - 但不立即添加到series，而是返回它们
        if (data.errorsData && data.errorsData.length > 0) {
          data.errorsData.forEach(errorData => {
            if (!errorData || !Array.isArray(errorData) || errorData.length < 2) {
              return; // 跳过无效的错误数据
            }

            // 解构人工标注和机器识别的错误数据
            const [manualErrors, machineErrors] = errorData;

            // 辅助函数：根据时间范围获取对应的数据点
            const getDataPointsInRange = (xRange) => {
              if (!Array.isArray(xRange) || xRange.length !== 2) {
                return [];
              }

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
            if (manualErrors && Array.isArray(manualErrors) && manualErrors.length > 0) {
              manualErrors.forEach((error, errorIndex) => {
                if (error && error.X_error && Array.isArray(error.X_error) && error.X_error.length > 0) {
                  error.X_error.forEach((xRange, rangeIndex) => {
                    const errorPoints = getDataPointsInRange(xRange);
                    if (errorPoints.length > 0) {
                      // 创建错误标记系列
                      const errorSeries = {
                        name: `${data.channelName}_manual_error_${errorIndex}_${rangeIndex}`,
                        data: errorPoints,
                        color: error.color || 'rgba(220, 20, 60, 0.3)',
                        lineWidth: 10,
                        zIndex: 999,
                        marker: {
                          enabled: false
                        },
                        states: {
                          hover: {
                            lineWidthPlus: 0
                          }
                        },
                        enableMouseTracking: false,
                        turboThreshold: 0 // 禁用 turboThreshold 以允许大量数据点
                      };
                      series.push(errorSeries);
                    }
                  });
                }
              });
            }

            // 处理机器识别的错误
            if (machineErrors && Array.isArray(machineErrors) && machineErrors.length > 0) {
              machineErrors.forEach((error, errorIndex) => {
                if (error && error.X_error && Array.isArray(error.X_error) && error.X_error.length > 0) {
                  error.X_error.forEach((xRange, rangeIndex) => {
                    const errorPoints = getDataPointsInRange(xRange);
                    if (errorPoints.length > 0) {
                      // 创建错误标记系列
                      const errorSeries = {
                        name: `${data.channelName}_machine_error_${errorIndex}_${rangeIndex}`,
                        data: errorPoints,
                        color: error.color || 'rgba(220, 20, 60, 0.3)',
                        lineWidth: 10,
                        zIndex: 999,
                        marker: {
                          enabled: false
                        },
                        states: {
                          hover: {
                            lineWidthPlus: 0
                          }
                        },
                        enableMouseTracking: false,
                        turboThreshold: 0 // 禁用 turboThreshold 以允许大量数据点
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
      
      return series;
    };
    
    // 批量准备所有系列数据
    const series = prepareSeries();

    // 确保有数据系列
    if (series.length === 0) {
      console.warn('没有有效的数据系列可以绘制');
      renderingState.completed = true;
      return;
    }

    // 销毁现有图表（如果有）
    const existingChart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
    if (existingChart) {
      existingChart.destroy();
    }

    // 创建 Highcharts 图表
    Highcharts.chart('combined-chart', {
      chart: {
        type: 'line',
        zoomType: isBoxSelect.value ? 'x' : 'xy',
        panning: true,
        panKey: 'shift',
        animation: false,
        height: mainChartDimensions.value.height,
        marginBottom: 80,
        marginTop: 30,
        marginRight: 10,
        spacingRight: 0,
        spacing: [0, 0, 0, 0], // 设置为0，确保图表不会自动添加额外的空间
        reflow: true, // 确保图表会重新计算尺寸
        events: {
          selection: function (event) {
            if (event.resetSelection) {
              // 点击空白处，恢复到总览条的范围
              if (brush_begin.value && brush_end.value) {
                // 恢复到总览条的范围
                xDomains.value.global = [parseFloat(brush_begin.value), parseFloat(brush_end.value)];
                
                // 计算带padding的Y轴范围
                const padding = 0.05;
                const yMinWithPadding = -1 - padding;
                const yMaxWithPadding = 1 + padding;
                
                // 重置 Y 轴到默认范围（带padding）
                originalDomains.value.global = {
                  x: [parseFloat(brush_begin.value), parseFloat(brush_end.value)],
                  y: [yMinWithPadding, yMaxWithPadding]
                };

                // 直接设置坐标轴范围，而不是重新调用 drawCombinedChart
                this.xAxis[0].setExtremes(
                  parseFloat(brush_begin.value),
                  parseFloat(brush_end.value),
                  false
                );
                this.yAxis[0].setExtremes(yMinWithPadding, yMaxWithPadding, true);

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
            } else if (event.xAxis) {
              // 如果是框选模式
              if (isBoxSelect.value) {
                // 处理框选标注
                const [x0, x1] = [event.xAxis[0].min, event.xAxis[0].max];

                // 确保x0 < x1
                const startX = Math.min(x0, x1);
                const endX = Math.max(x0, x1);

                // 如果选择范围太小，则忽略
                if (Math.abs(endX - startX) < 0.001) {
                  return false;
                }

                // 创建临时异常对象，但不添加到store
                const tempAnomaly = {
                  id: `temp_${Date.now()}`,
                  startX: startX,
                  endX: endX,
                  anomalyCategory: '',
                  anomalyDiagnosisName: '',
                  anomalyDescription: '',
                  isStored: false
                };

                // 清空当前异常对象并设置新的临时值
                Object.keys(currentAnomaly).forEach(key => {
                  delete currentAnomaly[key];
                });

                // 设置临时异常对象
                Object.assign(currentAnomaly, tempAnomaly);

                // 清空通道选择
                selectedChannelForAnnotation.value = '';

                // 立即在图表上显示临时选框（黄色）
                // 但不指定特定通道，只添加plotBand
                const chart = this;
                chart.xAxis[0].addPlotBand({
                  id: `temp-band-${tempAnomaly.id}`,
                  from: tempAnomaly.startX,
                  to: tempAnomaly.endX,
                  color: 'rgba(255, 165, 0, 0.2)',
                  borderColor: 'orange',
                  borderWidth: 1,
                  zIndex: 5,
                  label: {
                    text: `(${tempAnomaly.startX.toFixed(3)} - ${tempAnomaly.endX.toFixed(3)})`,
                    align: 'center',
                    verticalAlign: 'top',
                    y: -15,
                    style: {
                      color: '#ff8c00',
                      fontWeight: 'bold',
                      fontSize: '12px'
                    }
                  }
                });

                // 计算按钮位置
                const anomalyEndX = chart.xAxis[0].toPixels(tempAnomaly.endX);
                const buttonWidth = 12; // 增加按钮尺寸
                const buttonHeight = 12; // 增加按钮尺寸
                const buttonX = anomalyEndX - buttonWidth - 5;
                const buttonY = chart.chartHeight / 10; // 放在上部1/3处

                // 添加临时选区的删除按钮
                const deleteButton = chart.renderer.button(
                  '×',
                  buttonX - 2,
                  buttonY - buttonWidth * 2.8,
                  function () {
                    // 移除临时选区
                    chart.xAxis[0].removePlotBand(`temp-band-${tempAnomaly.id}`);
                    // 关闭异常表单
                    showAnomalyForm.value = false;
                    // 清空当前异常对象
                    Object.keys(currentAnomaly).forEach(key => {
                      delete currentAnomaly[key];
                    });
                    // 移除按钮
                    this.destroy();
                    const editBtn = document.querySelector(`.edit-button-${tempAnomaly.id}`);
                    if (editBtn) {
                      editBtn.remove();
                    }
                  },
                  {
                    fill: '#f56c6c',
                    style: {
                      color: 'white',
                      fontWeight: 'bold',
                      fontSize: '16px',
                      textAlign: 'center',
                      lineHeight: '24px',
                      paddingTop: '0px',
                      paddingLeft: '0px'
                    },
                    r: 6,
                    width: buttonWidth,
                    height: buttonHeight,
                    zIndex: 999
                  }
                )
                  .attr({
                    'class': `delete-button-${tempAnomaly.id}`,
                    'zIndex': 999
                  })
                  .css({
                    cursor: 'pointer',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                  })
                  .add();

                // 添加临时选区的编辑按钮
                const editButton = chart.renderer.button(
                  '✎',
                  buttonX - 2,
                  buttonY,
                  function () {
                    // 打开异常表单进行编辑
                    showAnomalyForm.value = true;
                  },
                  {
                    fill: '#409eff',
                    style: {
                      color: 'white',
                      fontWeight: 'bold',
                      fontSize: '16px',
                      textAlign: 'center',
                      lineHeight: '24px',
                      paddingTop: '0px',
                      paddingLeft: '0px'
                    },
                    r: 6,
                    width: buttonWidth,
                    height: buttonHeight,
                    zIndex: 999
                  }
                )
                  .attr({
                    'class': `edit-button-${tempAnomaly.id}`,
                    'zIndex': 999
                  })
                  .css({
                    cursor: 'pointer',
                    boxShadow: '0 2px 4px rgba(0,0,0,0.2)'
                  })
                  .add();

                // 打开异常表单，让用户选择通道
                showAnomalyForm.value = true;

                return false; // 阻止默认缩放行为
              } else if (!isBoxSelect.value) {
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

                // 更新视图范围但不重绘整个图表
                this.xAxis[0].setExtremes(newXDomain[0], newXDomain[1], false);
                this.yAxis[0].setExtremes(newYDomain[1], newYDomain[0], true);

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
            }
            return false; // 阻止默认缩放行为
          },
          // 添加双击事件处理
          click: function (event) {
            // 检查是否是双击（计算两次点击之间的时间间隔）
            const now = new Date().getTime();
            const lastClick = this.lastClickTime || 0;
            this.lastClickTime = now;

            if (now - lastClick < 300) { // 如果两次点击间隔小于300毫秒，认为是双击
              if (brush_begin.value && brush_end.value) {
                // 恢复到总览条的范围
                const beginValue = parseFloat(brush_begin.value);
                const endValue = parseFloat(brush_end.value);
                
                // 计算带padding的Y轴范围
                const padding = 0.05;
                const yMinWithPadding = -1 - padding;
                const yMaxWithPadding = 1 + padding;

                // 设置坐标轴范围
                this.xAxis[0].setExtremes(beginValue, endValue);
                this.yAxis[0].setExtremes(yMinWithPadding, yMaxWithPadding);

                // 更新内部状态
                xDomains.value.global = [beginValue, endValue];
                originalDomains.value.global = {
                  x: [beginValue, endValue],
                  y: [yMinWithPadding, yMaxWithPadding]
                };

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
            }
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
            fontSize: '1.3em',
            fontWeight: 'medium'
          },
          align: 'middle',
          y: -15
        },
        gridLineWidth: 1,
        gridLineDashStyle: 'ShortDash',
        gridLineColor: '#ccc',
        // 添加网格线设置，随缩放调整
        tickAmount: 10, // 指定标记数量，确保缩放时网格适应
        startOnTick: false, // 确保不从刻度线开始
        endOnTick: false, // 确保不在刻度线结束
        minPadding: 0, // 不添加左侧内边距
        maxPadding: 0, // 不添加右侧内边距
        labels: {
          style: {
            fontSize: '1.2em',
            fontWeight: 'medium'
          },
          y: 25,
          formatter: function () {
            // 格式化X轴标签，避免过多小数位
            return this.value.toFixed(2);
          }
        }
      },
      yAxis: {
        min: yMin,
        max: yMax,
        title: {
          text: 'Normalization',
          style: {
            fontSize: '1.4em',
            fontWeight: 'medium'
          }
        },
        gridLineWidth: 1,
        gridLineDashStyle: 'ShortDash',
        gridLineColor: '#ccc',
        // 添加网格线设置，随缩放调整
        tickAmount: 8, // 指定Y轴标记数量
        startOnTick: false,
        endOnTick: false,
        tickPositions: [-1, -0.8, -0.6, -0.4, -0.2, 0, 0.2, 0.4, 0.6, 0.8, 1], // 强制指定刻度位置
        minorTickInterval: null, // 禁用次要刻度
        minorGridLineWidth: 0, // 禁用次要网格线
        showFirstLabel: true, // 确保显示第一个标签
        showLastLabel: true, // 确保显示最后一个标签
        lineWidth: 1, // 显示Y轴线
        lineColor: '#ccc', // 设置Y轴线颜色
        plotLines: [{ // 添加上边界线
          color: '#ccc',
          width: 1,
          value: 1,
          dashStyle: 'ShortDash',
          zIndex: 1
        }, { // 添加padding区域的上边界线
          color: '#ccc',
          width: 1,
          value: 1 + 0.05, // 添加在1.05位置的边界线
          dashStyle: 'ShortDash',
          zIndex: 1
        }, { // 添加下边界线
          color: '#ccc',
          width: 1,
          value: -1,
          dashStyle: 'ShortDash',
          zIndex: 1
        }, { // 添加padding区域的下边界线
          color: '#ccc',
          width: 1,
          value: -1 - 0.05, // 添加在-1.05位置的边界线
          dashStyle: 'ShortDash',
          zIndex: 1
        }],
        labels: {
          style: {
            fontSize: '1em',
            fontWeight: 'medium'
          },
          formatter: function () {
            // 只显示-1到1范围内的刻度值
            return (this.value >= -1 && this.value <= 1) ? this.value.toFixed(1) : '';
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
          turboThreshold: 0, // 禁用数据量的限制（默认为1000点）
          states: {
            inactive: {
              opacity: 1
            },
            hover: {
              enabled: false // 禁用悬停状态，避免渲染问题
            },
            point: {
              events: {
                click: null // 禁用点上的单击事件，避免干扰双击检测
              }
            },
            stickyTracking: false, // 禁用粘性跟踪，减少事件冲突
            boostThreshold: 5000, // 提高性能阈值，确保大量数据点时的性能
            connectNulls: true, // 全局设置连接空值点
            dataGrouping: {
              enabled: false // 禁用数据分组，确保所有点都被绘制
            },
            gapSize: 0, // 禁用间隙大小，确保所有点连接
            cropThreshold: 100000, // 提高裁剪阈值，避免缩放时数据点被跳过
            findNearestPointBy: 'x' // 按X轴查找最近点，提高连接精度
          },
          line: {
            connectNulls: true, // 连接空值点
            marker: {
              enabled: false // 禁用标记点
            }
          }
        },
        line: {
          lineWidth: 1.5, // 全局线宽设置
          connectNulls: true, // 连接空值点
          marker: {
            enabled: false // 禁用标记点
          }
        }
      },
      credits: {
        enabled: false
      },
      series: series,
      exporting: {
        enabled: false
      },
      accessibility: {
        enabled: false // 禁用无障碍功能，避免相关错误
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

      // 绘制已有的异常标注
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const channelAnomalies = store.getters.getAnomaliesByChannel(channelKey);
      if (channelAnomalies && channelAnomalies.length > 0) {
        channelAnomalies.forEach(anomaly => {
          addAnomalyToChart(channelKey, anomaly);
        });
      }
    });

    // 确保图表高度正确
    nextTick(() => {
      const chart = Highcharts.charts.find(chart => chart && chart.renderTo.id === 'combined-chart');
      if (chart) {
        // 手动设置图表大小，增加一些额外的宽度以填充右侧空间
        chart.setSize(
          mainChartDimensions.value.width + 10, // 增加额外宽度
          mainChartDimensions.value.height
        );
      }

      // 标记渲染完成
      renderingState.completed = true;
      renderingState.isRendering = false;

      // 清除进度更新定时器
      if (loadingState.progressInterval) {
        clearInterval(loadingState.progressInterval);
        loadingState.progressInterval = null;
      }

      // 平滑过渡到100%
      const finalizeProgress = () => {
        const currentProgress = loadingState.progress;
        if (currentProgress < 100) {
          loadingState.progress = Math.min(currentProgress + 1, 100);
          if (loadingState.progress < 100) {
            setTimeout(finalizeProgress, 20);
          }
        }
      };

      finalizeProgress();
    });
  } catch (error) {
    console.error('Error drawing combined chart:', error);
    ElMessage.error(`绘制图表时出错: ${error.message}`);

    // 确保在出错时也标记为完成
    renderingState.completed = true;
    renderingState.isRendering = false;

    // 清除进度更新定时器
    if (loadingState.progressInterval) {
      clearInterval(loadingState.progressInterval);
      loadingState.progressInterval = null;
    }

    // 平滑过渡到100%
    const finalizeProgress = () => {
      const currentProgress = loadingState.progress;
      if (currentProgress < 100) {
        loadingState.progress = Math.min(currentProgress + 1, 100);
        if (loadingState.progress < 100) {
          setTimeout(finalizeProgress, 20);
        }
      }
    };

    finalizeProgress();
  }
};

// 添加确认通道选择的方法
const confirmChannelSelection = () => {
  if (selectedChannelForAnnotation.value) {
    showChannelSelectDialog.value = false;
    const channelName = selectedChannelForAnnotation.value.split('_')[0];
    const shotNumber = selectedChannelForAnnotation.value.split('_')[1];
    ElMessage.success(`已选择通道: ${channelName} | ${shotNumber}`);
  } else {
    ElMessage.warning('请选择一个通道');
  }
};
</script>


<style scoped>
.el-divider--horizontal {
  margin: 0px !important;
  border-top: 3px var(--el-border-color) var(--el-border-style);
}

.chart-container {
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  /* 改为从顶部开始 */
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
  height: 100%;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  overflow: hidden; /* 防止内容溢出 */
}

.chart-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: calc(100% - 40px);
  position: relative;
  overflow: hidden;
  margin-top: 5px;
  /* 减少顶部空白 */
  min-height: 300px; /* 设置最小高度 */
}

#combined-chart {
  width: 100%;
  height: 100%;
  position: relative;
  min-height: 300px; /* 设置最小高度 */
}

.legend-container {
  position: absolute;
  top: 40px;
  right: 40px;
  z-index: 999;
  min-width: 100px;
  max-width: 200px;
}

/* 添加图例样式 */
.legend {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: 6px;
  background-color: rgba(255, 255, 255, 0.95);
  border-radius: 4px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.1);
  max-height: 200px;
  overflow-y: auto;
  transition: box-shadow 0.2s ease;
}

.legend:hover {
  box-shadow: 0 2px 4px rgba(0,0,0,0.15);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  margin: 0;
  padding: 2px 4px;
  border-radius: 2px;
  transition: background-color 0.2s ease;
  cursor: default;
  min-height: 20px;
}

.legend-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.legend-text {
  font-size: 12px;
  font-weight: normal;
  white-space: nowrap;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
}

/* 自定义滚动条样式 */
.legend::-webkit-scrollbar {
  width: 4px;
}

.legend::-webkit-scrollbar-track {
  background: transparent;
}

.legend::-webkit-scrollbar-thumb {
  background-color: rgba(0, 0, 0, 0.15);
  border-radius: 2px;
}

.legend::-webkit-scrollbar-thumb:hover {
  background-color: rgba(0, 0, 0, 0.25);
}

.progress-container {
  z-index: 999;
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  justify-content: center;
  align-items: center;
  background-color: rgba(255, 255, 255, 0.8);
}

.progress-circle-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
}

.progress-info {
  text-align: center;
}

.progress-text {
  font-size: 14px;
  color: #606266;
  margin-bottom: 5px;
}

.progress-percentage {
  font-weight: bold;
  color: #409EFF;
  font-size: 16px;
}

/* 自定义环形进度条样式 */
:deep(.el-progress-circle) {
  width: 120px !important;
  height: 120px !important;
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

.annotation-controls {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 100;
  background-color: rgba(255, 255, 255, 0.8);
  padding: 8px;
  border-radius: 4px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.1);
}

.el-dialog :deep(.el-dialog__body) {
  padding: 20px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
