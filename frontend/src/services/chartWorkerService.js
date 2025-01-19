// 单例 Worker 实例
let worker = null;
let messageHandlers = new Map();
let messageCounter = 0;

// 获取 Worker 实例
const getWorker = () => {
  if (!worker) {
    worker = new Worker(new URL('@/workers/chartWorker.js', import.meta.url));
    worker.onmessage = (e) => {
      const { messageId, type, data, error } = e.data;
      const handler = messageHandlers.get(messageId);
      if (handler) {
        if (error) {
          handler.reject(new Error(error));
        } else {
          handler.resolve({ type, data });
        }
        messageHandlers.delete(messageId);
      }
    };
  }
  return worker;
};

// 处理数据
export const processData = async (channelData, options) => {
  const worker = getWorker();
  const messageId = messageCounter++;

  return new Promise((resolve, reject) => {
    messageHandlers.set(messageId, { resolve, reject });

    try {
      worker.postMessage({
        messageId,
        type: 'processData',
        data: {
          channelData: {
            X_value: channelData.X_value,
            Y_value: channelData.Y_value,
            X_unit: channelData.X_unit,
            Y_unit: channelData.Y_unit,
            channel_type: channelData.channel_type,
            channel_number: channelData.channel_number
          },
          ...options
        }
      });
    } catch (error) {
      messageHandlers.delete(messageId);
      reject(error);
    }
  });
};

// 处理错误数据
export const processErrorData = async (errorData, sampledData, options) => {
  const worker = getWorker();
  const messageId = messageCounter++;

  return new Promise((resolve, reject) => {
    messageHandlers.set(messageId, { resolve, reject });

    try {
      worker.postMessage({
        messageId,
        type: 'processErrorData',
        data: {
          errorData,
          sampledData: {
            X_value: sampledData.X_value,
            Y_value: sampledData.Y_value
          },
          ...options
        }
      });
    } catch (error) {
      messageHandlers.delete(messageId);
      reject(error);
    }
  });
};

// 清理 Worker
export const cleanupWorker = () => {
  if (worker) {
    worker.terminate();
    worker = null;
    messageHandlers.clear();
    messageCounter = 0;
  }
}; 