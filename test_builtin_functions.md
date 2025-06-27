# 内置函数 FFT() 和 Pca() 测试说明

## 功能概述

本次更新为 ChannelAnalysisView 添加了两个内置函数：
- **FFT()**: 快速傅里叶变换，用于信号的频域分析
- **Pca()**: 主成分分析，用于数据降维和特征提取

## 新增功能

### 1. ChannelStr.vue 增强
- ✅ 为内置函数添加了详细的参数说明和tooltip
- ✅ 支持鼠标悬浮显示函数详情（参数、输出、说明）
- ✅ 内置函数有特殊的视觉样式（渐变背景）

### 2. 后端表达式解析器增强  
- ✅ ExpressionParser 支持函数调用语法
- ✅ 添加了 FFT 和 PCA 的具体实现
- ✅ 支持参数解析和类型检查

### 3. 结果可视化增强
- ✅ ChannelCalculationResults.vue 支持不同类型的结果显示
- ✅ FFT 结果显示为频率-幅值图表（X轴：频率Hz，Y轴：幅值）
- ✅ PCA 结果显示为时间-主成分图表（X轴：时间s，Y轴：PC1）

## 使用方法

### FFT 函数
```
FFT(channel_name_shot_number)
FFT(channel_name_shot_number, frequency_limit)
```

**参数说明：**
- `channel_name_shot_number`: 通道数据（必需）
- `frequency_limit`: 频率上限，单位Hz（可选，默认1000Hz）

**使用示例：**
```
FFT(B36_11812)
FFT(B36_11812, 500)
```

### PCA 函数  
```
Pca(channel_name_shot_number)
Pca(channel_name_shot_number, n_components)
Pca(channel_name_shot_number, n_components, window_size)
```

**参数说明：**
- `channel_name_shot_number`: 通道数据（必需）
- `n_components`: 主成分数量（可选，默认2）
- `window_size`: 滑动窗口大小（可选，默认100）

**使用示例：**
```
Pca(B36_11812)
Pca(B36_11812, 3)
Pca(B36_11812, 2, 200)
```

## 测试步骤

### 1. 基本功能测试

1. **打开 Channel Analysis 页面**
2. **在通道列表中选择一个通道**（如 B36_11812）
3. **在公式输入框中测试以下表达式：**

#### FFT 测试
```
FFT(B36_11812)
FFT(B36_11812, 1000)
FFT(B36_11812, 500)
```

#### PCA 测试  
```
Pca(B36_11812)
Pca(B36_11812, 3)
Pca(B36_11812, 2, 150)
```

### 2. UI 功能测试

1. **函数高亮测试**
   - 输入 `FFT` 或 `Pca`，确认函数名有特殊样式（渐变背景）

2. **Tooltip 测试**
   - 鼠标悬浮在 `FFT` 上，查看函数详情
   - 鼠标悬浮在 `Pca` 上，查看函数详情
   - 确认显示参数列表、输出说明等信息

3. **表达式解析测试**
   - 输入包含函数的表达式并点击计算
   - 确认进度条正常显示
   - 确认结果图表正确渲染

### 3. 结果验证

#### FFT 结果验证
- **X轴标签**: Frequency (Hz)
- **Y轴标签**: Amplitude  
- **图表标题**: FFT - 通道名
- **数据特点**: 正频率范围的幅值谱

#### PCA 结果验证
- **X轴标签**: Time (s)
- **Y轴标签**: PC1
- **图表标题**: PCA - 通道名
- **数据特点**: 第一主成分随时间的变化

### 4. 错误处理测试

1. **参数错误测试**
```
FFT()  // 应显示"至少需要1个参数"
FFT(123)  // 应显示"第一个参数必须是通道数据"
Pca(B36_11812, -1)  // 应显示合理的错误信息
```

2. **数据不足测试**
- 测试数据点很少的通道
- 确认错误信息友好

## 依赖要求

### 后端依赖
- `numpy`: 用于FFT计算
- `scikit-learn`: 用于PCA分析（如果未安装会显示友好错误）

### 前端依赖
- `Element Plus`: UI组件
- `Highcharts`: 图表渲染

## 注意事项

1. **PCA功能需要安装 scikit-learn**
   ```bash
   pip install scikit-learn
   ```

2. **FFT对数据长度有要求**
   - 至少需要2个数据点
   - 数据点越多，频率分辨率越高

3. **PCA窗口大小限制**
   - 窗口大小不能超过数据点总数
   - 建议窗口大小为50-500之间

## 预期结果

完成测试后，用户应该能够：
- ✅ 在公式输入框中使用FFT()和Pca()函数
- ✅ 看到函数的详细tooltip信息
- ✅ 获得正确的频域和主成分分析结果
- ✅ 在结果图表中看到合适的轴标签和标题
- ✅ 体验流畅的计算进度反馈 