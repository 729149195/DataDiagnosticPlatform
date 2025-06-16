<template>
  <!-- 外层flex布局，右上角插入监控状态 -->
  <div class="filter-container-flex">
    <div class="filter-main">
      <!-- 原有过滤器内容 -->
      <div class="form-items">
        <div class="form-item">
          <span class="label">炮　号：</span>
          <div class="input-container">
            <el-input
              v-model="gunNumberInput"
              placeholder="请输入炮号，例如 1-5,7,9-12"
              @clear="handleGunNumberClear"
              @blur="handleGunNumberBlur"
              @keyup.enter="onGunNumberConfirm"
              class="gun-number-input"
              clearable
            >
              <template #append>
                <el-button size="small" @click="onGunNumberConfirm" type="primary" :loading="isIndexLoading">确认炮号</el-button>
              </template>
            </el-input>
          </div>
        </div>
        <div class="form-item">
          <span class="label">通道名：</span>
          <div class="input-container">
            <el-select v-model="selectedChannelNames" filterable multiple collapse-tags collapse-tags-tooltip placeholder="请输入通道名" @clear="handleChannelNameClear" clearable :filter-method="filterChannelNameMethod" reserve-keyword class="tag-select" :disabled="isChannelNameDisabled || isIndexLoading || !hasIndexLoaded">
              <el-option v-if="filteredChannelNameKeyword && filteredChannelNameResultOptions.length > 0" key="select-search-results" label="选择所有搜索结果" value="select-search-results" />
              <el-option v-for="item in filteredChannelNameOptionsList" :key="item.value" :label="item.value" :value="item.value" />
            </el-select>
          </div>
        </div>
        <div class="form-item">
          <span class="label">异常名：</span>
          <div class="input-container">
            <el-select v-model="selectederrorsNames" filterable multiple collapse-tags collapse-tags-tooltip placeholder="请输入异常名" @clear="handleErrorsNameClear" clearable :filter-method="filterErrorsNameMethod" reserve-keyword class="tag-select" :disabled="isErrorNameDisabled || isIndexLoading || !hasIndexLoaded">
              <el-option v-if="filteredErrorsNameKeyword && filteredErrorsNameResultOptions.length > 0" key="select-search-results" label="选择所有搜索结果" value="select-search-results" />
              <el-option v-for="item in filteredErrorsNameOptionsList" :key="item.value" :label="item.value" :value="item.value" />
            </el-select>
          </div>
        </div>
      </div>
      <div class="buttons">
        <el-button type="primary" @click="filterGunNumbers" style="width: 100%;">
          过滤
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import axios from 'axios';
import { useStore } from 'vuex';
import { ElMessage } from 'element-plus';
import { debounce } from 'lodash';
import _ from 'lodash';


const store = useStore();

// 炮号相关数据
const gunNumberInput = ref(''); // 炮号输入字符串
const selectedGunNumbers = ref([]); // 用户选中的炮号键

// 通道类别相关数据
const channelTypeOptions = ref([]);
const selectedChannelTypes = ref([]);
const channelTypeData = ref({});

// 通道名相关数据
const channelNameOptions = ref([]);
const selectedChannelNames = ref([]);
const channelNameData = ref({});

// 异常名相关数据
const errorsNameOptions = ref([]);
const selectederrorsNames = ref([]);
const errorsNameData = ref({});

// 添加新的输入变量
const channelTypeInput = ref('');
const channelNameInput = ref('');
const errorNameInput = ref('');

// 添加通道名搜索相关变量
const filteredChannelNameKeyword = ref('');
const filteredChannelNameResultOptions = ref([]);
const filteredChannelNameOptionsList = ref([]);

// 添加异常名搜索相关变量
const filteredErrorsNameKeyword = ref('');
const filteredErrorsNameResultOptions = ref([]);
const filteredErrorsNameOptionsList = ref([]);

// 添加索引加载状态
const isIndexLoading = ref(false);
const hasIndexLoaded = ref(false);

// 通用函数，用于设置选项和默认选中值
const setOptionsAndSelectAll = (optionsRef, selectedRef, dataRef, data) => {
  optionsRef.value = Object.keys(data).map(key => ({
    label: key,
    value: key,
  }));
  // 初始化时不选中任何选项
  selectedRef.value = [];
  dataRef.value = data; // 保存原始数据
};

