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
                          <el-dropdown-item command="exportSvg">导出图片</el-dropdown-item>
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
                        <el-dropdown-item command="exportSvg">导出图片</el-dropdown-item>
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
    <el-dialog v-model="showExportDialog" title="导出通道数据配置" width="900px" class="export-dialog">
      <div class="dialog-layout">
        <!-- 左侧：通道选择 -->
        <div class="left-section">
          <div class="section-title">选择通道</div>
          <div class="channel-selection">
            <div class="channel-header">
              <el-checkbox v-model="allChannelsSelected" @change="toggleAllChannels">全选</el-checkbox>
              <el-button size="small" @click="resetChannelNames" :icon="Refresh" :link="true">重置名称</el-button>
  </div>
            <el-scrollbar height="350px">
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
        </div>

        <!-- 右侧：参数配置和进度条 -->
        <div class="right-section">
          <div>
            <div class="section-title">导出参数</div>
            <div class="param-form">
              <el-form :model="exportConfig" label-width="100px">
                <!-- 频率设置 -->
                <el-form-item label="数据频率" class="frequency-options">
                  <div class="frequency-radio-container">
                    <div class="radio-option">
                      <el-radio v-model="exportConfig.frequencyMode" label="current">
                        使用当前采样频率 ({{ sampling }}KHz)
                      </el-radio>
                    </div>

                    <div class="radio-option">
                      <div class="radio-with-tag">
                        <el-radio v-model="exportConfig.frequencyMode" label="original">
                          使用原始频率
                        </el-radio>
                        <el-tag type="warning" size="small">需要更多耗时</el-tag>
                      </div>
                    </div>

                    <div class="radio-option">
                      <div class="radio-with-tag">
                        <el-radio v-model="exportConfig.frequencyMode" label="custom">
                          使用自定义频率
                        </el-radio>
                        <el-tag type="warning" size="small">需要更多耗时</el-tag>
                      </div>

                      <div class="custom-frequency-control">
                        <el-input-number v-model="exportConfig.customFrequency" :precision="2" :step="0.5" :min="0.1" :max="1000" size="small" :disabled="exportConfig.frequencyMode !== 'custom'" />
                        <span class="unit-label">KHz</span>
                      </div>
                    </div>
                  </div>
                </el-form-item>
              </el-form>
            </div>
          </div>

          <div class="progress-container">
            <!-- 进度条 -->
            <div v-if="exportProgress.isExporting" class="export-progress">
              <p>
                <template v-if="exportProgress.stage === 'downloading'">
                  正在下载数据: {{ exportProgress.currentChannel }} ({{ exportProgress.current }}/{{ exportProgress.total }})
                </template>
                <template v-else>
                  正在打包数据: {{ exportProgress.currentChannel }} ({{ exportProgress.current }}/{{ exportProgress.total }})
                </template>
              </p>
              <el-progress :percentage="exportProgress.percentage" :format="percentageFormat"></el-progress>
            </div>
            <!-- 占位容器，当没有进度条时占据空间，保持对齐 -->
            <div v-else class="export-progress-placeholder"></div>
          </div>
        </div>
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

    <!-- 添加导出SVG配置对话框 -->
    <el-dialog v-model="showSvgExportDialog" title="导出通道图片配置" width="900px" class="export-dialog">
      <div class="dialog-layout">
        <!-- 左侧：通道选择 -->
        <div class="left-section">
          <div class="section-title">选择通道</div>
          <div class="channel-selection">
            <div class="channel-header">
              <el-checkbox v-model="allSvgChannelsSelected" @change="toggleAllSvgChannels">全选</el-checkbox>
              <el-button size="small" @click="resetSvgChannelNames" :icon="Refresh" :link="true">重置名称</el-button>
            </div>
            <el-scrollbar height="350px">
              <div v-for="(channel, index) in selectedChannels" :key="`${channel.channel_name}_${channel.shot_number}`" class="channel-item">
                <el-checkbox v-model="svgExportConfig.selectedChannelIndices[index]"></el-checkbox>
                <span class="channel-name">{{ channel.channel_name }}_{{ channel.shot_number }}</span>
                <div class="filename-input-container">
                  <el-input v-model="svgExportConfig.channelRenames[index]" placeholder="自定义文件名" size="small"></el-input>
                  <span class="file-extension">.png</span>
                </div>
              </div>
            </el-scrollbar>
          </div>
        </div>

        <!-- 右侧：参数配置和进度条 -->
        <div class="right-section">
          <div>
            <div class="section-title">导出参数</div>
            <div class="param-form">
              <el-form :model="svgExportConfig" label-width="100px">
                <!-- 导出模式选择 -->
                <el-form-item label="导出模式" class="mode-selection">
                  <div class="mode-radio-container">
                    <div class="radio-option">
                      <el-radio v-model="svgExportConfig.exportMode" label="singleChannel">
                        单通道多图（每个通道单独导出）
                      </el-radio>
                    </div>
                    <div class="radio-option">
                      <el-radio v-model="svgExportConfig.exportMode" label="multiChannel">
                        多通道单图（所有通道合并导出）
                      </el-radio>
                    </div>
                  </div>
                </el-form-item>

                <!-- 图片尺寸设置 -->
                <el-form-item label="图片尺寸" class="size-controls-container">
                  <div class="size-controls">
                    <div class="size-input-group">
                      <span class="size-label">宽度:</span>
                      <el-input-number v-model="svgExportConfig.width" :min="300" :max="3000" :controls="false" size="small" />
                      <span class="size-unit">px</span>
                    </div>
                    
                    <div class="size-input-group">
                      <span class="size-label">高度:</span>
                      <el-input-number v-model="svgExportConfig.height" :min="200" :max="2000" :controls="false" size="small" />
                      <span class="size-unit">px</span>
                    </div>
                  </div>
                </el-form-item>

                <!-- 频率设置 -->
                <el-form-item label="数据频率" class="frequency-options">
                  <div class="frequency-radio-container">
                    <div class="radio-option">
                      <el-radio v-model="svgExportConfig.frequencyMode" label="current">
                        使用当前采样频率 ({{ sampling }}KHz)
                      </el-radio>
                    </div>

                    <div class="radio-option">
                      <div class="radio-with-tag">
                        <el-radio v-model="svgExportConfig.frequencyMode" label="original">
                          使用原始频率
                        </el-radio>
                        <el-tag type="warning" size="small">需要更多耗时</el-tag>
                      </div>
                    </div>

                    <div class="radio-option">
                      <div class="radio-with-tag">
                        <el-radio v-model="svgExportConfig.frequencyMode" label="custom">
                          使用自定义频率
                        </el-radio>
                        <el-tag type="warning" size="small">需要更多耗时</el-tag>
                      </div>

                      <div class="custom-frequency-control">
                        <el-input-number v-model="svgExportConfig.customFrequency" :precision="2" :step="0.5" :min="0.1" :max="1000" size="small" :disabled="svgExportConfig.frequencyMode !== 'custom'" />
                        <span class="unit-label">KHz</span>
                      </div>
                    </div>
                  </div>
                </el-form-item>
              </el-form>
            </div>
          </div>
          
          <!-- 其他内容保持不变 -->

          <div class="progress-container">
            <!-- 进度条 -->
            <div v-if="svgExportProgress.isExporting" class="export-progress">
              <p>
                <template v-if="svgExportProgress.stage === 'downloading'">
                  正在下载数据: {{ svgExportProgress.currentChannel }} ({{ svgExportProgress.current }}/{{ svgExportProgress.total }})
                </template>
                <template v-else-if="svgExportProgress.stage === 'rendering'">
                  正在渲染图表: {{ svgExportProgress.currentChannel }} ({{ svgExportProgress.current }}/{{ svgExportProgress.total }})
                </template>
                <template v-else>
                  正在打包图片: {{ svgExportProgress.currentChannel }} ({{ svgExportProgress.current }}/{{ svgExportProgress.total }})
                </template>
              </p>
              <el-progress :percentage="svgExportProgress.percentage" :format="percentageFormat"></el-progress>
            </div>
            <!-- 占位容器，当没有进度条时占据空间，保持对齐 -->
            <div v-else class="export-progress-placeholder"></div>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showSvgExportDialog = false">取消</el-button>
          <el-button type="primary" @click="startExportSvg" :loading="svgExportProgress.isExporting">
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

