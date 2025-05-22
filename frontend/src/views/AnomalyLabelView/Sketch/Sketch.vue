<template>
  <div class="container" :class="{ 'panel-open': resultsDrawerVisible }">
    <!-- 顶部操作栏，保留并恢复为中文 -->
    <div class="header">
      <span class="title">手绘查询
        <el-tooltip placement="top" effect="light">
          <template #content>
            <div style="max-width: 320px">
              <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">视图说明</div>
              <div style="margin-bottom:8px;">在画布上手绘一个模式，系统会在选中的通道数据中查找匹配的模式。</div>
              <hr style="margin:8px 0;">
              <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
              <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                <li>绘制操作：直接在画布上拖动鼠标绘制曲线，点击清除即可清除</li>
                <li>通道选择：在顶部下拉框选择需要匹配的通道</li>
                <li>查找范围：可设置整体查询的时间区间和数值区间</li>
                <li>匹配方法：调整低通滤波幅度和最后获得的匹配数量上限</li>
                <li>目标模式：设置手绘模式重复数、单个匹配结果的指标幅度和时间跨度</li>
                <li>全屏绘图：点击画板区域的右上角圆形全屏按钮可放大绘图区域</li>
                <li>匹配结果：通过右上角的展开/收起匹配结果按钮显示</li>
              </ul>
              <hr style="margin:8px 0;">
              <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">注意事项</div>
              <ul style="margin:0 0 0 18px;padding:0;list-style:disc;">
                <li>匹配结果仅供参考，建议人工复核</li>
              </ul>
            </div>
          </template>
          <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
        </el-tooltip>
      </span>
      <span class="channel-and-results-select">
        <span class="operate">
          <el-select v-model="selectedGunNumbers" placeholder="请选择需要匹配的通道" multiple collapse-tags clearable collapse-tags-tooltip class="select-gun-numbers">
            <el-option key="select-all" value="select-all" label="全选所有通道">
              <el-checkbox v-model="allSelected" @change="handleSelectAll">
                全选所有通道
              </el-checkbox>
            </el-option>
            <el-option v-for="group in selectV2Options" :key="'select-all-' + group.value" :value="'select-all-' + group.value" :label="'全选' + group.label">
              <el-checkbox v-model="groupSelectAll[group.value]" @change="(val) => handleSelectAllGroup(val, group)">
                全选{{ group.label }}
              </el-checkbox>
            </el-option>
            <el-option-group v-for="group in selectV2Options" :key="group.value" :label="group.label">
              <el-option v-for="option in group.children" :key="option.value" :label="option.label" :value="option.value" />
            </el-option-group>
          </el-select>
        </span>
        <el-button type="primary" @click="toggleResultsDrawer" :icon="List" style="width: 100%; bottom: 6px">
          {{ matchedResultsButtonText }}
        </el-button>
      </span>
    </div>
    <!-- 主体区域，左右分栏 -->
    <div class="main-content">
      <!-- 左侧2/3画板区域 -->
      <div class="sketch-area">
        <div class="canvas-container">
          <canvas ref="paperCanvas" id="paperCanvas" class="whiteboard-canvas" resize></canvas>
          <!-- <div class="segment-info" v-if="segmentInfo">{{ segmentInfo }}</div> -->
          <div class="buttons">
            <el-button type="primary" :icon="Search" @click="submitData" class="search-button">
              查询
            </el-button>
            <el-button type="danger" @click="clearCanvas" class="clear-button" style="margin-left: 8px;">
              清除
            </el-button>
          </div>
          <div class="zoom-button">
            <el-button type="primary" :icon="FullScreen" circle @click="openFullscreenCanvas"></el-button>
          </div>
        </div>
      </div>
      <!-- 右侧1/3操作区 -->
      <div class="operation-panel">
        <div class="params-area">
          <el-tabs v-model="activeTab" tab-position="top">
            <!-- 查找范围 -->
            <el-tab-pane name="range">
              <template #label>
                <span style=" text-align: center;">查找<br />范围</span>
              </template>
              <el-form label-width="80px" label-position="left">
                <el-form-item label="时间区间（单位s）" label-position="top">
                  <div style="display: flex; align-items: center; width: 100%;">
                    <el-input v-model="xFilterStart" placeholder="起点" style="width: 48%;" />
                    <span style="margin: 0 4px;">~</span>
                    <el-input v-model="xFilterEnd" placeholder="终点" style="width: 48%;" />
                  </div>
                </el-form-item>
                <el-form-item label="数值区间" label-position="top">
                  <div style="display: flex; align-items: center; width: 100%;">
                    <el-input v-model="yFilterStart" placeholder="起点" style="width: 48%;" />
                    <span style="margin: 0 4px;">~</span>
                    <el-input v-model="yFilterEnd" placeholder="终点" style="width: 48%;" />
                  </div>
                </el-form-item>
              </el-form>
            </el-tab-pane>
            <!-- 匹配方法 -->
            <el-tab-pane name="method">
              <template #label>
                <span style=" text-align: center;">匹配<br />方法</span>
              </template>
              <el-form label-width="80px" label-position="left">
                <el-form-item label-position="top">
                  <template #label>
                    <div style="display: flex; flex-direction: column;">
                      <span>低通滤波平滑幅度s</span>
                      <span style="font-size: 11px; color: #888; font-weight: normal; line-height: 1.2;">滤掉小于此周期的扰动(0.0001~0.1)</span>
                    </div>
                  </template>
                  <el-input v-model="lowpassAmplitude" style="width: 100%;" />
                </el-form-item>
                <el-form-item label="匹配上限">
                  <el-input v-model="maxMatchPerChannel" style="width: 100%;" />
                </el-form-item>
              </el-form>
            </el-tab-pane>
            <!-- 目标模式 -->
            <el-tab-pane name="target">
              <template #label>
                <span style=" text-align: center;">目标<br />模式</span>
              </template>
              <el-form label-width="80px" label-position="left">
                <el-form-item label="模式重复数">
                  <el-input v-model="patternRepeatCount" style="width: 100%;" />
                </el-form-item>
                <el-form-item label="指标幅度">
                  <el-input v-model="amplitudeLimit" placeholder="留空为不限制" style="width: 100%;" />
                </el-form-item>
                <el-form-item label="时间跨度">
                  <el-input v-model="timeSpanLimit" placeholder="留空为不限制" style="width: 100%;" />
                </el-form-item>
              </el-form>
            </el-tab-pane>
          </el-tabs>
        </div>
      </div>
    </div>

    <!-- 全屏绘图弹窗 -->
    <el-dialog v-model="dialogVisible" width="90%" :show-close="false" fullscreen :destroy-on-close="false" :close-on-click-modal="false" :close-on-press-escape="true">
      <template #header>
        <div class="custom-dialog-header">
          <span class="title">手绘查询</span>
          <el-button class="exit-fullscreen-btn" type="primary" @click="closeFullscreenCanvas">
            退出全屏
          </el-button>
        </div>
      </template>
      <div class="fullscreen-canvas-container">
        <canvas ref="fullscreenCanvas" id="fullscreenCanvas" class="fullscreen-whiteboard-canvas" resize></canvas>
        <div class="segment-info" v-if="segmentInfo">{{ segmentInfo }}</div>
        <div class="fullscreen-buttons">
          <el-button type="primary" @click="applyFullscreenDrawing">
            应用
          </el-button>
        </div>
      </div>
    </el-dialog>

    <!-- 匹配结果抽屉 -->
    <div class="results-panel" :class="{ 'panel-visible': resultsDrawerVisible }">
      <div class="panel-header">
        <span>匹配结果 ({{ sortedMatchedResults.length }})</span>
        <span class="collapse-button">
          收起
          <el-button @click="toggleResultsDrawer" :icon="ArrowLeft" circle />
        </span>
      </div>
      <div class="panel-content">
        <el-table ref="resultsTable" :data="groupedMatchedResults" v-model:selection="selectedMatchedResults" @selection-change="handleTableSelectionChange" height="calc(100vh - 83px)" size="default" border :span-method="objectSpanMethod">
          <el-table-column type="selection" width="40" align="center" />
          <el-table-column label="区间幅度s" min-width="110" align="center">
            <template #default="scope">
              <div class="amplitude-cell">
                <span class="group-value">≈{{ scope.row.groupAmplitude?.toFixed(6) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="通道名" min-width="90" align="center" show-overflow-tooltip prop="channelName" />
          <el-table-column label="炮号" min-width="60" align="center" prop="shotNumber" />
          <!-- <el-table-column label="平滑" min-width="60" align="center" prop="smoothLevel" /> -->
          <el-table-column label="匹配度" min-width="70" align="center">
            <template #default="scope">
              <span class="cell-number">{{ scope.row.confidence?.toFixed(3) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  ref,
  computed,
  onMounted,
  onUnmounted,
  watch,
} from 'vue';
import { Search, FullScreen, List, ArrowLeft } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useStore } from 'vuex';
import Paper from 'paper';

// 在导入Paper.js后立即添加猴子补丁，修改原生addEventListener方法
// 这个补丁会确保所有的touchstart事件都是passive的
(function patchAddEventListener() {
  // 保存原始方法
  const originalAddEventListener = EventTarget.prototype.addEventListener;

  // 替换为我们的修改版本
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    // 对于touchstart事件，强制使用passive: true
    if (type === 'touchstart') {
      let newOptions = options;
      if (typeof options === 'boolean') {
        // 如果options是布尔值（表示useCapture），创建一个新的对象
        newOptions = { capture: options, passive: true };
      } else if (typeof options === 'object') {
        // 如果options是对象，确保passive为true
        newOptions = { ...options, passive: true };
      } else {
        // 如果options未定义，使用默认的passive: true
        newOptions = { passive: true };
      }
      // 调用原始方法，但使用修改后的选项
      return originalAddEventListener.call(this, type, listener, newOptions);
    }

    // 对于其他事件类型，使用原始行为
    return originalAddEventListener.call(this, type, listener, options);
  };
})();

// 全局修复Paper.js的DomEvent.add方法，确保所有实例都使用相同的修复
const originalAdd = Paper.DomEvent.add;
Paper.DomEvent.add = function (element, events, handler) {
  if (typeof events === 'string' && events.includes('touchstart')) {
    // 分离事件字符串
    const eventArray = events.split(/\s+/);
    // 单独处理每个事件
    for (const event of eventArray) {
      if (event === 'touchstart') {
        element.addEventListener('touchstart', handler, { passive: true });
      } else if (event) {
        // 对非touchstart事件使用原始方法
        originalAdd.call(this, element, event, handler);
      }
    }
    return;
  }
  return originalAdd.call(this, element, events, handler);
};

// 使用 Vuex store
const store = useStore();

// 选中的炮号数组
const selectedGunNumbers = ref([]);

// 从 Vuex 获取 selectedChannels
const selectedChannels = computed(() => store.state.selectedChannels);

const selectV2Options = computed(() => {
  const grouped = selectedChannels.value.reduce((acc, channel) => {
    const { channel_type, channel_name, shot_number } = channel;
    if (!acc[channel_type]) {
      acc[channel_type] = [];
    }
    acc[channel_type].push({
      label: `${channel_name}_${shot_number}`,
      value: `${channel_name}_${shot_number}`,
    });
    return acc;
  }, {});

  return Object.keys(grouped).map((type) => ({
    label: type,
    value: type,
    children: grouped[type],
  }));
});

// ----------- Paper.js 绘图逻辑开始 -----------

// Paper.js 变量
let path = null;
let grid = null;
let paperScope = null;
let highlightGroup = null; // 用于存放高亮区间
const segmentInfo = ref('');
// 添加清除状态标记
const isClearing = ref(false);

// Paper.js canvas元素引用
const paperCanvas = ref(null);
// 添加ResizeObserver引用
let resizeObserver = null;
// 添加可见性变化检测
let visibilityCheckInterval = null;
// 添加MutationObserver引用
let mutationObserver = null;
// 添加resize事件处理函数引用
let handleResize = null;

// 添加选中的段点和手柄变量
let selectedSegment = null;
let selectedHandle = null;
let hitOptions = {
  segments: true,
  stroke: true,
  handles: true,
  tolerance: 5
};

// 创建网格
const createGrid = (width, height) => {
  // 清除现有网格
  if (grid) {
    grid.remove();
  }

  grid = new Paper.Group();

  // 网格间距
  const gridSpacing = 25;

  // 创建主网格
  for (let x = 0; x <= width; x += gridSpacing) {
    const line = new Paper.Path.Line(
      new Paper.Point(x, 0),
      new Paper.Point(x, height)
    );
    line.strokeColor = '#e6e6e6';
    line.strokeWidth = 0.8;
    grid.addChild(line);
  }

  for (let y = 0; y <= height; y += gridSpacing) {
    const line = new Paper.Path.Line(
      new Paper.Point(0, y),
      new Paper.Point(width, y)
    );
    line.strokeColor = '#e6e6e6';
    line.strokeWidth = 0.8;
    grid.addChild(line);
  }

  // 将网格置于底层
  grid.sendToBack();
  return grid;
};

// 调整画布大小
const resizeCanvas = () => {
  if (paperScope && paperScope.view) {
    // 重置视图大小
    paperScope.view.viewSize = new Paper.Size(
      paperCanvas.value.offsetWidth,
      paperCanvas.value.offsetHeight
    );

    // 重绘网格
    createGrid(paperCanvas.value.offsetWidth, paperCanvas.value.offsetHeight);

    // 重绘路径
    paperScope.view.draw();
  }
};

// 计算并绘制切线符号区间高亮背景
function updateHighlightBackground() {
  if (highlightGroup) {
    highlightGroup.remove();
    highlightGroup = null;
  }
  if (!path || !path.segments || path.segments.length < 2 || !paperScope) return;

  highlightGroup = new paperScope.Group();
  const colors = ['#ffcccc', '#ccffcc'];
  const segments = path.segments;
  let lastSign = null;
  let startIdx = 0;
  let colorIdx = 0;
  for (let i = 1; i < segments.length; i++) {
    const dx = segments[i].point.x - segments[i - 1].point.x;
    const dy = segments[i].point.y - segments[i - 1].point.y;
    if (dx === 0) continue; // 跳过竖直段
    const sign = Math.sign(dy / dx);
    if (sign === 0) continue; // 跳过水平段
    if (lastSign === null) lastSign = sign;
    if (sign !== lastSign) {
      // 画区间背景
      const left = segments[startIdx].point.x;
      const right = segments[i - 1].point.x;
      if (right > left) {
        const rect = new paperScope.Path.Rectangle({
          from: [left, 0],
          to: [right, paperCanvas.value.offsetHeight],
          fillColor: colors[colorIdx % 2],
          opacity: 0.3,
          insert: false
        });
        highlightGroup.addChild(rect);
      }
      startIdx = i - 1;
      lastSign = sign;
      colorIdx++;
    }
  }
  // 补画最后一个区间
  if (startIdx < segments.length - 1) {
    const left = segments[startIdx].point.x;
    const right = segments[segments.length - 1].point.x;
    if (right > left) {
      const rect = new paperScope.Path.Rectangle({
        from: [left, 0],
        to: [right, paperCanvas.value.offsetHeight],
        fillColor: colors[colorIdx % 2],
        opacity: 0.3,
        insert: false
      });
      highlightGroup.addChild(rect);
    }
  }
  highlightGroup.sendToBack();
  if (grid) highlightGroup.insertBelow(grid);
  else if (path) highlightGroup.insertBelow(path);
}

// 初始化Paper.js
const initPaperJs = () => {
  if (!paperCanvas.value) return;

  // 确保Paper.js还没有初始化
  if (paperScope) {
    paperScope.remove();
  }

  // 初始化Paper.js
  paperScope = new Paper.PaperScope();

  paperScope.setup(paperCanvas.value);

  // 创建网格
  createGrid(paperCanvas.value.offsetWidth, paperCanvas.value.offsetHeight);

  // 设置工具事件
  const tool = new paperScope.Tool();

  // 鼠标按下事件
  tool.onMouseDown = (event) => {
    if (isClearing.value) return;
    selectedSegment = null;
    selectedHandle = null;
    if (!path) {
      path = new paperScope.Path({
        segments: [event.point],
        strokeColor: 'black',
        strokeWidth: 2,
        strokeCap: 'round',
        strokeJoin: 'round'
      });
      updateHighlightBackground();
    }
  };

  // 鼠标拖动事件
  tool.onMouseDrag = (event) => {
    if (selectedSegment) {
      selectedSegment.point = selectedSegment.point.add(event.delta);
      updateHighlightBackground();
      return;
    }
    if (selectedHandle) {
      if (selectedHandle.type === 'handle-in') {
        selectedHandle.segment.handleIn = selectedHandle.segment.handleIn.add(event.delta);
      } else if (selectedHandle.type === 'handle-out') {
        selectedHandle.segment.handleOut = selectedHandle.segment.handleOut.add(event.delta);
      }
      updateHighlightBackground();
      return;
    }
    if (path && (!path.lastSegment || event.point.x >= path.lastSegment.point.x)) {
      path.add(event.point);
      segmentInfo.value = `点数: ${path.segments.length}`;
      updateHighlightBackground();
    }
  };

  // 鼠标释放事件
  tool.onMouseUp = (event) => {
    if (selectedSegment || selectedHandle) {
      selectedSegment = null;
      selectedHandle = null;
      updateHighlightBackground();
      return;
    }
    if (path && path.segments.length > 1) {
      const segmentCount = path.segments.length;
      if (!path.fullySelected) {
        path.simplify(10);
        path.fullySelected = true;
        const newSegmentCount = path.segments.length;
        const percentage = 100 - Math.round(newSegmentCount / segmentCount * 100);
        segmentInfo.value = `简化前点数: ${segmentCount}, 简化后点数: ${newSegmentCount}, 减少: ${percentage}%`;
        updateHighlightBackground();
      }
    }
    updateHighlightBackground();
  };
};

// 键盘事件处理函数
const handleKeyDown = (e) => {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    clearCanvas();
  }
};

