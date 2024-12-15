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
                <p><span>用户:</span> {{ person }}</p>
                <p><span>权限: </span>{{ authorityLabel }}</p>
              </div>
              <el-dropdown-item divided @click="logout">退出</el-dropdown-item>
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
                <div class="header-row">
                  <span>通道类别</span>
                  <span>通道名 & 炮号</span>
                  <span>异常类别</span>
                </div>
                <el-scrollbar height="55vh" :always="false">
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
              <div class="header-row">
                <span>通道类别</span>
                <span>通道名</span>
                <span>异常类别</span>
              </div>
              <el-scrollbar height="55vh" :always="false">
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
                  <div class="sampling-control">
                    <el-input v-model="sampling" class="sampling-wrapper">
                      <template #prepend>
                        <el-button-group>
                          <el-button type="primary" @click="decreaseSampling(10)">-10</el-button>
                          <el-button type="primary" @click="decreaseSampling(1)">-1</el-button>
                          <el-button type="primary" @click="decreaseSampling(0.1)">-0.1</el-button>
                        </el-button-group>
                      </template>
                      <template #suffix>
                        KHz
                      </template>
                      <template #append>
                        <el-button-group>
                          <el-button type="primary" @click="increaseSampling(0.1)">+0.1</el-button>
                          <el-button type="primary" @click="increaseSampling(1)">+1</el-button>
                          <el-button type="primary" @click="increaseSampling(10)">+10</el-button>
                        </el-button-group>
                      </template>
                    </el-input>
                  </div>
                </span>
                <span>平滑度 <el-input-number v-model="smoothness" :precision="3" :step="0.025" :max="1" :min="0.0"
                    @change="updateSmoothness" /></span>
                <el-switch v-model="test_channel_number"
                  style="--el-switch-on-color: #409EFF; --el-switch-off-color: #409EFF" active-text="单通道多行"
                  inactive-text="多通道单行" />
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
                    <MultiChannelSingleRow ref="MultiChannelRef" v-if="selectedChannels.length > 0"/>
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
                  <ChannelCalculationResults ref="resultRef"/>
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
import { ref, computed, watch, nextTick } from 'vue';
import { useStore } from 'vuex';
import { FolderChecked, Upload } from '@element-plus/icons-vue'
import html2canvas from 'html2canvas';
// 颜色配置及通道选取组件
import ChannelType from '@/components/Channel-Type.vue';
import ExceptionType from '@/components/Exception-Type.vue';
import ChannelTypeP from '@/components/Channel-Type-P.vue';
import Filter from './Filter/Filter.vue';

import MultiChannelSingleRow from '@/views/AnomalyLabelView/DataExploration/MultiChannelSingleRow.vue';
import SingleChannelMultiRow from '@/views/AnomalyLabelView/DataExploration/SingleChannelMultiRow.vue';

import HeatMap from '@/views/AnomalyLabelView/LabelResult/HeatMapResult.vue';
import ListResult from '@/views/AnomalyLabelView/LabelResult/ListResult.vue';

import Sketch from '@/views/AnomalyLabelView/Sketch/Sketch.vue';


import ChannelCards from '@/views/ChannelAnalysisView/ChannelList/ChannelCards.vue';
import ChannelOperator from '../ChannelAnalysisView/ChannelOperator/ChannelOperator.vue';
import ChannelStr from '../ChannelAnalysisView/ChannelStr/ChannelStr.vue';
import ChannelCalculationResults from '@/views/ChannelAnalysisView/ChannelCalculation/ChannelCalculationResults.vue';

const store = useStore()
const sampling = ref(1)
const smoothness = ref(0)

const person = computed(() => store.state.person);
const authority = computed(() => store.state.authority);

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
  console.log('用户已退出');
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


const selectButton = (button) => {
  selectedButton.value = button;
};


const channelSvgElementsRefs = computed(() => store.state.channelSvgElementsRefs);


