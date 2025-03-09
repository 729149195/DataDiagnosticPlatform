<template>
  <div class="channel-list">
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
      <div v-for="(item, index) in displayedData" :key="index" class="card">
        <table class="channel-table content-table">
          <tbody>
            <template v-for="(channel, cIndex) in item.channels" :key="`channel-${cIndex}`">
              <tr v-for="(error, eIndex) in channel.displayedErrors" :key="`error-${cIndex}-${eIndex}`">
                <!-- Channel Type Cell -->
                <td v-if="eIndex === 0 && cIndex === 0"
                  :rowspan="item.channels.reduce((total, c) => total + c.displayedErrors.length, 0)" class="channel-type"
                  @click.stop="toggleChannelCheckboxes(item)">
                  <span :title="item.channel_type" @click.stop="toggleChannelCheckboxes(item)">{{ formatChannelType(item.channel_type) }}</span>
                  <div class="type-header" @click.stop="toggleChannelCheckboxes(item)">
                    <!-- Use the reusable ChannelColorPicker component -->
                    <ChannelColorPicker 
                      :color="item.color" 
                      :predefineColors="predefineColors" 
                      @change="setChannelColor(item)" 
                      @update:color="item.color = $event"
                      :channelName="item.channel_type"
                      class="category-color-picker"
                    />
                    <el-checkbox v-model="item.checked" @change="toggleChannelCheckboxes(item)"
                      class="checkbox-margin" @click.stop></el-checkbox>
                  </div>
                </td>
                <td v-if="eIndex === 0" :rowspan="channel.displayedErrors.length" :class="{
                  'channel-name': true,
                  'channel-name-last': cIndex === item.channels.length - 1
                }"
                @click.stop="toggleSingleChannel(channel, item)">
                  <div class="name-container">
                    <span>{{ channel.channel_name }}</span>
                    <div class="name-right">
                      <!-- Use the reusable ChannelColorPicker component -->
                      <ChannelColorPicker 
                        :color="channel.color" 
                        :predefineColors="predefineColors" 
                        @change="setSingleChannelColor(channel)" 
                        @update:color="channel.color = $event"
                        :shotNumber="channel.shot_number"
                        :channelName="channel.channel_name"
                        class="channel-color-picker" 
                      />
                      <el-checkbox v-model="channel.checked" @change="updateChannelTypeCheckbox(item)"
                        class="checkbox-margin"></el-checkbox>
                    </div>
                  </div>
                  <el-tag type="info" effect="plain" class="shot-number-tag">
                    {{ channel.shot_number }}
                  </el-tag>
                  <div class="show-more-container">
                    <el-button link @click.stop="toggleShowAllErrors(channel)">
                      {{ channel.showAllErrors ? '全部收起' : '展开全部异常类别' }}
                      <span v-if="!channel.showAllErrors && hiddenErrorsCount(channel) > 0" style="margin-left: 5px;">({{
                        hiddenErrorsCount(channel) }})</span>
                    </el-button>
                  </div>
                </td>

                <!-- Error Column -->
                <td :class="{
                  'error-column': true,
                  'error-last':
                    eIndex === channel.displayedErrors.length - 1 &&
                    cIndex !== item.channels.length - 1
                }"
                @click.stop="toggleSingleChannel(channel, item)">
                  <span :title="error.error_name">
                    {{ formatError(error.error_name) }}
                  </span>
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
import { ref, onMounted, computed, onUnmounted, watch } from 'vue'
import { useStore } from 'vuex'
import ChannelColorPicker from './ChannelColorPicker.vue'
import { Loading } from '@element-plus/icons-vue'

const store = useStore()
const loading = ref(false)
const displayedData = computed(() => store.getters.getDisplayedData)
const selectedChannels = computed(() => store.state.selectedChannels)

