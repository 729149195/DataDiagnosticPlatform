<template>
  <div class="all-layout">
    <el-container>
      <AppHeader @button-change="selectButton" :initial-button="selectedButton" />
      <el-container>
        <el-aside class="aside">
          <div class="aside-content">
            <el-card class="filtandsearch" shadow="never">
              <span style="display: flex; margin-bottom: 5px; justify-content: space-between;">
                <span class="title">过滤器</span>
              </span>
              <Filter />
            </el-card>
            <el-card class="table" shadow="never" v-if="selectedButton === 'anay'">
              <span style="display: flex; align-items: center; margin-bottom: 5px;">
                <span class="title">可视化配置</span>
                <el-switch class="color_table_switch" v-model="color_table_value" style="--el-switch-on-color: #409EFF; --el-switch-off-color: #409EFF" active-text="通道颜色" inactive-text="异常颜色" />
              </span>
              <div class="scrollbar-container">
                <el-scrollbar :always="false">
                  <div v-if="color_table_value === true">
                    <ChannelType />
                  </div>
                  <div v-if="color_table_value === false">
                    <ExceptionType />
                  </div>
                </el-scrollbar>
              </div>
            </el-card>
            <el-card class="table" shadow="never" v-if="selectedButton === 'channel'">
              <span style="display: flex;margin-bottom: 5px; justify-content: space-between;">
                <span class="title">可视化配置</span>
              </span>
              <div class="scrollbar-container">
                <el-scrollbar :always="false">
                  <div>
                    <ChannelTypeP />
                  </div>
                </el-scrollbar>
              </div>
            </el-card>
          </div>
        </el-aside>
        <el-container>
          <el-main class="test_main" v-if="selectedButton === 'anay'">
            <el-card class="data_exploration" shadow="never">
              <span style="display: flex; align-items: center; justify-content: space-between; ">
                <span class="title">实验数据探索</span>
                <div class="control-panel">

                  <!-- 是否显示异常区域的按钮 -->
                  <div class="control-item">
                    <el-tooltip :content="showAnomaly ? '点击隐藏异常区域' : '点击显示异常区域'" placement="top">
                      <el-button circle :type="showAnomaly ? 'primary' : 'info'" @click="updateShowAnomaly(!showAnomaly)">
                        <el-icon>
                          <component :is="showAnomaly ? 'View' : 'Hide'" />
                        </el-icon>
                      </el-button>
                    </el-tooltip>
                  </div>

                  <div class="control-item">
                    <span class="control-label">采样频率</span>
                    <el-input-number v-model="sampling" :precision="2" :step="0.1" :min="0.1" :max="1000" @change="updateSampling" />
                    <span class="control-unit">KHz</span>
                  </div>

                  <!-- <div class="control-item">
                    <span class="control-label">平滑度</span>
                    <el-input-number v-model="smoothness" :precision="3" :step="0.025" :max="1" :min="0.0" @change="updateSmoothness" />
                  </div> -->

                  <div class="control-item">
                    <el-button-group>
                      <el-button :type="boxSelect ? 'primary' : 'default'" :plain="!boxSelect" @click="updateBoxSelect(true)" style="font-size: 0.9em;">
                        框选标注/编辑
                      </el-button>
                      <el-button :type="!boxSelect ? 'primary' : 'default'" :plain="boxSelect" @click="updateBoxSelect(false)" style="font-size: 0.9em;">
                        局部缩放
                      </el-button>
                    </el-button-group>
                  </div>

                  <div class="control-item">
                    <el-button-group>
                      <el-button type="primary" :plain="!SingleChannelMultiRow_channel_number" @click="toggleChannelDisplayMode(true)" style="font-size: 0.9em;">
                        单通道多行
                      </el-button>
                      <el-button type="primary" :plain="SingleChannelMultiRow_channel_number" @click="toggleChannelDisplayMode(false)" style="font-size: 0.9em;">
                        多通道单行
                      </el-button>
                    </el-button-group>
                  </div>

                  <div class="control-item">
                    <el-dropdown trigger="click" @command="handleExportCommand">
                      <el-button type="primary" class="menu-button" title="更多操作">
                        导出
                        <el-icon>
                          <Download />
                        </el-icon>
                      </el-button>
                      <template #dropdown>
                        <el-dropdown-menu>
                          <el-dropdown-item command="exportSvg">导出SVG</el-dropdown-item>
                          <el-dropdown-item command="exportData">导出数据</el-dropdown-item>
                        </el-dropdown-menu>
                      </template>
                    </el-dropdown>
                  </div>
                </div>
              </span>
              <div style="height: 100%; position: relative; display: flex; flex-direction: column;">
                <el-scrollbar :height="isSecondSectionCollapsed ? '81vh' : '50vh'" :always="false">
                  <div v-if="SingleChannelMultiRow_channel_number === true">
                    <SingleChannelMultiRow v-show="selectedChannels.length > 0" />
                  </div>
                  <div v-show="SingleChannelMultiRow_channel_number === false">
                    <MultiChannelSingleRow ref="MultiChannelRef" v-if="selectedChannels.length > 0" />
                  </div>
                </el-scrollbar>
                <OverviewBrush />
              </div>
            </el-card>

            <div class="arc-toggle-container" :style="{ marginBottom: isSecondSectionCollapsed ? '0' : '5px' }">
              <div class="arc-toggle" @click="toggleCollapse">
                <el-icon class="arc-toggle-icon">
                  <component :is="isSecondSectionCollapsed ? 'ArrowUp' : 'ArrowDown'" />
                </el-icon>
              </div>
            </div>
            <div class="two" v-show="!isSecondSectionCollapsed" v-if="selectedButton === 'anay'">
              <el-card class="two_left" shadow="never">
                <Sketch :key="selectedButton" />
              </el-card>
              <el-card class="two_right" shadow="never">
                <HeatMap ref="heatMapRef" />
              </el-card>
            </div>
          </el-main>
          <el-main class="channel_main" v-if="selectedButton === 'channel'">
            <el-card class="operator">
              <span style="display: flex;">
                <span class="title">运算符列表</span>
                <ChannelOperator />
              </span>
            </el-card>
            <div class="two">
              <el-card class="two_left" shadow="never">
                <span style="display: flex; justify-content: space-between;">
                  <span class="title">待选择通道</span>
                  <span>统一频率 <el-input-number v-model="unit_sampling" :precision="0.1" :step="10" :max="200" />
                    KHz</span>
                </span>
                <div style="display: flex; justify-content: center; align-items: center;">
                  <ChannelCards />
                </div>
              </el-card>
              <el-card class="two_right" shadow="never">
                <span class="title">通道分析公式</span>
                <ChannelStr />
              </el-card>
            </div>
            <el-card class="data_exploration" shadow="never">
              <span style="display: flex; justify-content: space-between;">
                <span class="title">通道分析结果</span>
                <span>
                  <el-dropdown trigger="click" @command="handleResultExportCommand">
                    <el-button type="primary" style="margin-right: 10px;" title="导出数据">
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
                  <el-button type="primary" :icon="FolderChecked">另存为新通道</el-button>
                </span>
              </span>
              <div style="display: flex; justify-content: center; align-items: center;">
                <div style="width: 100%">
                  <ChannelCalculationResults ref="resultRef" />
                </div>
              </div>
            </el-card>
          </el-main>
        </el-container>
      </el-container>
    </el-container>

    <!-- 添加导出配置对话框 -->
    <el-dialog v-model="showExportDialog" title="导出通道数据配置" width="600px">
      <el-form :model="exportConfig" label-width="120px">
        <el-form-item label="选择通道">
          <div class="channel-selection">
            <div class="channel-header">
              <el-checkbox v-model="allChannelsSelected" @change="toggleAllChannels">全选</el-checkbox>
              <el-button size="small" @click="resetChannelNames" :icon="Refresh" type="text">重置名称</el-button>
            </div>
            <el-scrollbar height="250px">
              <div v-for="(channel, index) in selectedChannels" :key="`${channel.channel_name}_${channel.shot_number}`" class="channel-item">
                <el-checkbox v-model="exportConfig.selectedChannelIndices[index]"></el-checkbox>
                <span class="channel-name">{{ channel.channel_name }}_{{ channel.shot_number }}</span>
                <div class="filename-input-container">
                  <el-input v-model="exportConfig.channelRenames[index]" placeholder="自定义文件名" size="small"></el-input>
                  <span class="file-extension">.json</span>
                </div>
              </div>
            </el-scrollbar>
          </div>
        </el-form-item>

        <el-form-item label="数据频率">
          <el-radio-group v-model="exportConfig.frequencyMode">
            <el-radio :value="'current'">使用当前采样频率 ({{ sampling }}KHz)</el-radio>
            <el-radio :value="'original'">使用原始频率 <el-tag type="warning" size="small">需要重新请求数据，耗时较长</el-tag></el-radio>
            <el-radio :value="'custom'">使用自定义频率 
              <el-input-number 
                v-if="exportConfig.frequencyMode === 'custom'"
                v-model="exportConfig.customFrequency" 
                :precision="2" 
                :step="0.5" 
                :min="0.1" 
                :max="1000" 
                style="width: 120px; margin-left: 10px;"
                size="small"
              />
              <span v-if="exportConfig.frequencyMode === 'custom'">KHz</span>
            </el-radio>
          </el-radio-group>
        </el-form-item>
      </el-form>

      <!-- 进度条 -->
      <div v-if="exportProgress.isExporting" class="export-progress">
        <p>{{ exportProgress.stage === 'downloading' ? '正在下载数据' : '正在打包数据' }}: {{ exportProgress.currentChannel }} ({{ exportProgress.current }}/{{ exportProgress.total }})</p>
        <el-progress :percentage="exportProgress.percentage" :format="percentageFormat"></el-progress>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showExportDialog = false">取消</el-button>
          <el-button type="primary" @click="startExportData" :loading="exportProgress.isExporting">
            导出
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, reactive } from 'vue';
import { useStore } from 'vuex';
import { FolderChecked, Upload, Menu, Refresh } from '@element-plus/icons-vue'
import { ElMessage, ElLoading } from 'element-plus'
import Highcharts from 'highcharts';
import 'highcharts/modules/boost';
import 'highcharts/modules/accessibility';
import JSZip from 'jszip'; // 导入JSZip库
import { CacheFactory } from "cachefactory"; // 导入CacheFactory
// 导入AppHeader组件
import AppHeader from '@/components/AppHeader.vue';
// 颜色配置及通道选取组件
import ChannelType from '@/components/Channel-Type.vue';
import ExceptionType from '@/components/Exception-Type.vue';
import ChannelTypeP from '@/components/Channel-Type-P.vue';
import Filter from './Filter/Filter.vue';

