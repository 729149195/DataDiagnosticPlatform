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
    const channelNames = selectedChannels.value.map((channel) => channel.channel_name);
    const colors = selectedChannels.value.reduce((acc, channel) => {
        acc[channel.channel_name] = channel.color;
        return acc;
    }, {});

    const tokens = tokenizeContent(content, channelNames);

    const highlightedContent = tokens
        .map((token) => {
            if (channelNames.includes(token)) {
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
        const response = await axios.post('http://localhost:5000/api/operator-strs/', {
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

const tokenizeContent = (content, channelNames) => {
    const tokens = [];
    let index = 0;
    while (index < content.length) {
        let matched = false;

        for (const name of channelNames.sort((a, b) => b.length - a.length)) {
            if (content.substr(index, name.length) === name) {
                tokens.push(name);
                index += name.length;
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
            // 若为括号形式，将光标放在括号中间
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
    const textContent = getPlainText(event.target);
    formulasarea.value = textContent;
    currentCursorPosition = getCaretCharacterOffsetWithin(event.target); // 更新光标位置

    highlightChannels();

    const editableDiv = document.querySelector('.editable-div');
    restoreCursorPosition(editableDiv, currentCursorPosition); // 恢复光标位置
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
