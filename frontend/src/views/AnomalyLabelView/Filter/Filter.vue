<template>
  <div>
    <div class="two">
      <div>
        <span>炮号：</span>
        <div class="gun-number-container">
          <el-autocomplete
              :model-value="gunNumberInput"
              :fetch-suggestions="querySearchGunNumbers"
              placeholder="请输入炮号，例如 1-5,7,9-12"
              @select="handleGunNumberSelect"
              @input="handleInput"
              @clear="handleGunNumberClear"
              @focus="handleGunNumberFocus"
              @blur="handleGunNumberBlur"
              clearable
              class="gun-number-input"
          ></el-autocomplete>
        </div>
      </div>
      <div>
        <span>通道名：</span>
        <el-select
            v-model="selectedChannelNames"
            filterable
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="请输入通道名"
            @clear="handleChannelNameClear"
            clearable
            :filter-method="filterChannelNameMethod"
            reserve-keyword
        >
          <el-option
              v-if="filteredChannelNameKeyword && filteredChannelNameResultOptions.length > 0"
              key="select-search-results"
              label="选择所有搜索结果"
              value="select-search-results"
          />
          <el-option
              v-for="item in filteredChannelNameOptionsList"
              :key="item.value"
              :label="item.value"
              :value="item.value"
          />
        </el-select>
        <span>异常名：</span>
        <el-select
            v-model="selectederrorsNames"
            filterable
            multiple
            collapse-tags
            collapse-tags-tooltip
            placeholder="请输入异常名"
            @clear="handleErrorsNameClear"
            clearable
            :filter-method="filterErrorsNameMethod"
            reserve-keyword
        >
          <el-option
              v-if="filteredErrorsNameKeyword && filteredErrorsNameResultOptions.length > 0"
              key="select-search-results"
              label="选择所有搜索结果"
              value="select-search-results"
          />
          <el-option
              v-for="item in filteredErrorsNameOptionsList"
              :key="item.value"
              :label="item.value"
              :value="item.value"
          />
        </el-select>
      </div>
    </div>
    <div class="buttons">
      <el-button type="primary" @click="filterGunNumbers" style="width: 100%;">
        过滤
      </el-button>
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
const gunNumberOptions = ref([]);
const gunNumberInput = ref(''); // 炮号输入字符串
const selectedGunNumbers = ref([]); // 用户选中的炮号键
const gunNumberData = ref({}); // 保存炮号键与值的映射
const gunNumberSearchResults = ref([]); // 保存当前搜索结果

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

// 添加全选状态管理
const channelTypesAllSelected = ref(false);
const channelNamesAllSelected = ref(false);
const errorsNamesAllSelected = ref(false);

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

