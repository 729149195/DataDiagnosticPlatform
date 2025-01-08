<template>
    <div class="result-chart-container">
      <div class="chart-wrapper">
        <svg id="chart" ref="resultSvgRef"></svg>
      </div>
    </div>
</template>

<script setup>
import * as d3 from "d3";
import { useStore } from 'vuex';
import { computed, ref, watch } from "vue";

// 获取 Vuex 状态
const store = useStore();
const scaleCache = {};
const curChannel = ref({});
const curChannelKey = ref('');
const ErrorLineXScopes = computed(() => store.state.ErrorLineXScopes);
const CalculateResult = computed(() => store.state.CalculateResult);
const channelDataCache = computed(() => store.state.channelDataCache);
const resultSvgRef = ref(null);
const resultData = ref(null);
defineExpose({
    resultSvgRef: resultSvgRef,
    resultData: resultData
})

const fetchChannelData = async (channel) => {
    try {
        // 构建 channelKey
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        const channelData = channelDataCache.value[channelKey];

        if (channelData) {
            // 绘制图表
            drawChart(
                channelData.X_value,
                channelData.Y_value,
                channel,
                channelKey
            );
        } else {
            console.error('Channel data not found in cache:', channelKey);
        }
    } catch (error) {
        console.error('Error fetching channel data:', error);
    }
};

const drawChart = (xValues, yValues, channel=-1, channelKey=-1) => {
    // 获取父容器的宽度
    const container = d3.select('.result-chart-container');
    const containerWidth = container.node().getBoundingClientRect().width;

    const svg = container.select('#chart');
    const margin = { top: 50, right: 30, bottom: 30, left: 65 };

    // 使用容器的宽度来计算图表的宽度
    const width = containerWidth - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom; // 固定高度可以根据需要调整

    svg.selectAll('*').remove(); // 清空之前的绘图

    // 设置 viewBox 使得图表响应式
    svg
        .attr(
            'viewBox',
            `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`
        )
        // .attr('preserveAspectRatio', 'xMidYMid meet')
        .attr('width', '100%'); // 确保宽度自适应父容器

    const xScale = d3
        .scaleLinear()
        .domain(d3.extent(xValues))
        .range([0, width]);

    const yExtent = d3.extent(yValues);
    const yRangePadding = (yExtent[1] - yExtent[0]) * 0.1;
    const yMin = yExtent[0] - yRangePadding;
    const yMax = yExtent[1] + yRangePadding;

    const yScale = d3
        .scaleLinear()
        .domain([yMin, yMax])
        .range([height, 0]);

    // 使用 channelKey 作为缓存键
    if(channelKey !== -1) {
        scaleCache[channelKey] = [xScale, yScale];
    }

    const line = d3
        .line()
        .x((d, i) => xScale(xValues[i]))
        .y((d, i) => yScale(yValues[i]));

    // 定义图表主体（使用 clip-path 仅限制曲线）
    const g = svg
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    
    let axisG = g.append('g').attr('class', 'axisG');
    let gridG = g.append('g').attr('class', 'gridG');
    let contentG = g.append('g').attr('class', 'contentG');

    // 添加 X 轴
    axisG.append('g')
        .attr('class', 'x-axis')
        .attr('transform', `translate(0,${height})`)
        .call(d3.axisBottom(xScale));

    // 添加 Y 轴
    axisG.append('g').attr('class', 'y-axis').call(d3.axisLeft(yScale));

    // 添加 Y 轴网格线（横向网格线）
    gridG.append('g')
        .attr('class', 'grid')
        .call(
            d3
                .axisLeft(yScale)
                .tickSize(-width)
                .tickFormat('')
        )
        .selectAll('line')
        .style('stroke', '#ccc')
        .style('stroke-dasharray', '3,3'); // 横向虚线

    // 添加 X 轴网格线（纵向网格线）
    gridG.append('g')
        .attr('class', 'grid')
        .attr('transform', `translate(0,${height})`) // 放置在 X 轴的位置
        .call(
            d3
                .axisBottom(xScale)
                .tickSize(-height) // 网格线的长度，即延伸到图表高度
                .tickFormat('')
        ) // 不显示 X 轴的刻度标签
        .selectAll('line')
        .style('stroke', '#ccc')
        .style('stroke-dasharray', '3,3'); // 纵向虚线

    // 添加图例
    const legend = svg
        .append('g')
        .attr('class', 'legend')
        .attr('transform', `translate(${margin.left},${margin.top - 30})`);

    // 添加图例项
    let index = 0;
    const legendItem = legend
        .append('g')
        .attr('transform', `translate(${index * 150},0)`);

    legendItem
        .append('rect')
        .attr('x', 0)
        .attr('y', -10)
        .attr('width', 20)
        .attr('height', 10)
        .attr('fill', channel.color || 'steelblue');

    legendItem
        .append('text')
        .attr('x', 25)
        .attr('y', 0)
        .attr('text-anchor', 'start')
        .style('font-size', '14px')
        .text(channel.channel_name || '');
    
    // const { xUnit, yUnit } = dataCache[channelKey];
    //
    // svg
    //     .append('text')
    //     .attr('x', width / 2 + margin.left) // 放在X轴末端
    //     .attr('y', height + margin.top + 30) // 距离X轴一些距离
    //     .attr('text-anchor', 'end')
    //     .attr('fill', '#000')
    //     .text(xUnit); // 使用xUnit作为横轴的单位图例
    //
    // // 添加Y轴图例 (yUnit) - 居中对齐
    // svg
    //     .append('text')
    //     .attr('transform', `translate(${margin.left - 50}, ${margin.top + height / 2}) rotate(-90)`)
    //     .attr('text-anchor', 'middle')
    //     .attr('alignment-baseline', 'middle') // 确保文本垂直居中
    //     .attr('fill', '#000')
    //     .text(yUnit); // 使用通用的Y轴单位

    // 绘制曲线
    contentG
        .append('path')
        .datum(yValues)
        .attr('fill', 'none')
        .attr('stroke', channel.color || 'steelblue')
        .attr('stroke-width', 1.5)
        .attr('d', line);
};

