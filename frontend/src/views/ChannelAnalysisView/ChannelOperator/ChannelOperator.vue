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
      <el-tooltip v-else :content="button.explanation" effect="light" placement="top">
        <el-button :type="button.type" plain size="large" @click="handleButtonClick(button, index)">
          {{ button.label }}
        </el-button>
      </el-tooltip>
    </template>
    <!-- upload 算法导入按钮 -->
    <el-upload v-model:file-list="fileList" class="upload-demo" :show-file-list="false" :http-request="handleFileSelect" accept=".py, .m" :limit="3" style="margin-left: 105px;">
      <el-button type="primary" size="large" class="import-button">
        <el-icon style="margin-right: 5px;">
          <Upload />
        </el-icon>
        算法导入
      </el-button>
    </el-upload>


    <el-dialog v-model="dialogVisible" title="文件信息">
      <el-form :model="fileInfo" label-position="left">
        <el-form-item label="文件名称 *" >
          <el-input v-model="fileInfo.name" autocomplete="off"></el-input>
        </el-form-item>
        <el-form-item label="文件描述 *" >
          <el-input v-model="fileInfo.description" autocomplete="off"></el-input>
        </el-form-item>
        <el-form-item label="算法类型 *" >
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
            <el-table-column label="操作" align="right">
              <template #default="scope">
                <el-button @click="removeInput(scope.$index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="add-param-container">
            <el-button type="primary" @click="addInputRow">添加输入参数</el-button>
          </div>
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
            <el-table-column label="操作" align="right">
              <template #default="scope">
                <el-button @click="removeOutput(scope.$index)">删除</el-button>
              </template>
            </el-table-column>

          </el-table>
          <div class="add-param-container">
            <el-button type="primary" @click="addOutputRow">添加输出参数</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit">确认</el-button>
        </div>
      </template>
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

// 解析文件内容，提取函数参数和返回值信息
const parseFileContent = (content, fileName) => {
  const result = {
    input: [],
    output: []
  };
  
  if (fileName.endsWith('.py')) {
    // 解析Python文件
    return parsePythonFile(content);
  } else if (fileName.endsWith('.m')) {
    // 解析MATLAB文件
    return parseMatlabFile(content);
  }
  
  return result;
};

// 解析Python文件
const parsePythonFile = (content) => {
  const result = {
    input: [],
    output: []
  };
  
  try {
    // 查找函数定义（支持多行和不同格式）
    const lines = content.split('\n');
    let functionFound = false;
    let functionLine = '';
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('def ') && line.includes('(')) {
        functionLine = line;
        // 检查是否是多行函数定义
        while (!functionLine.includes('):') && i < lines.length - 1) {
          i++;
          functionLine += ' ' + lines[i].trim();
        }
        functionFound = true;
        break;
      }
    }
    
    if (functionFound) {
      const functionRegex = /def\s+(\w+)\s*\(([^)]*)\):/;
      const match = functionRegex.exec(functionLine);
      
      if (match) {
        const params = match[2].trim();
        if (params) {
          // 解析参数列表
          const paramList = params.split(',').map(p => p.trim()).filter(p => p && p !== 'self');
          
          paramList.forEach(param => {
            // 移除默认值
            let paramName = param.split('=')[0].trim();
            // 移除类型注解
            paramName = paramName.split(':')[0].trim();
            // 移除星号（*args, **kwargs）
            paramName = paramName.replace(/^\*+/, '');
            
            if (paramName && paramName !== 'args' && paramName !== 'kwargs') {
              result.input.push({
                paraName: paramName,
                paraType: guessParameterType(paramName),
                paraDefinition: '',
                domain: '',
                default: extractDefaultValue(param)
              });
            }
          });
        }
      }
    }
    
    // 查找return语句来推断输出
    const returnRegex = /return\s+(.+)/g;
    const returnMatches = [...content.matchAll(returnRegex)];
    
    if (returnMatches.length > 0) {
      // 取最后一个return语句
      const lastReturn = returnMatches[returnMatches.length - 1][1].trim();
      
      // 移除注释
      const returnValue = lastReturn.split('#')[0].trim();
      
      // 简单解析return的内容
      if (returnValue.includes(',') && !returnValue.includes('(')) {
        // 多个返回值（排除元组情况）
        const returnValues = returnValue.split(',').map(v => v.trim()).filter(v => v);
        returnValues.forEach((value, index) => {
          // 判断是否为简单变量名（只包含字母、数字、下划线）
          const isSimpleVariable = /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(value);
          const outputName = isSimpleVariable ? value : `output_${index + 1}`;
          
          result.output.push({
            outputName: outputName,
            type: '通道数据',
            definition: ''
          });
        });
      } else {
        // 单个返回值或元组
        let outputName = 'result';
        if (returnValue && returnValue !== 'None') {
          // 判断是否为简单变量名
          const isSimpleVariable = /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(returnValue);
          outputName = isSimpleVariable ? returnValue : 'result';
        }
        result.output.push({
          outputName: outputName,
          type: '通道数据',
          definition: ''
        });
      }
    }
  } catch (error) {
    console.error('解析Python文件时出错:', error);
  }
  
  return result;
};