// 获取数据
const fetData = async () => {
  try {
    const [
      gunNumberResponse,
      channelTypeResponse,
      channelNameResponse,
      errorsNameResponse,
      // errorsOriginResponse
    ] = await Promise.all([
      axios.get('https://10.1.108.231:5000/api/get-shot-number-index'),
      axios.get('https://10.1.108.231:5000/api/get-channel-type-index'),
      axios.get('https://10.1.108.231:5000/api/get-channel-name-index'),
      axios.get('https://10.1.108.231:5000/api/get-errors-name-index'),
    ]);

    // 设置炮号选项和保存原始数据
    setOptionsAndSelectAll(gunNumberOptions, selectedGunNumbers, gunNumberData, gunNumberResponse.data);

    // 设置通道类别选项和保存原始数据
    setOptionsAndSelectAll(channelTypeOptions, selectedChannelTypes, channelTypeData, channelTypeResponse.data);

    // 设置通道名选项和保存原始数据
    setOptionsAndSelectAll(channelNameOptions, selectedChannelNames, channelNameData, channelNameResponse.data);

    // 设置异常名选项和保存原始数据
    setOptionsAndSelectAll(errorsNameOptions, selectederrorsNames, errorsNameData, errorsNameResponse.data);
  } catch (error) {
    console.error('Failed to fetch data:', error);
    ElMessage.error('数据获取失败，请稍后再试。');
  }
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
  const invalidNumbers = [];
  const invalidRanges = [];

  for (const part of parts) {
    const trimmedPart = part.trim();
    if (!trimmedPart) continue;

    const rangeMatch = trimmedPart.match(/^(\d+)-(\d+)$/);
    if (rangeMatch) {
      const start = parseInt(rangeMatch[1], 10);
      const end = parseInt(rangeMatch[2], 10);
      if (start <= end) {
        let validInRange = false;
        for (let i = start; i <= end; i++) {
          if (gunNumberOptions.value.find(option => option.value === i.toString())) {
            numbers.push(i.toString());
            validInRange = true;
          } else {
            invalidNumbers.push(i);
          }
        }
        // 如果范围内没有一个有效的炮号，则记录为无效范围
        if (!validInRange) {
          invalidRanges.push(trimmedPart);
        }
      } else {
        invalidRanges.push(trimmedPart);
      }
    } else {
      const num = trimmedPart;
      if (num && /^\d+$/.test(num)) {
        // 验证是否为有效的炮号
        if (gunNumberOptions.value.find(option => option.value === num)) {
          numbers.push(num);
        } else {
          invalidNumbers.push(num);
        }
      } else if (num) {
        // 非数字输入
        invalidNumbers.push(num);
      }
    }
  }

  // 去重
  selectedGunNumbers.value = Array.from(new Set(numbers));

  // 显示警告信息（如果有无效输入）
  if (invalidRanges.length > 0 || invalidNumbers.length > 0) {
    let warningMsg = '';
    
    if (invalidRanges.length > 0) {
      warningMsg += `无效的范围: ${invalidRanges.join(', ')}`;
    }
    
    if (invalidNumbers.length > 0) {
      if (warningMsg) warningMsg += '; ';
      // 限制显示的无效炮号数量，避免消息过长
      const displayInvalidNumbers = invalidNumbers.length > 10 
        ? invalidNumbers.slice(0, 10).join(', ') + `...等${invalidNumbers.length}个`
        : invalidNumbers.join(', ');
      warningMsg += `无效的炮号: ${displayInvalidNumbers}`;
    }
    
    if (warningMsg) {
      ElMessage.warning(warningMsg);
    }
  }
};

// 处理自动补全建议
const querySearchGunNumbers = debounce((queryString, cb) => {
  // 如果输入为空，显示初始建议
  if (!queryString.trim()) {
    // 获取前20个炮号作为建议
    const initialSuggestions = gunNumberOptions.value
      .slice(0, 20)
      .map(item => ({ value: item.value }));
    
    // 保存当前搜索结果
    gunNumberSearchResults.value = initialSuggestions;
    
    // 如果有很多炮号，添加一个提示选项
    if (gunNumberOptions.value.length > 20) {
      initialSuggestions.push({
        value: `输入数字或范围查看更多，共 ${gunNumberOptions.value.length} 个炮号`,
        disabled: true
      });
    }
    
    cb(initialSuggestions);
    return;
  }

  const parts = queryString.split(',');
  const lastPart = parts.pop().trim();

  let currentInput = lastPart;
  let suggestions = [];

  // 检查是否有范围符号 '-'
  const rangeMatch = currentInput.match(/^(\d+)-(\d*)$/); // 匹配 'a-' 或 'a-b'

  if (rangeMatch) {
    const start = parseInt(rangeMatch[1], 10);
    const partialEnd = rangeMatch[2];

    if (!isNaN(start)) {
      if (partialEnd) {
        // 用户正在输入范围的结束部分，如 '1-5'
        suggestions = gunNumberOptions.value
            .filter(item => item.value.startsWith(partialEnd) && parseInt(item.value, 10) >= start)
            .slice(0, 10) // 限制最多10个建议
            .map(item => ({value: item.value}));
      } else {
        // 用户输入范围的起始部分，如 '1-'
        suggestions = gunNumberOptions.value
            .filter(item => parseInt(item.value, 10) > start) // 确保建议的值大于起始值
            .sort((a, b) => parseInt(a.value, 10) - parseInt(b.value, 10)) // 按数值排序
            .slice(0, 10) // 限制最多10个建议
            .map(item => ({value: item.value}));
      }
    }
  } else {
    // 普通建议，根据最后一个部分匹配
    suggestions = gunNumberOptions.value
        .filter(item => item.value.startsWith(currentInput))
        .slice(0, 10) // 限制最多10个建议
        .map(item => ({value: item.value}));
  }

  // 保存当前搜索结果
  gunNumberSearchResults.value = suggestions;
  
  // 如果有搜索结果，添加"全选搜索结果"选项到第一位
  if (suggestions.length > 1) {
    suggestions.unshift({
      value: `全选 ${suggestions.length} 个搜索结果`,
      isSelectAll: true
    });
  }

  cb(suggestions);
}, 300); // 延迟300ms触发

