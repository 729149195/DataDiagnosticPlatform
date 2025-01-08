<template>
    <div class="cards">
        <el-card v-for="(channel, index) in selectedChannels" :key="channel.channel_name + '_' + channel.shot_number"
            class="channel-card" style="width: 19%" shadow="hover">
            <div class="channel-content">
                <div style="display: flex; align-items: center;">
                    {{ channel.channel_name }}
                    
                </div>
                <!-- <el-color-picker v-model="channel.color" @change="setSingleChannelColor(channel)"
                    class="channel-color-picker" show-alpha :predefine="predefineColors" size="small" /> -->
                    <el-tag link effect="plain" type="info" class="shot-number-tag">
                        {{ channel.shot_number }}
                    </el-tag>
            </div>
            <el-divider />
            <div :id="'chart-' + sanitizeChannelName(channel.channel_name + '_' + channel.shot_number)"
                class="chart-container" @click="handleCardClick(channel)"></div>
        </el-card>
    </div>
</template>

<script setup>
import { computed, ref, onMounted, watch, nextTick } from 'vue';
import { useStore } from 'vuex';
import debounce from 'lodash/debounce';
import * as d3 from 'd3';

const store = useStore();

const handleCardClick = (channel) => {
    const fullChannelIdentifier = `${channel.shot_number}_${channel.channel_name}`;
    store.commit('updateChannelName', fullChannelIdentifier);
    store.commit('addClickedShownChannelList', channel);
};

const predefineColors = ref([
    'rgba(255, 215, 0, 0)',
    '#4169E1',
    '#DC143C',
    '#228B22',
    '#FF8C00',
    '#800080',
    '#FF1493',
    '#40E0D0',
    '#FFD700',
    '#8B4513',
    '#2F4F4F',
    '#1E90FF',
    '#32CD32',
    '#FF6347',
    '#DA70D6',
    '#191970',
    '#FA8072',
    '#6B8E23',
    '#6A5ACD',
    '#FF7F50',
    '#4682B4',
]);

const selectedChannels = computed(() => store.state.selectedChannels);
const channelDataCache = computed(() => store.state.channelDataCache);

const sanitizeChannelName = (name) => {
    return name.replace(/[^a-zA-Z0-9_]/g, '');
};

const setSingleChannelColor = (channel) => {
    if (channel) {
        updateSelectedChannels();
        renderChannelChart(channel);
    } else {
        console.error('Invalid channel:', channel);
    }
};

const updateSelectedChannels = () => {
    const selected = selectedChannels.value.map((channel) => ({
        channel_name: channel.channel_name,
        shot_number: channel.shot_number,
        color: channel.color,
        channel_type: channel.channel_type,
        errors: channel.errors.map((error) => ({
            error_name: error.error_name,
            color: error.color,
        })),
    }));

    store.commit('updateSelectedChannels', selected);
};

const sampleData = (data, numSamples) => {
    const sampledData = [];
    const dataLength = data.length;
    if (dataLength <= numSamples) {
        return data.slice();
    }
    const samplingInterval = dataLength / numSamples;
    for (let i = 0; i < numSamples; i++) {
        sampledData.push(data[Math.floor(i * samplingInterval)]);
    }
    return sampledData;
};

const renderChannelChart = async (channel) => {
    try {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        const channelData = channelDataCache.value[channelKey];

        if (channelData) {
            const numSamples = 100;
            const sampledXValues = sampleData(channelData.X_value, numSamples);
            const sampledYValues = sampleData(channelData.Y_value, numSamples);

            renderChart(sampledXValues, sampledYValues, channel);
        }
    } catch (error) {
        console.error('Error rendering channel chart:', error);
    }
};

const renderChart = (xValues, yValues, channel) => {
    const containerId = 'chart-' + sanitizeChannelName(channel.channel_name + '_' + channel.shot_number);
    const container = d3.select('#' + containerId);

    container.selectAll('*').remove();

    const containerWidth = container.node().clientWidth;
    const containerHeight = 50;

    const margin = { top: 5, right: 5, bottom: 5, left: 5 };
    const width = containerWidth - margin.left - margin.right;
    const height = containerHeight - margin.top - margin.bottom;

    const svg = container
        .append('svg')
        .attr('width', containerWidth)
        .attr('height', containerHeight)
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);

    const xScale = d3
        .scaleLinear()
        .domain(d3.extent(xValues))
        .range([0, width]);

    const yScale = d3
        .scaleLinear()
        .domain(d3.extent(yValues))
        .range([height, 0]);

    const line = d3
        .line()
        .x((d, i) => xScale(xValues[i]))
        .y((d, i) => yScale(yValues[i]));

    svg
        .append('path')
        .datum(yValues)
        .attr('fill', 'none')
        .attr('stroke', channel.color || 'steelblue')
        .attr('stroke-width', 1.5)
        .attr('d', line);
};

const renderCharts = debounce(async () => {
    await Promise.all(
        selectedChannels.value.map((channel) => renderChannelChart(channel))
    );
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
    renderCharts();
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

.chart-container {
    width: 100%;
    height: 50px;
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