// 解析炮号输入字符串
const parseGunNumberInput = () => {
  const input = gunNumberInput.value;
  if (!input) {
    selectedGunNumbers.value = [];
    return;
  }

  const numbers = [];
  const parts = input.split(',');

  for (const part of parts) {
    const trimmedPart = part.trim();
    if (!trimmedPart) continue;

    const rangeMatch = trimmedPart.match(/^(\d+)-(\d+)$/);
    if (rangeMatch) {
      const start = parseInt(rangeMatch[1], 10);
      const end = parseInt(rangeMatch[2], 10);
      if (start <= end) {
        for (let i = start; i <= end; i++) {
          numbers.push(i.toString());
        }
      }
    } else {
      const num = trimmedPart;
      if (num && /^\d+$/.test(num)) {
        numbers.push(num);
      }
    }
  }

  // 去重
  selectedGunNumbers.value = Array.from(new Set(numbers));
};

// 添加失去焦点事件处理
const handleGunNumberBlur = () => {
  // 当输入框失去焦点时，解析输入并更新选中的炮号
  parseGunNumberInput();
};

// 计算属性：获取选中炮号及其对应的值
const selectedGunNumbersWithValues = computed(() => {
  return selectedGunNumbers.value.map(key => ({
    key,
    values: [key], // 简化为直接使用炮号本身
  }));
});

// 计算属性：获取选中通道类别及其对应的值
const selectedChannelTypesWithValues = computed(() => {
  return selectedChannelTypes.value.map(key => ({
    key,
    values: channelTypeData.value[key] || [],
  }));
});

// 计算属性：获取选中通道名及其对应的值
const selectedChannelNamesWithValues = computed(() => {
  return selectedChannelNames.value.map(key => ({
    key,
    values: channelNameData.value[key] || [],
  }));
});

// 计算属性：获取选中异常名及其对应的值
const selectederrorsNamesWithValues = computed(() => {
  return selectederrorsNames.value.map(key => ({
    key,
    values: errorsNameData.value[key] || [],
  }));
});

// 计算属性：判断是否有任何选中的数据
const hasSelectedData = computed(() => {
  return (
    selectedGunNumbersWithValues.value.length ||
    selectedChannelTypesWithValues.value.length ||
    selectedChannelNamesWithValues.value.length ||
    selectederrorsNamesWithValues.value.length
  );
});

// 过滤函数
const filterGunNumbers = () => {
  parseGunNumberInput();

  if (!selectedGunNumbers.value.length) {
    ElMessage.warning('请至少输入一个炮号。');
    return;
  }

  // 构造过滤条件对象
  const filterParams = {
    shot_numbers: selectedGunNumbers.value,
    channel_names: selectedChannelNames.value,
    error_names: selectederrorsNames.value
  };

  store.dispatch('fetchStructTree', filterParams);
};

// 在 setup 中添加新的计算属性和监听器
const filteredChannelNameOptions = computed(() => {
  let options = channelNameOptions.value;

  // 按通道类别过滤
  if (selectedChannelTypes.value.length) {
    const validIndices = new Set();
    selectedChannelTypes.value.forEach(type => {
      const indices = channelTypeData.value[type] || [];
      indices.forEach(index => validIndices.add(index));
    });
    options = options.filter(option => {
      const channelIndices = channelNameData.value[option.value] || [];
      return channelIndices.some(index => validIndices.has(index));
    });
  }

  // 按异常名过滤（只遍历已选异常名）
  if (selectederrorsNames.value.length) {
    const validIndices = new Set();
    selectederrorsNames.value.forEach(errorName => {
      const indices = errorsNameData.value[errorName] || [];
      indices.forEach(idx => validIndices.add(idx));
    });
    options = options.filter(option => {
      const channelIndices = channelNameData.value[option.value] || [];
      return channelIndices.some(idx => validIndices.has(idx));
    });
  }

  return options;
});

