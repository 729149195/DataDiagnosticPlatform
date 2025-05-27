<template>
  <div class="container" :class="{ 'panel-open': resultsDrawerVisible }">
    <!-- 顶部操作栏，保留并恢复为中文 -->
    <div class="header">
      <span class="title">手绘查询
        <el-tooltip placement="right" effect="light">
          <template #content>
            <div style="max-width: 430px">
              <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">视图说明</div>
              <div style="margin-bottom:8px;">在画布上绘制时序模式后，可在选中通道中查找相似模式。</div>
              <hr style="margin:8px 0;">
              <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
              <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                <li>通道选择：匹配前需要在顶部下拉框选择待查询的通道</li>
                <li>查询结果：通过右上角的展开/收起查询结果按钮显示</li>
                <li>绘制曲线的背景颜色：标注曲线斜率的正负性，是模式匹配的依据</li>
                <li>绘制面布（网格背景区域）
                  <ul style="margin:0 0 0 18px;padding:0;list-style:circle;">
                    <li>绘制操作：在画布上拖动鼠标即可绘制曲线</li>
                    <li>全屏绘图：点击画布右上角的圆形按钮可全屏绘制，绘制后需点击应用</li>
                    <li>查询操作：点击查询按钮，系统会在选中的通道数据中查找所绘模式</li>
                    <li>清除操作：点击清除按钮，可清除画布上的绘制</li>
                    <li>修改操作：拖拽曲线的锚点，可移动该点位置，从而修改曲线形状</li>
                  </ul>
                </li>
                <li>参数面板（右侧）
                  <ul style="margin:0 0 0 18px;padding:0;list-style:circle;">
                    <li>查找范围</li>
                    <ul style="margin:0 0 0 18px;padding:0;list-style:circle;">
                      <li>时间区间：限制模式查询的时间（X轴）范围</li>
                      <li>指标区间：限制模式查询的数值（Y轴）范围</li>
                    </ul>
                    <li>匹配方法
                      <ul style="margin:0 0 0 18px;padding:0;list-style:circle;">
                        <li>低通滤波幅度：通过平滑去除模式无关的扰动，数值越大，平滑程度越高，将无法识别小幅度模式；推荐将该参数设为目标模式的时间跨度</li>
                        <li>匹配数量上限：限制返回模式的数量，可缩短返回耗时</li>
                      </ul>
                    </li>
                    <li>目标模式
                      <ul style="margin:0 0 0 18px;padding:0;list-style:circle;">
                        <li>模式重复数：自动拼接多个绘制模式为查询目标</li>
                        <li>指标幅度：设置单个匹配结果的数值（Y轴）幅度</li>
                        <li>时间跨度：设置单个匹配结果的时间（X轴）跨度</li>
                      </ul>
                    </li>
                  </ul>
                </li>
              </ul>
            </div>
          </template>
          <el-icon style="color: #409EFF">
            <InfoFilled />
          </el-icon>
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
        <el-tooltip content="模板" placement="top" effect="light">
          <el-button type="primary" @click="openTemplateDialog" circle style="margin-left: 0px; border-radius: 10%;">
            <el-icon>
              <Collection />
            </el-icon>
          </el-button>
        </el-tooltip>
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
            <el-button type="success" @click="saveTemplate" class="save-template-button" style="margin-left: 8px;">
              保存模板
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
                    <el-input v-model="xFilterStart" placeholder="起点" size="small" style="width: 48%;" />
                    <span style="margin: 0 4px;">~</span>
                    <el-input v-model="xFilterEnd" placeholder="终点" size="small" style="width: 48%;" />
                  </div>
                </el-form-item>
                <el-form-item label="数值区间" label-position="top">
                  <div style="display: flex; align-items: center; width: 100%;">
                    <el-input v-model="yFilterStart" placeholder="起点" size="small" style="width: 48%;" />
                    <span style="margin: 0 4px;">~</span>
                    <el-input v-model="yFilterEnd" placeholder="终点" size="small" style="width: 48%;" />
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
                  <el-input v-model="lowpassAmplitude" size="small" style="width: 100%;" />
                </el-form-item>
                <el-form-item label="匹配数量上限">
                  <el-input v-model="maxMatchPerChannel" size="small" style="width: 100%;" />
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
                  <el-input v-model="patternRepeatCount" size="small" style="width: 100%;" />
                </el-form-item>
                <el-form-item label="指标幅度" label-position="top">
                  <el-input v-model="amplitudeLimit" placeholder="留空为不限制" size="small" style="width: 100%;" />
                </el-form-item>
                <el-form-item label="时间跨度" label-position="top">
                  <el-input v-model="timeSpanLimit" placeholder="留空为不限制" size="small" style="width: 100%;" />
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

    <!-- 保存模板对话框 -->
    <el-dialog v-model="saveTemplateDialogVisible" title="保存手绘曲线模板" width="500px" :close-on-click-modal="false">
      <el-form :model="templateForm" :rules="templateRules" ref="templateFormRef" label-width="80px">
        <el-form-item label="模板名称" prop="templateName">
          <el-input v-model="templateForm.templateName" placeholder="请输入模板名称" />
        </el-form-item>
        <el-form-item label="模板描述" prop="description">
          <el-input v-model="templateForm.description" type="textarea" :rows="3" placeholder="请输入模板描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="saveTemplateDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmSaveTemplate" :loading="saving">保存</el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 模板列表对话框 -->
    <el-dialog v-model="templateListDialogVisible" title="手绘曲线模板" width="70%" :close-on-click-modal="false">
      <div class="template-dialog-content">
        <el-table :data="templates" v-loading="loadingTemplates" style="width: 100%" max-height="500px">
          <el-table-column label="曲线预览" width="150" align="center">
            <template #default="scope">
              <div class="curve-preview">
                <canvas :ref="el => setCurveCanvasRef(el, scope.$index)" class="preview-canvas" width="120" height="60" @mouseover="drawCurvePreview(scope.row.raw_query_pattern, scope.$index)"></canvas>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="模板名称" prop="template_name" min-width="120" show-overflow-tooltip  align="center"/>
          <el-table-column label="模板描述" prop="description" min-width="150" show-overflow-tooltip  align="center"/>
          <el-table-column label="低通滤波" width="90" align="center">
            <template #default="scope">
              {{ scope.row.parameters?.lowpassAmplitude || 'N/A' }}
            </template>
          </el-table-column>
          <el-table-column label="时间区间" width="120" align="center">
            <template #default="scope">
              <span v-if="scope.row.parameters?.xFilterRange && scope.row.parameters.xFilterRange[0] !== null">
                {{ scope.row.parameters.xFilterRange[0] }}~{{ scope.row.parameters.xFilterRange[1] }}
              </span>
              <span v-else>不限制</span>
            </template>
          </el-table-column>
          <el-table-column label="数值区间" width="120" align="center">
            <template #default="scope">
              <span v-if="scope.row.parameters?.yFilterRange && scope.row.parameters.yFilterRange[0] !== null">
                {{ scope.row.parameters.yFilterRange[0] }}~{{ scope.row.parameters.yFilterRange[1] }}
              </span>
              <span v-else>不限制</span>
            </template>
          </el-table-column>
          <el-table-column label="重复数" width="80" align="center">
            <template #default="scope">
              {{ scope.row.parameters?.patternRepeatCount || 0 }}
            </template>
          </el-table-column>
          <el-table-column label="匹配上限" width="90" align="center">
            <template #default="scope">
              {{ scope.row.parameters?.maxMatchPerChannel || 'N/A' }}
            </template>
          </el-table-column>
          <el-table-column label="指标幅度" width="100" align="center">
            <template #default="scope">
              <span v-if="scope.row.parameters?.amplitudeLimit !== null && scope.row.parameters?.amplitudeLimit !== undefined">
                {{ scope.row.parameters.amplitudeLimit }}
              </span>
              <span v-else>不限制</span>
            </template>
          </el-table-column>
          <el-table-column label="时间跨度" width="100" align="center">
            <template #default="scope">
              <span v-if="scope.row.parameters?.timeSpanLimit !== null && scope.row.parameters?.timeSpanLimit !== undefined">
                {{ scope.row.parameters.timeSpanLimit }}
              </span>
              <span v-else>不限制</span>
            </template>
          </el-table-column>
          <!-- <el-table-column label="创建时间" width="120" align="center">
            <template #default="scope">
              {{ formatDate(scope.row.created_time) }}
            </template>
          </el-table-column> -->
          <el-table-column label="操作" width="150" align="center" fixed="right">
            <template #default="scope">
              <el-button type="primary" size="small" @click="applyTemplate(scope.row)">
                应用
              </el-button>
              <el-button type="danger" size="small" @click="deleteTemplate(scope.row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="templateListDialogVisible = false">关闭</el-button>
          <el-button type="primary" @click="loadTemplates">刷新</el-button>
        </span>
      </template>
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
        <el-table ref="resultsTable" :data="sortedGroupedMatchedResults" v-model:selection="selectedMatchedResults" @selection-change="handleTableSelectionChange" height="calc(100vh - 83px)" size="default" border :span-method="objectSpanMethod" @sort-change="handleSortChange">
          <el-table-column type="selection" width="40" align="center" />
          <el-table-column label="区间幅度s" min-width="110" align="center" sortable="custom" prop="groupAmplitude">
            <template #default="scope">
              <div class="amplitude-cell" @click="handleAmplitudeCellClick(scope.row)" :class="{ 'clickable': true }" :title="getAmplitudeCellTooltip(scope.row.groupIndex)">
                <span class="group-value">≈{{ scope.row.groupAmplitude?.toFixed(6) }}</span>
                <div class="click-hint">点击批量选择</div>
                <div class="group-selection-indicator" v-if="getGroupSelectionStatus(scope.row.groupIndex).hasSelection">
                  <el-icon v-if="getGroupSelectionStatus(scope.row.groupIndex).isFullySelected" class="selection-icon fully-selected">
                    <Check />
                  </el-icon>
                  <el-icon v-else class="selection-icon partially-selected">
                    <Minus />
                  </el-icon>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="通道名" min-width="90" align="center" show-overflow-tooltip prop="channelName" />
          <el-table-column label="炮号" min-width="60" align="center" prop="shotNumber" />
          <!-- <el-table-column label="平滑" min-width="60" align="center" prop="smoothLevel" /> -->
          <el-table-column label="匹配度" min-width="70" align="center" sortable="custom" prop="confidence">
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
import { Search, FullScreen, List, ArrowLeft, Check, Minus } from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { useStore } from 'vuex';
import Paper from 'paper';
import { Collection } from '@element-plus/icons-vue';

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

    // 确保画布获得焦点，使键盘事件能够正常工作
    if (paperCanvas.value) {
      paperCanvas.value.focus();
    }

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
// 修复：防止在操作区参数输入框中删除内容时意外清空绘制曲线
const handleKeyDown = (e) => {
  // 检查事件目标是否为输入框或可编辑元素
  const target = e.target;
  const isInputElement = target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.contentEditable === 'true' ||
    target.closest('.el-input') ||
    target.closest('.el-form-item');

  // 只有在非输入元素上且按下Delete或Backspace键时才清除画布
  // 这样可以避免用户在参数输入框中删除文字时意外清空画布内容
  if (!isInputElement && (e.key === 'Delete' || e.key === 'Backspace')) {
    e.preventDefault(); // 防止默认行为
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

// 模板相关变量
const saveTemplateDialogVisible = ref(false);
const templateListDialogVisible = ref(false);
const templates = ref([]);
const loadingTemplates = ref(false);
const saving = ref(false);
const templateForm = ref({
  templateName: '',
  description: ''
});
const templateFormRef = ref(null);
const curveCanvasRefs = ref({});

// 模板表单验证规则
const templateRules = {
  templateName: [
    { required: true, message: '请输入模板名称', trigger: 'blur' },
    { min: 1, max: 50, message: '长度在 1 到 50 个字符', trigger: 'blur' }
  ]
};

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

// 模板相关方法
// 保存模板
const saveTemplate = () => {
  // 检查是否有绘制的曲线
  if (!path || !path.segments || path.segments.length < 2) {
    ElMessage.warning('请先绘制曲线');
    return;
  }

  // 重置表单
  templateForm.value = {
    templateName: '',
    description: ''
  };

  saveTemplateDialogVisible.value = true;
};

// 确认保存模板
const confirmSaveTemplate = async () => {
  if (!templateFormRef.value) return;

  // 验证表单
  const valid = await templateFormRef.value.validate().catch(() => false);
  if (!valid) return;

  saving.value = true;

  try {
    // 获取当前的曲线数据
    const rawQueryPattern = path ? path.segments.map(segment => ({
      x: segment.point.x,
      y: paperCanvas.value.offsetHeight - segment.point.y,  // 翻转Y轴
      handleIn: segment.handleIn ? {
        x: segment.handleIn.x,
        y: -segment.handleIn.y  // 翻转控制点的Y坐标
      } : null,
      handleOut: segment.handleOut ? {
        x: segment.handleOut.x,
        y: -segment.handleOut.y  // 翻转控制点的Y坐标
      } : null
    })) : [];

    // 获取当前的参数设置
    const parameters = {
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
    };

    // 发送保存请求
    const response = await fetch('https://10.1.108.231:5000/api/sketch-templates/save', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        template_name: templateForm.value.templateName,
        raw_query_pattern: rawQueryPattern,
        parameters: parameters,
        description: templateForm.value.description
      })
    });

    const data = await response.json();

    if (response.ok) {
      ElMessage.success(data.message || '模板保存成功');
      saveTemplateDialogVisible.value = false;
    } else {
      throw new Error(data.error || '保存失败');
    }
  } catch (error) {
    ElMessage.error(error.message || '保存模板失败');
    console.error('保存模板错误:', error);
  } finally {
    saving.value = false;
  }
};

