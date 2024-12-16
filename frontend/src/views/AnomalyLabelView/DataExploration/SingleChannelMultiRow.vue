<template>
    <div class="chart-container">
        <div v-if="selectedChannels.length === 0">
            <el-empty description="请选择通道" style="margin-top: 15vh;" />
        </div>
        <div v-else>
            <div class="chart-wrapper" v-for="(channel, index) in selectedChannels"
                :key="channel.channel_name + '_' + channel.shot_number">
                <div v-if="loadingStates[channel.channel_name + '_' + channel.shot_number] !== 100 || 
                    renderingStates[channel.channel_name + '_' + channel.shot_number] !== 100"
                    class="progress-wrapper">
                    <div class="progress-title">
                        <span>{{ 
                            `${channel.channel_name}#${channel.shot_number}`
                        }} - {{ 
                            loadingStates[channel.channel_name + '_' + channel.shot_number] === 100 
                            ? '图表渲染中' : '数据加载中' 
                        }}</span>
                        <span class="progress-percentage">{{ 
                            getProgressPercentage(channel.channel_name + '_' + channel.shot_number)
                        }}%</span>
                    </div>
                    <el-progress 
                        :percentage="getProgressPercentage(channel.channel_name + '_' + channel.shot_number)"
                        :stroke-width="10"
                        :status="loadingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? '' : 'warning'"
                        :color="loadingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? '#409EFF' : ''"
                    />
                </div>
                <svg :id="'chart-' + channel.channel_name + '_' + channel.shot_number"
                    :ref="el => channelSvgElementsRefs[index] = el"
                    :style="{ 
                        opacity: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 1 : 0,
                        transition: 'opacity 0.5s ease'
                    }"></svg>
                <!-- Position the color picker near the chart -->
                <div class="color-picker-container"
                    :style="{ 
                        opacity: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 1 : 0,
                        visibility: renderingStates[channel.channel_name + '_' + channel.shot_number] === 100 ? 'visible' : 'hidden',
                        transition: 'opacity 0.5s ease'
                    }"
                    v-show="renderingStates[channel.channel_name + '_' + channel.shot_number] === 100"
                >
                    <ChannelColorPicker :color="channel.color" :predefineColors="predefineColors"
                        @change="updateChannelColor(channel)" @update:color="channel.color = $event" :channelName="channel.channel_name" :shotNumber="channel.shot_number" />
                </div>
            </div>
            <div class="overview-container">
                <el-divider />
                <span style="position: absolute; top: 15px; left:0px; z-index: 999;">
                    <el-tag type="info">总览条</el-tag><br />
                    <el-input size="small" style="width: 55px;" v-model="brush_begin"></el-input><br />
                    <el-input size="small" style="width: 55px" v-model="brush_end"></el-input>
                </span>
                <svg id="overview-chart" class="overview-svg"></svg>
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
import pLimit from 'p-limit';

import {
    ref,
    reactive,
    watch,
    computed,
    onMounted,
    nextTick,
} from 'vue';

import {
    ElDialog,
    ElForm,
    ElFormItem,
    ElInput,
    ElButton,
    ElMessage,
} from 'element-plus';
import { useStore } from 'vuex';
import axios from 'axios';

import { sampleData, sampleErrorSegment } from '@/utils/dataProcessing';

const currentAnomaly = reactive({});
const showAnomalyForm = ref(false);
const overviewData = ref([]);

const xDomains = ref({});
const anomalies = ref([]);

const brush_begin = ref(0);
const brush_end = ref(0);

const timeAxisRange = computed(() => {
    if (
        currentAnomaly &&
        currentAnomaly.startX !== undefined &&
        currentAnomaly.endX !== undefined
    ) {
        return `${currentAnomaly.startX.toFixed(3)} - ${currentAnomaly.endX.toFixed(
            2
        )}`;
    }
    return '';
});

const store = useStore();
const selectedChannels = computed(() => store.state.selectedChannels);
const sampling = computed(() => store.state.sampling);
const smoothnessValue = computed(() => store.state.smoothness);
const sampleRate = ref(store.state.sampling);
const channelSvgElementsRefs = computed(() => store.state.channelSvgElementsRefs);

const chartContainerWidth = ref(0);
const brushSelections = ref({ overview: null });

const matchedResults = computed(() => store.state.matchedResults);

const overviewBrushInstance = ref(null);
const overviewXScale = ref(null);
const updatingBrush = ref(false);

// 🚀 **新增部分：定义缓存对象**
const channelDataCache = computed(() => store.state.channelDataCache);

// 在 script setup 部分添加新的应式变量
const loadingStates = reactive({});  // 用于存储每个通道的加载状态
const renderingStates = reactive({}); // 用于存储每个通道的渲染状态

const limit = pLimit(50); // 限制最大并发请求数为5

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