const exportChannelSVG = () => {
  if (test_channel_number.value) {
    // 单通道多行的情况
    channelSvgElementsRefs.value.forEach((svgElement, index) => {
      if (svgElement) {
        // 克隆 SVG 元素并创建一个新的 XML 序列化器
        const clonedSvgElement = svgElement.cloneNode(true);
        const svgData = new XMLSerializer().serializeToString(clonedSvgElement);

        // 创建一个新的 Image 对象用于 SVG
        const svgImg = new Image();
        const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
        const svgUrl = URL.createObjectURL(svgBlob);

        svgImg.onload = function () {
          // 获取图例图片
          const legendImg = document.getElementById('channelLegendImage');
          
          const canvas = document.createElement('canvas');
          const legendWidth = legendImg.width;  // 缩小一半
          const legendHeight = legendImg.height; // 缩小一半
          const padding = 30
          const canvasWidth = Math.max(svgElement.width.baseVal.value, legendImg.width);
          const canvasHeight = svgElement.height.baseVal.value + legendImg.height + padding;
          canvas.width = canvasWidth;
          canvas.height = canvasHeight;
          const ctx = canvas.getContext('2d');

          // 绘制图例图片到 canvas 上（在最上面，缩小一半）
          ctx.drawImage(legendImg, canvasWidth-legendWidth - 30, 0, legendWidth, legendHeight);

          // 绘制 SVG 图像到 canvas 上（图片的下方）
          ctx.drawImage(svgImg, 0, legendHeight + padding);

          // 导出为 PNG
          const pngData = canvas.toDataURL('image/png');

          // 创建一个链接并自动下载 PNG
          const link = document.createElement('a');
          link.href = pngData;
          link.download = `exported_image_with_legend_${index + 1}.png`; // 使用唯一的文件名
          link.click();

          // 释放 URL 对象
          URL.revokeObjectURL(svgUrl);
        };

        // 设置 SVG 图片的源
        svgImg.src = svgUrl;
      }
    });
  }
  else {
    let svgRef = MultiChannelRef.value.channelsSvgRef;
    if (svgRef) {
      // 克隆 SVG 元素并创建一个新的 XML 序列化器
      const clonedSvgElement = svgRef.cloneNode(true);
      const svgData = new XMLSerializer().serializeToString(clonedSvgElement);

      // 创建一个新的 Image 对象用于 SVG
      const svgImg = new Image();
      const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
      const svgUrl = URL.createObjectURL(svgBlob);

      svgImg.onload = function () {
        // 获取图例图片
        const legendImg = document.getElementById('channelLegendImage');

        legendImg.onload = function () {
          // 创建一个 canvas 元素
          // 使用 html2canvas 将 div 内容转换为 canvas
          html2canvas(document.getElementById('channelLegendContainer'),  { scale: 0.75 }).then(function(divCanvas) {
              const canvas = document.createElement('canvas');
              const legendWidth = legendImg.width;  // 缩小一半
              const legendHeight = legendImg.height; // 缩小一半
              const padding = 30
              const canvasWidth = Math.max(svgRef.width.baseVal.value, legendImg.width);
              const canvasHeight = svgRef.height.baseVal.value + legendImg.height + padding;
              canvas.width = canvasWidth;
              canvas.height = canvasHeight;
              const ctx = canvas.getContext('2d');



              // 绘制 SVG 图像到 canvas 上（在图例图片的下方）
              ctx.drawImage(divCanvas, 200, legendHeight + padding/2);
              // 绘制图例图片到 canvas 上（在最上面，缩小一半）
              ctx.drawImage(legendImg, canvasWidth-legendWidth - 30, 0, legendWidth, legendHeight);
              ctx.drawImage(svgImg, 0, legendHeight);

              // 导出为 PNG
              const pngData = canvas.toDataURL('image/png');

              // 创建一个链接并自动下载 PNG
              const link = document.createElement('a');
              link.href = pngData;
              link.download = 'exported_image_with_legend.png';
              link.click();

              // 释放 URL 对象
              URL.revokeObjectURL(svgUrl);
          })
        };

        // 设置图例图片的源
        legendImg.src = legendImg.src; // 重新加载以确保图片正确绘制
      };

      // 设置 SVG 图片的源
      svgImg.src = svgUrl;
    }
  }
};

const exportChannelData = () => {
  if (test_channel_number.value) {
    // 单通道多行的情况
    channelSvgElementsRefs.value.forEach((svgElement, index) => {
      let channel = selectedChannels.value[index];
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      let data = channelDataCache.value[channelKey];
      const jsonData = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonData], { type: "application/json" });
      const url = URL.createObjectURL(blob);

      // 创建一个下载链接，并点击下载
      const link = document.createElement("a");
      link.href = url;
      link.download = "channel_data.json";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // 释放 Blob URL
      URL.revokeObjectURL(url);
    })
  }
  else {
    let channelsData = MultiChannelRef.value.channelsData;
    if (channelsData) {
      let data = channelsData;
      const jsonData = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonData], { type: "application/json" });
      const url = URL.createObjectURL(blob);

      // 创建一个下载链接，并点击下载
      const link = document.createElement("a");
      link.href = url;
      link.download = "channel_data.json";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      // 释放 Blob URL
      URL.revokeObjectURL(url);
    }
  }
}



