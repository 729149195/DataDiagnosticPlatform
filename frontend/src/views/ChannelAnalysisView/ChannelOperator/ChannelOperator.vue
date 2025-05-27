<template>
  <span style="
      display: flex;
      justify-content: center;
      align-items: center;
      width: 85%;
    ">
    <!-- 动态渲染下拉菜单按钮 -->
    <template v-for="(button, index) in buttons" :key="index">
      <!-- 分类按钮改为下拉菜单 -->
      <el-dropdown v-if="button.category" trigger="click" @command="handleOperatorSelect">
        <el-button :type="button.type" plain size="large">
          {{ button.label }}
          <el-icon class="el-icon--right">
            <arrow-down />
          </el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item 
              v-for="operator in operators[button.category]" 
              :key="operator"
              :command="operator"
              :class="{ 'imported-func-item': importedFunc.includes(operator) }"
            >
              <span style="display: flex; align-items: center; width: 100%; justify-content: space-between;">
                <span>
                  {{ operator }}
                  <span class="operator-explanation">{{ explanations[operator] || '' }}</span>
                </span>
                <el-icon v-if="importedFunc.includes(operator)" style="margin-left: 10px; color: #f56c6c; cursor: pointer;" @click.stop="confirmDeleteFunc(operator)">
                  <Delete />
                </el-icon>
              </span>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <!-- 其他功能按钮保持不变 -->
      <el-tooltip v-else :content="button.explanation" effect="dark" placement="top">
        <el-button :type="button.type" plain size="large" @click="handleButtonClick(button, index)">
          {{ button.label }}
        </el-button>
      </el-tooltip>
    </template>
    <!-- upload 算法导入按钮 -->
    <el-upload v-model:file-list="fileList" class="upload-demo" action="https://10.1.108.231:5000/api/get-function-params" :on-success="handleUpload" :show-file-list="false" :http-request="handleFileSelect" accept=".py, .m" :limit="3" style="margin-left: 105px;">
      <el-button type="primary" size="large" class="import-button">
        <el-icon style="margin-right: 5px;">
          <Upload />
        </el-icon>
        算法导入
      </el-button>
    </el-upload>


    <el-dialog v-model="dialogVisible" title="文件信息">
      <el-form :model="fileInfo">
        <el-form-item label="文件名称" :label-width="formLabelWidth">
          <el-input v-model="fileInfo.name" autocomplete="off"></el-input>
        </el-form-item>
        <el-form-item label="文件描述" :label-width="formLabelWidth">
          <el-input v-model="fileInfo.description" autocomplete="off"></el-input>
        </el-form-item>
        <el-form-item label="算法类型" :label-width="formLabelWidth">
          <el-select v-model="fileInfo.type" placeholder="请选择算法类型">
            <el-option label="诊断分析" value="诊断分析"></el-option>
            <el-option label="通道运算" value="通道运算"></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="输入参数">
          <el-table :data="fileInfo.input" border>
            <el-table-column label="参数名">
              <template #default="scope">
                <el-input v-model="scope.row.paraName" placeholder="参数名"></el-input>
              </template>
            </el-table-column>
            <el-table-column label="参数类型">
              <template #default="scope">
                <el-select v-model="scope.row.paraType" placeholder="参数类型">
                  <el-option label="整数" value="整数"></el-option>
                  <el-option label="浮点数" value="浮点数"></el-option>
                  <el-option label="字符串" value="字符串"></el-option>
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="参数定义">
              <template #default="scope">
                <el-input v-model="scope.row.paraDefinition" placeholder="参数定义"></el-input>
              </template>
            </el-table-column>
            <el-table-column label="取值范围">
              <template #default="scope">
                <el-input v-model="scope.row.domain" placeholder="取值范围"></el-input>
              </template>
            </el-table-column>
            <el-table-column label="默认值">
              <template #default="scope">
                <el-input v-model="scope.row.default" placeholder="默认值"></el-input>
              </template>
            </el-table-column>
            <el-table-column label="操作">
              <template #default="scope">
                <el-button @click="removeInput(scope.$index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-button type="primary" @click="addInputRow" style="margin-top: 10px;">添加输入参数</el-button>
        </el-form-item>
        <el-form-item label="输出参数">
          <el-table :data="fileInfo.output" border>
            <el-table-column label="输出参数名称">
              <template #default="scope">
                <el-input v-model="scope.row.outputName" placeholder="输出参数名称"></el-input>
              </template>
            </el-table-column>
            <el-table-column label="类型">
              <template #default="scope">
                <el-select v-model="scope.row.type" placeholder="类型">
                  <el-option label="新通道名" value="新通道名"></el-option>
                  <el-option label="通道数据" value="通道数据"></el-option>
                </el-select>
              </template>
            </el-table-column>
            <el-table-column label="定义">
              <template #default="scope">
                <span v-if="scope.row.type !== '新通道名'">
                  <el-input v-model="scope.row.definition" placeholder="定义"></el-input>
                </span>
                <span v-else>
                  <span style="margin-right: 20px">X轴标签:</span><el-input class="special_input" v-model="scope.row.definition.X_label" placeholder="X轴标签"></el-input><br />
                  <span style="margin-right: 20px">X轴单位:</span><el-input class="special_input" v-model="scope.row.definition.X_unit" placeholder="X轴单位"></el-input><br />
                  <span style="margin-right: 20px">Y轴标签:</span><el-input class="special_input" v-model="scope.row.definition.Y_label" placeholder="Y轴标签"></el-input><br />
                  <span style="margin-right: 20px">Y轴单位:</span><el-input class="special_input" v-model="scope.row.definition.Y_unit" placeholder="Y轴单位"></el-input><br />
                </span>
              </template>
            </el-table-column>
            <el-table-column label="操作">
              <template #default="scope">
                <el-button @click="removeOutput(scope.$index)">删除</el-button>
              </template>
            </el-table-column>

          </el-table>
          <el-button type="primary" @click="addOutputRow" style="margin-top: 10px;">添加输出参数</el-button>
        </el-form-item>
      </el-form>
      <span slot="footer" class="dialog-footer">
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit">确认</el-button>
      </span>
    </el-dialog>
  </span>