const filteredErrorsNameOptions = computed(() => {
  let options = errorsNameOptions.value;

  // 按通道类别和通道名过滤
  if (selectedChannelTypes.value.length) {
    const validIndices = new Set();
    selectedChannelTypes.value.forEach(type => {
      const indices = channelTypeData.value[type] || [];
      indices.forEach(index => validIndices.add(index));
    });
    options = options.filter(option => {
      const errorIndices = errorsNameData.value[option.value] || [];
      return errorIndices.some(idx => validIndices.has(idx));
    });
  }

  // 按通道名过滤（只遍历已选通道名）
  if (selectedChannelNames.value.length) {
    const validIndices = new Set();
    selectedChannelNames.value.forEach(channelName => {
      const indices = channelNameData.value[channelName] || [];
      indices.forEach(idx => validIndices.add(idx));
    });
    options = options.filter(option => {
      const errorIndices = errorsNameData.value[option.value] || [];
      return errorIndices.some(idx => validIndices.has(idx));
    });
  }

  return options;
});

// 添加监听器来清理无效选项
watch(selectedChannelTypes, (newTypes) => {
  // 清理无效的通道名选择
  selectedChannelNames.value = selectedChannelNames.value.filter(name => {
    return filteredChannelNameOptions.value.some(option => option.value === name);
  });

  // 清理无效的异常名选择
  selectederrorsNames.value = selectederrorsNames.value.filter(name => {
    return filteredErrorsNameOptions.value.some(option => option.value === name);
  });

  // 更新通道名选项列表
  filteredChannelNameOptionsList.value = filteredChannelNameOptions.value;

  // 更新异常名选项列表
  filteredErrorsNameOptionsList.value = filteredErrorsNameOptions.value;
});

watch(selectedChannelNames, (newVal) => {
  // 处理"选择所有搜索结果"选项
  if (newVal.includes('select-search-results')) {
    // 如果选中了"选择所有搜索结果"，则选中当前搜索结果中的所有选项
    const searchResultValues = filteredChannelNameResultOptions.value.map(item => item.value);
    // 删除"select-search-results"并添加所有搜索结果
    selectedChannelNames.value = Array.from(new Set([
      ...selectedChannelNames.value.filter(item => item !== 'select-search-results'),
      ...searchResultValues
    ]));
  }
  // 处理"全选"选项
  else if (newVal.includes('select-all')) {
    // 如果选中了全选，则选中所有选项（除了全选选项本身）
    selectedChannelNames.value = filteredChannelNameOptions.value.map(option => option.value);
  }

  // 清理无效的异常名选择
  selectederrorsNames.value = selectederrorsNames.value.filter(name => {
    return filteredErrorsNameOptions.value.some(option => option.value === name);
  });

  // 通道名变更时，更新异常名的选项列表
  filteredErrorsNameOptionsList.value = filteredErrorsNameOptions.value;

  // 如果当前有异常名搜索关键词，重新应用过滤
  if (filteredErrorsNameKeyword.value) {
    const filterOptions = filteredErrorsNameOptions.value.filter(
      item => item.value.toLowerCase().includes(filteredErrorsNameKeyword.value.toLowerCase())
    );
    filteredErrorsNameResultOptions.value = filterOptions;
    filteredErrorsNameOptionsList.value = filterOptions;
  }
});

// 修改计算属性，添加全选选项
const channelTypeOptionsWithAll = computed(() => {
  return [
    {
      value: 'select-all',
      label: '全选所有通道类别',
      disabled: false
    },
    ...channelTypeOptions.value
  ];
});

const channelNameOptionsWithAll = computed(() => {
  return [
    {
      value: 'select-all',
      label: '全选所有通道名',
      disabled: false
    },
    ...filteredChannelNameOptions.value
  ];
});

const errorsNameOptionsWithAll = computed(() => {
  return [
    {
      value: 'select-all',
      label: '全选所有异常名',
      disabled: false
    },
    ...filteredErrorsNameOptions.value
  ];
});

// 添加 watch 来处理全选逻辑
watch(selectedChannelTypes, (newVal) => {
  if (newVal.includes('select-all')) {
    // 如果选中了全选，则选中所有选项（除了全选选项本身）
    selectedChannelTypes.value = channelTypeOptions.value.map(option => option.value);
  }
});

watch(selectederrorsNames, (newVal) => {
  // 处理"选择所有搜索结果"选项
  if (newVal.includes('select-search-results')) {
    // 如果选中了"选择所有搜索结果"，则选中当前搜索结果中的所有选项
    const searchResultValues = filteredErrorsNameResultOptions.value.map(item => item.value);
    // 删除"select-search-results"并添加所有搜索结果
    selectederrorsNames.value = Array.from(new Set([
      ...selectederrorsNames.value.filter(item => item !== 'select-search-results'),
      ...searchResultValues
    ]));
  }
  // 处理"全选"选项
  else if (newVal.includes('select-all')) {
    // 如果选中了全选，则选中所有选项（除了全选选项本身）
    selectederrorsNames.value = filteredErrorsNameOptions.value.map(option => option.value);
  }
});

