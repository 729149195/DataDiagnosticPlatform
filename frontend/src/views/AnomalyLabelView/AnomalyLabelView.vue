<template>
  <div class="all-layout">
    <el-container>
      <el-header class="header">
        <div shadow="never">
          <el-button class="anay" :class="{ selected: selectedButton === 'anay' }"
            :type="selectedButton === 'anay' ? 'primary' : 'default'" size="large" @click="selectButton('anay')">
            <el-icon :size="20">
              <DataAnalysis />
            </el-icon>
            <span v-if="selectedButton === 'anay'">实验数据分析</span>
          </el-button>
          <el-button class="channel" :class="{ selected: selectedButton === 'channel' }"
            :type="selectedButton === 'channel' ? 'primary' : 'default'" size="large" @click="selectButton('channel')">
            <el-icon :size="20">
              <Odometer />
            </el-icon>
            <span v-if="selectedButton === 'channel'">通道分析模块</span>
          </el-button>
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
                    <el-icon><User /></el-icon>
                    <span class="label">身份</span>
                    <span class="value">{{ authorityLabel }}</span>
                  </div>
                </div>
              </div>
              <el-dropdown-item divided class="danger" @click="logout">
                <el-icon><SwitchButton /></el-icon>
                <span>退出登录</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
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
                <el-switch class="color_table_switch" v-model="color_table_value"
                  style="--el-switch-on-color: #409EFF; --el-switch-off-color: #409EFF" active-text="通道颜色"
                  inactive-text="异常颜色" />
              </span>
              <div>
                <el-scrollbar height="60vh" :always="false">
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
              <el-scrollbar height="60vh" :always="false">
                <div>
                  <ChannelTypeP />
                </div>
              </el-scrollbar>
            </el-card>
          </div>
        </el-aside>
        <el-container>
          <el-main class="test_main" v-if="selectedButton === 'anay'">
            <el-card class="data_exploration" shadow="never">
              <span style="display: flex; align-items: center; justify-content: space-between;">
                <span class="title">实验数据探索</span>
                <span style="display: flex; align-items: center;">
                  <span style="margin-right: 8px;">采样频率</span>
                  <el-input-number v-model="sampling" :precision="3" :step="0.1" :min="0.001" :max="1000"
                    @change="updateSampling" />
                  <span style="margin-left: 4px;">KHz</span>
                </span>
                <span>平滑度 <el-input-number v-model="smoothness" :precision="3" :step="0.025" :max="1" :min="0.0"
                    @change="updateSmoothness" /></span>
                <el-switch v-model="test_channel_number"
                  style="--el-switch-on-color: #409EFF; --el-switch-off-color: #409EFF" active-text="单通道多行"
                  inactive-text="多通道单行" />

                <el-switch 
                  v-model="boxSelect"
                  style="--el-switch-on-color: #00CED1; --el-switch-off-color: #00CED1" 
                  active-text="框选标注/编辑"
                  inactive-text="局部缩放" 
                  :disabled="!test_channel_number"
                />
                  
                <img src="/image1.png" style="height: 30px;" alt="图例" id="channelLegendImage">
                <div>
                  <el-button type="primary" @click="exportChannelSVG">
                    导出SVG<el-icon class="el-icon--right">
                      <Upload />
                    </el-icon>
                  </el-button>
                  <el-button type="primary" @click="exportChannelData">
                    导出数据<el-icon class="el-icon--right">
                      <Upload />
                    </el-icon>
                  </el-button>
                </div>
              </span>
              <div style=" height: 100%; position: relative;">
                <el-scrollbar height="58vh" :always="false">
                  <div v-if="test_channel_number === true">
                    <SingleChannelMultiRow />
                  </div>
                  <div v-if="test_channel_number === false">
                    <MultiChannelSingleRow ref="MultiChannelRef" v-if="selectedChannels.length > 0" />
                  </div>
                </el-scrollbar>
              </div>
            </el-card>
            <div class="two">
              <el-card class="two_left" shadow="never">
                <Sketch :key="selectedButton" />
              </el-card>
              <el-card class="two_right" shadow="never">
                <HeatMap />
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
                  <span>统一频率 <el-input-number v-model="unit_sampling" :precision="0" :step="10" :max="100000" />
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
                  <el-button type="primary" :icon="FolderChecked">另存为新通道</el-button>
                  <el-button type="primary" @click="exportResultSVG">
                    导出SVG<el-icon class="el-icon--right">
                      <Upload />
                    </el-icon>
                  </el-button>
                  <el-button type="primary" @click="exportResultData">
                    导出数据<el-icon class="el-icon--right">
                      <Upload />
                    </el-icon>
                  </el-button>
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
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted } from 'vue';
import { useStore } from 'vuex';
import { useRouter } from 'vue-router';
import { FolderChecked, Upload, User, SwitchButton } from '@element-plus/icons-vue'
import html2canvas from 'html2canvas';
import { ElMessage } from 'element-plus'
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

