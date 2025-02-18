<template>
  <span style="display: flex; align-items: center; justify-content: space-between;">
    <span class="title">自动识别和人工标注结果</span>
    <img src="/image2.png" style="height: 20px;" alt="图例" id="heatmapLegend">
    <div>
      <el-dropdown trigger="click" @command="handleHeatmapExport">
        <el-button type="primary" style="margin-right: 10px;">
          导出<el-icon class="el-icon--right">
            <Upload />
          </el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="exportSvg">导出SVG</el-dropdown-item>
            <el-dropdown-item command="exportData">导出数据</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
      <el-button type="primary" @click="syncUpload" v-if="store.state.authority != 0">
        上传同步<el-icon class="el-icon--right">
          <Upload />
        </el-icon>
      </el-button>
    </div>
  </span>
  <div class="heatmap-section">
    <div v-if="selectedChannels.length === 0">
      <el-empty :image-size="80" description="请选择通道" />
    </div>
    <div v-else class="heatmap-scrollbar">
      <el-scrollbar height="25vh" :always="false">
        <div class="heatmap-container">
          <div v-if="loading" class="progress-wrapper">
            <div class="progress-title">
              <span>热力图数据加载中</span>
              <span class="progress-percentage">{{ loadingPercentage }}%</span>
            </div>
            <el-progress :percentage="loadingPercentage" :stroke-width="10"
              :status="loadingPercentage === 100 ? 'success' : ''" />
          </div>
          <div class="heatmap-container" :style="{ opacity: loading ? 0 : 1, transition: 'opacity 0.3s ease' }">
            <svg id="heatmap" ref="HeatMapRef" preserveAspectRatio="xMidYMid slice"></svg>
          </div>
        </div>
      </el-scrollbar>
    </div>
    <el-dialog v-model="showAnomalyDialog" title="异常信息" :modal="true" :close-on-click-modal="false"
      @close="handleDialogClose" :destroy-on-close="true" class="anomaly-dialog">
      <div class="search-container">
        <el-input
          v-model="searchQuery"
          placeholder="模糊匹配搜索异常信息..."
          clearable
          style="width: 100"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
      <div class="anomaly-container">
        <div v-for="(group, groupIndex) in sortedAnomalies" :key="groupIndex" class="anomaly-group">
          <h3 class="group-title">{{ group.type }}</h3>
          <el-scrollbar height="45vh" :always="false">
            <div class="anomaly-content">
              <template v-if="group.anomalies.length > 0">
                <div v-for="(anomaly, index) in group.anomalies" :key="index" class="anomaly-item"
                  :class="{ 'highlight': isHighlighted(anomaly) }">
                  <el-card shadow="hover" :body-style="{ padding: '0px' }">
                    <div class="anomaly-bookmark">
                      <div class="bookmark-actions">
                        <el-icon 
                          v-if="anomaly.id"
                          class="action-icon edit-icon" 
                          @click="editAnomaly(anomaly, group.type)"
                        >
                          <Edit />
                        </el-icon>
                        <el-icon 
                          class="action-icon delete-icon"
                          @click="anomaly.id ? deleteAnomalyFromList(anomaly, group.type) : deleteErrorData(anomaly, group.type)"
                        >
                          <Delete />
                        </el-icon>
                      </div>
                    </div>
                    <el-descriptions :column="1" border class="anomaly-descriptions">
                      <el-descriptions-item v-for="(value, key) in anomaly" :key="key" :label="formatKey(key)">
                        {{ formatValue(value, key) }}
                      </el-descriptions-item>
                    </el-descriptions>
                  </el-card>
                </div>
              </template>
              <div v-else class="empty-message">
                无{{ group.type }}数据
              </div>
            </div>
          </el-scrollbar>
        </div>
      </div>
    </el-dialog>
    <el-dialog v-if="showAnomalyForm && currentAnomaly.channelName" v-model="showAnomalyForm" title="编辑/修改异常信息" :destroy-on-close="true">
      <el-form :model="currentAnomaly" label-width="auto">
        <el-form-item label="通道名">
          <el-input v-model="currentAnomaly.channelName" disabled />
        </el-form-item>
        <el-form-item label="异常类别">
          <el-input v-model="currentAnomaly.anomalyCategory" />
        </el-form-item>
        <el-form-item label="异常诊断名称">
          <el-input v-model="currentAnomaly.anomalyDiagnosisName" />
        </el-form-item>
        <el-form-item label="时间轴范围">
          <el-input :value="timeAxisRange" disabled />
        </el-form-item>
        <el-form-item label="异常描述">
          <el-input v-model="currentAnomaly.anomalyDescription" :rows="4" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="closeAnomalyForm">取消</el-button>
          <el-button type="primary" @click="saveAnomaly">保存</el-button>
          <el-button type="danger" @click="deleteAnomaly">删除</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import * as d3 from 'd3';
import { onMounted, watch, computed, ref, nextTick, onUnmounted, reactive } from 'vue';
import { useStore } from 'vuex';
import { ElDialog, ElDescriptions, ElDescriptionsItem, ElMessage, ElMessageBox, ElLoading } from 'element-plus';
import pLimit from 'p-limit';
import debounce from 'lodash/debounce';  // 添加 debounce 导入
import { Search, Delete, Edit } from '@element-plus/icons-vue';

// 添加进度相关的响应式变量
const loading = ref(false);
const loadingPercentage = ref(0);
const totalRequests = ref(0);
const completedRequests = ref(0);

// 获取 Vuex store 中的状态
const store = useStore();
const selectedChannels = computed(() => store.state.selectedChannels);
const storePerson = computed(() => store.state.person);
const anomaliesByChannel = computed(() => store.state.anomalies);

// 添加对 brush 范围的计算属性
const brushRange = computed(() => ({
  begin: parseFloat(store.state.brush_begin),
  end: parseFloat(store.state.brush_end)
}));

// 异常信息对话框的数据和显示状态
const anomalyDialogData = ref([]);
const showAnomalyDialog = ref(false);

// 全局存储所有错误和异常的数据
let errorResults = [];

// 在 script setup 部分的开头添加 channelDataCache 的计算属性
const channelDataCache = computed(() => store.state.channelDataCache);

// 添加解码中文文本的函数
const decodeChineseText = (text) => {
  if (!text) return '';
  try {
    // 如果是普通的中文字符串，直接返回
    if (typeof text === 'string' && /^[\u4e00-\u9fa5]+$/.test(text)) {
      return text;
    }

    // 如果是 URI 编码的字符串
    if (typeof text === 'string' && text.includes('%')) {
      try {
        return decodeURIComponent(text);
      } catch (e) {
        console.warn('Failed to decode URI component:', text, e);
      }
    }

    // 如果包含 Unicode 转义序列
    if (typeof text === 'string' && text.includes('\\u')) {
      try {
        return JSON.parse(`"${text}"`);
      } catch (e) {
        console.warn('Failed to decode Unicode escape:', text, e);
      }
    }

    // 如果包含需要解码的字符
    if (typeof text === 'string' && /[\u0080-\uffff]/.test(text)) {
      try {
        // 尝试多种解码方式
        const decoded = decodeURIComponent(escape(text));
        if (decoded !== text) {
          return decoded;
        }
      } catch (e) {
        try {
          // 尝试使用 Buffer 解码（如果是 Node.js 环境）
          return Buffer.from(text, 'binary').toString('utf8');
        } catch (e2) {
          console.warn('Failed to decode text:', text, e2);
        }
      }
    }
    return text;
  } catch (err) {
    console.warn('Error decoding text:', err);
    return text;
  }
};

// 添加处理对象的函数
const processObject = (obj) => {
  if (!obj) return obj;

  if (Array.isArray(obj)) {
    return obj.map(item => processObject(item));
  }

  if (typeof obj === 'object') {
    const newObj = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        // 跳过 X_error 和 Y_error 字段
        if (key !== 'X_error' && key !== 'Y_error') {
          let value = obj[key];
          // 对字符串类型的值进行解码
          if (typeof value === 'string') {
            value = decodeChineseText(value);
          }
          newObj[key] = processObject(value);
        } else {
          newObj[key] = obj[key];
        }
      }
    }
    return newObj;
  }

  if (typeof obj === 'string') {
    return decodeChineseText(obj);
  }

  return obj;
};

