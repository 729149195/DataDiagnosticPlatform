<template>
    <div class="channel-list-p">
        <div class="table-header-container">
            <table class="channel-table header-table">
                <thead>
                    <tr>
                        <th class="channel-type-header">通道类别</th>
                        <th class="channel-name-header">通道名 & 炮号</th>
                        <th class="error-header">异常类别</th>
                    </tr>
                </thead>
            </table>
        </div>
        <div class="table-content">
            <div v-if="!filteredDisplayedData || filteredDisplayedData.length === 0" :style="{ height: 'calc(70vh - 180px)', display: 'flex', alignItems: 'center', justifyContent: 'center' }">
                <el-empty description='请使用⬆"过滤器"获得通道' :image-size="150"/>
            </div>
            <div v-else v-for="(item, index) in filteredDisplayedData" :key="item.channel_type + '-' + index" class="card">
                <table class="channel-table content-table">
                    <tbody>
                        <template v-for="(channel, cIndex) in item.channels" :key="channel.channel_key">
                            <tr v-for="(error, eIndex) in channel.displayedErrors"
                                :key="`error-${channel.channel_key}-${eIndex}`">
                                <td v-if="eIndex === 0 && cIndex === 0"
                                    :rowspan="item.channels.reduce((total, c) => total + c.displayedErrors.length, 0)"
                                    class="channel-type" 
                                    @click.stop="toggleChannelCheckboxes(item)">
                                    <span :title="item.channel_type" @click.stop="toggleChannelCheckboxes(item)">{{ formatChannelType(item.channel_type) }}</span>
                                    <div class="type-header" @click.stop="toggleChannelCheckboxes(item)">
                                        <el-checkbox v-model="item.checked" @change="toggleChannelCheckboxes(item)"
                                            :disabled="item.allChannelsEmpty"
                                            class="checkbox-margin" @click.stop></el-checkbox>
                                    </div>
                                </td>

                                <td v-if="eIndex === 0" :rowspan="channel.displayedErrors.length" :class="{
                                    'channel-name': true,
                                    'channel-name-last': cIndex === item.channels.length - 1,
                                    'empty-data': channel.status === 'empty_data'
                                }"
                                @click.stop="!isChannelEmpty(channel) && toggleSingleChannel(channel, item)">
                                    <div class="name-container">
                                        <span class="channel-name-text">{{ channel.channel_name }}</span>
                                        <div class="name-right">
                                            <el-icon v-if="isChannelEmpty(channel)" class="empty-data-icon" title="数据为空或无效">
                                                <WarningFilled />
                                            </el-icon>
                                            <el-checkbox v-model="channel.checked" @change="updateChannelTypeCheckbox(item)"
                                                :disabled="isChannelEmpty(channel)"
                                                class="checkbox-margin"></el-checkbox>
                                        </div>
                                    </div>
                                    <el-tag link effect="plain" type="info" class="shot-number-tag">
                                        {{ channel.shot_number }}
                                    </el-tag>
                                    <div class="show-more-container">
                                        <el-button link @click.stop="toggleShowAllErrors(channel)" :disabled="isChannelEmpty(channel)">
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
                                        cIndex !== item.channels.length - 1,
                                    'empty-data': channel.status === 'empty_data'
                                }"
                                @click.stop="!isChannelEmpty(channel) && toggleSingleChannel(channel, item)">
                                    <div class="error-container">
                                        <span v-if="isChannelEmpty(channel)" class="empty-data-text">
                                            {{ channel.status_message || '数据为空或无效' }}
                                        </span>
                                        <span v-else :title="error.error_name">{{ formatError(error.error_name) }}</span>
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
    </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useStore } from 'vuex';
import { Loading, WarningFilled } from '@element-plus/icons-vue'

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
    try {
        // 尝试多种解码方式
        let decodedName = name;
        if (typeof name === 'string' && /[\u0080-\uffff]/.test(name)) {
            try {
                decodedName = decodeURIComponent(escape(name));
            } catch (e) {
                console.warn('Failed to decode error name:', name, e);
            }
        }
        return decodedName;
    } catch (err) {
        console.warn('Error formatting name:', err);
        return name;
    }
};

// 计算隐藏的错误数量
const hiddenErrorsCount = (channel) => {
    return channel.errors.length - channel.displayedErrors.length;
};

// 检查通道是否为空数据
const isChannelEmpty = (channel) => {
    return channel.status === 'empty_data'
}

