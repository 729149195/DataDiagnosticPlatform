<template>
  <div class="sketch-container">
    <div class="canvas-container">
      <canvas ref="canvas"></canvas>
      <el-progress :percentage="match_percentage"  v-if="match_percentage >= 0 && match_percentage < 100"/>
      <el-progress :percentage="match_percentage" status="success" v-if="match_percentage === 100"/>
      <button class="clear-button" @click="clearCanvas">×</button>
    </div>
    <span style="position: absolute; bottom: 8px; left: 8px;">
      起始
      <el-input type="number" v-model.number="time_begin" @input="onInputChange('time_begin')"
        style="width: 70px; margin-right: 8px;" placeholder="null" />/s
      时长
      <el-input type="number" v-model.number="time_during" @input="onInputChange('time_during')"
        style="width: 70px; margin-right: 8px;" placeholder="null" />
      终止
      <el-input type="number" v-model.number="time_end" @input="onInputChange('time_end')" style="width: 70px"
        placeholder="null" /> </span>
    <span style="position: absolute; bottom: 20%; left: 8px;">
      上界
      <el-input type="number" v-model.number="upper_bound" @input="onInputChange('upper_bound')"
        style="width: 70px; display: block; margin-bottom: 8px;" placeholder="null" />
      幅度
      <el-input type="number" v-model.number="scope_bound" @input="onInputChange('scope_bound')"
        style="width: 70px; display: block; margin-bottom: 8px;" placeholder="null" />
      下界
      <el-input type="number" v-model.number="lower_bound" @input="onInputChange('lower_bound')"
        style="width: 70px; display: block" placeholder="null" />
    </span>
    <span style="position: absolute; bottom: 8px; right: 8px;">
      <el-button type="success" :icon="Search" @click="submitData">查询</el-button>
    </span>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { Search } from '@element-plus/icons-vue';
import axios from 'axios';
import { useStore } from 'vuex';
import { io } from 'socket.io-client';

const store = useStore()

const socket = new WebSocket('ws://localhost:5000/ws/progress/');
socket.onopen = function(e) {
    console.log("WebSocket connection established.");
};
socket.onerror = function(error) {
    console.log(`WebSocket error: ${error.message}`);
};
socket.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.progress !== undefined) {
        console.log(`Progress: ${data.progress}%`);
        // 更新进度条等 UI 元素
        match_percentage.value = data.progress
    }
    if (data.matched_results !== undefined) {
        console.log("Matched Results:", data.matched_results);
        // 处理匹配结果，例如显示在界面上
        store.dispatch('updateMatchedResults', data.matched_results);
    }
};
const match_percentage = ref(-1)
const matchedResults = ref([]);

const canvas = ref(null);
let ctx = null;
let isDrawing = false;
let lastX = 0;
let lastY = 0;
let points = []; // 存储手绘点

const time_begin = ref(-0.25);
const time_during = ref(0.15);
const time_end = ref(-0.1);
const upper_bound = ref(0.1);
const scope_bound = ref(2.5);
const lower_bound = ref(-2.4);

const canDraw = ref(true);

let isManualChange = ref(false); // 标记是否为手动修改

const BASE_DURATION = 200; // 固定的基准时长
const BASE_SCOPE = 100; // 固定的基准幅度


const submitData = async () => {
  match_percentage.value = 0;
  try {
    const payload = {
      selectedChannels: store.getters.getSelectedChannels,
      actualPoints: actual_points,
      time_begin: time_begin.value,
      time_end: time_end.value,
      upper_bound: upper_bound.value,
      lower_bound: lower_bound.value
    };
    const response = await axios.post('http://localhost:5000/api/submit-data', payload);

    console.log('Response from server:', response.data);
  } catch (error) {
    console.error('Failed to send data to server:', error);
  }
};

function onInputChange(changedField) {
  isManualChange.value = true;
  updateValues(changedField);
}

function updateValues(changedField) {
  if (changedField === 'time_begin' && time_begin.value !== null && time_during.value !== null) {
    time_end.value = time_begin.value + time_during.value;
  } else if (changedField === 'time_during' && time_during.value !== null && time_begin.value !== null) {
    time_end.value = time_begin.value + time_during.value;
  } else if (changedField === 'time_end' && time_end.value !== null && time_begin.value !== null) {
    time_during.value = time_end.value - time_begin.value;
  }

  if (changedField === 'upper_bound' && upper_bound.value !== null && scope_bound.value !== null) {
    lower_bound.value = upper_bound.value - scope_bound.value;
  } else if (changedField === 'scope_bound' && scope_bound.value !== null && upper_bound.value !== null) {
    lower_bound.value = upper_bound.value - scope_bound.value;
  } else if (changedField === 'lower_bound' && lower_bound.value !== null && upper_bound.value !== null) {
    scope_bound.value = upper_bound.value - lower_bound.value;
  }

  isManualChange.value = false; // 重置手动修改标记
}