// 添加MutationObserver来监测元素可见性变化
const setupMutationObserver = () => {
  // 创建监听器
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.attributeName === 'style' || mutation.attributeName === 'class') {
        // 当元素的style或class变化时，检查可见性
        if (paperCanvas.value && paperCanvas.value.offsetParent !== null) {
          // 元素变为可见，重新绘制
          setTimeout(() => {
            resizeCanvas();
          }, 100);
        }
      }
    });
  });

  // 找到父级.two元素
  const parentElement = paperCanvas.value?.closest('.two');
  if (parentElement) {
    // 开始监听
    observer.observe(parentElement, {
      attributes: true,
      attributeFilter: ['style', 'class']
    });
    return observer;
  }
  return null;
};

// 启动定期检查可见性的定时器
const startVisibilityCheck = () => {
  // 清除可能存在的旧定时器
  if (visibilityCheckInterval) {
    clearInterval(visibilityCheckInterval);
  }

  // 创建新定时器，每500ms检查一次可见性
  return setInterval(() => {
    if (paperCanvas.value && paperCanvas.value.offsetParent !== null) {
      // 元素可见，检查大小是否变化
      const currentWidth = paperCanvas.value.offsetWidth;
      const currentHeight = paperCanvas.value.offsetHeight;

      // 如果Paper.js视图尺寸与当前尺寸不同，重新绘制
      if (paperScope && paperScope.view &&
        (paperScope.view.viewSize.width !== currentWidth ||
          paperScope.view.viewSize.height !== currentHeight)) {
        resizeCanvas();
      }
    }
  }, 500);
};

