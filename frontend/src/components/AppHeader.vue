<template>
  <el-header class="header">
    <div shadow="never">
      <el-button class="anay" :class="{ selected: selectedButton === 'anay' }" :type="selectedButton === 'anay' ? 'primary' : 'default'" size="large" @click="selectButton('anay')">
        <el-icon :size="20">
          <DataAnalysis />
        </el-icon>
        <span v-if="selectedButton === 'anay'">实验数据分析</span>
      </el-button>
      <el-button class="channel" :class="{ selected: selectedButton === 'channel' }" :type="selectedButton === 'channel' ? 'primary' : 'default'" size="large" @click="selectButton('channel')">
        <el-icon :size="20">
          <Odometer />
        </el-icon>
        <span v-if="selectedButton === 'channel'">通道分析模块</span>
      </el-button>
    </div>
    <div class="monitor-status-wrapper">
      <MonitorStatus />
    </div>
    <el-dropdown trigger="click">
      <el-avatar :style="avatarStyle" size="default">{{ avatarText }}</el-avatar>
      <template #dropdown>
        <el-dropdown-menu class="user-dropdown">
          <div class="user-info">
            <div class="user-avatar">
              <el-avatar :style="avatarStyle" size="large">{{ avatarText }}</el-avatar>
              <div class="user-name">{{ person }}</div>
            </div>
            <div class="user-detail">
              <div class="detail-item">
                <el-icon>
                  <User />
                </el-icon>
                <span class="label">身份</span>
                <span class="value">{{ authorityLabel }}</span>
              </div>
            </div>
          </div>
          <el-dropdown-item divided class="info" @click="viewCacheInfo">
            <el-icon style="color: #409EFF">
              <InfoFilled />
            </el-icon>
            <span>查看缓存信息</span>
          </el-dropdown-item>
          <el-dropdown-item divided class="warning" @click="clearCache">
            <el-icon>
              <Delete />
            </el-icon>
            <span>清空缓存</span>
          </el-dropdown-item>
          <el-dropdown-item divided class="danger" @click="logout">
            <el-icon>
              <SwitchButton />
            </el-icon>
            <span>退出登录</span>
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </el-header>

  <!-- 缓存信息对话框 -->
  <Teleport to="body">
    <el-dialog v-model="cacheInfoDialogVisible" title="缓存信息" width="80%" :close-on-click-modal="false" :close-on-press-escape="true" destroy-on-close append-to-body :modal-class="loadingCache ? 'loading-dialog-mask' : ''" top="5vh">
      <div v-if="cacheKeys.length === 0" class="empty-cache">
        <el-empty description="暂无缓存数据" v-loading="loadingCache" element-loading-text="加载缓存数据中..." />
      </div>
      <div v-else>
        <!-- 通道数据表格 -->
        <div class="table-divider">
          <span>通道数据</span>
        </div>
        <el-table :data="nonErrorCacheKeys" style="width: 100%" max-height="250px" border v-loading="loadingCache" :class="{ 'table-loading': loadingCache }" @selection-change="handleSelectionChange">
          <el-table-column type="selection" width="55" />
          <el-table-column type="expand">
            <template #default="props">
              <div class="cache-detail">
                <el-descriptions :column="2" border>
                  <el-descriptions-item label="通道名称">{{ props.row.details.channel_number }}</el-descriptions-item>
                  <el-descriptions-item label="X轴单位 / Y轴单位">{{ props.row.details.X_unit }} / {{ props.row.details.Y_unit }}</el-descriptions-item>
                  <el-descriptions-item label="原始频率">{{ formatFrequency(props.row.details.originalFrequency) }}</el-descriptions-item>
                  <el-descriptions-item label="数据点数量">{{ props.row.details.originalDataPoints || props.row.dataPoints }}</el-descriptions-item>
                </el-descriptions>
              </div>
            </template>
          </el-table-column>
          <el-table-column type="index" label="序号" width="60" />
          <el-table-column prop="key" label="缓存键" min-width="180" show-overflow-tooltip />
          <el-table-column label="数据类型" width="100">
            <template #default="scope">
              <el-tag type="success" effect="plain">通道数据</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="timestamp" label="缓存时间" width="180">
            <template #default="scope">
              {{ new Date(scope.row.timestamp).toLocaleString() }}
            </template>
          </el-table-column>
          <el-table-column prop="size" label="数据大小" width="100">
            <template #default="scope">
              {{ formatSize(scope.row.size) }}
            </template>
          </el-table-column>
          <el-table-column prop="dataPoints" label="数据点数" width="100">
            <template #default="scope">
              {{ scope.row.dataPoints || '-' }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="scope">
              <el-button type="danger" size="small" @click="deleteChannelCache(scope.row.key)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 错误数据表格 -->
        <div v-if="errorCacheKeys.length > 0" class="error-table-section">
          <div class="table-divider">
            <span>异常标注数据</span>
          </div>
          <el-table :data="errorCacheKeys" style="width: 100%" max-height="250px" border v-loading="loadingCache" :class="{ 'table-loading': loadingCache }" @selection-change="handleErrorSelectionChange">
            <el-table-column type="selection" width="55" />
            <el-table-column type="index" label="序号" width="60" />
            <el-table-column prop="key" label="缓存键" min-width="180" show-overflow-tooltip />
            <el-table-column label="数据类型" width="100">
              <template #default="scope">
                <el-tag type="danger" effect="plain">异常标注</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="timestamp" label="缓存时间" width="180">
              <template #default="scope">
                {{ new Date(scope.row.timestamp).toLocaleString() }}
              </template>
            </el-table-column>
            <el-table-column prop="size" label="数据大小" width="100">
              <template #default="scope">
                {{ formatSize(scope.row.size) }}
              </template>
            </el-table-column>
            <el-table-column label="操作" width="120">
              <template #default="scope">
                <el-button type="danger" size="small" @click="deleteChannelCache(scope.row.key)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <span class="cache-summary">
            总缓存数: {{ cacheKeys.length }} |
            通道数据: {{ nonErrorCacheKeys.length }} |
            异常标注: {{ errorCacheKeys.length }} |
            总大小: {{ formatSize(getTotalCacheSize()) }}
          </span>
          <div>
            <el-button @click="cacheInfoDialogVisible = false">关闭</el-button>
            <el-button type="warning" @click="deleteSelectedCache" :disabled="!hasSelectedCache">
              删除选中 ({{ selectedCacheKeys.length }})
            </el-button>
            <el-button type="primary" @click="refreshCacheInfo" :loading="loadingCache">
              刷新
            </el-button>
          </div>
        </span>
      </template>
    </el-dialog>
  </Teleport>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue';
import { useStore } from 'vuex';
import { useRouter } from 'vue-router';
import { User, SwitchButton, Delete, InfoFilled, DataAnalysis, Odometer, Timer } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import indexedDBService from '@/services/indexedDBService';
import MonitorStatus from '@/components/MonitorStatus.vue'; // 引入监控状态组件

const store = useStore()
const router = useRouter()
const selectedButton = ref('anay');


// 添加缓存服务性能优化
let isCachePreloading = false;
// 在应用空闲时预加载缓存数据
const preloadCacheData = () => {
  if (isCachePreloading) return;

  isCachePreloading = true;

  // 使用requestIdleCallback在浏览器空闲时预加载缓存数据
  // 如果浏览器不支持requestIdleCallback则使用setTimeout
  const requestIdleCallbackFn = window.requestIdleCallback ||
    ((cb) => setTimeout(cb, 1000));

  requestIdleCallbackFn(() => {
    // 只预取缓存键，不加载全部数据
    indexedDBService.getAllKeys()
      .then(keys => {
        // 存储缓存键以便后续使用
        cacheKeysIndex.value = keys;
        // console.log(`预加载了 ${keys.length} 个缓存键`);
      })
      .catch(err => {
        console.warn('预加载缓存键失败:', err);
      })
      .finally(() => {
        isCachePreloading = false;
      });
  });
};

// 预加载缓存索引，但不加载全部数据
const cacheKeysIndex = ref([]);

// 接收父组件传递的初始按钮状态
const props = defineProps({
  initialButton: {
    type: String,
    default: 'anay'
  }
});

const person = computed(() => store.state.person);
const authority = computed(() => store.state.authority);

// 检查登录状态
const checkLoginStatus = () => {
  if (!person.value) {
    router.push('/');
  }
};

// 在组件挂载时设置初始按钮状态
onMounted(() => {
  checkLoginStatus();
  // 每次挂载时都强制切换到实验数据分析模块
  selectedButton.value = 'anay';
  localStorage.setItem('selectedButton', 'anay');
  // 发出事件通知父组件按钮已更改
  emit('button-change', 'anay');

  // 预加载缓存索引
  preloadCacheData();

});

// 移除 initialButton prop 监听，因为现在总是强制设置为 'anay'

// 监听 person 的变化
watch(person, (newValue) => {
  if (!newValue) {
    // 用户登出时，重置按钮状态为实验数据分析模块
    selectedButton.value = 'anay';
    localStorage.setItem('selectedButton', 'anay');
    // 发出事件通知父组件按钮已更改
    emit('button-change', 'anay');
    router.push('/');
  }
});

const avatarText = computed(() => person.value ? person.value.charAt(0) : 'U');

const authorityLabel = computed(() => {
  return authority.value === '0' ? '查看者' : '标注者';
});

const avatarStyle = computed(() => {
  // 使用Element Plus主题蓝色系的渐变色
  const blueColors = [
    '#409EFF', // 主题蓝色
    '#337ECC', // 深蓝色
    '#66B1FF', // 浅蓝色
    '#79BBFF', // 更浅蓝色
    '#8CC5FF'  // 最浅蓝色
  ];
  const color = blueColors[authority.value % blueColors.length];
  return {
    backgroundColor: color,
    color: '#fff',
    cursor: 'pointer',
    border: '2px solid #fff',
    boxShadow: '0 2px 12px 0 rgba(64, 158, 255, 0.2)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: '600',
    fontSize: '16px',
    lineHeight: '1',
  };
});

const logout = async () => {
  // 使用新的platformLogout函数，它会处理cookie清除和页面跳转
  if (window.platformLogout) {
    await window.platformLogout();
  } else {
    // 如果authManager未加载，使用原有逻辑
    store.commit('setperson', '');
    store.commit('setauthority', 0);
    router.push('/');
  }
};

const selectButton = (button) => {
  selectedButton.value = button;
  // 发出事件通知父组件按钮已更改
  emit('button-change', button);
};

// 缓存信息相关
const cacheInfoDialogVisible = ref(false);
const cacheKeys = ref([]);
const selectedCacheKeys = ref([]);
const loadingCache = ref(false);

// 是否有选中的缓存
const hasSelectedCache = computed(() => {
  return selectedCacheKeys.value.length > 0;
});

// 删除选中的缓存
const deleteSelectedCache = async () => {
  if (selectedCacheKeys.value.length === 0) {
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedCacheKeys.value.length} 项缓存吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    // 逐个删除选中的缓存
    for (const row of selectedCacheKeys.value) {
      await indexedDBService.deleteChannelData(row.key);
      // 从Vuex中移除该缓存
      store.commit('removeChannelDataCache', row.key);
    }

    ElMessage({
      message: `已删除 ${selectedCacheKeys.value.length} 项缓存`,
      type: 'success'
    });

    // 清空选中项
    selectedCacheKeys.value = [];

    // 刷新缓存列表
    await getCacheInfo();
  } catch (error) {
    if (error === 'cancel' || error.toString().includes('cancel')) {
      return;
    }

    console.error('删除缓存失败:', error);
    ElMessage({
      message: '删除缓存失败，请重试',
      type: 'error'
    });
  }
};

