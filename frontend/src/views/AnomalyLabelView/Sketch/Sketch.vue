<template>
  <div class="container">
    <!-- 顶部操作栏 -->
    <div class="header">
      <span class="title">查询</span>
      <span class="operate">
        <el-select 
          v-model="selectedGunNumbers" 
          placeholder="请选择需要匹配的通道" 
          multiple 
          collapse-tags 
          clearable
          collapse-tags-tooltip 
          class="select-gun-numbers"
        >
          <!-- 添加全部全选选项 -->
          <el-option
            key="select-all"
            value="select-all"
            label="全选所有通道"
          >
            <el-checkbox
              v-model="allSelected"
              @change="handleSelectAll"
            >
              全选所有通道
            </el-checkbox>
          </el-option>

          <!-- 添加分组全选选项 -->
          <el-option
            v-for="group in selectV2Options"
            :key="'select-all-' + group.value"
            :value="'select-all-' + group.value"
            :label="'全选' + group.label"
          >
            <el-checkbox
              v-model="groupSelectAll[group.value]"
              @change="(val) => handleSelectAllGroup(val, group)"
            >
              全选{{ group.label }}
            </el-checkbox>
          </el-option>
          
          <!-- 原有的分组选项 -->
          <el-option-group 
            v-for="group in selectV2Options" 
            :key="group.value" 
            :label="group.label"
          >
            <el-option
              v-for="option in group.children"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-option-group>
        </el-select>

        <!-- 模板选择 -->
        <el-select 
          v-model="selectedTemplate" 
          placeholder="模板" 
          class="select-template" 
          @change="loadTemplate"
          :value-key="'name'"
        >
          <el-option
            v-for="template in templates"
            :key="template.name"
            :label="template.name"
            :value="template"
          >
            <div class="template-preview">
              <canvas
                :ref="el => { if (el) previewTemplate(template, el) }"
                width="120"
                height="60"
              ></canvas>
            </div>
          </el-option>
        </el-select>
      </span>
    </div>

    <!-- 绘图区域 -->
    <div class="sketch-container">
      <div class="canvas-container">
        <canvas 
          ref="canvas"
          @touchstart.passive="onCanvasTouch"
          @touchmove.passive="onCanvasTouch"
          @touchend.passive="onCanvasTouch"
          @touchcancel.passive="onCanvasTouch"
        ></canvas>
        <div class="buttons">
          <el-button type="danger" class="clear-button" @click="clearCanvas">
            清除
          </el-button>
          <el-button type="success" :icon="Search" @click="submitData" class="search-button">
            查询
          </el-button>
          <!-- <el-button type="success" :icon="Search" @click="exportCurrentCurve" class="search-button">
            导出当前曲线数据
          </el-button> -->
        </div>
      </div>
      <div class="controls-wrapper">
        <div class="inputs-container">
          <div class="input-row">
            <div class="input-group">
              <span class="input-label">开始:</span>
              <el-input-number v-model="time_begin" :precision="4" :step="0.01" size="small" class="time-input" />
            </div>
            <div class="input-group">
              <span class="input-label">持续:</span>
              <el-input-number v-model="time_during" :precision="4" :step="0.01" size="small" class="time-input" />
            </div>
            <div class="input-group">
              <span class="input-label">结束:</span>
              <el-input-number v-model="time_end" :precision="4" :step="0.01" size="small" class="time-input" />
            </div>
          </div>

          <div class="input-row">
            <div class="input-group">
              <span class="input-label">上界:</span>
              <el-input-number v-model="upper_bound" :precision="4" :step="0.01" size="small" class="bound-input" />
            </div>
            <div class="input-group">
              <span class="input-label">幅度:</span>
              <el-input-number v-model="scope_bound" :precision="4" :step="0.01" size="small" class="bound-input" />
            </div>
            <div class="input-group">
              <span class="input-label">下界:</span>
              <el-input-number v-model="lower_bound" :precision="4" :step="0.01" size="small" class="bound-input" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  ref,
  computed,
  onMounted,
  onBeforeUnmount,
  watch,
} from 'vue';
import { Search } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useStore } from 'vuex';
import paper from 'paper';
import curveTemplates from '@/assets/templates/curveTemplates.json'
import chartWorkerManager from '@/workers/chartWorkerManager';

