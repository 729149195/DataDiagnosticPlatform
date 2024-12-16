<template>
  <div v-for="item in data" :key="item.id" class="card">
    <table class="channel-table">
      <tbody>
        <template v-for="(channel, channelIndex) in item.channels" :key="channel.channel_key">
          <tr v-for="(error, errorIndex) in channel.displayedErrors" :key="error.error_key">

            <!-- 通道类别单元格 -->
            <td v-if="channelIndex === 0 && errorIndex === 0" :rowspan="computeTotalDisplayedErrors(item)"
              class="channel-type">
              <span>{{ item.channel_type }}</span>
              <div class="type-header">
                <!-- <el-color-picker v-model="item.color" @change="setChannelColor(item)" class="category-color-picker"
                  size="small" show-alpha :predefine="predefineColors" /> -->
                <el-checkbox v-model="item.checked" @change="toggleChannelCheckboxes(item)"
                  class="checkbox-margin"></el-checkbox>
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
                  <el-checkbox v-model="channel.checked" @change="clearChannelTypeCheckbox(item)"
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
</template>


<script setup>
import { shallowRef, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { useStore } from 'vuex';
import { ElMessage } from 'element-plus';
import ErrorColorPicker from './ErrorColorPicker.vue'

// Vuex store
const store = useStore();

// 从 Vuex 获取数据
const data = computed(() => store.getters.getStructTree);

// 预定义颜色
const predefineColors = shallowRef([
  '#000000', '#4169E1', '#DC143C', '#228B22', '#FF8C00',
  '#800080', '#FF1493', '#40E0D0', '#FFD700', '#8B4513',
  '#2F4F4F', '#1E90FF', '#32CD32', '#FF6347', '#DA70D6',
  '#191970', '#FA8072', '#6B8E23', '#6A5ACD', '#FF7F50',
  '#4682B4'
]);

const dataLoaded = shallowRef(false);

// 存储原始颜色，以便在卸载组件时恢复
const originalColors = shallowRef({});

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
  return (
    channel.displayedErrors[0] === channel.errors[0] &&
    item.channels[0] === channel
  );
};

// 判断是否是第一个异常
const isFirstError = (channel, item) => {
  return channel.displayedErrors[0] === channel.errors[0];
};

// 格式化异常名称，过长则截断
const formatError = (name) => {
  return name.length > 9 ? `${name.slice(0, 9)}...` : name;
};

// 计算隐藏的异常数量
const hiddenErrorsCount = (channel) => {
  return channel.errors.length - channel.displayedErrors.length;
};

// 更新选中的通道并同步到 Vuex Store
const updateSelectedChannels = () => {
  if (!data.value || !Array.isArray(data.value)) return;

  const selected = data.value.flatMap(item => {
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
  if (!data.value || !Array.isArray(data.value)) return;
  
  // 使用 requestAnimationFrame 分批处理数据
  const processChannels = (startIndex = 0) => {
    const BATCH_SIZE = 10;
    const items = data.value;
    
    for (let i = startIndex; i < Math.min(startIndex + BATCH_SIZE, items.length); i++) {
      const item = items[i];
      if (!item || !Array.isArray(item.channels)) continue;
      
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
    }
    
    if (startIndex + BATCH_SIZE < items.length) {
      requestAnimationFrame(() => processChannels(startIndex + BATCH_SIZE));
    }
  };
  
  requestAnimationFrame(() => processChannels());
};

// 监听数据变化
watch(
  () => data.value,
  (newData) => {
    if (newData && Array.isArray(newData)) {
      dataLoaded.value = true;
      initializeData();
      updateSelectedChannels();
    }
  },
  { immediate: true }
);

onMounted(() => {
  if (data.value && Array.isArray(data.value)) {
    dataLoaded.value = true;
    initializeData();
    updateSelectedChannels();
  }
});

onBeforeUnmount(() => {
  revertColors();
  updateSelectedChannels();
});

// 恢复通道的原始颜色
const revertColors = () => {
  data.value.forEach(item => {
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
    item.channels.forEach(channel => {
      channel.checked = item.checked;
    });
    updateSelectedChannels();
  }
};

// 更新通道类别的复选框状态
const clearChannelTypeCheckbox = (item) => {
  if (item && item.channels) {
    const allChecked = item.channels.every(channel => channel.checked);
    item.checked = allChecked;
    updateSelectedChannels();
  }
};

// 切换显示所有异常类别
const toggleShowAllErrors = (channel) => {
  channel.showAllErrors = !channel.showAllErrors;
  channel.displayedErrors = channel.showAllErrors ? [...channel.errors] : channel.errors.slice(0, 1);
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
}

.channel-table td {
  padding: 8px;
  vertical-align: top;
  /* Align top */
  text-align: center;
}

.channel-type {
  width: 20%;
  vertical-align: top;
  text-align: center;
}

.channel-name {
  width: 40%;
  vertical-align: middle;
  text-align: center;
  border-bottom: 0.5px solid #ddd;
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
</style>
