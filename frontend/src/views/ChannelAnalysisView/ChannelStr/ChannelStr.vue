<template>
    <div>
        <div class="editable-div" contenteditable="true" spellcheck="false" @input="onInput" @click="updateCursorPosition" @keyup="updateCursorPosition" @keydown="updateCursorPosition" @focus="updateCursorPosition"></div>
        <span style="position: absolute; bottom: 8px; right: 8px;">
            <!--            <span style="margin-right: 30px">{{output}}</span>-->

            <!-- <el-button type="primary">
                <FolderChecked />
                记录公式
            </el-button> -->
            <el-button type="primary" @click="sendClickedChannelNames" :loading="isCalculating">
                <Cpu />
                计算
            </el-button>
            <el-button type="danger" @click="clearFormulas">
                <CloseBold />
                清空
            </el-button>
        </span>
        
        <!-- 函数详情tooltip -->
        <div
            v-if="showFunctionTooltip && currentFunctionInfo"
            class="function-tooltip"
            :style="{
                left: tooltipPosition.x + 'px',
                top: tooltipPosition.y + 'px'
            }"
            @mouseenter="showFunctionTooltip = true"
            @mouseleave="showFunctionTooltip = false"
        >
            <div class="tooltip-content">
                <!-- 只显示带前缀函数的详细信息 -->
                <div class="function-header">
                    <h4 class="function-name-title">
                        {{ currentFunctionInfo.name }}
                    </h4>
                </div>

                <!-- 标识标签行 -->
                <div class="function-tags">
                    <span v-if="currentFunctionInfo.typeLabel"
                          :class="['function-type-prefix', `type-${currentFunctionInfo.typeLabel.toLowerCase().replace('-', '')}`]">
                        [{{ currentFunctionInfo.typeLabel }}]
                    </span>
                    <span class="function-type">{{ currentFunctionInfo.type }}</span>
                </div>

                <div class="function-description">
                    <strong>说明：</strong>{{ currentFunctionInfo.description }}
                </div>

                <div class="function-params" v-if="currentFunctionInfo.input && currentFunctionInfo.input.length > 0">
                    <strong>输入参数：</strong>
                    <div class="param-list">
                        <div
                            v-for="(param, index) in currentFunctionInfo.input"
                            :key="index"
                            class="param-item"
                        >
                            <span class="param-name">{{ param.paraName }}</span>
                            <span class="param-type">({{ param.paraType }})</span>
                            <span class="param-definition">{{ param.paraDefinition }}</span>
                            <span v-if="param.default && param.default !== 'None'" class="param-default">
                                默认值: {{ param.default }}
                            </span>
                        </div>
                    </div>
                </div>

                <div class="function-output" v-if="currentFunctionInfo.output && currentFunctionInfo.output.length > 0">
                    <strong>输出结果：</strong>
                    <div class="output-list">
                        <div
                            v-for="(output, index) in currentFunctionInfo.output"
                            :key="index"
                            class="output-item"
                        >
                            <span class="output-name">{{ output.outputName }}</span>
                            <span class="output-type">({{ output.type }})</span>
                            <span class="output-definition">{{ typeof output.definition === 'string' ? output.definition : JSON.stringify(output.definition) }}</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { useStore } from 'vuex';
import { FolderChecked, Cpu, CloseBold } from '@element-plus/icons-vue';
import axios from 'axios';

const store = useStore();

const formulasarea = ref('');

const operators = ref('');

const output = ref('');

// 计算状态
const isCalculating = computed(() => store.state.isCalculating);

let currentCursorPosition = 0; // 用于记录光标位置

// 导入的函数列表
const importedFunctions = ref([]);

// 函数详情弹窗相关
const showFunctionTooltip = ref(false);
const tooltipPosition = ref({ x: 0, y: 0 });
const currentFunctionInfo = ref(null);

