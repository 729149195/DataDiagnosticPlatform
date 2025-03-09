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
            <el-progress :percentage="loadingPercentage" :stroke-width="10" :status="loadingPercentage === 100 ? 'success' : ''" />
          </div>
          <div class="heatmap-container" :style="{ opacity: loading ? 0 : 1, transition: 'opacity 0.3s ease' }">
            <svg id="heatmap" ref="HeatMapRef" preserveAspectRatio="xMidYMid slice"></svg>
          </div>
        </div>
      </el-scrollbar>
    </div>
    <el-dialog v-model="showAnomalyDialog" :modal="true" :close-on-click-modal="false" @close="handleDialogClose" :destroy-on-close="true" class="anomaly-dialog">
      <template #header>
        <div class="dialog-header">
          <div class="dialog-title">
            <span>异常信息详情</span>
          </div>
        </div>
      </template>
      <div class="search-container">
        <el-input v-model="searchQuery" placeholder="输入任一连续关键词搜索异常信息..." clearable>
          <template #prefix>
            <el-icon class="search-icon">
              <Search />
            </el-icon>
          </template>
        </el-input>
      </div>
      <div class="anomaly-container">
        <div v-for="(group, groupIndex) in sortedAnomalies" :key="groupIndex" class="anomaly-group">
          <div class="group-title">{{ group.type }}</div>
          <el-scrollbar height="45vh" :always="false">
            <div class="anomaly-content">
              <template v-if="group.anomalies.length > 0">
                <div v-for="(anomaly, index) in group.anomalies" :key="index" class="anomaly-item" :class="{ 'highlight': isHighlighted(anomaly) }">
                  <el-card shadow="hover" :body-style="{ padding: '12px' }">
                    <!-- 修改操作按钮位置为绝对定位在右上角 -->
                    <div class="card-actions">
                      <el-icon v-if="anomaly.id || anomaly.ID" class="action-icon edit-icon" @click="editAnomaly(anomaly, group.type)">
                        <Edit />
                      </el-icon>
                      <el-icon class="action-icon delete-icon" @click="(anomaly.id || anomaly.ID) ? deleteAnomalyFromList(anomaly, group.type) : deleteErrorData(anomaly, group.type)">
                        <Delete />
                      </el-icon>
                    </div>
                    
                    <div class="statistic-layout">
                      <!-- 第一行：责任人和通道名称 -->
                      <div class="statistic-row">
                        <div class="statistic-item">
                          <div class="statistic-title">责任人</div>
                          <div class="statistic-value">
                            <el-tag size="small" :type="anomaly['责任人'] === storePerson.value ? 'success' : 'info'" effect="light">
                              {{ formatValue(anomaly['责任人'], '责任人') }}
                            </el-tag>
                            <!-- 标注时间作为小注释 -->
                            <div v-if="anomaly['标注时间']" class="statistic-note">
                              {{ formatValue(anomaly['标注时间'], '标注时间') }}
                            </div>
                          </div>
                        </div>
                        <div class="statistic-item">
                          <div class="statistic-title">通道名称</div>
                          <div class="statistic-value code-style">
                            {{ formatValue(anomaly['通道名称'], '通道名称') }}
                          </div>
                        </div>
                      </div>
                      
                      <!-- 第二行：异常类别和诊断名 -->
                      <div class="statistic-row">
                        <div class="statistic-item">
                          <div class="statistic-title">异常类别</div>
                          <div class="statistic-value">
                            <span class="wrap-tag">
                              {{ formatValue(anomaly['异常类别'] || anomaly['错误类型'], '异常类别') }}
                            </span>
                          </div>
                        </div>
                        <div class="statistic-item">
                          <div class="statistic-title">诊断名</div>
                          <div class="statistic-value code-style">
                            {{ formatValue(anomaly['诊断名称'] || anomaly['异常诊断名称'], '诊断名称') }}
                          </div>
                        </div>
                      </div>
                      
                      <div class="statistic-row">
                        <div class="statistic-item full-width">
                          <div class="statistic-title">异常描述</div>
                          <div class="statistic-value description">
                            <span v-if="formatValue(anomaly['异常描述'] || anomaly['错误描述'], '异常描述') === '无' || formatValue(anomaly['异常描述'] || anomaly['错误描述'], '异常描述') === ''" class="empty-value">
                              暂无描述
                            </span>
                            <span v-else>
                              {{ formatValue(anomaly['异常描述'] || anomaly['错误描述'], '异常描述') }}
                            </span>
                          </div>
                        </div>
                      </div>

                       <!-- 修改时间范围行，使标题和值在同一行 -->
                       <div class="statistic-row time-row">
                        <div class="time-title">异常时间范围:</div>
                        <div class="time-value">{{ formatValue(anomaly['时间范围'], '时间范围') }} s</div>
                      </div>
                    </div>
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
import { ElDialog, ElMessage, ElMessageBox, ElLoading } from 'element-plus';
import pLimit from 'p-limit';
import debounce from 'lodash/debounce';  // 添加 debounce 导入
import { Search, Delete, Edit, InfoFilled } from '@element-plus/icons-vue';

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
        let value = obj[key];

        // 对字符串类型的值进行解码
        if (typeof value === 'string') {
          value = decodeChineseText(value);
        }

        // 处理所有字段，包括X_error和Y_error
        newObj[key] = processObject(value);
      }
    }
    
    // 特殊处理某些字段，确保它们能正确显示
    if (obj.anomalyCategory) {
      newObj['异常类别'] = obj.anomalyCategory;
    }
    
    if (obj.anomalyDiagnosisName) {
      newObj['诊断名称'] = obj.anomalyDiagnosisName;
    }
    
    if (obj.anomalyDescription) {
      newObj['异常描述'] = obj.anomalyDescription;
    }
    
    if (obj.channelName) {
      newObj['通道名称'] = obj.channelName;
    }
    
    if (obj.diagnostic_name) {
      newObj['诊断名称'] = obj.diagnostic_name;
    }
    
    // 处理时间范围
    if (obj.startX !== undefined && obj.endX !== undefined) {
      newObj['时间范围'] = `[ ${parseFloat(obj.startX).toFixed(4)} —— ${parseFloat(obj.endX).toFixed(4)} ]`;
    }
    
    // 处理X_error字段，转换为时间范围
    if (obj.X_error && Array.isArray(obj.X_error) && obj.X_error.length > 0) {
      const timeRanges = obj.X_error.map(range => {
        if (Array.isArray(range) && range.length >= 2) {
          return `[ ${parseFloat(range[0]).toFixed(4)} —— ${parseFloat(range[1]).toFixed(4)} ]`;
        }
        return null;
      }).filter(Boolean);

      if (timeRanges.length > 0) {
        newObj['时间范围'] = timeRanges.join(', ');
      }
    }
    
    // 处理标注时间
    if (obj.annotationTime) {
      // 格式化时间为可读格式
      const date = new Date(obj.annotationTime);
      newObj['标注时间'] = date.toLocaleString();
    } else if (obj.timestamp && obj.person !== 'machine') {
      // 如果有timestamp字段，也可以用它
      const date = new Date(obj.timestamp);
      newObj['标注时间'] = date.toLocaleString();
    }
    
    // 处理诊断时间
    if (obj.diagnostic_time) {
      // 格式化时间为可读格式
      const date = new Date(obj.diagnostic_time);
      newObj['诊断时间'] = date.toLocaleString();
    } else if (obj.timestamp && obj.person === 'machine') {
      // 如果有timestamp字段，也可以用它
      const date = new Date(obj.timestamp);
      newObj['诊断时间'] = date.toLocaleString();
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
    annotationTime: '标注时间',
    '时间范围': '时间范围'
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
      globalXMax = 5;
    }

    // 全移除边距
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
            if (d.length === 0) {
              return '#f5f5f5'; // 正常数据颜色
            }

            // 如果有多个异常，需要检查是否为同一类型的异常
            if (d.length > 1) {
              // 获取该区域内所有异常的类型
              const errorTypes = new Set();
              
              for (const errorIdx of d) {
                const errorData = errorResults.find(
                  (result) => result && result.errorIdx === errorIdx && result.channelKey === channelKey
                );
                
                if (errorData) {
                  // 对于机器识别的异常，使用错误名称作为类型标识
                  if (!errorData.isAnomaly && Array.isArray(errorData.errorData)) {
                    const [, machineErrors] = errorData.errorData;
                    if (machineErrors && machineErrors.length > 0) {
                      // 使用错误名称作为类型标识
                      const errorName = machineErrors[0].error_name || 'unknown';
                      errorTypes.add(errorName);
                    }
                  } else if (errorData.isAnomaly) {
                    // 对于用户标注的异常，使用固定的类型标识
                    errorTypes.add('user_anomaly');
                  }
                }
              }
              
              // 如果只有一种类型的异常，使用第一个异常的颜色
              if (errorTypes.size === 1) {
                return errorColors[d[0]];
              }
              
              // 如果有多种类型的异常，使用灰色
              return '#999999';
            }

            // 只有一个异常的情况
            const errorIdx = d[0];
            const errorData = errorResults.find(
              (result) => result && result.errorIdx === errorIdx && result.channelKey === channelKey
            );

            // 如果是机器识别的异常，使用对应的颜色
            if (errorData && !errorData.isAnomaly && Array.isArray(errorData.errorData)) {
              const [, machineErrors] = errorData.errorData;
              if (machineErrors && machineErrors.length > 0) {
                return errorColors[errorIdx];
              }
            }

            // 其他情况使用默认颜色
            return '#f5f5f5';
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

            // 提取并格式化所有错误信息
            const processErrorData = (errorData) => {
              // 创建一个新的处理后的数据对象
              const processedData = {};
              
              // 深拷贝数据以避免引用问题
              const errorDataCopy = JSON.parse(JSON.stringify(errorData));

              // 处理X_error和Y_error字段，转换为时间范围
              if (errorDataCopy.X_error && Array.isArray(errorDataCopy.X_error) && errorDataCopy.X_error.length > 0) {
                // 提取所有时间范围
                const timeRanges = errorDataCopy.X_error.map(range => {
                  if (Array.isArray(range) && range.length >= 2) {
                    return `[ ${parseFloat(range[0]).toFixed(4)} —— ${parseFloat(range[1]).toFixed(4)} ]`;
                  }
                  return null;
                }).filter(Boolean);

                if (timeRanges.length > 0) {
                  processedData['时间范围'] = timeRanges.join(', ');
                }
              }

              // 对于前端标注的异常，使用startX和endX
              if (errorDataCopy.startX !== undefined && errorDataCopy.endX !== undefined) {
                processedData['时间范围'] = `[ ${parseFloat(errorDataCopy.startX).toFixed(4)} —— ${parseFloat(errorDataCopy.endX).toFixed(4)} ]`;
              }

              // 处理其他字段
              Object.keys(errorDataCopy).forEach((key) => {
                // 跳过X_error和Y_error，因为已经单独处理
                if (key === 'X_error' || key === 'Y_error') return;

                let value = errorDataCopy[key];

                // 处理特殊的中文字符编码
                if (typeof value === 'string') {
                  value = decodeChineseText(value);
                }

                const formattedValue = formatValue(value, key);
                if (formattedValue !== undefined && formattedValue !== null && formattedValue !== '') {
                  // 使用格式化的键名
                  const formattedKey = formatKey(key);
                  processedData[formattedKey] = formattedValue;
                }
              });

              // 处理时间字段
              if (processedData['责任人'] === 'machine' && processedData['诊断时间']) {
                processedData['诊断时间'] = formatValue(processedData['诊断时间'], 'diagnostic_time');
              }

              if (processedData['责任人'] !== 'machine' && processedData['标注时间']) {
                processedData['标注时间'] = formatValue(processedData['标注时间'], 'annotationTime');
              }
              
              // 确保异常类别和诊断名称正确显示
              if (errorDataCopy.anomalyCategory) {
                processedData['异常类别'] = errorDataCopy.anomalyCategory;
              }
              
              if (errorDataCopy.anomalyDiagnosisName) {
                processedData['诊断名称'] = errorDataCopy.anomalyDiagnosisName;
              }
              
              // 确保异常描述正确显示
              if (errorDataCopy.anomalyDescription) {
                processedData['异常描述'] = errorDataCopy.anomalyDescription;
              }
              
              // 确保通道名称正确显示
              if (errorDataCopy.channelName) {
                processedData['通道名称'] = errorDataCopy.channelName;
              }
              
              // 确保标注时间正确显示
              if (errorDataCopy.annotationTime) {
                // 格式化时间为可读格式
                const date = new Date(errorDataCopy.annotationTime);
                processedData['标注时间'] = date.toLocaleString();
              } else if (errorDataCopy.timestamp && processedData['责任人'] !== 'machine') {
                // 如果有timestamp字段，也可以用它
                const date = new Date(errorDataCopy.timestamp);
                processedData['标注时间'] = date.toLocaleString();
              }
              
              // 确保诊断时间正确显示
              if (errorDataCopy.diagnostic_time) {
                // 格式化时间为可读格式
                const date = new Date(errorDataCopy.diagnostic_time);
                processedData['诊断时间'] = date.toLocaleString();
              } else if (errorDataCopy.timestamp && processedData['责任人'] === 'machine') {
                // 如果有timestamp字段，也可以用它
                const date = new Date(errorDataCopy.timestamp);
                processedData['诊断时间'] = date.toLocaleString();
              }

              return processedData;
            };

            // 分离人工标注和机器识别的异常
            const manualAnomalies = [];
            const machineAnomalies = [];
            // 使用Map来存储唯一的机器识别异常，避免重复
            const machineAnomalyMap = new Map();

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
                  // 创建一个深拷贝
                  const errorDataCopy = JSON.parse(JSON.stringify(error.errorData));
                  const [manualErrors, machineErrors] = errorDataCopy;

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
                        const processedData = processErrorData(machineError);
                        
                        // 确保通道名称正确显示
                        if (!processedData['通道名称']) {
                          processedData['通道名称'] = error.channelKey;
                        }
                        
                        if (Object.keys(processedData).length > 0) {
                          // 使用时间范围作为唯一标识符
                          const key = processedData['时间范围'] || JSON.stringify(machineError);
                          if (!machineAnomalyMap.has(key)) {
                            machineAnomalyMap.set(key, processedData);
                          }
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
                      // 使用时间范围作为唯一标识符
                      const key = processedData['时间范围'] || JSON.stringify(error.errorData);
                      if (!machineAnomalyMap.has(key)) {
                        machineAnomalyMap.set(key, processedData);
                      }
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

            // 将Map中的值转换为数组
            const uniqueMachineAnomalies = Array.from(machineAnomalyMap.values());

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
            if (d.length === 0) return 'none';

            // 检查是否有多个异常
            if (d.length > 1) {
              // 检查是否同时存在自己和他人的标注
              const hasMultiplePersons = d.some(idx => {
                const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
                if (!result || result.isAnomaly) return false;

                if (Array.isArray(result.errorData)) {
                  const [manualErrors] = result.errorData;
                  return manualErrors && manualErrors.some(error => error.person === storePerson.value) &&
                    manualErrors.some(error => error.person !== storePerson.value);
                }
                return false;
              });

              return hasMultiplePersons ? 'red' : 'none';
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
            if (d.length === 0) return 'none';

            // 检查是否包含前端标注的异常
            const hasAnomaly = d.some(idx => {
              const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
              return result && result.isAnomaly;
            });

            if (hasAnomaly) {
              return 'orange'; // 前端标注的异常使用橙色边框
            }

            // 检查是否包含后端返回的人工标注异常
            const hasManualError = d.some(idx => {
              const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
              if (!result || result.isAnomaly) return false;

              if (Array.isArray(result.errorData)) {
                const [manualErrors] = result.errorData;
                return manualErrors && manualErrors.length > 0;
              }
              return false;
            });

            if (hasManualError) {
              return 'red'; // 人工标注的异常使用红色边框
            }

            return 'none';
          })
          .attr('stroke-width', (d) => d.length > 0 ? 3 : 0)
          .attr('stroke-dasharray', (d) => {
            if (d.length === 0) return '0';

            // 检查是否包含前端标注的异常
            const hasAnomaly = d.some(idx => {
              const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
              return result && result.isAnomaly;
            });

            if (hasAnomaly) {
              return '0'; // 前端标注的异常使用实线
            }

            // 检查人工标注的异常
            for (const idx of d) {
              const result = errorResults.find(r => r.errorIdx === idx && r.channelKey === channelKey);
              if (!result || result.isAnomaly) continue;

              if (Array.isArray(result.errorData)) {
                const [manualErrors] = result.errorData;
                if (!manualErrors || manualErrors.length === 0) continue;

                // 如果store中的person为空，使用虚线
                if (!storePerson.value) {
                  return '4 2';
                }

                // 检查是否包含当前用户的标注
                const hasSelfAnnotation = manualErrors.some(error => error.person === storePerson.value);

                // 如果包含当前用户的标注，使用实线，否则使用虚线
                return hasSelfAnnotation ? '0' : '4 2';
              }
            }

            return '0'; // 默认使用实线
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

      // idxList 已经是处理好的数组，只包含错误区间的头尾两个值
      const startX = idxList[0];
      const endX = idxList[1];

      // 计算对应的矩形索引范围
      const left = Math.floor((startX - Domain[0]) / step);
      const right = Math.floor((endX - Domain[0]) / step);

      // 将错误索引添加到对应的矩形中
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

      // idxList 已经是处理好的数组，只包含错误区间的头尾两个值
      const startX = idxList[0];
      const endX = idxList[1];

      // 计算对应的矩形索引范围
      const left = Math.floor((startX - Domain[0]) / step);
      const right = Math.floor((endX - Domain[0]) / step);

      // 将错误索引添加到对应的矩形中
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
    
    // 如果异常列表对话框正在显示，立即更新其内容
    if (showAnomalyDialog.value) {
      // 延迟一点执行更新，确保store中的数据已更新
      setTimeout(() => {
        updateAnomalyDialogContent();
      }, 100);
    }
    
    // 重新渲染热力图，确保显示最新数据
    if (selectedChannels.value.length > 0) {
      renderHeatmap(selectedChannels.value, true);
    }
  }
};

