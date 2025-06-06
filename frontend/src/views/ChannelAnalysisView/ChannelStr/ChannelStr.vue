<template>
    <div>
        <div class="editable-div" contenteditable="true" spellcheck="false" @input="onInput" @click="updateCursorPosition" @keyup="updateCursorPosition"></div>
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
                <div class="function-header">
                    <h4 class="function-name-title">{{ currentFunctionInfo.name }}</h4>
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
    highlightChannels();
    // 获取导入的函数列表
    await loadImportedFunctions();
    
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

    // 获取导入函数的名称列表
    const functionNames = importedFunctions.value.map(func => func.name);

    const tokens = tokenizeContent(content, channelIdentifiers, functionNames);

    const highlightedContent = tokens
        .map((token) => {
            if (channelIdentifiers.includes(token)) {
                const color = colors[token] || '#409EFF';
                return `<span class="tag" style="background-color: ${color};">${token}</span>`;
            } else if (functionNames.includes(token)) {
                // 为函数名添加特殊样式和事件处理
                return `<span class="function-name" data-function-name="${token}" style="color: #409EFF; font-weight: bold; cursor: help; text-decoration: underline;">${token}</span>`;
            } else {
                return token.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            }
        })
        .join('');

    editableDiv.innerHTML = highlightedContent;

    // 为函数名添加鼠标事件监听器
    addFunctionEventListeners();

    restoreCursorPosition(editableDiv, currentCursorPosition);
};



const restoreCursorPosition = (element, cursorPosition) => {
    const selection = window.getSelection();
    const range = document.createRange();
    let charCount = 0;
    let node;

    const traverseNodes = (currentNode) => {
        if (currentNode.nodeType === Node.TEXT_NODE) {
            const nextCharCount = charCount + currentNode.length;
            if (nextCharCount >= cursorPosition) {
                range.setStart(currentNode, cursorPosition - charCount);
                return true;
            }
            charCount = nextCharCount;
        }
        for (let i = 0; i < currentNode.childNodes.length; i++) {
            if (traverseNodes(currentNode.childNodes[i])) return true;
        }
        return false;
    };

    traverseNodes(element);
    selection.removeAllRanges();
    selection.addRange(range);
};

