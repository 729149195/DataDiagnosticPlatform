<!-- LegendComponent.vue -->
<template>
    <div class="legend" id="channelLegendContainer">
        <div class="legend-item" v-for="(item, index) in legendItems" :key="index">
            <!-- <ChannelColorPicker 
                v-model:color="item.color" 
                :predefineColors="predefineColors"
                @change="colorChanged(item)"
                :channelName="item.channelName"
                :shotNumber="item.shotNumber"
            /> -->
            <span :style="{ color: item.color }" class="legend-text">
                {{ item.text }}
            </span>
        </div>
    </div>
</template>

<script setup>
import { computed } from 'vue';
import ChannelColorPicker from '@/components/ChannelColorPicker.vue';

const props = defineProps({
    channelsData: {
        type: Array,
        required: true,
    },
});

const emit = defineEmits(['update-color']);

// Predefined colors
const predefineColors = [
    '#000000', '#4169E1', '#DC143C', '#228B22', '#FF8C00',
    '#800080', '#FF1493', '#40E0D0', '#FFD700', '#8B4513',
    '#2F4F4F', '#1E90FF', '#32CD32', '#FF6347', '#DA70D6',
    '#191970', '#FA8072', '#6B8E23', '#6A5ACD', '#FF7F50',
    '#4682B4',
];

// Construct legend items
const legendItems = computed(() => {
    return props.channelsData.map((data) => {
        const text = `${data.channelshotnumber}_${data.channelName}`;
        return {
            text,
            color: data.color,
            channelKey: `${data.channelName}_${data.channelshotnumber}`,
            channelName: data.channelName,
            shotNumber: data.channelshotnumber
        };
    });
});

// Handle color changes
const colorChanged = (item) => {
    emit('update-color', { channelKey: item.channelKey, color: item.color });
};
</script>

<style scoped>
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
    color: rgba(0, 0, 0, 0.75);
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
</style>