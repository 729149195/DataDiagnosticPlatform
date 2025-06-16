<template>
  <div class="algorithm-manager">
    <!-- 工具栏 -->
    <!-- <div class="toolbar">
      <el-button type="primary" size="small" @click="showAddAlgorithmDialog()" :icon="Plus">
        添加算法
      </el-button>
      <el-button type="success" size="small" @click="refreshData" :icon="Refresh">
        刷新
      </el-button>
    </div> -->

    <!-- 算法树形结构 -->
    <div class="algorithm-tree">
      <el-tree :data="treeData" :props="treeProps" :expand-on-click-node="true" :default-expanded-keys="expandedKeys"
        node-key="id" class="algorithm-tree-component" @node-expand="handleNodeExpand"
        @node-collapse="handleNodeCollapse" @node-click="handleNodeClick">
        <template #default="{ data }">
          <div class="tree-node">
            <!-- 算法节点 -->
            <div v-if="data.type === 'algorithm'" class="algorithm-node">
              <div class="algorithm-info">
                <el-icon class="node-icon algorithm-icon">
                  <Document />
                </el-icon>
                <el-tag size="small" 
                       :class="['category-tag', { 'category-tag-empty': !hasChannels(data) }]">
                  {{ data.category }}
                </el-tag>
                <span class="node-label" :class="{ 'node-label-empty': !hasChannels(data) }">{{ data.algorithmName }}</span>
              </div>
              <!-- <div class="node-actions">
                <el-button type="danger" size="small" @click.stop="deleteAlgorithm(data)" :icon="Delete">
                  删除算法
                </el-button>
              </div> -->
            </div>

            <!-- 通道标签区域 -->
            <div v-else-if="data.type === 'channels'" class="channels-container">
              <div class="channels-header">
                <el-icon class="node-icon">
                  <Collection />
                </el-icon>
                <span class="channels-label">通道列表 ({{ data.channels.length }})</span>
                <div v-if="data.channels.length > 0" class="channels-actions">
                  <el-checkbox v-model="selectAllChannels[`${data.parentCategory}-${data.parentAlgorithm}`]"
                    @change="handleSelectAllChannels(data)" :indeterminate="isIndeterminate(data)">
                    全选
                  </el-checkbox>
                  <el-button type="danger" size="small" @click="batchDeleteChannels(data)"
                    :disabled="!hasSelectedChannels(data)" :icon="Delete">
                    批量删除
                  </el-button>
                </div>
              </div>
              <div class="channels-content">
                <div class="channels-tags">
                  <el-tag v-for="channel in data.channels" :key="channel" :closable="true"
                    @close="removeChannel(data.parentCategory, data.parentAlgorithm, channel)"
                    @click="toggleChannelSelection(data, channel)" :class="{
                      'channel-tag': true,
                      'selected': isChannelSelected(data, channel)
                    }">
                    {{ channel }}
                  </el-tag>
                  <div v-if="data.channels.length === 0" class="empty-channels-hint">
                    <el-text type="info" size="small">暂无通道，请在下方输入框中添加</el-text>
                  </div>
                </div>
                <div class="channel-input-area">
                  <el-input v-model="newChannelInput[`${data.parentCategory}-${data.parentAlgorithm}`]"
                    placeholder="输入通道名称，按回车添加" size="small" @keyup.enter="addChannelInline(data)"
                    @blur="addChannelInline(data)" class="channel-input">
                    <template #append>
                      <el-button @click="addChannelInline(data)" :icon="Plus" size="small" />
                    </template>
                  </el-input>
                </div>
              </div>
            </div>
          </div>
        </template>
      </el-tree>
    </div>



    <!-- 添加算法对话框 -->
    <el-dialog v-model="addAlgorithmDialogVisible" title="添加算法" width="600px" :close-on-click-modal="false">
      <el-form :model="algorithmForm" label-width="80px">
        <el-form-item label="通道类别">
          <el-select v-model="algorithmForm.category" placeholder="请选择或输入通道类别" allow-create filterable>
            <el-option v-for="category in existingCategories" :key="category" :label="category" :value="category" />
          </el-select>
        </el-form-item>
        <el-form-item label="算法名称">
          <el-input v-model="algorithmForm.name" placeholder="请输入算法名称" maxlength="50" show-word-limit />
        </el-form-item>

        <el-form-item label="算法文件">
          <el-alert title="文件要求" type="info" :closable="false" show-icon class="file-requirement-alert">
            <p>必须同时上传 .mat 和 .py 文件，且文件名必须与算法名称相同</p>
          </el-alert>

          <el-upload ref="algorithmUploadRef" :auto-upload="false" :on-change="handleAlgorithmFileChange"
            :before-remove="handleAlgorithmFileRemove" multiple drag accept=".mat,.py" class="algorithm-upload">
            <el-icon class="el-icon--upload">
              <UploadFilled />
            </el-icon>
            <div class="el-upload__text">
              将算法文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                只能上传 .mat/.py 文件，文件名必须与算法名称一致
              </div>
            </template>
          </el-upload>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="addAlgorithmDialogVisible = false">取消</el-button>
          <el-button type="primary" @click="addAlgorithm">确定</el-button>
        </span>
      </template>
    </el-dialog>




  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import {
  Plus, Refresh, Folder, Document, Collection, Delete, UploadFilled
} from '@element-plus/icons-vue';
import { ElMessage, ElMessageBox } from 'element-plus';