// 当用户选择自动补全项时，更新输入框的值
const previousInput = ref('');

const handleInput = (value) => {
  previousInput.value = gunNumberInput.value;
  gunNumberInput.value = value;
  // 不再在输入时立即解析，而是仅更新输入值
};

// 添加失去焦点事件处理
const handleGunNumberBlur = () => {
  // 当输入框失去焦点时，解析输入并更新选中的炮号
  parseGunNumberInput();
};

const handleGunNumberSelect = (item) => {
  // 检查是否选择了"全选搜索结果"选项
  if (item.isSelectAll) {
    // 执行全选搜索结果的逻辑
    selectAllGunNumberResults();
    return;
  }
  
  // 由于选择建议项时，输入框的值会被自动替换，所以需要使用之前的输入值
  const inputBeforeSelection = previousInput.value;
  const parts = inputBeforeSelection.split(',');
  let lastPart = parts.pop().trim();

  const rangeMatch = lastPart.match(/^(\d+)-(\d*)$/);
  if (rangeMatch) {
    const start = rangeMatch[1];
    const partialEnd = rangeMatch[2];
    if (partialEnd) {
      // 如果已经有部分结束值，则替换为完整范围
      parts.push(`${start}-${item.value}`);
    } else {
      // 如果只有起始值，则补全范围
      parts.push(`${start}-${item.value}`);
    }
  } else {
    // 仅单个炮号，直接替换
    parts.push(item.value);
  }

  // 重新组合输入字符串，添加逗号和空格以便用户继续输入
  gunNumberInput.value = parts.join(', ') + ', ';
  
  // 选择后立即解析输入，因为这是用户的明确选择
  parseGunNumberInput();
};