// 监视匹配结果，绘制高亮矩形
watch(matchedResults, (newResults) => {
    // 清除所有通道的高亮
    selectedChannels.value.forEach(channel => {
        const channelName = `${channel.channel_name}_${channel.shot_number}`;
        const svg = d3.select(`#chart-${channelName}`);
        if (svg.node()) {
            svg.select(`.highlight-group-${channelName}`).remove();
        }
    });

    // 只有在有新结果时才绘制高亮
    if (newResults && newResults.length > 0) {
        // 按通道分组结果
        const resultsByChannel = newResults.reduce((acc, result) => {
            const channelKey = `${result.channelName}_${result.shotNumber}`;
            if (!acc[channelKey]) {
                acc[channelKey] = [];
            }
            acc[channelKey].push(result);
            return acc;
        }, {});

        // 为每个通道绘制高亮区域
        Object.entries(resultsByChannel).forEach(([channelKey, results]) => {
            drawHighlightRects(channelKey, results);
        });
    }
}, { deep: true });

// **New: Define predefined colors**
const predefineColors = ref([
    '#000000', // Black
    '#4169E1', // Royal Blue
    '#DC143C', // Crimson
    '#228B22', // Forest Green
    '#FF8C00', // Dark Orange
    '#800080', // Purple
    '#FF1493', // Deep Pink
    '#40E0D0', // Turquoise
    '#FFD700', // Gold
    '#8B4513', // Saddle Brown
    '#2F4F4F', // Dark Slate Gray
    '#1E90FF', // Dodger Blue
    '#32CD32', // Lime Green
    '#FF6347', // Tomato
    '#DA70D6', // Orchid
    '#191970', // Midnight Blue
    '#FA8072', // Salmon
    '#6B8E23', // Olive Drab
    '#6A5ACD', // Slate Blue
    '#FF7F50', // Coral
    '#4682B4'  // Steel Blue
]);

const updateChannelColor = (channel) => {
    store.commit('updateChannelColor', { channel_key: channel.channel_key, color: channel.color });
    renderCharts();
};


// 处理通道数据并绘制图表
const processChannelData = async (data, channel) => {
    try {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        const channelName = channelKey;

        const sampledData = sampleData(data, sampleRate.value);
        
        // 确保采样数据有效
        if (!sampledData || !sampledData.X_value || !sampledData.Y_value) {
            console.warn(`Invalid sampled data for channel ${channelName}`);
            return;
        }

        let errorsData = [];
        for (const [errorIndex, error] of channel.errors.entries()) {
            const error_name = error.error_name;
            const error_color = error.color;

            // 构建用于缓存的 errorKey
            const errorKey = `${channelKey}-${error_name}-${errorIndex}`;
            let errorData;

            // 检查缓存中是否已有异常数据
            if (channelDataCache.value[errorKey]) {
                errorData = channelDataCache.value[errorKey];
            } else {
                const params = {
                    channel_key: channelKey,
                    channel_type: channel.channel_type,
                    error_name: error_name,
                    error_index: errorIndex
                };

                try {
                    // 使用重试机制和并发限制获取错误数据
                    const errorResponse = await limit(() => retryRequest(async () => {
                        return await axios.get(`http://localhost:5000/api/error-data/`, { params });
                    }));
                    errorData = errorResponse.data;
                    channelDataCache.value[errorKey] = errorData;
                } catch (err) {
                    console.warn(`Failed to fetch error data for ${errorKey}:`, err);
                    continue; // 跳过这个错误数据，继续处理其他
                }
            }

            // 处理异常数据
            const processedErrorSegments = errorData.X_value_error.map(
                (errorSegment, idx) => {
                    return sampleErrorSegment(errorSegment, sampledData, findStartIndex, findEndIndex);
                }
            );

            const sampledErrorData = {
                X_value_error: processedErrorSegments.map((seg) => seg.X),
                Y_value_error: processedErrorSegments.map((seg) => seg.Y),
                color: error_color,
                person: error.person,
            };

            errorsData.push(sampledErrorData);
        }

        // 添加数据到 overviewData 前进行验证
        if (sampledData.X_value.length > 0 && sampledData.Y_value.length > 0) {
            overviewData.value.push({
                channelName: channelName,
                X_value: sampledData.X_value,
                Y_value: sampledData.Y_value,
                color: channel.color,
            });
        } else {
            console.warn(`Empty data for channel ${channelName}`);
        }

        await nextTick();
        drawChart(
            sampledData,
            errorsData,
            channelName,
            channel.color,
            data.X_unit,
            data.Y_unit,
            data.channel_type,
            data.channel_number,
            channel.shot_number
        );

        const channelMatchedResults = matchedResults.value.filter(
            (r) => r.channel_name === channelName
        );
        channelMatchedResults.forEach((result) => {
            drawHighlightRects(channelName, [result]);
        });
    } catch (error) {
        console.error(`Error processing channel data for ${channel.channel_name}:`, error);
    }
};