const exportResultSVG = () => {
  let svg = resultRef.value.resultSvgRef;
  if (svg) {
    // 克隆 SVG 元素并创建一个新的 XML 序列化器
    const clonedSvgElement = svg.cloneNode(true);
    const svgData = new XMLSerializer().serializeToString(clonedSvgElement);

    // 创建一个新的 Image 对象
    const img = new Image();
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const url = URL.createObjectURL(svgBlob);

    img.onload = function () {
      // 创建一个 canvas 元素
      const canvas = document.createElement('canvas');
      canvas.width = svg.width.baseVal.value;
      canvas.height = svg.height.baseVal.value;
      const ctx = canvas.getContext('2d');

      // 将 SVG 像绘制到 canvas 上
      ctx.drawImage(img, 0, 0);

      // 导出为 PNG
      const pngData = canvas.toDataURL('image/png');

      // 创建一个链接并自动下载 PNG
      const link = document.createElement('a');
      link.href = pngData;
      link.download = 'exported_image.png';
      link.click();

      // 释放 URL 对象
      URL.revokeObjectURL(url);
    };

    // 设置图片源为 SVG Blob URL
    img.src = url;
  }
}

const exportResultData = () => {
  let data = resultRef.value.resultData;

  const jsonData = JSON.stringify(data, null, 2);
  const blob = new Blob([jsonData], { type: "application/json" });
  const url = URL.createObjectURL(blob);

  // 创建一个下载链接，并点击下载
  const link = document.createElement("a");
  link.href = url;
  link.download = "error_data.json";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  // 释放 Blob URL
  URL.revokeObjectURL(url);
}

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

const increaseSampling = (step) => {
  let newValue = sampling.value + step;
  if (newValue > 10000) newValue = 10000;
  sampling.value = Number(newValue.toFixed(3));
  updateSampling(sampling.value);
};

const decreaseSampling = (step) => {
  let newValue = sampling.value - step;
  if (newValue < 0.001) newValue = 0.001;
  sampling.value = Number(newValue.toFixed(3));
  updateSampling(sampling.value);
};
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
  padding: 10px 0;
  min-width: 150px;
}

.user-info {
  flex-direction: column;
  padding: 10px 20px;
}

.user-info p {
  color: #303133;
  line-height: 1.5;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.el-dropdown-menu {
  min-width: 150px;
}

.el-avatar {
  transition: all 0.2s;
}

.el-avatar:hover {
  transform: scale(1.1);
}

.aside {
  width: 18vw;
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

  .color_table_switch {
    position: absolute;
    right: 10px;
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

.sampling-control {
  display: inline-flex;
  align-items: center;

  .sampling-wrapper {
    width: auto;
    
    :deep(.el-input__wrapper) {
      padding: 0 8px 0 0; // 给后缀留出一些空间
    }
    
    :deep(.el-input__inner) {
      width: 50px;
      text-align: center;
    }
    
    :deep(.el-input__suffix) {
      color: var(--el-text-color-regular);
      margin-right: 4px;
    }
    
    :deep(.el-input-group__prepend),
    :deep(.el-input-group__append) {
      padding: 0;
      background-color: transparent;
      border: none;
    }
    
    :deep(.el-button-group) {
      .el-button {
        margin: 0;
        border-radius: 0;
        color: white;
        
        &:hover {
          opacity: 0.9;
        }
        
        &:first-child {
          border-top-left-radius: 4px;
          border-bottom-left-radius: 4px;
        }
        
        &:last-child {
          border-top-right-radius: 4px;
          border-bottom-right-radius: 4px;
        }
      }
    }
  }
}

:deep(.el-button-group) {
  .el-button {
    margin: 0;
    border-radius: 0;
    color: white;
    
    &:hover {
      opacity: 0.9;
    }
    
    &:first-child {
      border-top-left-radius: 4px;
      border-bottom-left-radius: 4px;
    }
    
    &:last-child {
      border-top-right-radius: 4px;
      border-bottom-right-radius: 4px;
    }
  }
}

// 左侧按钮组（减号按钮，从深到浅）
:deep(.el-input-group__prepend) {
  .el-button-group {
    .el-button {
      &:nth-child(1) {
        background-color: #409EFF;
        border-color: #409EFF;
      }
      &:nth-child(2) {
        background-color: #66B1FF;
        border-color: #66B1FF;
      }
      &:nth-child(3) {
        background-color: #8CC5FF;
        border-color: #8CC5FF;
      }
    }
  }
}

// 右侧按钮组（加号按钮，从浅到深）
:deep(.el-input-group__append) {
  .el-button-group {
    .el-button {
      &:nth-child(1) {
        background-color: #8CC5FF;
        border-color: #8CC5FF;
      }
      &:nth-child(2) {
        background-color: #66B1FF;
        border-color: #66B1FF;
      }
      &:nth-child(3) {
        background-color: #409EFF;
        border-color: #409EFF;
      }
    }
  }
}
</style>
