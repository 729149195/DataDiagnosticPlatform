<template>
  <div class="container">
    <!-- 顶部操作栏 -->
    <div class="header">
      <span class="title">手绘查询</span>
      <span class="operate">
        <el-select v-model="selectedGunNumbers" placeholder="请选择需要匹配的通道" multiple collapse-tags clearable collapse-tags-tooltip class="select-gun-numbers">
          <!-- 添加全部全选选项 -->
          <el-option key="select-all" value="select-all" label="全选所有通道">
            <el-checkbox v-model="allSelected" @change="handleSelectAll">
              全选所有通道
            </el-checkbox>
          </el-option>

          <!-- 添加分组全选选项 -->
          <el-option v-for="group in selectV2Options" :key="'select-all-' + group.value" :value="'select-all-' + group.value" :label="'全选' + group.label">
            <el-checkbox v-model="groupSelectAll[group.value]" @change="(val) => handleSelectAllGroup(val, group)">
              全选{{ group.label }}
            </el-checkbox>
          </el-option>

          <!-- 原有的分组选项 -->
          <el-option-group v-for="group in selectV2Options" :key="group.value" :label="group.label">
            <el-option v-for="option in group.children" :key="option.value" :label="option.label" :value="option.value" />
          </el-option-group>
        </el-select>
      </span>
    </div>

    <!-- 绘图区域 -->
    <div class="sketch-container">
      <div class="canvas-container">
        <!-- 使用canvas替代SVG作为Paper.js的绘图区域 -->
        <canvas ref="paperCanvas" id="paperCanvas" class="whiteboard-canvas" resize></canvas>
        <div class="segment-info" v-if="segmentInfo">{{ segmentInfo }}</div>
        <div class="buttons">
          <el-button type="danger" class="clear-button" @click="clearCanvas">
            清除
          </el-button>
          <el-button type="primary" :icon="Search" @click="submitData" class="search-button">
            查询
          </el-button>
        </div>
        <div class="zoom-button">
          <el-button type="primary" :icon="FullScreen" circle @click="openFullscreenCanvas"></el-button>
        </div>
      </div>
    </div>

    <!-- 全屏绘图弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      width="90%"
      :show-close="false"
      fullscreen
      :destroy-on-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="true"
    >
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
          <el-button type="danger" @click="clearFullscreenCanvas">
            清除
          </el-button>
          <el-button type="primary" @click="applyFullscreenDrawing">
            应用
          </el-button>
        </div>
      </div>
    </el-dialog>
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
import { Search, FullScreen } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';
import { useStore } from 'vuex';
import Paper from 'paper';