const store = useStore()
const router = useRouter()
const sampling = ref(1)
const smoothness = ref(0)

const person = computed(() => store.state.person);
const authority = computed(() => store.state.authority);

// 检查登录状态
const checkLoginStatus = () => {
  if (!person.value) {
    router.push('/');
  }
};

// 组件挂载时检查登录状态
onMounted(() => {
  checkLoginStatus();
});

// 监听 person 的变化
watch(person, (newValue) => {
  if (!newValue) {
    router.push('/');
  }
});

const avatarText = computed(() => person.value ? person.value.charAt(0) : 'U');

const authorityLabel = computed(() => authority.value === 0 ? '普通用户' : '管理员');

const avatarStyle = computed(() => {
  const colors = ['#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399'];
  const color = colors[authority.value % colors.length];
  return {
    backgroundColor: color,
    color: '#fff',
    cursor: 'pointer',
    border: '2px solid #fff',
    boxShadow: '0 2px 12px 0 rgba(0, 0, 0, 0.1)',
  };
});

const logout = () => {
  store.commit('setperson', '');
  store.commit('setauthority', 0);
  router.push('/');
};

const updateSampling = (value) => {
  store.dispatch('updateSampling', value)
}

const updateSmoothness = (value) => {
  store.dispatch('updateSmoothness', value)
}

const color_table_value = ref(true)
const test_channel_number = ref(true)
const unit_sampling = ref(10)
const selectedButton = ref('anay');

const MultiChannelRef = ref(null)
const resultRef = ref(null)
const channelDataCache = computed(() => store.state.channelDataCache);
const selectedChannels = computed(() => store.state.selectedChannels);

const boxSelect = computed({
  get: () => {
    if (!test_channel_number.value) {
      return false;
    }
    return store.state.isBoxSelect;
  },
  set: (value) => {
    if (test_channel_number.value) {
      store.dispatch('updateIsBoxSelect', value);
    }
  }
});

const selectButton = (button) => {
  selectedButton.value = button;
};


const channelSvgElementsRefs = computed(() => store.state.channelSvgElementsRefs);

// 修改通用的下载函数以使用现代的文件系统API
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

const exportChannelSVG = async () => {
  if (test_channel_number.value) {
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

const exportChannelData = async () => {
  if (test_channel_number.value) {
    // 单通道多行的情况
    for (let [index, svgElement] of channelSvgElementsRefs.value.entries()) {
      let channel = selectedChannels.value[index];
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      let data = channelDataCache.value[channelKey];
      const jsonData = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonData], { type: "application/json" });
      await downloadFile(blob, `${channel.channel_name}_${channel.shot_number}_data.json`, 'json');
    }
  } else {
    let channelsData = MultiChannelRef.value.channelsData;
    if (channelsData) {
      const jsonData = JSON.stringify(channelsData, null, 2);
      const blob = new Blob([jsonData], { type: "application/json" });
      await downloadFile(blob, "multi_channel_data.json", 'json');
    }
  }
};