// 定义内置函数的详细信息
const builtInFunctions = ref({
    'FFT': {
        name: 'FFT',
        type: '信号处理',
        description: '对输入信号进行快速傅里叶变换，将时域信号转换为频域表示',
        input: [
            {
                paraName: 'channel',
                paraType: '通道对象',
                paraDefinition: '输入通道数据，包含时间序列信号',
                domain: '任何数值通道',
                default: ''
            },
            {
                paraName: 'frequency_limit',
                paraType: '浮点数',
                paraDefinition: '频率上限，用于限制FFT结果的频率范围(Hz)',
                domain: '0.1-10000',
                default: '1000'
            }
        ],
        output: [
            {
                outputName: 'frequency_spectrum',
                type: '频域数据',
                definition: '频率-幅值对应关系，X轴为频率(Hz)，Y轴为幅值'
            }
        ]
    },
    'Pca': {
        name: 'Pca',
        type: '数据分析',
        description: '主成分分析，用于数据降维和特征提取，识别数据中的主要变化模式',
        input: [
            {
                paraName: 'channel',
                paraType: '通道对象',
                paraDefinition: '输入通道数据进行主成分分析',
                domain: '任何数值通道',
                default: ''
            },
            {
                paraName: 'n_components',
                paraType: '整数',
                paraDefinition: '保留的主成分数量',
                domain: '1-10',
                default: '2'
            },
            {
                paraName: 'window_size',
                paraType: '整数',
                paraDefinition: '滑动窗口大小，用于分段分析',
                domain: '10-1000',
                default: '100'
            }
        ],
        output: [
            {
                outputName: 'principal_components',
                type: '降维数据',
                definition: '主成分数据，X轴为时间，Y轴为第一主成分值'
            }
        ]
    }
});

// 更新光标位置
const updateCursorPosition = () => {
    const editableDiv = document.querySelector('.editable-div');
    if (editableDiv) {
        currentCursorPosition = getCaretCharacterOffsetWithin(editableDiv);
    }
};


const selectedChannels = computed(() => store.state.selectedChannels);

const clickedChannelNames = computed(() => store.state.clickedChannelNames);

const CalculateResult = computed(() => store.state.CalculateResult);

onMounted(async () => {
    // 获取导入的函数列表
    await loadImportedFunctions();
    // 在函数列表加载后进行高亮
    highlightChannels();

    // 监听函数上传事件
    window.addEventListener('functionUploaded', handleFunctionUploaded);
    window.addEventListener('functionDeleted', handleFunctionDeleted);
});

onUnmounted(() => {
    formulasarea.value = '';
    store.commit("updateChannelName", '');
    // 清理tooltip
    showFunctionTooltip.value = false;
    
    // 移除事件监听器
    window.removeEventListener('functionUploaded', handleFunctionUploaded);
    window.removeEventListener('functionDeleted', handleFunctionDeleted);
});

// 辅助函数：根据文件路径获取函数类型标识（在 highlightChannels 中使用）
const getFunctionTypeLabel = (filePath) => {
    if (filePath && filePath.endsWith('.py')) {
        return 'Python';
    } else if (filePath && filePath.endsWith('.m')) {
        return 'Matlab';
    }
    return '';
};