const exportChannelSVG = () => {
  // 检查是否有通道被选中
  if (!selectedChannels.value || selectedChannels.value.length === 0) {
    ElMessage.warning('请先选择至少一个通道')
    return
  }
  
  // 初始化配置并打开对话框
  initSvgExportConfig()
  showSvgExportDialog.value = true
}

// 导出SVG配置对话框状态
const showSvgExportDialog = ref(false)
const svgExportConfig = reactive({
  selectedChannelIndices: [],
  channelRenames: [],
  frequencyMode: 'current',
  customFrequency: 10.0,
  width: 1200, // 默认宽度，像素
  height: 600,  // 默认高度，像素
  exportMode: 'singleChannel' // 默认为单通道多图模式
})

// 导出SVG进度状态
const svgExportProgress = reactive({
  isExporting: false,
  current: 0,
  total: 0,
  percentage: 0,
  currentChannel: '',
  stage: 'rendering' // 'rendering' 或 'packaging'
})

// 全选SVG通道状态
const allSvgChannelsSelected = computed({
  get: () => {
    if (!selectedChannels.value || selectedChannels.value.length === 0) return false
    return svgExportConfig.selectedChannelIndices.every(selected => selected)
  },
  set: (value) => {
    toggleAllSvgChannels(value)
  }
})

