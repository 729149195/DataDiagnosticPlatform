<template>
  <!-- 监控状态显示卡片 -->
  <div class="monitor-status">
    <div class="status-container">
      <!-- 三列炮号信息 - 水平排列 -->
      <div class="shot-info">
        <!-- 已检测炮号 -->
        <div class="shot-block">
          <el-icon class="shot-icon completed">
            <CircleCheck />
          </el-icon>
          <span class="shot-tag">完成检测炮号</span>
          <span class="shot-value">{{ monitorData.mongo_latest_shot || '--' }}</span>
        </div>
        <span class="separator">/</span>

        <!-- 正在检测炮号 -->
        <div class="shot-block">
          <el-icon class="shot-icon processing" :class="{ spinning: showProgress }">
            <Loading />
          </el-icon>
          <span class="shot-tag">检测中炮号</span>
          <span class="shot-value">{{ currentProcessingShot }}</span>

          <!-- Element圆形进度条 - 同一行显示 -->
          <div v-if="showProgress" class="inline-progress">
            <el-progress type="circle" :percentage="Math.round(processingProgress.progress_percent)" :width="20"
              :stroke-width="3" :show-text="false" color="#4285f4" />
            <span class="progress-text-inline">{{ progressPercentText }}</span>
          </div>
        </div>
        <span class="separator">/</span>

        <!-- 总待检测炮号 -->
        <div class="shot-block">
          <el-icon class="shot-icon total">
            <DataBoard />
          </el-icon>
          <span class="shot-tag">总炮号</span>
          <span class="shot-value">{{ monitorData.mds_latest_shot || '--' }}</span>
        </div>
      </div>

      <!-- 编辑自动异常检测方法按钮 -->
      <div class="edit-algorithm-section">
        <el-tooltip content="编辑自动异常检测方法" placement="top" effect="light">
          <el-button type="primary" @click="openAlgorithmDialog" :icon="Setting">
          </el-button>
        </el-tooltip>
      </div>
    </div>

    <!-- 算法编辑对话框 -->
    <el-dialog v-model="algorithmDialogVisible" title="编辑自动异常检测方法" width="90%" :close-on-click-modal="false"
      :close-on-press-escape="true" destroy-on-close append-to-body top="5vh">
      <div class="algorithm-dialog-content">
        <!-- 三列布局 -->
        <div class="algorithm-sections">
          <!-- 左侧：内置算法 -->
          <div class="algorithm-section built-in-section">
            <div class="section-header">
              <h3>内置算法</h3>
            </div>
            <div class="section-content">
              <AlgorithmManager v-if="algorithmDialogVisible" :algorithm-data="algorithmData"
                @refresh-data="loadAlgorithmData" />
            </div>
          </div>

          <!-- 中间：导入算法 -->
          <div class="algorithm-section import-section">
            <div class="section-header">
              <h3>导入算法</h3>
            </div>
            <div class="section-content placeholder-content">
              <el-empty description="功能开发中，敬请期待" />
            </div>
          </div>

          <!-- 右侧：手绘模式 -->
          <div class="algorithm-section manual-section">
            <div class="section-header">
              <h3>手绘模式</h3>
            </div>
            <div class="section-content placeholder-content">
              <el-empty description="功能开发中，敬请期待" />
            </div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
// 监控状态显示组件，包含状态获取和倒计时逻辑
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { CircleCheck, Loading, DataBoard, Setting } from '@element-plus/icons-vue';
import AlgorithmManager from './AlgorithmManager.vue';

// 响应式数据
const monitorData = ref({
  mds_latest_shot: 0,
  mongo_processing_shot: 0,
  mongo_latest_shot: 0,
  last_update: null,
  next_update: null,
  is_running: false,
  processing_progress: {
    current_shot: 0,
    total_channels: 0,
    processed_channels: 0,
    progress_percent: 0.0,
    is_processing: false
  }
});

const countdownSeconds = ref(60);

// 算法对话框相关数据
const algorithmDialogVisible = ref(false);
const algorithmData = ref({});

let monitorTimer = null;
let countdownTimer = null;

// 计算属性：处理进度
const processingProgress = computed(() => {
  return monitorData.value.processing_progress || {
    current_shot: 0,
    total_channels: 0,
    processed_channels: 0,
    progress_percent: 0.0,
    is_processing: false
  };
});

// 计算属性：当前正在检测的炮号显示
const currentProcessingShot = computed(() => {
  const progress = processingProgress.value;
  // 只要is_processing为true就显示当前炮号
  if (progress.is_processing) {
    return progress.current_shot || '无';
  }
  // 其他情况才判断是否N/A
  return '无';
});

// 计算属性：是否显示进度条
const showProgress = computed(() => {
  const progress = processingProgress.value;
  return progress.is_processing &&
    progress.total_channels > 0 &&
    progress.progress_percent < 100 &&
    currentProcessingShot.value !== '无';
});

// 计算属性：进度百分比文本
const progressPercentText = computed(() => {
  const progress = processingProgress.value;

  // 如果进度为0，显示"等待稳定"
  if (progress.progress_percent === 0 || progress.progress_percent < 0.1) {
    return '等待稳定';
  }

  // 如果进度达到100%，显示"完成"
  if (progress.progress_percent >= 100) {
    return '完成';
  }

  // 正常显示百分比
  return `${Math.round(progress.progress_percent)}%`;
});