import MultiChannelSingleRow from '@/views/AnomalyLabelView/DataExploration/MultiChannelSingleRow.vue';
import SingleChannelMultiRow from '@/views/AnomalyLabelView/DataExploration/SingleChannelMultiRow.vue';

import HeatMap from '@/views/AnomalyLabelView/LabelResult/HeatMapResult.vue';

import Sketch from '@/views/AnomalyLabelView/Sketch/Sketch.vue';

import ChannelCards from '@/views/ChannelAnalysisView/ChannelList/ChannelCards.vue';
import ChannelOperator from '../ChannelAnalysisView/ChannelOperator/ChannelOperator.vue';
import ChannelStr from '../ChannelAnalysisView/ChannelStr/ChannelStr.vue';
import ChannelCalculationResults from '@/views/ChannelAnalysisView/ChannelCalculation/ChannelCalculationResults.vue';

import OverviewBrush from '@/components/OverviewBrush.vue';

import { ElDialog, ElForm, ElFormItem, ElCheckbox, ElRadioGroup, ElRadio, ElTag, ElScrollbar, ElProgress } from 'element-plus'

const store = useStore()
const sampling = ref(5)
const smoothness = ref(0)
const isSecondSectionCollapsed = ref(true) // 默认为折叠状态
const showAnomaly = ref(true) // 是否显示异常区域，默认显示
const chartObserver = ref(null) // 添加MutationObserver引用

