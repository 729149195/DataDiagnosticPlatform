<template>
  <div class="exception-list">
    <div v-for="item in displayedData" :key="item.id" class="card">
      <table class="channel-table">
        <tbody>
          <template v-for="(channel, channelIndex) in item.channels" :key="channel.channel_key">
            <tr v-for="(error, errorIndex) in channel.displayedErrors" :key="error.error_key">

              <!-- 通道类别单元格 -->
              <td
                class="channel-type"
                :rowspan="computeTotalDisplayedErrors(item)"
                v-if="channelIndex === 0 && errorIndex === 0"
              >
                <div class="type-header">
                  <span :title="item.channel_type">{{ formatChannelType(item.channel_type) }}</span>
                  <el-checkbox
                    v-model="item.checked"
                    @change="toggleChannelCheckboxes(item)"
                    class="checkbox-margin"
                  />
                </div>
              </td>

              <!-- 通道名称单元格 -->
              <td v-if="errorIndex === 0" :rowspan="channel.displayedErrors.length" :class="{
                'channel-name': true,
                'channel-name-last': isLastChannel(item.channels, channel),
              }">
                <div class="name-container">
                  <span>{{ channel.channel_name }}</span>
                  <div class="name-right">
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
                    <span v-if="!channel.showAllErrors && hiddenErrorsCount(channel) > 0" style="margin-left: 5px;">
                      ({{ hiddenErrorsCount(channel) }})
                    </span>
                  </el-button>
                </div>
              </td>

              <!-- 异常类别单元格 -->
              <td :class="{
                'error-column': true,
                'error-last': isLastError(channel, error) && !isLastChannel(item.channels, channel),
              }">
                <div class="error-container">
                  <span :title="error.error_name">
                    {{ formatError(error.error_name) }}
                  </span>
                  <ErrorColorPicker
                    :color="error.color"
                    :predefine="predefineColors"
                    :error-name="error.error_name"
                    :shot-number="channel.shot_number"
                    :channel-name="channel.channel_name"
                    @change="setErrorColor(channel, error)"
                    @update:color="error.color = $event"
                  />
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
import { ref, onMounted, onUnmounted, computed, watch } from 'vue';
import { useStore } from 'vuex';
import { ElMessage } from 'element-plus';
import ErrorColorPicker from './ErrorColorPicker.vue'
import { Loading } from '@element-plus/icons-vue'

// Vuex store
const store = useStore();
const loading = ref(false);

// 从 Vuex 获取数据
const displayedData = computed(() => store.getters.getDisplayedData);

// 预定义颜色
const predefineColors = ref([
  '#000000', '#4169E1', '#DC143C', '#228B22', '#FF8C00',
  '#800080', '#FF1493', '#40E0D0', '#FFD700', '#8B4513',
  '#2F4F4F', '#1E90FF', '#32CD32', '#FF6347', '#DA70D6',
  '#191970', '#FA8072', '#6B8E23', '#6A5ACD', '#FF7F50',
  '#4682B4'
]);

// 存储原始颜色，以便在卸载组件时恢复
const originalColors = ref({});

// 辅助方法

// 计算所有显示的异常数量，用于 rowspan
const computeTotalDisplayedErrors = (item) => {
  return item.channels.reduce((total, c) => total + c.displayedErrors.length, 0);
};


// 判断是否是最后一个通道
const isLastChannel = (channels, channel) => {
  return channels[channels.length - 1] === channel;
};

// 判断是否是最后一个异常
const isLastError = (channel, error) => {
  return channel.displayedErrors[channel.displayedErrors.length - 1] === error;
};

// 判断是否是第一个异常且第一个通道
const isFirstErrorAndFirstChannel = (channel, item) => {
  return item.channels[0] === channel && channel.displayedErrors[0] === channel.displayedErrors[0];
};

// 判断是否是第一个异常
const isFirstError = (channel, item) => {
  return channel.displayedErrors[0] === channel.errors[0];
};

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
    if (decodedName.length > 8) {
      return decodedName.slice(0, 8) + '...';
    }
    return decodedName;
  } catch (err) {
    console.warn('Error formatting channel type:', err);
    return name;
  }
};

// 格式化异常名称，过长则截断
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
    if (decodedName.length > 8) {
      return decodedName.slice(0, 8) + '...';
    }
    return decodedName;
  } catch (err) {
    console.warn('Error formatting name:', err);
    return name;
  }
};

// 计算隐藏的异常数量
const hiddenErrorsCount = (channel) => {
  return channel.errors.length - channel.displayedErrors.length;
};

// 更新选中的通道并同步到 Vuex Store
const updateSelectedChannels = () => {
  if (!displayedData.value || !Array.isArray(displayedData.value)) return;

  const selected = displayedData.value.flatMap(item => {
    if (!item || !Array.isArray(item.channels)) return [];
    
    return item.channels
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
      }));
  });

  store.commit('updateSelectedChannels', selected);
};

