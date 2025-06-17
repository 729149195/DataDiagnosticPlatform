<template>
  <div class="sketch-template-list">
    <!-- 模板树形结构 -->
    <div class="template-tree">
      <el-tree :data="treeData" :props="treeProps" :expand-on-click-node="true" :default-expanded-keys="expandedKeys" node-key="id" class="template-tree-component" @node-expand="handleNodeExpand" @node-collapse="handleNodeCollapse" @node-click="handleNodeClick">
        <template #default="{ data }">
          <div class="tree-node">
            <!-- 模板节点 -->
            <div v-if="data.type === 'template'" class="template-node">
              <div class="template-info">
                <el-icon class="node-icon template-icon">
                  <Brush />
                </el-icon>
                <el-tag size="small" type="warning" class="template-tag">
                  手绘模板
                </el-tag>
                <span class="node-label">{{ data.templateName }}</span>
              </div>
              <el-button 
                size="small" 
                type="warning" 
                class="add-to-detection-btn"
                @click.stop="addToAnomalyDetection(data)">
                加入异常检测方法
              </el-button>
            </div>

            <!-- 模板详情区域 -->
            <div v-else-if="data.type === 'details'" class="template-details">
              <div class="details-header">
                <el-icon class="node-icon">
                  <InfoFilled />
                </el-icon>
                <span class="details-label">模板详情</span>
              </div>
              <div class="details-content-vertical">

                <!-- 描述单独一行 -->
                <div class="description-row">
                  <span class="desc-label">描述：</span>
                  <span class="desc-value">{{ data.description || '暂无描述' }}</span>
                </div>
                <!-- 曲线预览和参数 -->
                <div class="main-content-row">
                  <!-- 左侧：曲线预览 -->
                  <div class="preview-section">
                    <canvas :ref="el => setCurveCanvasRef(el, data.templateId)" class="curve-preview-canvas" width="160" height="90">
                    </canvas>
                  </div>

                  <!-- 右侧：参数信息 -->
                  <div class="params-section">
                    <!-- 参数网格 -->
                    <div class="params-grid-compact">
                      <!-- 查找范围 -->
                      <div class="param-group">
                        <span class="group-title">查找范围</span>
                        <div class="param-item-compact">
                          <span class="param-name">时间：</span>
                          <span class="param-value">
                            <span v-if="data.parameters?.xFilterRange && data.parameters.xFilterRange[0] !== null">
                              {{ data.parameters.xFilterRange[0] }}~{{ data.parameters.xFilterRange[1] }}s
                            </span>
                            <span v-else class="no-limit">--</span>
                          </span>
                        </div>
                        <div class="param-item-compact">
                          <span class="param-name">数值：</span>
                          <span class="param-value">
                            <span v-if="data.parameters?.yFilterRange && data.parameters.yFilterRange[0] !== null">
                              {{ data.parameters.yFilterRange[0] }}~{{ data.parameters.yFilterRange[1] }}
                            </span>
                            <span v-else class="no-limit">--</span>
                          </span>
                        </div>
                      </div>

                      <!-- 匹配方法 -->
                      <div class="param-group">
                        <span class="group-title">匹配方法</span>
                        <div class="param-item-compact filter-item">
                          <span class="param-name">滤波：</span>
                          <span class="param-value multiline">{{ data.parameters?.lowpassAmplitude || '--' }}s</span>
                        </div>
                        <div class="param-item-compact">
                          <span class="param-name">上限：</span>
                          <span class="param-value">{{ data.parameters?.maxMatchPerChannel || '--' }}</span>
                        </div>
                      </div>

                      <!-- 目标模式 -->
                      <div class="param-group">
                        <span class="group-title">目标模式</span>
                        <div class="param-item-compact">
                          <span class="param-name">重复：</span>
                          <span class="param-value">{{ data.parameters?.patternRepeatCount || 0 }}</span>
                        </div>
                        <div class="param-item-compact">
                          <span class="param-name">幅度：</span>
                          <span class="param-value">
                            <span v-if="data.parameters?.amplitudeLimit !== null && data.parameters?.amplitudeLimit !== undefined">
                              {{ data.parameters.amplitudeLimit }}
                            </span>
                            <span v-else class="no-limit">--</span>
                          </span>
                        </div>
                        <div class="param-item-compact">
                          <span class="param-name">跨度：</span>
                          <span class="param-value">
                            <span v-if="data.parameters?.timeSpanLimit !== null && data.parameters?.timeSpanLimit !== undefined">
                              {{ data.parameters.timeSpanLimit }}
                            </span>
                            <span v-else class="no-limit">--</span>
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>


              </div>
            </div>
          </div>
        </template>
      </el-tree>
    </div>
  </div>
  
  <!-- 导入模板对话框 -->
  <el-dialog v-model="importDialogVisible" title="导入到异常检测方法" width="500px" :close-on-click-modal="false">
    <el-form :model="importForm" label-width="100px">
      <el-form-item label="模板名称">
        <el-input v-model="importForm.templateName" placeholder="模板名称" disabled />
      </el-form-item>
      <el-form-item label="检测类别">
        <el-select 
          v-model="importForm.selectedCategory" 
          placeholder="请选择现有类别或输入新类别" 
          allow-create 
          filterable
          style="width: 100%">
          <el-option v-for="category in existingCategories" :key="category" :label="category" :value="category" />
        </el-select>
        <div style="margin-top: 8px;">
          <el-input 
            v-model="importForm.categoryName" 
            placeholder="或输入新的类别名称"
            :disabled="!!importForm.selectedCategory" />
        </div>
      </el-form-item>
    </el-form>
    <template #footer>
      <span class="dialog-footer">
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmImport">确定导入</el-button>
      </span>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { Brush, InfoFilled } from '@element-plus/icons-vue';