// 表格选择变化事件
const handleSelectionChange = (selection) => {
  // 只保存非error项的选择
  selectedCacheKeys.value = selection;
};

// 格式化数据大小
const formatSize = (bytes) => {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

// 格式化频率显示 - 不使用缓存
const formatFrequency = (frequency) => {
  if (frequency === undefined || frequency === null) {
    return '0 KHz';
  } else if (typeof frequency !== 'number') {
    return `${frequency} KHz`;
  } else if (frequency >= 1000) {
    return `${(frequency / 1000).toFixed(2)} MHz`;
  } else {
    return `${frequency.toFixed(2)} KHz`;
  }
};

// 获取缓存信息
const getCacheInfo = async () => {
  try {
    // 检查是否已经在加载中
    if (loadingCache.value && document.hidden) {
      console.log('已有加载请求在进行中且页面不可见，跳过');
      return;
    }

    // 设置加载状态 - 如果已在viewCacheInfo中设置则不再设置
    if (!loadingCache.value) {
      loadingCache.value = true;
    }

    // 高效获取缓存键
    const keys = cacheKeysIndex.value.length > 0
      ? cacheKeysIndex.value
      : await indexedDBService.getAllKeys();

    // 即使没有缓存也更新索引
    if (cacheKeysIndex.value.length === 0) {
      cacheKeysIndex.value = keys;
    }

    if (keys.length === 0) {
      cacheKeys.value = [];
      loadingCache.value = false;
      return;
    }

    // 使用批量异步处理模式
    await processKeysInBatches(keys);
  } catch (error) {
    console.error('获取缓存键失败:', error);
    ElMessage({
      message: '获取缓存信息失败，请重试',
      type: 'error'
    });
  } finally {
    loadingCache.value = false;
  }
};

// 批量处理缓存键
const processKeysInBatches = async (keys) => {
  // 保存处理结果
  const newCacheKeys = [];
  const batchSize = 15; // 每批处理的数量
  const totalBatches = Math.ceil(keys.length / batchSize);

  // 分批处理
  for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
    const startIdx = batchIndex * batchSize;
    const endIdx = Math.min(startIdx + batchSize, keys.length);
    const batchKeys = keys.slice(startIdx, endIdx);

    // 创建这一批次的Promise
    const batchPromises = batchKeys.map(key =>
      indexedDBService.getChannelData(key)
        .then(data => ({ key, data }))
        .catch(error => {
          console.error(`获取缓存数据失败: ${key}`, error);
          return null;
        })
    );

    // 等待本批次完成
    const batchResults = await Promise.all(batchPromises);

    // 处理本批次结果
    for (const result of batchResults) {
      if (!result || !result.data) continue;

      const { key, data } = result;

      // 计算数据大小和类型
      const size = JSON.stringify(data).length;
      const isErrorData = key.startsWith('error-');

      // 构建缓存项
      if (isErrorData) {
        // 错误数据
        newCacheKeys.push({
          key,
          timestamp: data.timestamp || Date.now(),
          size,
          isErrorData: true,
          details: data.data || {}
        });
      } else {
        // 通道数据
        const dataContent = data.data || {};
        const dataPoints = Array.isArray(dataContent.X_value) ? dataContent.X_value.length :
          (dataContent.originalDataPoints || 0);

        // 简化细节处理
        const details = { ...dataContent };
        details.channel_number = details.channel_number || key.split('_')[0] || '';
        details.X_unit = details.X_unit || 's';
        details.Y_unit = details.Y_unit || '';
        details.originalFrequency = details.originalFrequency || 0;
        details.originalDataPoints = details.originalDataPoints || dataPoints;

        // 删除大型数组
        delete details.X_value;
        delete details.Y_value;

        newCacheKeys.push({
          key,
          timestamp: data.timestamp || Date.now(),
          size,
          dataPoints,
          isErrorData: false,
          details
        });
      }
    }

    // 在批次之间使用rAF让出主线程，避免UI阻塞
    if (batchIndex < totalBatches - 1) {
      await new Promise(resolve => requestAnimationFrame(resolve));
    }
  }

  // 所有批次处理完成后，排序并更新状态
  newCacheKeys.sort((a, b) => b.timestamp - a.timestamp);
  cacheKeys.value = newCacheKeys;
};

