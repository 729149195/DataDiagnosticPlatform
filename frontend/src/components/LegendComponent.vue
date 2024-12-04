<!-- LegendComponent.vue -->
<template>
    <div class="legend" id="channelLegendContainer">
        <div class="legend-item" v-for="(item, index) in legendItems" :key="index">
            <ChannelColorPicker v-model:color="item.color" :predefineColors="predefineColors"
                @change="colorChanged(item)" />
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
        const minY = Math.min(...data.Y_original);
        const maxY = Math.max(...data.Y_original);
        const text = `${data.channelNumber} / ${data.channelshotnumber} / max(${maxY.toFixed(
            2
        )}) | min(${minY.toFixed(2)})`;
        return {
            text,
            color: data.color,
            channelKey: `${data.channelName}_${data.channelshotnumber}`,
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
    justify-content: center;
    align-items: center;
    flex-wrap: wrap;
    height: 100px;
    max-height: 100px;
    overflow-y: auto;
    margin-top: 5px;
}

.legend-item {
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 15px;

}

.legend-text {
    font-weight: bold;
    margin-left: 0px;
    font-size: 0.95em;
}
</style>