<template>
    <div class="result-chart-container">
        <div class="channel-info" v-if="curChannel.channel_name">
            <div class="color-block" :style="{ backgroundColor: curChannel.color || 'steelblue' }"></div>
            <div class="channel-name">{{ curChannel.channel_name }}</div>
        </div>
        
        <!-- 美化后的进度条 -->
        <transition name="fade">
            <div v-if="isCalculating" class="progress-overlay">
                <div class="progress-content">
                    <div class="progress-step-indicator">{{ calculatingProgress.step }}</div>
                    <div class="progress-bar-container">
                        <div class="progress-bar-track">
                            <div class="progress-bar-fill" :style="{ width: `${calculatingProgress.progress}%` }">
                                <div class="progress-bar-pulse"></div>
                            </div>
                        </div>
                        <div class="progress-percentage">{{ calculatingProgress.progress }}%</div>
                    </div>
                </div>
            </div>
        </transition>
        
        <div class="chart-wrapper">
            <div id="calculation-result-container" ref="chartContainerRef"></div>
        </div>
    </div>
</template>

<script setup>
import Highcharts from 'highcharts';
import 'highcharts/modules/boost';  // 引入Boost模块以提高大数据集的性能
import 'highcharts/modules/accessibility';  // 引入无障碍模块
import { useStore } from 'vuex';
import { computed, ref, watch, onMounted, onUnmounted } from "vue";

// 设置Highcharts全局配置
Highcharts.setOptions({
  accessibility: {
    enabled: false // 禁用无障碍功能，避免相关错误
  }
});


// 获取 Vuex 状态
const store = useStore();
const curChannel = ref({});
const curChannelKey = ref('');
const ErrorLineXScopes = computed(() => store.state.ErrorLineXScopes);
const CalculateResult = computed(() => store.state.CalculateResult);
const channelDataCache = computed(() => store.state.channelDataCache);
const chartContainerRef = ref(null);
const resultData = ref(null);
const chartInstance = ref(null);

// 计算状态和进度 
const isCalculating = computed(() => store.state.isCalculating);
const calculatingProgress = computed(() => store.state.calculatingProgress);

// 用于标识当前组件的图表实例
const CHART_INSTANCE_ID = 'calculation-result-chart';

defineExpose({
    chartContainerRef: chartContainerRef,
    resultData: resultData,
    resultSvgRef: computed(() => chartInstance.value ? document.getElementById('calculation-result-container').querySelector('svg') : null)
})

// 在组件卸载时销毁图表实例
onUnmounted(() => {
    // 清除防抖定时器
    if (debouncedDrawResult.timer) {
        clearTimeout(debouncedDrawResult.timer);
    }

    if (chartInstance.value) {
        // 先清空数据，减少内存占用
        if (chartInstance.value.series) {
            chartInstance.value.series.forEach(series => {
                if (series && series.setData) {
                    series.setData([], false);
                }
            });
        }

        // 销毁图表实例
        chartInstance.value.destroy();
        chartInstance.value = null;
    }

    // 移除键盘事件监听
    if (chartContainerRef.value) {
        chartContainerRef.value.removeEventListener('keydown', handleKeyDown);
    }

    // 移除窗口大小变化监听
    window.removeEventListener('resize', handleResize);
});

// 处理键盘事件 - 改为绑定到容器元素而非全局
const handleKeyDown = (e) => {
    if (e.key === 'Escape' && chartInstance.value) {
        // 按ESC键取消当前的选择操作
        if (chartInstance.value.pointer) {
            chartInstance.value.pointer.drop();
        }
    }
};

// 组件挂载时初始化
onMounted(() => {
    // 添加键盘事件监听 - 改为绑定到容器元素
    if (chartContainerRef.value) {
        chartContainerRef.value.addEventListener('keydown', handleKeyDown);
        // 确保容器可以获得焦点
        chartContainerRef.value.tabIndex = 0;
    }

    // 添加窗口大小变化监听 - 使用节流函数限制调用频率
    window.addEventListener('resize', handleResize);
});