//导出功能函数
const HeatMapRef = ref(null)

// 添加通用的下载函数
const downloadFile = async (blob, suggestedName, fileType = 'json') => {
  try {
    // 根据文件类型设置accept选项
    const acceptOptions = {
      'json': {
        'application/json': ['.json'],
      },
      'png': {
        'image/png': ['.png'],
      },
      'svg': {
        'image/svg+xml': ['.svg'],
      }
    };

    // 使用 showSaveFilePicker API 来显示保存对话框
    const handle = await window.showSaveFilePicker({
      suggestedName: suggestedName,
      types: [{
        description: '导出文件',
        accept: acceptOptions[fileType] || acceptOptions['json'],
      }],
    });

    // 创建 FileSystemWritableFileStream 来写入数据
    const writable = await handle.createWritable();
    await writable.write(blob);
    await writable.close();

    // 显示成功提示
    ElMessage({
      message: '文件保存成功',
      type: 'success',
    });
  } catch (err) {
    if (err.name === 'AbortError') {
      // 用户取消保存，不显示错误
      return;
    }
    console.error('保存文件时出错:', err);
    ElMessage({
      message: '保存文件失败，请重试',
      type: 'error',
    });
  }
};

// 修改导出SVG功能
const exportHeatMapSvg = async () => {
  let HeatMap = HeatMapRef.value;
  if (HeatMap) {
    try {
      // 克隆 SVG 元素并创建一个新的 XML 序列化器
      const clonedSvgElement = HeatMap.cloneNode(true);
      const svgData = new XMLSerializer().serializeToString(clonedSvgElement);

      // 创建一个新的 Image 对象用于 SVG
      const svgImg = new Image();
      const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
      const svgUrl = URL.createObjectURL(svgBlob);

      // 获取图例图片
      const legendImg = document.getElementById('heatmapLegend');

      // 创建一个 canvas 元素
      const canvas = document.createElement('canvas');
      const legendWidth = legendImg.width;  // 缩小一半
      const legendHeight = legendImg.height; // 缩小一半
      const padding = 30;
      const canvasWidth = Math.max(HeatMap.width.baseVal.value, legendImg.width);
      const canvasHeight = HeatMap.height.baseVal.value + legendImg.height + padding;
      canvas.width = canvasWidth;
      canvas.height = canvasHeight;
      const ctx = canvas.getContext('2d');

      // 等待SVG图像加载
      await new Promise((resolve, reject) => {
        svgImg.onload = resolve;
        svgImg.onerror = reject;
        svgImg.src = svgUrl;
      });

      // 绘制图例图片和SVG到canvas上
      ctx.drawImage(legendImg, canvasWidth - legendWidth - 30, 0, legendWidth, legendHeight);
      ctx.drawImage(svgImg, 0, legendHeight + padding);

      // 转换为blob并保存
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      await downloadFile(blob, 'heatmap_with_legend.png', 'png');

      // 释放 URL 对象
      URL.revokeObjectURL(svgUrl);
    } catch (error) {
      console.error('导出SVG时出错:', error);
      ElMessage({
        message: '导出图像失败，请重试',
        type: 'error',
      });
    }
  }
};

// 修改导出数据功能
const exportHeatMapData = async () => {
  // 深拷贝数据以避免修改原始数据
  let processedData = JSON.parse(JSON.stringify(errorResults));

  // 按通道分组数据
  const groupedByChannel = processedData.reduce((acc, result) => {
    const { channelKey } = result;
    if (!acc[channelKey]) {
      acc[channelKey] = {
        channelKey,
        errorIdx: result.errorIdx,
        errorData: [[], []] // [人工标注数据, 机器识别数据]
      };
    }
    return acc;
  }, {});

  // 处理每条数据
  processedData.forEach(result => {
    const { channelKey, errorData, isAnomaly } = result;
    const channelGroup = groupedByChannel[channelKey];

    if (isAnomaly) {
      // 前端标注的异常数据
      channelGroup.errorData[0].push(processObject(errorData));
    } else if (Array.isArray(errorData)) {
      // 后端返回的数据
      const [manualErrors, machineErrors] = errorData;
      if (manualErrors && manualErrors.length > 0) {
        channelGroup.errorData[0].push(...processObject(manualErrors));
      }
      if (machineErrors && machineErrors.length > 0) {
        channelGroup.errorData[1].push(...processObject(machineErrors));
      }
    } else {
      // 其他格式的数据
      if (errorData.person === 'machine') {
        channelGroup.errorData[1].push(processObject(errorData));
      } else {
        channelGroup.errorData[0].push(processObject(errorData));
      }
    }
  });

  // 转换为数组
  const reorganizedData = Object.values(groupedByChannel);
  const jsonData = JSON.stringify(reorganizedData, null, 2);
  const blob = new Blob([jsonData], { type: "application/json" });
  await downloadFile(blob, "heatmap_error_data.json", 'json');
};

// 修改 syncUpload 函数
const syncUpload = async () => {
  const loadingInstance = ElLoading.service({
    lock: true,
    text: '正在同步数据...',
    background: 'rgba(0, 0, 0, 0.7)'
  });

  try {
    // 深拷贝数据以避免修改原始数据
    let processedData = JSON.parse(JSON.stringify(errorResults));

    // 按通道分组数据
    const groupedByChannel = processedData.reduce((acc, result) => {
      const { channelKey } = result;
      if (!acc[channelKey]) {
        acc[channelKey] = {
          channelKey,
          errorIdx: result.errorIdx,
          errorData: [[], []] // [人工标注数据, 机器识别数据]
        };
      }
      return acc;
    }, {});

    // 处理每条数据
    processedData.forEach(result => {
      const { channelKey, errorData, isAnomaly } = result;
      const channelGroup = groupedByChannel[channelKey];

      if (isAnomaly) {
        // 前端标注的异常数据
        channelGroup.errorData[0].push(processObject(errorData));
      } else if (Array.isArray(errorData)) {
        // 后端返回的数据
        const [manualErrors, machineErrors] = errorData;
        if (manualErrors && manualErrors.length > 0) {
          channelGroup.errorData[0].push(...processObject(manualErrors));
        }
        if (machineErrors && machineErrors.length > 0) {
          channelGroup.errorData[1].push(...processObject(machineErrors));
        }
      }
    });

    // 转换为数组
    const reorganizedData = Object.values(groupedByChannel);

    // 发送到后端
    const response = await fetch('https://10.1.108.19:5000/api/sync-error-data/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(reorganizedData)
    });

    if (!response.ok) {
      throw new Error('同步失败');
    }

    // 同步成功后清空 store 中的 anomalies
    await store.commit('clearAnomalies');
    
    // 刷新数据
    await store.dispatch('refreshStructTreeData');
    ElMessage.success('同步成功');
  } catch (error) {
    console.error('同步失败:', error);
    ElMessage.error('同步失败: ' + error.message);
  } finally {
    loadingInstance.close();
  }
};

// 辅助函数：判断给定的 errorIdx 是否为异常
function isAnomaly(idx, channelKey) {
  const result = errorResults.find(
    (r) => r.errorIdx === idx && r.channelKey === channelKey
  );
  return result && result.isAnomaly;
}

// 辅助函数：将键名映射为友好的显示名称
function formatKey(key) {
  const keyMapping = {
    person: '责任人',
    diagnostic_name: '诊断名称',
    channel_number: '通道编号',
    error_type: '错误类型',
    x_unit: 'X 单位',
    y_unit: 'Y 单位',
    diagnostic_time: '诊断时间',
    error_description: '错误描述',
    sample_rate: '采样频率',
    id: 'ID',
    channelName: '通道名称',
    startX: '开始时间',
    endX: '结束时间',
    anomalyCategory: '异常类别',
    anomalyDiagnosisName: '异常诊断名称',
    anomalyDescription: '异常描述',
    isStored: '是否已保存',
    shot_number: '炮号',
    startTime: '开始时间',
    endTime: '结束时间',
    annotationTime: '标注时间'
  };

  return keyMapping[key] || key;
}

