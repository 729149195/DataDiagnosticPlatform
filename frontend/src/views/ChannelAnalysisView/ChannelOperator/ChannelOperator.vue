<template>
  <span
          style="
      display: flex;
      justify-content: center;
      align-items: center;
      width: 85%;
    "
          @click.stop="collapseAllCategories"
  >
    <!-- 动态渲染按钮 -->
    <template v-for="(button, index) in buttons" :key="index">
      <!-- Non-separator buttons with tooltips -->
      <el-tooltip
              v-if="!button.isSeparator && button.action !== 'import'"
              :content="button.explanation"
              effect="dark"
              placement="top"
      >
        <el-button
                :type="button.type"
                plain
                size="large"
                @click.stop="handleButtonClick(button, index)"
        >
          {{ button.label }}
        </el-button>
      </el-tooltip>

        <!-- Separator buttons -->
      <el-button v-else link plain size="large" style="color: gray" disabled>
        {{ button.label }}
      </el-button>
    </template>
      <!-- upload 算法导入按钮 -->
    <el-upload
            v-model:file-list="fileList"
            class="upload-demo"
            action=""
            :on-success="handleUpload"
            :show-file-list="false"
            :http-request="handleFileSelect"
            accept=".py, .m"
            :limit="3"
            style="margin-left: 105px;"
    >
      <el-button type="primary" plain
                 size="large">算法导入</el-button>
        <!--      <template #tip>-->
        <!--&lt;!&ndash;        <div class="el-upload__tip">&ndash;&gt;-->
        <!--&lt;!&ndash;          jpg/png files with a size less than 500KB.&ndash;&gt;-->
        <!--&lt;!&ndash;        </div>&ndash;&gt;-->
        <!--      </template>-->
    </el-upload>
    
    
    <el-dialog v-model="dialogVisible" title="文件信息">
    <el-form :model="fileInfo">
      <el-form-item label="文件名称" :label-width="formLabelWidth">
        <el-input v-model="fileInfo.name" autocomplete="off"></el-input>
      </el-form-item>
      <el-form-item label="文件描述" :label-width="formLabelWidth">
        <el-input v-model="fileInfo.description" autocomplete="off"></el-input>
      </el-form-item>
      <el-form-item label="文件类型" :label-width="formLabelWidth">
        <el-select v-model="fileInfo.type" placeholder="请选择文件类型">
<!--          <el-option label="运算" value="运算"></el-option>-->
          <el-option label="导入" value="导入"></el-option>
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
              <el-button size="mini" @click="removeInput(scope.$index)">删除</el-button>
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
              <el-input v-model="scope.row.definition" placeholder="定义"></el-input>
            </template>
          </el-table-column>
          <el-table-column label="操作">
            <template #default="scope">
              <el-button size="mini" @click="removeOutput(scope.$index)">删除</el-button>
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
import { ref, onMounted, onBeforeUnmount } from "vue";
import { useStore } from "vuex";
import axios from "axios";
import { ElMessage } from 'element-plus';

const store = useStore();

const fileList = ref([]);
const dialogVisible = ref(false);
// const fileInfo = ref({
//     name: 'NoiseThreshold',
//     description: '过滤噪声，产出新数据',
//     type: '导入',
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
const fileInfo = ref({
    name: 'LargerThanThreshold',
    description: '绝对值大于阈值的时间段都会被标记',
    type: '导入',
    file: null,
    input: [
        { paraName: 'channel_key', paraType: '通道对象', paraDefinition: '炮号', domain: 'None', default: 'None' },
        { paraName: 'threshold', paraType: '浮点数', paraDefinition: '阈值', domain: 'None', default: 'None' },
    ],
    output: [
        { outputName: 'X_range', type: '标注范围', definition: '异常数据的横轴标注范围' },
    ]
});
const formLabelWidth = '120px';