</template>

<script setup>
import { ref, onMounted } from "vue";
import { useStore } from "vuex";
import axios from "axios";
import { ElMessage, ElMessageBox } from 'element-plus';
import { ArrowDown, Upload, Delete } from '@element-plus/icons-vue';

const store = useStore();

const fileList = ref([]);
const dialogVisible = ref(false);
const fileInfo = ref({
  name: "",
  description: "",
  type: "",
  file: null,
  input: [],
  output: []
})
// const fileInfo = ref({
//     name: 'NoiseThreshold',
//     description: '过滤噪声，产出新数据',
//     type: '通道运算',
//     file: null,
//     input: [
//         { paraName: 'channel_key', paraType: '通道对象', paraDefinition: '炮号', domain: 'None', default: 'None' },
//         { paraName: 'threshold', paraType: '浮点数', paraDefinition: '阈值', domain: 'None', default: 'None' },
//     ],
//     output: [
//         { outputName: 'new_channel_name', type: '新通道名', definition: {
//                 X_label: '时间',
//                 X_unit: 's',
//                 Y_label: '电压',
//                 Y_unit: 'V',
//             }},
//         { outputName: 'channel_data', type: '通道数据', definition: '新通道XY数据' },
//     ]
// });
// const fileInfo = ref({
//     name: 'LargerThanThreshold',
//     description: '绝对值大于阈值的时间段都会被标记',
//     type: '诊断分析',
//     file: null,
//     input: [
//         { paraName: 'channel_key', paraType: '通道对象', paraDefinition: '炮号', domain: 'None', default: 'None' },
//         { paraName: 'threshold', paraType: '浮点数', paraDefinition: '阈值', domain: 'None', default: 'None' },
//     ],
//     output: [
//         { outputName: 'X_range', type: '标注范围', definition: '异常数据的横轴标注范围' },
//     ]
// });
const formLabelWidth = '120px';

// 定义运算符分类
const operators = {
  arithmetic: ["+", "-", "*", "/"],
  // comparison: [">", "<", ">=", "<=", "==", "!="],
  logical: ["&&", "||"],
  functions: ["FFT()"],
  // brackets: ["()", "[]", "{}"],
  da_functions: ["Pca()"],
};