// 辅助函数：格式化值的显示
function formatValue(value, key) {
  // 过滤掉X_error和Y_error数据
  if (key === 'X_error' || key === 'Y_error') {
    return undefined;
  }

  if (key === 'startX' || key === 'endX') {
    return parseFloat(value).toFixed(4);
  }

  // 统一时间格式：YYYY-MM-DD HH:mm:ss
  if (key === 'diagnostic_time' || key === 'annotationTime') {
    if (!value) return '无';
    try {
      const date = new Date(value);
      if (isNaN(date.getTime())) {
        // 如果是ISO字符串，尝试直接格式化
        if (typeof value === 'string' && value.includes('T')) {
          const [datePart, timePart] = value.split('T');
          const time = timePart.split('.')[0];
          return `${datePart} ${time}`;
        }
        return value; // 如果无法解析，返回原值
      }

      // 格式化为 YYYY-MM-DD HH:mm:ss
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      const seconds = String(date.getSeconds()).padStart(2, '0');

      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    } catch (err) {
      console.warn('Error formatting date:', err);
      // 尝试直接格式化ISO字符串
      if (typeof value === 'string' && value.includes('T')) {
        const [datePart, timePart] = value.split('T');
        const time = timePart.split('.')[0];
        return `${datePart} ${time}`;
      }
      return value;
    }
  }

  if (value === null || value === undefined || value === '') {
    return '无';
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  return value;
}

// 修改处理对话框关闭事件
function handleDialogClose() {
  nextTick(() => {
    anomalyDialogData.value = [];
    showAnomalyDialog.value = false;
  });
}

// 添加重试和并发限制
const limit = pLimit(50); // 限制并发请求数为5

const retryRequest = async (fn, retries = 3, delay = 1000) => {
  try {
    return await fn();
  } catch (err) {
    if (retries <= 0) throw err;
    await new Promise(resolve => setTimeout(resolve, delay));
    return retryRequest(fn, retries - 1, delay * 2);
  }
};

// 添加渲染状态控制
const isTransitioning = ref(false);
const renderTimeout = ref(null);

// 创建防抖的渲染函数
const debouncedRenderHeatmap = debounce(async (channels) => {
  if (isTransitioning.value) return;

  isTransitioning.value = true;

  // 设置渐出动画
  const heatmap = d3.select('#heatmap');
  heatmap.style('opacity', 0.3)
    .style('transition', 'opacity 0.2s ease-out');

  // 等待渐出动画完成
  await new Promise(resolve => setTimeout(resolve, 200));

  // 执行实际的渲染
  await renderHeatmap(channels);

  // 设置渐入动画
  heatmap.style('opacity', 1)
    .style('transition', 'opacity 0.3s ease-in');

  // 重置状态
  setTimeout(() => {
    isTransitioning.value = false;
  }, 300);
}, 300);  // 300ms 的防抖时间

// 修改 brush 范围监听器
watch(brushRange, (newRange, oldRange) => {
  if (!oldRange ||
    !selectedChannels.value.length ||
    isNaN(newRange.begin) ||
    isNaN(newRange.end)) return;

  // 检查变化是否显著（避免微小变化触发重绘）
  const threshold = 0.0001;
  const hasSignificantChange =
    Math.abs(newRange.begin - oldRange.begin) > threshold ||
    Math.abs(newRange.end - oldRange.end) > threshold;

  if (hasSignificantChange) {
    debouncedRenderHeatmap(selectedChannels.value);
  }
}, { deep: true });

// 在组件卸载时清理
onUnmounted(() => {
  if (renderTimeout.value) {
    clearTimeout(renderTimeout.value);
  }
  debouncedRenderHeatmap.cancel();
});

onMounted(() => {
  // 初始渲染
  if (selectedChannels.value.length > 0) {
    renderHeatmap(selectedChannels.value);
  }
});

const debounceRender = ref(null);

// 添加缓存记录已渲染的通道状态
const renderedChannelsState = ref(new Map());

// 检查通道是否需要重新渲染
function needsRerender(channel, newCache, newAnomalies) {
  const channelKey = `${channel.channel_name}_${channel.shot_number}`;
  const currentState = renderedChannelsState.value.get(channelKey);

  if (!currentState) return true;

  const newState = {
    errors: channel.errors,
    cacheData: newCache[channelKey],
    anomalies: newAnomalies ? newAnomalies[channelKey] : null
  };

  return JSON.stringify(currentState) !== JSON.stringify(newState);
}

// 更新已渲染通道的状态
// function updateRenderedState(channel, newCache, newAnomalies) {
//   const channelKey = `${channel.channel_name}_${channel.shot_number}`;
//   // 添加空值检查
//   if (!newCache || !newCache[channelKey]) {
//     console.warn(`Cache data not found for channel ${channelKey}`);
//     return;
//   }
  
//   renderedChannelsState.value.set(channelKey, {
//     errors: channel.errors,
//     cacheData: newCache[channelKey],
//     anomalies: newAnomalies ? newAnomalies[channelKey] : null
//   });
// }

watch(
  [() => channelDataCache.value, selectedChannels],
  async ([newCache, newChannels, newAnomalies], [oldCache, oldChannels]) => {
    if (!newChannels || newChannels.length === 0) {
      // 清空渲染状态和图表
      renderedChannelsState.value.clear();
      const heatmap = d3.select('#heatmap');
      heatmap.selectAll('*').remove();
      return;
    }

    // 检查是否有通道被删除
    if (oldChannels) {
      const removedChannels = oldChannels.filter(oldChannel =>
        !newChannels.some(newChannel =>
          `${newChannel.channel_name}_${newChannel.shot_number}` ===
          `${oldChannel.channel_name}_${oldChannel.shot_number}`
        )
      );

      // 清理已删除通道的渲染状态
      removedChannels.forEach(channel => {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        renderedChannelsState.value.delete(channelKey);
      });
    }

    // 找出需要重新渲染的通道
    const channelsToRender = newChannels.filter(channel =>
      needsRerender(channel, newCache, newAnomalies)
    );

    // 如果有通道被删除或有需要重新渲染的通道，执行渲染
    const shouldUpdate = channelsToRender.length > 0 || (oldChannels && oldChannels.length !== newChannels.length);

    if (!shouldUpdate) {
      return;
    }

    // 使用防抖来避免频繁渲染
    if (debounceRender.value) {
      clearTimeout(debounceRender.value);
    }

    // 创建一个新的 Promise 来处理渲染
    const renderPromise = new Promise((resolve) => {
      debounceRender.value = setTimeout(async () => {
        try {
          await nextTick();
          // 传入所有通道进行完整渲染
          await renderHeatmap(newChannels, false);

          // // 更新渲染状态
          // newChannels.forEach(channel => {
          //   updateRenderedState(channel, newCache, newAnomalies);
          // });

          resolve();
        } catch (error) {
          console.error('Error in debounced renderHeatmap:', error);
          loading.value = false;
          loadingPercentage.value = 0;
          resolve();
        }
      }, 300);
    });

    await renderPromise;
  },
  {
    deep: true
  }
);

// 组件卸载时清理定时器
onUnmounted(() => {
  if (debounceRender.value) {
    clearTimeout(debounceRender.value);
  }
});

// 添加数据处理函数
const processDataTo1KHz = (data) => {
  if (!data || !data.X_value || !data.Y_value) {
    return data;
  }

  const targetFrequency = 1000; // 1KHz
  const timeStep = 1 / targetFrequency;

  // 计算当前采样率
  const currentTimeStep = (data.X_value[data.X_value.length - 1] - data.X_value[0]) / (data.X_value.length - 1);
  const currentFrequency = 1 / currentTimeStep;

  // 如果当前频率接近1KHz，直接返回原始数据
  if (Math.abs(currentFrequency - targetFrequency) < 1) {
    return data;
  }

  // 创建新的时间点数组
  const startTime = data.X_value[0];
  const endTime = data.X_value[data.X_value.length - 1];
  const newXValues = [];
  const newYValues = [];

  let currentTime = startTime;
  let currentIndex = 0;

  while (currentTime <= endTime && currentIndex < data.X_value.length) {
    // 找到当前时间点对应的索引
    while (currentIndex < data.X_value.length - 1 && data.X_value[currentIndex + 1] < currentTime) {
      currentIndex++;
    }

    // 线性插值
    if (currentIndex < data.X_value.length - 1) {
      const x0 = data.X_value[currentIndex];
      const x1 = data.X_value[currentIndex + 1];
      const y0 = data.Y_value[currentIndex];
      const y1 = data.Y_value[currentIndex + 1];

      const ratio = (currentTime - x0) / (x1 - x0);
      const interpolatedY = y0 + ratio * (y1 - y0);

      newXValues.push(currentTime);
      newYValues.push(interpolatedY);
    }

    currentTime += timeStep;
  }

  return {
    X_value: newXValues,
    Y_value: newYValues,
    X_unit: data.X_unit,
    Y_unit: data.Y_unit
  };
};

async function renderHeatmap(channels, isOnlyAnomalyChange = false) {
  try {
    if (!channels || channels.length === 0) {
      loading.value = false;
      return;
    }

    // 重置进度状态
    loading.value = true;
    loadingPercentage.value = 0;
    completedRequests.value = 0;

    const heatmap = d3.select('#heatmap');

    // 保存当前的滚动位置
    const container = document.querySelector('.heatmap-scrollbar');
    const scrollTop = container ? container.scrollTop : 0;

    // 总是清除所有元素以确保正确的渲染
    heatmap.selectAll('*').remove();

    // 如果只是异常数据变化，保留现有的错误数据
    if (!isOnlyAnomalyChange) {
      errorResults = [];
    }

    // 计算总请求数
    totalRequests.value = channels.reduce((total, channel) => total + channel.errors.length, 0);
    if (totalRequests.value === 0) {
      loading.value = false;
      loadingPercentage.value = 100;
      return;
    }

    // 计算所有通道数据的 X 值范围
    let globalXMin = Infinity;
    let globalXMax = -Infinity;

    // 使用 Map 缓存已处理的通道数据
    const processedChannels = new Map();

    // 遍历所有通道数据来计算全局 X 范围
    for (const channel of channels) {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const channelData = channelDataCache.value[channelKey];

      if (channelData && channelData.X_value) {
        const processedData = processDataTo1KHz(channelData);
        let xValues = processedData.X_value;

        const localMin = Math.min(...xValues);
        const localMax = Math.max(...xValues);

        globalXMin = Math.min(globalXMin, localMin);
        globalXMax = Math.max(globalXMax, localMax);

        processedChannels.set(channelKey, {
          ...processedData,
          localMin,
          localMax
        });
      }
    }

    // 如果没有找到有效数据,使用默认
    if (globalXMin === Infinity || globalXMax === -Infinity) {
      globalXMin = -2;
      globalXMax = 6;
    }

    // 方案1：全移除边距
    const Domain = [brushRange.value.begin, brushRange.value.end];

    const step = (Domain[1] - Domain[0]) / 16; // 或者其他合适的步长计算方式
    const rectNum = Math.round((Domain[1] - Domain[0]) / step);

    const visData = {}; // { [channelKey]: data array }
    const errorColors = {}; // { [errorIdx]: color }
    let errorIdxCounter = 1;

    // 使用 Map 存储错误数据
    const errorDataMap = new Map();
    const errorPromises = [];

    // 对于每个通道
    for (const channel of channels) {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      const channelType = channel.channel_type;

      // 初始化该通道的可视化数据
      if (!visData[channelKey]) {
        visData[channelKey] = Array(rectNum).fill().map(() => []);
      }

      // 获取错误数据
      try {
        // 使用 store 中的方法获取错误数据
        const errorDataResults = await store.dispatch('fetchAllErrorData', channel);

        // 处理每个错误数据
        for (const [errorIndex, error] of channel.errors.entries()) {
          // 添加判断，如果是 NO ERROR 则跳过
          if (error.error_name === 'NO ERROR') {
            // 更新进度
            completedRequests.value++;
            loadingPercentage.value = Math.round((completedRequests.value / totalRequests.value) * 100);
            continue;
          }

          const errorIdxCurrent = errorIdxCounter++;
          errorColors[errorIdxCurrent] = error.color;

          // 存储错误数据
          if (errorDataResults[errorIndex]) {
            errorDataMap.set(errorIdxCurrent, {
              channelKey,
              errorIdx: errorIdxCurrent,
              errorData: errorDataResults[errorIndex],
              isAnomaly: false
            });

            // 处理错误数据
            processErrorData(errorDataResults[errorIndex], channelKey, errorIdxCurrent, visData, rectNum, Domain, step);
          }

          // 更新进度
          completedRequests.value++;
          loadingPercentage.value = Math.round((completedRequests.value / totalRequests.value) * 100);
        }
      } catch (err) {
        console.warn(`Failed to fetch error data for channel ${channelKey}:`, err);
        // 继续处理下一个通道
        continue;
      }
    }

    // 将所有错误数据添加到 errorResults
    errorResults = Array.from(errorDataMap.values());

    // 处理异常数据（用户标注的异常）
    // 如果只是异常数据变化，先移除旧的异常数据
    if (isOnlyAnomalyChange) {
      errorResults = errorResults.filter(result => !result.isAnomaly);
    }

    for (const channel of channels) {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      // 直接从store获取异常数据
      const channelAnomalies = store.getters.getAnomaliesByChannel(channelKey) || [];

      // 确保 visData[channelKey] 存在
      if (!visData[channelKey]) {
        visData[channelKey] = Array(rectNum).fill().map(() => []);
      }

      for (const anomaly of channelAnomalies) {
        const anomalyErrorIdxCurrent = errorIdxCounter++;
        errorColors[anomalyErrorIdxCurrent] = 'orange';

        // 将异常数据添加到 errorResults
        errorResults.push({
          channelKey,
          errorIdx: anomalyErrorIdxCurrent,
          errorData: anomaly,
          isAnomaly: true,
        });

        // 计算异常区间的位置，使用1KHz的时间步长
        const timeStep = 0.001; // 1KHz
        const startX = Math.floor(parseFloat(anomaly.startX) / timeStep) * timeStep;
        const endX = Math.ceil(parseFloat(anomaly.endX) / timeStep) * timeStep;

        // 计算对应的矩形索引
        const left = Math.floor((startX - Domain[0]) / step);
        const right = Math.floor((endX - Domain[0]) / step);

        // 将异常添加到对应的矩形中
        for (let i = left; i <= right && i < rectNum; i++) {
          if (i >= 0) {
            visData[channelKey][i].push(anomalyErrorIdxCurrent);
          }
        }
      }
    }

    // 准备绘图数据
    const channelKeys = channels.map(
      (channel) => `${channel.channel_name}_${channel.shot_number}`
    );
    const channelNames = channels.map(
      (channel) => `${channel.channel_name} / ${channel.shot_number}`
    );

    // 确保所有通道都有数据
    channelKeys.forEach(key => {
      if (!visData[key]) {
        visData[key] = Array(rectNum).fill().map(() => []);
      }
    });

    const visDataArrays = channelKeys.map((key) => visData[key]);

    // 准备X轴刻度
    const xAxisTick = [];
    for (let i = Domain[0]; i <= Domain[1]; i += step) {
      xAxisTick.push(i.toFixed(1)); // 保留一位小数
    }

    // 设置绘图尺寸
    const margin = { top: 8, right: 10, bottom: 100, left: 5 };
    const width = 1080 - margin.left - margin.right;
    const rectH = 25; // 固定每个矩形的高度
    const XaxisH = 20;
    const YaxisW = 140; // 调整宽度以适应通道名和炮号
    const height = rectH * channelNames.length + XaxisH;

    const rectW = (width - YaxisW - margin.left) / rectNum;

    // 动态设置 SVG 的 viewBox 属性
    heatmap
      .attr(
        'viewBox',
        `0 0 ${width + margin.left + margin.right + YaxisW / 2} ${height + margin.top + margin.bottom}`
      )
      .attr('preserveAspectRatio', 'xMidYMid slice') // 修改为 'slice' 以确保自适应
      .attr('width', '100%') // 设置宽度为 100%
      .attr('height', height + margin.top + margin.bottom); // 设置高度

    // 绘制Y轴通道名称和炮号
    heatmap
      .selectAll('.channelName')
      .data(channelNames)
      .join('text')
      .attr('class', 'channelName')
      .attr('x', YaxisW - margin.left - 5)
      .attr(
        'y',
        (d, i) =>
          rectH * 0.5 + 5 + XaxisH + i * (rectH + margin.top)
      )
      .style('text-anchor', 'end')
      .text((d) => d);

    // 绘制X轴刻度
    heatmap
      .selectAll('.xTick')
      .data(xAxisTick)
      .join('text')
      .attr('class', 'xTick')
      .attr('x', (d, i) => YaxisW + i * (rectW + margin.left))
      .attr('y', XaxisH - 5)
      .style('text-anchor', 'middle')
      .style('font-size', '10px')
      .text((d) => d);

    // 绘制热力图矩形
    heatmap
      .selectAll('.heatmapRectG')
      .data(visDataArrays)
      .join('g')
      .attr('class', 'heatmapRectG')
      .attr(
        'transform',
        (d, i) => `translate(${YaxisW}, ${XaxisH + i * (rectH + margin.top)})`
      )
      .each(function (d, i) {
        const channel = channels[i];
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;

        // 1. 首先绘制内部填充矩形（最底层）
        d3.select(this)
          .selectAll('.innerRect')
          .data(d)
          .join('rect')
          .attr('class', 'innerRect')
          .attr('x', (d, j) => j * (rectW + margin.left) + rectW * 0.1)
          .attr('y', rectH * 0.1)
          .attr('width', rectW * 0.8)
          .attr('height', rectH * 0.8)
          .attr('rx', 2)
          .attr('ry', 2)
          .attr('fill', (d) => {
            if (d.length > 0) {
              // 存在错误或异常
              if (channel.errors.length > 1) {
                return '#999999'; // 多个错误，使用灰色
              } else {
                const nonAnomalyIdx = d.find(
                  (idx) => !isAnomaly(idx, channelKey)
                );
                const errorData = errorResults.find(
                  (result) =>
                    result &&
                    result.errorIdx === nonAnomalyIdx &&
                    result.channelKey === channelKey
                );
                if (errorData && errorData.errorData.person === 'machine') {
                  return errorColors[nonAnomalyIdx];
                } else {
                  return '#f5f5f5';
                }
              }
            } else {
              return '#f5f5f5'; // 正常数据颜色
            }
          })
          .attr('cursor', 'pointer')
          .on('click', function (event, dRect) {
            event.stopPropagation();

            const errorIdxs = dRect;
            const errorsInRect = errorIdxs
              .map((idx) =>
                errorResults.find(
                  (result) =>
                    result &&
                    result.errorIdx === idx &&
                    result.channelKey === channelKey
                )
              )
              .filter((e) => e);

            // 提取并过滤所有错误信息
            const processErrorData = (errorData) => {
              // 过滤掉X_error和Y_error字段
              const { X_error, Y_error, ...filteredData } = errorData;

              // 格式化每个字段
              const processedData = {};
              Object.keys(filteredData).forEach((key) => {
                let value = filteredData[key];

                // 处理特殊的中文字符编码
                if (typeof value === 'string') {
                  value = decodeChineseText(value);
                }

                const formattedValue = formatValue(value, key);
                if (formattedValue !== undefined && formattedValue !== null && formattedValue !== '') {
                  processedData[key] = formattedValue;
                } else {
                  processedData[key] = '无';
                }
              });

              // 处理时间字段
              if (processedData.person === 'machine' && processedData.diagnostic_time) {
                processedData.diagnostic_time = formatValue(processedData.diagnostic_time, 'diagnostic_time');
              }

              if (processedData.person !== 'machine' && processedData.annotationTime) {
                processedData.annotationTime = formatValue(processedData.annotationTime, 'annotationTime');
              }

              return processedData;
            };

            // 分离人工标注和机器识别的异常
            const manualAnomalies = [];
            const machineAnomalies = [];

            errorsInRect.forEach((error) => {
              // 检查是否是前端标注的异常数据
              if (error.isAnomaly) {
                // 从store获取最新的异常数据
                const storedAnomalies = store.getters.getAnomaliesByChannel(error.channelKey);
                const storedAnomaly = storedAnomalies.find(a => a.id === error.errorData.id);

                if (storedAnomaly) {
                  const processedData = processErrorData(storedAnomaly);
                  if (Object.keys(processedData).length > 0) {
                    manualAnomalies.push(processedData);
                  }
                }
              } else {
                // 处理来自后端的异常数据
                try {
                  const [manualErrors, machineErrors] = error.errorData;

                  // 处理人工标注的异常
                  if (manualErrors && manualErrors.length > 0) {
                    manualErrors.forEach(manualError => {
                      if (manualError && Object.keys(manualError).length > 0) {
                        const processedData = processErrorData(manualError);
                        if (Object.keys(processedData).length > 0) {
                          manualAnomalies.push(processedData);
                        }
                      }
                    });
                  }

                  // 处理机器识别的异常
                  if (machineErrors && machineErrors.length > 0) {
                    machineErrors.forEach(machineError => {
                      if (machineError && Object.keys(machineError).length > 0) {
                        // 对机器识别的结果进行处理
                        const processedData = processObject(machineError);
                        if (Object.keys(processedData).length > 0) {
                          machineAnomalies.push(processedData);
                        }
                      }
                    });
                  }
                } catch (err) {
                  console.warn('Error processing error data:', err);
                  // 如果解构失败，尝试直接处理errorData
                  const processedData = processErrorData(error.errorData);
                  if (Object.keys(processedData).length > 0) {
                    if (error.errorData.person === 'machine') {
                      machineAnomalies.push(processedData);
                    } else {
                      manualAnomalies.push(processedData);
                    }
                  }
                }
              }
            });

            // 去除重复的异常信息
            const uniqueManualAnomalies = manualAnomalies.filter(
              (item, index, self) =>
                index === self.findIndex((t) => JSON.stringify(t) === JSON.stringify(item))
            );

            const uniqueMachineAnomalies = machineAnomalies.filter(
              (item, index, self) =>
                index === self.findIndex((t) => JSON.stringify(t) === JSON.stringify(item))
            );

            // 组合最终显示的数据
            const combinedAnomalies = [
              {
                type: '人工标注异常',
                anomalies: uniqueManualAnomalies.length > 0 ? uniqueManualAnomalies : []
              },
              {
                type: '机器识别异常',
                anomalies: uniqueMachineAnomalies.length > 0 ? uniqueMachineAnomalies : []
              }
            ];

            if (combinedAnomalies.length > 0) {
              anomalyDialogData.value = combinedAnomalies;
              showAnomalyDialog.value = true;
            } else {
              showAnomalyDialog.value = false;
            }
          });

        // 2. 然后绘制内部虚线框（中间层）
        d3.select(this)
          .selectAll('.innerDashedRect')
          .data(d)
          .join('rect')
          .attr('class', 'innerDashedRect')
          .attr('x', (d, j) => j * (rectW + margin.left) + 4)  // 调整内部框的大小
          .attr('y', 4)
          .attr('width', rectW - 8)
          .attr('height', rectH - 8)
          .attr('rx', 2)
          .attr('ry', 2)
          .attr('fill', 'none')
          .attr('stroke', (d) => {
            if (d.length > 0) {
              const nonAnomalyIdx = d.find(idx => {
                const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
                return result && !result.isAnomaly;
              });

              if (nonAnomalyIdx) {
                const errorData = errorResults.find(
                  result => result &&
                    result.errorIdx === nonAnomalyIdx &&
                    result.channelKey === channelKey
                );
                if (errorData && Array.isArray(errorData.errorData)) {
                  const [manualErrors] = errorData.errorData;
                  if (manualErrors && manualErrors.length > 0 && storePerson.value) {
                    // 检查是否同时存在自己和他人的标注
                    const hasSelfAnnotation = manualErrors.some(error => error.person === storePerson.value);
                    const hasOthersAnnotation = manualErrors.some(error => error.person !== storePerson.value);

                    // 只有同时存在两种标注时才显示内部虚线框
                    if (hasSelfAnnotation && hasOthersAnnotation) {
                      return 'red';
                    }
                  }
                }
              }
            }
            return 'none';
          })
          .attr('stroke-width', 2)
          .attr('stroke-dasharray', '3 2')
          .attr('pointer-events', 'none');

        // 3. 最后绘制外部边框（最上层）
        d3.select(this)
          .selectAll('.heatmapRect')
          .data(d)
          .join('rect')
          .attr('class', 'heatmapRect')
          .attr('x', (d, j) => j * (rectW + margin.left))
          .attr('y', 0)
          .attr('width', rectW)
          .attr('height', rectH)
          .attr('rx', 3)
          .attr('ry', 3)
          .attr('fill', 'none')
          .attr('stroke', (d) => {
            if (d.length > 0) {
              // 检查是否包含异常
              const hasAnomaly = d.some(idx => {
                const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
                return result && result.isAnomaly;
              });

              if (hasAnomaly) {
                return 'orange';
              }

              const nonAnomalyIdx = d.find(idx => {
                const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
                return result && !result.isAnomaly;
              });

              if (nonAnomalyIdx) {
                const errorData = errorResults.find(
                  result => result &&
                    result.errorIdx === nonAnomalyIdx &&
                    result.channelKey === channelKey
                );
                if (errorData && Array.isArray(errorData.errorData)) {
                  const [manualErrors] = errorData.errorData;
                  if (manualErrors && manualErrors.length > 0) {
                    return 'red';  // 无论是否匹配都使用红色
                  }
                }
              }
            }
            return 'none';
          })
          .attr('stroke-width', (d) => d.length > 0 ? 3 : 0)
          .attr('stroke-dasharray', (d) => {
            if (d.length > 0) {
              // 检查是否包含异常
              const hasAnomaly = d.some(idx => {
                const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
                return result && result.isAnomaly;
              });

              if (hasAnomaly) {
                return '0';
              }

              const nonAnomalyIdx = d.find(idx => {
                const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
                return result && !result.isAnomaly;
              });

              if (nonAnomalyIdx) {
                const errorData = errorResults.find(
                  result => result &&
                    result.errorIdx === nonAnomalyIdx &&
                    result.channelKey === channelKey
                );
                if (errorData && Array.isArray(errorData.errorData)) {
                  const [manualErrors] = errorData.errorData;
                  if (manualErrors && manualErrors.length > 0) {
                    // 如果store中的person为空，使用虚线
                    if (!storePerson.value) {
                      return '4 2';
                    }
                    // 检查是否同时存在自己和他人的标注
                    const hasSelfAnnotation = manualErrors.some(error => error.person === storePerson.value);
                    const hasOthersAnnotation = manualErrors.some(error => error.person !== storePerson.value);

                    // 如果只有一种标注，返回对应的样式
                    if (hasSelfAnnotation && !hasOthersAnnotation) {
                      return '0';  // 只有自己的标注，使用实线
                    } else if (!hasSelfAnnotation && hasOthersAnnotation) {
                      return '4 2';  // 只有他人的标注，使用虚线
                    }
                    // 如果同时存在两种标注，外框使用实线
                    return '0';
                  }
                }
              }
            }
            return '0';
          });
      });

    // 在所有数据处理完成后
    await Promise.allSettled(errorPromises);

    // 确保进度条显示完成
    loadingPercentage.value = 100;
    // 短暂延迟后隐藏加载状态，让用户能看到100%的进度
    setTimeout(() => {
      loading.value = false;
    });

    // 设置 SVG 元素的过渡效果
    heatmap.selectAll('.heatmapRectG')
      .style('opacity', 0)
      .transition()
      .duration(300)
      .style('opacity', 1);

    // 为矩形添加过渡效果
    heatmap.selectAll('.heatmapRect, .innerRect, .innerDashedRect')
      .style('transition', 'all 0.3s ease');

    // 恢复滚动位置
    if (container) {
      container.scrollTop = scrollTop;
    }

  } catch (error) {
    console.error('Error in renderHeatmap:', error);
    loading.value = false;
    loadingPercentage.value = 0;
  }
}

// 修改处理错误数据的辅助函数
function processErrorData(errorData, channelKey, errorIdx, visData, rectNum, Domain, step) {
  // 处理人工标注和机器识别的异常数据
  const [manualErrors, machineErrors] = errorData;

  // 处理机器识别的异常
  for (const machineError of machineErrors) {
    if (!machineError.X_error || machineError.X_error.length === 0 || machineError.X_error[0].length === 0) {
      continue; // 跳过空的错误数据
    }

    // 处理每个错误区间
    for (const idxList of machineError.X_error) {
      if (!Array.isArray(idxList) || idxList.length === 0) {
        continue;
      }

      // 处理错误数据到1KHz
      const processedErrorData = processDataTo1KHz({
        X_value: idxList,
        Y_value: new Array(idxList.length).fill(0) // Y值在这里不重要，我们只需要X值
      });

      const left = Math.floor((processedErrorData.X_value[0] - Domain[0]) / step);
      const right = Math.floor((processedErrorData.X_value[processedErrorData.X_value.length - 1] - Domain[0]) / step);

      for (let i = left; i <= right; i++) {
        if (i >= 0 && i < rectNum) {
          visData[channelKey][i].push(errorIdx);
        }
      }
    }
  }

  // 处理人工标注的异常
  for (const manualError of manualErrors) {
    if (!manualError.X_error || manualError.X_error.length === 0 || manualError.X_error[0].length === 0) {
      continue; // 跳过空的错误数据
    }

    // 处理每个错误区间
    for (const idxList of manualError.X_error) {
      if (!Array.isArray(idxList) || idxList.length === 0) {
        continue;
      }

      // 处理错误数据到1KHz
      const processedErrorData = processDataTo1KHz({
        X_value: idxList,
        Y_value: new Array(idxList.length).fill(0) // Y值在这里不重要，我们只需要X值
      });

      const left = Math.floor((processedErrorData.X_value[0] - Domain[0]) / step);
      const right = Math.floor((processedErrorData.X_value[processedErrorData.X_value.length - 1] - Domain[0]) / step);

      for (let i = left; i <= right; i++) {
        if (i >= 0 && i < rectNum) {
          visData[channelKey][i].push(errorIdx);
        }
      }
    }
  }
}

// 添加处理函数
const handleHeatmapExport = (command) => {
  if (command === 'exportSvg') {
    exportHeatMapSvg();
  } else if (command === 'exportData') {
    exportHeatMapData();
  }
}

// 在 watch 部分添加以下代码
watch(
  anomaliesByChannel,
  (newAnomalies) => {
    // 仅当有选中的通道时才进行渲染
    if (selectedChannels.value.length > 0) {
      // 使用 isOnlyAnomalyChange 参数调用渲染函数
      renderHeatmap(selectedChannels.value, true);
    }
  },
  { deep: true }
);

// 在 script setup 部分添加搜索相关的代码
const searchQuery = ref('');

// 添加搜索和排序函数
const sortedAnomalies = computed(() => {
  return anomalyDialogData.value.map(group => {
    const query = searchQuery.value.toLowerCase().trim();
    if (!query) {
      return group;
    }

    // 对异常数据进行搜索和排序
    const sortedAnomalies = [...group.anomalies].sort((a, b) => {
      const aMatch = Object.values(a).some(val => 
        String(val).toLowerCase().includes(query)
      );
      const bMatch = Object.values(b).some(val => 
        String(val).toLowerCase().includes(query)
      );
      
      if (aMatch && !bMatch) return -1;
      if (!aMatch && bMatch) return 1;
      return 0;
    });

    return {
      ...group,
      anomalies: sortedAnomalies
    };
  });
});

// 添加高亮判断函数
const isHighlighted = (anomaly) => {
  const query = searchQuery.value.toLowerCase().trim();
  if (!query) return false;
  
  return Object.values(anomaly).some(val => 
    String(val).toLowerCase().includes(query)
  );
};

// 修改 saveAnomaly 函数
const saveAnomaly = () => {
  if (currentAnomaly) {
    const payload = {
      channelName: currentAnomaly.channelName,
      anomaly: {
        ...currentAnomaly,
        anomalyCategory: decodeChineseText(currentAnomaly.anomalyCategory),
        anomalyDiagnosisName: decodeChineseText(currentAnomaly.anomalyDiagnosisName),
        anomalyDescription: decodeChineseText(currentAnomaly.anomalyDescription),
        isStored: true
      },
    };

    // 更新store中的异常数据
    store.dispatch('updateAnomaly', payload);

    // 关闭编辑框
    showAnomalyForm.value = false;

    ElMessage.success('异常标注信息已保存');

    // 清空当前异常数据
    Object.keys(currentAnomaly).forEach((key) => {
      delete currentAnomaly[key];
    });
  }
};

// 添加 deleteAnomaly 函数
const deleteAnomaly = () => {
  if (currentAnomaly && currentAnomaly.channelName && currentAnomaly.id) {
    // 从 store 中删除异常数据
    store.dispatch('deleteAnomaly', {
      channelName: currentAnomaly.channelName,
      anomalyId: currentAnomaly.id
    });

    // 关闭编辑框
    showAnomalyForm.value = false;

    ElMessage.success('异常标注已删除');

    // 清空当前异常数据
    Object.keys(currentAnomaly).forEach((key) => {
      delete currentAnomaly[key];
    });
  }
};

// 修改 closeAnomalyForm 函数
const closeAnomalyForm = () => {
  nextTick(() => {
    showAnomalyForm.value = false;
    // 清空当前异常数据
    Object.keys(currentAnomaly).forEach((key) => {
      delete currentAnomaly[key];
    });
  });
};

// 添加对 store 中 anomalies 的监听
watch(() => store.state.anomalies, (newAnomalies) => {
  // 如果当前正在编辑某个异常
  if (showAnomalyForm.value && currentAnomaly.id) {
    // 从store中获取最新数据
    const storedAnomalies = store.getters.getAnomaliesByChannel(currentAnomaly.channelName);
    const storedAnomaly = storedAnomalies.find(a => a.id === currentAnomaly.id);
    
    if (storedAnomaly) {
      // 更新currentAnomaly为最新数据
      Object.assign(currentAnomaly, storedAnomaly);
    } else {
      // 如果在store中找不到该异常（可能已被删除），关闭编辑框
      showAnomalyForm.value = false;
      Object.keys(currentAnomaly).forEach((key) => {
        delete currentAnomaly[key];
      });
    }
  }

  // 如果异常列表对话框正在显示，更新其内容
  if (showAnomalyDialog.value && anomalyDialogData.value.length > 0) {
    // 获取当前显示的通道信息
    const currentChannelData = anomalyDialogData.value[0].anomalies[0];
    if (currentChannelData && currentChannelData.channelName) {
      // 重新构建显示数据
      const manualAnomalies = [];
      const machineAnomalies = [];

      // 从 store 获取最新的异常数据
      const storedAnomalies = store.getters.getAnomaliesByChannel(currentChannelData.channelName);
      if (storedAnomalies) {
        storedAnomalies.forEach(anomaly => {
          const processedData = processObject(anomaly);
          if (Object.keys(processedData).length > 0) {
            manualAnomalies.push(processedData);
          }
        });
      }

      // 从 errorResults 中获取机器识别的异常
      const channelErrors = errorResults.filter(
        result => result.channelKey === currentChannelData.channelName && !result.isAnomaly
      );

      channelErrors.forEach(error => {
        if (Array.isArray(error.errorData)) {
          const [, machineErrors] = error.errorData;
          if (machineErrors && machineErrors.length > 0) {
            machineErrors.forEach(machineError => {
              if (machineError && Object.keys(machineError).length > 0) {
                const processedData = processObject(machineError);
                if (Object.keys(processedData).length > 0) {
                  machineAnomalies.push(processedData);
                }
              }
            });
          }
        }
      });

      // 更新对话框数据
      anomalyDialogData.value = [
        {
          type: '人工标注异常',
          anomalies: manualAnomalies
        },
        {
          type: '机器识别异常',
          anomalies: machineAnomalies
        }
      ];

      // 检查是否两种类型的异常都为空
      if (manualAnomalies.length === 0 && machineAnomalies.length === 0) {
        // 如果都为空，关闭对话框
        showAnomalyDialog.value = false;
      }
    }
  }
}, { deep: true });

// 添加编辑异常函数
const editAnomaly = (anomaly, type) => {
  if (type === '人工标注异常') {
    // 检查权限
    if (store.state.authority == 0) {
      ElMessage.warning('权限不足，无法编辑异常标注');
      return;
    }

    // 从store中获取最新的异常数据
    const storedAnomalies = store.getters.getAnomaliesByChannel(anomaly.channelName);
    const storedAnomaly = storedAnomalies.find(a => a.id === anomaly.id);
    
    if (storedAnomaly) {
      // 使用store中的数据更新currentAnomaly
      Object.assign(currentAnomaly, storedAnomaly);
      showAnomalyForm.value = true;
    }
  } else {
    ElMessage.warning('机器识别的异常不可编辑');
  }
};

// 添加从列表删除异常函数
const deleteAnomalyFromList = (anomaly, type) => {
  if (type === '人工标注异常') {
    // 检查权限
    if (store.state.authority == 0) {
      ElMessage.warning('权限不足，无法删除异常标注');
      return;
    }

    ElMessageBox.confirm(
      '确定要删除这个异常标注吗？',
      '警告',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
      .then(() => {
        store.dispatch('deleteAnomaly', {
          channelName: anomaly.channelName,
          anomalyId: anomaly.id
        });
        ElMessage.success('异常标注已删除');
      })
      .catch(() => {
        // 用户取消删除操作
      });
  } else {
    ElMessage.warning('机器识别的异常不可删除');
  }
};

// 在 script setup 的开头部分添加
const showAnomalyForm = ref(false);
const currentAnomaly = reactive({});
const timeAxisRange = computed(() => {
  if (
    currentAnomaly &&
    currentAnomaly.startX !== undefined &&
    currentAnomaly.endX !== undefined
  ) {
    return `${currentAnomaly.startX.toFixed(3)} - ${currentAnomaly.endX.toFixed(3)}`;
  }
  return '';
});

// 在 script setup 部分添加新的删除方法
const deleteErrorData = (errorData, type) => {
  // 检查权限
  if (store.state.authority == 0) {
    ElMessage.warning('权限不足，无法删除异常标注');
    return;
  }

  ElMessageBox.confirm(
    '确定要删除这个异常标注吗？',
    '警告',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  )
    .then(async () => {
      const loadingInstance = ElLoading.service({
        lock: true,
        text: '正在删除异常数据...',
        background: 'rgba(0, 0, 0, 0.7)'
      });

      try {
        const response = await fetch('https://10.1.108.19:5000/api/delete-error-data/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            diagnostic_name: errorData.diagnostic_name,
            channel_number: errorData.channel_number,
            shot_number: errorData.shot_number,
            error_type: errorData.error_type
          })
        });

        if (!response.ok) {
          throw new Error('删除失败');
        }

        // 删除成功后刷新数据
        await store.dispatch('refreshStructTreeData');
        ElMessage.success('异常标注已删除');

        // 关闭对话框
        showAnomalyDialog.value = false;
      } catch (error) {
        console.error('删除失败:', error);
        ElMessage.error('删除失败: ' + error.message);
      } finally {
        // 无论成功还是失败，都关闭加载状态
        loadingInstance.close();
      }
    })
    .catch(() => {
      // 用户取消删除操作
    });
};
</script>