const handleFileSelect = ({ file }) => {
    fileInfo.value.file = file;
    dialogVisible.value = true;
    console.log('xxxx')
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
        const response = await axios.post('http://localhost:5000/api/upload/', formData, {
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
        ElMessage.success('文件上传成功');

        let tt = ["Pca()"]
        // 更新 detect anomaly functions
        const response2 = await axios.get(`http://localhost:5000/api/view-functions/`);
        operators['da_functions'] = tt.concat(response2.data.imported_functions.map(d => d['name']+'()'));
        dialogVisible.value = false;
    } catch (error) {
        ElMessage.error('文件上传失败');
    }
};

// 定义运算符分类
const operators = {
    arithmetic: ["+", "-", "*", "/", "%", "^", "()"],
    comparison: [">", "<", ">=", "<=", "==", "!="],
    logical: ["&&", "||", "!"],
    functions: ["FFT()", "sin()", "cos()", "tan()", "log()"],
    // brackets: ["()", "[]", "{}"],
    da_functions: ["Pca()"],
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
    "sin()": "正弦函数",
    "cos()": "余弦函数",
    "tan()": "正切函数",
    "log()": "对数函数",
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
    自定义算法: "自定义算法",
    算法导入: "导入算法",
};

// 初始化按钮列表，包含大类按钮和其他功能按钮
const buttons = ref([
    {
        label: "算术运算符",
        type: "primary",
        category: "arithmetic",
        explanation: "展开算术运算符",
    },
    {
        label: "比较运算符",
        type: "primary",
        category: "comparison",
        explanation: "展开比较运算符",
    },
    {
        label: "逻辑运算符",
        type: "primary",
        category: "logical",
        explanation: "展开逻辑运算符",
    },
    {
        label: "运算函数",
        type: "primary",
        category: "functions",
        explanation: "展开运算函数",
    },
    // {
    //     label: "括号",
    //     type: "primary",
    //     category: "brackets",
    //     explanation: "展开括号",
    // },
    {
        label: "诊断函数",
        type: "primary",
        category: "da_functions",
        explanation: "展开诊断函数",
    },
    {
        label: "自定义算法",
        type: "info",
        action: "custom",
        explanation: "自定义算法",
    },
    // {
    //   label: "算法导入",
    //   type: "success",
    //   action: "import",
    //   explanation: "导入算法",
    // },
]);

// 记录哪些分类已经展开
const expandedCategories = ref({});

const appendToClickedChannelNames = (content) => {
    store.commit("updateChannelName", content);
};

const handleButtonClick = async (button, index) => {
    if (button.category) {
        // 判断分类是否已展开
        if (expandedCategories.value[button.category]) {
            // 已展开，需收起
            collapseCategory(button.category, index);
        } else {
            // 未展开，需展开
            expandCategory(button.category, index);
        }
    } else if (button.content) {
        // 操作符按钮，执行添加操作并收起分类
        appendToClickedChannelNames(button.content);
        collapseAllCategories();
    } else if (button.action === "custom") {
        // 自定义算法的处理逻辑
        // ...
    } else if (button.action === "import") {
        // const file = event.target.files[0];
        // const formData = new FormData();
        // formData.append("file", file);
        // try {
        //     const response = await axios.post("http://localhost:5000/api/upload/", formData, {
        //         headers: { "Content-Type": "multipart/form-data" }
        //     });
        //     functions.value = response.data.functions;
        //     console.log(functions.value);
        // } catch (error) {
        //     console.error("File upload error:", error);
        // }
    }
};

const handleUpload = (files, res) => {
    operators['da_functions'] = operators['da_functions'].concat(res.response.functions.map(d => d['name']+"()"));
    console.log(functions.value);
};

const expandCategory = (category, index) => {
    const operatorButtons = [
        { label: "▶", disabled: true, isSeparator: true }, // 左侧分隔符
        ...operators[category].map((op) => ({
            label: op,
            type: "primary",
            content: op,
            explanation: explanations[op] || "",
        })),
        { label: "◀", disabled: true, isSeparator: true }, // 右侧分隔符
    ];

    // 在按钮列表中替换分类按钮为其操作符按钮，并添加分隔符
    buttons.value.splice(index, 1, ...operatorButtons);
    expandedCategories.value[category] = true;
};

const collapseCategory = (category, index) => {
    const categoryButton = {
        label: getCategoryLabel(category),
        type: "primary",
        category: category,
        explanation: getCategoryExplanation(category),
    };
    // 获取该分类下操作符和分隔符的数量
    const operatorCount = operators[category].length + 2;
    // 在按钮列表中替换操作符按钮为分类按钮
    buttons.value.splice(index, operatorCount, categoryButton);
    expandedCategories.value[category] = false;
};

const collapseAllCategories = () => {
    // 重置按钮列表
    buttons.value = [
        {
            label: "算术运算符",
            type: "primary",
            category: "arithmetic",
            explanation: "展开算术运算符",
        },
        {
            label: "比较运算符",
            type: "primary",
            category: "comparison",
            explanation: "展开比较运算符",
        },
        {
            label: "逻辑运算符",
            type: "primary",
            category: "logical",
            explanation: "展开逻辑运算符",
        },
        {
            label: "运算函数",
            type: "primary",
            category: "functions",
            explanation: "展开运算函数",
        },
        // {
        //     label: "括号",
        //     type: "primary",
        //     category: "brackets",
        //     explanation: "展开括号",
        // },
        {
            label: "诊断函数",
            type: "primary",
            category: "da_functions",
            explanation: "展开诊断函数",
        },
        {
            label: "自定义算法",
            type: "info",
            action: "custom",
            explanation: "自定义算法",
        },
        // {
        //   label: "算法导入",
        //   type: "success",
        //   action: "import",
        //   explanation: "导入算法",
        // },
    ];
    expandedCategories.value = {};
};

// 点击空白区域关闭所有展开
const handleClickOutside = (event) => {
    collapseAllCategories();
};

// 设置点击空白区域监听器
onMounted(async () => {
    document.addEventListener("click", handleClickOutside);

    // 更新 detect anomaly functions
    const response = await axios.get(`http://localhost:5000/api/view-functions/`);
    operators['da_functions'] = operators['da_functions'].concat(response.data.imported_functions.map(d => d['name']+'()'));
    console.log('xxx');
});

// 移除点击空白区域监听器
onBeforeUnmount(() => {
    document.removeEventListener("click", handleClickOutside);
});

// 根据分类获取对应的按钮标签
const getCategoryLabel = (category) => {
    const labels = {
        arithmetic: "算术运算符",
        comparison: "比较运算符",
        logical: "逻辑运算符",
        functions: "运算函数",
        // brackets: "括号",
        da_functions: "诊断函数",
    };
    return labels[category];
};

// 根据分类获取解释
const getCategoryExplanation = (category) => {
    const explanations = {
        arithmetic: "展开算术运算符",
        comparison: "展开比较运算符",
        logical: "展开逻辑运算符",
        functions: "展开运算函数",
        // brackets: "展开括号",
        da_functions: "展开诊断函数",
    };
    return explanations[category] || "";
};
</script>

<style scoped lang="scss"></style>
