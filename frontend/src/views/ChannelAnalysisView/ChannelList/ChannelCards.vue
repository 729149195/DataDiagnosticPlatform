<template>
    <div class="cards">
        <el-card v-for="(channel, index) in selectedChannels" :key="channel.channel_name + '_' + channel.shot_number"
            class="channel-card" style="width: 19%" shadow="hover">
            <div class="channel-content">
                <div style="display: flex; align-items: center;">
                    {{ channel.channel_name }}
                    
                </div>
                    <el-tag link effect="plain" type="info" class="shot-number-tag">
                        {{ channel.shot_number }}
                    </el-tag>
            </div>
            <el-divider />
            <div class="chart-container-wrapper">
                <div :id="'chart-' + sanitizeChannelName(channel.channel_name + '_' + channel.shot_number)"
                    class="chart-container" @click="handleCardClick(channel)"></div>
                <div v-if="loadingChannels[`${channel.channel_name}_${channel.shot_number}`]" class="loading-indicator">
                    <el-icon class="loading-icon"><Loading /></el-icon>
                </div>
            </div>
        </el-card>
    </div>
</template>

<script setup>
import { computed, ref, onMounted, watch, nextTick, onBeforeUnmount } from 'vue';
import { useStore } from 'vuex';
import debounce from 'lodash/debounce';
import Highcharts from 'highcharts';
import 'highcharts/modules/boost';  // 引入Boost模块以提高大数据集的性能
import { Loading } from '@element-plus/icons-vue';

const store = useStore();
// 存储创建的图表实例，用于清理
const chartInstances = ref({});
// 跟踪正在加载的通道
const loadingChannels = ref({});

const handleCardClick = (channel) => {
    // 确保使用"通道名_炮号"的格式
    const fullChannelIdentifier = `${channel.channel_name}_${channel.shot_number}`;
    console.log("点击通道卡片，添加标识符:", fullChannelIdentifier);
    store.commit('updateChannelName', fullChannelIdentifier);
    store.commit('addClickedShownChannelList', channel);
};

const selectedChannels = computed(() => store.state.selectedChannels);
const channelDataCache = computed(() => store.state.channelDataCache);

const sanitizeChannelName = (name) => {
    return name.replace(/[^a-zA-Z0-9_]/g, '');
};

const renderChannelChart = async (channel) => {
    try {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        const containerId = 'chart-' + sanitizeChannelName(channel.channel_name + '_' + channel.shot_number);
        
        // 设置加载状态
        loadingChannels.value[channelKey] = true;
        
        // 清理之前的图表实例
        if (chartInstances.value[containerId]) {
            chartInstances.value[containerId].destroy();
            delete chartInstances.value[containerId];
        }
        
        // 确保DOM元素存在
        const container = document.getElementById(containerId);
        if (!container) {
            console.error(`容器不存在: ${containerId}`);
            loadingChannels.value[channelKey] = false;
            return;
        }
        
        // 清空容器内容
        container.innerHTML = '';
        
        // 从缓存获取通道数据
        let channelData = channelDataCache.value[channelKey];
        if (!channelData) {
            try {
                // 如果缓存中没有，从API获取
                channelData = await store.dispatch('fetchChannelData', { channel });
                if (!channelData?.X_value || !channelData?.Y_value) {
                    console.error(`无效的API数据结构: ${channelKey}`);
                    loadingChannels.value[channelKey] = false;
                    return;
                }
            } catch (error) {
                console.error(`获取数据错误: ${channelKey}`, error);
                loadingChannels.value[channelKey] = false;
                return;
            }
        }
        
        if (!channelData?.X_value || !channelData?.Y_value) {
            console.warn(`无效的通道数据结构: ${channelKey}`);
            loadingChannels.value[channelKey] = false;
            return;
        }
        
        // 创建数据的深拷贝
        const xValues = [...channelData.X_value];
        const yValues = [...channelData.Y_value];
        
        // 对数据进行降采样，直接在这里处理，不使用worker
        const sampledData = sampleDataForThumbnail(xValues, yValues);
        
        // 将X和Y值组合成Highcharts需要的格式
        const seriesData = sampledData.xValues.map((x, i) => [x, sampledData.yValues[i]]);
        
        // 创建Highcharts配置
        const options = {
            chart: {
                renderTo: containerId,
                type: 'line',
                height: 50,
                margin: [0, 0, 0, 0], // 移除所有边距
                backgroundColor: 'transparent',
                animation: false,
                spacing: [0, 0, 0, 0], // 移除内部间距
                skipClone: true, // 优化性能
                styledMode: false, // 禁用样式模式以提高性能
                events: {
                    // 图表渲染完成后的回调
                    load: function() {
                        // 移除加载状态
                        loadingChannels.value[channelKey] = false;
                    }
                }
            },
            title: {
                text: null // 不显示标题
            },
            xAxis: {
                visible: false // 隐藏X轴
            },
            yAxis: {
                visible: false // 隐藏Y轴
            },
            tooltip: {
                enabled: false // 禁用工具提示
            },
            legend: {
                enabled: false // 禁用图例
            },
            credits: {
                enabled: false // 禁用版权信息
            },
            boost: {
                useGPUTranslations: true,
                usePreallocated: true,
                seriesThreshold: 1 // 始终使用boost模式
            },
            plotOptions: {
                series: {
                    animation: false,
                    enableMouseTracking: false, // 禁用鼠标跟踪
                    marker: {
                        enabled: false // 禁用数据点标记
                    },
                    states: {
                        hover: {
                            enabled: false // 禁用悬停状态
                        }
                    },
                    turboThreshold: 0, // 取消默认的1000点限制
                    findNearestPointBy: 'xy',
                    boostThreshold: 1 // 始终使用boost模式
                },
                line: {
                    lineWidth: 1.5
                }
            },
            series: [{
                id: `series-${channel.channel_name}-${channel.shot_number}`, // 添加唯一ID
                name: channel.channel_name,
                color: channel.color || 'steelblue',
                data: seriesData,
                lineWidth: 1.5
            }]
        };
        
        // 创建图表并存储实例
        chartInstances.value[containerId] = Highcharts.chart(options);
    } catch (error) {
        console.error(`渲染通道图表错误: ${channel?.channel_name}`, error);
        // 确保在出错时也移除加载状态
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        loadingChannels.value[channelKey] = false;
    }
};