const exportResultSVG = async () => {
  let svg = resultRef.value.resultSvgRef;
  if (svg) {
    try {
      const clonedSvgElement = svg.cloneNode(true);
      const svgData = new XMLSerializer().serializeToString(clonedSvgElement);
      
      // 创建 canvas
      const canvas = document.createElement('canvas');
      canvas.width = svg.width.baseVal.value;
      canvas.height = svg.height.baseVal.value;
      const ctx = canvas.getContext('2d');

      // 创建图像并等待加载
      const img = new Image();
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
        img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svgData);
      });

      // 绘制SVG
      ctx.drawImage(img, 0, 0);

      // 转换为blob并保存
      const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/png'));
      await downloadFile(blob, 'analysis_result.png', 'png');
    } catch (error) {
      console.error('导出SVG时出错:', error);
      ElMessage({
        message: '导出图像失败，请重试',
        type: 'error',
      });
    }
  }
};

const exportResultData = async () => {
  let data = resultRef.value.resultData;
  if (data) {
    const jsonData = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonData], { type: "application/json" });
    await downloadFile(blob, "analysis_result.json", 'json');
  }
};

// 修改 updateSelectedChannels mutation 的调用时机
watch(selectedChannels, async (newChannels, oldChannels) => {
  if (JSON.stringify(newChannels) !== JSON.stringify(oldChannels)) {
    // 确保在更新 selectedChannels 之前重置进度状态
    await nextTick();
    if (MultiChannelRef.value &&
      !test_channel_number.value &&
      MultiChannelRef.value.resetProgress) {
      MultiChannelRef.value.resetProgress();
    }
  }
}, { deep: true });

// 添加对 test_channel_number 的监听
watch(test_channel_number, (newValue) => {
  if (!newValue) {
    // 切换到多通道单行时，保存当前的 boxSelect 状态并设置为 false
    const currentBoxSelectState = store.state.isBoxSelect;
    store.dispatch('updateIsBoxSelect', false);
    // 将状态保存到 store 中（需要在 store 中添加新的状态）
    store.dispatch('updatePreviousBoxSelectState', currentBoxSelectState);
  } else {
    // 切换回单通道多行时，恢复之前的 boxSelect 状态
    const previousState = store.state.previousBoxSelectState;
    store.dispatch('updateIsBoxSelect', previousState);
  }
});
</script>


<style scoped lang="scss">
.header-row {
  display: flex;
  justify-content: space-between;
  font-weight: bold;
  width: 100%;
  text-align: center;
  padding: 5px 10px;
}


.title {
  color: #999;
}

.el-card {
  --el-card-padding: 8px;
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

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #ffffff;
  width: 100vw;
  height: 5vh;
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
  background: linear-gradient(to bottom, rgba(0,0,0,0.02), transparent);
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
    background: rgba(0,0,0,0.02);
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

.el-avatar {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  border: 2px solid rgba(255, 255, 255, 0.8);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.el-avatar:hover {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.aside {
  width:22vw;
  background-color: #e9e9e9;
  height: 95vh;
  padding: 5px;
  box-sizing: border-box;
  display: flex;
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
  margin-bottom: 5px;
}

.anay,
.channel {
  transition: all 0.2s;
}

.selected {
  font-weight: bold;
}

.table {
  flex-grow: 1;
  position: relative;
  display: flex;
  flex-direction: column;

  .color_table_switch {
    position: absolute;
    right: 10px;
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

  :deep(.el-scrollbar) {
    height: 100%;
    
    .el-scrollbar__wrap {
      overflow-x: hidden;
    }
  }
}

.test_main {
  background-color: #e9e9e9;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;

  .data_exploration {
    margin-bottom: 5px;
    width: 100%;
    height: 100%;
    flex: 2.1;
  }

  .two {
    display: flex;
    flex: 1;
    flex-grow: 1;
    gap: 5px;
    position: relative;

  }

  .two_left {
    flex: 1;
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
</style>