// 使用 Vuex store
const store = useStore();

// 绑定的值
const templatavalue = ref('');
const historyvalue = ref('');

// 选中的炮号数组
const selectedGunNumbers = ref([]);
const smoothness = computed(() => store.state.smoothness);
const sampling = computed(() => store.state.sampling);

// 从 Vuex 获取 selectedChannels
const selectedChannels = computed(() => store.state.selectedChannels);

// 历史选项
const historys = [
  { value: 'Option1', label: '历史1' },
  { value: 'Option2', label: '历史2' },
];

// 模板选项
const selectedTemplate = ref(null);
const templates = ref(curveTemplates.templates || []);

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

// 其他绑定的值
const brush_begin = computed(() => store.state.brush_begin);
const brush_end = computed(() => store.state.brush_end);
const time_begin = computed({
  get: () => store.state.time_begin,
  set: (value) => {
    store.dispatch('updateTimeBegin', value);
    // 移除不必要的重新渲染
  }
});
const time_during = computed({
  get: () => store.state.time_during,
  set: (value) => {
    store.dispatch('updateTimeDuring', value);
    // 移除不必要的重新渲染
  }
});
const time_end = computed({
  get: () => store.state.time_end,
  set: (value) => {
    store.dispatch('updateTimeEnd', value);
    // 移除不必要的重新渲染
  }
});
const upper_bound = computed({
  get: () => store.state.upper_bound,
  set: (value) => {
    store.dispatch('updateUpperBound', value);
    // 移除不必要的重新渲染
  }
});
const scope_bound = computed({
  get: () => store.state.scope_bound,
  set: (value) => {
    store.dispatch('updateScopeBound', value);
    // 移除不必要的重新渲染
  }
});
const lower_bound = computed({
  get: () => store.state.lower_bound,
  set: (value) => {
    store.dispatch('updateLowerBound', value);
    // 移除不必要的重新渲染
  }
});

// ----------- 画绘图逻辑开始 -----------

class DrawingApp {
  constructor(canvasElement) {
    // Note: 已知问题 - paper.js 会触发 passive event listener 警告
    // 这是由于 paper.js 内部实现导致的，不影响功能使用
    this.canvas = canvasElement;
    // 确保先清理之前的项目工具
    if (paper.project) {
      paper.project.remove();
    }
    if (paper.tools) {
      paper.tools.forEach(tool => tool.remove());
    }

    // 设置 paper.js 的全局配置
    paper.settings.handleSize = 8;
    paper.settings.hitTolerance = 8;

    // 重新初始化 paper
    paper.setup(this.canvas);
    this.project = paper.project;

    // 设置视图配置
    paper.view.settings = {
      ...paper.view.settings,
      handleSize: 8,
      hitTolerance: 8
    };

    this.size = { width: paper.view.size.width, height: paper.view.size.height };
    this.hitOptions = {
      segments: true,
      stroke: true,
      handles: true,
      tolerance: 5,
      guides: false,
    };
    this.path = null;
    this.isDrawing = false;
    this.segment = null;
    this.handle = null;

    this.gridGroup = new paper.Group();

    // 移除触摸事件相关的绑定
    this.onMouseDown = this.onMouseDown.bind(this);
    this.onMouseDrag = this.onMouseDrag.bind(this);
    this.onMouseUp = this.onMouseUp.bind(this);

    this.setupTool();
    this.drawGrid();

    window.addEventListener('resize', this.resizeCanvas.bind(this));

    // 添加一个标志来追踪是否已经初始化
    this.isInitialized = false;
  }

  setupTool() {
    if (this.tool) {
      this.tool.remove();
    }
    this.tool = new paper.Tool();
    this.tool.activate();
    
    // 只处理鼠标事件
    this.tool.onMouseDown = this.onMouseDown;
    this.tool.onMouseDrag = this.onMouseDrag;
    this.tool.onMouseUp = this.onMouseUp;
  }

