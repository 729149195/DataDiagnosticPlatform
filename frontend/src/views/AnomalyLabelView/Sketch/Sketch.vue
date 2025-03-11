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
        <!-- 使用SVG替代Canvas作为白板 -->
        <svg ref="svgCanvas" class="whiteboard-svg"></svg>
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
import * as d3 from 'd3';
import curveTemplates from '@/assets/templates/curveTemplates.json'
import chartWorkerManager from '@/workers/chartWorkerManager';

// 使用 Vuex store
const store = useStore();

// 选中的炮号数组
const selectedGunNumbers = ref([]);
const sampling = computed(() => store.state.sampling);

// 从 Vuex 获取 selectedChannels
const selectedChannels = computed(() => store.state.selectedChannels);

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

// ----------- 白板绘图逻辑开始 -----------

class WhiteboardApp {
  constructor(svgElement) {
    this.svg = d3.select(svgElement);
    this.width = svgElement.clientWidth;
    this.height = svgElement.clientHeight;
    
    // 创建网格线组
    this.gridGroup = this.svg.append('g').attr('class', 'grid-group');
    
    // 创建绘图组
    this.drawingGroup = this.svg.append('g').attr('class', 'drawing-group');
    
    // 创建路径生成器
    this.line = d3.line()
      .x(d => d.x)
      .y(d => d.y)
      .curve(d3.curveCatmullRom.alpha(0.5));
    
    // 当前绘制的路径
    this.currentPath = null;
    this.pathData = [];
    
    // 设置事件监听
    this.setupEvents();
    
    // 绘制网格线
    this.drawGrid();
    
    // 添加窗口大小变化监听
    window.addEventListener('resize', this.resizeCanvas.bind(this));
  }
  
  setupEvents() {
    // 鼠标事件
    this.svg
      .on('mousedown', (event) => this.onMouseDown(event))
      .on('mousemove', (event) => this.onMouseMove(event))
      .on('mouseup', () => this.onMouseUp())
      .on('mouseleave', () => this.onMouseUp());
      
    // 触摸事件
    this.svg.node()
      .addEventListener('touchstart', (event) => this.onTouchStart(event), { passive: true });
    this.svg.node()
      .addEventListener('touchmove', (event) => this.onTouchMove(event), { passive: true });
    this.svg.node()
      .addEventListener('touchend', () => this.onTouchEnd(), { passive: true });
    this.svg.node()
      .addEventListener('touchcancel', () => this.onTouchEnd(), { passive: true });
  }
  
  drawGrid() {
    // 清除现有网格
    this.gridGroup.selectAll('*').remove();
    
    // 获取当前尺寸
    this.width = this.svg.node().clientWidth;
    this.height = this.svg.node().clientHeight;
    
    // 网格间距
    const gridSpacing = 20;
    
    // 计算中心点
    const centerX = this.width / 2;
    const centerY = this.height / 2;
    
    // 计算最大距离（从中心点到最远角落的距离）
    const maxDistance = Math.sqrt(Math.pow(this.width, 2) + Math.pow(this.height, 2)) / 2;
    
    // 绘制垂直线
    for (let x = 0; x <= this.width; x += gridSpacing) {
      // 计算当前线到中心的距离
      const distanceFromCenter = Math.abs(x - centerX);
      // 计算透明度（距离中心越远越透明）
      const opacity = Math.max(0.05, 0.3 - (distanceFromCenter / maxDistance) * 0.3);
      
      this.gridGroup.append('line')
        .attr('x1', x)
        .attr('y1', 0)
        .attr('x2', x)
        .attr('y2', this.height)
        .attr('stroke', 'black')
        .attr('stroke-width', 1)
        .attr('opacity', opacity);
    }
    
    // 绘制水平线
    for (let y = 0; y <= this.height; y += gridSpacing) {
      // 计算当前线到中心的距离
      const distanceFromCenter = Math.abs(y - centerY);
      // 计算透明度（距离中心越远越透明）
      const opacity = Math.max(0.05, 0.3 - (distanceFromCenter / maxDistance) * 0.3);
      
      this.gridGroup.append('line')
        .attr('x1', 0)
        .attr('y1', y)
        .attr('x2', this.width)
        .attr('y2', y)
        .attr('stroke', 'black')
        .attr('stroke-width', 1)
        .attr('opacity', opacity);
    }
  }
  
  resizeCanvas() {
    // 更新尺寸
    this.width = this.svg.node().clientWidth;
    this.height = this.svg.node().clientHeight;
    
    // 重绘网格
    this.drawGrid();
  }
  
  onMouseDown(event) {
    // 开始绘制
    this.isDrawing = true;
    
    // 获取鼠标位置
    const [x, y] = d3.pointer(event);
    
    // 创建新路径
    this.pathData = [{ x, y }];
    this.previousPoint = { x, y };
    
    this.currentPath = this.drawingGroup.append('path')
      .datum(this.pathData)
      .attr('d', this.line)
      .attr('fill', 'none')
      .attr('stroke', 'black')
      .attr('stroke-width', 6)
      .attr('stroke-linecap', 'round')
      .attr('stroke-linejoin', 'round');
  }
  
  onMouseMove(event) {
    if (!this.isDrawing) return;
    
    // 获取鼠标位置
    const [x, y] = d3.pointer(event);
    
    // x 轴递增约束
    if (x >= this.previousPoint.x) {
      this.pathData.push({ x, y });
      this.previousPoint = { x, y };
      
      // 更新路径
      this.currentPath.datum(this.pathData).attr('d', this.line);
    }
  }
  