// 添加一个简单的降采样函数，直接在组件中处理，不依赖worker
const sampleDataForThumbnail = (xValues, yValues) => {
    // 如果数据点少于500，直接返回原始数据
    if (xValues.length <= 500) {
        return { xValues, yValues };
    }
    
    // 计算采样间隔
    const interval = Math.ceil(xValues.length / 500);
    
    // 采样数据
    const sampledX = [];
    const sampledY = [];
    
    for (let i = 0; i < xValues.length; i += interval) {
        sampledX.push(xValues[i]);
        sampledY.push(yValues[i]);
    }
    
    // 确保包含最后一个点
    if (sampledX[sampledX.length - 1] !== xValues[xValues.length - 1]) {
        sampledX.push(xValues[xValues.length - 1]);
        sampledY.push(yValues[yValues.length - 1]);
    }
    
    return { xValues: sampledX, yValues: sampledY };
};

// 修改渲染所有图表的方法，使用串行处理
const renderCharts = debounce(async () => {
    // 初始化所有通道的加载状态
    selectedChannels.value.forEach(channel => {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        loadingChannels.value[channelKey] = true;
    });
    
    // 串行处理每个通道，避免竞争条件
    for (const channel of selectedChannels.value) {
        await renderChannelChart(channel);
    }
}, 150);

watch(
    selectedChannels,
    async (newChannels, oldChannels) => {
        if (JSON.stringify(newChannels) !== JSON.stringify(oldChannels)) {
            await nextTick();
            renderCharts();
        }
    },
    { deep: true }
);

watch(
    channelDataCache,
    () => {
        renderCharts();
    },
    { deep: true }
);

onMounted(() => {
    console.log('ChannelCards组件已挂载，开始初始化图表');
    // 确保DOM已经渲染完成
    nextTick(() => {
        renderCharts();
    });
});

onBeforeUnmount(() => {
    // 清理所有图表实例
    Object.values(chartInstances.value).forEach(chart => {
        if (chart && chart.destroy) {
            try {
                chart.destroy();
            } catch (error) {
                console.error('清理图表实例时出错:', error);
            }
        }
    });
    chartInstances.value = {};
});
</script>


<style scoped lang="scss">
.channel-card {
    margin: 5px;
}

.channel-content {
    display: flex;
    justify-content: space-between;
}

.chart-container-wrapper {
    position: relative;
    width: 100%;
    height: 50px;
}

.chart-container {
    width: 100%;
    height: 100%;
}

.loading-indicator {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    background-color: rgba(255, 255, 255, 0.7);
    z-index: 10;
}

.loading-icon {
    font-size: 20px;
    color: #409EFF;
    animation: rotating 2s linear infinite;
}

@keyframes rotating {
    from {
        transform: rotate(0deg);
    }
    to {
        transform: rotate(360deg);
    }
}

.cards {
    display: flex;
    flex-wrap: wrap;
    justify-content: start;
    width: 100%;
    height: 100%;
    max-height: 29.5vh;
    overflow-y: auto;

    .el-card {
        --el-card-padding: 8px;
        cursor: pointer;
    }
}

:deep(.is-icon-arrow-down) {
    display: none !important;
}

.el-divider--horizontal {
    margin: 5px;
}

.shot-number-tag {
    margin-left: 5px;
}
</style>