// 打开模板列表对话框
const openTemplateDialog = () => {
  templateListDialogVisible.value = true;
  loadTemplates().then(() => {
    setTimeout(() => {
      drawAllCurvePreviews();
    }, 100);
  });
};

// 加载模板列表
const loadTemplates = async () => {
  loadingTemplates.value = true;
  try {
    const response = await fetch('https://10.1.108.231:5000/api/sketch-templates/list');
    const data = await response.json();
    if (response.ok) {
      templates.value = data.templates || [];
      setTimeout(() => {
        drawAllCurvePreviews();
      }, 100);
    } else {
      throw new Error(data.error || '获取模板列表失败');
    }
  } catch (error) {
    ElMessage.error(error.message || '获取模板列表失败');
    console.error('获取模板列表错误:', error);
  } finally {
    loadingTemplates.value = false;
  }
};

// 应用模板
const applyTemplate = (template) => {
  try {
    // 清除当前画布
    clearCanvas();

    // 恢复参数设置
    const params = template.parameters || {};
    lowpassAmplitude.value = params.lowpassAmplitude || 0.03;
    xFilterStart.value = params.xFilterRange && params.xFilterRange[0] !== null ? params.xFilterRange[0] : '';
    xFilterEnd.value = params.xFilterRange && params.xFilterRange[1] !== null ? params.xFilterRange[1] : '';
    yFilterStart.value = params.yFilterRange && params.yFilterRange[0] !== null ? params.yFilterRange[0] : '';
    yFilterEnd.value = params.yFilterRange && params.yFilterRange[1] !== null ? params.yFilterRange[1] : '';
    patternRepeatCount.value = params.patternRepeatCount || 0;
    maxMatchPerChannel.value = params.maxMatchPerChannel || 100;
    amplitudeLimit.value = params.amplitudeLimit !== null ? params.amplitudeLimit : '';
    timeSpanLimit.value = params.timeSpanLimit !== null ? params.timeSpanLimit : '';

    // 恢复手绘曲线
    if (template.raw_query_pattern && template.raw_query_pattern.length > 0 && paperScope) {
      const canvasHeight = paperCanvas.value.offsetHeight;

      // 创建新路径
      path = new Paper.Path();
      path.strokeColor = 'black';
      path.strokeWidth = 2;
      path.strokeCap = 'round';
      path.strokeJoin = 'round';

      // 恢复路径点和控制点
      template.raw_query_pattern.forEach((segmentData) => {
        const point = new Paper.Point(segmentData.x, canvasHeight - segmentData.y); // 翻转Y轴
        const handleIn = segmentData.handleIn
          ? new Paper.Point(segmentData.handleIn.x, -segmentData.handleIn.y)
          : null;
        const handleOut = segmentData.handleOut
          ? new Paper.Point(segmentData.handleOut.x, -segmentData.handleOut.y)
          : null;
        path.add(new Paper.Segment(point, handleIn, handleOut));
      });

      // 选中所有锚点
      path.fullySelected = true;

      // 更新段点信息显示
      segmentInfo.value = `点数: ${path.segments.length}`;

      // 恢复高亮区间
      updateHighlightBackground();

      // 重绘Paper.js视图
      paperScope.view.draw();
    }

    templateListDialogVisible.value = false;
    ElMessage.success(`模板 "${template.template_name}" 应用成功`);
  } catch (error) {
    ElMessage.error('应用模板失败');
    console.error('应用模板错误:', error);
  }
};

