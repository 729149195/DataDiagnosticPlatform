<template>
    <div v-for="(item, index) in filteredData" :key="item.channel_type + '-' + index" class="card">
        <table class="channel-table">
            <tbody>
                <template v-for="(channel, cIndex) in item.channels" :key="channel.channel_key">
                    <tr v-for="(error, eIndex) in channel.displayedErrors"
                        :key="`error-${channel.channel_key}-${eIndex}`">
                        <td v-if="eIndex === 0 && cIndex === 0"
                            :rowspan="item.channels.reduce((total, c) => total + c.displayedErrors.length, 0)"
                            class="channel-type">
                            <span>{{ item.channel_type }}</span>
                            <div class="type-header">
                                <el-checkbox v-model="item.checked" @change="toggleChannelCheckboxes(item)"
                                    class="checkbox-margin"></el-checkbox>
                            </div>
                        </td>

                        <td v-if="eIndex === 0" :rowspan="channel.displayedErrors.length" :class="{
                            'channel-name': true,
                            'channel-name-last': cIndex === item.channels.length - 1
                        }">
                            <div class="name-container">
                                <span class="channel-name-text">{{ channel.channel_name }}</span>
                                <div class="name-right">
                                    <el-checkbox v-model="channel.checked" @change="updateChannelTypeCheckbox(item)"
                                        class="checkbox-margin"></el-checkbox>
                                </div>
                            </div>
                            <el-tag link effect="plain" type="info" class="shot-number-tag">
                                {{ channel.shot_number }}
                            </el-tag>
                            <div class="show-more-container">
                                <el-button link @click="toggleShowAllErrors(channel)">
                                    {{ channel.showAllErrors ? '收起' : '展开全部异常类别' }}
                                    <span v-if="!channel.showAllErrors && hiddenErrorsCount(channel) > 0"
                                        class="hidden-errors">
                                        ({{ hiddenErrorsCount(channel) }})
                                    </span>
                                </el-button>
                            </div>
                        </td>

                        <td :class="{
                            'error-column': true,
                            'error-last':
                                eIndex === channel.displayedErrors.length - 1 &&
                                cIndex !== item.channels.length - 1
                        }">
                            <div class="error-container">
                                <span :title="error.error_name" :style="{ color: error.color }">
                                    {{ formatError(error.error_name) }}
                                </span>
                            </div>
                        </td>
                    </tr>
                </template>
            </tbody>
        </table>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useStore } from 'vuex';

const store = useStore();

// 获取 StructTree 数据
const data = computed(() => store.getters.getStructTree);

// 搜索输入
const search = ref('');

// 计算过滤后的数据
const filteredData = computed(() => {
    if (!search.value) {
        return data.value;
    }
    const query = search.value.toLowerCase();
    return data.value.map(item => {
        const filteredChannels = item.channels.filter(channel =>
            channel.channel_name.toLowerCase().includes(query) ||
            channel.shot_number.toLowerCase().includes(query) ||
            channel.errors.some(error => error.error_name.toLowerCase().includes(query))
        );
        return {
            ...item,
            channels: filteredChannels
        };
    }).filter(item => item.channels.length > 0);
});

// 格式化错误名称
const formatError = (name) => {
    if (name.length > 9) {
        return name.slice(0, 9) + '...';
    }
    return name;
};

// 计算隐藏的错误数量
const hiddenErrorsCount = (channel) => {
    return channel.errors.length - channel.displayedErrors.length;
};

// 更新选中的通道并同步到 Vuex Store
const updateSelectedChannels = () => {
    if (!data.value) {
        return;
    }
    const selected = data.value.flatMap(item =>
        item.channels
            .filter(channel => channel.checked)
            .map(channel => ({
                channel_key: channel.channel_key, // 添加 channel_key
                channel_name: channel.channel_name,
                shot_number: channel.shot_number,
                color: channel.color,
                channel_type: item.channel_type,
                errors: channel.errors.map(error => ({
                    error_key: error.error_key, // 添加 error_key
                    error_name: error.error_name,
                    color: error.color
                }))
            }))
    );

    store.commit('updateSelectedChannels', selected);
};

// 切换所有通道的复选框
const toggleChannelCheckboxes = (item) => {
    if (item && item.channels) {
        item.channels.forEach((channel) => {
            channel.checked = item.checked;
        });
        updateSelectedChannels();
    }
};

// 更新通道类别的复选框状态
const updateChannelTypeCheckbox = (item) => {
    if (!item || !item.channels) {
        console.error('Invalid item or channels:', item);
        return;
    }

    const allChecked = item.channels.every((channel) => channel.checked);
    item.checked = allChecked;
    updateSelectedChannels();
};

// 切换显示所有异常类别
const toggleShowAllErrors = (channel) => {
    channel.showAllErrors = !channel.showAllErrors;
    if (channel.showAllErrors) {
        channel.displayedErrors = channel.errors;
    } else {
        channel.displayedErrors = channel.errors.slice(0, 1);
    }
};

// 监视 StructTree 数据变化，确保复选框状态同步
watch(data, (newData) => {
    updateSelectedChannels();
}, { deep: true });

// 初始化组件时同步复选框状态
onMounted(() => {
    updateSelectedChannels();
});
</script>

<style scoped>
.card {
    border: 1px solid #ddd;
    margin-bottom: 10px;
    border-radius: 5px;
    width: 100%;
}

.channel-table {
    width: 100%;
    border-collapse: collapse;
}

.channel-table td {
    padding: 8px;
    vertical-align: top;
    text-align: center;
}

.channel-type {
    width: 20%;
    vertical-align: top;
    text-align: center;
    padding: 12px;
}

.channel-name {
    width: 35%;
    vertical-align: middle;
    text-align: center;
    border-bottom: 0.5px solid #ddd;
    padding: 12px;
}

.name-container {
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.name-right {
    display: flex;
    align-items: center;
}

.channel-name-text {
    display: block;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-right: 10px;
}

.shot-number-tag {
    color: gray;
    width: 100%;
    margin-top: 5px;
}

.show-more-container {
    display: flex;
    justify-content: center;
    margin-top: 3px;
}

.hidden-errors {
    margin-left: 5px;
    color: #888;
    font-size: 12px;
}

.error-column {
    width: 32%;
    text-align: center;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    border-bottom: none;
}

.error-container {
    display: flex;
    justify-content: center;
    align-items: center;
}

.error-last {
    border-bottom: 0.5px solid #ddd;
}

.checkbox-margin {
    margin-left: 5px;
}

.type-header {
    display: flex;
    justify-content: center;
    align-items: center;
}

.channel-name-last {
    border-bottom: none;
}
</style>
