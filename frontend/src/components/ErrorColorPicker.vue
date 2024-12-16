<template>
  <div class="error-picker-wrapper">
    <el-color-picker 
      v-model="localColor" 
      @change="handleChange" 
      class="error-picker" 
      size="small" 
      show-alpha
      :predefine="defaultColors"
      :popper-class="`custom-error-picker-${uniqueId}`"
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
    default: () => [
      '#000000', // Black
      '#4169E1', // Royal Blue
      '#DC143C', // Crimson
      '#228B22', // Forest Green
      '#FF8C00', // Dark Orange
      '#800080', // Purple
      '#FF1493', // Deep Pink
      '#40E0D0', // Turquoise
      '#FFD700', // Gold
      '#8B4513', // Saddle Brown
      '#2F4F4F', // Dark Slate Gray
      '#1E90FF', // Dodger Blue
      '#32CD32', // Lime Green
      '#FF6347', // Tomato
      '#DA70D6', // Orchid
      '#191970', // Midnight Blue
      '#FA8072', // Salmon
      '#6B8E23', // Olive Drab
      '#6A5ACD', // Slate Blue
      '#FF7F50', // Coral
      '#4682B4'  // Steel Blue
    ]
  },
  errorName: {
    type: String,
    default: ''
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
const defaultColors = ref(props.predefineColors)

// 动态添加样式
onMounted(() => {
  const styleId = `error-picker-style-${uniqueId.value}`
  const styleEl = document.createElement('style')
  styleEl.id = styleId
  
  styleEl.textContent = `
    .custom-error-picker-${uniqueId.value} .el-color-dropdown__main-wrapper::before {
      content: '修改${props.shotNumber} | ${props.channelName} | ${props.errorName}的颜色';
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
  const styleEl = document.getElementById(`error-picker-style-${uniqueId.value}`)
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
  emit('update:color', newColor)
  emit('change', newColor)
}
</script>

<style>
.error-picker-wrapper {
  display: inline-block;
}
</style> 