// 参数区相关变量
import { reactive } from 'vue';
const lowpassAmplitude = ref(0.03); // 低通滤波幅度，默认0.03
const xFilterStart = ref('');
const xFilterEnd = ref('');
const yFilterStart = ref('');
const yFilterEnd = ref('');
const patternRepeatCount = ref(0); // 模式重复数量，默认0
const maxMatchPerChannel = ref(100); // 单通道获取匹配最大数量，默认100
const activeTab = ref('range');
const amplitudeLimit = ref(''); // 新增：指标幅度限制
const timeSpanLimit = ref(''); // 新增：时间跨度限制

// 提交数据函数
const submitData = async () => {
  // 获取绘制的路径数据（包括控制点信息以便重现曲线）
  const rawQueryPattern = path ? path.segments.map(segment => ({
    x: segment.point.x,
    y: paperCanvas.value.offsetHeight - segment.point.y,  // 在这里翻转Y轴
    handleIn: segment.handleIn ? {
      x: segment.handleIn.x,
      y: -segment.handleIn.y  // 翻转控制点的Y坐标
    } : null,
    handleOut: segment.handleOut ? {
      x: segment.handleOut.x,
      y: -segment.handleOut.y  // 翻转控制点的Y坐标
    } : null
  })) : [];

  if (rawQueryPattern.length > 0) {
    // 首先更新本地的查询模式
    store.dispatch('updateQueryPattern', { rawPattern: rawQueryPattern });

    // 检查是否有选中的通道
    if (selectedGunNumbers.value.length === 0) {
      ElMessage.warning('请选择需要匹配的通道');
      return;
    }

    try {
      // 显示加载中消息
      const loadingInstance = ElMessage({
        message: '正在搜索匹配的通道数据...',
        type: 'info',
        duration: 0
      });

      // 将选中的通道ID转换为通道对象
      const selectedChannels = selectedGunNumbers.value.map(channelId => {
        // 从选项中找到匹配的通道
        for (const group of selectV2Options.value) {
          for (const option of group.children) {
            if (option.value === channelId) {
              // 分离通道名和炮号，通道名可能包含多个下划线，所以只分离最后一个下划线
              const lastUnderscoreIndex = channelId.lastIndexOf('_');
              const channelName = channelId.substring(0, lastUnderscoreIndex);
              const shotNumber = channelId.substring(lastUnderscoreIndex + 1);
              return {
                channel_name: channelName,
                shot_number: shotNumber,
                channel_type: group.value
              };
            }
          }
        }
        return null;
      }).filter(channel => channel !== null);

      // 发送请求到后端，增加参数
      const response = await fetch('https://10.1.108.231:5000/api/sketch-query', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rawQueryPattern,
          sampling: 5,
          selectedChannels,
          lowpassAmplitude: Number(lowpassAmplitude.value),
          xFilterRange: [
            xFilterStart.value === '' ? null : Number(xFilterStart.value),
            xFilterEnd.value === '' ? null : Number(xFilterEnd.value)
          ],
          yFilterRange: [
            yFilterStart.value === '' ? null : Number(yFilterStart.value),
            yFilterEnd.value === '' ? null : Number(yFilterEnd.value)
          ],
          patternRepeatCount: Number(patternRepeatCount.value),
          maxMatchPerChannel: Number(maxMatchPerChannel.value),
          amplitudeLimit: amplitudeLimit.value === '' ? null : Number(amplitudeLimit.value),
          timeSpanLimit: timeSpanLimit.value === '' ? null : Number(timeSpanLimit.value)
        })
      });

      // 关闭加载消息
      loadingInstance.close();

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || '查询失败');
      }

      const data = await response.json();

      // 显示成功消息
      ElMessage.success(data.message || '查询成功');

      // 将结果存储到Vuex
      store.dispatch('updateMatchedResults', data.results);

      // console.log(store.state.matchedResults);

    } catch (error) {
      ElMessage.error(error.message || '查询过程中发生错误');
      console.error('手绘查询错误:', error);
    }
  } else {
    ElMessage.warning('请先绘制曲线');
  }
};