// 添加 deleteAnomaly 函数
const deleteAnomaly = () => {
  if (currentAnomaly) {
    const anomalyId = currentAnomaly.id || currentAnomaly.ID;
    const channelName = currentAnomaly.channelName || currentAnomaly.通道名称;
    
    if (!anomalyId || !channelName) {
      console.error('删除失败: 缺少必要的字段', currentAnomaly);
      ElMessage.error('删除失败: 缺少必要的字段');
      return;
    }
    
    // 从 store 中删除异常数据
    store.dispatch('deleteAnomaly', {
      channelName: channelName,
      anomalyId: anomalyId
    });

    // 关闭编辑框
    showAnomalyForm.value = false;

    ElMessage.success('异常标注已删除');

    // 清空当前异常数据
    Object.keys(currentAnomaly).forEach((key) => {
      delete currentAnomaly[key];
    });
    
    // 如果异常列表对话框正在显示，立即更新其内容
    if (showAnomalyDialog.value) {
      // 延迟一点执行更新，确保store中的数据已更新
      setTimeout(() => {
        updateAnomalyDialogContent();
      }, 100);
    }
    
    // 重新渲染热力图，确保显示最新数据
    if (selectedChannels.value.length > 0) {
      renderHeatmap(selectedChannels.value, true);
    }
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

  // 更新对话框内容
  updateAnomalyDialogContent();
}, { deep: true });