  onMouseDown(event) {
    this.segment = null;
    this.handle = null;

    let hitResult = this.project.hitTest(event.point, this.hitOptions);

    if (hitResult && hitResult.item) {
      // 用户点击了一个目
      let clickedPath = hitResult.item;
      if (!(clickedPath instanceof paper.Path)) {
        // 果点击不是 Path，而是其子项
        clickedPath = clickedPath.parent;
      }

      if (clickedPath === this.path) {
        // 进入编辑模式
        this.path.fullySelected = true;

        if (hitResult.type === 'segment') {
          if (event.modifiers.alt) {
            // 删除点
            hitResult.segment.remove();
            paper.view.update();
          } else {
            // 移动点
            this.segment = hitResult.segment;
          }
        } else if (hitResult.type === 'handle-in' || hitResult.type === 'handle-out') {
          // 移动控制柄
          this.segment = hitResult.segment;
          this.handle = hitResult.type === 'handle-in' ? 'handleIn' : 'handleOut';
        } else if (hitResult.type === 'stroke' && event.modifiers.shift) {
          // 添加点
          const location = hitResult.location;
          let newSegment = this.path.insert(location.index + 1, event.point);
          this.segment = newSegment;
        }
      } else {
        // 点击了其他项目，但只允许一个路径存在
        console.log('Clicked on another item, but only one path is allowed.');
      }
    } else {
      // 点击了空白区域
      if (!this.path) {
        // 开始新的绘制
        this.isDrawing = true;
        this.path = new paper.Path();
        this.path.strokeColor = 'black';
        this.path.strokeWidth = 6;
        this.path.strokeCap = 'round';
        this.path.strokeJoin = 'round';
        this.path.fullySelected = false;

        // 添加第个点
        this.previousPoint = event.point.clone();
        this.path.add(this.previousPoint);
      } else {
        console.log('Path already exists, cannot start a new one.');
      }
    }
  }

  onMouseDrag(event) {
    if (this.isDrawing) {
      const newPoint = event.point.clone();

      // x 轴递增约束
      if (newPoint.x >= this.previousPoint.x) {
        this.path.add(newPoint);
        this.previousPoint = newPoint.clone();
        paper.view.update();
      }
    } else if (this.segment) {
      if (this.handle) {
        // 移动控制柄
        this.segment[this.handle] = this.segment[this.handle].add(event.delta);
      } else {
        // 移动点
        this.segment.point = this.segment.point.add(event.delta);
      }
      paper.view.update();
    }
  }

  onMouseUp(event) {
    if (this.isDrawing) {
      this.isDrawing = false;
      // 绘制完成后，对曲线进行平滑处理
      this.path.simplify();
      this.path.smooth({ type: 'catmull-rom', factor: 0.5 });
      this.path.fullySelected = true; // 显示控制柄
      paper.view.update();
    }

    // 重选中的段和控制柄
    this.segment = null;
    this.handle = null;
  }

  drawGrid() {
    this.gridGroup.removeChildren();
    const gridSpacing = 20;

    // 计算中心点
    const centerX = this.size.width / 2;
    const centerY = this.size.height / 2;
    // 计算最大距离（从中心点到最远角落的距离）
    const maxDistance = Math.sqrt(Math.pow(this.size.width, 2) + Math.pow(this.size.height, 2)) / 2;

    // 绘制垂直线
    for (let x = 0; x <= this.size.width; x += gridSpacing) {
      const path = new paper.Path.Line({
        from: [x, 0],
        to: [x, this.size.height],
        strokeWidth: 1,
      });

      // 计算当前线到中心的距离
      const distanceFromCenter = Math.abs(x - centerX);
      // 计算透明度（距离中心越远越透明）
      const opacity = Math.max(0.05, 0.3 - (distanceFromCenter / maxDistance) * 0.3);

      path.strokeColor = new paper.Color(0, 0, 0, opacity);
      path.guide = true;
      this.gridGroup.addChild(path);
    }

    // 绘制水平线
    for (let y = 0; y <= this.size.height; y += gridSpacing) {
      const path = new paper.Path.Line({
        from: [0, y],
        to: [this.size.width, y],
        strokeWidth: 1,
      });

      // 计算当前线到中心的距离
      const distanceFromCenter = Math.abs(y - centerY);
      // 计算透明度（距离中心越远越透明）
      const opacity = Math.max(0.05, 0.3 - (distanceFromCenter / maxDistance) * 0.3);

      path.strokeColor = new paper.Color(0, 0, 0, opacity);
      path.guide = true;
      this.gridGroup.addChild(path);
    }

    this.gridGroup.sendToBack();
    paper.view.update();
  }