<style scoped lang="scss">
.heatmap-section {
  display: flex;
  flex-direction: column;
  width: 100%;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.heatmap-scrollbar {
  width: 100%;
  flex: 1;
}

.heatmap-container {
  width: 100%;
  height: 100%;
  overflow: hidden; // 确保没有溢出
}

#heatmap {
  width: 100%;
  height: 100%;
}

.anomaly-dialog {
  width: 90% !important;
  max-width: 1400px;

  :deep(.el-dialog__header) {
    padding: 16px 24px;
    margin: 0;
    border-bottom: 1px solid #e0e0e0;
  }

  :deep(.el-dialog__title) {
    font-size: 20px;
    color: #202124;
    font-weight: 500;
  }

  :deep(.el-dialog__body) {
    padding: 16px 24px;
  }
}

.search-container {
  padding: 0 0 16px;
  border-bottom: 1px solid #e0e0e0;
  margin-bottom: 16px;

  .el-input {
    width: 320px;

    :deep(.el-input__wrapper) {
      box-shadow: none;
      border: 1px solid #e0e0e0;
      border-radius: 8px;
      transition: all 0.3s ease;

      &:hover {
        border-color: #bdbdbd;
      }

      &.is-focus {
        border-color: #1a73e8;
        box-shadow: 0 1px 2px 0 rgba(26,115,232,0.3);
      }
    }

    :deep(.el-input__inner) {
      &::placeholder {
        color: #5f6368;
      }
    }
  }
}