// 计算非错误数据缓存项
const nonErrorCacheKeys = computed(() => {
  return cacheKeys.value.filter(item => !item.isErrorData);
});

// 计算错误数据缓存项
const errorCacheKeys = computed(() => {
  return cacheKeys.value.filter(item => item.isErrorData);
});

// 错误数据表格选择变化事件
const handleErrorSelectionChange = (selection) => {
  // 将选中的error项添加到selectedCacheKeys中
  selectedCacheKeys.value = [...selectedCacheKeys.value.filter(item => !item.isErrorData), ...selection];
};

// 获取总缓存大小
const getTotalCacheSize = () => {
  // 使用reduce计算总大小，比forEach更高效
  return cacheKeys.value.reduce((total, item) => total + (item.size || 0), 0);
};

// 删除单个通道缓存
const deleteChannelCache = async (key) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除缓存 "${key}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    );

    await indexedDBService.deleteChannelData(key);
    // 从Vuex中移除该缓存
    store.commit('removeChannelDataCache', key);

    ElMessage({
      message: '缓存已删除',
      type: 'success'
    });

    // 刷新缓存列表
    await getCacheInfo();
  } catch (error) {
    if (error === 'cancel' || error.toString().includes('cancel')) {
      return;
    }

    console.error('删除缓存失败:', error);
    ElMessage({
      message: '删除缓存失败，请重试',
      type: 'error'
    });
  }
};