const color_table_value = ref(true)
const SingleChannelMultiRow_channel_number = ref(true)
const unit_sampling = ref(10)
const selectedButton = ref('anay');

// 添加监听函数，当unit_sampling改变时更新store
watch(unit_sampling, (newValue) => {
  store.dispatch('updateUnitSampling', newValue);
});

const MultiChannelRef = ref(null)
const resultRef = ref(null)
const heatMapRef = ref(null)
const channelDataCache = computed(() => store.state.channelDataCache);
const selectedChannels = computed(() => store.state.selectedChannels);

const boxSelect = computed({
  get: () => {
    if (store.state.authority === '0') {
      return false;
    }
    return store.state.isBoxSelect;
  },
  set: (value) => {
    if (store.state.authority === '0' && value === true) {
      ElMessage({
        message: '您当前为查看者权限，无法进行标注操作',
        type: 'warning'
      });
      return;
    }
    store.dispatch('updateIsBoxSelect', value);
  }
});

// 监听权限变化，自动更新isBoxSelect状态
watch(() => store.state.authority, (newValue) => {
  if (newValue === '0') {
    store.dispatch('updateIsBoxSelect', false);
  }
});

// 确保在组件挂载时设置正确的初始状态
onMounted(() => {
  // 如果有需要，可以从localStorage或其他地方恢复上次的状态
  const savedButton = localStorage.getItem('selectedButton');
  if (savedButton) {
    selectedButton.value = savedButton;
  }

  // 恢复通道显示模式
  const savedChannelMode = localStorage.getItem('channelDisplayMode');
  if (savedChannelMode !== null) {
    SingleChannelMultiRow_channel_number.value = savedChannelMode === 'true';
  }
  
  // 恢复异常区域显示状态
  const savedShowAnomaly = localStorage.getItem('showAnomaly');
  if (savedShowAnomaly !== null) {
    showAnomaly.value = savedShowAnomaly === 'true';
  }
  
  // 创建并启动MutationObserver，监听图表变化
  setupChartObserver();
});