const highlightChannels = () => {
    const editableDiv = document.querySelector('.editable-div');
    if (!editableDiv) return;

    const content = formulasarea.value;
    const channelIdentifiers = selectedChannels.value.map((channel) =>
        `${channel.channel_name}_${channel.shot_number}`
    );
    const colors = selectedChannels.value.reduce((acc, channel) => {
        acc[`${channel.channel_name}_${channel.shot_number}`] = channel.color;
        return acc;
    }, {});

    // 获取带前缀的函数显示名称列表（不包括括号，用于高亮识别）
    const functionDisplayNames = [];

    importedFunctions.value.forEach(func => {
        const typeLabel = getFunctionTypeLabel(func.file_path);
        if (typeLabel) {
            // 添加紧凑格式（用于高亮识别）：[Python]functionName
            functionDisplayNames.push(`[${typeLabel}]${func.name}`);
        }
    });

    const tokens = tokenizeContent(content, channelIdentifiers, functionDisplayNames, importedFunctions.value);

    // 简单函数列表（如FFT, Pca等）
    const simpleFunctions = ['FFT', 'Pca']; // 可以根据需要扩展

    const highlightedContent = tokens
        .map((token) => {
            // 处理字符串 token
            if (channelIdentifiers.includes(token)) {
                const color = colors[token] || '#409EFF';
                return `<span class="tag" style="background-color: ${color};">${token}</span>`;
            } else if (functionDisplayNames.includes(token)) {
                // 只处理带前缀的函数名匹配（不包括括号）
                const match = token.match(/^\[(\w+)\](.+)$/);
                if (match) {
                    const [, typeLabel, funcName] = match;
                    const matchingFunction = importedFunctions.value.find(func =>
                        func.name === funcName && getFunctionTypeLabel(func.file_path) === typeLabel
                    );
                    if (matchingFunction) {
                        const functionData = JSON.stringify([matchingFunction]).replace(/"/g, '&quot;');
                        return `<span class="function-name" data-function-name="${funcName}" data-function-type="${typeLabel}" data-function-list="${functionData}" style="color: #409EFF; font-weight: bold; cursor: help; text-decoration: underline;">${token}</span>`;
                    }
                }
                return token.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            } else if (simpleFunctions.includes(token)) {
                // 处理简单函数名（如FFT, Pca）
                const functionData = JSON.stringify([builtInFunctions.value[token] || {}]).replace(/"/g, '&quot;');
                return `<span class="function-name builtin-function" data-function-name="${token}" data-function-type="builtin" data-function-list="${functionData}" style="color: #409EFF; font-weight: bold; cursor: help; text-decoration: underline;">${token}</span>`;
            } else {
                return token.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            }
        })
        .join('');

    editableDiv.innerHTML = highlightedContent;

    // 为函数名添加鼠标事件监听器
    addFunctionEventListeners();
};





// 轮询后端进度的函数
const pollCalculationProgress = (taskId) => {
    try {
        // 增加防抖处理，避免频繁请求
        let isRequestPending = false;
        let consecutiveErrors = 0; // 连续错误计数
        const maxConsecutiveErrors = 5; // 增加最大连续错误次数
        let progressCheckInterval = null; // 将interval变量提升到外层作用域
        
        // 延迟启动轮询，给后端处理时间
        setTimeout(() => {
            if (!store.state.isCalculating) {
                return;
            }
            
            progressCheckInterval = setInterval(async () => {
                // 如果计算已停止或正在等待请求响应，则跳过本次轮询
                if (!store.state.isCalculating || isRequestPending) {
                    if (!store.state.isCalculating) {
                        clearInterval(progressCheckInterval);
                    }
                    return;
                }
            
            try {
                isRequestPending = true;
                const response = await axios.get(`http://192.168.20.49:5000/api/calculation-progress/${taskId}`, {
                    timeout: 8000 // 增加到8秒超时
                });
                isRequestPending = false;
                consecutiveErrors = 0; // 重置错误计数
                
                const { step, progress, status } = response.data;
                
                // 更新后端计算进度
                store.commit('setCalculatingProgress', {
                    step: step,
                    progress: progress
                });
                
                // 如果计算完成，开始处理渲染阶段
                if (status === 'completed') {
                    clearInterval(progressCheckInterval);
                    
                    // 开始渲染进度跟踪
                    store.commit('setCalculatingProgress', {
                        step: '开始渲染图表',
                        progress: 100
                    });
                    
                    // 短暂延迟让用户看到100%的状态
                    setTimeout(() => {
                        store.commit('setCalculatingProgress', {
                            step: '渲染图表中',
                            progress: 100
                        });
                    }, 200);
                    
                } else if (status === 'failed') {
                    clearInterval(progressCheckInterval);
                    
                    store.commit('setCalculatingProgress', {
                        step: `计算失败: ${response.data.error || step || '未知错误'}`,
                        progress: 0
                    });
                    
                    // 3秒后清除错误状态
                    setTimeout(() => {
                        store.commit('setCalculatingStatus', false);
                    }, 3000);
                }
            } catch (error) {
                isRequestPending = false;
                consecutiveErrors++;
                

                
                // 如果是404错误且错误次数不多，可能是任务还在初始化
                if (error.response && error.response.status === 404) {
                    if (consecutiveErrors <= 3) { // 对404错误更宽容，允许最多3次404错误
                        return; // 继续轮询，不停止
                    } else {
                        clearInterval(progressCheckInterval);
                        // 不显示错误，因为计算可能已经完成
                        return;
                    }
                }
                
                // 如果连续多次轮询失败，停止轮询
                if (consecutiveErrors >= maxConsecutiveErrors) {
                    clearInterval(progressCheckInterval);
                    
                    store.commit('setCalculatingProgress', {
                        step: '网络连接异常，但计算可能仍在进行',
                        progress: 50
                    });
                    
                    // 不立即清除计算状态，给计算一些时间完成
                    setTimeout(() => {
                        if (store.state.isCalculating) {
                            store.commit('setCalculatingProgress', {
                                step: '网络异常，请检查计算结果',
                                progress: 0
                            });
                            setTimeout(() => {
                                store.commit('setCalculatingStatus', false);
                            }, 3000);
                        }
                    }, 10000); // 10秒后再清除状态
                }
            }
        }, 800); // 将轮询间隔增加到800ms，减少服务器压力
        }, 1000); // 延迟1秒启动轮询
    } catch (error) {
        // 忽略轮询设置错误
    }
};

const sendClickedChannelNames = async () => {
    try {
        // 设置计算开始状态
        store.commit('setCalculatingStatus', true);
        store.commit('setCalculatingProgress', {
            step: '初始化计算任务',
            progress: 0
        });
        
        // 使用axios的取消令牌
        const source = axios.CancelToken.source();
        const timeoutId = setTimeout(() => {
            source.cancel('操作超时');
            store.commit('setCalculatingProgress', {
                step: '计算超时，请重试',
                progress: 0
            });
            setTimeout(() => {
                store.commit('setCalculatingStatus', false);
            }, 3000);
        }, 120000); // 增加到120秒超时
        
        try {
            // 发送计算初始化请求
            store.commit('setCalculatingProgress', {
                step: '连接服务器',
                progress: 5
            });
            
            const initResponse = await axios.post('http://192.168.20.49:5000/api/operator-strs/init', {
                expression: formulasarea.value
            }, {
                cancelToken: source.token,
                timeout: 15000 // 初始化请求15秒超时
            });
            
            const taskId = initResponse.data.task_id;
            
            // 更新进度显示
            store.commit('setCalculatingProgress', {
                step: '任务创建成功，开始计算',
                progress: 10
            });
            
            // 在发送计算请求前启动轮询
            pollCalculationProgress(taskId);
            
            // 发送实际计算请求
            const response = await axios.post('http://192.168.20.49:5000/api/operator-strs', {
                clickedChannelNames: formulasarea.value,
                anomaly_func_str: formulasarea.value,
                channel_mess: selectedChannels.value,
                task_id: taskId,
                sample_freq: store.state.unit_sampling
            }, {
                cancelToken: source.token,
                timeout: 100000 // 计算请求100秒超时
            });
            
            // 处理计算结果
            store.state.ErrorLineXScopes = response.data.data;
            
            // 更新进度：后端计算完成
            store.commit('setCalculatingProgress', {
                step: '后端计算完成，开始渲染',
                progress: 95
            });
            
            // 短暂延迟后提交结果并清除状态
            setTimeout(() => {
                // 提交计算结果，这会触发图表组件的渲染
                store.commit('updateCalculateResult', response.data.data.result);
                
                // 延迟清除计算状态，让用户看到完成状态
                setTimeout(() => {
                    store.commit('setCalculatingStatus', false);
                }, 500);
            }, 200);
            
        } catch (error) {
            // 处理错误
            
            if (!axios.isCancel(error)) {
                // 非取消错误才更新进度
                let errorMessage = '未知错误';
                if (error.code === 'ECONNABORTED') {
                    errorMessage = '请求超时，请重试';
                } else if (error.response) {
                    errorMessage = error.response.data?.error || error.message || '服务器错误';
                } else if (error.request) {
                    errorMessage = '网络连接失败';
                } else {
                    errorMessage = error.message || '计算出错';
                }
                
                store.commit('setCalculatingProgress', {
                    step: `计算出错: ${errorMessage}`,
                    progress: 0
                });
                
                // 3秒后清除计算状态
                setTimeout(() => {
                    store.commit('setCalculatingStatus', false);
                }, 3000);
            } else {
                // 用户取消操作
                store.commit('setCalculatingStatus', false);
            }
        } finally {
            clearTimeout(timeoutId); // 清除超时计时器
        }
    } catch (error) {
        store.commit('setCalculatingProgress', {
            step: '初始化失败，请重试',
            progress: 0
        });
        setTimeout(() => {
            store.commit('setCalculatingStatus', false);
        }, 3000);
    }
};

const tokenizeContent = (content, channelIdentifiers, functionDisplayNames = []) => {
    if (!content) return [];

    // 对channelIdentifiers按长度降序排序，确保先匹配较长的标识符
    const sortedIdentifiers = [...channelIdentifiers].sort((a, b) => b.length - a.length);
    // 对带前缀的函数名按长度降序排序，优先匹配
    const sortedFunctionDisplayNames = [...functionDisplayNames].sort((a, b) => b.length - a.length);

    // 运算符列表
    const operators = ['+', '-', '*', '/', '(', ')'];

    const tokens = [];
    let i = 0;

    while (i < content.length) {
        let matched = false;

        // 先检查是否是通道标识符
        for (const identifier of sortedIdentifiers) {
            if (content.substring(i, i + identifier.length) === identifier) {
                tokens.push(identifier);
                i += identifier.length;
                matched = true;
                break;
            }
        }

        // 如果不是通道标识符，检查是否是带前缀的函数名
        if (!matched) {
            for (const funcDisplayName of sortedFunctionDisplayNames) {
                // funcDisplayName 格式: [Python]functionName 或 [Matlab]functionName
                const match = funcDisplayName.match(/^\[(\w+)\](.+)$/);
                if (!match) continue;

                const [, typeLabel, funcName] = match;

                // 1. 检查带空格和括号的完整版本（如 "[Python] functionName()"）
                const funcWithSpaceAndBrackets = `[${typeLabel}] ${funcName}()`;
                if (content.substring(i, i + funcWithSpaceAndBrackets.length) === funcWithSpaceAndBrackets) {
                    const prevChar = i > 0 ? content[i - 1] : null;
                    const validBefore = !prevChar || !/[a-zA-Z0-9\]]/.test(prevChar);

                    if (validBefore) {
                        // 重要：只添加函数名部分用于高亮，括号单独处理
                        // 这样可以确保高亮不受括号影响
                        tokens.push(funcDisplayName); // [Python]functionName - 用于高亮

                        // 跳过空格，直接处理括号
                        const spaceAndFuncLength = `[${typeLabel}] ${funcName}`.length;
                        i += spaceAndFuncLength; // 移动到左括号位置

                        // 单独处理左括号
                        if (content[i] === '(') {
                            tokens.push('(');
                            i++;
                        }

                        // 单独处理右括号
                        if (content[i] === ')') {
                            tokens.push(')');
                            i++;
                        }

                        matched = true;
                        break;
                    }
                }

                // 1.5. 检查带空格但没有括号的版本（如 "[Python] functionName"）
                const funcWithSpace = `[${typeLabel}] ${funcName}`;
                if (!matched && content.substring(i, i + funcWithSpace.length) === funcWithSpace) {
                    const prevChar = i > 0 ? content[i - 1] : null;
                    const validBefore = !prevChar || !/[a-zA-Z0-9\]]/.test(prevChar);

                    if (validBefore) {
                        // 检查后面是否紧跟着非字母数字字符（如运算符、空格等）
                        const nextChar = i + funcWithSpace.length < content.length ? content[i + funcWithSpace.length] : null;
                        const validAfter = !nextChar || !/[a-zA-Z0-9]/.test(nextChar);

                        if (validAfter) {
                            tokens.push(funcDisplayName); // [Python]functionName - 用于高亮
                            i += funcWithSpace.length;
                            matched = true;
                            break;
                        }
                    }
                }

                // 2. 检查紧凑格式（如 "[Python]functionName"，用户手动输入或编辑后的格式）
                if (!matched && content.substring(i, i + funcDisplayName.length) === funcDisplayName) {
                    const prevChar = i > 0 ? content[i - 1] : null;
                    const validBefore = !prevChar || !/[a-zA-Z0-9\]]/.test(prevChar);

                    if (validBefore) {
                        tokens.push(funcDisplayName);
                        i += funcDisplayName.length;
                        matched = true;
                        break;
                    }
                }
            }
        }

        // 如果都不是，检查是否是简单函数（如FFT()或FFT(args)）
        if (!matched) {
            // 检查简单函数模式：字母开头，后跟字母数字，然后是(任意内容)
            const simpleFunctionMatch = content.substring(i).match(/^([A-Za-z][A-Za-z0-9_]*)\(/);
            if (simpleFunctionMatch) {
                const funcName = simpleFunctionMatch[1];
                
                const prevChar = i > 0 ? content[i - 1] : null;
                const validBefore = !prevChar || !/[a-zA-Z0-9\]]/.test(prevChar);

                if (validBefore) {
                    // 添加函数名（不包括括号）
                    tokens.push(funcName);
                    // 单独添加左括号
                    tokens.push('(');
                    
                    // 移动到左括号后
                    i += simpleFunctionMatch[0].length;
                    
                    // 寻找匹配的右括号
                    let parenthesesCount = 1;
                    let j = i;
                    while (j < content.length && parenthesesCount > 0) {
                        if (content[j] === '(') {
                            parenthesesCount++;
                        } else if (content[j] === ')') {
                            parenthesesCount--;
                        }
                        j++;
                    }
                    
                    // 处理括号内的内容
                    if (j > i) {
                        const innerContent = content.substring(i, j - 1); // 不包括最后的右括号
                        if (innerContent.trim()) {
                            // 将内容按逗号分割并添加
                            const parts = innerContent.split(',');
                            for (let k = 0; k < parts.length; k++) {
                                const part = parts[k].trim();
                                if (part) {
                                    tokens.push(part);
                                }
                                if (k < parts.length - 1) {
                                    tokens.push(',');
                                }
                            }
                        }
                        i = j - 1; // 移动到右括号位置
                    }
                    
                    // 单独添加右括号
                    if (i < content.length && content[i] === ')') {
                        tokens.push(')');
                        i++;
                    }
                    
                    matched = true;
                }
            }
        }

        // 如果都不是，检查是否是运算符
        if (!matched) {
            const char = content[i];
            if (operators.includes(char)) {
                tokens.push(char);
                i++;
            } else if (char.trim() === '') {
                // 跳过空白字符
                i++;
            } else {
                // 处理其他字符（可能是部分通道名称或函数名）
                tokens.push(char);
                i++;
            }
        }
    }

    return tokens;
};

