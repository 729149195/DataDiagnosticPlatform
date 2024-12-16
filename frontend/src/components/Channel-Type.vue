<template>
  <el-scrollbar height="55vh" :always="false" @scroll="handleScroll" ref="scrollbarRef">
    <div v-for="(item, index) in visibleData" :key="index" class="card">
      <table class="channel-table">
        <tbody>
          <template v-for="(channel, cIndex) in item.channels" :key="`channel-${cIndex}`">
            <tr v-for="(error, eIndex) in channel.displayedErrors" :key="`error-${cIndex}-${eIndex}`">
              <!-- Channel Type Cell -->
              <td v-if="eIndex === 0 && cIndex === 0"
                :rowspan="item.channels.reduce((total, c) => total + c.displayedErrors.length, 0)" class="channel-type">
                <span>{{ item.channel_type }}</span>
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
    <div v-if="loading" class="loading-more">
      加载更多...
    </div>
  </el-scrollbar>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue'
import { useStore } from 'vuex'
import ChannelColorPicker from './ChannelColorPicker.vue' // Import the new component

const store = useStore()

const INITIAL_LOAD_COUNT = 1;
const BATCH_SIZE = 1;

const visibleData = ref([]);
const currentIndex = ref(0);
const loading = ref(false);
const scrollbarRef = ref(null);

const rawData = computed(() => store.getters.getStructTree);

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
  if (name.length > 8) {
    return name.slice(0, 8) + '...'
  }
  return name
}

const hiddenErrorsCount = (channel) => {
  return channel.errors.length - channel.displayedErrors.length
}

const initializeVisibleData = () => {
  if (!rawData.value) return;
  
  visibleData.value = rawData.value.slice(0, INITIAL_LOAD_COUNT);
  currentIndex.value = INITIAL_LOAD_COUNT;
};

const handleScroll = async (e) => {
  if (loading.value) return;
  
  // 获取 scrollbar 实例的 wrap 元素
  const wrap = scrollbarRef.value?.wrap;
  if (!wrap) return;
  
  const { scrollTop, clientHeight, scrollHeight } = wrap;
  
  if (scrollHeight - scrollTop - clientHeight < 100 && currentIndex.value < rawData.value.length) {
    loading.value = true;
    
    await nextTick();
    
    const nextBatch = rawData.value.slice(
      currentIndex.value,
      currentIndex.value + BATCH_SIZE
    );
    
    visibleData.value = [...visibleData.value, ...nextBatch];
    currentIndex.value += BATCH_SIZE;
    
    loading.value = false;
  }
};

watch(
  () => rawData.value,
  () => {
    initializeVisibleData();
  },
  { immediate: true }
);

// 定义 emit
const emit = defineEmits(['loaded'])

onMounted(async () => {
  await initializeVisibleData();
  emit('loaded');
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
  if (!rawData.value) {
    return;
  }
  const selected = rawData.value.flatMap(item =>
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


const toggleChannelCheckboxes = (item) => {
  item.channels.forEach((channel) => {
    channel.checked = item.checked
  })
  updateSelectedChannels()
}

const updateChannelTypeCheckbox = (item) => {
  if (!item || !item.channels) {
    console.error('Invalid item or channels:', item)
    return
  }

  item.checked = item.channels.every(channel => channel.checked)
  updateSelectedChannels()
}

const toggleShowAllErrors = (channel) => {
  channel.showAllErrors = !channel.showAllErrors
  if (channel.showAllErrors) {
    channel.displayedErrors = channel.errors
  } else {
    channel.displayedErrors = channel.errors.slice(0, 1)
  }
}
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

.loading-more {
  text-align: center;
  padding: 10px 0;
  color: #909399;
  font-size: 14px;
}
</style>
