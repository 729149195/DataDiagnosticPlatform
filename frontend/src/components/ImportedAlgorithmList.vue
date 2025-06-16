<template>
  <div class="imported-algorithm-list">
    <!-- 算法树形结构 -->
    <div class="algorithm-tree">
      <el-tree 
        :data="treeData" 
        :props="treeProps" 
        :expand-on-click-node="true" 
        :default-expanded-keys="expandedKeys"
        node-key="id" 
        class="algorithm-tree-component" 
        @node-expand="handleNodeExpand"
        @node-collapse="handleNodeCollapse" 
        @node-click="handleNodeClick">
        <template #default="{ data }">
          <div class="tree-node">
            <!-- 算法节点 -->
            <div v-if="data.type === 'algorithm'" class="algorithm-node">
              <div class="algorithm-info">
                <el-icon class="node-icon algorithm-icon">
                  <Document />
                </el-icon>
                <el-tag size="small" :class="getCategoryTagClass(data.category)">
                  {{ getCategoryDisplayName(data.category) }}
                </el-tag>
                <span class="node-label">{{ data.algorithmName }}</span>
                <el-tag size="small" type="info" class="file-type-tag">
                  {{ data.fileType }}
                </el-tag>
              </div>
              <el-button 
                v-if="data.category === '诊断分析'"
                size="small" 
                type="success" 
                class="add-to-detection-btn"
                @click.stop="addToAnomalyDetection(data)">
                加入异常检测方法
              </el-button>
            </div>

            <!-- 算法详情区域 -->
            <div v-else-if="data.type === 'details'" class="algorithm-details">
              <div class="details-header">
                <el-icon class="node-icon">
                  <InfoFilled />
                </el-icon>
                <span class="details-label">算法详情</span>
              </div>
              <div class="details-content-vertical">
                
                <!-- 描述单独一行 -->
                <div class="description-row">
                  <span class="desc-label">描述：</span>
                  <span class="desc-value">{{ data.description || '暂无描述' }}</span>
                </div>
                
                <!-- 参数横向布局 -->
                <div class="params-row">
                  <!-- 输入参数 -->
                  <div class="param-section" v-if="data.inputParams && data.inputParams.length > 0">
                    <div class="section-title">输入参数：</div>
                    <div class="params-grid">
                      <div v-for="param in data.inputParams" :key="param.paraName" class="param-item-compact">
                        <el-tag size="small" type="primary">{{ param.paraName }}</el-tag>
                        <span class="param-type">({{ param.paraType }})</span>
                        <span v-if="param.paraDefinition" class="param-definition">{{ param.paraDefinition }}</span>
                      </div>
                    </div>
                  </div>
                  
                  <!-- 输出参数 -->
                  <div class="param-section" v-if="data.outputParams && data.outputParams.length > 0">
                    <div class="section-title">输出参数：</div>
                    <div class="params-grid">
                      <div v-for="param in data.outputParams" :key="param.outputName" class="param-item-compact">
                        <el-tag size="small" type="success">{{ param.outputName }}</el-tag>
                        <span class="param-type">({{ param.type }})</span>
                        <span v-if="param.definition" class="param-definition">{{ param.definition }}</span>
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
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { Document, InfoFilled } from '@element-plus/icons-vue';

// 响应式数据
const treeData = ref([]);
const treeProps = {
  children: 'children',
  label: 'label'
};

// 树形展开控制
const expandedKeys = ref([]);

// 获取分类显示名称
const getCategoryDisplayName = (category) => {
  const categoryMap = {
    '通道运算': '运算函数',
    '诊断分析': '诊断函数'
  };
  return categoryMap[category] || category;
};

// 获取分类标签样式类
const getCategoryTagClass = (category) => {
  const classMap = {
    '通道运算': 'function-tag',
    '诊断分析': 'diagnosis-tag'
  };
  return classMap[category] || 'default-tag';
};

// 获取文件类型标识
const getFileTypeLabel = (filePath) => {
  if (filePath && filePath.endsWith('.py')) {
    return 'Python';
  } else if (filePath && filePath.endsWith('.m')) {
    return 'MATLAB';
  }
  return '';
};