const fetchChannelData = async (channel) => {
    try {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;

        // 确保使用最新数据
        let channelData = channelDataCache.value[channelKey];
        if (!channelData) {
            const data = await store.dispatch('fetchChannelData', { channel });
            channelData = data; // 获取最新数据
        }

        // 强制重新绘制
        drawChart(
            channelData.X_value,
            channelData.Y_value,
            channel,
            channelKey
        );

    } catch (error) {
        console.error('Error fetching channel data:', error);
    }
};

// 优化数据处理函数，减少数据点数量
const optimizeDataPoints = (xValues, yValues, maxPoints = 100000) => {
    const totalPoints = xValues.length;

    // 如果数据点少于最大点数，直接返回原始数据
    if (totalPoints <= maxPoints) {
        return { xValues, yValues };
    }

    // 计算采样间隔
    const interval = Math.ceil(totalPoints / maxPoints);

    // 采样数据
    const sampledX = [];
    const sampledY = [];

    for (let i = 0; i < totalPoints; i += interval) {
        sampledX.push(xValues[i]);
        sampledY.push(yValues[i]);
    }

    // 确保包含最后一个点
    if (sampledX[sampledX.length - 1] !== xValues[totalPoints - 1]) {
        sampledX.push(xValues[totalPoints - 1]);
        sampledY.push(yValues[totalPoints - 1]);
    }

    return { xValues: sampledX, yValues: sampledY };
};