const selectButton = (button) => {
  selectedButton.value = button;
  localStorage.setItem('selectedButton', button);
};

// 添加保存通道显示模式的函数
const toggleChannelDisplayMode = (value) => {
  SingleChannelMultiRow_channel_number.value = value;
  localStorage.setItem('channelDisplayMode', value);
};

// 添加更新框选模式的函数
const updateBoxSelect = (value) => {
  if (store.state.authority === '0' && value === true) {
    ElMessage({
      message: '您当前为查看者权限，无法进行标注操作',
      type: 'warning'
    });
    return;
  }
  store.dispatch('updateIsBoxSelect', value);
};

const channelSvgElementsRefs = computed(() => store.state.channelSvgElementsRefs);

// 修改通用的下载函数以使用传统的文件下载方式
const downloadFile = async (blob, suggestedName, fileType = 'json') => {
  try {
    // 创建一个下载链接
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = suggestedName;
    
    // 模拟点击链接进行下载
    document.body.appendChild(link);
    link.click();
    
    // 清理
    setTimeout(() => {
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }, 100);

    // 显示成功提示
    ElMessage({
      message: '文件保存成功',
      type: 'success',
    });
  } catch (err) {
    console.error('保存文件时出错:', err);
    ElMessage({
      message: '保存文件失败，请重试',
      type: 'error',
    });
  }
};

// 添加设置MutationObserver的函数
const setupChartObserver = () => {
  // 如果已经存在观察者，先断开连接
  if (chartObserver.value) {
    chartObserver.value.disconnect();
  }
  
  // 创建新的MutationObserver
  chartObserver.value = new MutationObserver((mutations) => {
    // 如果图表发生变化，应用当前的显示/隐藏状态到所有异常区域
    applyAnomalyVisibility();
  });
  
  // 开始观察整个文档，关注子节点的添加
  chartObserver.value.observe(document.body, {
    childList: true,
    subtree: true
  });
};

// 应用异常区域可见性的函数，可以单独调用
const applyAnomalyVisibility = () => {
  const currentVisibility = showAnomaly.value;
  
  if (SingleChannelMultiRow_channel_number.value) {
    // 单通道多行模式
    const allCharts = document.querySelectorAll('[id^="chart-"]');
    allCharts.forEach(chartElement => {
      const chartInstance = Highcharts.charts.find(c => c && c.renderTo === chartElement);
      if (chartInstance) {
        chartInstance.xAxis[0].plotLinesAndBands.forEach(band => {
          if (band.id && (band.id.startsWith('band-') || band.id.startsWith('error-band-'))) {
            // 不影响现场标注的异常(橙色)
            if (band.id.startsWith('band-') && !band.options.color.includes('255, 0, 0')) {
              return;
            }
            const element = band.svgElem;
            if (element) {
              element.attr({
                fill: currentVisibility ? (band.options.color || 'rgba(255, 0, 0, 0.2)') : 'rgba(0, 0, 0, 0)'
              });
            }
          }
        });
      }
    });
  } else if (MultiChannelRef.value) {
    // 多通道单行模式实现类似逻辑
    const chartInstance = MultiChannelRef.value.chartInstance;
    if (chartInstance) {
      // 实现与单通道多行模式类似的透明度控制
      chartInstance.xAxis[0].plotLinesAndBands.forEach(band => {
        if (band.id && (band.id.startsWith('band-') || band.id.startsWith('error-band-'))) {
          // 不影响现场标注的异常(橙色)
          if (band.id.startsWith('band-') && !band.options.color.includes('255, 0, 0')) {
            return;
          }
          const element = band.svgElem;
          if (element) {
            element.attr({
              fill: currentVisibility ? (band.options.color || 'rgba(255, 0, 0, 0.2)') : 'rgba(0, 0, 0, 0)'
            });
          }
        }
      });
    }
  }
};