// 修改清除函数，确保清除时也更新选中的炮号
const handleGunNumberClear = () => {
  gunNumberInput.value = '';
  selectedGunNumbers.value = [];
};

const handleChannelTypeClear = () => {
  selectedChannelTypes.value = [];
  // 清空通道类别时，也需要清空依赖于通道类别的其他选择
  selectedChannelNames.value = [];
  selectederrorsNames.value = [];
};

const handleChannelNameClear = () => {
  selectedChannelNames.value = [];
  // 清空通道名时，也需要清空依赖于通道名的异常名选择
  selectederrorsNames.value = [];
};

const handleErrorsNameClear = () => {
  selectederrorsNames.value = [];
};

// 通道类别搜索建议
const querySearchChannelTypes = debounce((queryString, cb) => {
  const results = queryString
    ? channelTypeOptions.value.filter(
      item => item.value.toLowerCase().includes(queryString.toLowerCase())
    )
    : channelTypeOptions.value;
  cb(results.map(item => ({ value: item.value })));
}, 300);

// 通道名搜索建议
const querySearchChannelNames = debounce((queryString, cb) => {
  const results = queryString
    ? filteredChannelNameOptions.value.filter(
      item => item.value.toLowerCase().includes(queryString.toLowerCase())
    )
    : filteredChannelNameOptions.value;
  cb(results.map(item => ({ value: item.value })));
}, 300);

// 异常名搜索建议
const querySearchErrorNames = debounce((queryString, cb) => {
  const results = queryString
    ? filteredErrorsNameOptions.value.filter(
      item => item.value.toLowerCase().includes(queryString.toLowerCase())
    )
    : filteredErrorsNameOptions.value;
  cb(results.map(item => ({ value: item.value })));
}, 300);


// 添加输入监听
watch(channelTypeInput, (newVal) => {
  if (!newVal) {
    selectedChannelTypes.value = [];
  }
});

watch(channelNameInput, (newVal) => {
  if (!newVal) {
    selectedChannelNames.value = [];
  }
});

watch(errorNameInput, (newVal) => {
  if (!newVal) {
    selectederrorsNames.value = [];
  }
});

// 通道名筛选方法
const filterChannelNameMethod = (val) => {
  if (val) {
    filteredChannelNameKeyword.value = val;
    // 使用过滤后的选项进行搜索
    const filterOptions = filteredChannelNameOptions.value.filter(
      item => item.value.toLowerCase().includes(val.toLowerCase())
    );
    filteredChannelNameResultOptions.value = filterOptions;
    // 显示过滤后的选项和全选按钮
    filteredChannelNameOptionsList.value = filterOptions;
  } else {
    filteredChannelNameKeyword.value = '';
    filteredChannelNameResultOptions.value = [];
    // 不搜索时显示所有选项
    filteredChannelNameOptionsList.value = filteredChannelNameOptions.value;
  }
  return true; // 返回true表示已自定义了过滤逻辑，避免内部再次过滤
};

// 监听filteredChannelNameOptions，更新显示的选项列表
watch(filteredChannelNameOptions, (newOptions) => {
  // 如果当前没有搜索关键词，则更新显示的选项列表
  if (!filteredChannelNameKeyword.value) {
    filteredChannelNameOptionsList.value = newOptions;
  }
});

// 异常名筛选方法
const filterErrorsNameMethod = (val) => {
  if (val) {
    filteredErrorsNameKeyword.value = val;
    // 使用过滤后的选项进行搜索（基于选中的通道名过滤后的选项）
    const filterOptions = filteredErrorsNameOptions.value.filter(
      item => item.value.toLowerCase().includes(val.toLowerCase())
    );
    filteredErrorsNameResultOptions.value = filterOptions;
    // 显示过滤后的选项和全选按钮
    filteredErrorsNameOptionsList.value = filterOptions;
  } else {
    filteredErrorsNameKeyword.value = '';
    filteredErrorsNameResultOptions.value = [];
    // 不搜索时显示基于通道名过滤后的选项
    filteredErrorsNameOptionsList.value = filteredErrorsNameOptions.value;
  }
  return true; // 返回true表示已自定义了过滤逻辑，避免内部再次过滤
};