.anomaly-container {
  display: flex;
  margin-top: 10px;
  gap: 20px;
  min-height: 45vh;
}

.anomaly-group {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  width: 50%;
  max-width: 50%;
}

.group-title {
  margin: 0 0 12px 0;
  padding: 8px 16px;
  background-color: #f8f9fa;
  border-left: 4px solid #1a73e8;
  font-size: 16px;
  font-weight: 500;
  color: #202124;
  border-radius: 0 8px 8px 0;
}

.anomaly-content {
  padding: 0 10px;
}

.anomaly-item {
  margin-bottom: 12px;
  transition: all 0.2s ease;
  position: relative;

  &:last-child {
    margin-bottom: 0;
  }

  &.highlight {
    transform: translateY(-1px);

    :deep(.el-card) {
      border-color: #1a73e8;
      box-shadow: 0 2px 6px 2px rgba(26,115,232,0.15);
    }

    :deep(.el-descriptions__body) {
      background-color: #f3f8fe;
    }
  }

  :deep(.el-card) {
    border-radius: 8px;
    transition: all 0.2s ease;
    border: 1px solid #e0e0e0;
    box-shadow: 0 1px 2px 0 rgba(60,64,67,0.1);
    overflow: visible;
    padding-bottom: 8px; // 为底部图标留出空间

    &:hover {
      box-shadow: 0 2px 8px 0 rgba(60,64,67,0.15);
      
      .anomaly-bookmark {
        transform: translateY(-2px); // 悬停时向上移动
      }
    }
  }
}