const drawChart = (xValues, yValues, channel, channelKey) => {
    try {
        // console.log('初始化图表，通道:', channel?.channel_name);
        
        if (!xValues || xValues.length === 0 || !yValues || yValues.length === 0) {
            console.error('Invalid data for drawing chart');
            return;
        }

        // 优化数据点数量
        const { xValues: optimizedX, yValues: optimizedY } = optimizeDataPoints(xValues, yValues);

        // 将X和Y值组合成Highcharts需要的格式
        const seriesData = optimizedX.map((x, i) => [x, optimizedY[i]]);

        // 如果已经存在图表实例，则销毁它
        if (chartInstance.value) {
            chartInstance.value.destroy();
        }

        // 创建Highcharts配置 - 不使用全局配置，而是在每个实例中设置
        const options = {
            chart: {
                renderTo: 'calculation-result-container', // 使用更具体的ID
                type: 'line',
                zoomType: 'xy', // 允许在x和y轴上进行选择缩放
                panning: true,
                panKey: 'shift',
                animation: false, // 禁用动画提高性能
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
                spacing: [10, 10, 30, 10], // 增加底部间距，为X轴标签留出空间
                marginTop: 10,
                marginBottom: 40, // 增加底部边距，确保X轴标签可见
                marginLeft: 40, // 确保Y轴标签可见
                marginRight: 20, // 右侧留出一些空间
                events: {
                    load: function () {
                        const container = this.container;
                        const chart = this;

                        // 绑定双击事件，使用更高效的方式重置缩放
                        container.ondblclick = function () {
                            // 直接重置缩放，不使用动画
                            chart.xAxis[0].setExtremes(null, null, false);
                            chart.yAxis[0].setExtremes(null, null, false);
                            chart.redraw(false); // 禁用动画加速重绘
                        };
                    }
                }
            },
            // 使用实例配置而非全局配置
            global: {
                useUTC: false
            },
            boost: {
                useGPUTranslations: true,
                usePreallocated: true,
                seriesThreshold: 1
            },
            title: {
                text: '', // 不使用标题
            },
            xAxis: {
                title: {
                    text: ''
                },
                gridLineWidth: 1, // 恢复网格线
                gridLineDashStyle: 'ShortDash', // 使用虚线样式
                gridLineColor: '#e6e6e6', // 使用浅灰色
                tickLength: 5,
                lineColor: '#ccc',
                lineWidth: 1,
                labels: {
                    enabled: true, // 确保标签启用
                    style: {
                        fontSize: '11px',
                        color: '#666'
                    },
                    y: 20 // 增加标签与轴的距离
                }
            },
            yAxis: {
                title: {
                    text: ''
                },
                gridLineWidth: 1, // 恢复网格线
                gridLineDashStyle: 'ShortDash', // 使用虚线样式
                gridLineColor: '#e6e6e6', // 使用浅灰色
                tickLength: 5,
                lineColor: '#ccc',
                lineWidth: 1,
                labels: {
                    enabled: true, // 确保标签启用
                    style: {
                        fontSize: '11px',
                        color: '#666'
                    },
                    align: 'right',
                    x: -10 // 调整标签与轴的距离
                }
            },
            boost: {
                useGPUTranslations: true,
                usePreallocated: true,
                seriesThreshold: 1, // 启用boost模块的阈值
                allowForce: true, // 强制使用boost模式
                debug: {
                    timeRendering: false,
                    timeSeriesProcessing: false,
                    timeSetup: false
                }
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
                    animation: false, // 禁用系列动画
                    enableMouseTracking: true,
                    marker: {
                        enabled: false
                    },
                    states: {
                        hover: {
                            enabled: false // 禁用悬停状态以提高性能
                        }
                    },
                    turboThreshold: 0, // 取消默认的1000点限制
                    findNearestPointBy: 'xy', // 优化点查找算法
                    stickyTracking: false // 禁用粘性跟踪以提高性能
                },
                line: {
                    lineWidth: 1.5
                }
            },
            legend: {
                enabled: false  // 禁用默认图例
            },
            credits: {
                enabled: false
            },
            accessibility: {
                enabled: false // 禁用无障碍功能，避免相关错误
            },
            // 禁用Highcharts自带的导出按钮
            exporting: {
                enabled: false
            },
            series: [{
                id: CHART_INSTANCE_ID, // 添加唯一ID，避免与其他图表冲突
                name: channel?.channel_name || '',
                color: channel?.color || 'steelblue',
                data: seriesData,
                boostThreshold: 1, // 当数据点超过1000时启用boost
                lineWidth: 1.5,
                animation: false // 禁用动画
            }]
        };

        // 创建图表 - 使用try/catch捕获可能的错误
        try {
            chartInstance.value = new Highcharts.Chart(options);
            
            // 确保图表完全渲染后轴标签可见
            setTimeout(() => {
                if (chartInstance.value) {
                    try {
                        // 强制更新轴以确保标签可见
                        chartInstance.value.xAxis[0].update({
                            labels: {
                                enabled: true,
                                y: 20
                            }
                        }, false);

                        chartInstance.value.yAxis[0].update({
                            labels: {
                                enabled: true
                            }
                        }, false);

                        chartInstance.value.redraw(false);
                    } catch (error) {
                        console.error("更新轴标签时出错:", error);
                    }
                }
            }, 200);
        } catch (error) {
            console.error("创建图表实例时出错:", error);
        }
    } catch (error) {
        console.error("DrawChart全局错误:", error);
    }
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
    // 检查结果是否为空或无效
    if (!CalculateResult) {
        console.error('Invalid calculation result');
        return;
    }

    // 绘制新通道数据
    if ('X_value' in CalculateResult) {
        try {
            // console.log("开始绘制计算结果:", CalculateResult.channel_name);
            
            // 优化数据点数量
            const { xValues: optimizedX, yValues: optimizedY } = optimizeDataPoints(
                CalculateResult['X_value'],
                CalculateResult['Y_value']
            );

            const seriesData = optimizedX.map((x, i) => [x, optimizedY[i]]);

            // 更新通道信息显示 - 显示运算表达式作为通道名
            if (CalculateResult['channel_name']) {
                curChannel.value = {
                    channel_name: CalculateResult['channel_name'],
                    color: 'steelblue'
                };
            }

            if (chartInstance.value) {
                // console.log("更新现有图表...");
                // 如果图表已存在，更新数据
                try {
                    if (chartInstance.value.series && chartInstance.value.series.length > 0) {
                        // 更新图例标题（不使用update方法）
                        if (CalculateResult['channel_name']) {
                            chartInstance.value.series[0].name = CalculateResult['channel_name'];
                        }
                        
                        // 直接使用setData替代update
                        chartInstance.value.series[0].setData(seriesData, false); // 禁用动画
                        chartInstance.value.redraw(false); // 禁用动画加速重绘
                    } else {
                        // 如果没有系列，添加一个新的
                        chartInstance.value.addSeries({
                            id: CHART_INSTANCE_ID, // 确保使用唯一ID
                            name: CalculateResult['channel_name'] || '计算结果',
                            data: seriesData,
                            boostThreshold: 1000,
                            lineWidth: 1.5,
                            animation: false // 禁用动画
                        }, false);
                        chartInstance.value.redraw(false); // 禁用动画加速重绘
                    }
                } catch (error) {
                    console.error("更新图表失败，尝试重新创建:", error);
                    // 如果更新失败，尝试重新创建图表
                    chartInstance.value.destroy();
                    chartInstance.value = null;
                    
                    // 重新创建图表
                    drawChart(
                        CalculateResult['X_value'], 
                        CalculateResult['Y_value'], 
                        { 
                            channel_name: CalculateResult['channel_name'] || '计算结果',
                            color: 'steelblue'
                        }
                    );
                }
            } else {
                // console.log("创建新图表...");
                // 如果图表不存在，创建新图表
                drawChart(
                    CalculateResult['X_value'], 
                    CalculateResult['Y_value'], 
                    { 
                        channel_name: CalculateResult['channel_name'] || '计算结果',
                        color: 'steelblue'
                    }
                );
            }
        } catch (error) {
            console.error('Error drawing calculation result:', error);
        }
    }

    // 绘制异常数据
    if ('X_range' in CalculateResult) {
        try {
            // console.log("绘制异常区域...");
            await fetchChannelData(curChannel.value);
            const ErrorLineXScopes = CalculateResult['X_range'];
            const channelKey = curChannelKey.value;

            const channelData = channelDataCache.value[channelKey];
            if (!channelData) {
                console.error('Channel data not found in cache:', channelKey);
                return;
            }

            let xValues = channelData.X_value;
            let yValues = channelData.Y_value;

            // 移除之前的异常区域系列
            if (chartInstance.value) {
                try {
                    // 保存第一个系列（主数据系列）
                    const mainSeries = chartInstance.value.series[0];
                    const mainSeriesOptions = {
                        id: CHART_INSTANCE_ID,
                        name: mainSeries.name,
                        color: mainSeries.color,
                        data: mainSeries.options.data,
                        boostThreshold: 1000,
                        lineWidth: 1.5,
                        animation: false
                    };

                    // 准备所有异常区域系列数据
                    const newSeriesOptions = [];
                    newSeriesOptions.push(mainSeriesOptions);

                    ErrorLineXScopes.forEach((ErrorLineXScope, errorIndex) => {
                        let ErrorLineXIndex = scope2Index(ErrorLineXScope, xValues);

                        // 优化异常区域数据点
                        let X_value_error = xValues.slice(ErrorLineXIndex[0], ErrorLineXIndex[1] + 1);
                        let Y_value_error = yValues.slice(ErrorLineXIndex[0], ErrorLineXIndex[1] + 1);

                        // 对异常区域数据进行优化
                        const { xValues: optimizedX, yValues: optimizedY } = optimizeDataPoints(
                            X_value_error,
                            Y_value_error,
                            2000 // 异常区域使用更少的点
                        );

                        const errorData = optimizedX.map((x, i) => [x, optimizedY[i]]);

                        newSeriesOptions.push({
                            id: `${CHART_INSTANCE_ID}-error-${errorIndex}`,
                            name: `异常区域 ${errorIndex + 1}`,
                            data: errorData,
                            color: '#ff6767',
                            lineWidth: 2,
                            opacity: 0.8,
                            boostThreshold: 1000,
                            animation: false
                        });
                    });

                    // 销毁当前图表，创建新图表
                    const container = chartInstance.value.container.id;
                    chartInstance.value.destroy();
                    
                    // 创建新的图表配置
                    const options = {
                        chart: {
                            renderTo: container,
                            type: 'line',
                            zoomType: 'xy',
                            panning: true,
                            panKey: 'shift',
                            animation: false,
                            resetZoomButton: {
                                enabled: false,
                                theme: { style: { display: 'none' } },
                                position: { x: -9999, y: -9999 }
                            },
                            spacing: [10, 10, 30, 10],
                            marginTop: 10,
                            marginBottom: 40,
                            marginLeft: 40,
                            marginRight: 20
                        },
                        global: { useUTC: false },
                        boost: {
                            useGPUTranslations: true,
                            usePreallocated: true,
                            seriesThreshold: 1
                        },
                        title: { text: '' },
                        xAxis: {
                            title: { text: '' },
                            gridLineWidth: 1,
                            gridLineDashStyle: 'ShortDash',
                            gridLineColor: '#e6e6e6',
                            tickLength: 5,
                            lineColor: '#ccc',
                            lineWidth: 1,
                            labels: {
                                enabled: true,
                                style: { fontSize: '11px', color: '#666' },
                                y: 20
                            }
                        },
                        yAxis: {
                            title: { text: '' },
                            gridLineWidth: 1,
                            gridLineDashStyle: 'ShortDash',
                            gridLineColor: '#e6e6e6',
                            tickLength: 5,
                            lineColor: '#ccc',
                            lineWidth: 1,
                            labels: {
                                enabled: true,
                                style: { fontSize: '11px', color: '#666' },
                                align: 'right',
                                x: -10
                            }
                        },
                        tooltip: {
                            enabled: true,
                            formatter: function() {
                                return `( ${this.x.toFixed(3)}, ${this.y.toFixed(3)} )`;
                            },
                            backgroundColor: 'rgba(255, 255, 255, 0.8)',
                            borderWidth: 1,
                            borderColor: '#ccc',
                            shadow: false,
                            style: { fontSize: '12px', padding: '2px 5px' }
                        },
                        plotOptions: {
                            series: {
                                animation: false,
                                enableMouseTracking: true,
                                marker: { enabled: false },
                                states: { hover: { enabled: false } },
                                turboThreshold: 0,
                                findNearestPointBy: 'xy',
                                stickyTracking: false
                            },
                            line: { lineWidth: 1.5 }
                        },
                        legend: { enabled: false },
                        credits: { enabled: false },
                        accessibility: { enabled: false },
                        series: newSeriesOptions
                    };
                    
                    // 创建新图表实例
                    chartInstance.value = new Highcharts.Chart(options);
                    
                } catch (error) {
                    console.error("绘制异常区域出错:", error);
                }
            }
        } catch (error) {
            console.error('Error drawing error ranges:', error);
        }
    }
};