// 修改清除画布函数
const clearCanvas = () => {
  isClearing.value = true;
  resultsDrawerVisible.value = false;
  store.dispatch('clearMatchedResults');
  if (paperScope) {
    if (path) {
      path.remove();
      path = null;
    }
    segmentInfo.value = '';
    // 清除高亮
    if (highlightGroup) {
      highlightGroup.remove();
      highlightGroup = null;
    }
  }
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      isClearing.value = false;
    });
  });
};

// 添加全选状态处理
const groupSelectAll = ref({});

// 处理分组全选
const handleSelectAllGroup = (checked, group) => {
  const groupValues = group.children.map(item => item.value);

  if (checked) {
    // 全选当前分组
    const newSelection = new Set([...selectedGunNumbers.value]);
    groupValues.forEach(value => newSelection.add(value));
    selectedGunNumbers.value = Array.from(newSelection);
  } else {
    // 取消全选当前分组
    selectedGunNumbers.value = selectedGunNumbers.value.filter(
      value => !groupValues.includes(value)
    );
  }
};

// 添加全选状态
const allSelected = ref(false);

// 获取所有可选值
const getAllOptions = computed(() => {
  return selectV2Options.value.reduce((acc, group) => {
    return acc.concat(group.children.map(item => item.value));
  }, []);
});

// 处理全选所有通道
const handleSelectAll = (checked) => {
  if (checked) {
    // 全选所有通道
    selectedGunNumbers.value = getAllOptions.value;
  } else {
    // 取消全选
    selectedGunNumbers.value = [];
  }
};

// 修改原有的 watch 函数，增加对全选状态的监控
watch(selectedGunNumbers, (newVal) => {
  // 更新分组全选状态
  selectV2Options.value.forEach(group => {
    const groupValues = group.children.map(item => item.value);
    const selectedGroupValues = newVal.filter(value => groupValues.includes(value));
    groupSelectAll.value[group.value] = selectedGroupValues.length === groupValues.length;
  });

  // 更新全部全选状态
  const allOptions = getAllOptions.value;
  allSelected.value = allOptions.length > 0 &&
    allOptions.every(value => newVal.includes(value));
});

// 组件挂载时执行的逻辑
onMounted(() => {
  if (paperCanvas.value) {
    // 初始化Paper.js
    initPaperJs();

    // 给canvas元素添加passive触摸事件处理
    const passiveTouchHandler = () => { };
    paperCanvas.value.addEventListener('touchstart', passiveTouchHandler, { passive: true });

    // 设置ResizeObserver监听容器大小变化
    if (window.ResizeObserver) {
      resizeObserver = new ResizeObserver(() => {
        if (paperCanvas.value) {
          resizeCanvas();
        }
      });
      resizeObserver.observe(paperCanvas.value);
    }

    // 设置MutationObserver
    mutationObserver = setupMutationObserver();

    // 启动可见性检查
    visibilityCheckInterval = startVisibilityCheck();

    // 监听DOM大小变化
    handleResize = () => {
      resizeCanvas();
    };
    window.addEventListener('resize', handleResize);
  }

  // 监听键盘事件
  window.addEventListener('keydown', handleKeyDown);

  // 初始化分组全选状态
  selectV2Options.value.forEach(group => {
    groupSelectAll.value[group.value] = false;
  });
  allSelected.value = false;
});

