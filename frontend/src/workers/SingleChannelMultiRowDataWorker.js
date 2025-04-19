// 通道数据处理Web Worker
// 只做数据处理，不涉及Highcharts或DOM操作

self.onmessage = function(e) {
  const { data, channel } = e.data;
  try {
    // 直接透传后端数据，不再重复计算
    self.postMessage({
      ...data,
      channel_type: data.channel_type || channel?.channel_type || '',
      // 其它字段都直接用后端的
    });
  } catch (err) {
    self.postMessage({ error: err.message });
  }
}; 