const getCaretCharacterOffsetWithin = (element) => {
    let caretOffset = 0;
    const selection = window.getSelection();
    if (selection.rangeCount > 0) {
        const range = selection.getRangeAt(0);

        // 遍历所有节点来计算正确的字符偏移量
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        let node;
        while (node = walker.nextNode()) {
            if (node === range.endContainer) {
                caretOffset += range.endOffset;
                break;
            } else {
                caretOffset += node.textContent.length;
            }
        }
    }
    return caretOffset;
};

// 简化的光标恢复函数
const restoreCursorPosition = (element, cursorPosition) => {
    const selection = window.getSelection();
    const range = document.createRange();
    let charCount = 0;
    let found = false;

    const walkTextNodes = (node) => {
        if (found) return true;

        if (node.nodeType === Node.TEXT_NODE) {
            const nextCharCount = charCount + node.length;
            if (nextCharCount >= cursorPosition) {
                const offset = Math.min(cursorPosition - charCount, node.length);
                range.setStart(node, offset);
                range.setEnd(node, offset);
                found = true;
                return true;
            }
            charCount = nextCharCount;
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            for (let i = 0; i < node.childNodes.length; i++) {
                if (walkTextNodes(node.childNodes[i])) {
                    return true;
                }
            }
        }
        return false;
    };

    walkTextNodes(element);

    if (found) {
        try {
            selection.removeAllRanges();
            selection.addRange(range);
        } catch (error) {
            // 忽略光标恢复错误
        }
    }
};