// 监听filteredErrorsNameOptions，更新显示的选项列表
watch(filteredErrorsNameOptions, (newOptions) => {
  // 如果当前没有搜索关键词，则更新显示的选项列表
  if (!filteredErrorsNameKeyword.value) {
    filteredErrorsNameOptionsList.value = newOptions;
  }
});

// 只刷新异常名的函数
const fetchErrorNames = async () => {
  try {
    // 如果有选中的炮号，传递给refreshErrorNames函数
    const shotNumbers = selectedGunNumbers.value.length > 0 ? selectedGunNumbers.value : null;
    const data = await store.dispatch('refreshErrorNames', shotNumbers);
    setOptionsAndSelectAll(errorsNameOptions, selectederrorsNames, errorsNameData, data);
  } catch (error) {
    ElMessage.error('异常名索引获取失败');
  }
};

// 监听异常名索引版本号变化，自动刷新异常名下拉
watch(
  () => store.state.errorNamesVersion,
  async () => {
    // 只有在有选中炮号的情况下才刷新异常名，避免加载全库异常名
    if (selectedGunNumbers.value.length > 0) {
      await fetchErrorNames();
    }
  }
);

// 初始化时不再获取炮号选项
onMounted(async () => {
  selectedChannelNames.value = [];
  selectederrorsNames.value = [];
  filteredChannelNameOptionsList.value = [];
  filteredErrorsNameOptionsList.value = [];
});

// 通道名和异常名下拉禁用逻辑
const isChannelNameDisabled = computed(() => selectedGunNumbers.value.length === 0);
const isErrorNameDisabled = computed(() => selectedGunNumbers.value.length === 0);

const onGunNumberConfirm = async () => {
  parseGunNumberInput();
  hasIndexLoaded.value = false;
  if (selectedGunNumbers.value.length > 0) {
    isIndexLoading.value = true;
    try {
      // 请求通道名索引
      const channelNameRes = await axios.get('http://192.168.20.49:5000/api/get-channel-name-index', {
        params: { 
          shot_numbers: selectedGunNumbers.value.join(',')
        }
      });
      
      // 检查响应是否包含错误信息
      if (channelNameRes.data.error) {
        throw new Error(`获取通道名索引失败: ${channelNameRes.data.error}`);
      }
      
      // 检查是否为空对象（没有任何通道名数据）
      if (Object.keys(channelNameRes.data).length === 0) {
        console.warn(`未找到炮号 ${selectedGunNumbers.value.join(', ')} 的通道名索引`);
        ElMessage.warning(`未找到选中炮号的通道名数据，请检查炮号是否存在或索引是否已建立`);
      }
      
      setOptionsAndSelectAll(channelNameOptions, selectedChannelNames, channelNameData, channelNameRes.data);
      
      // 请求异常名索引
      const errorNameRes = await axios.get('http://192.168.20.49:5000/api/get-errors-name-index', {
        params: { 
          shot_numbers: selectedGunNumbers.value.join(',')
        }
      });
      
      // 检查响应是否包含错误信息
      if (errorNameRes.data.error) {
        throw new Error(`获取异常名索引失败: ${errorNameRes.data.error}`);
      }
      
      // 检查是否为空对象（没有任何异常名数据）
      if (Object.keys(errorNameRes.data).length === 0) {
        console.warn(`未找到炮号 ${selectedGunNumbers.value.join(', ')} 的异常名索引`);
        // 这里不显示警告，因为可能确实没有异常
      }
      
      setOptionsAndSelectAll(errorsNameOptions, selectederrorsNames, errorsNameData, errorNameRes.data);
      hasIndexLoaded.value = true;
      ElMessage.success('炮号确认成功，通道/异常名列表已更新');
    } catch (error) {
      console.error('通道名或异常名索引获取失败:', error);
      ElMessage.error(`获取索引失败: ${error.message || '未知错误'}`);
      hasIndexLoaded.value = false;
    } finally {
      isIndexLoading.value = false;
    }
  } else {
    channelNameOptions.value = [];
    errorsNameOptions.value = [];
    selectedChannelNames.value = [];
    selectederrorsNames.value = [];
    hasIndexLoaded.value = false;
  }
};
</script>

