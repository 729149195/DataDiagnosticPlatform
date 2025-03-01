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
        <div id="overview-chart" class="overview-chart"></div>
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
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useStore } from 'vuex';
import * as Highcharts from 'highcharts';
import debounce from 'lodash/debounce';
import { ElMessage } from 'element-plus';
import { Loading } from '@element-plus/icons-vue';

const store = useStore();
const chartContainer = ref(null);

// 响应式引用
const overviewData = ref([]);
const chartInstance = ref(null);
const updatingBrush = ref(false);
const originalDomains = ref({});
const renderCount = ref(0);
const initialDataLoaded = ref(false);
const isLoading = ref(false);
const retryCount = ref(0);
const extremes = ref(null);

// 追加一个强制渲染标志，用于确保至少绘制一次
const forceRender = ref(false);

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
  if (overviewData.value && overviewData.value.length > 0) {
    // 记住当前的刷选状态
    const currentExtreme = extremes.value;
    
    // 重新渲染图表
    renderChart();
    
    // 如果原来有滑动块选择，重新设置
    if (currentExtreme && chartInstance.value) {
      nextTick(() => {
        try {
          const chart = chartInstance.value;
          if (chart) {
            // 不再设置图表的极值，只更新遮罩区域
            const xAxis = chart.xAxis[0];
            const xMin = originalDomains.value.x[0];
            const xMax = originalDomains.value.x[1];
            
            // 移除并重新添加左侧遮罩
            xAxis.removePlotBand('mask-before');
            xAxis.addPlotBand({
              id: 'mask-before',
              from: xMin,
              to: currentExtreme.min,
              color: 'rgba(64, 158, 255, 0.1)'
            });
            
            // 移除并重新添加右侧遮罩
            xAxis.removePlotBand('mask-after');
            xAxis.addPlotBand({
              id: 'mask-after',
              from: currentExtreme.max,
              to: xMax,
              color: 'rgba(64, 158, 255, 0.1)'
            });
            
            // 刷新图表
            chart.redraw();
            
            // 更新brush值
            updatingBrush.value = true;
            brush_begin.value = currentExtreme.min.toFixed(4);
            brush_end.value = currentExtreme.max.toFixed(4);
            store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
            updatingBrush.value = false;
          }
        } catch (error) {
          console.warn('窗口大小变化时更新遮罩区域出错:', error);
        }
      });
    }
  }
}, 200);

// 组件挂载和卸载
onMounted(() => {
  window.addEventListener('resize', handleResize);
  
  // 添加双击事件监听
  const chartContainer = document.getElementById('overview-chart');
  if (chartContainer) {
    chartContainer.addEventListener('dblclick', handleDblClick);
  }
  
  // 延迟初始化以确保DOM渲染完成
  setTimeout(() => {
    checkDataAndRender();
  }, 500);
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
  
  // 移除双击事件监听
  const chartContainer = document.getElementById('overview-chart');
  if (chartContainer) {
    chartContainer.removeEventListener('dblclick', handleDblClick);
  }
  
  // 销毁图表实例
  if (chartInstance.value) {
    try {
      chartInstance.value.destroy();
    } catch (error) {
      console.warn('销毁图表时出错:', error);
    }
    chartInstance.value = null;
  }
});

// 监听选中通道的变化
watch(selectedChannels, () => {
  forceRender.value = false; // 重置强制渲染标记
  checkDataAndRender();
}, { deep: true });

// 监听通道数据缓存的变化
watch(channelDataCache, () => {
  // 仅在有选中通道且当前无数据时才尝试重新获取
  if (selectedChannels.value.length > 0 && overviewData.value.length === 0) {
    collectData();
  }
}, { deep: true });

// 检查数据是否准备好并渲染
const checkDataAndRender = () => {
  retryCount.value = 0;
  // 直接获取数据，不需要先做检查
  collectData();
};