// 监听每个通道类别的选中状态
watch(displayedData, (newData) => {
  if (newData) {
    newData.forEach(item => {
      if (item && item.channels) {
        // 监听通道类别的选中状态变化
        watch(() => item.checked, (newChecked) => {
          if (item.channels) {
            item.channels.forEach(channel => {
              channel.checked = newChecked;
            });
            updateSelectedChannels();
          }
        });

        // 监听每个通道的选中状态变化
        item.channels.forEach(channel => {
          watch(() => channel.checked, () => {
            if (item.channels) {
              const allChecked = item.channels.every(ch => ch.checked);
              item.checked = allChecked;
              updateSelectedChannels();
            }
          });
        });
      }
    });
  }
}, { immediate: true, deep: true });

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

// 监听数据变化
watch(
  () => displayedData.value,
  (newData) => {
    if (newData && Array.isArray(newData)) {
      // 初始化新加载数据的复选框状态
      newData.forEach(item => {
        if (item.channels) {
          // 确保每个 item 有 checked 属性
          if (!('checked' in item)) {
            item.checked = false;
          }
          // 确保每个 channel 有 checked 属性
          item.channels.forEach(channel => {
            if (!('checked' in channel)) {
              channel.checked = false;
            }
            // 确保每个 channel 有 displayedErrors 属性
            if (!channel.displayedErrors) {
              channel.displayedErrors = channel.errors.slice(0, 1);
            }
            // 确保每个 channel 有 showAllErrors 属性
            if (!('showAllErrors' in channel)) {
              channel.showAllErrors = false;
            }
          });
          // 检查是否所有通道都被选中
          const allChecked = item.channels.every(channel => channel.checked);
          // 更新通道类型的复选框状态
          item.checked = allChecked;
        }
      });
      updateSelectedChannels();
    }
  },
  { deep: true }
);

// 修改对 selectedChannels 的深度监听
watch(selectedChannels, (newSelectedChannels) => {
  if (!displayedData.value) return;
  
  newSelectedChannels.forEach(selectedChannel => {
    // 遍历所有通道类别
    displayedData.value.forEach(item => {
      // 在每个类别中查找对应的通道
      const channel = item.channels.find(ch => 
        ch.channel_name === selectedChannel.channel_name && 
        ch.shot_number === selectedChannel.shot_number
      );
      
      // 如果找到对应通道且颜色不同，则只更新通道的颜色
      if (channel && channel.color !== selectedChannel.color) {
        channel.color = selectedChannel.color;
      }
    });
  });
}, { deep: true });

// 初始化组件
onMounted(async () => {
  // 获取父级的 el-scrollbar__wrap 元素并添加滚动监听
  const parentScrollbar = document.querySelector('.el-scrollbar__wrap');
  if (parentScrollbar) {
    parentScrollbar.addEventListener('scroll', handleParentScroll);
  }
  
  // 如果还没有数据，初始化加载
  if (!displayedData.value || displayedData.value.length === 0) {
    await store.dispatch('loadMoreData', true);
  }
  
  // 初始化复选框状态
  if (displayedData.value) {
    displayedData.value.forEach(item => {
      if (item.channels) {
        // 确保每个 item 有 checked 属性
        if (!('checked' in item)) {
          item.checked = false;
        }
        // 确保每个 channel 有 checked 属性
        item.channels.forEach(channel => {
          if (!('checked' in channel)) {
            channel.checked = false;
          }
          // 确保每个 channel 有 displayedErrors 属性
          if (!channel.displayedErrors) {
            channel.displayedErrors = channel.errors.slice(0, 1);
          }
          // 确保每个 channel 有 showAllErrors 属性
          if (!('showAllErrors' in channel)) {
            channel.showAllErrors = false;
          }
        });
        const allChecked = item.channels.every(channel => channel.checked);
        item.checked = allChecked;
      }
    });
    updateSelectedChannels();
  }
});

onUnmounted(() => {
  // 组件卸载时移除滚动监听
  const parentScrollbar = document.querySelector('.el-scrollbar__wrap');
  if (parentScrollbar) {
    parentScrollbar.removeEventListener('scroll', handleParentScroll);
  }
});

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

const dataLoaded = ref(false)

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
}

const hiddenErrorsCount = (channel) => {
  return channel.errors.length - channel.displayedErrors.length
}

const setChannelColor = (item) => {
  if (item && item.channels) {
    item.channels.forEach((channel) => {
      channel.color = item.color;
    });
    updateSelectedChannels();
  }
};