let importedFunc = ref([]);

const handleFileSelect = ({ file }) => {
  fileInfo.value.file = file;
  dialogVisible.value = true;
  console.log(fileInfo.value);
};

const addInputRow = () => {
  fileInfo.value.input.push({ paraName: '', paraType: '', paraDefinition: '', domain: '', default: '' });
};

const removeInput = (index) => {
  fileInfo.value.input.splice(index, 1);
};

const addOutputRow = () => {
  fileInfo.value.output.push({ outputName: '', type: '', definition: '' });
};

const removeOutput = (index) => {
  fileInfo.value.output.splice(index, 1);
};

const handleSubmit = async () => {
  if (!fileInfo.value.name || !fileInfo.value.description || !fileInfo.value.type || !fileInfo.value.file) {
    ElMessage.error('请填写所有必填信息');
    return;
  }

  const formData = new FormData();
  formData.append('file', fileInfo.value.file);
  formData.append('fileInfo', JSON.stringify({
    name: fileInfo.value.name,
    description: fileInfo.value.description,
    type: fileInfo.value.type,
    input: fileInfo.value.input,
    output: fileInfo.value.output,
  }));

  try {
    const response = await axios.post('https://10.1.108.231:5000/api/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    ElMessage.success('文件上传成功');

    let ttda = ["Pca()"]
    let ttcp = ['FFT()']
    // 更新 detect anomaly functions
    const response2 = await axios.get(`https://10.1.108.231:5000/api/view-functions`);
    for (let func of response2.data.imported_functions) {
      if (func.type === '诊断分析') {
        ttda.push(func['name'] + '()')
      }
      else {
        ttcp.push(func['name'] + '()')
      }
    }
    operators['da_functions'] = ttda;
    operators['functions'] = ttcp;

    dialogVisible.value = false;
    importedFunc.value = response2.data.imported_functions.map(d => d['name'] + '()');
  } catch (error) {
    ElMessage.error('文件上传失败');
  }
};



// 更新 detect anomaly functions


// 定义运算符和按钮的解释
const explanations = {
  "+": "加法运算符",
  "-": "减法运算符",
  "*": "乘法运算符",
  "/": "除法运算符",
  "%": "取模运算符",
  "^": "幂运算符",
  ">": "大于比较运算符",
  "<": "小于比较运算符",
  ">=": "大于等于比较运算符",
  "<=": "小于等于比较运算符",
  "==": "等于比较运算符",
  "!=": "不等于比较运算符",
  "&&": "逻辑与运算符",
  "||": "逻辑或运算符",
  "!": "逻辑非运算符",
  "FFT()": "快速傅里叶变换函数",
  "()": "括号",
  "[]": "中括号",
  "{}": "左花括号",
  "Pca()": "主成分分析函数",
  算术运算符: "展开算术运算符",
  比较运算符: "展开比较运算符",
  逻辑运算符: "展开逻辑运算符",
  运算函数: "展开运算函数",
  // 括号: "展开括号",
  诊断函数: "展开诊断函数",
  // 自定义算法: "自定义算法",
  算法导入: "导入算法",
};

// 初始化按钮列表，包含大类按钮和其他功能按钮
const buttons = ref([
  {
    label: "算术运算符",
    type: "primary",
    category: "arithmetic",
    explanation: "选择算术运算符",
  },
  {
    label: "逻辑运算符",
    type: "primary",
    category: "logical",
    explanation: "选择逻辑运算符",
  },
  {
    label: "运算函数",
    type: "primary",
    category: "functions",
    explanation: "选择运算函数",
  },
  {
    label: "诊断函数",
    type: "primary",
    category: "da_functions",
    explanation: "选择诊断函数",
  },
]);

const appendToClickedChannelNames = (content) => {
  store.commit("updateChannelName", content);
};

// 处理下拉菜单中操作符的选择
const handleOperatorSelect = (operator) => {
  appendToClickedChannelNames(operator);
};

const handleButtonClick = async (button, index) => {
  if (button.action === "custom") {
    // 自定义算法的处理逻辑
    // ...
  } else if (button.action === "import") {
    // 算法导入的处理逻辑
    // ...
  }
};

const handleUpload = (files, res) => {
  operators['da_functions'] = operators['da_functions'].concat(res.response.functions.map(d => d['name'] + "()"));
  console.log(res);
};

// 初始化时加载已导入的函数
onMounted(async () => {
  // 更新 detect anomaly functions
  const response = await axios.get(`https://10.1.108.231:5000/api/view-functions`);
  let ttda = ["Pca()"]
  let ttcp = ['FFT()']
  for (let func of response.data.imported_functions) {
    if (func.type === '诊断分析') {
      ttda.push(func['name'] + '()')
    }
    else {
      ttcp.push(func['name'] + '()')
    }
  }
  operators['da_functions'] = ttda;
  operators['functions'] = ttcp;
  importedFunc.value = response.data.imported_functions.map(d => d['name'] + '()');
});

// 删除自定义算法
const confirmDeleteFunc = (operator) => {
  const funcName = operator.replace(/\(\)$/,'');
  ElMessageBox.confirm(
    `确定要删除算法 "${funcName}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    }
  ).then(async () => {
    try {
      await axios.post('https://10.1.108.231:5000/api/delete-function', { function_name: funcName });
      ElMessage.success('删除成功');
      // 刷新导入函数列表
      const response2 = await axios.get(`https://10.1.108.231:5000/api/view-functions`);
      let ttda = ["Pca()"]
      let ttcp = ['FFT()']
      for (let func of response2.data.imported_functions) {
        if (func.type === '诊断分析') {
          ttda.push(func['name'] + '()')
        }
        else {
          ttcp.push(func['name'] + '()')
        }
      }
      operators['da_functions'] = ttda;
      operators['functions'] = ttcp;
      importedFunc.value = response2.data.imported_functions.map(d => d['name'] + '()');
    } catch (error) {
      ElMessage.error('删除失败');
    }
  }).catch(() => {});
};

