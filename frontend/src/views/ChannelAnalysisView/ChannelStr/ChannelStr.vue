<template>
    <div>
        <div class="editable-div" contenteditable="true" spellcheck="false" @input="onInput" @click="updateCursorPosition" @keyup="updateCursorPosition"></div>
        <span style="position: absolute; bottom: 8px; right: 8px;">
            <!--            <span style="margin-right: 30px">{{output}}</span>-->

            <el-button type="primary">
                <FolderChecked />
                记录公式
            </el-button>
            <el-button type="primary" @click="sendClickedChannelNames" :loading="isCalculating">
                <Cpu />
                计算
            </el-button>
            <el-button type="danger" @click="clearFormulas">
                <CloseBold />
                清空
            </el-button>
        </span>
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

onMounted(() => {
    highlightChannels();
});

onUnmounted(() => {
    formulasarea.value = '';
    store.commit("updateChannelName", '')
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

    const tokens = tokenizeContent(content, channelIdentifiers);

    const highlightedContent = tokens
        .map((token) => {
            if (channelIdentifiers.includes(token)) {
                const color = colors[token] || '#409EFF';
                return `<span class="tag" style="background-color: ${color};">${token}</span>`;
            } else {
                return token.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            }
        })
        .join('');

    editableDiv.innerHTML = highlightedContent;

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
const pollCalculationProgress = async (taskId) => {
    try {
        // 增加防抖处理，避免频繁请求
        let isRequestPending = false;
        const progressCheckInterval = setInterval(async () => {
            // 如果计算已停止或正在等待请求响应，则跳过本次轮询
            if (!store.state.isCalculating || isRequestPending) {
                if (!store.state.isCalculating) {
                    clearInterval(progressCheckInterval);
                }
                return;
            }
            
            try {
                isRequestPending = true;
                const response = await axios.get(`https://10.1.108.231:5000/api/calculation-progress/${taskId}/`);
                isRequestPending = false;
                
                const { step, progress, status } = response.data;
                
                // 更新进度和步骤
                store.commit('setCalculatingProgress', {
                    step: step,
                    progress: progress
                });
                
                // 如果计算完成或失败，停止轮询
                if (status === 'completed' || status === 'failed') {
                    clearInterval(progressCheckInterval);
                    
                    if (status === 'failed') {
                        store.commit('setCalculatingProgress', {
                            step: `计算失败: ${response.data.error || '未知错误'}`,
                            progress: 0
                        });
                        
                        // 3秒后清除错误状态
                        setTimeout(() => {
                            store.commit('setCalculatingStatus', false);
                        }, 3000);
                    } else {
                        // 短暂延迟后清除计算状态
                        setTimeout(() => {
                            store.commit('setCalculatingStatus', false);
                        }, 500);
                    }
                }
            } catch (error) {
                isRequestPending = false;
                console.error('Error polling calculation progress:', error);
                // 如果连续多次轮询失败，停止轮询
                if (error.response && error.response.status === 404) {
                    clearInterval(progressCheckInterval);
                    store.commit('setCalculatingStatus', false);
                }
            }
        }, 1000); // 将轮询间隔从300ms增加到1000ms
    } catch (error) {
        console.error('Error setting up progress polling:', error);
    }
};

const sendClickedChannelNames = async () => {
    try {
        // 设置计算开始状态
        store.commit('setCalculatingStatus', true);
        store.commit('setCalculatingProgress', {
            step: '准备计算',
            progress: 0
        });
        
        // 使用axios的取消令牌
        const source = axios.CancelToken.source();
        const timeoutId = setTimeout(() => {
            source.cancel('操作超时');
            store.commit('setCalculatingStatus', false);
        }, 60000); // 60秒超时
        
        try {
            // 发送计算请求，并获取后端返回的任务ID
            const initResponse = await axios.post('https://10.1.108.231:5000/api/operator-strs/init/', {
                expression: formulasarea.value
            });
            
            const taskId = initResponse.data.task_id;
            
            // 启动进度轮询
            pollCalculationProgress(taskId);
            
            // 发送实际计算请求
            const response = await axios.post('https://10.1.108.231:5000/api/operator-strs/', {
                clickedChannelNames: formulasarea.value,
                anomaly_func_str: formulasarea.value,
                channel_mess: selectedChannels.value,
                task_id: taskId,
                sample_freq: store.state.unit_sampling
            }, {
                cancelToken: source.token
            });
            
            // 处理计算结果
            store.state.ErrorLineXScopes = response.data.data;
            store.commit('updateCalculateResult', response.data.data.result);
            
        } catch (error) {
            // 处理错误
            console.error('Error sending data to backend:', error);
            
            if (!axios.isCancel(error)) {
                // 非取消错误才更新进度
                store.commit('setCalculatingProgress', {
                    step: `计算出错: ${error.message || '未知错误'}`,
                    progress: 0
                });
                
                // 3秒后清除计算状态
                setTimeout(() => {
                    store.commit('setCalculatingStatus', false);
                }, 3000);
            }
        } finally {
            clearTimeout(timeoutId); // 清除超时计时器
        }
    } catch (error) {
        console.error('Error in calculation process:', error);
        store.commit('setCalculatingStatus', false);
    }
};

const tokenizeContent = (content, channelIdentifiers) => {
    if (!content) return [];
    
    // 对channelIdentifiers按长度降序排序，确保先匹配较长的标识符
    const sortedIdentifiers = [...channelIdentifiers].sort((a, b) => b.length - a.length);
    
    // 运算符列表
    const operators = ['+', '-', '*', '/', '(', ')'];
    
    const tokens = [];
    let i = 0;
    
    while (i < content.length) {
        // 先检查是否是通道标识符
        let matched = false;
        
        for (const identifier of sortedIdentifiers) {
            if (content.substring(i, i + identifier.length) === identifier) {
                tokens.push(identifier);
                i += identifier.length;
                matched = true;
                break;
            }
        }
        
        // 如果不是通道标识符，再检查是否是运算符
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
</style>