import { ElMessage } from 'element-plus';

// 响应式数据
const treeData = ref([]);
const treeProps = {
  children: 'children',
  label: 'label'
};

// 树形展开控制
const expandedKeys = ref([]);

// 曲线画布引用
const curveCanvasRefs = ref({});

// 更新树形数据结构
const updateTreeData = (data) => {
  const tree = [];

  if (!data || !Array.isArray(data.templates)) {
    treeData.value = tree;
    return;
  }

  data.templates.forEach((template, index) => {
    const templateNode = {
      id: `template-${template.template_name}-${index}`,
      label: template.template_name,
      type: 'template',
      templateName: template.template_name,
      templateId: `${template.template_name}-${index}`,
      children: []
    };

    // 添加详情节点
    const detailsNode = {
      id: `details-${template.template_name}-${index}`,
      label: '模板详情',
      type: 'details',
      templateId: `${template.template_name}-${index}`,
      description: template.description,
      parameters: template.parameters || {},
      rawQueryPattern: template.raw_query_pattern || []
    };

    templateNode.children.push(detailsNode);
    tree.push(templateNode);
  });

  treeData.value = tree;
};

// 展开控制
const handleNodeExpand = (data) => {
  if (data.type === 'template') {
    expandedKeys.value = [data.id];
    // 展开时绘制曲线预览
    setTimeout(() => {
      const detailsNode = data.children[0];
      if (detailsNode && detailsNode.rawQueryPattern) {
        drawCurvePreview(detailsNode.rawQueryPattern, detailsNode.templateId);
      }
    }, 100);
  }
};

const handleNodeCollapse = (data) => {
  const index = expandedKeys.value.indexOf(data.id);
  if (index > -1) {
    expandedKeys.value.splice(index, 1);
  }
};

// 处理节点点击事件
const handleNodeClick = (data) => {
  if (data.children && data.children.length > 0) {
    if (expandedKeys.value.includes(data.id)) {
      const index = expandedKeys.value.indexOf(data.id);
      if (index > -1) {
        expandedKeys.value.splice(index, 1);
      }
    } else {
      expandedKeys.value.push(data.id);
      // 展开时绘制曲线预览
      setTimeout(() => {
        const detailsNode = data.children[0];
        if (detailsNode && detailsNode.rawQueryPattern) {
          drawCurvePreview(detailsNode.rawQueryPattern, detailsNode.templateId);
        }
      }, 100);
    }
  }
};

// 添加到异常检测方法
const addToAnomalyDetection = (data) => {
  console.log('添加手绘模板到异常检测方法:', data);
  
  // 显示导入对话框
  showImportDialog(data);
};