  onMouseUp() {
    this.isDrawing = false;
  }
  
  onTouchStart(event) {
    if (event.touches.length !== 1) return;
    
    // 阻止默认行为
    event.preventDefault();
    
    const touch = event.touches[0];
    const rect = this.svg.node().getBoundingClientRect();
    const x = touch.clientX - rect.left;
    const y = touch.clientY - rect.top;
    
    // 开始绘制
    this.isDrawing = true;
    
    // 创建新路径
    this.pathData = [{ x, y }];
    this.previousPoint = { x, y };
    
    this.currentPath = this.drawingGroup.append('path')
      .datum(this.pathData)
      .attr('d', this.line)
      .attr('fill', 'none')
      .attr('stroke', 'black')
      .attr('stroke-width', 6)
      .attr('stroke-linecap', 'round')
      .attr('stroke-linejoin', 'round');
  }
  
  onTouchMove(event) {
    if (!this.isDrawing || event.touches.length !== 1) return;
    
    // 阻止默认行为
    event.preventDefault();
    
    const touch = event.touches[0];
    const rect = this.svg.node().getBoundingClientRect();
    const x = touch.clientX - rect.left;
    const y = touch.clientY - rect.top;
    
    // x 轴递增约束
    if (x >= this.previousPoint.x) {
      this.pathData.push({ x, y });
      this.previousPoint = { x, y };
      
      // 更新路径
      this.currentPath.datum(this.pathData).attr('d', this.line);
    }
  }
  
  onTouchEnd() {
    this.isDrawing = false;
  }
  
  clear() {
    // 清除所有绘制的路径
    this.drawingGroup.selectAll('*').remove();
    this.pathData = [];
    this.currentPath = null;
  }
  
  destroy() {
    // 移除事件监听
    this.svg
      .on('mousedown', null)
      .on('mousemove', null)
      .on('mouseup', null)
      .on('mouseleave', null);
      
    this.svg.node().removeEventListener('touchstart', this.onTouchStart);
    this.svg.node().removeEventListener('touchmove', this.onTouchMove);
    this.svg.node().removeEventListener('touchend', this.onTouchEnd);
    this.svg.node().removeEventListener('touchcancel', this.onTouchEnd);
    
    window.removeEventListener('resize', this.resizeCanvas);
    
    // 清除所有内容
    this.svg.selectAll('*').remove();
  }
  
  getPathsData() {
    // 获取路径的数据
    return this.pathData.map(point => ({
      x: point.x,
      y: point.y
    }));
  }
  
  loadTemplate(templatePoints) {
    // 清除现有路径
    this.clear();
    
    if (templatePoints && templatePoints.length > 0) {
      // 创建新路径
      this.pathData = templatePoints.map(point => ({
        x: point.x,
        y: point.y
      }));
      
      this.currentPath = this.drawingGroup.append('path')
        .datum(this.pathData)
        .attr('d', this.line)
        .attr('fill', 'none')
        .attr('stroke', 'black')
        .attr('stroke-width', 6)
        .attr('stroke-linecap', 'round')
        .attr('stroke-linejoin', 'round');
    }
  }
}

let whiteboardApp = null;

// 引用SVG元素
const svgCanvas = ref(null);

// 键盘事件处理函数
const handleKeyDown = (e) => {
  if (e.key === 'Delete' || e.key === 'Backspace') {
    clearCanvas();
  }
};

// 生命周期钩子
onMounted(() => {
  if (svgCanvas.value) {
    // 确保之前的实例被完全清理
    if (whiteboardApp) {
      whiteboardApp.destroy();
      whiteboardApp = null;
    }
    // 创建新实例
    whiteboardApp = new WhiteboardApp(svgCanvas.value);
  }

  // 监听键盘事件
  window.addEventListener('keydown', handleKeyDown);
  
  // 初始化分组全选状态
  selectV2Options.value.forEach(group => {
    groupSelectAll.value[group.value] = false;
  });
  allSelected.value = false;
});

onBeforeUnmount(() => {
  if (whiteboardApp) {
    whiteboardApp.destroy();
    whiteboardApp = null;
  }
  // 移除全局键盘事件监听器
  window.removeEventListener('keydown', handleKeyDown);
});

// 提交数据函数
const submitData = async () => {
  const channelDataCache = store.state.channelDataCache;
  const rawQueryPattern = whiteboardApp ? whiteboardApp.getPathsData() : [];

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
  if (whiteboardApp) {
    whiteboardApp.clear();
    // 清 store 中的匹配结果
    store.dispatch('clearMatchedResults');
  }
};

// 导出当前曲线数据到控制台
const exportCurrentCurve = () => {
  if (whiteboardApp) {
    console.log(JSON.stringify({
      name: "新模板",
      points: whiteboardApp.getPathsData()
    }, null, 2));
  }
}

// 加载选中的模板
const loadTemplate = (template) => {
  if (whiteboardApp && template && template.points) {
    whiteboardApp.loadTemplate(template.points);
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
</script>

<style scoped>
.container {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
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

.whiteboard-svg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: white;
  touch-action: none;
  -webkit-touch-callout: none;
  -webkit-user-select: none;
  user-select: none;
  -webkit-tap-highlight-color: transparent;
  overscroll-behavior: contain;
  pointer-events: auto;
  isolation: isolate;
}

.buttons {
  position: absolute;
  bottom: 6px;
  right: 6px;
}

.search-button {
  margin-left: 5px;
}

.title {
  color: #333;
  font-weight: bold;
  font-size: 12pt;
  margin-left: 5px;
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