// 删除模板
const deleteTemplate = async (template) => {
  const confirmResult = await ElMessageBox.confirm(
    `确定要删除模板 "${template.template_name}" 吗？`,
    '确认删除',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).catch(() => false);

  if (!confirmResult) return;

  try {
    const response = await fetch('https://10.1.108.231:5000/api/sketch-templates/delete', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        template_name: template.template_name
      })
    });

    const data = await response.json();

    if (response.ok) {
      ElMessage.success(data.message || '模板删除成功');
      // 重新加载模板列表
      loadTemplates();
    } else {
      throw new Error(data.error || '删除失败');
    }
  } catch (error) {
    ElMessage.error(error.message || '删除模板失败');
    console.error('删除模板错误:', error);
  }
};

// 设置曲线画布引用
const setCurveCanvasRef = (el, index) => {
  if (el) {
    curveCanvasRefs.value[index] = el;
    // 立即绘制
    if (templates.value[index]) {
      drawCurvePreview(templates.value[index].raw_query_pattern, index);
    }
  }
};

// 批量绘制所有曲线预览
const drawAllCurvePreviews = () => {
  templates.value.forEach((tpl, idx) => {
    drawCurvePreview(tpl.raw_query_pattern, idx);
  });
};

// 绘制曲线预览
const drawCurvePreview = (rawQueryPattern, index) => {
  const canvas = curveCanvasRefs.value[index];
  if (!canvas || !rawQueryPattern || rawQueryPattern.length === 0) return;

  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;

  // 清除画布
  ctx.clearRect(0, 0, width, height);

  // 绘制背景
  ctx.fillStyle = '#f9f9f9';
  ctx.fillRect(0, 0, width, height);

  // 绘制边框
  ctx.strokeStyle = '#ddd';
  ctx.lineWidth = 1;
  ctx.strokeRect(0, 0, width, height);

  if (rawQueryPattern.length < 2) return;

  // 找到数据的边界
  const xs = rawQueryPattern.map(p => p.x);
  const ys = rawQueryPattern.map(p => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);

  const xRange = maxX - minX || 1;
  const yRange = maxY - minY || 1;

  // 添加边距
  const margin = 8;
  const drawWidth = width - 2 * margin;
  const drawHeight = height - 2 * margin;

  // 绘制曲线
  ctx.strokeStyle = '#007bff';
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.beginPath();

  rawQueryPattern.forEach((point, index) => {
    const x = margin + ((point.x - minX) / xRange) * drawWidth;
    const y = margin + ((maxY - point.y) / yRange) * drawHeight; // 翻转Y轴

    if (index === 0) {
      ctx.moveTo(x, y);
    } else {
      ctx.lineTo(x, y);
    }
  });

  ctx.stroke();

  // 绘制端点
  ctx.fillStyle = '#007bff';
  rawQueryPattern.forEach((point, index) => {
    if (index === 0 || index === rawQueryPattern.length - 1) {
      const x = margin + ((point.x - minX) / xRange) * drawWidth;
      const y = margin + ((maxY - point.y) / yRange) * drawHeight;
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, 2 * Math.PI);
      ctx.fill();
    }
  });
};

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return 'N/A';
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit'
    });
  } catch {
    return 'N/A';
  }
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

  // 监听键盘事件 - 绑定到画布容器而非全局
  if (paperCanvas.value) {
    paperCanvas.value.addEventListener('keydown', handleKeyDown);
    // 确保画布容器可以获得焦点
    paperCanvas.value.tabIndex = 0;
  }

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

  // 移除画布键盘事件监听器
  if (paperCanvas.value) {
    paperCanvas.value.removeEventListener('keydown', handleKeyDown);
  }
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
// 表格引用
const resultsTable = ref(null);
// 排序状态
const sortConfig = ref({
  prop: 'confidence',
  order: 'descending'
});
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