// 🚀 **使用缓存**
const fetchDataAndDrawChart = async (channel) => {
    try {
        if (!channel || !channel.channel_name || !channel.shot_number) {
            console.warn('Invalid channel data:', channel);
            return;
        }

        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        
        loadingStates[channelKey] = Number(0);
        renderingStates[channelKey] = Number(0);

        let data;
        if (channelDataCache.value[channelKey]) {
            loadingStates[channelKey] = Number(100);
            renderingStates[channelKey] = Number(100);
            data = channelDataCache.value[channelKey];
        } else {
            const params = {
                channel_key: channelKey,
                channel_type: channel.channel_type
            };
            
            const progressInterval = setInterval(() => {
                if (loadingStates[channelKey] < 90) {
                    loadingStates[channelKey] = Math.min(Number(loadingStates[channelKey]) + 10, 90);
                }
            }, 100);

            // 使用重试机制包装请求
            const response = await limit(() => retryRequest(async () => {
                return await axios.get(`http://localhost:5000/api/channel-data/`, { params });
            }));
            
            data = response.data;
            channelDataCache.value[channelKey] = data;
            
            clearInterval(progressInterval);
            loadingStates[channelKey] = Number(100);
        }

        if (!data || !data.X_value) {
            throw new Error('Invalid data format: missing X_value');
        }

        renderingStates[channelKey] = Number(0);
        const renderInterval = setInterval(() => {
            if (renderingStates[channelKey] < 90) {
                renderingStates[channelKey] = Math.min(Number(renderingStates[channelKey]) + 10, 90);
            }
        }, 50);

        await processChannelData(data, channel);
        
        clearInterval(renderInterval);
        renderingStates[channelKey] = Number(100);

    } catch (error) {
        console.error('Error fetching channel data:', error);
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        loadingStates[channelKey] = Number(100);
        renderingStates[channelKey] = Number(100);
        ElMessage.error(`加载通道 ${channelKey} 数据失败: ${error.message}`);
    }
};



const renderCharts = debounce(async () => {
    try {
        performance.mark('Total Render Time-start');
        
        // 重置概览数据
        overviewData.value = [];

        // 确保有选中的通道
        if (!selectedChannels.value || selectedChannels.value.length === 0) {
            console.warn('No channels selected');
            return;
        }

        // 使用 Promise.all 并行处理所有通道
        await Promise.all(selectedChannels.value.map(async (channel) => {
            try {
                await fetchDataAndDrawChart(channel);
            } catch (error) {
                console.error(`Error processing channel ${channel.channel_name}:`, error);
            }
        }));

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
    }
}, 200);

onMounted(async () => {
    try {
        const container = document.querySelector('.chart-container');
        if (container) {
            chartContainerWidth.value = container.offsetWidth;
        }

        // 确保 selectedChannels 有值且 overviewData 已初始化后再绘制
        if (selectedChannels.value && selectedChannels.value.length > 0) {
            await renderCharts();
            // 只有在有数据时才绘制概览图
            if (overviewData.value && overviewData.value.length > 0) {
                drawOverviewChart();
            }
        }
    } catch (error) {
        console.error('Error in mounted hook:', error);
    }
});

watch(selectedChannels, async (newChannels, oldChannels) => {
    if (JSON.stringify(newChannels) !== JSON.stringify(oldChannels)) {
        try {
            // 重置概览数据
            overviewData.value = [];
            await nextTick();
            
            // 只有在有选中通道时才进行渲染
            if (newChannels && newChannels.length > 0) {
                await renderCharts();
                // 确保有数据后再绘制���览图
                if (overviewData.value && overviewData.value.length > 0) {
                    drawOverviewChart();
                }
            }
        } catch (error) {
            console.error('Error in selectedChannels watch:', error);
        }
    }
}, { deep: true });

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

    const margin = { top: 20, right: 30, bottom: 30, left: 65 };
    const width = svg.node().getBoundingClientRect().width - margin.left - margin.right;
    const height = 200 - margin.top - margin.bottom;

    // 获取当前图表的x比例尺
    const x = d3.scaleLinear()
        .domain(xDomains.value[channelName] || [-2, 6])
        .range([0, width]);

    // 获取当前通道的数据并进行采样和平滑处理
    const channelData = channelDataCache.value[channelName];
    if (!channelData) return;

    // 进行采样
    const samplingInterval = Math.floor(1 / sampling.value);
    const sampledData = {
        X_value: channelData.X_value.filter((_, i) => i % samplingInterval === 0),
        Y_value: channelData.Y_value.filter((_, i) => i % samplingInterval === 0)
    };

    // 应用平滑处理
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

    // 获取时间和边界值约束
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
                .on('mouseover', function(event) {
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

                    // 设置提示框位置
                    const tooltipWidth = tooltip.node().getBoundingClientRect().width;
                    const tooltipHeight = tooltip.node().getBoundingClientRect().height;
                    const mouseX = event.pageX;
                    const mouseY = event.pageY;
                    
                    tooltip
                        .style('left', `${mouseX - tooltipWidth/2}px`)
                        .style('top', `${mouseY - tooltipHeight - 10}px`);
                })
                .on('mouseout', function() {
                    d3.selectAll('.custom-tooltip').remove();
                });
        }
    });
};

