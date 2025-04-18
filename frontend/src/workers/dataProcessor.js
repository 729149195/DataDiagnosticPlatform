// frontend/src/workers/dataProcessor.js

self.onmessage = function(e) {
  const { type, payload } = e.data;
  if (type === 'processChannels') {
    const result = processChannels(payload);
    self.postMessage({ type: 'processedChannels', result });
  }
};

function processChannels({ channels, anomalies }) {
  const processedChannels = [];
  let minX = null, maxX = null;
  let minY = null, maxY = null;

  channels.forEach(channel => {
    const x = channel.X_value || [];
    const y = channel.Y_normalized || [];

    x.forEach(val => {
      if (minX === null || val < minX) minX = val;
      if (maxX === null || val > maxX) maxX = val;
    });
    y.forEach(val => {
      if (minY === null || val < minY) minY = val;
      if (maxY === null || val > maxY) maxY = val;
    });

    let errorData = [];
    if (channel.errors && channel.errors.length > 0) {
      errorData = channel.errors.map(error => {
        return error;
      });
    }

    processedChannels.push({
      channelKey: `${channel.channel_name}_${channel.shot_number}`,
      channelName: channel.channel_name,
      channelshotnumber: channel.shot_number,
      color: channel.color,
      data: { x, y },
      channel,
      errorData
    });
  });

  let processedAnomalies = [];
  if (anomalies) {
    processedAnomalies = anomalies;
  }

  return {
    processedChannels,
    xDomain: [minX, maxX],
    yDomain: [minY, maxY],
    processedAnomalies
  };
} 