// 初始化数据：设置默认颜色和 displayedErrors
const initializeData = () => {
  if (!displayedData.value || !Array.isArray(displayedData.value)) return;
  
  displayedData.value.forEach(item => {
    if (!item || !Array.isArray(item.channels)) return;
    
    item.channels.forEach(channel => {
      if (!channel || !Array.isArray(channel.errors)) return;
      
      // 保存原始颜色
      if (!originalColors.value[channel.channel_key]) {
        originalColors.value[channel.channel_key] = channel.color;
      }

      // 设置默认颜色（如果需要）
      if (!channel.color) {
        channel.color = '#D3D3D3';
      }

      // 初始化 displayedErrors
      if (!channel.displayedErrors) {
        channel.displayedErrors = channel.errors.slice(0, 1);
      }

      // 初始化每个异常的 color 属性
      channel.errors.forEach(error => {
        if (!error.hasOwnProperty('color')) {
          error.color = '#000000'; // 设置默认颜色
        }
      });
    });
  });
};

// 监听数据变化
watch(
  () => displayedData.value,
  (newData) => {
    if (newData && Array.isArray(newData)) {
      initializeData();
      updateSelectedChannels();
    }
  },
  { immediate: true }
);

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

// 恢复通道的原始颜色
const revertColors = () => {
  displayedData.value.forEach(item => {
    item.channels.forEach(channel => {
      const originalColor = originalColors.value[channel.channel_key];
      if (originalColor) {
        channel.color = originalColor;
      }
    });
  });
};

// 设置通道类别的颜色
const setChannelColor = (item) => {
  if (item && item.channels) {
    item.channels.forEach(channel => {
      channel.color = item.color;
    });
    updateSelectedChannels();
  }
};

// 设置单个通道的颜色
const setSingleChannelColor = (channel) => {
  if (channel) {
    // 如果需要，可以在这里添加颜色验证逻辑
    updateSelectedChannels();
  }
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
    const someChecked = item.channels.some((channel) => channel.checked);
    
    // 如果所有通道都选中,则通道类别也选中
    // 如果部分通道选中,则通道类别不选中
    // 如果没有通道选中,则通道类别不选中
    item.checked = allChecked;
    
    updateSelectedChannels();
};

// 切换显示所有异常类别
const toggleShowAllErrors = (channel) => {
  if (!channel || !Array.isArray(channel.errors)) return;
  
  // 切换显示状态
  channel.showAllErrors = !channel.showAllErrors;
  
  // 根据显示状态设置要显示的异常
  if (channel.showAllErrors) {
    // 展开时，保持第一个异常不变，添加其余异常
    const firstError = channel.displayedErrors[0];
    const remainingErrors = channel.errors.filter(error => error !== firstError);
    channel.displayedErrors = [firstError, ...remainingErrors];
  } else {
    // 收起时，只保留第一个异常
    channel.displayedErrors = [channel.displayedErrors[0]];
  }
};

const setErrorColor = (channel, error) => {
  if (channel && error) {
    updateSelectedChannels();
  }
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
  margin: 0;
}

.type-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
}

.type-header span {
  font-size: 14px;
  word-break: break-all;
  text-align: center;
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

/* 去除颜色选择器里面的箭头 */
:deep(.is-icon-arrow-down) {
  display: none !important;
}

/* 去除颜色选择器最外层的边框 */
:deep(.el-color-picker__trigger) {
  border: none;
}

/* 将颜色色块变为圆形 */
:deep(.el-color-picker__color) {
  border-radius: 50%;
}

/* 将下拉面板中的选色区域的选框变为圆形 */
:deep(.el-color-dropdown__main-wrapper .el-color-alpha-slider__thumb,
  .el-color-dropdown__main-wrapper .el-color-hue-slider__thumb) {
  width: 14px;
  height: 14px;
  border-radius: 50%;
}

/* 将下拉面板中的预设颜色方块变为圆形 */
:deep(.el-color-predefine__color-selector) {
  border-radius: 50%;
}

:deep(.el-color-picker__color-inner) {
  border-radius: 50%;
}

:deep(.el-color-predefine__color-selector)::before {
  border-radius: 50%;
}

/* 添加新的样式 */
:deep(.error-color-picker-dropdown) {
  .el-color-dropdown__btns {
    &::before {
      content: "正在修改异常颜色";
      display: block;
      text-align: center;
      padding: 8px 0;
      color: #606266;
      font-size: 14px;
    }
  }
}

.exception-list {
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

.error-container {
  display: flex;
  justify-content: center;
  align-items: center;
  font-family: inherit;
}
</style>
