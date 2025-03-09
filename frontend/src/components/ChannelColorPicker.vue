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
      @active-change="handleActiveChange"
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

const predefineColors = [
    '#000000', '#4169E1', '#DC143C', '#228B22', '#FF8C00',
    '#800080', '#FF1493', '#40E0D0', '#FFD700', '#8B4513',
    '#2F4F4F', '#1E90FF', '#32CD32', '#FF6347', '#DA70D6',
    '#191970', '#FA8072', '#6B8E23', '#6A5ACD', '#FF7F50',
    '#4682B4',
];

const emit = defineEmits(['update:color', 'change'])
const localColor = ref(props.color)
const uniqueId = ref(Math.random().toString(36).substr(2, 9))
const pickerInstance = ref(null)

// 手动管理颜色选择器的激活状态，解决点击确定后无法再次打开的问题
const handleActiveChange = (active) => {
  console.log('颜色选择器状态变化:', active)
  
  // 当选择器关闭时，记录关闭状态并添加延迟以确保状态完全重置
  if (!active) {
    setTimeout(() => {
      // 找到并重置颜色选择器组件的内部状态
      const pickerEls = document.querySelectorAll('.el-color-picker')
      pickerEls.forEach(el => {
        // 确保下一次点击能打开选择器
        if (el.__vueParentComponent?.ctx?.$attrs?.class?.includes(`color-picker`)) {
          el.__vueParentComponent.ctx.handleClick = function() {
            this.showPicker = true
          }
        }
      })
    }, 10)
  }
}

// 确保在组件挂载时正确初始化颜色值
onMounted(() => {
  // 设置本地颜色值
  localColor.value = props.color;
  
  // 添加自定义样式
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

// 监听props.color的变化，更新本地颜色值
watch(
  () => props.color,
  (newColor) => {
    if (newColor !== localColor.value) {
      localColor.value = newColor
    }
  }
)

// 处理颜色变化事件
const handleChange = (newColor) => {
  console.log('颜色变化:', newColor);
  
  // 更新颜色值
  emit('update:color', newColor);
  
  // 触发change事件
  emit('change', newColor);
  
  // 确保本地颜色值与新颜色一致
  localColor.value = newColor;
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