  resizeCanvas() {
    if (this.canvas) {
      this.canvas.width = this.canvas.parentElement.clientWidth;
      this.canvas.height = this.canvas.parentElement.clientHeight;
      paper.view.viewSize = new paper.Size(this.canvas.width, this.canvas.height);
      this.size.width = paper.view.size.width;
      this.size.height = paper.view.size.height;

      this.drawGrid();
    }
  }

  clear() {
    if (this.path) {
      this.path.remove();
      this.path = null;
    }
    
    // 只有在未初始化时才重新设置工具和网格
    if (!this.isInitialized) {
      if (this.tool) {
        this.tool.remove();
      }
      if (paper.project) {
        paper.project.clear();
        this.gridGroup = new paper.Group();
        this.drawGrid();
        this.setupTool();
        paper.view.update();
      }
      this.isInitialized = true;
    }
  }

  destroy() {
    if (this.tool) {
      this.tool.remove();
    }
    if (paper.project) {
      paper.project.remove();
    }
    window.removeEventListener('resize', this.resizeCanvas.bind(this));
  }

  getPathsData() {
    // 获取路径的数据
    if (this.path) {
      return this.path.segments.map((segment) => ({
        x: segment.point.x,
        y: segment.point.y,
      }));
    } else {
      return [];
    }
  }

  // 修改触摸事件处理方法
  onTouchStart(event) {
    if (event.touches.length === 1) {
      const touch = event.touches[0];
      const rect = this.canvas.getBoundingClientRect();
      const point = new paper.Point(
        touch.clientX - rect.left,
        touch.clientY - rect.top
      );
      
      // 调用现有的鼠标事件处理逻辑
      this.onMouseDown({
        point: point,
        modifiers: {
          alt: false,
          shift: false
        }
      });
    }
  }

  onTouchMove(event) {
    if (event.touches.length === 1) {
      const touch = event.touches[0];
      const rect = this.canvas.getBoundingClientRect();
      const point = new paper.Point(
        touch.clientX - rect.left,
        touch.clientY - rect.top
      );
      
      // 调用现有的鼠标事件处理逻辑
      this.onMouseDrag({
        point: point,
        delta: this.previousPoint ? point.subtract(this.previousPoint) : new paper.Point(0, 0)
      });
      
      this.previousPoint = point;
    }
  }

  onTouchEnd(event) {
    // 调用现有的鼠标事件处理逻辑
    this.onMouseUp();
    this.previousPoint = null;
  }
}

let drawingApp = null;

// 引用画布
const canvas = ref(null);

// 键盘事件处理函数
const handleKeyDown = (e) => {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    // 删除选中的路径或点
    if (drawingApp && drawingApp.path) {
      const selectedItems = drawingApp.project.selectedItems;
      if (selectedItems.length > 0) {
        selectedItems.forEach((item) => {
          item.remove();
        });
        drawingApp.path = null;
        paper.view.update();
      }
    }
  }
};

// 生命周期钩子
onMounted(() => {
  if (canvas.value) {
    // 确保之前的实例被完全清理
    if (drawingApp) {
      drawingApp.destroy();
      drawingApp = null;
    }
    // 创建新实例
    drawingApp = new DrawingApp(canvas.value);
  }

  // 监听键盘事件
  window.addEventListener('keydown', handleKeyDown);
});

onBeforeUnmount(() => {
  if (drawingApp) {
    drawingApp.destroy();
    drawingApp = null;
  }
  // 移除全局键盘事件监听器
  window.removeEventListener('keydown', handleKeyDown);
});