const clickedShownChannelList = computed(() => store.state.clickedShownChannelList);

watch(clickedShownChannelList, async (newClickedShownChannelList, oldV) => {
    // 支持多通道情况
    if (newClickedShownChannelList && newClickedShownChannelList.length > 0) {
        // 获取第一个通道用于展示
        const channel = newClickedShownChannelList[0];
        await fetchChannelData(channel);
        curChannel.value = channel;
        // 构建 channelKey
        curChannelKey.value = `${channel.channel_name}_${channel.shot_number}`;
    }
}, { deep: true });

// 优化防抖函数，添加取消功能
const debounce = (fn, delay) => {
    let timer = null;
    const debouncedFn = function (...args) {
        if (timer) clearTimeout(timer);
        timer = setTimeout(() => {
            fn.apply(this, args);
            timer = null;
        }, delay);
    };
    debouncedFn.timer = timer;
    debouncedFn.cancel = () => {
        if (timer) {
            clearTimeout(timer);
            timer = null;
        }
    };
    return debouncedFn;
};

// 使用防抖处理CalculateResult的变化
const debouncedDrawResult = debounce(async (newCalculateResult) => {
    resultData.value = newCalculateResult;
    if (newCalculateResult) {
        await drawResult(newCalculateResult);
    }
}, 50); // 50ms的防抖延迟