// 采集数据
const collectData = async (forcedRender = false) => {
  // 检查是否有选中的通道
  if (!selectedChannels.value || selectedChannels.value.length === 0) {
    overviewData.value = [];
    return;
  }
  
  // 保存现有数据
  const existingData = [...overviewData.value];
  
  // 使用直接获取数据的方式，而不是依赖channelDataCache
  isLoading.value = true;
  
  try {
    const dataPromises = selectedChannels.value.map(async (channel) => {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      
      // 避免重复处理已经有数据的通道
      if (existingData.some(d => d.channelName === channelKey) && !forcedRender) {
        return null;
      }
      
      try {
        // 直接使用store action获取数据，不依赖channelDataCache
        const channelData = await store.dispatch('fetchChannelData', { channel });
        
        if (channelData && channelData.X_value && channelData.Y_value &&
            Array.isArray(channelData.X_value) && Array.isArray(channelData.Y_value) &&
            channelData.X_value.length > 0 && channelData.Y_value.length > 0) {
        
          
          // 返回处理后的数据对象
          return {
            channelName: channelKey,
            X_value: [...channelData.X_value],
            Y_value: [...channelData.Y_value],
            color: channel.color || '#7cb5ec'
          };
        } else {
          console.warn(`通道 ${channelKey} 返回的数据无效`);
          return null;
        }
      } catch (error) {
        console.error(`获取通道 ${channelKey} 数据失败:`, error);
        return null;
      }
    });
    
    // 等待所有数据请求完成
    const results = await Promise.all(dataPromises);
    
    // 过滤掉null和undefined结果
    const newChannelsData = results.filter(Boolean);
    
    // 合并现有数据和新数据，避免重复
    if (newChannelsData.length > 0) {
      const merged = [...existingData];
      
      newChannelsData.forEach(newData => {
        // 检查是否已存在
        const existingIndex = merged.findIndex(item => item.channelName === newData.channelName);
        if (existingIndex >= 0) {
          // 更新现有数据
          merged[existingIndex] = newData;
        } else {
          // 添加新数据
          merged.push(newData);
        }
      });
      
      overviewData.value = merged;
    } else if (existingData.length === 0) {
      overviewData.value = [];
    }
    
    // 绘制图表
    if (overviewData.value.length > 0) {
      initialDataLoaded.value = true;
      renderChart();
    } else {
      console.warn('没有收集到任何有效数据');
      clearChart();
    }
  } catch (error) {
    console.error('获取数据过程中发生错误:', error);
  } finally {
    isLoading.value = false;
  }
};

// 清空图表
const clearChart = () => {
  if (chartInstance.value) {
    try {
      chartInstance.value.destroy();
    } catch (error) {
      console.warn('销毁图表时出错:', error);
    }
    chartInstance.value = null;
  }
};

