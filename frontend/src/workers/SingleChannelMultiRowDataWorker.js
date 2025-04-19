// 通道数据处理Web Worker
// 只做数据处理，不涉及Highcharts或DOM操作

self.onmessage = function(e) {
  const { data, channel } = e.data;
  try {
    // 计算统计数据
    const stats = {};
    if (data && data.Y_value && Array.isArray(data.Y_value)) {
      const yMin = Math.min(...data.Y_value);
      const yMax = Math.max(...data.Y_value);
      stats.y_axis_min = yMin;
      stats.y_axis_max = yMax;
      stats.x_min = data.X_value ? Math.min(...data.X_value) : undefined;
      stats.x_max = data.X_value ? Math.max(...data.X_value) : undefined;
    }

    // 判断是否为数字信号（简单判定：只有0/1或true/false）
    let isDigital = false;
    if (data && data.Y_value && Array.isArray(data.Y_value)) {
      const uniqueVals = Array.from(new Set(data.Y_value));
      if (uniqueVals.length <= 2 && uniqueVals.every(v => v === 0 || v === 1 || v === true || v === false)) {
        isDigital = true;
      }
    }

    // 归一化Y值（0-1归一化）
    let Y_normalized = undefined;
    if (data && data.Y_value && Array.isArray(data.Y_value) && stats.y_axis_max !== stats.y_axis_min) {
      Y_normalized = data.Y_value.map(y => (y - stats.y_axis_min) / (stats.y_axis_max - stats.y_axis_min));
    }

    // 返回处理结果
    self.postMessage({
      ...data,
      stats,
      is_digital: isDigital,
      Y_normalized,
      channel_type: data.channel_type || channel?.channel_type || '',
    });
  } catch (err) {
    self.postMessage({ error: err.message });
  }
}; 