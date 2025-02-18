<template>
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
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue';
import { useStore } from 'vuex';
import * as d3 from 'd3';
import debounce from 'lodash/debounce';
import { ElMessage } from 'element-plus';

const store = useStore();

// 响应式引用
const overviewData = ref([]);
const overviewBrushInstance = ref(null);
const overviewXScale = ref(null);
const updatingBrush = ref(false);
const brushSelections = ref({ overview: null });
const originalDomains = ref({});

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
    drawOverviewChart();
  }
}, 200);

// 组件挂载和卸载
onMounted(() => {
  window.addEventListener('resize', handleResize);
  updateOverviewData();
});

onUnmounted(() => {
  window.removeEventListener('resize', handleResize);
});

// 监听选中通道的变化
watch(selectedChannels, () => {
  updateOverviewData();
}, { deep: true });

// 监听 brush 范围变化
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
  });
}, { immediate: true });

// 更新总览数据
const updateOverviewData = () => {
  overviewData.value = [];
  
  selectedChannels.value.forEach(channel => {
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;
    const data = channelDataCache.value[channelKey];
    
    if (data) {
      overviewData.value.push({
        channelName: channelKey,
        X_value: data.X_value,
        Y_value: data.Y_value,
        color: channel.color
      });
    }
  });

  if (overviewData.value.length > 0) {
    nextTick(() => {
      drawOverviewChart();
    });
  }
};

// 绘制总览图表
const drawOverviewChart = () => {
  if (overviewData.value.length === 0) return;

  const svg = d3.select('#overview-chart');
  svg.selectAll('*').remove();

  const svgNode = svg.node();
  const svgWidth = svgNode.getBoundingClientRect().width;

  const margin = { top: 10, right: 45, bottom: 35, left: 45 };
  const width = svgWidth - margin.left - margin.right;
  const height = 80 - margin.top - margin.bottom;

  svg
    .attr('viewBox', `0 0 ${svgWidth} ${height + margin.top + margin.bottom}`)
    .attr('preserveAspectRatio', 'xMidYMid meet');

  const g = svg.append('g')
    .attr('transform', `translate(${margin.left},${margin.top})`);

  // 计算所有数据的范围
  const allX = overviewData.value.flatMap(d => d.X_value);
  const allY = overviewData.value.flatMap(d => d.Y_value);
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
    .data(overviewData.value, d => d.channelName);

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
    .extent([[0, 0], [width, height]])
    .on('brush end', brushed);

  overviewBrushInstance.value = brush;

  const brushG = g.append('g')
    .attr('class', 'brush')
    .call(brush);

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
  }
};

// 处理输入框
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
  const allX = overviewData.value.flatMap(d => d.X_value);
  const dataExtent = d3.extent(allX);
  const epsilon = 0.0001; // 添加容差值

  // 确保在有效范围内
  if (start < dataExtent[0] - epsilon || end > dataExtent[1] + epsilon) {
    ElMessage.warning(`输入值必须在 ${dataExtent[0].toFixed(4)} 到 ${dataExtent[1].toFixed(4)} 之间`);
    brush_begin.value = currentExtent[0].toFixed(4);
    brush_end.value = currentExtent[1].toFixed(4);
    return;
  }

  // 更新 store 中的值
  store.commit("updatebrush", { begin: brush_begin.value, end: brush_end.value });

  // 更新刷选区域
  const selection = [x(start), x(end)];
  updatingBrush.value = true;
  d3.select('#overview-chart').select('.brush').call(brush.move, selection);
  updatingBrush.value = false;

  // 更新所有通道的 domain
  selectedChannels.value.forEach((channel) => {
    const channelName = `${channel.channel_name}_${channel.shot_number}`;
    store.dispatch('updateDomains', {
      channelName,
      xDomain: [start, end],
      yDomain: domains.value.y[channelName]
    });
  });
};
</script>

<style scoped>
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

.el-divider--horizontal {
  margin: 0px !important;
  border-top: 3px var(--el-border-color) var(--el-border-style);
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