// 提交数据函数
const submitData = async () => {
  const channelDataCache = store.state.channelDataCache;
  const rawQueryPattern = drawingApp ? drawingApp.getPathsData() : [];

  if (rawQueryPattern.length > 0) {
    // 归一化查询模式的 x 和 y 值
    const minX = Math.min(...rawQueryPattern.map(p => p.x));
    const maxX = Math.max(...rawQueryPattern.map(p => p.x));
    const xRange = maxX - minX;

    const minY = Math.min(...rawQueryPattern.map(p => p.y));
    const maxY = Math.max(...rawQueryPattern.map(p => p.y));
    const yRange = maxY - minY;

    // 只在这里翻转 Y 值
    const queryPattern = rawQueryPattern.map((point, index) => ({
      x: -1 + (2 * (point.x - minX) / xRange),
      y: -(-1 + (2 * (point.y - minY) / yRange))  // 翻转 Y 值
    }));

    // 初始化结果对象
    const matchResults = {};
    const smoothedData = {};

    // 使用 Promise.all 并行处理所有通道数据
    await Promise.all(selectedGunNumbers.value.map(async channel => {
      const channelData = channelDataCache[channel];
      if (channelData && queryPattern.length > 0) {
        try {
          // 使用 Worker 处理数据
          const processedData = await chartWorkerManager.processData({
            X_value: Array.from(channelData.X_value),
            Y_value: Array.from(channelData.Y_value)
          }, sampling.value);

          if (processedData) {
            // 使用 Worker 进行模式匹配
            const matches = await chartWorkerManager.findPatterns(
              queryPattern,
              Array.from(processedData.processedData.Y_value),
              Array.from(processedData.processedData.X_value)
            );

            // 使用 selectV2Options 中的格式作为键
            const channelInfo = selectV2Options.value.find(option =>
              option.children.some(child => child.value === channel)
            );

            if (channelInfo) {
              const child = channelInfo.children.find(child => child.value === channel);
              if (child) {
                const shotNumber = channel.split('_').pop();
                const channelName = child.label.split('_')[0];
                const key = `${channelName}_${shotNumber}`;

                // 存储匹配结果
                matchResults[key] = matches.map(match => ({
                  range: match.range,
                  distance: match.distance,
                  confidence: match.confidence,
                  timeSpan: match.range[1] - match.range[0],
                  startTime: match.range[0],
                  endTime: match.range[1],
                  channelName: channelName,
                  shotNumber: shotNumber
                }));

                // 存储采样后的数据
                smoothedData[key] = processedData;
              }
            }
          }
        } catch (error) {
          console.error(`处理通道 ${channel} 时出错:`, error);
          ElMessage.error(`处理通道 ${channel} 失败: ${error.message}`);
        }
      }
    }));

    // 当获取到匹配结果后
    if (Object.keys(matchResults).length > 0) {
      // 将匹配结果存入 store
      store.dispatch('updateMatchedResults', Object.values(matchResults));
    }
  }
};

// 修改清除画布函数
const clearCanvas = () => {
  if (drawingApp) {
    drawingApp.clear();
    // 清 store 中的匹配结果
    store.dispatch('clearMatchedResults');
  }
};

// 导出当前曲线数据到控制台
const exportCurrentCurve = () => {
  if (drawingApp) {
    console.log(JSON.stringify({
      name: "新模板",
      points: drawingApp.getPathsData()
    }, null, 2));
  }
}

// 加载选中的模板
const loadTemplate = (template) => {
  if (drawingApp && template && template.points) {
    // 清除前的路径
    drawingApp.clear();
    
    // 创建新路径
    drawingApp.path = new paper.Path();
    drawingApp.path.strokeColor = 'black';
    drawingApp.path.strokeWidth = 6;
    drawingApp.path.strokeCap = 'round';
    drawingApp.path.strokeJoin = 'round';
    
    // 直接添加模板中的点
    template.points.forEach(point => {
      drawingApp.path.add(new paper.Point(point.x, point.y));
    });
    
    // 平滑处理
    drawingApp.path.simplify();
    drawingApp.path.smooth({ type: 'catmull-rom', factor: 0.5 });
    drawingApp.path.fullySelected = true;
    
    // 更新图
    paper.view.update();
  }
}