// 组件卸载时清理资源
onUnmounted(() => {
  // 清理Paper.js实例
  if (paperScope) {
    paperScope.remove();
    paperScope = null;
  }

  // 清理ResizeObserver
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }

  // 清理MutationObserver
  if (mutationObserver) {
    mutationObserver.disconnect();
    mutationObserver = null;
  }

  // 清理可见性检查定时器
  if (visibilityCheckInterval) {
    clearInterval(visibilityCheckInterval);
    visibilityCheckInterval = null;
  }

  // 移除resize事件监听
  if (handleResize) {
    window.removeEventListener('resize', handleResize);
    handleResize = null;
  }

  // 移除全局键盘事件监听器
  window.removeEventListener('keydown', handleKeyDown);
});

// 弹窗相关变量
const dialogVisible = ref(false);
const fullscreenCanvas = ref(null);
let fullscreenPaperScope = null;
let fullscreenPath = null;
let fullscreenHighlightGroup = null; // 全屏高亮区间
let fullscreenSelectedSegment = null; // 全屏选中段点
let fullscreenSelectedHandle = null;  // 全屏选中手柄

// 打开全屏绘图弹窗
const openFullscreenCanvas = () => {
  dialogVisible.value = true;

  // 弹窗打开后初始化全屏绘图区域
  setTimeout(() => {
    initFullscreenPaper();

    // 给全屏canvas元素添加passive触摸事件处理
    if (fullscreenCanvas.value) {
      const passiveTouchHandler = () => { };
      fullscreenCanvas.value.addEventListener('touchstart', passiveTouchHandler, { passive: true });
    }

    // 如果原画布有内容，复制到全屏画布
    if (path && path.segments && path.segments.length > 0) {
      copyPathToFullscreen();
    }
  }, 100);
};

// 初始化全屏Paper.js
const initFullscreenPaper = () => {
  if (!fullscreenCanvas.value) return;
  if (fullscreenPaperScope) {
    fullscreenPaperScope.remove();
  }
  fullscreenPaperScope = new Paper.PaperScope();
  fullscreenPaperScope.setup(fullscreenCanvas.value);
  createFullscreenGrid(fullscreenCanvas.value.offsetWidth, fullscreenCanvas.value.offsetHeight);
  const tool = new fullscreenPaperScope.Tool();
  tool.onMouseDown = (event) => {
    fullscreenSelectedSegment = null;
    fullscreenSelectedHandle = null;
    // 检查是否点击了现有路径上的段点或手柄
    if (fullscreenPath) {
      const hitResult = fullscreenPath.hitTest(event.point, hitOptions);
      if (hitResult) {
        if (hitResult.type === 'segment') {
          fullscreenSelectedSegment = hitResult.segment;
          return;
        } else if (hitResult.type === 'handle-in' || hitResult.type === 'handle-out') {
          fullscreenSelectedHandle = hitResult;
          return;
        }
      }
    }
    if (fullscreenPath) {
      fullscreenPath.remove();
      fullscreenPath = null;
      segmentInfo.value = '';
      if (fullscreenHighlightGroup) {
        fullscreenHighlightGroup.remove();
        fullscreenHighlightGroup = null;
      }
    }
    fullscreenPath = new fullscreenPaperScope.Path({
      segments: [event.point],
      strokeColor: 'black',
      strokeWidth: 2,
      strokeCap: 'round',
      strokeJoin: 'round'
    });
    updateFullscreenHighlightBackground();
  };
  tool.onMouseDrag = (event) => {
    if (fullscreenSelectedSegment) {
      fullscreenSelectedSegment.point = fullscreenSelectedSegment.point.add(event.delta);
      updateFullscreenHighlightBackground();
      return;
    }
    if (fullscreenSelectedHandle) {
      if (fullscreenSelectedHandle.type === 'handle-in') {
        fullscreenSelectedHandle.segment.handleIn = fullscreenSelectedHandle.segment.handleIn.add(event.delta);
      } else if (fullscreenSelectedHandle.type === 'handle-out') {
        fullscreenSelectedHandle.segment.handleOut = fullscreenSelectedHandle.segment.handleOut.add(event.delta);
      }
      updateFullscreenHighlightBackground();
      return;
    }
    if (fullscreenPath && (!fullscreenPath.lastSegment || event.point.x >= fullscreenPath.lastSegment.point.x)) {
      fullscreenPath.add(event.point);
      segmentInfo.value = `点数: ${fullscreenPath.segments.length}`;
      updateFullscreenHighlightBackground();
    }
  };
  tool.onMouseUp = (event) => {
    if (fullscreenSelectedSegment || fullscreenSelectedHandle) {
      fullscreenSelectedSegment = null;
      fullscreenSelectedHandle = null;
      updateFullscreenHighlightBackground();
      return;
    }
    if (fullscreenPath && fullscreenPath.segments.length > 1) {
      const segmentCount = fullscreenPath.segments.length;
      if (!fullscreenPath.fullySelected) {
        fullscreenPath.simplify(10);
        fullscreenPath.fullySelected = true;
        const newSegmentCount = fullscreenPath.segments.length;
        const percentage = 100 - Math.round(newSegmentCount / segmentCount * 100);
        segmentInfo.value = `简化前点数: ${segmentCount}, 简化后点数: ${newSegmentCount}, 减少: ${percentage}%`;
        updateFullscreenHighlightBackground();
      }
    }
    updateFullscreenHighlightBackground();
  };
};

// 创建全屏网格
const createFullscreenGrid = (width, height) => {
  // 清除现有网格
  if (fullscreenPaperScope.project.activeLayer.children.find(child => child.name === 'grid')) {
    fullscreenPaperScope.project.activeLayer.children.find(child => child.name === 'grid').remove();
  }

  const grid = new fullscreenPaperScope.Group();
  grid.name = 'grid';

  // 网格间距
  const gridSpacing = 50;

  // 创建主网格
  for (let x = 0; x <= width; x += gridSpacing) {
    const line = new fullscreenPaperScope.Path.Line(
      new fullscreenPaperScope.Point(x, 0),
      new fullscreenPaperScope.Point(x, height)
    );
    line.strokeColor = '#e6e6e6';
    line.strokeWidth = 0.8;
    grid.addChild(line);
  }

  for (let y = 0; y <= height; y += gridSpacing) {
    const line = new fullscreenPaperScope.Path.Line(
      new fullscreenPaperScope.Point(0, y),
      new fullscreenPaperScope.Point(width, y)
    );
    line.strokeColor = '#e6e6e6';
    line.strokeWidth = 0.8;
    grid.addChild(line);
  }

  // 将网格置于底层
  grid.sendToBack();
  return grid;
};