// 添加编辑异常函数
const editAnomaly = (anomaly, type) => {
  if (type === '人工标注异常') {
    // 检查权限
    if (store.state.authority == 0) {
      ElMessage.warning('权限不足，无法编辑异常标注');
      return;
    }

    // 获取 ID 和通道名称
    const anomalyId = anomaly.id || anomaly.ID;
    const channelName = anomaly.channelName || anomaly.通道名称;
    
    if (!anomalyId || !channelName) {
      console.error('编辑失败: 缺少必要的字段', anomaly);
      ElMessage.error('编辑失败: 缺少必要的字段');
      return;
    }

    // 从store中获取最新的异常数据
    const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
    const storedAnomaly = storedAnomalies.find(a => a.id === anomalyId || a.ID === anomalyId);

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
        // 检查是否有 ID 字段
        const anomalyId = anomaly.id || anomaly.ID;
        const channelName = anomaly.channelName || anomaly.通道名称;
        
        if (!anomalyId || !channelName) {
          console.error('删除失败: 缺少必要的字段', anomaly);
          ElMessage.error('删除失败: 缺少必要的字段');
          return;
        }
        
        store.dispatch('deleteAnomaly', {
          channelName: channelName,
          anomalyId: anomalyId
        });
        ElMessage.success('异常标注已删除');
        
        // 立即更新对话框内容
        updateAnomalyDialogContent();
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
        // 打印错误数据，帮助调试
        console.log('要删除的异常数据:', errorData);
        
        // 处理字段名称映射，确保使用正确的字段名
        const requestData = {
          diagnostic_name: errorData.diagnostic_name || errorData.诊断名称,
          channel_number: errorData.channel_number || errorData.通道编号,
          shot_number: errorData.shot_number || errorData.炮号,
          error_type: errorData.error_type || errorData.错误类型
        };
        
        console.log('处理后的请求数据:', requestData);

        // 检查是否所有必要字段都存在
        if (!requestData.diagnostic_name || !requestData.channel_number ||
            !requestData.shot_number || !requestData.error_type) {
          console.error('删除失败: 缺少必要的字段', errorData);
          throw new Error('删除失败: 缺少必要的字段');
        }

        const response = await fetch('https://10.1.108.19:5000/api/delete-error-data/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(requestData)
        });

        if (!response.ok) {
          const errorText = await response.text();
          console.error('服务器返回错误:', errorText);
          throw new Error('删除失败');
        }

        // 删除成功后刷新数据
        await store.dispatch('refreshStructTreeData');
        ElMessage.success('异常标注已删除');

        // 关闭对话框
        showAnomalyDialog.value = false;
        
        // 立即更新对话框内容
        updateAnomalyDialogContent();
      } catch (error) {
        console.error('删除失败:', error);
        ElMessage.error('删除失败: ' + error.message);
      } finally {
        loadingInstance.close();
      }
    })
    .catch(() => {
      // 用户取消删除操作
    });
};