// Props
const props = defineProps({
  algorithmData: {
    type: Object,
    default: () => ({})
  }
});

// Emits
const emit = defineEmits(['refresh-data']);

// 响应式数据
const treeData = ref([]);
const treeProps = {
  children: 'children',
  label: 'label'
};

// 对话框控制
const addAlgorithmDialogVisible = ref(false);

// 表单数据
const algorithmForm = ref({ name: '', category: '' });

// 当前操作的数据
const uploadFiles = ref([]);

// 树形展开控制
const expandedKeys = ref([]);

// 通道选择状态
const selectedChannels = ref({});
const selectAllChannels = ref({});
const newChannelInput = ref({});

// 现有类别列表
const existingCategories = ref([]);

// 更新树形数据结构 - 修改为平铺的算法列表
const updateTreeData = (data) => {
  const tree = [];

  // 安全检查
  if (!data || typeof data !== 'object') {
    treeData.value = tree;
    return;
  }

  Object.keys(data).forEach(categoryKey => {
    const algorithms = data[categoryKey];
    if (!algorithms || typeof algorithms !== 'object') {
      return;
    }

    Object.keys(algorithms).forEach(algorithmKey => {
      const algorithmNode = {
        id: `algorithm-${categoryKey}-${algorithmKey}`,
        label: algorithmKey,  // 只显示算法名
        type: 'algorithm',
        category: categoryKey,
        algorithmName: algorithmKey,
        key: algorithmKey,
        children: []
      };

      // 总是为算法添加通道列表节点，即使没有通道也要显示输入框
      const channels = algorithms[algorithmKey] || [];
      const channelsNode = {
        id: `channels-${categoryKey}-${algorithmKey}`,
        label: '通道列表',
        type: 'channels',
        channels: channels,
        parentCategory: categoryKey,
        parentAlgorithm: algorithmKey
      };
      algorithmNode.children.push(channelsNode);

      tree.push(algorithmNode);
    });
  });

  treeData.value = tree;
  
  // 更新现有类别列表
  existingCategories.value = Object.keys(data || {});
};

// 监听算法数据变化，更新树形结构
watch(() => props.algorithmData, (newData) => {
  if (newData && typeof newData === 'object') {
    updateTreeData(newData);
  }
}, { immediate: true, deep: true });

// 展开控制
const handleNodeExpand = (data) => {
  // 对于算法节点，只展开当前节点
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
  // 只对有子节点的节点进行展开/折叠操作
  if (data.children && data.children.length > 0) {
    if (expandedKeys.value.includes(data.id)) {
      // 收起节点
      const index = expandedKeys.value.indexOf(data.id);
      if (index > -1) {
        expandedKeys.value.splice(index, 1);
      }
    } else {
      // 展开节点 - 不使用手风琴模式，允许多个节点同时展开
      expandedKeys.value.push(data.id);
    }
  }
};

// 通道选择管理
const getChannelKey = (data) => `${data.parentCategory}-${data.parentAlgorithm}`;

const isChannelSelected = (data, channel) => {
  const key = getChannelKey(data);
  return selectedChannels.value[key]?.includes(channel) || false;
};

const toggleChannelSelection = (data, channel) => {
  const key = getChannelKey(data);
  if (!selectedChannels.value[key]) {
    selectedChannels.value[key] = [];
  }

  const index = selectedChannels.value[key].indexOf(channel);
  if (index > -1) {
    selectedChannels.value[key].splice(index, 1);
  } else {
    selectedChannels.value[key].push(channel);
  }

  // 更新全选状态
  updateSelectAllState(data);
};

const handleSelectAllChannels = (data) => {
  const key = getChannelKey(data);
  const isSelectAll = selectAllChannels.value[key];

  if (isSelectAll) {
    selectedChannels.value[key] = [...data.channels];
  } else {
    selectedChannels.value[key] = [];
  }
};

const updateSelectAllState = (data) => {
  const key = getChannelKey(data);
  const selectedCount = selectedChannels.value[key]?.length || 0;
  const totalCount = data.channels.length;

  selectAllChannels.value[key] = selectedCount === totalCount && totalCount > 0;
};