watch(
    selectedChannels,
    () => {
        highlightChannels();
    },
    { deep: true } // 深度监听，以捕捉对象内部变化，比如颜色改变
);

// 监听导入函数列表变化，重新高亮
watch(
    importedFunctions,
    () => {
        highlightChannels();
    },
    { deep: true }
);


watch(
    clickedChannelNames,
    async (newstr) => {
        if (!newstr) return;



        const editableDiv = document.querySelector('.editable-div');
        if (!editableDiv) return;

        // 优先使用用户当前的实际光标位置，而不是全局变量
        const actualCursorPosition = getCaretCharacterOffsetWithin(editableDiv);

        // 如果能获取到实际光标位置，使用它；否则使用全局变量作为备用
        const insertPosition = actualCursorPosition !== undefined ? actualCursorPosition : currentCursorPosition;



        // 使用实际光标位置进行文本插入
        const beforeCursor = formulasarea.value.slice(0, insertPosition);
        const afterCursor = formulasarea.value.slice(insertPosition);

        formulasarea.value = beforeCursor + newstr + afterCursor;

        // 更新光标位置到插入内容的后面
        currentCursorPosition = insertPosition + newstr.length;

        await nextTick();

        // 进行高亮处理
        highlightChannels();

        // 恢复光标到正确位置
        await nextTick();
        if (editableDiv) {
            restoreCursorPosition(editableDiv, currentCursorPosition);
        }
    },
    { immediate: true }
);