// 添加一个新的函数用于更新对话框内容
const updateAnomalyDialogContent = () => {
  // 如果异常列表对话框正在显示，更新其内容
  if (showAnomalyDialog.value && anomalyDialogData.value.length > 0) {
    // 获取当前显示的通道信息
    const currentChannelData = anomalyDialogData.value[0].anomalies[0];
    if (currentChannelData && (currentChannelData.channelName || currentChannelData.通道名称)) {
      // 获取通道名称
      const channelName = currentChannelData.channelName || currentChannelData.通道名称;
      
      // 重新构建显示数据
      const manualAnomalies = [];
      const machineAnomalies = [];

      // 从 store 获取最新的异常数据
      const storedAnomalies = store.getters.getAnomaliesByChannel(channelName);
      if (storedAnomalies && storedAnomalies.length > 0) {
        storedAnomalies.forEach(anomaly => {
          // 深拷贝异常数据，避免引用问题
          const anomalyCopy = JSON.parse(JSON.stringify(anomaly));
          const processedData = processObject(anomalyCopy);
          
          // 确保时间范围格式正确
          if (anomalyCopy.startX !== undefined && anomalyCopy.endX !== undefined) {
            processedData['时间范围'] = `[ ${parseFloat(anomalyCopy.startX).toFixed(4)} —— ${parseFloat(anomalyCopy.endX).toFixed(4)} ]`;
          }
          
          // 确保异常类别和诊断名称正确显示
          if (anomalyCopy.anomalyCategory) {
            processedData['异常类别'] = anomalyCopy.anomalyCategory;
          }
          
          if (anomalyCopy.anomalyDiagnosisName) {
            processedData['诊断名称'] = anomalyCopy.anomalyDiagnosisName;
          }
          
          // 确保异常描述正确显示
          if (anomalyCopy.anomalyDescription) {
            processedData['异常描述'] = anomalyCopy.anomalyDescription;
          }
          
          // 确保通道名称正确显示
          if (anomalyCopy.channelName) {
            processedData['通道名称'] = anomalyCopy.channelName;
          }
          
          // 确保责任人正确显示
          if (anomalyCopy.person) {
            processedData['责任人'] = anomalyCopy.person;
          }
          
          // 确保标注时间正确显示
          if (anomalyCopy.annotationTime) {
            // 格式化时间为可读格式
            const date = new Date(anomalyCopy.annotationTime);
            processedData['标注时间'] = date.toLocaleString();
          } else if (anomalyCopy.timestamp) {
            // 如果有timestamp字段，也可以用它
            const date = new Date(anomalyCopy.timestamp);
            processedData['标注时间'] = date.toLocaleString();
          }
          
          if (Object.keys(processedData).length > 0) {
            manualAnomalies.push(processedData);
          }
        });
      }

      // 从 errorResults 中获取机器识别的异常
      // 使用一个Map来存储唯一的机器识别异常，避免重复
      const machineAnomalyMap = new Map();
      
      const channelErrors = errorResults.filter(
        result => result.channelKey === channelName && !result.isAnomaly
      );

      channelErrors.forEach(error => {
        if (Array.isArray(error.errorData)) {
          // 创建深拷贝以避免引用问题
          const errorDataCopy = JSON.parse(JSON.stringify(error.errorData));
          const [, machineErrors] = errorDataCopy;
          
          if (machineErrors && machineErrors.length > 0) {
            machineErrors.forEach(machineError => {
              if (machineError && Object.keys(machineError).length > 0) {
                // 深拷贝机器异常数据，避免引用问题
                const machineErrorCopy = JSON.parse(JSON.stringify(machineError));
                const processedData = processObject(machineErrorCopy);
                
                // 确保时间范围格式正确
                if (machineErrorCopy.X_error && Array.isArray(machineErrorCopy.X_error) && machineErrorCopy.X_error.length > 0) {
                  const timeRanges = machineErrorCopy.X_error.map(range => {
                    if (Array.isArray(range) && range.length >= 2) {
                      return `[ ${parseFloat(range[0]).toFixed(4)} —— ${parseFloat(range[1]).toFixed(4)} ]`;
                    }
                    return null;
                  }).filter(Boolean);

                  if (timeRanges.length > 0) {
                    processedData['时间范围'] = timeRanges.join(', ');
                  }
                }
                
                // 确保责任人正确显示
                if (machineErrorCopy.person) {
                  processedData['责任人'] = machineErrorCopy.person;
                } else {
                  processedData['责任人'] = 'machine';
                }
                
                // 确保诊断名称正确显示
                if (machineErrorCopy.diagnostic_name) {
                  processedData['诊断名称'] = machineErrorCopy.diagnostic_name;
                }
                
                // 确保通道名称正确显示
                if (machineErrorCopy.channelName) {
                  processedData['通道名称'] = machineErrorCopy.channelName;
                } else {
                  processedData['通道名称'] = channelName;
                }
                
                // 确保诊断时间正确显示
                if (machineErrorCopy.diagnostic_time) {
                  // 格式化时间为可读格式
                  const date = new Date(machineErrorCopy.diagnostic_time);
                  processedData['诊断时间'] = date.toLocaleString();
                } else if (machineErrorCopy.timestamp) {
                  // 如果有timestamp字段，也可以用它
                  const date = new Date(machineErrorCopy.timestamp);
                  processedData['诊断时间'] = date.toLocaleString();
                }
                
                if (Object.keys(processedData).length > 0) {
                  // 使用时间范围作为唯一标识符
                  const key = processedData['时间范围'] || JSON.stringify(machineErrorCopy);
                  if (!machineAnomalyMap.has(key)) {
                    machineAnomalyMap.set(key, processedData);
                  }
                }
              }
            });
          }
        }
      });
      
      // 将Map中的值转换为数组
      const uniqueMachineAnomalies = Array.from(machineAnomalyMap.values());

      // 更新对话框数据
      anomalyDialogData.value = [
        {
          type: '人工标注异常',
          anomalies: manualAnomalies
        },
        {
          type: '机器识别异常',
          anomalies: uniqueMachineAnomalies
        }
      ];

      // 检查是否两种类型的异常都为空
      if (manualAnomalies.length === 0 && uniqueMachineAnomalies.length === 0) {
        // 如果都为空，关闭对话框
        showAnomalyDialog.value = false;
      }
    }
  }
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
  width: 80% !important;
  max-width: 900px;

  :deep(.el-dialog__header) {
    padding: 12px 16px;
    margin: 0;
    border-bottom: 1px solid #eaeaea;
    background-color: #f9fafc;
  }

  :deep(.el-dialog__title) {
    font-size: 16px;
    color: #303133;
    font-weight: 600;
    letter-spacing: 0.5px;
  }

  :deep(.el-dialog__body) {
    padding: 16px;
    background-color: #ffffff;
  }

  :deep(.el-dialog__headerbtn) {
    top: 12px;
    right: 12px;
  }

  :deep(.el-dialog__wrapper) {
    backdrop-filter: blur(8px);
  }

  :deep(.el-overlay-dialog) {
    background-color: rgba(0, 0, 0, 0.5);
  }
}