const isIndeterminate = (data) => {
  const key = getChannelKey(data);
  const selectedCount = selectedChannels.value[key]?.length || 0;
  const totalCount = data.channels.length;

  return selectedCount > 0 && selectedCount < totalCount;
};

const hasSelectedChannels = (data) => {
  const key = getChannelKey(data);
  return (selectedChannels.value[key]?.length || 0) > 0;
};

// 判断算法是否有通道
const hasChannels = (algorithmData) => {
  if (algorithmData.type !== 'algorithm' || !algorithmData.children || algorithmData.children.length === 0) {
    return false;
  }
  
  const channelsNode = algorithmData.children.find(child => child.type === 'channels');
  return channelsNode && channelsNode.channels && channelsNode.channels.length > 0;
};

// 内联添加通道
const addChannelInline = async (data) => {
  const key = getChannelKey(data);
  const channelName = newChannelInput.value[key]?.trim();

  if (!channelName) return;

  try {
    const response = await fetch('http://192.168.20.49:5000/api/algorithm-channel-channels', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        category_name: data.parentCategory,
        algorithm_name: data.parentAlgorithm,
        channel_names: [channelName]
      })
    });

    const result = await response.json();
    if (result.success) {
      newChannelInput.value[key] = '';
      emit('refresh-data');
    } else {
      ElMessage.error(result.message || '添加失败');
    }
  } catch (error) {
    console.error('添加通道失败:', error);
    ElMessage.error('添加失败，请重试');
  }
};

// 批量删除通道
const batchDeleteChannels = async (data) => {
  const key = getChannelKey(data);
  const channelsToDelete = selectedChannels.value[key] || [];

  if (channelsToDelete.length === 0) return;

  try {
    for (const channel of channelsToDelete) {
      const response = await fetch(`http://192.168.20.49:5000/api/algorithm-channel-channels/${data.parentCategory}/${data.parentAlgorithm}/${channel}`, {
        method: 'DELETE'
      });

      if (!response.ok) {
        throw new Error(`Failed to delete channel: ${channel}`);
      }
    }

    ElMessage.success(`成功删除 ${channelsToDelete.length} 个通道`);
    selectedChannels.value[key] = [];
    selectAllChannels.value[key] = false;
    emit('refresh-data');
  } catch (error) {
    console.error('批量删除通道失败:', error);
    ElMessage.error('删除失败，请重试');
  }
};

// 刷新数据
const refreshData = () => {
  emit('refresh-data');
};

// 显示添加算法对话框
const showAddAlgorithmDialog = (algorithmData = null) => {
  algorithmForm.value = { name: '', category: algorithmData?.category || '' };
  addAlgorithmDialogVisible.value = true;
};





// 算法文件处理
const handleAlgorithmFileChange = (_file, fileList) => {
  uploadFiles.value = fileList;
};

const handleAlgorithmFileRemove = (_file, fileList) => {
  uploadFiles.value = fileList;
};

// 添加算法（包含文件上传）
const addAlgorithm = async () => {
  const algorithmName = algorithmForm.value.name.trim();
  const categoryName = algorithmForm.value.category.trim();

  if (!categoryName) {
    ElMessage.warning('请选择或输入通道类别');
    return;
  }

  if (!algorithmName) {
    ElMessage.warning('请输入算法名称');
    return;
  }

  // 验证文件
  if (uploadFiles.value.length === 0) {
    ElMessage.warning('请上传算法文件');
    return;
  }

  const matFiles = uploadFiles.value.filter(file => file.name.endsWith('.mat'));
  const pyFiles = uploadFiles.value.filter(file => file.name.endsWith('.py'));

  if (matFiles.length === 0 || pyFiles.length === 0) {
    ElMessage.warning('请同时上传 .mat 和 .py 文件');
    return;
  }

  if (matFiles.length !== 1 || pyFiles.length !== 1) {
    ElMessage.warning('只能上传一个 .mat 文件和一个 .py 文件');
    return;
  }

  const matFileName = matFiles[0].name.replace('.mat', '');
  const pyFileName = pyFiles[0].name.replace('.py', '');

  if (matFileName !== pyFileName) {
    ElMessage.warning('.mat 和 .py 文件名必须相同');
    return;
  }

  if (matFileName !== algorithmName) {
    ElMessage.warning('文件名必须与算法名称一致');
    return;
  }

  try {
    // 首先创建算法条目
    const createResponse = await fetch('http://192.168.20.49:5000/api/algorithm-channel-algorithm', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        category_name: categoryName,
        algorithm_name: algorithmName
      })
    });

    const createResult = await createResponse.json();
    if (!createResult.success) {
      ElMessage.error(createResult.message || '创建算法失败');
      return;
    }

    // 然后上传文件
    const formData = new FormData();
    formData.append('category', categoryName);
    formData.append('algorithm', algorithmName);
    formData.append('mat_file', matFiles[0].raw);
    formData.append('py_file', pyFiles[0].raw);

    const uploadResponse = await fetch('http://192.168.20.49:5000/api/algorithm-upload-files', {
      method: 'POST',
      body: formData
    });

    const uploadResult = await uploadResponse.json();
    if (uploadResult.success) {
      ElMessage.success('算法创建成功');
      addAlgorithmDialogVisible.value = false;
      algorithmForm.value = { name: '', category: '' };
      uploadFiles.value = [];
      emit('refresh-data');
    } else {
      // 如果文件上传失败，删除已创建的算法条目
      await fetch(`http://192.168.20.49:5000/api/algorithm-channel-algorithm/${categoryName}/${algorithmName}`, {
        method: 'DELETE'
      });
      ElMessage.error(uploadResult.message || '文件上传失败');
    }
  } catch (error) {
    console.error('添加算法失败:', error);
    ElMessage.error('添加失败，请重试');
  }
};