// 预览模板
const previewTemplate = (template, canvas) => {
  const ctx = canvas.getContext('2d')
  const width = canvas.width
  const height = canvas.height
  
  ctx.clearRect(0, 0, width, height)
  ctx.beginPath()
  ctx.strokeStyle = '#409EFF'
  ctx.lineWidth = 2
  
  if (template.points.length > 0) {
    // 计算缩放比例
    const templatePoints = template.points;
    const minX = Math.min(...templatePoints.map(p => p.x));
    const maxX = Math.max(...templatePoints.map(p => p.x));
    const minY = Math.min(...templatePoints.map(p => p.y));
    const maxY = Math.max(...templatePoints.map(p => p.y));
    
    const scaleX = width / (maxX - minX);
    const scaleY = height / (maxY - minY);
    const scale = Math.min(scaleX, scaleY) * 0.8; // 留出一些边距
    
    // 计算居中偏移
    const offsetX = (width - (maxX - minX) * scale) / 2 - minX * scale;
    const offsetY = (height - (maxY - minY) * scale) / 2 - minY * scale;
    
    templatePoints.forEach((point, index) => {
      const x = point.x * scale + offsetX;
      const y = point.y * scale + offsetY;
      
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    
    ctx.stroke();
  }
}

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

// 修改原有的 onMounted，增加全选状态的初始化
onMounted(() => {
  selectV2Options.value.forEach(group => {
    groupSelectAll.value[group.value] = false;
  });
  allSelected.value = false;
});

// 修改触摸事件处理函数
const onCanvasTouch = (event) => {
  if (!drawingApp) return;
  
  // 将触摸事件转换为鼠标事件
  const touch = event.touches?.[0] || event.changedTouches?.[0];
  if (!touch) return;
  
  const rect = canvas.value.getBoundingClientRect();
  const point = new paper.Point(
    touch.clientX - rect.left,
    touch.clientY - rect.top
  );
  
  // 根据事件类型调用相应的处理函数
  switch (event.type) {
    case 'touchstart':
      drawingApp.onMouseDown({ point });
      break;
    case 'touchmove':
      drawingApp.onMouseDrag({ 
        point,
        delta: drawingApp.previousPoint ? 
          point.subtract(drawingApp.previousPoint) : 
          new paper.Point(0, 0)
      });
      drawingApp.previousPoint = point;
      break;
    case 'touchend':
    case 'touchcancel':
      drawingApp.onMouseUp();
      drawingApp.previousPoint = null;
      break;
  }
};
</script>

<style scoped>
.container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.header {
  padding: 5px 0;
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

.select-template,
.select-history {
  width: 150px;
  margin-left: 5px;
}

.sketch-container {
  position: relative;
  border: 0.5px solid #ccc;
  display: flex;
  flex-direction: column;
  border-radius: 5px;
  width: 100%;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  touch-action: none;
  overscroll-behavior: contain;
}

.canvas-container {
  position: relative;
  flex: 1;
  min-height: 0;
  height: 0;
  touch-action: none;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  overscroll-behavior: contain;
  pointer-events: auto;
  isolation: isolate;
}

canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  touch-action: none;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  overscroll-behavior: contain;
  pointer-events: auto;
  isolation: isolate;
}

.controls-wrapper {
  flex-shrink: 0;
  padding: 8px;
  background-color: #fff;
}

.inputs-container {
  position: relative;
}

.input-row {
  display: flex;
  justify-content: space-between;
  padding: 8px;
  background-color: #f5f7fa;
  border-radius: 4px;
  gap: 12px;
}

.input-row+.input-row {
  margin-top: 8px;
}

.input-group {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.input-label {
  margin-right: 8px;
  color: #606266;
  font-size: 14px;
  white-space: nowrap;
  width: 40px;
}

.time-input,
.bound-input {
  flex: 1;
  width: 100%;
}

.buttons {
  position: absolute;
  bottom: 0px;
  right: 6px;
}

.search-button {
  margin-left: 5px;
}

.title {
  color: #999;
}

.template-controls {
  margin-bottom: 16px;
  display: flex;
  gap: 16px;
}

.template-preview {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 4px;
  background: #f5f7fa;
  border-radius: 4px;
}

.template-preview canvas {
  display: block;
}
</style>