const updateShowAnomaly = (value) => {
  showAnomaly.value = value;
  localStorage.setItem('showAnomaly', value.toString());
  // 调用统一的应用函数
  applyAnomalyVisibility();
};

const exportChannelSVG = async () => {
  if (SingleChannelMultiRow_channel_number.value) {
    // 单通道多行的情况
    for (let [index, svgElement] of channelSvgElementsRefs.value.entries()) {
      if (svgElement) {
        try {
          // 克隆 SVG 元素并创建一个新的 XML 序列化器
          const clonedSvgElement = svgElement.cloneNode(true);
          const svgData = new XMLSerializer().serializeToString(clonedSvgElement);
          const legendImg = document.getElementById('channelLegendImage');

          // 创建 canvas
          const canvas = document.createElement('canvas');
          const legendWidth = legendImg.width;
          const legendHeight = legendImg.height;
          const padding = 30;
          const canvasWidth = Math.max(svgElement.width.baseVal.value, legendImg.width);
          const canvasHeight = svgElement.height.baseVal.value + legendImg.height + padding;
          canvas.width = canvasWidth;
          canvas.height = canvasHeight;
          const ctx = canvas.getContext('2d');

          // 创建图像并等待加载
          const svgImg = new Image();
          await new Promise((resolve, reject) => {
            svgImg.onload = resolve;
            svgImg.onerror = reject;
            svgImg.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgData);
          });

          // 绘制图例和SVG
          ctx.drawImage(legendImg, canvasWidth - legendWidth - 30, 0, legendWidth, legendHeight);
          ctx.drawImage(svgImg, 0, legendHeight + padding);

          // 转换为blob并保存
          const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
          await downloadFile(blob, `channel_${index + 1}_image.png`, 'png');
        } catch (error) {
          console.error('导出SVG时出错:', error);
          ElMessage({
            message: '导出图像失败，请重试',
            type: 'error',
          });
        }
      }
    }
  } else {
    let svgRef = MultiChannelRef.value.channelsSvgRef;
    if (svgRef) {
      try {
        const clonedSvgElement = svgRef.cloneNode(true);
        const svgData = new XMLSerializer().serializeToString(clonedSvgElement);
        const legendImg = document.getElementById('channelLegendImage');

        // 创建 canvas
        const canvas = document.createElement('canvas');
        const legendWidth = legendImg.width;
        const legendHeight = legendImg.height;
        const padding = 30;
        const canvasWidth = Math.max(svgRef.width.baseVal.value, legendImg.width);
        const canvasHeight = svgRef.height.baseVal.value + legendImg.height + padding;
        canvas.width = canvasWidth;
        canvas.height = canvasHeight;
        const ctx = canvas.getContext('2d');

        // 创建图像并等待加载
        const svgImg = new Image();
        await new Promise((resolve, reject) => {
          svgImg.onload = resolve;
          svgImg.onerror = reject;
          svgImg.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgData);
        });

        // 绘制图例和SVG
        ctx.drawImage(legendImg, canvasWidth - legendWidth - 30, 0, legendWidth, legendHeight);
        ctx.drawImage(svgImg, 0, legendHeight + padding);

        // 转换为blob并保存
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
        await downloadFile(blob, 'multi_channel_image.png', 'png');
      } catch (error) {
        console.error('导出SVG时出错:', error);
        ElMessage({
          message: '导出图像失败，请重试',
          type: 'error',
        });
      }
    }
  }
};

// 导出配置对话框状态
const showExportDialog = ref(false)
const exportConfig = reactive({
  selectedChannelIndices: [],
  channelRenames: [],
  frequencyMode: 'current', // 改为三种模式：'current', 'original', 'custom'
  customFrequency: 10.0 // 默认自定义频率10KHz
})