// Handle input event
const onInput = (event) => {
    // 先获取当前光标位置，避免在getPlainText后丢失
    const currentPosition = getCaretCharacterOffsetWithin(event.target);
    const newText = getPlainText(event.target);
    const channelIdentifiers = selectedChannels.value.map((channel) =>
        `${channel.channel_name}_${channel.shot_number}`
    );

    // 如果新文本比之前的短，说明可能发生了删除操作
    if (newText.length < formulasarea.value.length) {
        const deletedPosition = currentCursorPosition - 1; // 假设删除发生在光标位置前一个字符
        const channelInfo = findChannelIdentifierAtPosition(formulasarea.value, deletedPosition, channelIdentifiers);

        if (channelInfo) {
            // 如果删除的是通道标识符的一部分，删除整个标识符
            const beforeChannel = formulasarea.value.substring(0, channelInfo.start);
            const afterChannel = formulasarea.value.substring(channelInfo.end);
            formulasarea.value = beforeChannel + afterChannel;
            currentCursorPosition = channelInfo.start;
        } else {
            formulasarea.value = newText;
            currentCursorPosition = currentPosition;
        }
    } else {
        formulasarea.value = newText;
        currentCursorPosition = currentPosition;
    }

    // 立即更新全局光标位置
    currentCursorPosition = currentPosition;

    // 使用 nextTick 确保 DOM 更新后再进行高亮和光标恢复
    nextTick(() => {
        highlightChannels();

        // 恢复光标位置
        nextTick(() => {
            const editableDiv = document.querySelector('.editable-div');
            if (editableDiv) {
                restoreCursorPosition(editableDiv, currentCursorPosition);
            }
        });
    });
};