// 删除算法
const deleteAlgorithm = async (algorithmData) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除算法 "${algorithmData.label}" 吗？这将删除相关的算法文件。`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    const response = await fetch(`http://192.168.20.49:5000/api/algorithm-channel-algorithm/${algorithmData.category}/${algorithmData.key}`, {
      method: 'DELETE'
    });

    const result = await response.json();
    if (result.success) {
      ElMessage.success('算法删除成功');
      emit('refresh-data');
    } else {
      ElMessage.error(result.message || '删除失败');
    }
  } catch (error) {
    if (error === 'cancel') return;
    console.error('删除算法失败:', error);
    ElMessage.error('删除失败，请重试');
  }
};

// 删除通道
const removeChannel = async (category, algorithm, channelName) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除通道 "${channelName}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    );

    const response = await fetch(`http://192.168.20.49:5000/api/algorithm-channel-channels/${category}/${algorithm}/${channelName}`, {
      method: 'DELETE'
    });

    const result = await response.json();
    if (result.success) {
      ElMessage.success('通道删除成功');
      emit('refresh-data');
    } else {
      ElMessage.error(result.message || '删除失败');
    }
  } catch (error) {
    if (error === 'cancel') return;
    console.error('删除通道失败:', error);
    ElMessage.error('删除失败，请重试');
  }
};




</script>

<style scoped lang="scss">
.algorithm-manager {
  height: 100%;
  display: flex;
  flex-direction: column;
  /* 确保整个组件的滚动条不挤压布局 */
  box-sizing: border-box;

  /* 全局滚动条样式优化 */
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

.toolbar {
  margin-bottom: 16px;
  display: flex;
  gap: 8px;
}

.algorithm-tree {
  flex: 1;
  overflow: auto;
}

.algorithm-tree-component {
  background: transparent;
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

.category-tag {
  background-color: #409eff;
  border-color: #409eff;
  color: white;
  font-size: 12px;
  flex-shrink: 0;
  
  &.category-tag-empty {
    background-color: #c0c4cc;
    border-color: #c0c4cc;
    color: #909399;
  }
}

.node-label {
  flex: 1;
  font-weight: 500;
  margin-left: 0;
  
  &.node-label-empty {
    color: #909399;
  }
}

.node-actions {
  display: flex;
  gap: 4px;
}

/* 通道容器样式已在文件末尾统一定义 */

.channels-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.channels-label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

/* 通道标签样式已在下方统一定义 */

.channel-tag {
  margin: 0;
}

.empty-tag {
  margin: 0;
}

.upload-section {
  .el-alert {
    margin-bottom: 16px;
  }
}

.file-upload-area {
  margin-top: 16px;
}

.form-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
}

/* 通道管理样式 */
.channels-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.channels-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.channels-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.channels-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  min-height: 32px;
  max-height: 200px;
  overflow-x: hidden;
  overflow-y: auto;
}

.empty-channels-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  padding: 8px;
  background: #f5f7fa;
  border: 1px dashed #dcdfe6;
  border-radius: 4px;
  margin-bottom: 8px;
}

.channel-tag {
  margin: 0;
  cursor: pointer;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  &.selected {
    background-color: #409eff;
    color: white;
    border-color: #409eff;
  }
}

.channel-input-area {
  margin-top: 8px;
}

.channel-input {
  max-width: 300px;
}

/* 算法上传样式 */
.file-requirement-alert {
  margin-bottom: 16px;
}

.algorithm-upload {
  margin-top: 12px;
}

/* 树形结构改进 */
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

/* 展开动画 */
:deep(.el-tree-node__children) {
  transition: all 0.3s ease;
}



/* 通道容器布局修复 */
.channels-container {
  width: 100%;
  margin-top: 8px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 6px;
  border: 1px solid #e9ecef;
  /* 确保容器本身不会因为内容滚动而改变布局 */
  box-sizing: border-box;
  overflow: hidden;
}
</style>