// 更新树形数据结构
const updateTreeData = (data) => {
  const tree = [];

  if (!data || !Array.isArray(data.imported_functions)) {
    treeData.value = tree;
    return;
  }

  data.imported_functions.forEach((func, index) => {
    const fileType = getFileTypeLabel(func.file_path);
    
    const algorithmNode = {
      id: `algorithm-${func.type}-${func.name}-${index}`,
      label: func.name,
      type: 'algorithm',
      category: func.type,
      algorithmName: func.name,
      fileType: fileType,
      children: []
    };

    // 添加详情节点
    const detailsNode = {
      id: `details-${func.type}-${func.name}-${index}`,
      label: '算法详情',
      type: 'details',
      description: func.description,
      inputParams: func.input || [],
      outputParams: func.output || []
    };
    
    algorithmNode.children.push(detailsNode);
    tree.push(algorithmNode);
  });

  treeData.value = tree;
};

// 展开控制
const handleNodeExpand = (data) => {
  if (data.type === 'algorithm') {
    expandedKeys.value = [data.id];
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
    }
  }
};

// 添加到异常检测方法
const addToAnomalyDetection = (data) => {
  console.log('添加算法到异常检测方法:', data);
  // TODO: 实现添加到异常检测方法的逻辑
  // 可以触发事件或调用父组件方法
};

// 加载导入的算法数据
const loadImportedAlgorithms = async () => {
  try {
    const response = await fetch('http://192.168.20.49:5000/api/view-functions');
    if (response.ok) {
      const result = await response.json();
      updateTreeData(result);
    } else {
      console.error('Failed to load imported algorithms: HTTP', response.status);
      treeData.value = [];
    }
  } catch (error) {
    console.error('Error loading imported algorithms:', error);
    treeData.value = [];
  }
};

onMounted(() => {
  loadImportedAlgorithms();
  
  // 监听函数上传和删除事件，自动刷新列表
  window.addEventListener('functionUploaded', loadImportedAlgorithms);
  window.addEventListener('functionDeleted', loadImportedAlgorithms);
});
</script>

<style scoped lang="scss">
.imported-algorithm-list {
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

.algorithm-tree {
  flex: 1;
  overflow: auto;
}

.algorithm-tree-component {
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

.algorithm-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.algorithm-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
}

.node-icon {
  margin-right: 0;
}

.algorithm-icon {
  color: #67c23a;
}

.node-label {
  flex: 1;
  font-weight: 500;
  margin-left: 0;
}

// 分类标签样式
.function-tag {
  background-color: #67c23a;
  border-color: #67c23a;
  color: white;
  font-size: 12px;
  flex-shrink: 0;
}

.diagnosis-tag {
  background-color: #529b2e;
  border-color: #529b2e;
  color: white;
  font-size: 12px;
  flex-shrink: 0;
}

.default-tag {
  background-color: #85ce61;
  border-color: #85ce61;
  color: white;
  font-size: 12px;
  flex-shrink: 0;
}

.file-type-tag {
  font-size: 11px;
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
    box-shadow: 0 2px 4px rgba(64, 158, 255, 0.3);
  }
}

// 算法详情样式
.algorithm-details {
  width: 100%;
  margin-top: 8px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e9ecef;
  box-sizing: border-box;
  overflow: hidden;
}

.details-header {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  gap: 8px;
}

.details-label {
  font-size: 15px;
  color: #606266;
  font-weight: 500;
}

.details-content-vertical {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

// 描述行样式
.description-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.desc-label {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
}

.desc-value {
  font-size: 14px;
  color: #606266;
  line-height: 1.4;
  flex: 1;
}

// 参数横向布局
.params-row {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}

.param-section {
  flex: 1;
  min-width: 0;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}

.params-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.param-item-compact {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 13px;
}

.param-type {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.param-definition {
  font-size: 12px;
  color: #606266;
  font-style: italic;
  word-break: break-word;
}

// 展开动画
:deep(.el-tree-node__children) {
  transition: all 0.3s ease;
}
</style> 