<template>
  <!-- 监控状态显示卡片 -->
  <div class="monitor-status">
    <div class="status-container">
      <!-- <span class="status-title">MDS数据库检测状态</span> -->
      <div class="shot-info">
        <div class="shot-block">
          <span class="shot-tag">{{ shotStatusLabel }}</span>
          <span class="shot-value">{{ monitorData.mongo_latest_shot || '--' }}</span>
        </div>
        <span class="separator">/</span>
        <div class="shot-block">
          <span class="shot-tag">当前总炮号</span>
          <span class="shot-value">{{ monitorData.mds_latest_shot || '--' }}</span>
        </div>
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

const countdownSeconds = ref(60);

let monitorTimer = null;
let countdownTimer = null;

// 计算属性：判断检测状态并返回相应的标签文本
const shotStatusLabel = computed(() => {
  const { mds_latest_shot, mongo_processing_shot, mongo_latest_shot } = monitorData.value;
  
  // 当所有shot值都相同时，显示"检测完全炮号"
  if (mds_latest_shot === mongo_processing_shot && 
      mongo_processing_shot === mongo_latest_shot && 
      mds_latest_shot !== 0) {
    return '检测完全炮号';
  }
  
  // 否则显示"检测中炮号"
  return '检测中炮号';
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
.shot-block {
  display: flex;
  flex-direction: row;
  align-items: center;
  min-width: 70px;
  margin: 0 4px;
}
.shot-value {
  color: #4285F4;
  font-weight: 600;
  font-size: 18px;
  margin-left: 8px;
}
.shot-tag {
  color: #5f6368;
  font-size: 14px;
  font-weight: 500;
  background: none;
  border-radius: 0;
  padding: 0;
  margin: 0;
  letter-spacing: 0.2px;
}
.separator {
  margin: 0 16px;
  color: #dadce0;
  font-weight: 400;
  font-size: 18px;
}
.status-container {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(60,64,67,0.08), 0 1.5px 6px rgba(60,64,67,0.08);
  padding: 4px;
  display: flex;
  flex-direction: column;
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