// 排序后的分组结果
const sortedGroupedMatchedResults = computed(() => {
  if (groupedMatchedResults.value.length === 0) return [];

  // 如果没有排序配置，直接返回分组结果
  if (!sortConfig.value.prop || !sortConfig.value.order) {
    return groupedMatchedResults.value;
  }

  // 按组分类
  const groupMap = new Map();
  groupedMatchedResults.value.forEach(item => {
    if (!groupMap.has(item.groupIndex)) {
      groupMap.set(item.groupIndex, []);
    }
    groupMap.get(item.groupIndex).push(item);
  });

  // 对每个组内的数据进行排序
  const sortedGroups = [];
  for (const [groupIndex, groupItems] of groupMap) {
    const sortedGroupItems = [...groupItems].sort((a, b) => {
      let aValue = a[sortConfig.value.prop];
      let bValue = b[sortConfig.value.prop];

      // 处理数值类型
      if (typeof aValue === 'number' && typeof bValue === 'number') {
        if (sortConfig.value.order === 'ascending') {
          return aValue - bValue;
        } else {
          return bValue - aValue;
        }
      }

      // 处理字符串类型
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        if (sortConfig.value.order === 'ascending') {
          return aValue.localeCompare(bValue);
        } else {
          return bValue.localeCompare(aValue);
        }
      }

      return 0;
    });

    sortedGroups.push({ groupIndex, items: sortedGroupItems });
  }

  // 根据排序字段对组进行排序（使用组内第一个元素的值）
  if (sortConfig.value.prop === 'groupAmplitude') {
    sortedGroups.sort((a, b) => {
      const aValue = a.items[0].groupAmplitude;
      const bValue = b.items[0].groupAmplitude;
      if (sortConfig.value.order === 'ascending') {
        return aValue - bValue;
      } else {
        return bValue - aValue;
      }
    });
  }

  // 展平结果
  return sortedGroups.flatMap(group => group.items);
});