// 轮询后端进度的函数
const pollCalculationProgress = (taskId) => {
    try {
        // 增加防抖处理，避免频繁请求
        let isRequestPending = false;
        let consecutiveErrors = 0; // 连续错误计数
        const maxConsecutiveErrors = 5; // 增加最大连续错误次数
        let progressCheckInterval = null; // 将interval变量提升到外层作用域
        
        // console.log('启动进度轮询，任务ID:', taskId);
        
        // 延迟启动轮询，给后端处理时间
        setTimeout(() => {
            if (!store.state.isCalculating) {
                // console.log('计算已停止，取消轮询启动');
                return;
            }
            
            progressCheckInterval = setInterval(async () => {
                // 如果计算已停止或正在等待请求响应，则跳过本次轮询
                if (!store.state.isCalculating || isRequestPending) {
                    if (!store.state.isCalculating) {
                        clearInterval(progressCheckInterval);
                        // console.log('计算状态已停止，停止轮询');
                    }
                    return;
                }
            
            try {
                isRequestPending = true;
                const response = await axios.get(`https://10.1.108.231:5000/api/calculation-progress/${taskId}`, {
                    timeout: 8000 // 增加到8秒超时
                });
                isRequestPending = false;
                consecutiveErrors = 0; // 重置错误计数
                
                const { step, progress, status } = response.data;
                // console.log(`进度更新: ${step} - ${progress}% - ${status}`);
                
                // 更新后端计算进度
                store.commit('setCalculatingProgress', {
                    step: step,
                    progress: progress
                });
                
                // 如果计算完成，开始处理渲染阶段
                if (status === 'completed') {
                    clearInterval(progressCheckInterval);
                    // console.log('后端计算完成，进入渲染阶段');
                    
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
                    // console.log('后端计算失败');
                    
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
                
                console.warn(`进度轮询错误 (${consecutiveErrors}/${maxConsecutiveErrors}):`, error.message);
                
                // 如果是404错误且错误次数不多，可能是任务还在初始化
                if (error.response && error.response.status === 404) {
                    if (consecutiveErrors <= 3) { // 对404错误更宽容，允许最多3次404错误
                        // console.log('任务可能还在初始化，继续轮询...');
                        return; // 继续轮询，不停止
                    } else {
                        // console.log('任务可能已完成或不存在，停止轮询');
                        clearInterval(progressCheckInterval);
                        // 不显示错误，因为计算可能已经完成
                        return;
                    }
                }
                
                // 如果连续多次轮询失败，停止轮询
                if (consecutiveErrors >= maxConsecutiveErrors) {
                    clearInterval(progressCheckInterval);
                    console.error('轮询失败次数过多，停止轮询');
                    
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
        console.error('Error setting up progress polling:', error);
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
            
            // console.log('发送初始化请求...');
            const initResponse = await axios.post('https://10.1.108.231:5000/api/operator-strs/init', {
                expression: formulasarea.value,
                db_suffix: store.state.selectedDbSuffix
            }, {
                cancelToken: source.token,
                timeout: 15000 // 初始化请求15秒超时
            });
            
            const taskId = initResponse.data.task_id;
            // console.log('任务初始化成功, 任务ID:', taskId);
            
            // 更新进度显示
            store.commit('setCalculatingProgress', {
                step: '任务创建成功，开始计算',
                progress: 10
            });
            
            // 在发送计算请求前启动轮询
            // console.log('启动进度轮询...');
            pollCalculationProgress(taskId);
            
            // 发送实际计算请求
            // console.log('发送计算请求...');
            const response = await axios.post('https://10.1.108.231:5000/api/operator-strs', {
                clickedChannelNames: formulasarea.value,
                anomaly_func_str: formulasarea.value,
                channel_mess: selectedChannels.value,
                task_id: taskId,
                sample_freq: store.state.unit_sampling,
                db_suffix: store.state.selectedDbSuffix
            }, {
                cancelToken: source.token,
                timeout: 100000 // 计算请求100秒超时
            });
            
            // console.log('计算请求完成，处理结果...');
            
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
            console.error('Error sending data to backend:', error);
            
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
                // console.log('用户取消计算操作');
                store.commit('setCalculatingStatus', false);
            }
        } finally {
            clearTimeout(timeoutId); // 清除超时计时器
        }
    } catch (error) {
        console.error('Error in calculation process:', error);
        store.commit('setCalculatingProgress', {
            step: '初始化失败，请重试',
            progress: 0
        });
        setTimeout(() => {
            store.commit('setCalculatingStatus', false);
        }, 3000);
    }
};

const tokenizeContent = (content, channelIdentifiers, functionNames = []) => {
    if (!content) return [];
    
    // 对channelIdentifiers按长度降序排序，确保先匹配较长的标识符
    const sortedIdentifiers = [...channelIdentifiers].sort((a, b) => b.length - a.length);
    // 对functionNames也按长度降序排序
    const sortedFunctionNames = [...functionNames].sort((a, b) => b.length - a.length);
    
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
        
        // 如果不是通道标识符，检查是否是函数名
        if (!matched) {
            for (const funcName of sortedFunctionNames) {
                if (content.substring(i, i + funcName.length) === funcName) {
                    // 确保这是完整的函数名（前面和后面都应该是分隔符）
                    const prevChar = i > 0 ? content[i - 1] : null;
                    const nextChar = content[i + funcName.length];
                    
                    // 前面应该是开始、空格或运算符，后面应该是结束、空格、运算符或括号
                    const validBefore = !prevChar || /\s|[+\-*/()]/.test(prevChar);
                    const validAfter = !nextChar || /\s|[+\-*/()]/.test(nextChar);
                    
                    if (validBefore && validAfter) {
                        tokens.push(funcName);
                        i += funcName.length;
                        matched = true;
                        break;
                    }
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
        const preCaretRange = range.cloneRange();
        preCaretRange.selectNodeContents(element);
        preCaretRange.setEnd(range.endContainer, range.endOffset);
        caretOffset = preCaretRange.toString().length;
    }
    return caretOffset;
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
        
        // console.log("接收到点击的通道标识符:", newstr);
        
        const editableDiv = document.querySelector('.editable-div');
        if (!editableDiv) return;

        // 使用全局光标位置记录
        const beforeCursor = formulasarea.value.slice(0, currentCursorPosition);
        const afterCursor = formulasarea.value.slice(currentCursorPosition);

        formulasarea.value = beforeCursor + newstr + afterCursor;

        // 扩展正则表达式以匹配 "函数名 + 括号" 或单独的括号对
        const functionOrBracketPattern = /^[A-Za-z]*\(\)|^[A-Za-z]*\[\]|^[A-Za-z]*\{\}$/;
        const isFunctionOrBracket = functionOrBracketPattern.test(newstr);

        if (isFunctionOrBracket) {
            // 若为括号形，将光标放在括号中间
            currentCursorPosition += newstr.length - 1; // 移动光标到括号内部
        } else {
            // 否则，将光标放在新插入内容的后面
            currentCursorPosition += newstr.length;
        }

        await nextTick();

        highlightChannels();
        restoreCursorPosition(editableDiv, currentCursorPosition);
    },
    { immediate: true }
);



// Handle input event
const onInput = (event) => {
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
            currentCursorPosition = getCaretCharacterOffsetWithin(event.target);
        }
    } else {
        formulasarea.value = newText;
        currentCursorPosition = getCaretCharacterOffsetWithin(event.target);
    }

    highlightChannels();

    const editableDiv = document.querySelector('.editable-div');
    restoreCursorPosition(editableDiv, currentCursorPosition);
};


// Get plain text content from the editable div
const getPlainText = (element) => {
    let text = '';
    element.childNodes.forEach((node) => {
        if (node.nodeType === Node.TEXT_NODE) {
            text += node.textContent;
        } else if (node.nodeType === Node.ELEMENT_NODE && node.classList.contains('tag')) {
            text += node.textContent;
        } else {
            text += node.innerText;
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
        const response = await axios.get('https://10.1.108.231:5000/api/view-functions');
        importedFunctions.value = response.data.imported_functions || [];
        console.log('导入函数列表加载成功:', importedFunctions.value);
    } catch (error) {
        console.error('获取导入函数列表失败:', error);
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
    const functionName = event.target.getAttribute('data-function-name');
    const functionInfo = importedFunctions.value.find(func => func.name === functionName);
    
    if (functionInfo) {
        currentFunctionInfo.value = functionInfo;
        
        // 计算tooltip位置，显示在函数名下方
        const rect = event.target.getBoundingClientRect();
        tooltipPosition.value = {
            x: rect.left + rect.width / 2,
            y: rect.bottom + 10  // 改为显示在下方
        };
        
        showFunctionTooltip.value = true;
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
    console.log('检测到函数上传事件，重新加载函数列表');
    await loadImportedFunctions();
};

// 处理函数删除事件
const handleFunctionDeleted = async () => {
    console.log('检测到函数删除事件，重新加载函数列表');
    await loadImportedFunctions();
};

// 在 script setup 部分添加一个新的辅助函数
const findChannelIdentifierAtPosition = (text, position, channelIdentifiers) => {
    // console.log("查找位置:", position, "文本:", text);
    // console.log("可用通道标识符:", channelIdentifiers);
    
    // 按长度排序标识符，优先匹配较长的标识符
    const sortedIdentifiers = [...channelIdentifiers].sort((a, b) => b.length - a.length);
    
    for (const identifier of sortedIdentifiers) {
        // 检查position是否在某个通道标识符的范围内
        let currentIndex = 0;
        while (currentIndex < text.length) {
            const idx = text.indexOf(identifier, currentIndex);
            if (idx === -1) break;
            if (position >= idx && position < idx + identifier.length) {
                const result = {
                    identifier,
                    start: idx,
                    end: idx + identifier.length
                };
                // console.log("找到标识符:", result);
                return result;
            }
            currentIndex = idx + 1;
        }
    }
    // console.log("未找到标识符");
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
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #e1f3ff;
}

.function-name-title {
    margin: 0;
    font-size: 16px;
    font-weight: 600;
    color: #1a73e8;
}

.function-type {
    background: #e1f3ff;
    color: #409EFF;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
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