// 获取监控状态
const fetchMonitorStatus = async () => {
  try {
    let response = await fetch('https://10.1.108.231:5000/api/system-monitor-status');
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const result = await response.json();
    if (result.success && result.data) {
      monitorData.value = result.data;
      countdownSeconds.value = 60;
    } else {
      monitorData.value = {
        mds_latest_shot: '--',
        mongo_processing_shot: '--',
        mongo_latest_shot: '--',
        is_running: false,
        processing_progress: {
          current_shot: 0,
          total_channels: 0,
          processed_channels: 0,
          progress_percent: 0.0,
          is_processing: false
        }
      };
    }
  } catch (error) {
    monitorData.value = {
      mds_latest_shot: '--',
      mongo_processing_shot: '--',
      mongo_latest_shot: '--',
      is_running: false,
      processing_progress: {
        current_shot: 0,
        total_channels: 0,
        processed_channels: 0,
        progress_percent: 0.0,
        is_processing: false
      }
    };
  }
};

// 启动定时器
const startMonitoring = () => {
  fetchMonitorStatus();
  monitorTimer = setInterval(fetchMonitorStatus, 10000);
  countdownTimer = setInterval(() => {
    countdownSeconds.value--;
    if (countdownSeconds.value <= 0) {
      countdownSeconds.value = 60;
    }
  }, 1000);
};

// 停止定时器
const stopMonitoring = () => {
  if (monitorTimer) {
    clearInterval(monitorTimer);
    monitorTimer = null;
  }
  if (countdownTimer) {
    clearInterval(countdownTimer);
    countdownTimer = null;
  }
};

// 打开算法编辑对话框
const openAlgorithmDialog = () => {
  algorithmDialogVisible.value = true;
  loadAlgorithmData();
};

// 加载算法数据
const loadAlgorithmData = async () => {
  try {
    const response = await fetch('https://10.1.108.231:5000/api/algorithm-channel-map');
    if (response.ok) {
      const result = await response.json();
      if (result.success) {
        algorithmData.value = result.data || {};
      } else {
        console.error('Failed to load algorithm data:', result.error);
        algorithmData.value = {};
      }
    } else {
      console.error('Failed to load algorithm data: HTTP', response.status);
      algorithmData.value = {};
    }
  } catch (error) {
    console.error('Error loading algorithm data:', error);
    algorithmData.value = {};
  }
};

onMounted(() => {
  startMonitoring();
});
onBeforeUnmount(() => {
  stopMonitoring();
});
</script>

<style scoped lang="scss">
.shot-info {
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
  width: auto;
}

.shot-block {
  display: flex;
  flex-direction: row;
  align-items: center;
  min-width: 70px;
  margin: 0 4px;
  gap: 2px;
}

.shot-icon {
  font-size: 18px;
  line-height: 1;
  vertical-align: middle;
  margin-right: 4px;
  display: flex;
  align-items: center;
  justify-content: center;

  &.completed {
    color: #409eff;
    /* 绿色 - 已完成 */
  }

  &.processing {
    color: #409eff;
  }

  &.spinning {
    animation: el-icon-rotate 1s linear infinite;
  }

  &.total {
    color: #409eff;
    /* 灰色 - 统计信息 */
  }
}

.shot-tag {
  color: #5f6368;
  font-size: 16px;
  font-weight: 500;
  margin: 0 2px 0 0;
  line-height: 1;
}

.shot-value {
  color: #4285F4;
  font-weight: 600;
  font-size: 18px;
  margin-left: 4px;
  line-height: 1;
  display: flex;
  align-items: center;
}

.separator {
  margin: 0 16px;
  color: #dadce0;
  font-weight: 400;
  font-size: 18px;
}

.status-container {
  background: #fff;
  border-radius: 4px;
  box-shadow: 0 1px 4px rgba(60, 64, 67, 0.08), 0 1.5px 6px rgba(60, 64, 67, 0.08);
  padding: 4px;
  display: flex;
  flex-direction: row;
  justify-content: center;
  align-items: center;
}

.monitor-status {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  background: transparent;
}

/* 内联进度条样式 */
.inline-progress {
  display: flex;
  align-items: center;
  margin-left: 8px;
  gap: 6px;
}

.progress-text-inline {
  color: #5f6368;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

/* Element Plus 进度条样式调整 */
:deep(.el-progress-circle) {
  width: 20px !important;
  height: 20px !important;
}

:deep(.el-progress-circle__track) {
  stroke: #e8eaed;
}

:deep(.el-progress-circle__path) {
  stroke: #4285f4;
}

@keyframes el-icon-rotate {
  100% {
    transform: rotate(360deg);
  }
}

/* 编辑算法按钮样式 */
.edit-algorithm-section {
  margin-left: 8px;
  display: flex;
  justify-content: center;
}

/* 算法对话框样式 */
.algorithm-dialog-content {
  height: 70vh;
  overflow: hidden;
}

.algorithm-sections {
  display: flex;
  height: 100%;
  gap: 16px;
}

.algorithm-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.section-header {
  background: #f5f7fa;
  padding: 12px 16px;
  border-bottom: 1px solid #e4e7ed;
}

.section-header h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.section-content {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.placeholder-content {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.built-in-section {
  border-color: #409eff;
}

.built-in-section .section-header {
  background: #ecf5ff;
  color: #409eff;
}

.import-section {
  border-color: #67c23a;
}

.import-section .section-header {
  background: #f0f9ff;
  color: #67c23a;
}

.manual-section {
  border-color: #e6a23c;
}

.manual-section .section-header {
  background: #fdf6ec;
  color: #e6a23c;
}
</style>