// 解析MATLAB文件
const parseMatlabFile = (content) => {
  const result = {
    input: [],
    output: []
  };
  
  try {
    // 查找function定义（支持多行）
    const lines = content.split('\n');
    let functionFound = false;
    let functionLine = '';
    
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      if (line.startsWith('function ') && line.includes('(')) {
        functionLine = line;
        // 检查是否是多行函数定义
        while (!functionLine.includes(')') && i < lines.length - 1) {
          i++;
          functionLine += ' ' + lines[i].trim();
        }
        functionFound = true;
        break;
      }
    }
    
    if (functionFound) {
      // 更灵活的正则表达式来匹配不同的function格式
      const functionRegex = /function\s*(?:\[([^\]]+)\]\s*=\s*|(\w+)\s*=\s*)?(\w+)\s*\(([^)]*)\)/;
      const match = functionRegex.exec(functionLine);
      
      if (match) {
        // 解析输入参数
        const inputParams = match[4];
        if (inputParams.trim()) {
          const paramList = inputParams.split(',').map(p => p.trim()).filter(p => p);
          
          paramList.forEach(param => {
            // 移除可能的默认值（虽然MATLAB函数定义通常不在参数列表中设置默认值）
            const paramName = param.split('=')[0].trim();
            if (paramName) {
              result.input.push({
                paraName: paramName,
                paraType: guessParameterType(paramName),
                paraDefinition: '',
                domain: '',
                default: extractDefaultValue(param)
              });
            }
          });
        }
        
        // 解析输出参数
        const outputParams = match[1] || match[2];
        if (outputParams) {
          if (outputParams.includes(',')) {
            // 多个输出
            const outputList = outputParams.split(',').map(p => p.trim()).filter(p => p);
            outputList.forEach(output => {
              result.output.push({
                outputName: output,
                type: '通道数据',
                definition: ''
              });
            });
          } else {
            // 单个输出
            result.output.push({
              outputName: outputParams.trim(),
              type: '通道数据',
              definition: ''
            });
          }
        } else {
          // 如果没有明确的输出参数，添加一个默认的
          result.output.push({
            outputName: 'result',
            type: '通道数据',
            definition: ''
          });
        }
      }
    }
  } catch (error) {
    console.error('解析MATLAB文件时出错:', error);
  }
  
  return result;
};

// 根据参数名猜测参数类型
const guessParameterType = (paramName) => {
  const name = paramName.toLowerCase();
  
  if (name.includes('channel') || name.includes('data')) {
    return '通道对象';
  } else if (name.includes('threshold') || name.includes('rate') || name.includes('freq')) {
    return '浮点数';
  } else if (name.includes('count') || name.includes('num') || name.includes('size') || name.includes('index')) {
    return '整数';
  } else if (name.includes('name') || name.includes('label') || name.includes('title')) {
    return '字符串';
  } else {
    return '浮点数'; // 默认类型
  }
};

