<template>
  <div class="channel-list">
    <div v-for="(item, index) in displayedData" :key="index" class="card">
      <table class="channel-table">
        <tbody>
          <template v-for="(channel, cIndex) in item.channels" :key="`channel-${cIndex}`">
            <tr v-for="(error, eIndex) in channel.displayedErrors" :key="`error-${cIndex}-${eIndex}`">
              <!-- Channel Type Cell -->
              <td v-if="eIndex === 0 && cIndex === 0"
                :rowspan="item.channels.reduce((total, c) => total + c.displayedErrors.length, 0)" class="channel-type">
                <span :title="item.channel_type">{{ formatChannelType(item.channel_type) }}</span>
                <div class="type-header">
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
                    class="checkbox-margin"></el-checkbox>
                </div>
              </td>
              <td v-if="eIndex === 0" :rowspan="channel.displayedErrors.length" :class="{
                'channel-name': true,
                'channel-name-last': cIndex === item.channels.length - 1
              }">
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
                  <el-button link @click="toggleShowAllErrors(channel)">
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
              }">
                <span :title="error.error_name">
                  {{ formatError(error.error_name) }}
                </span>
                <!-- Optional: Additional Color Picker for Errors -->
                <!-- 
                  <el-color-picker v-model="error.color" @change="setErrorColor(channel, error)"
                    class="error-color-picker" show-alpha size="small" :predefine="predefineColors" />
                  -->
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
import { ref, onMounted, computed, onUnmounted, watch } from 'vue'
import { useStore } from 'vuex'
import ChannelColorPicker from './ChannelColorPicker.vue'
import { Loading } from '@element-plus/icons-vue'

const store = useStore()
const loading = ref(false)
const displayedData = computed(() => store.getters.getDisplayedData)

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
          // 检查是否有选中的通道
          const hasCheckedChannels = item.channels.some(channel => channel.checked);
          // 更新通道类型的复选框状态
          item.checked = hasCheckedChannels;
        }
      });
      updateSelectedChannels();
    }
  },
  { deep: true }
);

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
  const decodedName = decodeURIComponent(escape(name));
  if (decodedName.length > 8) {
    return decodedName.slice(0, 8) + '...';
  }
  return decodedName;
}

const hiddenErrorsCount = (channel) => {
  return channel.errors.length - channel.displayedErrors.length
}

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
});

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
  if (item && item.channels) {
    item.channels.forEach((channel) => {
      channel.checked = item.checked;
    });
    updateSelectedChannels();
  }
};

const updateChannelTypeCheckbox = (item) => {
  if (!item || !item.channels) {
    console.error('Invalid item or channels:', item);
    return;
  }

  item.checked = item.channels.every(channel => channel.checked);
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
  const decodedName = decodeURIComponent(escape(name));
  if (decodedName.length > 8) {
    return decodedName.slice(0, 8) + '...';
  }
  return decodedName;
};
</script>

<style scoped>
/* Existing styles remain unchanged */

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
  font-family: inherit;
}

.channel-name {
  width: 40%;
  vertical-align: middle;
  text-align: center;
  border-bottom: 0.5px solid #ddd;
  font-family: inherit;
}

.name-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-family: inherit;
}

.name-right {
  display: flex;
  align-items: center;
}

.error-column {
  width: 30%;
  vertical-align: middle;
  text-align: center;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  border-bottom: none;
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
  margin-top: 5px;
}

.channel-name-last {
  border-bottom: none;
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

.hidden-errors-count {
  text-align: center;
  color: #888;
  margin-top: 2px;
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

.channel-list {
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
