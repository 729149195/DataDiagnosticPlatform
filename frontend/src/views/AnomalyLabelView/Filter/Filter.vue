<template>
  <div>
    <div class="two">
      <div>
        <span>炮号：</span>
        <el-autocomplete
            :model-value="gunNumberInput"
            :fetch-suggestions="querySearchGunNumbers"
            placeholder="请输入炮号，例如 1-5,7,9-12"
            @select="handleGunNumberSelect"
            @input="handleInput"
            @clear="handleGunNumberClear"
            clearable
        ></el-autocomplete>
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
        >
          <el-option
              v-for="item in channelNameOptions"
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
        >
          <el-option
              v-for="item in errorsNameOptions"
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
      axios.get('https://10.1.108.19:5000/api/get-shot-number-index'),
      axios.get('https://10.1.108.19:5000/api/get-channel-type-index'),
      axios.get('https://10.1.108.19:5000/api/get-channel-name-index'),
      axios.get('https://10.1.108.19:5000/api/get-errors-name-index'),
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

  for (const part of parts) {
    const trimmedPart = part.trim();
    if (!trimmedPart) continue;

    const rangeMatch = trimmedPart.match(/^(\d+)-(\d+)$/);
    if (rangeMatch) {
      const start = parseInt(rangeMatch[1], 10);
      const end = parseInt(rangeMatch[2], 10);
      if (start <= end) {
        for (let i = start; i <= end; i++) {
          if (gunNumberOptions.value.find(option => option.value === i.toString())) {
            numbers.push(i.toString());
          } else {
            // ElMessage.warning(`无效的炮号: ${i}`);
          }
        }
      } else {
        // ElMessage.warning(`无效的范围: ${trimmedPart}`);
      }
    } else {
      const num = trimmedPart;
      if (num) {
        // 验证是否为有效的炮号
        if (gunNumberOptions.value.find(option => option.value === num)) {
          numbers.push(num);
        } else {
          // ElMessage.warning(`无效的炮号: ${num}`);
        }
      }
    }
  }

  // 去重
  selectedGunNumbers.value = Array.from(new Set(numbers));
};

// 处理自动补全建议
const querySearchGunNumbers = debounce((queryString, cb) => {
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
            .filter(item => parseInt(item.value, 10) >= start)
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

  cb(suggestions);
}, 300); // 延迟300ms触发

// 当用户选择自动补全项时，更新输入框的值
const previousInput = ref('');

const handleInput = (value) => {
  previousInput.value = gunNumberInput.value;
  gunNumberInput.value = value;
};

const handleGunNumberSelect = (item) => {
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
};

// 监听输入变化，实时解析输入
watch(gunNumberInput, (newVal) => {
  parseGunNumberInput();
});

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
});

watch(selectedChannelNames, (newNames) => {
  // 清理无效的异常名选择
  selectederrorsNames.value = selectederrorsNames.value.filter(name => {
    return filteredErrorsNameOptions.value.some(option => option.value === name);
  });
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

watch(selectedChannelNames, (newVal) => {
  if (newVal.includes('select-all')) {
    // 如果选中了全选，则选中所有选项（除了全选选项本身）
    selectedChannelNames.value = filteredChannelNameOptions.value.map(option => option.value);
  }
});

watch(selectederrorsNames, (newVal) => {
  if (newVal.includes('select-all')) {
    // 如果选中了全选，则选中所有选项（除了全选选项本身）
    selectederrorsNames.value = filteredErrorsNameOptions.value.map(option => option.value);
  }
});

// 添加清空处理函数
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

onMounted(async () => {
  await fetData();
  // 初始化时所有选择都为空
  selectedChannelNames.value = [];
  selectederrorsNames.value = [];
  store.dispatch('fetchStructTree');
});
</script>

<style scoped lang="scss">
.buttons {
  margin-top: 10px;
  width: 100%;
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