// 在导入Paper.js后立即添加猴子补丁，修改原生addEventListener方法
// 这个补丁会确保所有的touchstart事件都是passive的
(function patchAddEventListener() {
  // 保存原始方法
  const originalAddEventListener = EventTarget.prototype.addEventListener;
  
  // 替换为我们的修改版本
  EventTarget.prototype.addEventListener = function(type, listener, options) {
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
Paper.DomEvent.add = function(element, events, handler) {
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
const sampling = computed(() => store.state.sampling);

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
    // 如果正在清除过程中，忽略鼠标按下事件
    if (isClearing.value) return;
    
    selectedSegment = null;
    selectedHandle = null;

    // 检查是否点击了现有路径上的段点或手柄
    if (path) {
      const hitResult = path.hitTest(event.point, hitOptions);
      if (hitResult) {
        if (hitResult.type === 'segment') {
          selectedSegment = hitResult.segment;
          return;
        } else if (hitResult.type === 'handle-in' || hitResult.type === 'handle-out') {
          selectedHandle = hitResult;
          return;
        }
      }
    }

    // 如果已有路径，先清除它
    if (path) {
      path.remove();
      path = null;
      segmentInfo.value = '';
      store.dispatch('updateMatchedResults', []);
    }

    // 创建新路径
    path = new paperScope.Path({
      segments: [event.point],
      strokeColor: 'black',
      strokeWidth: 2,
      strokeCap: 'round',
      strokeJoin: 'round'
    });
  };

  // 鼠标拖动事件
  tool.onMouseDrag = (event) => {
    // 如果正在拖动段点
    if (selectedSegment) {
      selectedSegment.point = selectedSegment.point.add(event.delta);
      return;
    }

    // 如果正在拖动手柄
    if (selectedHandle) {
      if (selectedHandle.type === 'handle-in') {
        selectedHandle.segment.handleIn = selectedHandle.segment.handleIn.add(event.delta);
      } else if (selectedHandle.type === 'handle-out') {
        selectedHandle.segment.handleOut = selectedHandle.segment.handleOut.add(event.delta);
      }
      return;
    }

    // 否则绘制新路径
    if (path && (!path.lastSegment || event.point.x >= path.lastSegment.point.x)) {
      path.add(event.point);
      segmentInfo.value = `点数: ${path.segments.length}`;
    }
  };

  // 鼠标释放事件
  tool.onMouseUp = (event) => {
    // 如果是在拖动段点或手柄，不进行简化操作
    if (selectedSegment || selectedHandle) {
      selectedSegment = null;
      selectedHandle = null;
      return;
    }

    if (path && path.segments.length > 1) {
      const segmentCount = path.segments.length;

      // 只有在绘制新路径时才简化路径
      if (!path.fullySelected) {
        path.simplify(10);

        // 设置路径为选中状态，显示控制点和手柄
        path.fullySelected = true;

        const newSegmentCount = path.segments.length;
        const difference = segmentCount - newSegmentCount;
        const percentage = 100 - Math.round(newSegmentCount / segmentCount * 100);

        segmentInfo.value = `简化前点数: ${segmentCount}, 简化后点数: ${newSegmentCount}, 减少: ${percentage}%`;
      }
    }
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

      // 发送请求到后端
      const response = await fetch('https://10.1.108.231:5000/api/sketch-query/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          rawQueryPattern,
          // sampling: sampling.value,
          sampling: 1,
          selectedChannels
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
  // 设置清除状态为true
  isClearing.value = true;
  
  // 清除匹配结果
  store.dispatch('clearMatchedResults');
  
  // 立即清除路径
  if (paperScope) {
    if (path) {
      path.remove();
      path = null;
    }
    segmentInfo.value = '';
  }
  
  // 使用requestAnimationFrame确保UI更新完成后再允许新绘制
  requestAnimationFrame(() => {
    // 延迟一帧后再设置为false，确保清除操作和UI更新完成
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
    const passiveTouchHandler = () => {};
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

// 打开全屏绘图弹窗
const openFullscreenCanvas = () => {
  dialogVisible.value = true;
  
  // 弹窗打开后初始化全屏绘图区域
  setTimeout(() => {
    initFullscreenPaper();
    
    // 给全屏canvas元素添加passive触摸事件处理
    if (fullscreenCanvas.value) {
      const passiveTouchHandler = () => {};
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

  // 确保Paper.js还没有初始化
  if (fullscreenPaperScope) {
    fullscreenPaperScope.remove();
  }

  // 初始化Paper.js
  fullscreenPaperScope = new Paper.PaperScope();
  
  fullscreenPaperScope.setup(fullscreenCanvas.value);

  // 创建网格
  createFullscreenGrid(fullscreenCanvas.value.offsetWidth, fullscreenCanvas.value.offsetHeight);

  // 设置工具事件
  const tool = new fullscreenPaperScope.Tool();

  // 将selectedSegment和selectedHandle提升到函数作用域顶部
  let selectedSegment = null;
  let selectedHandle = null;

  // 鼠标按下事件
  tool.onMouseDown = (event) => {
    selectedSegment = null;
    selectedHandle = null;

    // 检查是否点击了现有路径上的段点或手柄
    if (fullscreenPath) {
      const hitResult = fullscreenPath.hitTest(event.point, hitOptions);
      if (hitResult) {
        if (hitResult.type === 'segment') {
          selectedSegment = hitResult.segment;
          return;
        } else if (hitResult.type === 'handle-in' || hitResult.type === 'handle-out') {
          selectedHandle = hitResult;
          return;
        }
      }
    }

    // 如果已有路径，先清除它
    if (fullscreenPath) {
      fullscreenPath.remove();
      fullscreenPath = null;
      segmentInfo.value = '';
    }

    // 创建新路径
    fullscreenPath = new fullscreenPaperScope.Path({
      segments: [event.point],
      strokeColor: 'black',
      strokeWidth: 2,
      strokeCap: 'round',
      strokeJoin: 'round'
    });
  };

  // 鼠标拖动事件
  tool.onMouseDrag = (event) => {
    // 如果正在拖动段点
    if (selectedSegment) {
      selectedSegment.point = selectedSegment.point.add(event.delta);
      return;
    }

    // 如果正在拖动手柄
    if (selectedHandle) {
      if (selectedHandle.type === 'handle-in') {
        selectedHandle.segment.handleIn = selectedHandle.segment.handleIn.add(event.delta);
      } else if (selectedHandle.type === 'handle-out') {
        selectedHandle.segment.handleOut = selectedHandle.segment.handleOut.add(event.delta);
      }
      return;
    }

    // 否则绘制新路径
    if (fullscreenPath && (!fullscreenPath.lastSegment || event.point.x >= fullscreenPath.lastSegment.point.x)) {
      fullscreenPath.add(event.point);
      segmentInfo.value = `点数: ${fullscreenPath.segments.length}`;
    }
  };

  // 鼠标释放事件
  tool.onMouseUp = (event) => {
    // 如果是在拖动段点或手柄，不进行简化操作
    if (selectedSegment || selectedHandle) {
      selectedSegment = null;
      selectedHandle = null;
      return;
    }

    if (fullscreenPath && fullscreenPath.segments.length > 1) {
      const segmentCount = fullscreenPath.segments.length;

      // 只有在绘制新路径时才简化路径
      if (!fullscreenPath.fullySelected) {
        fullscreenPath.simplify(10);

        // 设置路径为选中状态，显示控制点和手柄
        fullscreenPath.fullySelected = true;

        const newSegmentCount = fullscreenPath.segments.length;
        const difference = segmentCount - newSegmentCount;
        const percentage = 100 - Math.round(newSegmentCount / segmentCount * 100);

        segmentInfo.value = `简化前点数: ${segmentCount}, 简化后点数: ${newSegmentCount}, 减少: ${percentage}%`;
      }
    }
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
    strokeJoin: 'round',
    fullySelected: true
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
    strokeJoin: 'round',
    fullySelected: true
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
  }
};

// 关闭全屏绘图弹窗
const closeFullscreenCanvas = () => {
  dialogVisible.value = false;
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
  bottom: 6px;
  right: 6px;
}

.title {
  color: #333;
  font-weight: bold;
  font-size: 12pt;
  margin-left: 5px;
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
  height: calc(100vh - 120px);
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

.custom-dialog-header .title {
  font-size: 16px;
  font-weight: bold;
  margin-left: 0;
}

.exit-fullscreen-btn {
  margin-left: auto;
  font-size: 14px;
}
</style>