// 导入对话框相关数据
const importDialogVisible = ref(false);
const importForm = ref({
  templateName: '',
  categoryName: '',
  selectedCategory: ''
});
const currentImportData = ref(null);
const existingCategories = ref([]);

// 显示导入对话框
const showImportDialog = async (templateData) => {
  currentImportData.value = templateData;
  importForm.value.templateName = templateData.templateName;
  importForm.value.categoryName = '';
  importForm.value.selectedCategory = '';
  
  // 获取现有类别
  await loadExistingCategories();
  importDialogVisible.value = true;
};

// 加载现有类别
const loadExistingCategories = async () => {
  try {
    const response = await fetch('http://192.168.20.49:5000/api/algorithm-channel-map');
    if (response.ok) {
      const result = await response.json();
      if (result.success) {
        existingCategories.value = Object.keys(result.data || {});
      }
    }
  } catch (error) {
    console.error('加载现有类别失败:', error);
  }
};

// 确认导入
const confirmImport = async () => {
  const categoryName = importForm.value.selectedCategory || importForm.value.categoryName;
  
  if (!categoryName.trim()) {
    ElMessage.warning('请选择或输入类别名称');
    return;
  }
  
  if (!importForm.value.templateName.trim()) {
    ElMessage.warning('模板名称不能为空');
    return;
  }
  
  try {
    const response = await fetch('http://192.168.20.49:5000/api/import-algorithm-to-detection', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        type: 'sketch_template',
        algorithm_name: importForm.value.templateName,
        category_name: categoryName,
        source_data: currentImportData.value
      })
    });
    
    const result = await response.json();
    if (result.success) {
      ElMessage.success('手绘模板已成功加入异常检测方法');
      importDialogVisible.value = false;
      // 触发事件通知父组件刷新
      window.dispatchEvent(new CustomEvent('algorithmImported'));
    } else {
      ElMessage.error(result.message || '导入失败');
    }
  } catch (error) {
    console.error('导入模板失败:', error);
    ElMessage.error('导入失败，请重试');
  }
};

// 设置曲线画布引用
const setCurveCanvasRef = (el, templateId) => {
  if (el) {
    curveCanvasRefs.value[templateId] = el;
  }
};

// 绘制曲线预览
const drawCurvePreview = (rawQueryPattern, templateId) => {
  const canvas = curveCanvasRefs.value[templateId];
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

  // 调整边距适应小画布
  const margin = 6;
  const drawWidth = width - 2 * margin;
  const drawHeight = height - 2 * margin;

  // 绘制曲线，调整线宽适应小画布
  ctx.strokeStyle = '#e6a23c';
  ctx.lineWidth = 1.5;
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

  // 绘制端点，调整点的大小
  ctx.fillStyle = '#e6a23c';
  rawQueryPattern.forEach((point, index) => {
    if (index === 0 || index === rawQueryPattern.length - 1) {
      const x = margin + ((point.x - minX) / xRange) * drawWidth;
      const y = margin + ((maxY - point.y) / yRange) * drawHeight;
      ctx.beginPath();
      ctx.arc(x, y, 2, 0, 2 * Math.PI);
      ctx.fill();
    }
  });
};

// 加载手绘模板数据
const loadSketchTemplates = async () => {
  try {
    const response = await fetch('http://192.168.20.49:5000/api/sketch-templates/list');
    if (response.ok) {
      const result = await response.json();
      updateTreeData(result);
    } else {
      console.error('Failed to load sketch templates: HTTP', response.status);
      treeData.value = [];
    }
  } catch (error) {
    console.error('Error loading sketch templates:', error);
    treeData.value = [];
  }
};

onMounted(() => {
  loadSketchTemplates();
});
</script>

<style scoped lang="scss">
.sketch-template-list {
  height: 100%;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;

  // 全局滚动条样式优化
  * {
    scrollbar-width: thin;
    scrollbar-color: rgba(144, 147, 153, 0.3) transparent;
  }

  *::-webkit-scrollbar {
    width: 6px;
    height: 6px;
    background: transparent;
  }

  *::-webkit-scrollbar-thumb {
    background: rgba(144, 147, 153, 0.3);
    border-radius: 3px;

    &:hover {
      background: rgba(144, 147, 153, 0.5);
    }
  }

  *::-webkit-scrollbar-track {
    background: transparent;
  }

  *::-webkit-scrollbar-corner {
    background: transparent;
  }
}