// 渲染图表
const renderChart = () => {
  renderCount.value++;
  
  if (overviewData.value.length === 0) {
    console.warn('无数据可渲染');
    clearChart();
    return;
  }
  
  // 确保容器存在
  if (!chartContainer.value) {
    console.error('图表容器不存在');
    return;
  }
  
  // 清空现有图表
  clearChart();
  
  // 准备数据系列
  const series = [];
  let xMin = Infinity;
  let xMax = -Infinity;
  let yMin = Infinity;
  let yMax = -Infinity;
  
  // 处理每个通道的数据
  overviewData.value.forEach((channel, index) => {
    // 创建数据点
    const data = channel.X_value.map((x, i) => {
      // 更新数据范围
      xMin = Math.min(xMin, x);
      xMax = Math.max(xMax, x);
      yMin = Math.min(yMin, channel.Y_value[i]);
      yMax = Math.max(yMax, channel.Y_value[i]);
      
      return [x, channel.Y_value[i]];
    });
    
    // 添加系列
    series.push({
      name: channel.channelName,
      data: data,
      color: channel.color,
      lineWidth: 1.5,
      marker: {
        enabled: false
      }
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
  
  // 创建遮罩填充颜色
  const maskFill = 'rgba(64, 158, 255, 0.1)';
  
  // 创建Highcharts图表
  chartInstance.value = Highcharts.chart('overview-chart', {
    chart: {
      height: 80,
      marginLeft: 20,
      marginRight: 20,
      marginTop: 10,
      marginBottom: 20,
      animation: false,
      reflow: false,
      borderWidth: 0,
      backgroundColor: null,
      zooming: {
        type: 'x'
      },
      events: {
        selection: function(event) {
          if (event.xAxis) {
            const min = event.xAxis[0].min;
            const max = event.xAxis[0].max;
            
            // 更新刷选值
            updatingBrush.value = true;
            brush_begin.value = min.toFixed(4);
            brush_end.value = max.toFixed(4);
            
            // 更新store
            store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
            
            // 更新所有通道的domain
            selectedChannels.value.forEach(channel => {
              const channelName = `${channel.channel_name}_${channel.shot_number}`;
              store.dispatch('updateDomains', {
                channelName,
                xDomain: [min, max],
                yDomain: domains.value.y[channelName]
              });
            });
            
            try {
              // 更新遮罩区域
              const xAxis = this.xAxis[0];
              
              // 移除并重新添加左侧遮罩
              xAxis.removePlotBand('mask-before');
              xAxis.addPlotBand({
                id: 'mask-before',
                from: xMin,
                to: min,
                color: maskFill
              });
              
              // 移除并重新添加右侧遮罩
              xAxis.removePlotBand('mask-after');
              xAxis.addPlotBand({
                id: 'mask-after',
                from: max,
                to: xMax,
                color: maskFill
              });
            } catch (error) {
              console.warn('更新遮罩区域时出错:', error);
            }
            
            updatingBrush.value = false;
            extremes.value = { min, max };
            
            // 保持选区
            return false;
          }
        },
        // 添加双击事件处理
        dblclick: function() {
          try {
            // 获取原始数据范围
            const xMin = originalDomains.value.x[0];
            const xMax = originalDomains.value.x[1];
            
            // 更新刷选值为原始范围
            updatingBrush.value = true;
            brush_begin.value = xMin.toFixed(4);
            brush_end.value = xMax.toFixed(4);
            
            // 更新store
            store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
            
            // 更新所有通道的domain
            selectedChannels.value.forEach(channel => {
              const channelName = `${channel.channel_name}_${channel.shot_number}`;
              store.dispatch('updateDomains', {
                channelName,
                xDomain: [xMin, xMax],
                yDomain: domains.value.y[channelName]
              });
            });
            
            // 更新遮罩区域
            const xAxis = this.xAxis[0];
            
            // 重置遮罩区域
            xAxis.removePlotBand('mask-before');
            xAxis.addPlotBand({
              id: 'mask-before',
              from: xMin,
              to: xMin,
              color: maskFill
            });
            
            xAxis.removePlotBand('mask-after');
            xAxis.addPlotBand({
              id: 'mask-after',
              from: xMax,
              to: xMax,
              color: maskFill
            });
            
            // 更新极值
            extremes.value = { min: xMin, max: xMax };
            updatingBrush.value = false;
            
            // 刷新图表
            this.redraw();
          } catch (error) {
            console.warn('双击重置时出错:', error);
          }
        }
      }
    },
    title: {
      text: null
    },
    accessibility: {
      enabled: false
    },
    xAxis: {
      min: xMin,
      max: xMax,
      gridLineWidth: 0.5,
      gridLineColor: '#e0e0e0',
      lineColor: '#999',
      tickColor: '#999',
      labels: {
        align: 'center',
        y: 15,
        style: {
          fontSize: '10px',
          fontWeight: 'bold'
        }
      },
      tickLength: 3,
      tickPosition: 'inside',
      plotBands: [{
        id: 'mask-before',
        from: xMin,
        to: xMin,
        color: maskFill
      }, {
        id: 'mask-after',
        from: xMax,
        to: xMax,
        color: maskFill
      }],
      events: {
        afterSetExtremes: function(e) {
          if (updatingBrush.value) return; // 避免循环调用
          
          updatingBrush.value = true;
          const min = e.min;
          const max = e.max;
          
          // 更新输入框
          brush_begin.value = min.toFixed(4);
          brush_end.value = max.toFixed(4);
          
          // 更新store
          store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
          
          // 更新所有通道的domain
          selectedChannels.value.forEach(channel => {
            const channelName = `${channel.channel_name}_${channel.shot_number}`;
            store.dispatch('updateDomains', {
              channelName,
              xDomain: [min, max],
              yDomain: domains.value.y[channelName]
            });
          });
          
          try {
            // 更新遮罩区域
            const xAxis = chartInstance.value.xAxis[0];
            
            // 移除并重新添加左侧遮罩
            xAxis.removePlotBand('mask-before');
            xAxis.addPlotBand({
              id: 'mask-before',
              from: xMin,
              to: min,
              color: maskFill
            });
            
            // 移除并重新添加右侧遮罩
            xAxis.removePlotBand('mask-after');
            xAxis.addPlotBand({
              id: 'mask-after',
              from: max,
              to: xMax,
              color: maskFill
            });
          } catch (error) {
            console.warn('更新遮罩区域时出错:', error);
          }
          
          // 更新极值
          extremes.value = { min, max };
          updatingBrush.value = false;
        }
      }
    },
    yAxis: {
      min: yMin,
      max: yMax,
      gridLineWidth: 0,
      labels: {
        enabled: false
      },
      title: {
        text: null
      },
      showFirstLabel: false
    },
    legend: {
      enabled: false
    },
    tooltip: {
      enabled: false
    },
    credits: {
      enabled: false
    },
    plotOptions: {
      series: {
        fillColor: 'transparent', // 移除底部填充
        lineWidth: 1,
        marker: {
          enabled: false
        },
        shadow: false,
        states: {
          hover: {
            lineWidth: 1
          }
        },
        enableMouseTracking: false,
        animation: false
      }
    },
    series: series.map(s => ({
      ...s,
      type: 'line' // 使用线图而不是区域图
    })),
    exporting: {
      enabled: false
    }
  });
  
  // 更新brush值到store
  updatingBrush.value = true;
  brush_begin.value = initialBrushBegin.toFixed(4);
  brush_end.value = initialBrushEnd.toFixed(4);
  store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
  updatingBrush.value = false;
  
  // 保存初始极值
  extremes.value = { min: initialBrushBegin, max: initialBrushEnd };
  
  // 设置初始遮罩
  if (chartInstance.value) {
    nextTick(() => {
      try {
        // 初始时确保选中区域为整个数据范围，但不缩放图表
        const xAxis = chartInstance.value.xAxis[0];
        
        // 设置遮罩区域
        xAxis.removePlotBand('mask-before');
        xAxis.addPlotBand({
          id: 'mask-before',
          from: xMin,
          to: initialBrushBegin,
          color: maskFill
        });
        
        xAxis.removePlotBand('mask-after');
        xAxis.addPlotBand({
          id: 'mask-after',
          from: initialBrushEnd,
          to: xMax,
          color: maskFill
        });
        
        // 刷新图表
        chartInstance.value.redraw();
      } catch (error) {
        console.warn('设置初始遮罩时出错:', error);
      }
    });
  }
};

// 处理输入框
const handleInputBlur = (type) => {
  if (updatingBrush.value) return;
  if (!chartInstance.value) return;

  const chart = chartInstance.value;
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

  try {
    // 更新遮罩区域，但不缩放图表
    const xAxis = chart.xAxis[0];
    const xMin = originalDomain[0];
    const xMax = originalDomain[1];
    
    // 移除并重新添加左侧遮罩
    xAxis.removePlotBand('mask-before');
    xAxis.addPlotBand({
      id: 'mask-before',
      from: xMin,
      to: start,
      color: 'rgba(64, 158, 255, 0.1)'
    });
    
    // 移除并重新添加右侧遮罩
    xAxis.removePlotBand('mask-after');
    xAxis.addPlotBand({
      id: 'mask-after',
      from: end,
      to: xMax,
      color: 'rgba(64, 158, 255, 0.1)'
    });
    
    // 更新极值
    extremes.value = { min: start, max: end };
    
    // 更新所有通道的domain
    updatingBrush.value = true;
    selectedChannels.value.forEach(channel => {
      const channelName = `${channel.channel_name}_${channel.shot_number}`;
      store.dispatch('updateDomains', {
        channelName,
        xDomain: [start, end],
        yDomain: domains.value.y[channelName]
      });
    });
    updatingBrush.value = false;
  } catch (error) {
    console.warn('更新遮罩区域时出错:', error);
  }
};

// 处理双击事件
const handleDblClick = () => {
  if (!chartInstance.value) return;
  
  try {
    // 获取原始数据范围
    const xMin = originalDomains.value.x[0];
    const xMax = originalDomains.value.x[1];
    
    // 更新刷选值为原始范围
    updatingBrush.value = true;
    brush_begin.value = xMin.toFixed(4);
    brush_end.value = xMax.toFixed(4);
    
    // 更新store
    store.commit('updatebrush', { begin: brush_begin.value, end: brush_end.value });
    
    // 更新所有通道的domain
    selectedChannels.value.forEach(channel => {
      const channelName = `${channel.channel_name}_${channel.shot_number}`;
      store.dispatch('updateDomains', {
        channelName,
        xDomain: [xMin, xMax],
        yDomain: domains.value.y[channelName]
      });
    });
    
    // 更新遮罩区域
    const xAxis = chartInstance.value.xAxis[0];
    
    // 重置遮罩区域
    xAxis.removePlotBand('mask-before');
    xAxis.addPlotBand({
      id: 'mask-before',
      from: xMin,
      to: xMin,
      color: 'rgba(64, 158, 255, 0.1)'
    });
    
    xAxis.removePlotBand('mask-after');
    xAxis.addPlotBand({
      id: 'mask-after',
      from: xMax,
      to: xMax,
      color: 'rgba(64, 158, 255, 0.1)'
    });
    
    // 更新极值
    extremes.value = { min: xMin, max: xMax };
    updatingBrush.value = false;
    
    // 刷新图表
    chartInstance.value.redraw();
  } catch (error) {
    console.warn('双击重置时出错:', error);
  }
};
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