<template>
  <div class="container">
    <!-- 顶部操作栏 -->
    <div class="header">
      <span class="title">查询</span>
      <span class="operate">
        <el-select v-model="selectedGunNumbers" placeholder="请选择需要匹配的通道" multiple collapse-tags clearable
          collapse-tags-tooltip class="select-gun-numbers">
          <el-option-group v-for="group in selectV2Options" :key="group.value" :label="group.label">
            <el-option v-for="option in group.children" :key="option.value" :label="option.label"
              :value="option.value" />
          </el-option-group>
        </el-select>

        <!-- 模板选择 -->
        <el-select v-model="templatavalue" placeholder="模板" class="select-template">
          <el-option v-for="item in templates" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>

        <!-- 历史选择 -->
        <el-select v-model="historyvalue" placeholder="历史" class="select-history">
          <el-option v-for="item in historys" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
      </span>
    </div>

    <!-- 绘图区域 -->
    <div class="sketch-container">
      <canvas ref="canvas"></canvas>
      <div class="buttons">
        <el-button type="danger" class="clear-button" @click="clearCanvas">
          清除
        </el-button>
        <el-button type="success" :icon="Search" @click="submitData" class="search-button">
          查询
        </el-button>
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
} from 'vue';
import { Search } from '@element-plus/icons-vue';
import { useStore } from 'vuex';
import paper from 'paper';
import { DataSmoother } from './data-smoother'; // 导入数据平滑处理类
import { PatternMatcher } from './pattern-matcher'; // 导入模式匹配类

// 使用 Vuex store
const store = useStore();

// 绑定的值
const templatavalue = ref('');
const historyvalue = ref('');

// 选中的炮号数组
const selectedGunNumbers = ref([]);
const smoothness = computed(() => store.state.smoothness);
const sampling = computed(() => store.state.sampling);

const brush_begin = computed(() => store.state.brush_begin);
const brush_end = computed(() => store.state.brush_end);

// 从 Vuex 获取 selectedChannels
const selectedChannels = computed(() => store.state.selectedChannels);

// 历史选项
const historys = [
  { value: 'Option1', label: '历史1' },
  { value: 'Option2', label: '历史2' },
];

// 模板选项
const templates = [
  { value: 'Option1', label: '模板1' },
  { value: 'Option2', label: '模板2' },
];

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
const time_begin = ref(-0.25);
const time_during = ref(0.15);
const time_end = ref(-0.1);
const upper_bound = ref(0.1);
const scope_bound = ref(2.5);
const lower_bound = ref(-2.4);

// ----------- 画布绘图逻辑开始 -----------

class DrawingApp {
  constructor(canvasElement) {
    this.canvas = canvasElement;
    // 确保先清理之前的项目和工具
    if (paper.project) {
      paper.project.remove();
    }
    if (paper.tools) {
      paper.tools.forEach(tool => tool.remove());
    }

    // 重新初始化 paper
    paper.setup(this.canvas);
    this.project = paper.project;

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

    // 绑定方法
    this.onMouseDown = this.onMouseDown.bind(this);
    this.onMouseDrag = this.onMouseDrag.bind(this);
    this.onMouseUp = this.onMouseUp.bind(this);

    this.setupTool();
    this.drawGrid();

    window.addEventListener('resize', this.resizeCanvas.bind(this));
  }

  setupTool() {
    if (this.tool) {
      this.tool.remove();
    }
    this.tool = new paper.Tool();
    this.tool.activate();
    this.tool.onMouseDown = this.onMouseDown;
    this.tool.onMouseDrag = this.onMouseDrag;
    this.tool.onMouseUp = this.onMouseUp;
  }

  onMouseDown(event) {
    this.segment = null;
    this.handle = null;

    let hitResult = this.project.hitTest(event.point, this.hitOptions);

    if (hitResult && hitResult.item) {
      // 用户点击了一个项目
      let clickedPath = hitResult.item;
      if (!(clickedPath instanceof paper.Path)) {
        // 如果点击不是 Path，而是其子项
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
          // 添加新点
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

        // 添加第一个点
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

    // 重置选中的段和控制柄
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
    if (this.tool) {
      this.tool.remove();
    }
    if (paper.project) {
      paper.project.clear();
      // 重新初始化网格
      this.gridGroup = new paper.Group();
      this.drawGrid();
      // 重新设置工具
      this.setupTool();
      // 确保视图更新
      paper.view.update();
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
  // 创建数据平滑器实例
  const dataSmoother = new DataSmoother();
  
  const patternMatcher = new PatternMatcher({
    distanceMetric: 'euclidean',
    matchThreshold: 1.0,
    windowSize: 1.5
  });

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

    selectedGunNumbers.value.forEach(channel => {
      const channelData = channelDataCache[channel];
      if (channelData && queryPattern.length > 0) {
        // 进行采样处理
        const samplingInterval = Math.floor(1 / sampling.value);
        const sampledData = {
          ...channelData,
          X_value: channelData.X_value.filter((_, i) => i % samplingInterval === 0),
          Y_value: channelData.Y_value.filter((_, i) => i % samplingInterval === 0),
        };

        // 创建数据点数组
        const dataPoints = sampledData.Y_value.map((y, index) => ({
          x: sampledData.X_value[index],
          y: y,
          origX: sampledData.X_value[index],
          origY: y
        }));

        // 对数据进行平滑处理
        const smoothedPoints = dataSmoother.smoothData(dataPoints, smoothness.value);

        try {
          // 使用平滑后的数据进行模式匹配
          const matches = patternMatcher.findPatterns(
            queryPattern,
            smoothedPoints.map(p => p.y),  // 使用平滑后的 Y 值
            smoothedPoints.map(p => p.x)   // 使用平滑后的 X 值
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
              
              // 存储匹配结果，包含所有必要的指标
              matchResults[key] = matches.map(match => ({
                range: match.range,                // X值区间 [startX, endX]
                distance: match.distance,          // DTW距离
                confidence: match.confidence,      // 匹配置信度
                timeSpan: match.range[1] - match.range[0],  // 时间跨度
                startTime: match.range[0],        // 开始时间
                endTime: match.range[1],          // 结束时间
                channelName: channelName,         // 通道名称
                shotNumber: shotNumber            // 炮号
              }));

              // 存储采样后的数据
              smoothedData[key] = sampledData;
            }
          }
        } catch (error) {
          console.error(`处理通道 ${channel} 时出错:`, error);
        }
      }
    });

    // 输出结果
    console.log('平滑后的数据:', smoothedData);
    console.log('匹配结果:', matchResults);
    console.log('查询模式:', queryPattern);

    // 当获取到匹配结果后
    if (Object.keys(matchResults).length > 0) {
      // 将匹配结果存入 store
      store.dispatch('updateMatchedResults', Object.values(matchResults));
    }

    console.log(store.state.matchedResults);
  }
};

// 修改清除画布函数
const clearCanvas = () => {
  if (drawingApp) {
    drawingApp.clear();
    // 清除 store 中的匹配结果
    store.dispatch('clearMatchedResults');
  }
};
</script>

<style scoped>
.container {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 5px;
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
  width: 80px;
  margin-left: 5px;
}

.sketch-container {
  position: relative;
  border: 0.5px solid #ccc;
  display: flex;
  border-radius: 5px;
  flex-direction: column;
  align-items: stretch;
  width: 100%;
  height: 100%;
}

canvas {
  width: 100%;
  height: 100%;
}

.buttons {
  position: absolute;
  bottom: 8px;
  right: 8px;
  display: flex;
}

.search-button {
  margin-left: 5px;
}

.title {
  color: #999;
}
</style>