// 全选/取消全选SVG通道
const toggleAllSvgChannels = (value) => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    svgExportConfig.selectedChannelIndices = selectedChannels.value.map(() => value)
  }
}

// 重置SVG通道名称
const resetSvgChannelNames = () => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    svgExportConfig.channelRenames = selectedChannels.value.map((channel) =>
      `${channel.channel_name}_${channel.shot_number}_image`
    )
  }
}

// 初始化SVG导出配置
const initSvgExportConfig = () => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    svgExportConfig.selectedChannelIndices = selectedChannels.value.map(() => true)
    svgExportConfig.channelRenames = selectedChannels.value.map((channel) =>
      `${channel.channel_name}_${channel.shot_number}_image`
    )
    svgExportConfig.frequencyMode = 'current'
    svgExportConfig.customFrequency = 10.0
    
    // 根据当前显示模式设置默认尺寸
    if (SingleChannelMultiRow_channel_number.value) {
      // 单通道多行模式
      svgExportConfig.width = 1200
      svgExportConfig.height = 600
  } else {
      // 多通道单行模式
      svgExportConfig.width = 1600
      svgExportConfig.height = 800
    }
    
    // 设置默认导出模式为当前显示模式
    svgExportConfig.exportMode = SingleChannelMultiRow_channel_number.value ? 'singleChannel' : 'multiChannel'
  }
}