.search-container {
  padding: 0 0 12px;
  border-bottom: 1px solid #eaeaea;
  margin-bottom: 16px;
}

.anomaly-container {
  display: flex;
  gap: 10px;
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
  margin: 0 0 16px 0;
  padding: 12px 16px;
  background-color: #f9fafc;
  border-left: 4px solid #409EFF;
  font-size: 16px;
  font-weight: 500;
  color: #303133;
  border-radius: 0 8px 8px 0;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.anomaly-content {
  padding: 0 10px;
}

.anomaly-item {
  margin-bottom: 16px;
  transition: all 0.3s ease;
  position: relative;

  &:last-child {
    margin-bottom: 0;
  }

  &.highlight {
    transform: translateY(-2px);

    :deep(.el-card) {
      border-color: #409EFF;
      box-shadow: 0 8px 20px rgba(64, 158, 255, 0.15);
    }
  }

  :deep(.el-card) {
    border-radius: 12px;
    transition: all 0.3s ease;
    border: none;
    box-shadow: 0 4px 12px 0 rgba(0, 0, 0, 0.08);
    overflow: visible;
    position: relative;

    &:hover {
      box-shadow: 0 8px 16px 0 rgba(0, 0, 0, 0.12);
      transform: translateY(-2px);
    }

    .el-card__body {
      padding: 16px !important;
    }
  }
}

.anomaly-bookmark {
  display: none;
}

.card-actions {
  position: absolute;
  top: 8px;
  right: 8px;
  display: flex;
  gap: 8px;
  z-index: 10;
}

.wrap-tag {
  white-space: normal;
  height: auto;
  line-height: 1.5;
  padding: 4px 6px;
  word-break: break-word;
}

.anomaly-descriptions {
  width: 100%;

  :deep(.el-descriptions__body) {
    background-color: #fff;
    border-radius: 8px;
  }

  :deep(.el-descriptions__label) {
    width: 120px;
    min-width: 120px;
    max-width: 120px;
    padding: 12px 16px !important;
    background-color: #f9fafc;
    font-size: 14px;
    color: #606266;
    font-weight: 500;
    border-right: 1px solid #ebeef5;
  }

  :deep(.el-descriptions__content) {
    padding: 12px 16px !important;
    font-size: 14px;
    color: #303133;
    line-height: 1.5;
  }

  :deep(.el-descriptions__cell) {
    padding: 0 !important;
  }

  :deep(.el-descriptions__table) {
    border-collapse: collapse;
    margin: 0;
    border: none;
    width: 100%;
  }

  :deep(.el-descriptions__row) {
    border-bottom: 1px solid #ebeef5;

    &:last-child {
      border-bottom: none;
    }

    &:first-child {
      :deep(.el-descriptions__label) {
        border-top-left-radius: 8px;
      }

      :deep(.el-descriptions__content) {
        border-top-right-radius: 8px;
      }
    }

    &:last-child {
      :deep(.el-descriptions__label) {
        border-bottom-left-radius: 8px;
      }

      :deep(.el-descriptions__content) {
        border-bottom-right-radius: 8px;
      }
    }
  }
}

.empty-message {
  padding: 30px;
  text-align: center;
  color: #909399;
  font-size: 15px;
  background-color: #f9fafc;
  border-radius: 12px;
  border: 1px dashed #e0e0e0;
  margin: 10px 0;
}

// 修改滚动条样式
.el-scrollbar {
  :deep(.el-scrollbar__bar) {
    &.is-horizontal {
      height: 6px;
    }

    &.is-vertical {
      width: 6px;
    }

    .el-scrollbar__thumb {
      background-color: rgba(144, 147, 153, 0.3);
      border-radius: 3px;

      &:hover {
        background-color: rgba(144, 147, 153, 0.5);
      }
    }
  }
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.title {
  color: #333;
  font-weight: bold;
  font-size: 12pt;
  margin-left: 5px;
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
      background-color: rgba(95, 99, 104, 0.3);
      border-radius: 4px;

      &:hover {
        background-color: rgba(95, 99, 104, 0.5);
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

.time-range-value {
  font-weight: 600;
  color: #409EFF;
  background-color: rgba(64, 158, 255, 0.1);
  padding: 2px 6px;
  border-radius: 3px;
  display: inline-block;
  letter-spacing: 0.5px;
  font-size: 12px;
}

.highlight-row {
  :deep(.el-descriptions__label) {
    background-color: #ecf5ff;
    color: #409EFF;
    font-weight: 600;
  }

  :deep(.el-descriptions__content) {
    background-color: #f9fafc;
  }
}

:deep(.el-tag) {
  border-radius: 4px;
  padding: 0 6px;
  height: 20px;
  line-height: 18px;
  font-size: 12px;
  font-weight: 500;

  &.el-tag--success {
    background-color: #f0f9eb;
    border-color: #e1f3d8;
    color: #67c23a;
  }

  &.el-tag--info {
    background-color: #f4f4f5;
    border-color: #e9e9eb;
    color: #909399;
  }

  &.el-tag--warning {
    background-color: #fdf6ec;
    border-color: #faecd8;
    color: #e6a23c;
  }
}

// 添加以下样式:

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dialog-title {
  display: flex;
  align-items: center;
  font-size: 20px;
  font-weight: 600;
  color: #303133;

  .title-icon {
    margin-right: 10px;
    font-size: 22px;
    color: #409EFF;
  }
}

.search-icon {
  color: #909399;
  font-size: 18px;
}

.anomaly-info-container {
  display: table;
  width: 100%;
  border-collapse: separate;
  border-spacing: 0 4px;
}

.anomaly-info-item {
  display: table-row;

  &.highlight-item {
    .info-label {
      background-color: #ecf5ff;
      color: #409EFF;
      font-weight: 600;
    }

    .info-value {
      background-color: #f9fafc;
    }
  }
}

.info-label {
  display: table-cell;
  font-weight: 600;
  color: #606266;
  font-size: 12px;
  width: 80px;
  padding: 6px 8px;
  position: relative;
  background-color: #f5f7fa;
  border-radius: 4px 0 0 4px;
  vertical-align: middle;
}

.info-value {
  display: table-cell;
  font-size: 12px;
  color: #303133;
  word-break: break-word;
  padding: 6px 10px;
  background-color: #ffffff;
  border-radius: 0 4px 4px 0;
  border: 1px solid #ebeef5;
  border-left: none;
  vertical-align: middle;

  &.code-style {
    font-family: 'Consolas', 'Monaco', monospace;
    letter-spacing: 0.5px;
    font-weight: 500;
  }

  &.error-type {
    color: #e6a23c;
    font-weight: 500;
  }

  &.person {
    font-weight: 500;
  }
}

.empty-value {
  color: #909399;
  font-size: 14px;
  font-style: italic;
}

.statistic-layout {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.statistic-row {
  display: flex;
  gap: 16px;
  
  &.time-row {
    display: flex;
    align-items: center;
    background-color: rgba(64, 158, 255, 0.05);
    padding: 6px 10px;
    border-radius: 6px;
    margin-top: -4px;
    margin-bottom: -4px;
  }
}

.time-title {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
  white-space: nowrap;
  margin-right: 8px;
}

.time-value {
  font-size: 14px;
  color: #409EFF;
  font-weight: 500;
  flex: 1;
}

.statistic-item {
  flex: 1;
  min-width: 0;
  
  &.full-width {
    width: 100%;
  }
}

.statistic-title {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
}

.statistic-value {
  font-size: 14px;
  color: #303133;
  font-weight: 500;
  word-break: break-word;
  
  &.code-style {
    font-family: 'Consolas', 'Monaco', monospace;
    letter-spacing: 0.5px;
  }
  
  &.description {
    font-size: 13px;
    font-weight: normal;
    line-height: 1.5;
    background-color: #f9fafc;
    padding: 10px;
    border-radius: 4px;
    border-left: 3px solid #e6e6e6;
  }
}

.statistic-note {
  font-size: 11px;
  color: #909399;
  margin-top: 3px;
  font-weight: normal;
}

/* 修改操作图标样式 */
.action-icon {
  cursor: pointer;
  padding: 6px;
  border-radius: 6px;
  transition: all 0.2s ease;
  font-size: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;

  &.edit-icon {
    color: #409EFF;
    background-color: rgba(64, 158, 255, 0.1);

    &:hover {
      background-color: rgba(64, 158, 255, 0.2);
      transform: scale(1.1);
    }
  }

  &.delete-icon {
    color: #F56C6C;
    background-color: rgba(245, 108, 108, 0.1);

    &:hover {
      background-color: rgba(245, 108, 108, 0.2);
      transform: scale(1.1);
    }
  }
}
</style>