</script>

<style scoped lang="scss">
.special_input {
  display: inline-block;
  width: 60%;
}

.importedFunc {
  background: lightpink;
  color: deeppink;
}

// 下拉菜单项样式
:deep(.el-dropdown-menu__item) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  
  .operator-explanation {
    font-size: 12px;
    color: #909399;
    margin-left: 10px;
  }
}

// 导入函数的高亮样式（element主题蓝色色系）
:deep(.imported-func-item) {
  background-color: rgba(64, 158, 255, 0.15) !important; // element主题蓝色
  color: #409EFF !important; // element主题主色
  font-weight: 500;

  &:hover {
    background-color: rgba(64, 158, 255, 0.25) !important;
  }
}

// 下拉按钮样式
.el-dropdown {
  margin-right: 8px;
  
  .el-button {
    border: 1px solid #dcdfe6;
    background-color: #ffffff;
    transition: all 0.3s ease;
    
    &:hover {
      border-color: #409eff;
      color: #409eff;
      background-color: #ecf5ff;
    }
  }
}

// 算法导入按钮特殊样式
.import-button {
  background: linear-gradient(135deg, #409eff 0%, #66b3ff 100%) !important;
  border: none !important;
  box-shadow: 0 2px 8px rgba(64, 158, 255, 0.3) !important;
  transition: all 0.3s ease !important;
  
  &:hover {
    background: linear-gradient(135deg, #66b3ff 0%, #85c5ff 100%) !important;
    box-shadow: 0 4px 12px rgba(64, 158, 255, 0.4) !important;
    transform: translateY(-1px) !important;
  }
  
  &:active {
    transform: translateY(0) !important;
    box-shadow: 0 2px 6px rgba(64, 158, 255, 0.3) !important;
  }
}

// 为算法导入按钮添加分隔线
.upload-demo {
  position: relative;
  
  &::before {
    content: '';
    position: absolute;
    left: -52px;
    top: 50%;
    transform: translateY(-50%);
    width: 2px;
    height: 24px;
    background: linear-gradient(to bottom, transparent, #e4e7ed, transparent);
  }
}
</style>