// 修复renderChannelToPng函数，使用正确的方法导出图表为图片
const renderChannelToPng = async (channel, fileName, width, height, frequencyParams, channelData = null) => {
  try {
    // 使用预先获取的数据或者重新获取
    const data = channelData || await store.dispatch('fetchChannelData', { 
      channel, 
      ...frequencyParams 
    })
    
    // 创建临时容器来渲染图表
    const container = document.createElement('div')
    container.style.width = `${width}px`
    container.style.height = `${height}px`
    container.style.position = 'absolute'
    container.style.top = '-9999px'
    container.style.left = '-9999px'
    container.style.zIndex = '-1000'
    container.style.opacity = '0'
    container.style.pointerEvents = 'none'
    document.body.appendChild(container)
    
    // 创建图表配置
    const options = {
      chart: {
        type: 'line',
        width: width,
        height: height,
        animation: false,
        backgroundColor: '#ffffff',
        style: {
          fontFamily: 'Arial, Helvetica, sans-serif'
        },
        spacing: [30, 10, 30, 60] // 上、右、下、左的边距
      },
      title: {
        text: `${channel.channel_name}_${channel.shot_number}`,
        align: 'center',
        style: {
          fontSize: '18px',
          fontWeight: 'bold',
          color: '#000000'
        },
        margin: 20
      },
      credits: {
        enabled: false
      },
      xAxis: {
        title: {
          text: 'Time (s)',
          style: {
            fontSize: '14px',
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 15
        },
        min: data.X_value[0],
        max: data.X_value[data.X_value.length - 1],
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: '12px',
            color: '#000000'
          }
        }
      },
      yAxis: {
        title: {
          text: data.Y_unit || 'Value',
          style: {
            fontSize: '14px',
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 15
        },
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: '12px',
            color: '#000000'
          }
        }
      },
      legend: {
        enabled: true,
        align: 'right',
        verticalAlign: 'top',
        layout: 'vertical',
        backgroundColor: '#FFFFFF',
        borderWidth: 1,
        borderColor: '#E0E0E0',
        borderRadius: 5,
        itemStyle: {
          fontSize: '12px',
          fontWeight: 'normal',
          color: '#000000'
        },
        itemHoverStyle: {
          color: '#4572A7'
        }
      },
      series: [{
        name: channel.channel_name,
        data: data.X_value.map((x, i) => [x, data.Y_value[i]]),
        color: channel.color || '#4572A7',
        lineWidth: 1.5,
        marker: {
          enabled: false,
          radius: 3,
          symbol: 'circle'
        },
        states: {
          hover: {
            lineWidth: 2
          }
        },
        boostThreshold: 1000
      }],
      plotOptions: {
        series: {
          animation: false,
          turboThreshold: 0,
          shadow: false,
          stickyTracking: false
        },
        line: {
          marker: {
            enabled: false
          }
        }
      },
      tooltip: {
        enabled: false
      },
      boost: {
        useGPUTranslations: true,
        seriesThreshold: 1
      },
      exporting: {
        enabled: false // 确保不显示导出按钮
      }
    }
    
    // 渲染图表
    const chart = Highcharts.chart(container, options)
    
    // 等待图表渲染完成
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // 使用canvas直接从DOM中获取图表并转换为PNG
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    
    // 使用html2canvas或相似技术从DOM获取图表
    // 由于直接获取SVG有问题，我们使用canvas直接绘制DOM元素
    const svgElement = container.querySelector('svg')
    const serializedSvg = new XMLSerializer().serializeToString(svgElement)
    const img = new Image()
    
    // 使用Promise包装图像加载
    const pngBlob = await new Promise((resolve, reject) => {
      img.onload = () => {
        // 清理背景
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, width, height)
        
        // 绘制图表
        ctx.drawImage(img, 0, 0)
        
        // 转换为blob
        canvas.toBlob(blob => resolve(blob), 'image/png')
      }
      img.onerror = reject
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(serializedSvg)
    })
    
    // 清理
    chart.destroy()
    document.body.removeChild(container)
    
    return pngBlob
      } catch (error) {
    console.error('渲染通道图片失败:', error)
    throw error
  }
}

