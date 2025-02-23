<template>
    <div>
        <div class="editable-div" contenteditable="true" spellcheck="false" @input="onInput"
            @click="updateCursorPosition" @keyup="updateCursorPosition"></div>


        <span style="position: absolute; bottom: 8px; right: 8px;">
<!--            <span style="margin-right: 30px">{{output}}</span>-->
            
            <el-button type="primary">
                <FolderChecked />
                记录公式
            </el-button>
            <el-button type="primary" @click="sendClickedChannelNames">
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
    store.commit("updateChannelName",  '')
});

const highlightChannels = () => {
    const editableDiv = document.querySelector('.editable-div');
    if (!editableDiv) return;

    const content = formulasarea.value;
    const channelIdentifiers = selectedChannels.value.map((channel) => 
        `${channel.shot_number}_${channel.channel_name}`
    );
    const colors = selectedChannels.value.reduce((acc, channel) => {
        acc[`${channel.shot_number}_${channel.channel_name}`] = channel.color;
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

const sendClickedChannelNames = async () => {
    try {
        console.log(selectedChannels)
        const response = await axios.post('https://10.1.108.19:5000/api/operator-strs/', {
            clickedChannelNames: formulasarea.value,
            anomaly_func_str: formulasarea.value,
            channel_mess: selectedChannels.value[0], // 目前只做一个通道的情况
        });
        console.log('Response from backend:', response.data);
        store.state.ErrorLineXScopes = response.data.data;
        store.commit('updateCalculateResult', response.data.data.result)
        console.log('xxx')
    } catch (error) {
        console.error('Error sending data to backend:', error);
    }
};

const tokenizeContent = (content, channelIdentifiers) => {
    const tokens = [];
    let index = 0;
    while (index < content.length) {
        let matched = false;

        for (const identifier of channelIdentifiers.sort((a, b) => b.length - a.length)) {
            if (content.substr(index, identifier.length) === identifier) {
                tokens.push(identifier);
                index += identifier.length;
                matched = true;
                break;
            }
        }
        if (!matched) {
            tokens.push(content[index]);
            index++;
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
        `${channel.shot_number}_${channel.channel_name}`
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
    for (const identifier of channelIdentifiers) {
        // 检查position是否在某个通道标识符的范围内
        const index = text.indexOf(identifier);
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
</style>