.anomaly-bookmark {
  position: absolute;
  top: auto; // 取消顶部定位
  bottom: -6px; // 改为底部定位
  right: -6px; // 调整右侧位置
  opacity: 1;
  transition: all 0.2s ease;
  z-index: 1;
}

.bookmark-actions {
  display: flex;
  gap: 4px; // 减小图标间距
  background: white;
  padding: 4px; // 减小内边距
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.action-icon {
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s ease;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px; // 减小宽度
  height: 24px; // 减小高度
  
  &.edit-icon {
    color: #409EFF;
    
    &:hover {
      background-color: rgba(64,158,255,0.1);
      transform: scale(1.1);
    }
  }
  
  &.delete-icon {
    color: #F56C6C;
    
    &:hover {
      background-color: rgba(245,108,108,0.1);
      transform: scale(1.1);
    }
  }
}

.anomaly-descriptions {
  width: 100%;

  :deep(.el-descriptions__body) {
    background-color: #fff;
  }

  :deep(.el-descriptions__label) {
    width: 120px;
    min-width: 120px;
    max-width: 120px;
    padding: 8px 12px !important;
    background-color: #fafafa;
    font-size: 14px;
    color: #606266;
    font-weight: normal;
  }

  :deep(.el-descriptions__content) {
    padding: 8px 12px !important;
    font-size: 14px;
    color: #303133;
  }

  :deep(.el-descriptions__cell) {
    padding: 0 !important;
  }

  :deep(.el-descriptions__table) {
    border-collapse: collapse;
    margin: 0;
    border: none;
  }

  :deep(.el-descriptions__row) {
    border-bottom: 1px solid #f0f0f0;
    
    &:last-child {
      border-bottom: none;
    }
  }
}

.title {
  color: #999;
}

.channelName {
  font-size: 12px;
  fill: #333;
}

.xTick {
  font-size: 10px;
  fill: #666;
}

.progress-wrapper {
  margin: 20px 0;
  padding: 0 10px;
}

.progress-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  font-size: 13px;
  color: #606266;
}