// 修复renderMultiChannelToPng函数，使用正确的方法导出图表为图片
const renderMultiChannelToPng = async (channels, width, height, frequencyParams, channelDataMap = null) => {
  try {
    // 创建临时容器
    const container = document.createElement('div')
    container.style.width = `${width}px`
    container.style.height = `${height}px`
    container.style.position = 'absolute'
    container.style.top = '-9999px'
    container.style.left = '-9999px'
    container.style.zIndex = '-1000'
    container.style.opacity = '0'
    container.style.pointerEvents = 'none'
    document.body.appendChild(container)
    
    // 获取所有通道数据并准备系列
    const seriesData = []
    const xMin = [], xMax = []
    
    for (const channel of channels) {
      // 获取通道数据，优先使用预先获取的数据
      const data = channelDataMap ? channelDataMap.get(channel) : await store.dispatch('fetchChannelData', { 
        channel, 
        ...frequencyParams 
      })
      
      // 记录x轴范围
      xMin.push(data.X_value[0])
      xMax.push(data.X_value[data.X_value.length - 1])
      
      // 添加系列
      seriesData.push({
        name: `${channel.channel_name}_${channel.shot_number}`,
        data: data.X_value.map((x, i) => [x, data.Y_value[i]]),
        color: channel.color || getRandomColor(channel.channel_name),
        lineWidth: 1.5,
        marker: {
          enabled: false,
          radius: 3,
          symbol: 'circle'
        },
        states: {
          hover: {
            lineWidth: 2
          }
        },
        boostThreshold: 1000
      })
    }
    
    // 创建图表配置
    const options = {
      chart: {
        type: 'line',
        width: width,
        height: height,
        animation: false,
        backgroundColor: '#ffffff',
        style: {
          fontFamily: 'Arial, Helvetica, sans-serif'
        },
        spacing: [30, 10, 30, 60] // 上、右、下、左的边距
      },
      title: {
        text: '多通道数据视图',
        align: 'center',
        style: {
          fontSize: '18px',
          fontWeight: 'bold',
          color: '#000000'
        },
        margin: 20
      },
      credits: {
        enabled: false
      },
      xAxis: {
        title: {
          text: 'Time (s)',
          style: {
            fontSize: '14px',
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 15
        },
        min: Math.min(...xMin),
        max: Math.max(...xMax),
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: '12px',
            color: '#000000'
          }
        }
      },
      yAxis: {
        title: {
          text: 'Value',
          style: {
            fontSize: '14px',
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 15
        },
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: '12px',
            color: '#000000'
          }
        }
      },
      legend: {
        enabled: true,
        align: 'right',
        verticalAlign: 'top',
        layout: 'vertical',
        backgroundColor: '#FFFFFF',
        borderWidth: 1,
        borderColor: '#E0E0E0',
        borderRadius: 5,
        itemStyle: {
          fontSize: '12px',
          fontWeight: 'normal',
          color: '#000000'
        },
        itemHoverStyle: {
          color: '#4572A7'
        }
      },
      series: seriesData,
      plotOptions: {
        series: {
          animation: false,
          turboThreshold: 0,
          shadow: false,
          stickyTracking: false
        },
        line: {
          marker: {
            enabled: false
          }
        }
      },
      tooltip: {
        enabled: false
      },
      boost: {
        useGPUTranslations: true,
        seriesThreshold: 1
      },
      exporting: {
        enabled: false // 确保不显示导出按钮
      }
    }
    
    // 渲染图表
    const chart = Highcharts.chart(container, options)
    
    // 等待图表渲染完成
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // 使用canvas直接从DOM中获取图表并转换为PNG
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    
    // 获取SVG并转换为PNG
    const svgElement = container.querySelector('svg')
    const serializedSvg = new XMLSerializer().serializeToString(svgElement)
    const img = new Image()
    
    // 使用Promise包装图像加载
    const pngBlob = await new Promise((resolve, reject) => {
      img.onload = () => {
        // 清理背景
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, width, height)
        
        // 绘制图表
        ctx.drawImage(img, 0, 0)
        
        // 转换为blob
        canvas.toBlob(blob => resolve(blob), 'image/png')
      }
      img.onerror = reject
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(serializedSvg)
    })
    
    // 清理
    chart.destroy()
    document.body.removeChild(container)
    
    return pngBlob
    } catch (error) {
    console.error('渲染多通道图片失败:', error)
    throw error
  }
}