// Get plain text content from the editable div
const getPlainText = (element) => {
    let text = '';
    element.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE) {
            text += node.textContent;
        } else if (node.nodeType === Node.ELEMENT_NODE &&
                   (node.classList.contains('tag') || node.classList.contains('function-name'))) {
            text += node.textContent;
        } else if (node.nodeType === Node.ELEMENT_NODE) {
            text += node.innerText || node.textContent || '';
        }
    });
    return text;
};

const clearFormulas = () => {
    formulasarea.value = '';
    const editableDiv = document.querySelector('.editable-div');
    if (editableDiv) {
        editableDiv.innerHTML = '';
    }
};

// 获取导入的函数列表
const loadImportedFunctions = async () => {
    try {
        const response = await axios.get('http://192.168.20.49:5000/api/view-functions');
        importedFunctions.value = response.data.imported_functions || [];

    } catch (error) {
        // 获取导入函数列表失败
        importedFunctions.value = [];
    }
};

// 为函数名添加鼠标事件监听器
const addFunctionEventListeners = () => {
    const functionElements = document.querySelectorAll('.function-name');
    
    functionElements.forEach(element => {
        // 移除之前的事件监听器（如果有的话）
        element.removeEventListener('mouseenter', handleFunctionMouseEnter);
        element.removeEventListener('mouseleave', handleFunctionMouseLeave);
        
        // 添加新的事件监听器
        element.addEventListener('mouseenter', handleFunctionMouseEnter);
        element.addEventListener('mouseleave', handleFunctionMouseLeave);
    });
};

// 鼠标进入函数名时的处理
const handleFunctionMouseEnter = (event) => {
    const functionType = event.target.getAttribute('data-function-type');
    const functionName = event.target.getAttribute('data-function-name');
    const functionListData = event.target.getAttribute('data-function-list');

    if (functionListData) {
        try {
            const matchingFunctions = JSON.parse(functionListData.replace(/&quot;/g, '"'));

            if (functionType === 'builtin' && matchingFunctions.length > 0) {
                // 处理内置函数
                const functionInfo = matchingFunctions[0];
                currentFunctionInfo.value = {
                    ...functionInfo,
                    typeLabel: 'Built-in',
                    isMultiple: false
                };

                // 计算tooltip位置，显示在函数名下方
                const rect = event.target.getBoundingClientRect();
                tooltipPosition.value = {
                    x: rect.left + rect.width / 2,
                    y: rect.bottom + 10
                };

                showFunctionTooltip.value = true;
            } else if (functionType && matchingFunctions.length > 0) {
                // 处理带前缀的导入函数
                const functionInfo = matchingFunctions[0]; // 带前缀的函数只会有一个匹配项
                const typeLabel = getFunctionTypeLabel(functionInfo.file_path);
                currentFunctionInfo.value = {
                    ...functionInfo,
                    typeLabel: typeLabel,
                    isMultiple: false
                };

                // 计算tooltip位置，显示在函数名下方
                const rect = event.target.getBoundingClientRect();
                tooltipPosition.value = {
                    x: rect.left + rect.width / 2,
                    y: rect.bottom + 10  // 改为显示在下方
                };

                showFunctionTooltip.value = true;
            }
        } catch (error) {
            // 解析函数数据失败
            console.error('解析函数数据失败:', error);
        }
    }
};





// 鼠标离开函数名时的处理
const handleFunctionMouseLeave = () => {
    // 延迟隐藏tooltip，给用户时间移动到tooltip上
    setTimeout(() => {
        showFunctionTooltip.value = false;
    }, 100);
};

// 处理函数上传事件
const handleFunctionUploaded = async () => {
    await loadImportedFunctions();
};

// 处理函数删除事件
const handleFunctionDeleted = async () => {
    await loadImportedFunctions();
};



// 在 script setup 部分添加一个新的辅助函数
const findChannelIdentifierAtPosition = (text, position, channelIdentifiers) => {

    
    // 按长度排序标识符，优先匹配较长的标识符
    const sortedIdentifiers = [...channelIdentifiers].sort((a, b) => b.length - a.length);
    
    for (const identifier of sortedIdentifiers) {
        // 检查position是否在某个通道标识符的范围内
        let currentIndex = 0;
        while (currentIndex < text.length) {
            const idx = text.indexOf(identifier, currentIndex);
            if (idx === -1) break;
            if (position >= idx && position < idx + identifier.length) {
                return {
                    identifier,
                    start: idx,
                    end: idx + identifier.length
                };
            }
            currentIndex = idx + 1;
        }
    }
    return null;
};

