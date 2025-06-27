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
- ✅ **修复：支持带参数的函数高亮和悬浮功能**

### 2. 后端表达式解析器增强  
- ✅ ExpressionParser 支持函数调用语法
- ✅ 添加了 FFT 和 PCA 的具体实现
- ✅ 支持参数解析和类型检查
- ✅ **修复：正确处理内置函数调用**

### 3. 结果可视化增强
- ✅ ChannelCalculationResults.vue 支持不同类型的结果显示
- ✅ FFT 结果显示为频率-幅值图表（X轴：频率Hz，Y轴：幅值）
- ✅ PCA 结果显示为时间-主成分图表（X轴：时间s，Y轴：PC1）
- ✅ **修复：移除图表上方标题，轴标题字体加大加粗**

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
FFT(B36_11812, 1500.5)
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
Pca(B36_11812, 2, 150)
```

## 🐛 修复的问题

### 问题1：函数高亮在有参数时失效
**问题描述：** 当内置函数括号中包含参数时（如 `FFT(B36_11812, 500)`），函数名无法正确高亮，鼠标悬浮也无法显示函数详情。

**解决方案：**
- 修改了 `tokenizeContent` 函数中的简单函数识别逻辑
- 从只匹配 `FFT()` 改为匹配 `FFT(任意内容)`
- 正确解析括号内的参数，支持嵌套括号
- 确保函数名单独标记，保持高亮和tooltip功能
- 将内置函数背景色改为标准蓝色(#409EFF)，去掉紫色渐变

**测试用例：**
- `FFT()` ✅ 正常高亮和tooltip
- `FFT(B36_11812)` ✅ 正常高亮和tooltip  
- `FFT(B36_11812, 500)` ✅ 正常高亮和tooltip
- `Pca(B36_11812, 2, 100)` ✅ 正常高亮和tooltip

### 问题2：图表显示优化
**问题描述：** 图表上方显示不必要的标题，轴标题字体偏小不够突出。

**解决方案：**
- 移除图表上方的标题显示（`title.text = ''`）
- 将X轴和Y轴标题字体从12px/16px增加到18px
- 将轴标题颜色从灰色(#666)改为深色(#333)
- 将字体权重改为粗体(bold)
- 增加标题与轴的距离(margin: 15px)
- 增加图表左边距从60px到80px，防止Y轴标题超出边界

**视觉效果：**
- ❌ 之前：图表上方有"FFT - B36_11812"等标题
- ✅ 现在：干净的图表，无上方标题
- ❌ 之前：轴标题字体较小，颜色较淡
- ✅ 现在：轴标题18px粗体，颜色突出

## 📋 测试检查清单

### 前端功能测试
- [ ] 在ChannelStr中输入 `FFT()` 确认有蓝色高亮背景
- [ ] 鼠标悬浮在 `FFT` 上显示详细tooltip
- [ ] 在ChannelStr中输入 `FFT(B36_11812)` 确认函数名依然高亮
- [ ] 鼠标悬浮在带参数的 `FFT` 上依然显示tooltip
- [ ] 输入 `FFT(B36_11812, 500)` 测试多参数情况
- [ ] 同样测试 `Pca` 函数的各种参数组合

### 后端功能测试
- [ ] 发送 `FFT(B36_11812)` 请求，确认能正确解析和计算
- [ ] 发送 `FFT(B36_11812, 500)` 请求，确认参数传递正确
- [ ] 验证FFT结果包含frequency_spectrum数据
- [ ] 验证PCA结果包含principal_components数据

### 可视化测试
- [ ] FFT结果图表确认无上方标题
- [ ] 确认X轴标题为"Frequency (Hz)"，字体18px粗体
- [ ] 确认Y轴标题为"Amplitude"，字体18px粗体，不超出左边界
- [ ] PCA结果确认轴标题正确且样式一致
- [ ] 确认图表左边距足够，Y轴标题完全可见

## 🔧 技术细节

### 函数解析改进
```javascript
// 修改前：只匹配空括号
const simpleFunctionMatch = content.substring(i).match(/^([A-Za-z][A-Za-z0-9_]*)\(\)/);

// 修改后：匹配任意内容的括号
const simpleFunctionMatch = content.substring(i).match(/^([A-Za-z][A-Za-z0-9_]*)\(/);
```

### 括号匹配算法
```javascript
// 支持嵌套括号的参数解析
let parenthesesCount = 1;
let j = i;
while (j < content.length && parenthesesCount > 0) {
    if (content[j] === '(') parenthesesCount++;
    else if (content[j] === ')') parenthesesCount--;
    j++;
}
```

### 图表样式优化
```javascript
// X轴Y轴标题样式统一
style: {
    fontSize: '18px',
    color: '#333', 
    fontWeight: 'bold'
}
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