watch(CalculateResult, (newCalculateResult, oldV) => {
    debouncedDrawResult(newCalculateResult);
}, { deep: true });

// 节流函数限制事件触发频率
const throttle = (fn, delay) => {
    let last = 0;
    return function (...args) {
        const now = Date.now();
        if (now - last >= delay) {
            last = now;
            fn.apply(this, args);
        }
    };
};

// 处理窗口大小变化
const handleResize = throttle(() => {
    if (chartInstance.value) {
        chartInstance.value.reflow();

        // 确保X轴标签可见
        if (chartInstance.value.xAxis && chartInstance.value.xAxis[0]) {
            chartInstance.value.xAxis[0].update({
                labels: {
                    enabled: true,
                    y: 20
                }
            }, false);
        }

        // 确保Y轴标签可见
        if (chartInstance.value.yAxis && chartInstance.value.yAxis[0]) {
            chartInstance.value.yAxis[0].update({
                labels: {
                    enabled: true
                }
            }, false);
        }

        chartInstance.value.redraw(false);
    }
}, 100); // 100ms的节流延迟

</script>

<style scoped>
.result-chart-container {
    display: flex;
    flex-direction: column;
    padding-bottom: 0;
    height: 100%;
    position: relative; /* 添加相对定位，使进度条可以绝对定位 */
}