// 监听输入值的变化，并在所有值都有时，允许绘制
watch([time_begin, time_during, time_end, upper_bound, scope_bound, lower_bound], ([begin, during, end, upper, scope, lower]) => {
  canDraw.value = begin !== null && during !== null && end !== null && upper !== null && scope !== null && lower !== null;
});

function drawGrid() {
  if (!ctx) return;
  const { width, height } = canvas.value;

  ctx.strokeStyle = '#e0e0e0';
  ctx.lineWidth = 1.5;

  for (let x = 0; x <= width; x += 20) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
  }

  for (let y = 0; y <= height; y += 20) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
  }
}

function initCanvas() {
  const canvasEl = canvas.value;
  ctx = canvasEl.getContext('2d');

  resizeCanvas();
  drawGrid();

  ctx.strokeStyle = 'black';
  ctx.lineWidth = 1;
  ctx.lineCap = 'round';
}

function resizeCanvas() {
  const canvasEl = canvas.value;
  const container = canvasEl.parentElement;
  canvasEl.width = container.clientWidth;
  canvasEl.height = container.clientHeight;
}

function handleResize() {
  if (!ctx) return;
  const imageData = ctx.getImageData(0, 0, canvas.value.width, canvas.value.height);
  ctx.clearRect(0, 0, canvas.value.width, canvas.value.height);
  resizeCanvas();
  drawGrid();
  ctx.putImageData(imageData, 0, 0);
}

function startDrawing(e) {
  if (!canDraw.value) {
    alert("请先填写所有必要的参数（上界、下界、幅度、起始、时长、终止）。");
    return;
  }

  isDrawing = true;
  points = [];
  const { x, y } = getMousePos(e);
  lastX = x;
  lastY = y;
  points.push({ x: lastX, y: lastY });
}

function draw(e) {
  if (!isDrawing) return;
  const { x, y } = getMousePos(e);

  ctx.beginPath();
  ctx.moveTo(lastX, lastY);
  ctx.lineTo(x, y);
  ctx.stroke();

  lastX = x;
  lastY = y;
  points.push({ x: lastX, y: lastY });
}

function stopDrawing() {
  isDrawing = false;
  if (points.length > 1) {
    smoothAndReplaceCurve();
  }
}

let actual_points = []; // 用于保存实际范围内的点

function smoothAndReplaceCurve() {
  if (points.length < 4) return;
  clearCanvas();

  // 1. 简化曲线
  const simplifiedPoints = simplifyRDP(points, 2);

  // 2. 生成平滑曲线
  const splinePoints = generateCatmullRomSpline(simplifiedPoints, 0.1);

  // 3. 缩放曲线到用户指定的范围
  const scaledPoints = scalePointsToRange(splinePoints, {
    xMin: time_begin.value,
    xMax: time_end.value,
    yMin: lower_bound.value,
    yMax: upper_bound.value
  });

  // 4. 保存实际的点到 actual_points 数组中，并转换为 {'X': [], 'Y': []} 格式
  actual_points = {
    X: splinePoints.map(point => 
      ((point.x - Math.min(...points.map(p => p.x))) / (Math.max(...points.map(p => p.x)) - Math.min(...points.map(p => p.x)))) * (time_end.value - time_begin.value) + time_begin.value
    ),
    Y: splinePoints.map(point => 
      ((point.y - Math.min(...points.map(p => p.y))) / (Math.max(...points.map(p => p.y)) - Math.min(...points.map(p => p.y)))) * (upper_bound.value - lower_bound.value) + lower_bound.value
    )
  };

  // 5. 计算曲线的边界（最小和最大值）
  const xMin = Math.min(...scaledPoints.map(p => p.x));
  const xMax = Math.max(...scaledPoints.map(p => p.x));
  const yMin = Math.min(...scaledPoints.map(p => p.y));
  const yMax = Math.max(...scaledPoints.map(p => p.y));

  // 6. 计算缩放系数（将曲线缩放到基准范围）
  const scaleX = BASE_DURATION / (time_end.value - time_begin.value);
  const scaleY = BASE_SCOPE / (upper_bound.value - lower_bound.value);

  // 7. 计算画布的中心点
  const canvasCenterX = canvas.value.width / 2;
  const canvasCenterY = canvas.value.height / 2;

  // 8. 计算曲线的中心点
  const curveCenterX = (xMin + xMax) / 2;
  const curveCenterY = (yMin + yMax) / 2;

  // 9. 计算平移量，使曲线位于画布中心
  const translateX = canvasCenterX - curveCenterX * scaleX;
  const translateY = canvasCenterY - curveCenterY * scaleY;

  // 10. 保存当前线条宽度
  const originalLineWidth = ctx.lineWidth;

  // 11. 平移和缩放画布，将曲线缩放到基准大小并居中
  ctx.save(); // 保存当前的绘图状态
  ctx.translate(translateX, translateY);
  ctx.scale(scaleX, scaleY);

  // 12. 恢复线条宽度，确保线条粗细不受缩放影响
  ctx.lineWidth = originalLineWidth / Math.max(scaleX, scaleY);

  // 13. 绘制缩放后的曲线，保持恒定粗细
  ctx.beginPath();
  ctx.moveTo(scaledPoints[0].x, scaledPoints[0].y);
  for (let i = 1; i < scaledPoints.length; i++) {
    ctx.lineTo(scaledPoints[i].x, scaledPoints[i].y);
  }
  ctx.stroke();

  // 14. 恢复上下文的状态
  ctx.restore();

  // console.log("points", points);
  // console.log("splinePoints", splinePoints);
  // console.log("actual_points", actual_points);  // 输出新格式的 actual_points
  
}