// 更新选中的通道并同步到 Vuex Store
const updateSelectedChannels = () => {
    if (!displayedData.value) {
        return;
    }
    const selected = displayedData.value.flatMap(item =>
        item.channels
            .filter(channel => channel.checked && !isChannelEmpty(channel))
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
        // 点击单元格时，先切换通道类别的选中状态
        item.checked = !item.checked;
        
        // 然后将此状态应用到所有非空数据通道
        item.channels.forEach((channel) => {
            if (!isChannelEmpty(channel)) {
                channel.checked = item.checked;
            } else {
                channel.checked = false; // 确保空数据通道不被选中
            }
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

    // 只考虑非空数据的通道
    const validChannels = item.channels.filter(channel => !isChannelEmpty(channel));
    const allChecked = validChannels.length > 0 && validChannels.every((channel) => channel.checked);
    
    // 如果所有通道都选中,则通道类别也选中
    // 如果部分通道选中,则通道类别不选中
    // 如果没有通道选中,则通道类别不选中
    item.checked = allChecked;
    
    // 检查是否所有通道都是空数据
    item.allChannelsEmpty = item.channels.every(channel => isChannelEmpty(channel));
    
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

// 切换单个通道的选中状态
const toggleSingleChannel = (channel, item) => {
    if (channel && !isChannelEmpty(channel)) {
        channel.checked = !channel.checked;
        updateChannelTypeCheckbox(item);
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
    try {
        // 尝试多种解码方式
        let decodedName = name;
        if (typeof name === 'string' && /[\u0080-\uffff]/.test(name)) {
            try {
                decodedName = decodeURIComponent(escape(name));
            } catch (e) {
                console.warn('Failed to decode channel type:', name, e);
            }
        }
        return decodedName;
    } catch (err) {
        console.warn('Error formatting channel type:', err);
        return name;
    }
};
</script>

<style scoped>
.channel-list-p {
    position: relative;
    height: 100%;
    padding: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
}

.table-header-container {
    position: absolute;
    top: 0;
    left: 10px;
    right: 10px;
    z-index: 2;
    background-color: #f5f7fa;
}

.header-table {
    margin: 0;
    border-collapse: separate;
    border-spacing: 0;
}

.table-content {
    padding: 44px 10px 10px;
    height: 100%;
    overflow-y: auto;
    box-sizing: border-box;
}

.channel-table {
    width: 100%;
    table-layout: fixed;
    font-family: inherit;
}

.content-table {
    border-collapse: collapse;
}

.channel-table th {
    padding: 12px;
    text-align: center;
    font-weight: normal;
    color: #606266;
    white-space: nowrap;
    overflow: visible;
    border: none;
    background-color: #f5f7fa;
    font-size: 14px;
}

.channel-type-header {
    width: 25%;
    white-space: nowrap;
    overflow: visible;
}

.channel-name-header {
    width: 45%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.error-header {
    width: 30%;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.card {
    border: 1px solid #ddd;
    margin-bottom: 10px;
    border-radius: 5px;
    width: 100%;
}

.channel-table td {
    padding: 12px;
    vertical-align: top;
    text-align: left;
    font-family: inherit;
    border-right: 1px solid #eee;
    word-wrap: break-word;
    white-space: normal;
    cursor: pointer;
    transition: background-color 0.2s ease;
}

.channel-table td:hover {
    background-color: #f0f9ff;
}

.channel-type {
    width: 25%;
    vertical-align: top;
    text-align: left;
    font-family: inherit;
    background-color: #fafafa;
    padding: 12px;
    position: relative;
    z-index: 1;
}

.channel-type::before {
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: -1;
    cursor: pointer;
}

.channel-type span {
    display: block;
    word-wrap: break-word;
    white-space: normal;
    margin-bottom: 8px;
}

.type-header {
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: flex-start;
    gap: 8px;
}

.channel-name {
    width: 45%;
    vertical-align: top;
    text-align: left;
    border-bottom: 1px solid #eee;
    font-family: inherit;
    background-color: #fff;
    padding: 12px;
}

.name-container {
    display: flex;
    flex-wrap: nowrap;
    justify-content: space-between;
    align-items: center;
    width: 100%;
}

.channel-name-text {
    flex: 1;
    word-wrap: break-word;
    white-space: normal;
    margin-right: 8px;
    min-width: 0;
}

.name-right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

.error-column {
    width: 30%;
    vertical-align: top;
    text-align: left;
    word-wrap: break-word;
    word-break: break-all;
    white-space: normal;
    border-bottom: none;
    background-color: #fff;
    padding: 12px;
    max-width: 30%;
}

.error-container {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 8px;
    width: 100%;
    overflow-wrap: break-word;
}

.error-container span {
    flex: 1;
    word-wrap: break-word;
    word-break: break-all;
    white-space: normal;
    min-width: 0;
}

.shot-number-tag {
  color: #666;
  width: calc(100%);
  text-align: center;
}

.show-more-container {
    margin-top: 8px;
    text-align: left;
}

.hidden-errors {
    margin-left: 5px;
    color: #888;
    font-size: 12px;
}

.loading-indicator {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 10px;
    color: #909399;
}

/* 空数据样式 */
.empty-data {
    opacity: 0.6;
    background-color: #fafafa !important;
}

.empty-data-icon {
    color: #f56c6c;
    font-size: 16px;
    margin-right: 4px;
}

.empty-data-text {
    color: #909399;
    font-style: italic;
    font-size: 12px;
}

.disabled {
    opacity: 0.6;
    pointer-events: none;
}

/* 禁用状态的复选框样式 */
:deep(.el-checkbox.is-disabled) {
    opacity: 0.6;
}

:deep(.el-checkbox.is-disabled .el-checkbox__input) {
    cursor: not-allowed;
}
</style>