const scope2Index = (scope, X) => {
    let [l, r] = scope;
    let left_find = false;
    let right_find = false;
    let li = 0;
    let ri = X.length - 1;
    for (let i in X) {
        i = parseInt(i);
        let v = X[i];
        if (v >= l && !left_find) {
            left_find = true;
            li = i;
        }
        if (r <= v && !right_find) {
            right_find = true;
            ri = i - 1;
        }
    }
    return [li, ri];
};

const drawResult = async (CalculateResult) => {
    // 绘制新通道数据
    if('X_value' in CalculateResult) {
        drawChart(CalculateResult['X_value'], CalculateResult['Y_value'])
    }
    // 绘制异常数据
    if('X_range' in CalculateResult) {
        await fetchChannelData(curChannel.value)
        const ErrorLineXScopes = CalculateResult['X_range']
        const channelKey = curChannelKey.value;
        const container = d3.select('.result-chart-container');
        const contentG = container.select('#chart .contentG');

        let channel = curChannel.value;
        const channelData = channelDataCache.value[channelKey];
        if (!channelData) {
            console.error('Channel data not found in cache:', channelKey);
            return;
        }

        let xValues = channelData.X_value;
        let yValues = channelData.Y_value;

        ErrorLineXScopes.forEach((ErrorLineXScope, errorIndex) => {
            let ErrorLineXIndex = scope2Index(ErrorLineXScope, xValues);
            let X_value_error = xValues.slice(ErrorLineXIndex[0], ErrorLineXIndex[1] + 1);
            let Y_value_error = yValues.slice(ErrorLineXIndex[0], ErrorLineXIndex[1] + 1);

            let [x, y] = scaleCache[channelKey];
            const errorLine = d3
                .line()
                .x((d, i) => x(X_value_error[i]))
                .y((d, i) => y(Y_value_error[i]))
                .curve(d3.curveMonotoneX);

            contentG
                .append('path')
                .datum(Y_value_error)
                .attr('class', `error-line-${channel.channel_name}-${errorIndex}`)
                .attr('fill', 'none')
                .attr('stroke', "#ff6767")
                .attr('stroke-width', 2)
                .attr('opacity', 0.8)
                .attr('d', errorLine);
        });
    }
};

const clickedShownChannelList = computed(() => store.state.clickedShownChannelList);

watch(clickedShownChannelList, async (newClickedShownChannelList, oldV) => {
    // 暂时只考虑一个图计算的情况
    const channel = newClickedShownChannelList[0];
    await fetchChannelData(channel);
    curChannel.value = channel;
    // 构建 channelKey
    curChannelKey.value = `${channel.channel_name}_${channel.shot_number}`;
}, { deep: true });

watch(CalculateResult, async (newCalculateResult, oldV) => {
    resultData.value = newCalculateResult;
    await drawResult(newCalculateResult);
}, { deep: true });

</script>

<style scoped>
  .result-chart-container {
      display: flex;
      flex-direction: column;
      padding-bottom: 10vh;
  }

  .chart-wrapper {
      flex: 1;
      display: flex;
      flex-direction: column;
      width: 100%;
      margin-bottom: -10px;
  }
</style>