// 将原始画布的路径复制到全屏画布
const copyPathToFullscreen = () => {
  if (!path || !path.segments || !fullscreenPaperScope) return;

  // 删除现有路径
  if (fullscreenPath) {
    fullscreenPath.remove();
  }

  // 计算缩放因子
  const scaleX = fullscreenCanvas.value.offsetWidth / paperCanvas.value.offsetWidth;
  const scaleY = fullscreenCanvas.value.offsetHeight / paperCanvas.value.offsetHeight;

  // 创建新路径
  fullscreenPath = new fullscreenPaperScope.Path({
    strokeColor: 'black',
    strokeWidth: 2,
    strokeCap: 'round',
    strokeJoin: 'round'
  });

  // 复制所有段点和手柄
  path.segments.forEach(segment => {
    const newSegment = new fullscreenPaperScope.Segment(
      new fullscreenPaperScope.Point(segment.point.x * scaleX, segment.point.y * scaleY)
    );

    if (segment.handleIn) {
      newSegment.handleIn = new fullscreenPaperScope.Point(
        segment.handleIn.x * scaleX,
        segment.handleIn.y * scaleY
      );
    }

    if (segment.handleOut) {
      newSegment.handleOut = new fullscreenPaperScope.Point(
        segment.handleOut.x * scaleX,
        segment.handleOut.y * scaleY
      );
    }

    fullscreenPath.add(newSegment);
  });
  // 复制完路径后，更新全屏高亮辅助
  updateFullscreenHighlightBackground();
};

// 将全屏画布的路径应用到原始画布
const applyFullscreenDrawing = () => {
  if (!fullscreenPath || !fullscreenPath.segments || !paperScope) {
    closeFullscreenCanvas();
    return;
  }

  // 删除原始路径
  if (path) {
    path.remove();
  }

  // 计算缩放因子
  const scaleX = paperCanvas.value.offsetWidth / fullscreenCanvas.value.offsetWidth;
  const scaleY = paperCanvas.value.offsetHeight / fullscreenCanvas.value.offsetHeight;

  // 创建新路径
  path = new paperScope.Path({
    strokeColor: 'black',
    strokeWidth: 2,
    strokeCap: 'round',
    strokeJoin: 'round'
  });

  // 复制所有段点和手柄
  fullscreenPath.segments.forEach(segment => {
    const newSegment = new paperScope.Segment(
      new paperScope.Point(segment.point.x * scaleX, segment.point.y * scaleY)
    );

    if (segment.handleIn) {
      newSegment.handleIn = new paperScope.Point(
        segment.handleIn.x * scaleX,
        segment.handleIn.y * scaleY
      );
    }

    if (segment.handleOut) {
      newSegment.handleOut = new paperScope.Point(
        segment.handleOut.x * scaleX,
        segment.handleOut.y * scaleY
      );
    }

    path.add(newSegment);
  });

  // 更新段点信息
  segmentInfo.value = `点数: ${path.segments.length}`;

  // 复制完路径后，更新主画板高亮辅助
  updateHighlightBackground();

  // 关闭弹窗
  closeFullscreenCanvas();
};

// 清除全屏画布
const clearFullscreenCanvas = () => {
  if (fullscreenPaperScope) {
    if (fullscreenPath) {
      fullscreenPath.remove();
      fullscreenPath = null;
    }
    segmentInfo.value = '';
    if (fullscreenHighlightGroup) {
      fullscreenHighlightGroup.remove();
      fullscreenHighlightGroup = null;
    }
    // 重置全屏选中段点和手柄
    fullscreenSelectedSegment = null;
    fullscreenSelectedHandle = null;
  }
};

// 关闭全屏绘图弹窗
const closeFullscreenCanvas = () => {
  dialogVisible.value = false;
};

// 全屏高亮区间绘制方法
function updateFullscreenHighlightBackground() {
  if (fullscreenHighlightGroup) {
    fullscreenHighlightGroup.remove();
    fullscreenHighlightGroup = null;
  }
  if (!fullscreenPath || !fullscreenPath.segments || fullscreenPath.segments.length < 2 || !fullscreenPaperScope) return;

  fullscreenHighlightGroup = new fullscreenPaperScope.Group();
  const colors = ['#ffcccc', '#ccffcc'];
  const segments = fullscreenPath.segments;
  let lastSign = null;
  let startIdx = 0;
  let colorIdx = 0;
  for (let i = 1; i < segments.length; i++) {
    const dx = segments[i].point.x - segments[i - 1].point.x;
    const dy = segments[i].point.y - segments[i - 1].point.y;
    if (dx === 0) continue;
    const sign = Math.sign(dy / dx);
    if (sign === 0) continue;
    if (lastSign === null) lastSign = sign;
    if (sign !== lastSign) {
      const left = segments[startIdx].point.x;
      const right = segments[i - 1].point.x;
      if (right > left) {
        const rect = new fullscreenPaperScope.Path.Rectangle({
          from: [left, 0],
          to: [right, fullscreenCanvas.value.offsetHeight],
          fillColor: colors[colorIdx % 2],
          opacity: 0.3,
          insert: false
        });
        fullscreenHighlightGroup.addChild(rect);
      }
      startIdx = i - 1;
      lastSign = sign;
      colorIdx++;
    }
  }
  // 补画最后一个区间
  if (startIdx < segments.length - 1) {
    const left = segments[startIdx].point.x;
    const right = segments[segments.length - 1].point.x;
    if (right > left) {
      const rect = new fullscreenPaperScope.Path.Rectangle({
        from: [left, 0],
        to: [right, fullscreenCanvas.value.offsetHeight],
        fillColor: colors[colorIdx % 2],
        opacity: 0.3,
        insert: false
      });
      fullscreenHighlightGroup.addChild(rect);
    }
  }
  fullscreenHighlightGroup.sendToBack();
  // 保证在网格下方
  const grid = fullscreenPaperScope.project.activeLayer.children.find(child => child.name === 'grid');
  if (grid) fullscreenHighlightGroup.insertBelow(grid);
  else if (fullscreenPath) fullscreenHighlightGroup.insertBelow(fullscreenPath);
}

// 匹配结果抽屉相关变量
const resultsDrawerVisible = ref(false);
const selectedMatchedResults = ref([]);
// 全选状态
const allMatchedSelected = ref(false);
// 排序后的匹配结果
const sortedMatchedResults = computed(() => {
  // 按confidence降序排列
  return [...store.state.matchedResults].sort((a, b) => (b.confidence || 0) - (a.confidence || 0));
});

