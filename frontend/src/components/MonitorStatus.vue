<template>
  <!-- 监控状态显示卡片 -->
  <div class="monitor-status">
    <div class="status-container">
      <!-- <span class="status-title">MDS数据库检测状态</span> -->
      <div class="shot-info">
        <span class="processing-shot">{{ monitorData.mongo_latest_shot || '--' }}</span>
        <span class="separator">/</span>
        <span class="latest-shot">{{ monitorData.mds_latest_shot || '--' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
// 监控状态显示组件，包含状态获取和倒计时逻辑
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';

// 响应式数据
const monitorData = ref({
  mds_latest_shot: 0,
  mongo_processing_shot: 0,
  mongo_latest_shot: 0,
  last_update: null,
  next_update: null,
  is_running: false
});

const countdownSeconds = ref(10);
const countdownText = computed(() => `${countdownSeconds.value}s`);

let monitorTimer = null;
let countdownTimer = null;

// 获取监控状态
const fetchMonitorStatus = async () => {
  try {
    let response = await fetch('https://10.1.108.231:5000/api/system-monitor-status');
    if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
    const result = await response.json();
    if (result.success && result.data) {
      monitorData.value = result.data;
      countdownSeconds.value = 10;
    } else {
      monitorData.value = {
        mds_latest_shot: '--',
        mongo_processing_shot: '--',
        mongo_latest_shot: '--',
        is_running: false
      };
    }
  } catch (error) {
    monitorData.value = {
      mds_latest_shot: '--',
      mongo_processing_shot: '--',
      mongo_latest_shot: '--',
      is_running: false
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
      countdownSeconds.value = 10;
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
  margin-bottom: 4px;
  font-size: 16px;
  font-weight: 500;
  line-height: 1.2;
}
.processing-shot {
  color: #8b8b8b;
  font-weight: 600;
  font-size: 16px;
}
.separator {
  margin: 0 8px;
  color: #5F6368;
  font-weight: 400;
}
.latest-shot {
  color: #4285F4;
  font-weight: 600;
  font-size: 16px;
}
.countdown-info {
  display: flex;
  align-items: center;
  color: #5F6368;
  font-size: 12px;
  font-weight: 400;
  line-height: 1;
}
.timer-icon {
  margin-right: 4px;
  color: #4285F4;
}
.countdown {
  font-weight: 500;
  color: #4285F4;
}
</style> 