</script>

<style scoped lang="scss">
.editable-div {
    width: 100%;
    min-height: 85%;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    padding: 10px;
    overflow: auto;
    line-height: 1.5;
    cursor: text;
    outline: none;
}

.editable-div:focus {
    border: 1px solid #dcdfe6;
    box-shadow: none;
}

.editable-div:empty::before {
    content: attr(placeholder);
    color: #c0c4cc;
}

:deep(.tag) {
    display: inline-block;
    padding: 0 8px;
    font-size: 12px;
    border-radius: 4px;
    color: #fff;
    background-color: #409EFF;
    margin: 0 2px;
    vertical-align: middle;
    overflow: hidden;
    white-space: nowrap;
}

/* 函数详情tooltip样式 */
.function-tooltip {
    position: fixed;
    z-index: 9999;
    transform: translateX(-50%);
    margin-top: 8px;
    pointer-events: auto;
}

.tooltip-content {
    background: #ffffff;
    border: 1px solid #e4e7ed;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    padding: 16px;
    min-width: 280px;
    max-width: 400px;
    font-size: 13px;
    line-height: 1.4;
}

.function-header {
    margin-bottom: 8px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e1f3ff;
}

.function-name-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #1a73e8;
}

.function-tags {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}

.function-type-prefix {
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 12px;
    font-weight: 500;
    border: 1px solid;

    /* 默认样式（Python） */
    background: #f0f9ff;
    color: #0369a1;
    border-color: #bae6fd;

    /* Python 样式 */
    &.type-python {
        background: #f0f9ff;
        color: #0369a1;
        border-color: #bae6fd;
    }

    /* Matlab 样式 */
    &.type-matlab {
        background: #fef3c7;
        color: #d97706;
        border-color: #fde68a;
    }
}

.function-type {
    background: #e1f3ff;
    color: #409EFF;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
}

/* 多个函数选择界面样式 */
.multiple-functions {
    .multiple-indicator {
        background: #fff3cd;
        color: #856404;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 500;
        border: 1px solid #ffeaa7;
    }
}

.function-selector {
    margin-top: 12px;

    .selector-hint {
        font-size: 12px;
        color: #606266;
        margin-bottom: 8px;
        font-weight: 500;
    }
}

.function-options {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.function-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    border: 1px solid #e4e7ed;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
    background: #fafbfc;

    &:hover {
        border-color: #409EFF;
        background: #f0f9ff;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(64, 158, 255, 0.15);
    }

    .function-name {
        font-weight: 600;
        color: #303133;
        flex: 1;
    }

    .function-type-small {
        font-size: 10px;
        color: #909399;
        background: #f5f7fa;
        padding: 1px 6px;
        border-radius: 3px;
    }
}

.function-description {
    margin-bottom: 12px;
    color: #606266;
}

.function-params,
.function-output {
    margin-bottom: 12px;
}

.function-params strong,
.function-output strong {
    color: #303133;
    font-size: 14px;
    display: block;
    margin-bottom: 6px;
}

.param-list,
.output-list {
    margin-left: 12px;
}

.param-item,
.output-item {
    margin-bottom: 6px;
    padding: 6px 8px;
    background: #f8fbff;
    border-radius: 4px;
    border-left: 3px solid #409EFF;
}

.param-name,
.output-name {
    font-weight: 600;
    color: #409EFF;
    margin-right: 6px;
}

.param-type,
.output-type {
    color: #909399;
    font-style: italic;
    margin-right: 6px;
}

.param-definition,
.output-definition {
    color: #606266;
    margin-right: 6px;
}

.param-default {
    color: #1890ff;
    font-size: 12px;
    background: #e6f7ff;
    padding: 1px 4px;
    border-radius: 2px;
}

/* 内置函数特殊样式 */
:deep(.builtin-function) {
    background: #409EFF !important;
    color: white !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
    font-weight: 600 !important;
    text-decoration: none !important;
    
    &:hover {
        background: #337ecc !important;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(64, 158, 255, 0.3);
    }
}

/* Built-in 标识样式 */
.function-type-prefix.type-builtin {
    background: #409EFF;
    color: white;
    border-color: #409EFF;
}

/* 添加三角箭头指向函数名 */
.function-tooltip::after {
    content: '';
    position: absolute;
    top: -6px;
    left: 50%;
    transform: translateX(-50%);
    border: 6px solid transparent;
    border-bottom-color: #ffffff;
}

.function-tooltip::before {
    content: '';
    position: absolute;
    top: -7px;
    left: 50%;
    transform: translateX(-50%);
    border: 7px solid transparent;
    border-bottom-color: #e4e7ed;
}
</style>