// 导出进度状态
const exportProgress = reactive({
  isExporting: false,
  current: 0,
  total: 0,
  percentage: 0,
  currentChannel: '',
  stage: 'downloading' // 添加阶段标识: 'downloading' 或 'packaging'
})

// 全选状态
const allChannelsSelected = computed({
  get: () => {
    if (!selectedChannels.value || selectedChannels.value.length === 0) return false
    return exportConfig.selectedChannelIndices.every(selected => selected)
  },
  set: (value) => {
    toggleAllChannels(value)
  }
})

// 初始化导出配置
const initExportConfig = () => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    exportConfig.selectedChannelIndices = selectedChannels.value.map(() => true)
    exportConfig.channelRenames = selectedChannels.value.map((channel) =>
      `${channel.channel_name}_${channel.shot_number}_data`
    )
    exportConfig.frequencyMode = 'current'
    exportConfig.customFrequency = 10.0 // 默认值重置为10kHz
  }
}

// 全选/取消全选
const toggleAllChannels = (value) => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    exportConfig.selectedChannelIndices = selectedChannels.value.map(() => value)
  }
}

// 重置通道名称
const resetChannelNames = () => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    exportConfig.channelRenames = selectedChannels.value.map((channel) =>
      `${channel.channel_name}_${channel.shot_number}_data`
    )
  }
}

// 格式化百分比显示
const percentageFormat = (percentage) => {
  return percentage === 100 ? '完成' : `${percentage}%`
}