.progress-percentage {
  font-weight: bold;
  color: #409EFF;
}

:deep(.el-progress-bar__outer) {
  background-color: #f0f2f5;
  border-radius: 4px;
}

:deep(.el-progress-bar__inner) {
  transition: width 0.3s ease;
  border-radius: 4px;
}

:deep(.el-progress--line) {
  margin-bottom: 0;
}

/* 修改进度条成功状态的颜色 */
:deep(.el-progress.is-success .el-progress-bar__inner) {
  background-color: #67C23A;
}

:deep(.el-progress-bar__innerText) {
  font-size: 12px;
  margin: 0 5px;
  color: #fff;
}

/* 让输入框内的文字可以选中 */
.el-input {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让输入框内的文字可以选中 */
.el-input__inner {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让对话框中的输入框文字可以选中 */
.el-dialog .el-input {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

.anomaly-group {
  margin-bottom: 20px;
}

.group-title {
  margin: 10px 0;
  padding: 5px 10px;
  background-color: #f5f7fa;
  border-left: 4px solid #409EFF;
  font-size: 16px;
  font-weight: bold;
}

.anomaly-item {
  margin-bottom: 15px;

  &:last-child {
    margin-bottom: 0;
  }
}

.empty-message {
  padding: 24px;
  text-align: center;
  color: #5f6368;
  font-size: 14px;
  background-color: #f8f9fa;
  border-radius: 8px;
}

// 修改滚动条样式
.el-scrollbar {
  :deep(.el-scrollbar__bar) {
    &.is-horizontal {
      height: 8px;
    }
    &.is-vertical {
      width: 8px;
    }

    .el-scrollbar__thumb {
      background-color: rgba(95,99,104,0.3);
      border-radius: 4px;

      &:hover {
        background-color: rgba(95,99,104,0.5);
      }
    }
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.anomaly-card-header {
  display: flex;
  justify-content: flex-end;
  padding: 8px 16px;
  border-bottom: 1px solid #e0e0e0;
}

.anomaly-actions {
  display: flex;
  gap: 8px;
}

:deep(.el-button--small) {
  padding: 6px 12px;
  font-size: 12px;
}
</style>
 color: #409EFF;
}

:deep(.el-progress-bar__outer) {
  background-color: #f0f2f5;
  border-radius: 4px;
}

:deep(.el-progress-bar__inner) {
  transition: width 0.3s ease;
  border-radius: 4px;
}

:deep(.el-progress--line) {
  margin-bottom: 0;
}

/* 修改进度条成功状态的颜色 */
:deep(.el-progress.is-success .el-progress-bar__inner) {
  background-color: #67C23A;
}

:deep(.el-progress-bar__innerText) {
  font-size: 12px;
  margin: 0 5px;
  color: #fff;
}

/* 让输入框内的文字可以选中 */
.el-input {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让输入框内的文字可以选中 */
.el-input__inner {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让对话框中的输入框文字可以选中 */
.el-dialog .el-input {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

.anomaly-group {
  margin-bottom: 20px;
}

.group-title {
  margin: 10px 0;
  padding: 5px 10px;
  background-color: #f5f7fa;
  border-left: 4px solid #409EFF;
  font-size: 16px;
  font-weight: bold;
}

.anomaly-item {
  margin-bottom: 15px;

  &:last-child {
    margin-bottom: 0;
  }
}

.empty-message {
  padding: 24px;
  text-align: center;
  color: #5f6368;
  font-size: 14px;
  background-color: #f8f9fa;
  border-radius: 8px;
}

// 修改滚动条样式
.el-scrollbar {
  :deep(.el-scrollbar__bar) {
    &.is-horizontal {
      height: 8px;
    }
    &.is-vertical {
      width: 8px;
    }

    .el-scrollbar__thumb {
      background-color: rgba(95,99,104,0.3);
      border-radius: 4px;

      &:hover {
        background-color: rgba(95,99,104,0.5);
      }
    }
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.anomaly-card-header {
  display: flex;
  justify-content: flex-end;
  padding: 8px 16px;
  border-bottom: 1px solid #e0e0e0;
}

.anomaly-actions {
  display: flex;
  gap: 8px;
}

:deep(.el-button--small) {
  padding: 6px 12px;
  font-size: 12px;
}
</style>