// 刷新缓存信息
const refreshCacheInfo = async () => {
  if (loadingCache.value) return; // 如果正在加载，忽略请求

  await getCacheInfo();

  ElMessage({
    message: '缓存信息已刷新',
    type: 'success'
  });
};

// 查看缓存信息
const viewCacheInfo = () => {
  // 重置缓存列表，确保每次都重新加载
  cacheKeys.value = [];
  cacheKeysIndex.value = [];

  // 立即打开对话框，不等待任何异步操作
  cacheInfoDialogVisible.value = true;

  // 使用requestAnimationFrame确保DOM更新后再处理数据加载
  requestAnimationFrame(() => {
    // 强制设置加载状态，确保UI有反馈
    loadingCache.value = true;

    // 使用setTimeout将数据加载移至宏任务队列末尾
    setTimeout(async () => {
      try {
        // 每次都重新获取缓存索引
        const keys = await indexedDBService.getAllKeys();
        cacheKeysIndex.value = keys;

        // 始终加载新数据
        if (keys.length > 0) {
          await getCacheInfo();
        } else {
          // 没有缓存数据，结束加载状态
          loadingCache.value = false;
        }
      } catch (error) {
        console.error('加载缓存数据失败:', error);
        loadingCache.value = false;
      }
    }, 0);
  });
};