// 提取参数默认值
const extractDefaultValue = (param) => {
  if (param.includes('=')) {
    const defaultValue = param.split('=')[1].trim();
    // 移除引号
    return defaultValue.replace(/['"]/g, '');
  }
  return '';
};

const handleFileSelect = ({ file }) => {
  // 重置文件信息
  fileInfo.value = {
    name: "",
    description: "",
    type: "",
    file: null,
    input: [],
    output: []
  };
  
  fileInfo.value.file = file;
  
  // 自动填充文件名称（去掉扩展名）
  const fileName = file.name.replace(/\.(py|m)$/, '');
  fileInfo.value.name = fileName;
  
  // 读取文件内容并解析参数
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const content = e.target.result;
      const parsedInfo = parseFileContent(content, file.name);
      
      // 预填充解析出的参数信息
      if (parsedInfo.input.length > 0) {
        fileInfo.value.input = parsedInfo.input;
      }
      if (parsedInfo.output.length > 0) {
        fileInfo.value.output = parsedInfo.output;
      }
      
      // 提供详细的解析结果反馈
      const inputCount = parsedInfo.input.length;
      const outputCount = parsedInfo.output.length;
      let message = '文件解析完成！';
      
      if (inputCount > 0 || outputCount > 0) {
        message += ` 已自动识别 ${inputCount} 个输入参数和 ${outputCount} 个输出参数`;
      } else {
        message += ' 未识别到函数参数，请手动添加';
      }
      
      ElMessage.success(message);
    } catch (error) {
      console.error('文件读取错误:', error);
      ElMessage.error('文件读取失败，请检查文件格式');
    }
  };
  
  reader.onerror = () => {
    ElMessage.error('文件读取失败');
  };
  
  reader.readAsText(file, 'UTF-8');
  
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
  // 检查必填项
  if (!fileInfo.value.name) {
    ElMessage.error('请填写文件名称');
    return;
  }
  if (!fileInfo.value.description) {
    ElMessage.error('请填写文件描述');
    return;
  }
  if (!fileInfo.value.type) {
    ElMessage.error('请选择算法类型');
    return;
  }
  if (!fileInfo.value.file) {
    ElMessage.error('请选择要上传的文件');
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

    // 更新 detect anomaly functions
    const response2 = await axios.get(`https://10.1.108.231:5000/api/view-functions`);

    // 保留内置函数，追加导入的函数
    let importedDaFunctions = [];
    let importedChannelFunctions = [];

    for (let func of response2.data.imported_functions) {
      const displayName = getFunctionDisplayName(func);
      if (func.type === '诊断分析') {
        importedDaFunctions.push(displayName);
      }
      else {
        importedChannelFunctions.push(displayName);
      }
    }

    // 将导入的函数追加到内置函数后面
    operators['da_functions'] = ["Pca()"].concat(importedDaFunctions);
    operators['functions'] = ["FFT()"].concat(importedChannelFunctions);

    dialogVisible.value = false;
    importedFunc.value = response2.data.imported_functions.map(d => getFunctionDisplayName(d));
    
    // 发送函数上传事件，通知其他组件刷新函数列表
    window.dispatchEvent(new CustomEvent('functionUploaded'));
  } catch (error) {
    // 检查是否是后端返回的具体错误信息
    if (error.response && error.response.data && error.response.data.error) {
      ElMessage.error(error.response.data.error);
    } else {
      ElMessage.error('文件上传失败');
    }
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



// 辅助函数：根据文件路径获取函数类型标识
const getFunctionTypeLabel = (filePath) => {
  if (filePath && filePath.endsWith('.py')) {
    return 'Py';
  } else if (filePath && filePath.endsWith('.m')) {
    return 'M';
  }
  return '';
};

// 辅助函数：生成带类型标识的函数显示名
const getFunctionDisplayName = (func) => {
  const typeLabel = getFunctionTypeLabel(func.file_path);
  return typeLabel ? `${func.name}() [${typeLabel}]` : `${func.name}()`;
};

// 初始化时加载已导入的函数
onMounted(async () => {
  // 更新 detect anomaly functions
  const response = await axios.get(`https://10.1.108.231:5000/api/view-functions`);

  // 保留内置函数，追加导入的函数
  let importedDaFunctions = [];
  let importedChannelFunctions = [];

  for (let func of response.data.imported_functions) {
    const displayName = getFunctionDisplayName(func);
    if (func.type === '诊断分析') {
      importedDaFunctions.push(displayName);
    }
    else {
      importedChannelFunctions.push(displayName);
    }
  }

  // 将导入的函数追加到内置函数后面
  operators['da_functions'] = ["Pca()"].concat(importedDaFunctions);
  operators['functions'] = ["FFT()"].concat(importedChannelFunctions);
  importedFunc.value = response.data.imported_functions.map(d => getFunctionDisplayName(d));
});

// 删除自定义算法
const confirmDeleteFunc = (operator) => {
  // 提取函数名，去掉 () 和类型标识 [Py] 或 [M]
  const funcName = operator.replace(/\(\)\s*\[.*?\]$/, '').replace(/\(\)$/, '');
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

      // 保留内置函数，追加导入的函数
      let importedDaFunctions = [];
      let importedChannelFunctions = [];

      for (let func of response2.data.imported_functions) {
        const displayName = getFunctionDisplayName(func);
        if (func.type === '诊断分析') {
          importedDaFunctions.push(displayName);
        }
        else {
          importedChannelFunctions.push(displayName);
        }
      }

      // 将导入的函数追加到内置函数后面
      operators['da_functions'] = ["Pca()"].concat(importedDaFunctions);
      operators['functions'] = ["FFT()"].concat(importedChannelFunctions);
      importedFunc.value = response2.data.imported_functions.map(d => getFunctionDisplayName(d));
      
      // 发送函数删除事件，通知其他组件刷新函数列表
      window.dispatchEvent(new CustomEvent('functionDeleted'));
    } catch (error) {
      // 检查是否是后端返回的具体错误信息
      if (error.response && error.response.data && error.response.data.error) {
        ElMessage.error(error.response.data.error);
      } else {
        ElMessage.error('删除失败');
      }
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

// 对话框底部按钮右对齐
.dialog-footer {
  text-align: right;
}

// 表单标签左对齐
:deep(.el-form-item__label) {
  text-align: left !important;
}

// 添加参数按钮右对齐
.add-param-container {
  text-align: right !important;
  margin-top: 10px !important;
  display: block !important;
}
</style>