<style scoped lang="scss">
/* 新增flex布局样式 */
.filter-container-flex {
  position: relative;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: flex-start;
  width: 100%;
}
.filter-main {
  flex: 1 1 auto;
  min-width: 0;
}

.filter-container {
  width: 100%;
  display: flex;
  flex-direction: column;
}

.form-items {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-item {
  display: flex;
  align-items: center;
  height: 32px;
}

.label {
  min-width: 60px;
  text-align: right;
  margin-right: 5px;
  margin-left: 5px;
}

.input-container {
  flex: 1;
}

.buttons {
  margin-top: 8px;
  width: 100%;
}

.gun-number-input {
  width: 100%;
}

.db-select {
  width: 100%;
}

/* 修改Element Plus组件样式 */
:deep(.el-input__wrapper),
:deep(.el-select .el-input__wrapper) {
  height: 32px !important;
  line-height: 32px !important;
}

:deep(.el-select),
:deep(.el-input) {
  width: 100%;
}

:deep(.el-button) {
  height: 32px;
  padding-top: 5px;
  padding-bottom: 5px;
}

.select-all-btn {
  height: 28px;
  padding: 0 12px;
  font-size: 12px;
}

.select-container {
  display: inline-flex;
  flex-direction: column;
  min-width: 200px;
  margin-right: 20px;
}

.selected-tags {
  margin-top: 5px;
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.selected-tag {
  margin: 2px;
}

.selected-data {
  margin-top: 20px;
  background-color: #f9f9f9;
  padding: 10px;
  border-radius: 5px;
}

.selected-data h3 {
  margin-bottom: 10px;
}

.selected-data ul {
  list-style-type: none;
  padding: 0;
}

.selected-data li {
  margin-bottom: 5px;
}

.input-hint {
  color: #999;
  font-size: 12px;
  margin-left: 5px;
}

:deep(.tag-select) {
  width: 100%;
  /* 确保选择器占满整行宽度 */

  /* 自定义宽度控制，基于容器宽度 */
  &.el-select {
    width: 100%;
  }

  /* 整体标签容器 */
  .el-select__tags {
    display: flex;
    flex-wrap: nowrap;
    overflow-x: hidden;
    max-width: calc(100% - 30px);
    /* 给下拉箭头留出空间 */
    padding-right: 30px;
    /* 为下拉箭头留出空间 */
    align-items: center;
    min-height: 28px;
  }

  /* 标签容器内部滚动区域 */
  .el-select__tags-wrap {
    display: flex;
    flex-wrap: nowrap;
    width: 100%;
    overflow-x: hidden;
  }

  /* 输入框 */
  .el-input__inner {
    line-height: 28px;
    height: 28px;
  }

  /* 标签文字部分 */
  .el-select__tags-text {
    display: inline-block;
    max-width: 100px;
    /* 标签默认最大宽度 */
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: 11px;
  }

  /* 标签基本样式 */
  .el-tag {
    display: inline-flex;
    align-items: center;
    flex-shrink: 0;
    margin-right: 2px;
    max-width: fit-content;
    padding: 0 2px 0 4px;
    height: 20px;
    white-space: nowrap;
  }

  /* 关闭按钮 */
  .el-tag .el-tag__close {
    margin-left: 1px;
    width: 12px;
    height: 12px;
    line-height: 12px;
    right: 0;
    transform: translateY(0);
  }

  /* 调整折叠标签的样式 */
  .el-select__collapse-tags {
    display: inline-flex;
    align-items: center;
    position: relative;
    margin-left: 2px;
    height: 20px;
    flex-shrink: 0;
  }

  /* 折叠标签样式 */
  .el-select__collapse-tag,
  .el-select__collapse-tags .el-tag {
    height: 20px;
    padding: 0 4px;
    font-size: 11px;
    background-color: #f4f4f5;
    border-color: #e9e9eb;
    color: #909399;
    margin-right: 0;
  }

  /* 使折叠标签比其他标签更靠右显示 */
  .el-select-dropdown__wrap {
    max-width: 100%;
  }

  /* 确保+N标签始终显示且位置正确 */
  .el-select--collapse-tags {
    .el-select__tags {
      justify-content: flex-start;
    }
  }
}
</style>
