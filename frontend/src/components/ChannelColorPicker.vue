<template>
  <div class="color-picker-wrapper">
    <el-color-picker 
      v-model="localColor" 
      @change="handleChange" 
      class="color-picker" 
      size="small" 
      show-alpha
      :predefine="predefineColors"
      :popper-class="`custom-color-picker-${uniqueId}`"
    />
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  color: {
    type: String,
    required: true
  },
  predefineColors: {
    type: Array,
    default: () => []
  },
  shotNumber: {
    type: [String, Number],
    default: ''
  },
  channelName: {
    type: String,
    default: ''
  }
})

const emit = defineEmits(['update:color', 'change'])
const localColor = ref(props.color)
const uniqueId = ref(Math.random().toString(36).substr(2, 9))

// 动态添加样式
onMounted(() => {
  const styleId = `color-picker-style-${uniqueId.value}`
  const styleEl = document.createElement('style')
  styleEl.id = styleId
  
  // 根据是否有炮号来决定显示的文本
  let displayText;
  if (props.shotNumber) {
    // 如果 channelName 包含 | 符号，说明是异常类型的颜色选择器
    if (props.channelName.includes('|')) {
      const [channelName, errorName] = props.channelName.split('|').map(s => s.trim());
      displayText = `修改${props.shotNumber} | ${channelName} | ${errorName}的颜色`;
    } else {
      displayText = `修改${props.shotNumber} | ${props.channelName}通道的颜色`;
    }
  } else {
    displayText = `修改${props.channelName}类所有通道的颜色`;
  }

  styleEl.textContent = `
    .custom-color-picker-${uniqueId.value} .el-color-dropdown__main-wrapper::before {
      content: '${displayText}';
      display: block;
      padding: 8px 12px;
      color: #606266;
      font-size: 14px;
      border-bottom: 1px solid #eee;
      margin-bottom: 8px;
    }
  `
  document.head.appendChild(styleEl)
})

// 清理样式
onBeforeUnmount(() => {
  const styleEl = document.getElementById(`color-picker-style-${uniqueId.value}`)
  if (styleEl) {
    styleEl.remove()
  }
})

watch(
  () => props.color,
  (newColor) => {
    if (newColor !== localColor.value) {
      localColor.value = newColor
    }
  }
)

const handleChange = (newColor) => {
  // 先更新颜色值
  emit('update:color', newColor)
  
  // 使用setTimeout确保DOM更新后再触发change事件
  setTimeout(() => {
    emit('change', newColor)
    
    // 手动关闭颜色选择器弹窗
    const colorPicker = document.querySelector(`.custom-color-picker-${uniqueId.value}`)
    if (colorPicker && colorPicker.parentNode) {
      // 查找关闭按钮并触发点击
      const closeBtn = colorPicker.querySelector('.el-color-dropdown__btn')
      if (closeBtn) {
        closeBtn.click()
      } else {
        // 如果找不到关闭按钮，尝试从DOM中移除弹窗
        colorPicker.parentNode.removeChild(colorPicker)
      }
    }
  }, 0)
}
</script>

<style>
.color-picker-wrapper {
  display: inline-block;
}

.el-color-dropdown__main-wrapper {
  position: relative;
}
</style>
