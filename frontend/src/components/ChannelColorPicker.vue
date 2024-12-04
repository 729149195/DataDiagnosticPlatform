<template>
  <el-color-picker v-model="localColor" @change="handleChange" class="color-picker" size="small" show-alpha
    :predefine="predefineColors" />
</template>

<script setup>
import { ref, watch, defineProps, defineEmits } from 'vue'

const props = defineProps({
  color: {
    type: String,
    required: true
  },
  predefineColors: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['update:color', 'change'])

const localColor = ref(props.color)

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