// 获取所有匹配结果id，使用原始索引
const allMatchedIds = computed(() => sortedGroupedMatchedResults.value.map(item =>
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
    selectedMatchedResults.value = [...sortedGroupedMatchedResults.value];
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
  allMatchedSelected.value = selection.length === sortedGroupedMatchedResults.value.length && selection.length > 0;
};

// 监听selectedMatchedResults变化，更新全选状态
watch(selectedMatchedResults, (newVal) => {
  allMatchedSelected.value = newVal.length === sortedGroupedMatchedResults.value.length && newVal.length > 0;
});

// 监听匹配结果，有新结果时自动展开抽屉
watch(sortedMatchedResults, (newVal) => {
  if (newVal.length > 0) {
    resultsDrawerVisible.value = true;
    // 关键：直接赋值为所有行对象，实现el-table自动全选
    selectedMatchedResults.value = [...sortedGroupedMatchedResults.value];
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
      for (let i = rowIndex + 1; i < sortedGroupedMatchedResults.value.length; i++) {
        if (sortedGroupedMatchedResults.value[i].groupIndex === row.groupIndex) {
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
  const currentRow = sortedGroupedMatchedResults.value[index];
  const prevRow = sortedGroupedMatchedResults.value[index - 1];
  return currentRow.groupIndex !== prevRow.groupIndex;
};

// 处理表格排序变化
const handleSortChange = ({ prop, order }) => {
  sortConfig.value = {
    prop: prop,
    order: order
  };
};

// 获取组的选择状态
const getGroupSelectionStatus = (groupIndex) => {
  const groupItems = sortedGroupedMatchedResults.value.filter(item => item.groupIndex === groupIndex);
  const selectedItems = selectedMatchedResults.value.filter(item => item.groupIndex === groupIndex);

  return {
    hasSelection: selectedItems.length > 0,
    isFullySelected: selectedItems.length === groupItems.length && groupItems.length > 0,
    isPartiallySelected: selectedItems.length > 0 && selectedItems.length < groupItems.length
  };
};

// 获取区间幅度单元格的提示文本
const getAmplitudeCellTooltip = (groupIndex) => {
  const groupItems = sortedGroupedMatchedResults.value.filter(item => item.groupIndex === groupIndex);
  const groupSelectionStatus = getGroupSelectionStatus(groupIndex);

  if (groupSelectionStatus.isFullySelected) {
    return `点击取消选择该区间幅度组的所有 ${groupItems.length} 项`;
  } else if (groupSelectionStatus.isPartiallySelected) {
    const selectedCount = selectedMatchedResults.value.filter(item => item.groupIndex === groupIndex).length;
    return `点击选择该区间幅度组的所有 ${groupItems.length} 项（当前已选 ${selectedCount} 项）`;
  } else {
    return `点击选择该区间幅度组的所有 ${groupItems.length} 项`;
  }
};

// 处理区间幅度单元格点击
const handleAmplitudeCellClick = (clickedRow) => {
  const groupIndex = clickedRow.groupIndex;
  const groupItems = sortedGroupedMatchedResults.value.filter(item => item.groupIndex === groupIndex);
  const groupSelectionStatus = getGroupSelectionStatus(groupIndex);

  // 获取表格引用
  const tableRef = resultsTable.value;

  // 如果组内全部选中，则取消全部选择；否则选中全部
  if (groupSelectionStatus.isFullySelected) {
    // 取消选中该组的所有项
    groupItems.forEach(item => {
      if (tableRef) {
        tableRef.toggleRowSelection(item, false);
      }
    });
  } else {
    // 选中该组的所有项
    groupItems.forEach(item => {
      if (tableRef) {
        tableRef.toggleRowSelection(item, true);
      }
    });
  }
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
  border: 1px solid #e1e8ed;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-right: 8px;
}

.operation-panel {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  background: transparent;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
  position: relative;
  overflow: hidden;
}

.operation-panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #409eff 0%, #337ecc 50%, #409eff 100%);
  opacity: 0.9;
}

.params-area {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  padding-top: 4px;
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
  outline: none;
  /* 移除默认的焦点轮廓 */
}

.whiteboard-canvas:focus {
  /* 添加一个微妙的焦点指示，但不影响用户体验 */
  box-shadow: inset 0 0 0 1px rgba(64, 158, 255, 0.3);
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

/* 确保区间幅度列的单元格完全可点击 */
:deep(.el-table td:nth-child(2)) {
  padding: 0 !important;
  vertical-align: middle;
}

:deep(.el-table td:nth-child(2) .cell) {
  padding: 0 !important;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
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

/* 模板相关样式 */
.template-dialog-content {
  max-height: 500px;
  overflow-y: auto;
}

.curve-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 5px;
}

.preview-canvas {
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #fafafa;
  cursor: pointer;
}

.preview-canvas:hover {
  border-color: #409EFF;
  box-shadow: 0 0 4px rgba(64, 158, 255, 0.3);
}

.save-template-button {
  background-color: #67c23a;
  border-color: #67c23a;
}

.save-template-button:hover {
  background-color: #5daf34;
  border-color: #5daf34;
}

.amplitude-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px;
  position: relative;
  transition: all 0.2s ease;
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  min-height: 50px;
  justify-content: center;
}

.amplitude-cell.clickable {
  cursor: pointer;
  border-radius: 4px;
  user-select: none;
  border: 1px solid transparent;
  margin: -1px;
  /* 补偿边框占用的空间 */
}

.amplitude-cell.clickable:hover {
  background-color: rgba(64, 158, 255, 0.15);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.25);
  border: 1px solid rgba(64, 158, 255, 0.3);
}

.amplitude-cell.clickable:active {
  transform: translateY(0);
  box-shadow: 0 1px 4px rgba(64, 158, 255, 0.4);
  background-color: rgba(64, 158, 255, 0.2);
}

.group-value {
  font-weight: bold;
  font-size: 16px;
  pointer-events: none;
  /* 确保点击事件传递到父元素 */
}

.click-hint {
  font-size: 10px;
  color: #999;
  margin-top: 2px;
  opacity: 0;
  transition: opacity 0.2s ease;
  pointer-events: none;
  /* 确保点击事件传递到父元素 */
}

.amplitude-cell.clickable:hover .click-hint {
  opacity: 1;
}

.group-selection-indicator {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background-color: rgba(255, 255, 255, 0.9);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
  pointer-events: none;
  /* 确保点击事件传递到父元素 */
}

.selection-icon {
  font-size: 12px;
  pointer-events: none;
  /* 确保点击事件传递到父元素 */
}

.selection-icon.fully-selected {
  color: #67c23a;
}

.selection-icon.partially-selected {
  color: #e6a23c;
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

/* 表单样式优化 */
:deep(.el-form) {
  padding: 0 4px;
}

:deep(.el-form-item__label) {
  padding: 0px 0px 4px 0px !important;
  margin-bottom: 0px !important;
  font-weight: 600;
  color: #303133;
  font-size: 13px;
  line-height: 1.4;
}

:deep(.el-form-item) {
  margin-bottom: 8px !important;
}

:deep(.el-input__wrapper) {
  padding: 4px 6px;
  margin-bottom: 0px !important;
  border-radius: 4px;
  border: 1px solid #d9ecff;
  background: transparent;
  transition: all 0.3s ease;
  box-shadow: none;
}

:deep(.el-input__wrapper:hover) {
  border-color: #b3d8ff;
  box-shadow: none;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.2);
}

:deep(.el-input__inner) {
  padding: 0;
  font-size: 13px;
  color: #303133;
  background: transparent;
  border: none;
}

:deep(.el-input__inner::placeholder) {
  color: #a8abb2;
  font-size: 12px;
}

:deep(.el-input-number) {
  width: 100%;
  margin-bottom: 4px !important;
}

:deep(.el-input-number .el-input__wrapper) {
  padding: 6px 8px;
}

/* 标签页样式优化 */
:deep(.el-tabs__header) {
  margin: 0 0 8px 0;
  background: transparent;
  border-radius: 6px;
  padding: 1px;
  box-shadow: none;
}

:deep(.el-tabs__nav-wrap) {
  padding: 0;
  overflow: visible !important;
}

:deep(.el-tabs__nav-scroll) {
  overflow: visible !important;
}

:deep(.el-tabs__nav) {
  border: none;
  background: transparent;
  display: flex !important;
  width: 100% !important;
  justify-content: space-between;
}

:deep(.el-tabs__item) {
  min-width: 45px;
  max-width: calc(33.333% - 1px);
  flex: 1 1 calc(33.333% - 1px);
  text-align: center;
  font-size: 13px;
  line-height: 15px;
  padding: 6px 2px !important;
  word-break: keep-all;
  letter-spacing: 0;
  border: none;
  border-radius: 3px;
  margin: 0 0.5px;
  transition: all 0.3s ease;
  color: #606266;
  font-weight: 500;
  background: transparent;
  white-space: nowrap;
  overflow: visible;
}

:deep(.el-tabs__item:hover) {
  background: rgba(64, 158, 255, 0.1);
  color: #409eff;
  transform: translateY(-1px);
}

:deep(.el-tabs__item.is-active) {
  background: linear-gradient(135deg, #409eff 0%, #337ecc 100%);
  color: white;
  font-weight: 600;
  box-shadow: 0 2px 6px rgba(64, 158, 255, 0.4);
  transform: translateY(-1px);
}

:deep(.el-tabs__active-bar) {
  display: none;
}

/* 标签页内容区域样式 */
:deep(.el-tab-pane) {
  padding: 6px 3px;
  background: transparent;
  border-radius: 6px;
  margin-top: -2px;
  min-height: 180px;
  backdrop-filter: none;
  border: none;
}

/* 特殊标签样式 */
:deep(.el-form-item__label) {
  position: relative;
}

:deep(.el-form-item__label::before) {
  content: '';
  position: absolute;
  left: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 12px;
  background: linear-gradient(135deg, #409eff, #337ecc);
  border-radius: 2px;
  opacity: 0.7;
  transition: all 0.3s ease;
}

:deep(.el-form-item:hover .el-form-item__label::before) {
  opacity: 1;
  width: 4px;
  height: 14px;
}

/* 整体动画效果 */
.operation-panel {
  transition: all 0.3s ease;
}

.operation-panel:hover {
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.1);
  transform: none;
}

/* 响应式优化 */
@media (max-width: 1200px) {
  :deep(.el-form-item) {
    margin-bottom: 6px !important;
  }

  :deep(.el-tab-pane) {
    min-height: 160px;
    padding: 4px 2px;
  }

  :deep(.el-tabs__item) {
    font-size: 12px !important;
    line-height: 14px !important;
    padding: 5px 1px !important;
    min-width: 42px;
  }
}
</style>