// 清空缓存
const clearCache = async () => {
  try {
    // 使用 ElMessageBox 显示确认对话框
    await ElMessageBox.confirm(
      '确定要清空所有缓存数据吗？此操作不可恢复。',
      '清空缓存确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
        draggable: true,
      }
    );

    // 用户点击确认后，执行清空操作
    await indexedDBService.clearAllChannelData();
    // 清空Vuex中的缓存
    store.commit('clearChannelDataCache');
    ElMessage({
      message: '缓存数据已清空',
      type: 'success'
    });
  } catch (error) {
    // 如果是用户取消操作，不显示错误信息
    if (error === 'cancel' || error.toString().includes('cancel')) {
      return;
    }

    console.error('清空缓存失败:', error);
    ElMessage({
      message: '清空缓存失败，请重试',
      type: 'error'
    });
  }
};

// 定义组件的事件
const emit = defineEmits(['button-change']);

// 获取行类名
const getRowClassName = (row) => {
  return row.isErrorData ? 'error-row' : '';
};

// 确定哪些行可以展开
const isExpandable = (row) => {
  return !row.isErrorData;
};
</script>

<style scoped lang="scss">
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #ffffff;
  width: 100%;
  height: 5vh;
  min-height: 40px;
  max-height: 60px;
  padding: 0 6px;
  box-sizing: border-box;
  position: relative;
  z-index: 10;
}