// 缩放点到指定的范围
function scalePointsToRange(points, range) {
  const xMin = Math.min(...points.map(p => p.x));
  const xMax = Math.max(...points.map(p => p.x));
  const yMin = Math.min(...points.map(p => p.y));
  const yMax = Math.max(...points.map(p => p.y));

  return points.map(point => ({
    x: ((point.x - xMin) / (xMax - xMin)) * (range.xMax - range.xMin) + range.xMin,
    y: ((point.y - yMin) / (yMax - yMin)) * (range.yMax - range.yMin) + range.yMin
  }));
}

function simplifyRDP(points, epsilon) {
  if (points.length < 3) return points;

  const firstPoint = points[0];
  const lastPoint = points[points.length - 1];

  let maxDist = 0;
  let index = 0;

  for (let i = 1; i < points.length - 1; i++) {
    const dist = perpendicularDistance(points[i], firstPoint, lastPoint);
    if (dist > maxDist) {
      maxDist = dist;
      index = i;
    }
  }

  if (maxDist > epsilon) {
    const left = simplifyRDP(points.slice(0, index + 1), epsilon);
    const right = simplifyRDP(points.slice(index), epsilon);
    return left.slice(0, left.length - 1).concat(right);
  } else {
    return [firstPoint, lastPoint];
  }
}

function perpendicularDistance(point, lineStart, lineEnd) {
  const x0 = point.x, y0 = point.y;
  const x1 = lineStart.x, y1 = lineStart.y;
  const x2 = lineEnd.x, y2 = lineEnd.y;

  const numerator = Math.abs((y2 - y1) * x0 - (x2 - x1) * y0 + x2 * y1 - y2 * x1);
  const denominator = Math.sqrt(Math.pow(y2 - y1, 2) + Math.pow(x2 - x1, 2));

  return numerator / denominator;
}

function generateCatmullRomSpline(points, step = 0.01) {
  const splinePoints = [];
  const alpha = 0.5;

  for (let i = 0; i < points.length - 1; i++) {
    const p0 = i > 0 ? points[i - 1] : points[i];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = i !== points.length - 2 ? points[i + 2] : points[i + 1];

    for (let t = 0; t <= 1; t += step) {
      const point = catmullRomInterpolate(p0, p1, p2, p3, t, alpha);
      splinePoints.push(point);
    }
  }

  return splinePoints;
}

function catmullRomInterpolate(p0, p1, p2, p3, t, alpha) {
  const t2 = t * t;
  const t3 = t2 * t;

  const x = 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * t + (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 + (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3);
  const y = 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * t + (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 + (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3);

  return { x, y };
}

function clearCanvas() {
  if (!ctx) return;
  ctx.clearRect(0, 0, canvas.value.width, canvas.value.height);
  drawGrid();
  ctx.strokeStyle = 'black';
  ctx.lineWidth = 2;
  ctx.lineCap = 'round';
}

function getMousePos(e) {
  const rect = canvas.value.getBoundingClientRect();
  return {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top
  };
}

onMounted(() => {
  initCanvas();
  canvas.value.addEventListener('mousedown', startDrawing);
  canvas.value.addEventListener('mousemove', draw);
  canvas.value.addEventListener('mouseup', stopDrawing);
  canvas.value.addEventListener('mouseleave', stopDrawing);
  window.addEventListener('resize', handleResize);
});

onBeforeUnmount(() => {
  canvas.value.removeEventListener('mousedown', startDrawing);
  canvas.value.removeEventListener('mousemove', draw);
  canvas.value.removeEventListener('mouseup', stopDrawing);
  canvas.value.removeEventListener('mouseleave', stopDrawing);
  window.removeEventListener('resize', handleResize);
});
</script>

<style scoped>
.sketch-container {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.canvas-container {
  position: relative;
  flex: 1;
  margin-left: 75px;
  height: 100%;
}

canvas {
  border: 1px solid #ccc;
  width: 100%;
  height: 100%;
  cursor: crosshair;
  display: block;
}

.clear-button {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(255, 255, 255, 0.8);
  border: none;
  color: #333;
  font-size: 18px;
  line-height: 1;
  padding: 4px 8px;
  cursor: pointer;
  border-radius: 50%;
  box-shadow: 0 0 5px rgba(0, 0, 0, 0.2);
  transition: background 0.3s, color 0.3s;
}

.clear-button:hover {
  background: rgba(255, 17, 0, 0.274);
  color: #fff;
}
</style>