const setSingleChannelColor = (channel) => {
  if (channel) {
    updateSelectedChannels();
  }
};


const updateSelectedChannels = () => {
    if (!displayedData.value) {
        return;
    }
    const selected = displayedData.value.flatMap(item =>
        item.channels
            .filter(channel => channel.checked)
            .map(channel => ({
                channel_key: channel.channel_key,
                channel_name: channel.channel_name,
                shot_number: channel.shot_number,
                color: channel.color,
                channel_type: item.channel_type,
                errors: channel.errors.map(error => ({
                    error_key: error.error_key,
                    error_name: error.error_name,
                    color: error.color
                }))
            }))
    );

    store.commit('updateSelectedChannels', selected);
};


const toggleChannelCheckboxes = (item) => {
    if (item && Array.isArray(item.channels)) {
        // 点击单元格时，先切换通道类别的选中状态
        item.checked = !item.checked;
        
        // 获取通道类别复选框的新状态
        const newState = item.checked;
        
        // 更新所有通道的选中状态
        item.channels.forEach((channel) => {
            channel.checked = newState;
        });
        
        // 立即更新 Vuex store
        updateSelectedChannels();
    }
};

const updateChannelTypeCheckbox = (item) => {
    if (!item || !item.channels) {
        console.error('Invalid item or channels:', item);
        return;
    }

    // 检查是否所有通道都被选中
    const allChecked = item.channels.every((channel) => channel.checked);
    
    // 更新通道类别复选框状态
    item.checked = allChecked;
    
    // 立即更新 Vuex store
    updateSelectedChannels();
};

const toggleShowAllErrors = (channel) => {
  channel.showAllErrors = !channel.showAllErrors;
  if (channel.showAllErrors) {
    channel.displayedErrors = channel.errors;
  } else {
    channel.displayedErrors = channel.errors.slice(0, 1);
  }
};

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

const toggleSingleChannel = (channel, item) => {
  if (channel) {
    channel.checked = !channel.checked;
    updateChannelTypeCheckbox(item);
  }
};
</script>

<style scoped>
.channel-list {
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

.channel-name {
  width: 45%;
  vertical-align: top;
  text-align: left;
  border-bottom: 1px solid #eee;
  font-family: inherit;
  background-color: #fff;
}

.name-container {
  display: flex;
  flex-wrap: nowrap;
  justify-content: space-between;
  align-items: flex-start;
  font-family: inherit;
  margin-bottom: 8px;
  width: 100%;
}

.name-container span {
  word-wrap: break-word;
  white-space: normal;
  flex: 1;
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
  white-space: normal;
  border-bottom: none;
  background-color: #fff;
}

.error-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.error-container span {
  word-wrap: break-word;
  white-space: normal;
  flex: 1;
}

.error-last {
  border-bottom: 1px solid #eee;
}

.checkbox-margin {
  margin-left: 8px;
  flex-shrink: 0;
}

.type-header {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
}

.type-header span {
  font-size: 14px;
  word-wrap: break-word;
  white-space: normal;
}

.channel-name-last {
  border-bottom: none;
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

.hidden-errors-count {
  color: #888;
  font-size: 12px;
  margin-left: 4px;
}

/* Remove arrows from color picker */
:deep(.is-icon-arrow-down) {
  display: none !important;
}

/* Remove outer border from color picker trigger */
:deep(.el-color-picker__trigger) {
  border: none;
}

/* Make color swatches circular */
:deep(.el-color-picker__color) {
  border-radius: 50%;
}

/* Make color picker sliders and selectors circular */
:deep(.el-color-dropdown__main-wrapper .el-color-alpha-slider__thumb,
  .el-color-dropdown__main-wrapper .el-color-hue-slider__thumb) {
  width: 14px;
  height: 14px;
  border-radius: 50%;
}

/* Make predefined color selectors circular */
:deep(.el-color-predefine__color-selector) {
  border-radius: 50%;
}

:deep(.el-color-picker__color-inner) {
  border-radius: 50%;
}

:deep(.el-color-predefine__color-selector)::before {
  border-radius: 50%;
}

.loading-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px;
  color: #909399;
}
</style>