// 根据区间幅度自动分组后的结果
const groupedMatchedResults = computed(() => {
  if (sortedMatchedResults.value.length === 0) return [];

  // 1. 提取所有区间幅度值并排序
  const amplitudes = sortedMatchedResults.value.map((item, originalIndex) => {
    const amplitude = item.range?.[0]?.[1] - item.range?.[0]?.[0] || 0;
    return { ...item, amplitude, originalIndex }; // 保存原始索引
  }).sort((a, b) => b.amplitude - a.amplitude);

  // 2. 使用简单的聚类方法确定分组
  const groups = [];
  let currentGroup = [amplitudes[0]];

  // 计算相邻值差异的平均值作为分组阈值
  const diffs = [];
  for (let i = 1; i < amplitudes.length; i++) {
    diffs.push(amplitudes[i - 1].amplitude - amplitudes[i].amplitude);
  }

  // 使用差值平均值的1.5倍作为分组阈值
  const avgDiff = diffs.reduce((sum, diff) => sum + diff, 0) / Math.max(1, diffs.length);
  const threshold = avgDiff * 1.5;

  // 根据阈值进行分组
  for (let i = 1; i < amplitudes.length; i++) {
    const diff = Math.abs(amplitudes[i - 1].amplitude - amplitudes[i].amplitude);

    if (diff > threshold) {
      // 差值大于阈值，创建新组
      groups.push([...currentGroup]);
      currentGroup = [amplitudes[i]];
    } else {
      // 差值小于阈值，添加到当前组
      currentGroup.push(amplitudes[i]);
    }
  }

  // 添加最后一组
  if (currentGroup.length > 0) {
    groups.push(currentGroup);
  }

  // 3. 为每个结果项添加组信息、组内排序和平均幅度值
  return groups.map((group, groupIndex) => {
    // 计算组内平均幅度值
    const avgAmplitude = group.reduce((sum, item) => sum + item.amplitude, 0) / group.length;

    return group.map(item => ({
      ...item,
      groupIndex,
      groupSize: group.length,
      // 使用组内平均幅度值作为统一显示
      groupAmplitude: avgAmplitude
    }));
  }).flat();
});

// 获取所有匹配结果id，使用原始索引
const allMatchedIds = computed(() => groupedMatchedResults.value.map(item =>
  `${item.channelName}_${item.shotNumber}_${item.originalIndex}`
));

// 动态按钮文本，抽屉展开时显示Collapse，收起时显示Expand
const matchedResultsButtonText = computed(() =>
  resultsDrawerVisible.value ? '收起查询结果' : '展开查询结果'
);

// 控制抽屉展开和收起
const toggleResultsDrawer = () => {
  resultsDrawerVisible.value = !resultsDrawerVisible.value;

  // 当打开面板时，确保所有结果都被选中
  if (resultsDrawerVisible.value && sortedMatchedResults.value.length > 0) {
    // 关键：直接赋值为所有行对象，实现el-table自动全选
    selectedMatchedResults.value = [...groupedMatchedResults.value];
    // 同步id到store
    store.commit('setVisibleMatchedResultIds', allMatchedIds.value);
  }
};

// 表格选择变化处理
const handleTableSelectionChange = (selection) => {
  // selection是被选中的行对象数组
  selectedMatchedResults.value = selection;
  // 同步id到store
  const ids = selection.map(row =>
    `${row.channelName}_${row.shotNumber}_${row.originalIndex}`
  );
  store.commit('setVisibleMatchedResultIds', ids);
  allMatchedSelected.value = selection.length === groupedMatchedResults.value.length && selection.length > 0;
};

// 监听selectedMatchedResults变化，更新全选状态
watch(selectedMatchedResults, (newVal) => {
  allMatchedSelected.value = newVal.length === groupedMatchedResults.value.length && newVal.length > 0;
});

// 监听匹配结果，有新结果时自动展开抽屉
watch(sortedMatchedResults, (newVal) => {
  if (newVal.length > 0) {
    resultsDrawerVisible.value = true;
    // 关键：直接赋值为所有行对象，实现el-table自动全选
    selectedMatchedResults.value = [...groupedMatchedResults.value];
    // 同步id到store
    store.commit('setVisibleMatchedResultIds', allMatchedIds.value);
  }
}, { immediate: true });

// 表格单元格合并方法
const objectSpanMethod = ({ row, column, rowIndex, columnIndex }) => {
  // 选择框列不参与合并
  if (columnIndex === 0) {
    return {
      rowspan: 1,
      colspan: 1
    };
  }

  // 区间幅度列需要合并
  if (columnIndex === 1) {
    if (isGroupStart(rowIndex)) {
      // 计算当前组有多少行
      let rowCount = 1;
      for (let i = rowIndex + 1; i < groupedMatchedResults.value.length; i++) {
        if (groupedMatchedResults.value[i].groupIndex === row.groupIndex) {
          rowCount++;
        } else {
          break;
        }
      }

      return {
        rowspan: rowCount,
        colspan: 1
      };
    } else {
      // 非组的第一行，区间幅度不显示
      return {
        rowspan: 0,
        colspan: 0
      };
    }
  }

  return {
    rowspan: 1,
    colspan: 1
  };
};

// 判断是否是组的第一个元素（用于显示组标签）
const isGroupStart = (index) => {
  if (index === 0) return true;
  const currentRow = groupedMatchedResults.value[index];
  const prevRow = groupedMatchedResults.value[index - 1];
  return currentRow.groupIndex !== prevRow.groupIndex;
};
</script>

<style scoped>
.container {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}

.header {
  padding: 0px 0 5px 0;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.operate {
  display: flex;
  align-items: center;
}

.select-gun-numbers {
  margin-left: 8px;
  width: 200px;
}

.main-content {
  display: flex;
  flex: 1;
  height: 100%;
  width: 100%;
}

.sketch-area {
  flex: 3;
  min-width: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid #eee;
  border-radius: 4px;
}

.operation-panel {
  flex: 1;
  padding: 3px;
  display: flex;
  flex-direction: column;
  border: 1px solid #eee;
  border-radius: 4px;
}

.params-area {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
}

.canvas-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  touch-action: none;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  overscroll-behavior: contain;
  pointer-events: auto;
  isolation: isolate;
}

.whiteboard-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: white;
  touch-action: none !important;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  overscroll-behavior: contain;
  pointer-events: auto;
  isolation: isolate;
}

.segment-info {
  position: absolute;
  bottom: 10px;
  left: 10px;
  background-color: rgba(255, 255, 255, 0.8);
  padding: 5px 10px;
  border-radius: 4px;
  font-size: 12px;
  color: #333;
}

.buttons {
  position: absolute;
  bottom: 0px;
  right: 6px;
}

.zoom-button {
  position: absolute;
  top: 6px;
  right: 6px;
  z-index: 10;
}

.fullscreen-canvas-container {
  position: relative;
  width: 100%;
  height: calc(100vh - 121px);
  background-color: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  overflow: hidden;
}

.fullscreen-whiteboard-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: white;
  touch-action: none !important;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  overscroll-behavior: contain;
  pointer-events: auto;
  isolation: isolate;
}

