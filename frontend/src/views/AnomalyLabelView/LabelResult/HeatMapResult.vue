<template>
  <span style="display: flex; align-items: center; justify-content: space-between;">
    <span class="title">自动识别和人工标注结果</span>
    <!-- <el-switch v-model="result_switch" style="--el-switch-on-color: #409EFF; --el-switch-off-color: #409EFF"
      active-text="他人标注模式" inactive-text="自己标注" /> -->
    <img src="/image2.png" style="height: 20px;" alt="图例" id="heatmapLegend">
    <div>
      <el-button type="primary" @click="exportHeatMapSvg">
        导出SVG<el-icon class="el-icon--right">
          <Upload />
        </el-icon>
      </el-button>
      <el-button type="primary" @click="exportHeatMapData">
        导出数据<el-icon class="el-icon--right">
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
          <svg id="heatmap" ref="HeatMapRef" preserveAspectRatio="xMidYMid slice"></svg>
        </div>
      </el-scrollbar>
    </div>
    <el-dialog v-model="showAnomalyDialog" title="异常信息" :modal="true" :close-on-click-modal="false"
      @close="handleDialogClose" class="anomaly-dialog">
      <el-scrollbar class="anomaly-scrollbar" height="60vh" :always="false">
        <div v-for="(anomaly, index) in anomalyDialogData" :key="index" class="anomaly-item">
          <el-descriptions :title="`异常 ${index + 1}`" :column="1" border class="anomaly-descriptions">
            <el-descriptions-item v-for="(value, key) in anomaly" :key="key" :label="formatKey(key)">
              {{ formatValue(value, key) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>
      </el-scrollbar>
    </el-dialog>
  </div>
</template>

<script setup>
import * as d3 from 'd3';
import { onMounted, watch, computed, ref, nextTick } from 'vue';
import { useStore } from 'vuex';
import { ElDialog, ElDescriptions, ElDescriptionsItem } from 'element-plus';
const result_switch = ref(true)


// 获取 Vuex store 中的状态
const store = useStore();
const selectedChannels = computed(() => store.state.selectedChannels);
const storePerson = computed(() => store.state.person);
const anomaliesByChannel = computed(() => store.state.anomalies);

// 异常信息对话框的数据和显示状态
const anomalyDialogData = ref([]);
const showAnomalyDialog = ref(false);

// 全局存储所有错误和异常的数据
let errorResults = [];

//导出功能函数
const HeatMapRef = ref(null)
const exportHeatMapSvg = () => {
  let HeatMap = HeatMapRef.value;
  console.log(HeatMapRef)
  if (HeatMap) {
    // 克隆 SVG 元素并创建一个新的 XML 序列化器
    const clonedSvgElement = HeatMap.cloneNode(true);
    const svgData = new XMLSerializer().serializeToString(clonedSvgElement);

    // 创建一个新的 Image 对象用于 SVG
    const svgImg = new Image();
    const svgBlob = new Blob([svgData], { type: 'image/svg+xml;charset=utf-8' });
    const svgUrl = URL.createObjectURL(svgBlob);

    svgImg.onload = function () {
      // 获取图例图片
      const legendImg = document.getElementById('heatmapLegend');

      legendImg.onload = function () {
        // 创建一个 canvas 元素
        const canvas = document.createElement('canvas');
        const legendWidth = legendImg.width;  // 缩小一半
        const legendHeight = legendImg.height; // 缩小一半
        const padding = 30
        const canvasWidth = Math.max(HeatMap.width.baseVal.value, legendImg.width);
        const canvasHeight = HeatMap.height.baseVal.value + legendImg.height + padding;
        canvas.width = canvasWidth;
        canvas.height = canvasHeight;
        const ctx = canvas.getContext('2d');

        // 绘制图例图片到 canvas 上（在最上面，缩小一半）
        ctx.drawImage(legendImg, canvasWidth-legendWidth - 30, 0, legendWidth, legendHeight);

        // 绘制 SVG 图像到 canvas 上（在图例图片的下方）
        ctx.drawImage(svgImg, 0, legendHeight + padding);

        // 导出为 PNG
        const pngData = canvas.toDataURL('image/png');

        // 创建一个链接并自动下载 PNG
        const link = document.createElement('a');
        link.href = pngData;
        link.download = 'exported_image_with_legend.png';
        link.click();

        // 释放 URL 对象
        URL.revokeObjectURL(svgUrl);
      };

      // 设置图例图片的源
      legendImg.src = legendImg.src; // 重新加载以确保图片正确绘制
    };

    // 设置 SVG 图片的源
    svgImg.src = svgUrl;
  }
}

const exportHeatMapData = () => {
  let HeatMapData = errorResults;

  const jsonData = JSON.stringify(HeatMapData, null, 2);
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
    sample_rate: '采样率',
    id: 'ID',
    channelName: '通道名称',
    startX: '开始时间',
    endX: '结束时间',
    anomalyCategory: '异常类别',
    anomalyDiagnosisName: '异常诊断名称',
    anomalyDescription: '异常描述',
    isStored: '是否已保存',
    // ... 可以添加更多的映射
  };

  return keyMapping[key] || key;
}

// 辅助函数：格式化值的显示
function formatValue(value, key) {
  if (key === 'startX' || key === 'endX') {
    return parseFloat(value).toFixed(4);
  }
  if (key === 'diagnostic_time') {
    return new Date(value).toLocaleString();
  }
  if (value === null || value === undefined || value === '') {
    return '无';
  }
  if (typeof value === 'boolean') {
    return value ? '是' : '否';
  }
  return value;
}

// 处理对话框关闭事件
function handleDialogClose() {
  anomalyDialogData.value = [];
}


onMounted(() => {
  watch(
    [selectedChannels, anomaliesByChannel],
    async ([newChannels, newAnomalies]) => {
      await nextTick();
      renderHeatmap(newChannels);
    },
    { immediate: true, deep: true }
  );
});



async function renderHeatmap(channels) {
  const heatmap = d3.select('#heatmap');

  // 清空之前的内容
  heatmap.selectAll('*').remove();


  if (channels.length === 0) {
    return;
  }

  // 设置常量
  const Domain = [-2, 6];
  const step = 0.5;
  const rectNum = Math.round((Domain[1] - Domain[0]) / step);

  const visData = {}; // { [channelKey]: data array }
  const errorColors = {}; // { [errorIdx]: color }
  let errorIdxCounter = 1;

  const errorPromises = [];

  // 重置 errorResults
  errorResults = [];

  // 对于每个通道
  for (const channel of channels) {
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;
    const channelType = channel.channel_type;
    visData[channelKey] = [];
    for (let i = 0; i < rectNum; i++) {
      visData[channelKey][i] = []; // 初始化为数组
    }

    // 对于每个错误
    for (const [errorIndex, error] of channel.errors.entries()) {
      const errorIdxCurrent = errorIdxCounter++;
      errorColors[errorIdxCurrent] = error.color;

      const errorName = error.error_name;

      // 构建请求参数
      const params = {
        channel_key: channelKey,
        channel_type: channelType,
        error_name: errorName,
        error_index: errorIndex,
      };

      const errorPromise = d3
        .json(
          `http://localhost:5000/api/error-data/?${new URLSearchParams(params).toString()}`
        )
        .then((errorData) => {
          // 存储带有 errorIdx 的错误数据
          errorResults.push({
            channelKey,
            errorIdx: errorIdxCurrent,
            errorData: errorData,
            isAnomaly: false,
          });
          return { channelKey, errorIdx: errorIdxCurrent, errorData };
        })
        .catch((err) => {
          console.error(
            `Failed to fetch error data for ${errorName} at index ${errorIndex}:`,
            err
          );
          return null;
        });

      errorPromises.push(errorPromise);
    }
  }

  // 等待所有错误数据加载完成
  await Promise.all(errorPromises);

  // 处理错误数据
  for (const result of errorResults) {
    if (!result) continue;
    const { channelKey, errorIdx, errorData } = result;
    const X_value_error = errorData['X_value_error'];

    // 对于每个错误区间
    for (const idxList of X_value_error) {
      if (!Array.isArray(idxList) || idxList.length === 0) {
        continue; // 跳过无效的错误区间数据
      }

      const left = Math.floor((idxList[0] - Domain[0]) / step);
      const right = Math.floor((idxList[idxList.length - 1] - Domain[0]) / step);
      for (let i = left; i <= right; i++) {
        if (i >= 0 && i < rectNum) {
          visData[channelKey][i].push(errorIdx); // 将错误索引加入数组
        }
      }
    }
  }

  // 处理异常数据（用户标注的异常）
  for (const channel of channels) {
    const channel_name = channel.channel_name;
    const channelKey = `${channel.channel_name}_${channel.shot_number}`;
    const channelAnomalies = anomaliesByChannel.value[channelKey] || [];

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

      const left = Math.floor((anomaly.startX - Domain[0]) / step);
      const right = Math.floor((anomaly.endX - Domain[0]) / step);
      for (let i = left; i <= right; i++) {
        if (i >= 0 && i < rectNum) {
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
      const channel = channels[i]; // 获取当前通道
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;

      // 在该通道的 g 元素中绘制大矩形
      d3.select(this)
        .selectAll('.heatmapRect')
        .data(d)
        .join('rect')
        .attr('class', 'heatmapRect')
        .attr('x', (d, j) => j * (rectW + margin.left))
        .attr('y', 0)
        .attr('width', rectW)
        .attr('height', rectH)
        .attr('rx', 3) // 设置圆角半径
        .attr('ry', 3) // 设置圆角半径
        .attr('fill', 'none') // 不填充颜色
        .attr('stroke', (d) => {
          if (d.length > 0) {
            if (channel.errors.length > 1) {
              return '#ccc'; // 多个错误，灰色边框
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
              if (
                errorData &&
                errorData.errorData.person !== storePerson.value
              ) {
                return errorColors[nonAnomalyIdx];
              } else if (d.some((idx) => isAnomaly(idx, channelKey))) {
                // 如果包含异常，使用橙色边框
                return 'orange';
              } else {
                return 'none';
              }
            }
          } else {
            return 'none'; // 正常数据无边框
          }
        })
        .attr('stroke-width', (d) => {
          if (d.length > 0) {
            return 3;
          } else {
            return 0;
          }
        })
        .attr('stroke-dasharray', (d) => {
          if (d.length > 0) {
            if (channel.errors.length > 1) {
              return '4 2'; // 多个错误，虚线边框
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
              if (
                errorData &&
                errorData.errorData.person !== storePerson.value
              ) {
                return '4 2'; // person 不同，虚线边框
              } else if (d.some((idx) => isAnomaly(idx, channelKey))) {
                // 如果包含异常，使用实线边框
                return '0';
              } else {
                return '0'; // person 相同，实线边框
              }
            }
          } else {
            return '0'; // 正常数据，实线边框（不可见）
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
          const filteredErrorsInRect = errorsInRect.map((e) => {
            const errorData = e.errorData;
            const { X_value_error, Y_value_error, ...filteredData } = errorData;
            // 将不存在的字段设置为 'unknown'
            Object.keys(filteredData).forEach((key) => {
              if (
                filteredData[key] === undefined ||
                filteredData[key] === null
              ) {
                filteredData[key] = 'unknown';
              }
            });
            return filteredData;
          });

          // 去除重复的异常信息
          const uniqueFilteredErrorsInRect = filteredErrorsInRect.filter(
            (item, index, self) =>
              index ===
              self.findIndex(
                (t) => JSON.stringify(t) === JSON.stringify(item)
              )
          );

          if (uniqueFilteredErrorsInRect.length > 0) {
            anomalyDialogData.value = uniqueFilteredErrorsInRect;
            showAnomalyDialog.value = true;
          } else {
            showAnomalyDialog.value = false;
          }
        });

      // 在大的矩形内绘制小的矩形
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
          const filteredErrorsInRect = errorsInRect.map((e) => {
            const errorData = e.errorData;
            const { X_value_error, Y_value_error, ...filteredData } = errorData;
            // 将不存在的字段设置为 'unknown'
            Object.keys(filteredData).forEach((key) => {
              if (
                filteredData[key] === undefined ||
                filteredData[key] === null
              ) {
                filteredData[key] = 'unknown';
              }
            });
            return filteredData;
          });

          // 去除重复的异常息
          const uniqueFilteredErrorsInRect = filteredErrorsInRect.filter(
            (item, index, self) =>
              index ===
              self.findIndex(
                (t) => JSON.stringify(t) === JSON.stringify(item)
              )
          );

          if (uniqueFilteredErrorsInRect.length > 0) {
            anomalyDialogData.value = uniqueFilteredErrorsInRect;
            showAnomalyDialog.value = true;
          } else {
            showAnomalyDialog.value = false;
          }
        });
    });
}
</script>

<style scoped lang="scss">
.heatmap-section {
  display: flex;
  flex-direction: column;
  width: 100%;
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
  width: 80% !important; // 根据需要调整对话框宽度
  max-width: 100%;
}

.anomaly-scrollbar {
  width: 100%;
}

.anomaly-item {
  width: 100%;
}

.anomaly-descriptions {
  width: 100%;
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
</style>