/* 淡入淡出动画 */
.fade-enter-active, .fade-leave-active {
    transition: opacity 0.3s ease;
}
.fade-enter-from, .fade-leave-to {
    opacity: 0;
}

/* 进度条覆盖层 */
.progress-overlay {
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    z-index: 1000;
    width: 400px;
    max-width: 90%;
    background-color: rgba(255, 255, 255, 0.95);
    border-radius: 8px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
    padding: 20px;
}

.progress-content {
    display: flex;
    flex-direction: column;
    align-items: center;
}

.progress-step-indicator {
    font-size: 14px;
    font-weight: 500;
    color: #333;
    margin-bottom: 15px;
    text-align: center;
}

.progress-bar-container {
    width: 100%;
    display: flex;
    align-items: center;
    margin-bottom: 10px;
}

.progress-bar-track {
    flex-grow: 1;
    height: 8px;
    background-color: #f1f1f1;
    border-radius: 4px;
    overflow: hidden;
    margin-right: 15px;
    position: relative;
}

.progress-bar-fill {
    height: 100%;
    background: linear-gradient(90deg, #4285F4, #34A853);
    border-radius: 4px;
    position: relative;
    transition: width 0.3s ease;
}

/* 脉冲效果 */
.progress-bar-pulse {
    position: absolute;
    right: 0;
    top: 0;
    height: 100%;
    width: 15px;
    background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.8), rgba(255,255,255,0));
    animation: pulse 1.5s infinite;
}

.progress-percentage {
    font-size: 14px;
    font-weight: 600;
    color: #4285F4;
    min-width: 40px;
    text-align: right;
}

@keyframes pulse {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

.channel-info {
    display: flex;
    align-items: center;
    padding: 8px 0 4px 65px;
    /* 左侧与Y轴对齐 */
    font-weight: bold;
}

.color-block {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    margin-right: 6px;
}

.channel-name {
    font-size: 14px;
}

.chart-wrapper {
    flex: 1;
    display: flex;
    flex-direction: column;
    width: 100%;
    margin-bottom: 0;
    height: calc(100% - 30px);
    /* 减去通道信息的高度 */
    min-height: 400px;
    /* 增加最小高度，确保有足够空间显示X轴标签 */
}

#calculation-result-container {
    width: 100%;
    height: 100%;
    /* 使用100%高度填充父容器 */
    min-height: 400px;
    /* 增加最小高度，确保有足够空间显示X轴标签 */
}

:deep(.highcharts-selection-marker) {
    fill: rgba(51, 92, 173, 0.25);
    stroke: #335cad;
}

:deep(.highcharts-zooming-rect) {
    fill: rgba(51, 92, 173, 0.25);
    stroke: #335cad;
}

/* 确保X轴标签可见 */
:deep(.highcharts-axis-labels) {
    font-size: 11px;
    fill: #666;
}

:deep(.highcharts-xaxis-labels) {
    visibility: visible !important;
}
</style>