.fullscreen-buttons {
  position: absolute;
  bottom: 20px;
  right: 20px;
  display: flex;
  gap: 10px;
}

.custom-dialog-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #eee;
}

.custom-dialog-header {
  color: #333;
  font-weight: bold;
  font-size: 12pt;
  margin-left: 5px;
}

.exit-fullscreen-btn {
  margin-left: auto;
  font-size: 14px;
}

.results-panel {
  position: fixed;
  top: 0;
  left: 0;
  width: 24.5vw;
  height: 100vh;
  background-color: white;
  transform: translateX(-100%);
  transition: transform 0.3s ease;
  z-index: 2000;
  box-shadow: 2px 0 10px rgba(0, 0, 0, 0.1);
  overflow: hidden;
  /* 防止外部滚动条 */
}

.panel-header {
  padding: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #eee;
}

.panel-content {
  padding: 10px;
  height: calc(100vh - 60px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  /* 修改为hidden，将滚动交给表格 */
}

.panel-header span {
  font-size: 16px;
  font-weight: bold;
}

.panel-header .el-button {
  font-size: 14px;
}

.panel-visible {
  transform: translateX(0);
}

/* 添加匹配结果面板打开时的标识，用于视觉反馈 */
.results-toggle-active {
  background-color: #67c23a !important;
  border-color: #67c23a !important;
}

/* 确保el-table不会导致额外的滚动条 */
:deep(.el-table) {
  width: 100% !important;
  max-width: 100%;
  overflow: hidden;
  --el-table-border-color: #ebeef5;
  border-color: transparent;
  font-size: 14px;
  /* 增大基础字体大小 */
}

:deep(.el-table__body-wrapper) {
  overflow-x: hidden !important;
  overflow-y: auto !important;
  /* 确保始终显示滚动条 */
}

:deep(.el-table--border) {
  border: none;
}

:deep(.el-table::before),
:deep(.el-table::after) {
  display: none;
}

/* 优化表格在窄屏下的显示 */
@media (max-width: 1400px) {

  :deep(.el-table th),
  :deep(.el-table td) {
    padding: 8px 2px;
  }

  :deep(.el-table .cell) {
    padding-left: 5px;
    padding-right: 5px;
  }
}

/* 增大表格中的文字 */
:deep(.el-table .cell) {
  font-size: 14px;
  line-height: 23px;
  /* 增加行高 */
  padding: 2px 6px;
  /* 添加内边距增加可读性 */
}

:deep(.el-table th) {
  font-size: 14px;
  font-weight: bold;
  background-color: #f5f7fa;
}

/* 调整滚动条样式 */
:deep(.el-scrollbar__bar.is-vertical) {
  width: 8px;
}

:deep(.el-scrollbar__thumb) {
  background-color: rgba(144, 147, 153, 0.5);
}

/* 增大表格中的文字 */
:deep(.el-table .cell) {
  font-size: 14px;
  line-height: 24px;
  /* 增加行高 */
  padding: 4px 6px;
  /* 添加内边距增加可读性 */
}

/* 优化表格行的样式 */
:deep(.el-table tr) {
  height: 36px;
}

:deep(.el-table__row:hover) {
  background-color: #f5f7fa !important;
}

:deep(.el-table__row.current-row) {
  background-color: #ecf5ff !important;
}

/* 修复Chrome下的滚动条问题 */
:deep(.el-table__body-wrapper::-webkit-scrollbar) {
  width: 8px;
  height: 8px;
}

:deep(.el-table__body-wrapper::-webkit-scrollbar-thumb) {
  background: #c0c4cc;
  border-radius: 4px;
}

:deep(.el-table__body-wrapper::-webkit-scrollbar-track) {
  background: #f5f7fa;
}

/* 确保数字右对齐 */
:deep(.el-table .cell-number) {
  text-align: right;
}

.collapse-button {
  display: flex;
  flex-direction: row;
  gap: 10px;
  align-items: center;
  justify-content: center;
}

.title {
  color: #333;
  font-weight: bold;
  font-size: 12pt;
  margin-left: 5px;
  display: flex;
  gap: 5px;
  align-items: center;
  justify-content: center;
}

.channel-and-results-select {
  display: flex;
  flex-direction: row;
  gap: 6px;
  align-items: center;
  justify-content: center;
}

/* 添加组样式 */
:deep(.group-0) {
  background-color: rgba(240, 249, 235, 0.4);
}

:deep(.group-1) {
  background-color: rgba(230, 247, 255, 0.4);
}

:deep(.group-2) {
  background-color: rgba(253, 246, 236, 0.4);
}

:deep(.group-3) {
  background-color: rgba(245, 243, 254, 0.4);
}

/* 组分隔线 */
:deep(.el-table__row.group-0:first-child),
:deep(.el-table__row.group-1:first-child),
:deep(.el-table__row.group-2:first-child),
:deep(.el-table__row.group-3:first-child) {
  border-top: 2px dashed #dcdfe6;
}

/* 组标记样式 */
.group-marker {
  position: relative;
}

.group-tag {
  display: none;
}

.amplitude-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 0;
}

.group-value {
  font-weight: bold;
  font-size: 16px;
}

.group-label {
  margin-top: 4px;
  background-color: #409eff;
  color: white;
  border-radius: 4px;
  padding: 0 6px;
  font-size: 12px;
}

/* 修改分组样式 */
:deep(.el-table__row.group-0) {
  background-color: rgba(240, 249, 235, 0.6);
}

:deep(.el-table__row.group-1) {
  background-color: rgba(230, 247, 255, 0.6);
}

:deep(.el-table__row.group-2) {
  background-color: rgba(253, 246, 236, 0.6);
}

:deep(.el-table__row.group-3) {
  background-color: rgba(245, 243, 254, 0.6);
}

/* 删除之前的组标记和标签样式 */
.group-marker {
  position: relative;
}

.group-tag {
  display: none;
}

:deep(.el-input__wrapper) {
  padding: 2px 4px;
  margin-bottom: 0px !important;
}

:deep(.el-form-item__label) {
  padding: 0px 0px 0px 0px !important;
  margin-bottom: 0px !important;
}

:deep(.el-form-item) {
  margin-bottom: 4px !important;
}

:deep(.el-input__inner) {
  padding: 2px 4px;
  font-size: 13px;
}

:deep(.el-input-number) {
  width: 100%;
  margin-bottom: 4px !important;
}

:deep(.el-input-number .el-input__inner) {
  padding: 2px 4px;
  font-size: 13px;
}

:deep(.el-tabs__item) {
  min-width: 56px;
  width: 64px;
  text-align: center;
  font-size: 15px;
  line-height: 18px;
  padding: 4px 0 !important;
  word-break: keep-all;
  letter-spacing: 2px;
}
</style>