// 开始导出数据
const startExportData = async () => {
  try {
    // 获取选中的通道
    const channelsToExport = []
    const fileNames = []

    selectedChannels.value.forEach((channel, index) => {
      if (exportConfig.selectedChannelIndices[index]) {
        channelsToExport.push(channel)
        fileNames.push(exportConfig.channelRenames[index] || `${channel.channel_name}_${channel.shot_number}_data`)
      }
    })

    if (channelsToExport.length === 0) {
      ElMessage.warning('请至少选择一个通道进行导出')
      return
    }

    // 创建新的zip实例
    const zip = new JSZip()

    // 设置进度状态
    exportProgress.isExporting = true
    exportProgress.current = 0
    exportProgress.total = channelsToExport.length
    exportProgress.percentage = 0
    exportProgress.stage = 'downloading'

    // 获取通道数据并添加到zip
    const missingChannels = []

    for (let i = 0; i < channelsToExport.length; i++) {
      const channel = channelsToExport[i]
      const fileName = fileNames[i]

      // 更新进度
      exportProgress.current = i + 1
      exportProgress.currentChannel = `${channel.channel_name}_${channel.shot_number}`
      exportProgress.percentage = Math.floor((i / channelsToExport.length) * 100)

      try {
        // 根据频率模式设置参数
        const params = { channel }
        
        if (exportConfig.frequencyMode === 'original') {
          params.sample_mode = 'full'
        } else if (exportConfig.frequencyMode === 'custom') {
          params.sample_mode = 'downsample'  // 修改为downsample，后端只支持full和downsample
          params.sample_freq = exportConfig.customFrequency // 使用sample_freq参数传递自定义频率
        }
        
        // 获取通道数据
        const data = await store.dispatch('fetchChannelData', params)

        if (data) {
          // 添加到zip
          const jsonData = JSON.stringify(data, null, 2)
          zip.file(`${fileName}.json`, jsonData)
        } else {
          missingChannels.push(`${channel.channel_name}_${channel.shot_number}`)
        }
    } catch (error) {
        console.error(`获取通道 ${channel.channel_name}_${channel.shot_number} 数据失败:`, error)
        missingChannels.push(`${channel.channel_name}_${channel.shot_number}`)
      }

      // 等待一点时间以更新UI
      await new Promise(resolve => setTimeout(resolve, 100))
    }

    // 完成下载阶段
    exportProgress.percentage = 100
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // 开始打包阶段
    exportProgress.stage = 'packaging'
    exportProgress.percentage = 0
    exportProgress.currentChannel = '所有通道'

    // 检查是否有缺失的通道
    if (missingChannels.length > 0) {
      if (missingChannels.length === channelsToExport.length) {
        ElMessage.error('所有选中通道的数据都无法获取，导出取消')
        exportProgress.isExporting = false
        return
      } else {
        ElMessage.warning(`部分通道数据无法获取: ${missingChannels.join(', ')}`)
      }
    }

    // 显示打包进度
    for (let i = 0; i <= 90; i += 10) {
      exportProgress.percentage = i;
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    // 生成文件名中包含频率信息
    let frequencyInfo = '';
    if (exportConfig.frequencyMode === 'current') {
      frequencyInfo = `_${sampling.value}kHz`;
    } else if (exportConfig.frequencyMode === 'custom') {
      frequencyInfo = `_${exportConfig.customFrequency}kHz`;
    } else {
      frequencyInfo = '_originalFrequency';
    }

    // 生成时间戳文件名并下载
    const now = new Date()
    const timestamp = `${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}_${now.getHours().toString().padStart(2, '0')}${now.getMinutes().toString().padStart(2, '0')}${now.getSeconds().toString().padStart(2, '0')}`
    const content = await zip.generateAsync({
      type: 'blob',
      compression: 'DEFLATE',
      compressionOptions: { level: 6 }
    })

    exportProgress.percentage = 100

    // 下载文件
    await downloadFile(content, `channel_data${frequencyInfo}_${timestamp}.zip`, 'zip')

    // 重置导出状态
    exportProgress.isExporting = false
    showExportDialog.value = false

  } catch (error) {
    console.error('导出通道数据失败:', error)
    ElMessage.error('导出通道数据失败，请重试')
    exportProgress.isExporting = false
  }
}

// 修改handleExportCommand函数以显示配置对话框
const handleExportCommand = (command) => {
  if (command === 'exportSvg') {
    exportChannelSVG()
  } else if (command === 'exportData') {
    // 打开导出配置对话框
    initExportConfig()
    showExportDialog.value = true
  }
}

const handleResultExportCommand = (command) => {
  if (command === 'exportSvg') {
    exportChannelSVG();
  } else if (command === 'exportData') {
    exportResultSVG();
  }
}

const toggleCollapse = () => {
  isSecondSectionCollapsed.value = !isSecondSectionCollapsed.value
}

const updateSampling = (value) => {
  store.dispatch('updateSampling', value)
}

const updateSmoothness = (value) => {
  store.dispatch('updateSmoothness', value)
}

</script>

<style scoped lang="scss">
.title {
  position: relative;
  font-size: 12pt;
  color: #333;
  font-weight: bold;
  margin-left: 5px;
}

.el-card {
  --el-card-padding: 6px;
}

.el-main {
  padding: 5px 5px 5px 0 !important;
}

.all-layout {
  width: 100vw;
  height: 100vh;
  background-color: #e2e2e2;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.aside {
  width: 25vw;
  background-color: #e9e9e9;
  height: 95vh;
  padding: 5px;
  box-sizing: border-box;
  display: flex;
}

// 添加这个样式确保el-container正确显示
:deep(.el-container) {
  height: 100%;
  flex-direction: column;
}

// 确保内部容器正确显示
:deep(.el-container .el-container) {
  flex-direction: row;
}

.aside-content,
.main {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}

.jump_switch {
  margin-bottom: 5px;
  padding-bottom: 10px;
  display: flex;
  justify-content: center;
}

.filtandsearch {
  margin-bottom: 2px;
  flex-shrink: 0;
}

.table {
  flex-grow: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-top: 0;

  .color_table_switch {
    position: absolute;
    right: 10px;
  }

  .scrollbar-container {
    flex: 1;
    height: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  :deep(.el-scrollbar) {
    height: 100%;
    flex: 1;

    .el-scrollbar__wrap {
      overflow-x: hidden;
    }
  }

  .title-row {
    padding: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .table-container {
    flex: 1;
    position: relative;
    display: flex;
    flex-direction: column;
    height: calc(100% - 32px); // 减去title-row的高度
  }
}

.test_main {
  background-color: #e9e9e9;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;

  .data_exploration {
    margin-bottom: 0;
    width: 100%;
    height: 100%;
    flex: 2.1;
    position: relative;
  }

  .collapse-control {
    display: flex;
    justify-content: center;
    margin: 0 0 2px 0;

    .collapse-btn {
      padding: 2px 8px;
      font-size: 12px;
      display: flex;
      align-items: center;
      color: #909399;
      height: 24px;

      &:hover {
        color: #409EFF;
      }

      .el-icon {
        margin-right: 2px;
        font-size: 12px;
      }

      .collapse-text {
        font-size: 12px;
      }
    }
  }

  .collapse-bookmark {
    position: absolute;
    bottom: -12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;

    .bookmark-btn {
      width: 24px;
      height: 16px;
      padding: 0;
      border-radius: 0 0 4px 4px;
      background-color: #f2f6fc;
      border: 1px solid #dcdfe6;
      border-top: none;
      box-shadow: 0 2px 2px rgba(0, 0, 0, 0.05);
      display: flex;
      justify-content: center;
      align-items: center;

      &:hover {
        background-color: #ecf5ff;
        color: #409EFF;
      }

      .el-icon {
        font-size: 12px;
        margin: 0;
      }
    }
  }

  .two {
    margin-top: 0;
    display: flex;
    flex: 1;
    flex-grow: 1;
    gap: 5px;
    position: relative;
    transition: all 0.3s ease;
  }

  .two_left {
    flex: 1.5;
    position: relative;
    width: 100%;
  }

  .two_right {
    flex: 2;
    position: relative;
    width: 70%;
    height: 100%;
  }
}

.channel_main {
  background-color: #e9e9e9;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;

  .operator {
    margin-bottom: 5px;
  }

  .data_exploration {
    width: 100%;
    height: 100%;
    flex: 1.4;
  }

  .two {
    display: flex;
    flex: 1;
    flex-grow: 1;
    gap: 5px;
    height: 100%;
    margin-bottom: 5px;
  }

  .two_left {
    flex: 2.5;
    position: relative;
    height: 100%;
  }

  .two_right {
    flex: 1;
    position: relative;
    height: 100%;
  }
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

/* 让数字输入框内的文字可以选中 */
.el-input-number {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让下拉菜单中的文字可以选中 */
.el-dropdown-menu {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

.arc-toggle-container {
  position: relative;
  display: flex;
  justify-content: center;
  height: 0;
  z-index: 999;
}

.arc-toggle {
  position: absolute;
  top: -20px;
  padding: 3px 20px 5px 20px;
  background-color: #f2f6fc;
  border: 1px solid #dcdfe6;
  border-top-left-radius: 12px;
  border-top-right-radius: 12px;
  border-top: none;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;

  &:hover {
    background-color: #ecf5ff;
    box-shadow: 0 3px 6px rgba(0, 0, 0, 0.15);
    transform: translateY(1px);
  }

  .arc-toggle-icon {
    margin-right: 4px;
    font-size: 14px;
    color: #409EFF;
  }

  .arc-toggle-text {
    font-size: 12px;
    color: #606266;
    white-space: nowrap;
    /* 防止文本换行 */
  }
}

/* 三横线菜单按钮样式 */
.menu-button {
  padding: 8px;
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-button .el-icon {
  font-size: 18px;
  margin: 0;
}

/* 视图切换按钮组样式 */
.el-button-group {
  margin: 0 8px;
}

.el-button-group .el-button {
  font-size: 12px;
  padding: 6px 12px;
  transition: all 0.3s;
}

.el-button-group .el-button:not(:first-child):not(:last-child) {
  margin: 0 -1px;
}

/* 控制面板样式 */
.control-panel {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.control-item {
  display: flex;
  align-items: center;
}

.control-label {
  margin-right: 8px;
  font-size: 1em;
  color: #606266;
  white-space: nowrap;
}

.control-unit {
  margin-left: 4px;
  font-size: 1em;
  color: #606266;
}

/* 统一输入框样式 */
:deep(.el-input-number) {
  width: 140px;
}

:deep(.el-input-number .el-input__inner) {
  text-align: center;
}

/* 统一按钮组样式 */
:deep(.el-button-group .el-button) {
  font-size: 12px;
  padding: 6px 12px;
}

/* 导出配置对话框样式 */
.channel-selection {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 10px;
  margin-bottom: 10px;
}

.channel-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e4e7ed;
}

.channel-item {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px dashed #ebeef5;
}

.channel-name {
  margin-left: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 180px;
}

.filename-input-container {
  position: relative;
  margin-left: 10px;
  width: 180px;
  
  .el-input {
    width: 100%;
  }
  
  .file-extension {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    color: #909399;
    pointer-events: none;
  }
}

.export-progress {
  margin-top: 20px;
  padding: 15px;
  background-color: #f5f7fa;
  border-radius: 4px;
}
</style>