// 计算属性：获取选中炮号及其对应的值
const selectedGunNumbersWithValues = computed(() => {
  return selectedGunNumbers.value.map(key => ({
    key,
    values: gunNumberData.value[key] || [],
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

// // 计算属性：获取选中异常来源及其对应的值
// const selectederrorsOriginWithValues = computed(() => {
//     return selectederrorsOrigin.value.map(key => ({
//         key,
//         values: errorsOriginData.value[key] || [],
//     }));
// });

// 计算属性：判断是否有任何选中的数据
const hasSelectedData = computed(() => {
  return (
      selectedGunNumbersWithValues.value.length ||
      selectedChannelTypesWithValues.value.length ||
      selectedChannelNamesWithValues.value.length ||
      selectederrorsNamesWithValues.value.length
      // selectederrorsOriginWithValues.value.length
  );
});

// 过滤函数
const filterGunNumbers = () => {
  // 首先解析炮号输入
  parseGunNumberInput();

  // 检查是否有任何选中的数据
  if (!selectedGunNumbers.value.length && !selectedChannelNames.value.length && !selectederrorsNames.value.length) {
    ElMessage.warning('请至少输入一个搜索条件。');
    return;
  }

  const filterData = {
    gunNumbers: selectedGunNumbersWithValues.value,
    channelNames: selectedChannelNamesWithValues.value,
    errorsNames: selectederrorsNamesWithValues.value,
  };

  // 收集所有有选中值的选项的 values 数组
  let selectedValuesArrays = [];

  Object.entries(filterData).forEach(([key, value]) => {
    if (value.length > 0) {  // 只处理有选中值的选项
      let values = [];
      value.forEach(item => {
        values = values.concat(item.values);
      });
      selectedValuesArrays.push(values);
    }
  });

  // 如果没有任何选中的值，返回空结果
  if (selectedValuesArrays.length === 0) {
    ElMessage.warning('请至少选择一个过滤条件。');
    return;
  }

  // 计算所有选中选项的交集
  let intersectionArray = selectedValuesArrays[0];

  for (let i = 1; i < selectedValuesArrays.length; i++) {
    intersectionArray = _.intersection(intersectionArray, selectedValuesArrays[i]);
  }

  // 最终结果
  const finalResult = intersectionArray;

  if (!finalResult || finalResult.length === 0) {
    ElMessage.warning('没有找到符合条件的结果。');
    return;
  }

  store.dispatch('fetchStructTree', finalResult);
};

// 在 setup 中添加新的计算属性和监听器
const filteredChannelNameOptions = computed(() => {
  if (!selectedChannelTypes.value.length) {
    return channelNameOptions.value;
  }

  // 获取所选通道类别下的所有通道名索引
  const validIndices = new Set();
  selectedChannelTypes.value.forEach(type => {
    const indices = channelTypeData.value[type] || [];
    indices.forEach(index => validIndices.add(index));
  });

  // 只返回在选中通道类别下有效的通道名选项
  return channelNameOptions.value.filter(option => {
    const channelIndices = channelNameData.value[option.value] || [];
    return channelIndices.some(index => validIndices.has(index));
  });
});

const filteredErrorsNameOptions = computed(() => {
  if (!selectedChannelTypes.value.length && !selectedChannelNames.value.length) {
    return errorsNameOptions.value;
  }

  // 获取所有有效的索引
  const validIndices = new Set();

  // 从选中的通道类别获取索引
  selectedChannelTypes.value.forEach(type => {
    const indices = channelTypeData.value[type] || [];
    indices.forEach(index => validIndices.add(index));
  });

  // 从选中的通道名获取索引
  selectedChannelNames.value.forEach(name => {
    const indices = channelNameData.value[name] || [];
    indices.forEach(index => validIndices.add(index));
  });

  // 只返回在有效索引范围内的异常名选项
  return errorsNameOptions.value.filter(option => {
    const errorIndices = errorsNameData.value[option.value] || [];
    return errorIndices.some(index => validIndices.has(index));
  });
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
  gunNumberSearchResults.value = []; // 清除搜索结果
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

// 处理选择事件
const handleChannelTypeSelect = (item) => {
  if (!selectedChannelTypes.value.includes(item.value)) {
    selectedChannelTypes.value.push(item.value);
  }
  channelTypeInput.value = selectedChannelTypesText.value;
};

const handleChannelNameSelect = (item) => {
  if (!selectedChannelNames.value.includes(item.value)) {
    selectedChannelNames.value.push(item.value);
  }
  channelNameInput.value = selectedChannelNamesText.value;
};

const handleErrorNameSelect = (item) => {
  if (!selectederrorsNames.value.includes(item.value)) {
    selectederrorsNames.value.push(item.value);
  }
  errorNameInput.value = selectedErrorNamesText.value;
};

// 添加移除标签的处理函数
const removeChannelType = (type) => {
  selectedChannelTypes.value = selectedChannelTypes.value.filter(t => t !== type);
};

const removeChannelName = (name) => {
  selectedChannelNames.value = selectedChannelNames.value.filter(n => n !== name);
};

const removeErrorName = (name) => {
  selectederrorsNames.value = selectederrorsNames.value.filter(n => n !== name);
};

// 添加计算属性来处理选中选项的文本显示
const selectedChannelTypesText = computed(() => {
  return selectedChannelTypes.value.join(', ');
});

const selectedChannelNamesText = computed(() => {
  return selectedChannelNames.value.join(', ');
});

const selectedErrorNamesText = computed(() => {
  return selectederrorsNames.value.join(', ');
});

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

// 全选炮号搜索结果
const selectAllGunNumberResults = () => {
  // 过滤掉特殊选项（如全选选项和提示选项）
  const validResults = gunNumberSearchResults.value.filter(item => !item.isSelectAll && !item.disabled);
  
  if (validResults.length > 0) {
    const resultValues = validResults.map(item => item.value);
    
    // 检查当前输入是否为范围格式
    const currentInput = gunNumberInput.value.trim();
    const parts = currentInput.split(',');
    const lastPart = parts[parts.length - 1].trim();
    const isRangeInput = lastPart.includes('-');
    
    if (isRangeInput && resultValues.length > 1) {
      // 如果是范围输入，并且有多个结果，则使用范围格式
      const rangeMatch = lastPart.match(/^(\d+)-(\d*)$/);
      if (rangeMatch) {
        const start = rangeMatch[1];
        // 找到结果中的最小值和最大值
        const min = Math.min(...resultValues.map(v => parseInt(v, 10)));
        const max = Math.max(...resultValues.map(v => parseInt(v, 10)));
        
        // 替换最后一部分为完整范围
        parts.pop();
        parts.push(`${start}-${max}`);
        
        // 更新输入
        gunNumberInput.value = parts.join(', ');
      }
    } else {
      // 否则使用逗号分隔的列表
      // 将结果格式化为用户输入形式
      gunNumberInput.value = resultValues.join(', ');
    }
    
    // 解析输入并更新选中的炮号
    parseGunNumberInput();
    
    // 清空搜索结果
    gunNumberSearchResults.value = [];
    
    ElMessage.success(`已选择 ${resultValues.length} 个炮号`);
  }
};

// 处理炮号输入框获取焦点事件
const handleGunNumberFocus = () => {
  // 当输入框为空时，显示所有可用的炮号选项（限制数量以避免过多）
  if (!gunNumberInput.value.trim()) {
    // 获取前20个炮号作为建议
    const initialSuggestions = gunNumberOptions.value
      .slice(0, 20)
      .map(item => ({ value: item.value }));
    
    // 如果有多个选项，添加全选选项
    if (initialSuggestions.length > 1) {
      initialSuggestions.unshift({
        value: `全选 ${initialSuggestions.length} 个炮号`,
        isSelectAll: true
      });
    }
    
    // 保存当前搜索结果
    gunNumberSearchResults.value = initialSuggestions;
    
    // 如果有很多炮号，添加一个提示选项
    if (gunNumberOptions.value.length > 20) {
      gunNumberSearchResults.value.push({
        value: `输入数字或范围查看更多，共 ${gunNumberOptions.value.length} 个炮号`,
        disabled: true
      });
    }
  }
};

onMounted(async () => {
  await fetData();
  // 初始化时所有选择都为空
  selectedChannelNames.value = [];
  selectederrorsNames.value = [];
  filteredChannelNameOptionsList.value = filteredChannelNameOptions.value;
  filteredErrorsNameOptionsList.value = filteredErrorsNameOptions.value;
  store.dispatch('fetchStructTree');
});
</script>

<style scoped lang="scss">
.buttons {
  margin-top: 10px;
  width: 100%;
}

.gun-number-container {
  display: flex;
  align-items: center;
}

.gun-number-input {
  margin-right: 10px;
}

.select-all-btn {
  height: 32px;
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
</style>