.anay,
.channel {
  transition: all 0.2s;
}

.selected {
  font-weight: bold;
}

.user-dropdown {
  padding: 0;
  min-width: 240px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.98);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(0, 0, 0, 0.1);
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.1);
  margin-top: 8px;
  overflow: hidden;
}

.user-info {
  padding: 20px;
  background: linear-gradient(to bottom, rgba(0, 0, 0, 0.02), transparent);
}

.user-avatar {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 16px;

  .el-avatar {
    width: 60px;
    height: 60px;
    font-size: 24px;
    margin-bottom: 8px;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    font-weight: 600 !important;
    line-height: 1 !important;
  }

  .user-name {
    font-size: 16px;
    font-weight: 500;
    color: #1d1d1f;
  }
}

.user-detail {
  margin-top: 12px;

  .detail-item {
    display: flex;
    align-items: center;
    padding: 8px 12px;
    background: rgba(0, 0, 0, 0.02);
    border-radius: 8px;

    .el-icon {
      font-size: 16px;
      color: #86868b;
      margin-right: 8px;
    }

    .label {
      color: #86868b;
      font-size: 14px;
      margin-right: 8px;
    }

    .value {
      color: #1d1d1f;
      font-size: 14px;
      font-weight: 500;
    }
  }
}

.el-dropdown-menu :deep(.el-dropdown-menu__item) {
  padding: 12px 20px;
  font-size: 14px;
  color: #1d1d1f;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  margin: 4px 8px;
  border-radius: 8px;

  .el-icon {
    margin-right: 8px;
    font-size: 16px;
  }
}

.el-dropdown-menu :deep(.el-dropdown-menu__item:hover) {
  background-color: rgba(0, 0, 0, 0.04);
  color: #1d1d1f;
}

.el-dropdown-menu :deep(.el-dropdown-menu__item.danger) {
  color: #ff3b30;
  margin-top: 4px;
  margin-bottom: 8px;

  .el-icon {
    color: #ff3b30;
  }

  &:hover {
    background-color: rgba(255, 59, 48, 0.08);
  }
}

.el-dropdown-menu :deep(.el-dropdown-menu__item.warning) {
  color: #ff9500;
  margin-top: 4px;

  .el-icon {
    color: #ff9500;
  }

  &:hover {
    background-color: rgba(255, 149, 0, 0.08);
  }
}

.el-dropdown-menu :deep(.el-dropdown-menu__item.info) {
  color: #007aff;
  margin-top: 4px;

  .el-icon {
    color: #007aff;
  }

  &:hover {
    background-color: rgba(0, 122, 255, 0.08);
  }
}

.el-avatar {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid rgba(255, 255, 255, 0.8);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
  font-weight: 600 !important;
  font-size: 16px !important;
  line-height: 1 !important;
  text-align: center !important;
  position: relative;
}

.el-avatar:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 16px rgba(64, 158, 255, 0.25);
}

/* 确保头像内的文字完全居中 */
.el-avatar span {
  display: block;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 16px;
  line-height: 1;
}

.empty-cache {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 300px;
}

.dialog-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.cache-summary {
  color: #606266;
  font-size: 14px;
}

.cache-detail {
  padding: 10px;
  background-color: #f8f8f8;
  border-radius: 4px;
}

.detail-tag {
  margin-right: 5px;
  margin-bottom: 5px;
}

.error-table-section {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e0e0e0;
}

.table-divider {
  margin-bottom: 10px;
  font-weight: bold;
}

.table-loading {
  opacity: 0.6;
}

.loading-dialog-mask {
  backdrop-filter: blur(2px);
}

.monitor-status-wrapper {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
}

</style>