.template-tree {
  flex: 1;
  overflow: auto;
}

.template-tree-component {
  background: transparent;

  :deep(.el-tree-node__content) {
    height: auto;
    min-height: 32px;
    padding: 4px 0;
  }

  :deep(.el-tree-node__expand-icon) {
    padding: 6px;
  }

  :deep(.el-tree-node__children) {
    overflow: visible;
  }
}

.tree-node {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 0;
}

.template-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.template-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.node-icon {
  margin-right: 0;
}

.template-icon {
  color: #e6a23c;
}

.node-label {
  flex: 1;
  font-weight: 500;
  margin-left: 0;
}

.template-tag {
  background-color: #e6a23c;
  border-color: #e6a23c;
  color: white;
  font-size: 12px;
  flex-shrink: 0;
}

.add-to-detection-btn {
  margin-left: auto;
  flex-shrink: 0;
  font-size: 12px;
  height: 28px;
  padding: 0 12px;
  
  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(230, 162, 60, 0.3);
  }
}

// 模板详情样式
.template-details {
  width: 100%;
  margin-top: 8px;
  padding: 10px;
  background: #fefaf5;
  border-radius: 6px;
  border: 1px solid #f0e6d2;
  box-sizing: border-box;
  overflow: hidden;
}

.details-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
  gap: 6px;
}

.details-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
}

// 垂直布局容器
.details-content-vertical {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

// 主要内容行：曲线和参数
.main-content-row {
  display: flex;
  gap: 12px;
  align-items: stretch;
  height: 110px;
}

// 左侧预览区域
.preview-section {
  flex-shrink: 0;
  display: flex;
  align-items: stretch;
  justify-content: center;
  height: 100%;
  width: 160px;
}

.curve-preview-canvas {
  border: 1px solid #ddd;
  border-radius: 4px;
  background-color: #fafafa;
  cursor: pointer;
  transition: all 0.3s ease;
  width: 160px;
  height: 100%;
}

.curve-preview-canvas:hover {
  border-color: #e6a23c;
  box-shadow: 0 0 4px rgba(230, 162, 60, 0.3);
  transform: scale(1.02);
}

// 右侧参数区域
.params-section {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: stretch;
  height: 100%;
}

// 紧凑参数网格
.params-grid-compact {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  width: 100%;
  height: 100%;
}

.param-group {
  background: rgba(255, 255, 255, 0.6);
  padding: 8px;
  border-radius: 4px;
  border: 1px solid rgba(240, 230, 210, 0.6);
  min-width: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
}

.group-title {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #e6a23c;
  margin-bottom: 6px;
  border-bottom: 1px solid #f0e6d2;
  padding-bottom: 2px;
}

.param-item-compact {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 3px;
  gap: 4px;
  min-height: 18px;
}

.param-item-compact:last-child {
  margin-bottom: 0;
}

.param-name {
  font-size: 13px;
  color: #909399;
  font-weight: 500;
  flex-shrink: 0;
  white-space: nowrap;
  overflow: hidden;
}

.param-value {
  font-size: 13px;
  color: #303133;
  font-weight: 600;
  text-align: right;
  word-break: break-word;
  min-width: 0;
  max-width: 60px;
  overflow-wrap: break-word;
  line-height: 1.2;
}

.param-value.multiline {
  word-break: break-all;
  hyphens: auto;
  max-width: 40px;
  white-space: normal;
  overflow-wrap: anywhere;
}

.filter-item {
  flex-direction: column !important;
  align-items: flex-start !important;
  min-height: 32px !important;
  gap: 2px !important;
}

.filter-item .param-name {
  text-align: left;
}

.filter-item .param-value {
  line-height: 1.1;
  text-align: left;
  max-width: none;
}

// 描述行 - 单独一行
.description-row {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin-top: 0px;
}

.desc-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  flex-shrink: 0;
  min-width: 40px;
}

.desc-value {
  font-size: 14px;
  color: #606266;
  line-height: 1.4;
  word-break: break-word;
}

.no-limit {
  color: #909399;
  font-style: italic;
}

// 展开动画
:deep(.el-tree-node__children) {
  transition: all 0.3s ease;
}
</style>