// 为多通道视图生成一致的颜色
const getRandomColor = (seed) => {
  // 使用简单的字符串哈希算法为通道名生成一致的颜色
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  }
  
  // 预定义的MATLAB风格颜色
  const matlabColors = [
    '#0072BD', // 蓝色
    '#D95319', // 橙色
    '#EDB120', // 黄色
    '#7E2F8E', // 紫色
    '#77AC30', // 绿色
    '#4DBEEE', // 浅蓝色
    '#A2142F'  // 红褐色
  ];
  
  // 根据哈希值选择颜色
  return matlabColors[Math.abs(hash) % matlabColors.length];
}

const handleExportCommand = (command) => {
  if (command === 'exportSvg') {
    exportChannelSVG()
  } else if (command === 'exportData') {
    // 检查是否有通道被选中
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      ElMessage.warning('请先选择至少一个通道')
      return
    }
    
    // 打开导出配置对话框
    initExportConfig()
    showExportDialog.value = true
  }
}

const handleResultExportCommand = (command) => {
  if (command === 'exportSvg') {
    exportChannelSVG();
  } else if (command === 'exportData') {
    // 检查是否有通道被选中
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      ElMessage.warning('请先选择至少一个通道')
      return
    }
    
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

// 开始导出SVG为PNG
const startExportSvg = async () => {
  try {
    // 获取选中的通道
    const channelsToExport = []
    const fileNames = []

    selectedChannels.value.forEach((channel, index) => {
      if (svgExportConfig.selectedChannelIndices[index]) {
        channelsToExport.push(channel)
        fileNames.push(svgExportConfig.channelRenames[index] || `${channel.channel_name}_${channel.shot_number}_image`)
      }
    })

    if (channelsToExport.length === 0) {
      ElMessage.warning('请至少选择一个通道进行导出')
      return
    }

    // 创建新的zip实例（仅在单通道多图模式下使用）
    const zip = new JSZip()

    // 设置进度状态 - 首先是下载数据阶段
    svgExportProgress.isExporting = true
    svgExportProgress.current = 0
    svgExportProgress.total = channelsToExport.length
    svgExportProgress.percentage = 0
    svgExportProgress.stage = 'downloading'

    // 设置频率参数
    const frequencyParams = {}
    if (svgExportConfig.frequencyMode === 'original') {
      frequencyParams.sample_mode = 'full'
    } else if (svgExportConfig.frequencyMode === 'custom') {
      frequencyParams.sample_mode = 'downsample'
      frequencyParams.sample_freq = svgExportConfig.customFrequency
    }
    
    // 下载所有需要的通道数据
    const channelDataMap = new Map()
    for (let i = 0; i < channelsToExport.length; i++) {
      const channel = channelsToExport[i]
      
      // 更新进度
      svgExportProgress.current = i + 1
      svgExportProgress.currentChannel = `${channel.channel_name}_${channel.shot_number}`
      svgExportProgress.percentage = Math.floor((i / channelsToExport.length) * 100)
      
      try {
        // 获取通道数据
        const data = await store.dispatch('fetchChannelData', { 
          channel, 
          ...frequencyParams 
        })
        
        // 存储数据以便后续渲染使用
        channelDataMap.set(channel, data)
      } catch (error) {
        console.error(`获取通道 ${channel.channel_name}_${channel.shot_number} 数据失败:`, error)
        ElMessage.warning(`获取通道 ${channel.channel_name}_${channel.shot_number} 数据失败，将跳过此通道`)
      }
      
      // 等待一点时间以更新UI
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    
    // 完成下载阶段，进入渲染阶段
    svgExportProgress.percentage = 100
    await new Promise(resolve => setTimeout(resolve, 300))
    
    // 开始渲染阶段
    svgExportProgress.current = 0
    svgExportProgress.percentage = 0
    svgExportProgress.stage = 'rendering'
    
    // 根据选择的导出模式决定导出方式，而不是根据当前显示模式
    if (svgExportConfig.exportMode === 'singleChannel') {
      // 单通道多图模式：每个通道单独导出
      const validChannels = channelsToExport.filter(channel => channelDataMap.has(channel))
      svgExportProgress.total = validChannels.length
      
      for (let i = 0; i < validChannels.length; i++) {
        const channel = validChannels[i]
        const fileName = fileNames[channelsToExport.indexOf(channel)]

        // 更新进度
        svgExportProgress.current = i + 1
        svgExportProgress.currentChannel = `${channel.channel_name}_${channel.shot_number}`
        svgExportProgress.percentage = Math.floor((i / validChannels.length) * 100)

        try {
          // 渲染并获取PNG
          const channelData = channelDataMap.get(channel)
          const pngBlob = await renderChannelToPng(
            channel, 
            fileName, 
            svgExportConfig.width, 
            svgExportConfig.height,
            frequencyParams,
            channelData
          )

          // 添加到zip
          zip.file(`${fileName}.png`, pngBlob)
        } catch (error) {
          console.error(`导出通道 ${channel.channel_name}_${channel.shot_number} 图片失败:`, error)
          ElMessage.warning(`导出通道 ${channel.channel_name}_${channel.shot_number} 图片失败`)
        }

        // 等待一点时间以更新UI
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      
      // 切换到打包阶段
      svgExportProgress.percentage = 100
      await new Promise(resolve => setTimeout(resolve, 300))
      
      svgExportProgress.current = 0
      svgExportProgress.percentage = 0
      svgExportProgress.stage = 'packaging'
      svgExportProgress.currentChannel = '所有通道'
      await new Promise(resolve => setTimeout(resolve, 300))
      svgExportProgress.percentage = 50

      // 生成频率信息
      let frequencyInfo = ''
      if (svgExportConfig.frequencyMode === 'current') {
        frequencyInfo = `_${sampling.value}kHz`
      } else if (svgExportConfig.frequencyMode === 'custom') {
        frequencyInfo = `_${svgExportConfig.customFrequency}kHz`
      } else {
        frequencyInfo = '_originalFrequency'
      }

      // 生成时间戳
      const now = new Date()
      const timestamp = `${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}_${now.getHours().toString().padStart(2, '0')}${now.getMinutes().toString().padStart(2, '0')}`
      
      // 生成zip包
      const content = await zip.generateAsync({
        type: 'blob'
      })

      svgExportProgress.percentage = 100

      // 下载文件
      await downloadFile(content, `channel_images${frequencyInfo}_${timestamp}.zip`, 'zip')
      
    } else {
      // 多通道单图模式：将所有通道一起导出为一个图片
      svgExportProgress.currentChannel = '多通道视图'
      svgExportProgress.percentage = 30
      svgExportProgress.total = 1
      svgExportProgress.current = 0

      try {
        // 过滤出有效的通道(已成功下载数据的)
        const validChannels = channelsToExport.filter(channel => channelDataMap.has(channel))
        
        if (validChannels.length === 0) {
          ElMessage.error('没有有效的通道数据可以导出')
          svgExportProgress.isExporting = false
          return
        }
        
        // 更新进度
        svgExportProgress.current = 1
        
        // 渲染并获取PNG
        const pngBlob = await renderMultiChannelToPng(
          validChannels, 
          svgExportConfig.width, 
          svgExportConfig.height,
          frequencyParams,
          channelDataMap
        )

        // 多通道单图模式：直接导出图片，不打包
        svgExportProgress.percentage = 100
        svgExportProgress.stage = 'packaging'
        await new Promise(resolve => setTimeout(resolve, 300))
        
        // 生成频率信息用于文件名
        let frequencyInfo = ''
        if (svgExportConfig.frequencyMode === 'current') {
          frequencyInfo = `_${sampling.value}kHz`
        } else if (svgExportConfig.frequencyMode === 'custom') {
          frequencyInfo = `_${svgExportConfig.customFrequency}kHz`
        } else {
          frequencyInfo = '_originalFrequency'
        }
        
        // 生成时间戳
        const now = new Date()
        const timestamp = `${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}_${now.getHours().toString().padStart(2, '0')}${now.getMinutes().toString().padStart(2, '0')}`
        
        // 为多通道图片生成文件名
        const fileName = validChannels.length === 1 
          ? fileNames[channelsToExport.indexOf(validChannels[0])]
          : `multi_channel_image${frequencyInfo}_${timestamp}`
          
        // 直接下载PNG文件
        await downloadFile(pngBlob, `${fileName}.png`, 'png')
      } catch (error) {
        console.error('导出多通道图片失败:', error)
        ElMessage.error('导出多通道图片失败，请重试')
        svgExportProgress.isExporting = false
        return
      }
    }

    // 重置导出状态
    svgExportProgress.isExporting = false
    showSvgExportDialog.value = false
  } catch (error) {
    console.error('导出通道图片失败:', error)
    ElMessage.error('导出通道图片失败，请重试')
    svgExportProgress.isExporting = false
  }
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
  font-size: 0.9em;
  color: #606266;
  white-space: nowrap;
}

.control-unit {
  margin-left: 4px;
  font-size: 0.9em;
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
.export-dialog {
  :deep(.el-dialog__body) {
    padding: 20px 25px;
  }
}

.channel-selection {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 15px;
  margin-bottom: 15px;
  background-color: #f8f9fa;
}

.channel-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e4e7ed;
}

.channel-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed #ebeef5;
}

.channel-name {
  margin-left: 10px;
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
    pointer-events: none;
  }
}

/* 频率选项样式 */
.frequency-options {
  margin-top: 5px;
}

.frequency-radio-container {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.radio-option {
  display: flex;
  flex-direction: column;
  margin-bottom: 10px;

  &:last-child {
    margin-bottom: 0;
  }
}

.radio-with-tag {
  display: flex;
  align-items: center;
  height: 28px;
  line-height: 28px;

  .el-radio {
    margin-right: 8px;
  }

  .el-tag {
    margin-left: 8px;
  }
}

.custom-frequency-control {
  margin-top: 5px;
  margin-left: 23px;
  display: flex;
  align-items: center;

  .el-input-number {
    width: 110px;
  }

  .unit-label {
    margin-left: 5px;
    color: #606266;
  }
}

.export-progress {
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
  min-height: 70px; /* 减小最小高度 */

  p {
    margin-bottom: 8px;
    color: #606266;
  }
}

/* 添加导出模式相关样式 */
.mode-selection {
  margin-bottom: 10px;
}

.mode-radio-container {
  display: flex;
  flex-direction: column;
}

.mode-radio-container .radio-option {
  margin-bottom: 8px;
}

/* 导出对话框左右布局样式 */
.dialog-layout {
  display: flex;
  gap: 20px;
  max-height: 500px; /* 设置最大高度 */
}

.left-section {
  flex: 1;
  min-width: 400px;
  display: flex;
  flex-direction: column;
}

.right-section {
  flex: 1;
  min-width: 400px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.section-title {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 15px;
  color: #333;
}

.param-form {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 15px;
  background-color: #f8f9fa;
  margin-bottom: 15px;
}

.progress-container {
  margin-top: 20px; /* 确保进度条区域位于底部 */
  margin-bottom: 10px;
}

/* 添加新的占位容器样式，用于保持对齐 */
.export-progress-placeholder {
  height: 70px; /* 与进度条区域高度一致 */
  border: 1px solid transparent; /* 透明边框，保持尺寸一致 */
}

/* 添加上边距类 */
.mt-10 {
  margin-top: 10px;
}

/* 调整尺寸控件容器 */
.size-controls-container {
  margin-bottom: 8px;
}

/* SVG导出对话框尺寸控件 */
.size-controls {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}

.size-input-group {
  display: flex;
  align-items: center;
  
  .size-label {
    margin-right: 5px;
    white-space: nowrap;
  }
  
  .size-unit {
    margin-left: 5px;
    color: #606266;
  }

  :deep(.el-input-number) {
    width: 80px;
  }
}
</style>
