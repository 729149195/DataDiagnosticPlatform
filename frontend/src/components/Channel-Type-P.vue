<template>
    <div class="channel-list-p">
        <div v-for="(item, index) in filteredDisplayedData" :key="item.channel_type + '-' + index" class="card">
            <table class="channel-table">
                <tbody>
                    <template v-for="(channel, cIndex) in item.channels" :key="channel.channel_key">
                        <tr v-for="(error, eIndex) in channel.displayedErrors"
                            :key="`error-${channel.channel_key}-${eIndex}`">
                            <td v-if="eIndex === 0 && cIndex === 0"
                                :rowspan="item.channels.reduce((total, c) => total + c.displayedErrors.length, 0)"
                                class="channel-type">
                                <span :title="item.channel_type">{{ formatChannelType(item.channel_type) }}</span>
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
        <div v-if="loading" class="loading-indicator">
            <el-icon class="is-loading"><Loading /></el-icon>
            加载中...
        </div>
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useStore } from 'vuex';
import { Loading } from '@element-plus/icons-vue'

const store = useStore();
const loading = ref(false);

// 获取 displayedData 数据
const displayedData = computed(() => store.getters.getDisplayedData);

// 搜索输入
const search = ref('');

// 计算过滤后的数据
const filteredDisplayedData = computed(() => {
    if (!search.value) {
        return displayedData.value;
    }
    const query = search.value.toLowerCase();
    return displayedData.value.map(item => {
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

// 监听父组件的滚动事件
const handleParentScroll = async (event) => {
    if (loading.value) return;
    
    const scrollElement = event.target;
    const { scrollTop, scrollHeight, clientHeight } = scrollElement;
    
    // 当滚动到距离底部50px时加载更多
    if (scrollHeight - scrollTop - clientHeight < 50) {
        loading.value = true;
        await store.dispatch('loadMoreData');
        loading.value = false;
    }
};

onMounted(() => {
    // 获取父级的 el-scrollbar__wrap 元素并添加滚动监听
    const parentScrollbar = document.querySelector('.el-scrollbar__wrap');
    if (parentScrollbar) {
        parentScrollbar.addEventListener('scroll', handleParentScroll);
    }
});

onUnmounted(() => {
    // 组件卸载时移除滚动监听
    const parentScrollbar = document.querySelector('.el-scrollbar__wrap');
    if (parentScrollbar) {
        parentScrollbar.removeEventListener('scroll', handleParentScroll);
    }
});

// 格式化错误名称
const formatError = (name) => {
    if (!name) return '';
    const decodedName = decodeURIComponent(escape(name));
    if (decodedName.length > 9) {
        return decodedName.slice(0, 9) + '...';
    }
    return decodedName;
};

// 计算隐藏的错误数量
const hiddenErrorsCount = (channel) => {
    return channel.errors.length - channel.displayedErrors.length;
};

// 更新选中的通道并同步到 Vuex Store
const updateSelectedChannels = () => {
    if (!displayedData.value) {
        return;
    }
    const selected = displayedData.value.flatMap(item =>
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
watch(displayedData, (newData) => {
    updateSelectedChannels();
}, { deep: true });

// 初始化组件时同步复选框状态
onMounted(() => {
    updateSelectedChannels();
});

// 格式化通道类别名称
const formatChannelType = (name) => {
    if (!name) return '';
    const decodedName = decodeURIComponent(escape(name));
    if (decodedName.length > 8) {
        return decodedName.slice(0, 8) + '...';
    }
    return decodedName;
};
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
    font-family: inherit;
}

.channel-table td {
    padding: 8px;
    vertical-align: top;
    text-align: center;
    font-family: inherit;
}

.channel-type {
    width: 20%;
    vertical-align: top;
    text-align: center;
    padding: 12px;
    font-family: inherit;
}

.channel-name {
    width: 35%;
    vertical-align: middle;
    text-align: center;
    border-bottom: 0.5px solid #ddd;
    padding: 12px;
    font-family: inherit;
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
    font-family: inherit;
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

.channel-list-p {
    padding: 10px;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
}

.loading-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 10px;
    color: #909399;
}
</style>