const findStartIndex = (array, startX) => {
    let low = 0;
    let high = array.length - 1;
    let result = -1;
    while (low <= high) {
        let mid = Math.floor((low + high) / 2);
        if (array[mid] >= startX) {
            result = mid;
            high = mid - 1;
        } else {
            low = mid + 1;
        }
    }
    return result;
};

const findEndIndex = (array, endX) => {
    let low = 0;
    let high = array.length - 1;
    let result = -1;
    while (low <= high) {
        let mid = Math.floor((low + high) / 2);
        if (array[mid] <= endX) {
            result = mid;
            low = mid + 1;
        } else {
            high = mid - 1;
        }
    }
    return result;
};

// 绘制概览图表
const drawOverviewChart = () => {
    try {
        // 清除现有图表
        d3.select('#overview-chart').selectAll('*').remove();

        // 验证容器
        const container = d3.select('.overview-container');
        if (!container.node()) {
            console.warn('Overview container not found');
            return;
        }

        // 验证数据
        if (!overviewData.value || !Array.isArray(overviewData.value)) {
            console.warn('Overview data is not an array');
            return;
        }

        if (overviewData.value.length === 0) {
            console.warn('No overview data available');
            return;
        }

        // 验证每个数据项
        const validData = overviewData.value.filter(d => 
            d && Array.isArray(d.X_value) && 
            Array.isArray(d.Y_value) && 
            d.X_value.length > 0 && 
            d.Y_value.length > 0
        );

        if (validData.length === 0) {
            console.warn('No valid data points in overview data');
            return;
        }

        const containerWidth = container.node().getBoundingClientRect().width;

        const margin = { top: 15, right: 50, bottom: 30, left: 50 };
        const width = containerWidth - margin.left - margin.right;
        const height = 80 - margin.top - margin.bottom;

        const svg = d3
            .select('#overview-chart')
            .attr(
                'viewBox',
                `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`
            )
            .attr('preserveAspectRatio', 'xMidYMid meet')
            .attr('width', '100%');

        const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`);

        // 计算所有数据的 X 范围
        const allX = overviewData.value.flatMap((d) => d.X_value);
        const xExtent = d3.extent(allX);
        
        // 确保 xExtent 有效
        if (!xExtent || !xExtent[0] || !xExtent[1]) {
            console.warn('Invalid X extent:', xExtent);
            return;
        }

        const x = d3.scaleLinear().domain(xExtent).range([0, width]);
        overviewXScale.value = x;

        // 更新 brush_begin 和 brush_end，确保它们是有效的数值
        brush_begin.value = xExtent[0].toFixed(4);
        brush_end.value = xExtent[1].toFixed(4);

        // 更新 store 中的范围值
        store.commit("updatebrush", { 
            begin: brush_begin.value, 
            end: brush_end.value 
        });

        const yExtent = d3.extent(
            overviewData.value.flatMap((d) => d.Y_value)
        );
        const y = d3.scaleLinear().domain(yExtent).range([height, 0]);

        overviewData.value.forEach((data) => {
            g.append('path')
                .datum(data.Y_value)
                .attr('fill', 'none')
                .attr('stroke', data.color || 'steelblue')
                .attr('stroke-width', 1)
                .attr(
                    'd',
                    d3
                        .line()
                        .x((d, i) => x(data.X_value[i]))
                        .y((d) => y(d))
                        .curve(d3.curveMonotoneX)
                );
        });

        g.append('g')
            .attr('transform', `translate(0,${height})`)
            .call(d3.axisBottom(x))
            .selectAll("text") // 选择所有刻度标签
            .style("font-size", "1.1em") // 增大字体大小
            .style("font-weight", "bold"); // 加粗字体;

        const brush = d3
            .brushX()
            .extent([
                [0, 0],
                [width, height],
            ])
            .on('brush end', debounce(brushed, 150));

        overviewBrushInstance.value = brush;

        const brushG = g.append('g').attr('class', 'brush').call(brush);

        // 应用有的 brush_begin 和 brush_end
        const start = parseFloat(brush_begin.value);
        const end = parseFloat(brush_end.value);

        if (!isNaN(start) && !isNaN(end) && start < end) {
            const selection = [x(start), x(end)];
            brushG.call(brush.move, selection);
        } else {
            // 如果 brush_begin 和 brush_end 无效，则使用默认范围
            const initialSelection = brushG.node().__brushSelection || x.range();
            const initialDomain = initialSelection.map(x.invert, x);
            brush_begin.value = initialDomain[0].toFixed(4);
            brush_end.value = initialDomain[1].toFixed(4);
        }

        brushSelections.value.overview = [x(start), x(end)];

        function brushed(event) {
            if (updatingBrush.value) return;

            const selection = event.selection || x.range();
            const newDomain = selection.map(x.invert, x);

            updatingBrush.value = true;
            brush_begin.value = newDomain[0].toFixed(4);
            brush_end.value = newDomain[1].toFixed(4);
            updatingBrush.value = false;

            brushSelections.value.overview = selection;

            selectedChannels.value.forEach((channel) => {
                const channelName = `${channel.channel_name}_${channel.shot_number}`;
                xDomains.value[channelName] = newDomain;
            });

            selectedChannels.value.forEach((channel) => {
                fetchDataAndDrawChart(channel);
            });

            selectedChannels.value.forEach((channel) => {
                const channelName = `${channel.channel_name}_${channel.shot_number}`;
                const channelMatchedResults = matchedResults.value.filter(
                    (r) => r.channel_name === channelName
                );
                channelMatchedResults.forEach((result) => {
                    drawHighlightRects(channelName, [result]);
                });
            });
        }

    } catch (error) {
        console.error('Error in drawOverviewChart:', error);
    }
};

watch(
    () => [store.state.brush_begin, store.state.brush_end],
    ([newBegin, newEnd]) => {
        if (updatingBrush.value) return;
        if (!overviewXScale.value || !overviewBrushInstance.value) return;

        const x = overviewXScale.value;
        const brush = overviewBrushInstance.value;

        const start = parseFloat(newBegin);
        const end = parseFloat(newEnd);

        if (isNaN(start) || isNaN(end) || start >= end) {
            ElMessage.error('请输入有效的起始和结束值');
            return;
        }

        // 更新本地的 brush 值
        brush_begin.value = newBegin;
        brush_end.value = newEnd;

        const selection = [x(start), x(end)];

        updatingBrush.value = true;
        d3.select('#overview-chart').select('.brush').call(brush.move, selection);
        updatingBrush.value = false;

        selectedChannels.value.forEach((channel) => {
            const channelName = `${channel.channel_name}_${channel.shot_number}`;
            xDomains.value[channelName] = [start, end];
        });

        selectedChannels.value.forEach((channel) => {
            fetchDataAndDrawChart(channel);
        });

        selectedChannels.value.forEach((channel) => {
            const channelName = `${channel.channel_name}_${channel.shot_number}`;
            const channelMatchedResults = matchedResults.value.filter(
                (r) => r.channel_name === channelName
            );
            channelMatchedResults.forEach((result) => {
                drawHighlightRects(channelName, [result]);
            });
        });
    }
);

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

// 应用斯平滑
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
        return data; // 不平滑直接返回
    }

    const sigma = t * 20; // 根据 t 调整平滑强度
    return gaussianSmooth(data, sigma);
};


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
    try {
        performance.mark(`Draw Chart ${channelName}-start`);
        
        const container = d3.select('.chart-container');
        const containerWidth = container.node().getBoundingClientRect().width;

        const svg = d3.select(`#chart-${channelName}`);
        const margin = { top: 20, right: 30, bottom: 30, left: 65 };

        const width = containerWidth - margin.left - margin.right;
        const height = 200 - margin.top - margin.bottom;

        svg.selectAll('*').remove();

        svg
            .attr(
                'viewBox',
                `0 0 ${width + margin.left + margin.right} ${height + margin.top + margin.bottom}`
            )
            .attr('preserveAspectRatio', 'xMidYMid meet')
            .attr('width', '100%');

        const yExtent = d3.extent(data.Y_value);
        const yRangePadding = (yExtent[1] - yExtent[0]) * 0.2;
        const yMin = yExtent[0] - yRangePadding;
        const yMax = yExtent[1] + yRangePadding;

        const x = d3
            .scaleLinear()
            .domain(xDomains.value[channelName] || [-2, 6])
            .range([0, width]);

        const y = d3.scaleLinear().domain([yMin, yMax]).range([height, 0]);

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

        g.append('g')
            .attr('class', 'x-axis')
            .attr('transform', `translate(0,${height})`)
            .call(d3.axisBottom(x))
            .selectAll("text") // 选择所有刻度标签
            .style("font-size", "1.3em") // 增大字体大小
            .style("font-weight", "bold");

        g.append('g').attr('class', 'y-axis').call(d3.axisLeft(y)).style("font-size", "1em").style("font-weight", "bold"); // 加粗字体;

        g.append('g')
            .attr('class', 'grid')
            .call(
                d3
                    .axisLeft(y)
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

        g.append('text')
            .attr('x', 20)
            .attr('y', margin.top - 25)
            .attr('text-anchor', 'start')
            .style('font-size', '1.1em')
            .style('font-weight', 'bold')
            .style('fill', color)
            .text(`${channelNumber} | ${shotNumber}:`);

        svg
            .append('text')
            .attr('x', width + margin.left + 15)
            .attr('y', height + margin.top + 20)
            .attr('text-anchor', 'end')
            .style('font-size', '1.1em')
            .style('font-weight', 'bold') // 加粗字体
            .attr('fill', '#000')
            .text(xUnit);

        svg
            .append('text')
            .attr('transform', `translate(${margin.left - 50}, ${margin.top + height / 2}) rotate(-90)`)
            .attr('text-anchor', 'middle')
            .style('font-size', '1.1em')
            .style('font-weight', 'bold') // 加粗字体
            .attr('alignment-baseline', 'middle')
            .attr('fill', '#000')
            .text(yUnit);

        clipGroup
            .append('path')
            .datum(data.Y_value)
            .attr('class', 'original-line')
            .attr('fill', 'none')
            .attr('stroke', color || 'steelblue')
            .attr('stroke-width', 1.5)
            .attr('opacity', smoothnessValue.value > 0 ? 0.3 : 1)
            .attr('d', line);

        errorsData.forEach((errorData, errorIndex) => {
            errorData.X_value_error.forEach((X_value_error, index) => {
                const Y_value_error = errorData.Y_value_error[index];

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
            });
        });

        if (smoothnessValue.value > 0 && smoothnessValue.value <= 1) {
            clipGroup
                .append('path')
                .datum(smoothedYValue)
                .attr('class', 'smoothed-line')
                .attr('fill', 'none')
                .attr('stroke', color || 'steelblue')
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

        g.append('g')
            .attr('class', 'selection-brush')
            .call(selectionBrush);

        const anomaliesGroup = g.append('g').attr('class', 'anomalies-group');

        const channelAnomalies = anomalies.value.filter(
            (a) => a.channelName === channelName
        );
        channelAnomalies.forEach((anomaly) => {
            drawAnomalyElements(anomaly, anomaliesGroup);
        });

        const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
        storedAnomalies.forEach((anomaly) => {
            drawAnomalyElements(anomaly, anomaliesGroup, true);
        });

        function selectionBrushed(event) {
            if (!event.sourceEvent) return;
            if (!event.selection) return;

            const [x0, x1] = event.selection;
            const [startX, endX] = [x.invert(x0), x.invert(x1)];

            const anomaly = {
                id: Date.now(),
                channelName: channelName,
                startX: startX,
                endX: endX,
                anomalyCategory: '',
                anomalyDiagnosisName: '',
                anomalyDescription: '',
            };

            d3.select(this).call(selectionBrush.move, null);

            g.select('.selection-brush .overlay').style(
                'pointer-events',
                'none'
            );

            g.select('.selection-brush .selection').style('display', 'none');

            anomalies.value.push(anomaly);

            drawAnomalyElements(anomaly, anomaliesGroup);
        }

        function drawAnomalyElements(anomaly, anomaliesGroup, isStored = false) {
            const anomalyGroup = anomaliesGroup
                .append('g')
                .attr('class', `anomaly-group-${anomaly.id}-${channelName}`);

            const anomalyLabelsGroup = g
                .append('g')
                .attr('class', `anomaly-labels-group-${anomaly.id}-${channelName}`);

            anomalyLabelsGroup
                .append('text')
                .attr('class', `left-label-${anomaly.id}-${channelName}`)
                .attr('x', x(anomaly.startX))
                .attr('y', -5)
                .style('font-size', '1.1em')
                .style('font-weight', 'bold') // 加粗字体
                .attr('text-anchor', 'middle')
                .attr('fill', 'black')
                .text(anomaly.startX.toFixed(3));

            anomalyLabelsGroup
                .append('text')
                .attr('class', `right-label-${anomaly.id}-${channelName}`)
                .attr('x', x(anomaly.endX))
                .attr('y', -5)
                .style('font-size', '1.1em')
                .style('font-weight', 'bold') // 加粗字体
                .attr('text-anchor', 'middle')
                .attr('fill', 'black')
                .text(anomaly.endX.toFixed(3));

            if (!isStored) {
                const anomalyRect = anomalyGroup
                    .append('rect')
                    .attr('class', `anomaly-rect-${anomaly.id}-${channelName}`)
                    .attr('x', x(anomaly.startX))
                    .attr('y', 0)
                    .attr('width', x(anomaly.endX) - x(anomaly.startX))
                    .attr('height', height)
                    .attr('fill', 'orange')
                    .attr('fill-opacity', 0.1)
                    .attr('stroke', 'orange')
                    .attr('stroke-width', 1)
                    .attr('cursor', 'move')
                    .style('pointer-events', 'all')
                    .call(
                        d3
                            .drag()
                            .on('start', function (event) {
                                anomaly.initialX = event.x;
                            })
                            .on('drag', function (event) {
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

                                updateAnomalyElements(anomaly);
                            })
                            .on('end', function () {
                                const index = anomalies.value.findIndex(
                                    (a) => a.id === anomaly.id
                                );
                                if (index !== -1) {
                                    anomalies.value[index] = anomaly;
                                }
                            })
                    );

                anomalyGroup
                    .append('rect')
                    .attr('class', `left-handle-${anomaly.id}-${channelName}`)
                    .attr('x', x(anomaly.startX) - 5)
                    .attr('y', 0)
                    .attr('width', 10)
                    .attr('height', height)
                    .attr('fill', 'transparent')
                    .attr('cursor', 'ew-resize')
                    .style('pointer-events', 'all')
                    .call(
                        d3
                            .drag()
                            .on('drag', function (event) {
                                const newX = x.invert(event.x);
                                if (newX < anomaly.endX && newX >= x.domain()[0]) {
                                    anomaly.startX = newX;
                                    updateAnomalyElements(anomaly);
                                }
                            })
                            .on('end', function () {
                                const index = anomalies.value.findIndex(
                                    (a) => a.id === anomaly.id
                                );
                                if (index !== -1) {
                                    anomalies.value[index] = anomaly;
                                }
                            })
                    );

                anomalyGroup
                    .append('rect')
                    .attr('class', `right-handle-${anomaly.id}-${channelName}`)
                    .attr('x', x(anomaly.endX) - 5)
                    .attr('y', 0)
                    .attr('width', 10)
                    .attr('height', height)
                    .attr('fill', 'transparent')
                    .attr('cursor', 'ew-resize')
                    .style('pointer-events', 'all')
                    .call(
                        d3
                            .drag()
                            .on('drag', function (event) {
                                const newX = x.invert(event.x);
                                if (newX > anomaly.startX && newX <= x.domain()[1]) {
                                    anomaly.endX = newX;
                                    updateAnomalyElements(anomaly);
                                }
                            })
                            .on('end', function () {
                                const index = anomalies.value.findIndex(
                                    (a) => a.id === anomaly.id
                                );
                                if (index !== -1) {
                                    anomalies.value[index] = anomaly;
                                }
                            })
                    );
            } else {
                anomalyGroup
                    .append('rect')
                    .attr('class', `anomaly-rect-${anomaly.id}-${channelName}`)
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

            const buttonGroup = anomalyGroup
                .append('g')
                .attr(
                    'class',
                    `anomaly-buttons-${anomaly.id}-${channelName}`
                )
                .attr(
                    'transform',
                    `translate(${x(anomaly.endX) - 40}, ${height - 20})`
                )
                .style('pointer-events', 'all');

            const deleteButton = buttonGroup
                .append('g')
                .attr('class', 'delete-button')
                .attr('cursor', 'pointer')
                .on('click', () => {
                    if (isStored) {
                        store.dispatch('deleteAnomaly', {
                            channelName: anomaly.channelName,
                            anomalyId: anomaly.id,
                        });
                    } else {
                        anomalies.value = anomalies.value.filter(
                            (a) => a.id !== anomaly.id
                        );
                    }
                    removeAnomalyElements(anomaly.id, channelName);
                });

            deleteButton
                .append('rect')
                .attr('width', 16)
                .attr('height', 16)
                .attr('fill', '#f56c6c')
                .attr('rx', 3);

            deleteButton
                .append('text')
                .attr('x', 8)
                .attr('y', 12)
                .attr('text-anchor', 'middle')
                .attr('fill', 'white')
                .attr('font-size', '12px')
                .attr('font-weight', 'bold')
                .attr('pointer-events', 'none')
                .text('×');

            const editButton = buttonGroup
                .append('g')
                .attr('class', 'edit-button')
                .attr('transform', 'translate(20, 0)')
                .attr('cursor', 'pointer')
                .on('click', () => {
                    Object.assign(currentAnomaly, anomaly);
                    currentAnomaly.isStored = isStored;
                    showAnomalyForm.value = true;
                });

            editButton
                .append('rect')
                .attr('width', 16)
                .attr('height', 16)
                .attr('fill', '#409eff')
                .attr('rx', 3);

            editButton
                .append('text')
                .attr('x', 8)
                .attr('y', 12)
                .attr('text-anchor', 'middle')
                .attr('fill', 'white')
                .attr('font-size', '12px')
                .attr('font-weight', 'bold')
                .attr('pointer-events', 'none')
                .text('✒️');

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
                .attr('class', `anomaly-line-${anomaly.id}-${channelName}`)
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
                    .select(`.anomaly-rect-${anomaly.id}-${channelName}`)
                    .style('pointer-events', 'none');
                anomalyGroup
                    .selectAll(
                        `.left-handle-${anomaly.id}-${channelName}, .right-handle-${anomaly.id}-${channelName}`
                    )
                    .remove();
            }
        }

        function updateAnomalyElements(anomaly, isStored = false) {
            const anomalyGroup = d3.select(`#chart-${anomaly.channelName}`)
                .select('.anomalies-group')
                .select(`.anomaly-group-${anomaly.id}-${channelName}`);

            anomalyGroup
                .select(`.anomaly-rect-${anomaly.id}-${channelName}`)
                .attr('x', x(anomaly.startX))
                .attr('width', x(anomaly.endX) - x(anomaly.startX));

            anomalyGroup
                .select(`.left-handle-${anomaly.id}-${channelName}`)
                .attr('x', x(anomaly.startX) - 5);

            anomalyGroup
                .select(`.right-handle-${anomaly.id}-${channelName}`)
                .attr('x', x(anomaly.endX) - 5);

            anomalyGroup
                .select(`.anomaly-buttons-${anomaly.id}-${channelName}`)
                .attr(
                    'transform',
                    `translate(${x(anomaly.endX) - 40}, ${height - 20})`
                );

            g.select(
                `.anomaly-labels-group-${anomaly.id}-${channelName} .left-label-${anomaly.id}-${channelName}`
            )
                .attr('x', x(anomaly.startX))
                .text(anomaly.startX.toFixed(3));

            g.select(
                `.anomaly-labels-group-${anomaly.id}-${channelName} .right-label-${anomaly.id}-${channelName}`
            )
                .attr('x', x(anomaly.endX))
                .text(anomaly.endX.toFixed(3));

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
                .select(`.anomaly-line-${anomaly.id}-${channelName}`)
                .datum(anomalyYValues)
                .attr(
                    'd',
                    d3
                        .line()
                        .x((d, i) => x(anomalyXValues[i]))
                        .y((d, i) => y(d))
                );
        }

        function removeAnomalyElements(anomalyId, channelName) {
            const anomaliesGroup = d3.select(`#chart-${channelName}`)
                .select('.anomalies-group');

            anomaliesGroup
                .select(`.anomaly-group-${anomalyId}-${channelName}`)
                .remove();
            g.select(
                `.anomaly-labels-group-${anomalyId}-${channelName}`
            ).remove();

            g.select('.selection-brush .overlay').style(
                'pointer-events',
                'all'
            );

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
    } catch (error) {
        console.error('Error in drawChart:', error);
    }
};

const saveAnomaly = () => {
    if (currentAnomaly) {
        const payload = {
            channelName: currentAnomaly.channelName,
            anomaly: { ...currentAnomaly },
        };

        if (currentAnomaly.isStored) {
            store.dispatch('updateAnomaly', payload);
        } else {
            store.dispatch('addAnomaly', payload);

            anomalies.value = anomalies.value.filter(
                (a) => a.id !== currentAnomaly.id
            );
        }

        showAnomalyForm.value = false;
        ElMessage.success('异常标注信息已保存');

        Object.keys(currentAnomaly).forEach((key) => {
            delete currentAnomaly[key];
        });


        const targetChannel = selectedChannels.value.find(
            (ch) => `${ch.channel_name}_${ch.shot_number}` === payload.channelName
        );

        if (targetChannel) {
            fetchDataAndDrawChart(targetChannel);
        } else {
            console.error('无法找到对应的通道:', payload.channelName);
        }
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
    let percentage = 0;
    const loadingTotal = Number(loadingStates[channelKey]) || 0;
    const renderingTotal = Number(renderingStates[channelKey]) || 0;

    if (loadingTotal === 100) {
        percentage = 50 + renderingTotal / 2;
    } else {
        percentage = loadingTotal / 2;
    }
    return Math.min(Math.max(Math.floor(percentage), 0), 100);
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
    top: -3px;
    left: 60px;
    z-index: 10;
}


.divider {
    width: 100%;
    height: 8px;
}

.overview-container {
    width: 100%;
    position: absolute;
    bottom: 10px;
    top: 82%;
    background-color: white;
}

.overview-svg {
    margin-left: 20px;
    height: 80px;
}

.edit-button {
    z-index: 999999;
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

/* 让对话框中的输入框文字可以选中 */
.el-dialog .el-input {
    user-select: text;
    -webkit-user-select: text;
    -moz-user-select: text;
    -ms-user-select: text;
}
</style>
