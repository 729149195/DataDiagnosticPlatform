// store.js
import { createStore } from "vuex";
import { reactive, ref } from "vue";
import colors from "./color.json"; // 导入 color.json 文件
import axios from "axios";
import { CacheFactory } from 'cachefactory';

// 定义一个映射，用于存储每个 channel_key 分配的颜色
const channelColorMap = new Map();
let colorIndex = 0;

// 缓存工厂配置
const cacheFactory = new CacheFactory();
const dataCache = cacheFactory.createCache('channelData', {
  maxEntries: 200, // 最大缓存条目数
  maxAge: 60 * 60 * 1000, // 30分钟
  deleteOnExpire: 'aggressive',
  storageMode: 'memory', // 纯内存存储
  recycleFreq: 60 * 1000 // 内存回收频率
});

const store = createStore({
  state() {
    return {
      person: "",
      authority: 0,
      StructTree: null,
      selectedChannels: [],
      sampling: 1,
      smoothness: 0,
      anomalies: {},
      matchedResults: [],
      clickedChannelNames: "",
      clickedShownChannelList: [],
      ErrorLineXScopes: [],
      brush_begin: -2,
      brush_end: 6,

      channelSvgElementsRefs: [],
      channelDataCache: reactive({
        // 仅存储缓存元数据
        getCacheInfo: () => ({
          size: dataCache.info().size,
          keys: dataCache.keys()
        })
      }),
      xDomains: {},
      yDomains: {},

      CalculateResult: {},
      time_begin: -0.25,
      time_during: 0,
      time_end: 1.0,
      upper_bound: 0.1,
      scope_bound: 0,
      lower_bound: -2.4,
      isBoxSelect: true,
      previousBoxSelectState: true,
      rawData: [], 
      displayedData: [], 
      pageSize: 15, 
      currentPage: 1, 
      hasMoreData: true, 
      userMessage: "", 
    };
  },
  getters: {
    getStructTree(state) {
      return state.StructTree;
    },
    getSelectedChannels(state) {
      return state.selectedChannels;
    },
    getSampling(state) {
      return state.sampling;
    },
    getSmoothness(state) {
      return state.smoothness;
    },
    getAnomaliesByChannel: (state) => (channelName) => {
      return state.anomalies[channelName] || [];
    },
    getMatchedResults(state) {
      return state.matchedResults;
    },
    getClickedChannelNames(state) {
      return state.clickedChannelNames;
    },
    getDisplayedData(state) {
      return state.displayedData;
    },
    hasMoreData(state) {
      return state.hasMoreData;
    },
  },
  mutations: {
    setperson(state, value) {
      state.person = value;
    },
    setauthority(state, value) {
      state.authority = value;
    },
    setStructTree(state, data) {
      state.StructTree = data;
    },
    setSampling(state, value) {
      state.sampling = value;
    },
    setSmoothness(state, value) {
      state.smoothness = value;
    },
    setSelectedChannels(state, channels) {
      state.selectedChannels = channels;
    },
    addAnomaly(state, { channelName, anomaly }) {
      if (!state.anomalies[channelName]) {
        state.anomalies[channelName] = [];
      }
      anomaly.id = `${anomaly.id}_${Date.now()}`;
      state.anomalies[channelName].push(anomaly);
    },
    updateAnomaly(state, { channelName, anomaly }) {
      if (state.anomalies[channelName]) {
        const index = state.anomalies[channelName].findIndex(
          (a) => a.id === anomaly.id
        );
        if (index !== -1) {
          state.anomalies[channelName][index] = anomaly;
        }
      }
      console.log(state.anomalies);
    },
    updateChannelColor(state, { channel_key, color }) {
      const selectedChannel = state.selectedChannels.find(
        (ch) => ch.channel_key === channel_key
      );
      if (selectedChannel) {
        selectedChannel.color = color;
      }

      if (state.StructTree) {
        state.StructTree.forEach((channelTypeEntry) => {
          if (channelTypeEntry.channels) {
            channelTypeEntry.channels.forEach((channelEntry) => {
              if (channelEntry.channel_key === channel_key) {
                channelEntry.color = color;
              }
            });
            const uniqueColors = new Set(
              channelTypeEntry.channels.map((ch) => ch.color)
            );
            if (uniqueColors.size === 1) {
              channelTypeEntry.color = [...uniqueColors][0];
            } else {
              channelTypeEntry.color = "";
            }
          }
        });
      }
    },
    deleteAnomaly(state, { channelName, anomalyId }) {
      if (state.anomalies[channelName]) {
        state.anomalies[channelName] = state.anomalies[channelName].filter(
          (a) => a.id !== anomalyId
        );
      }
    },
    setMatchedResults(state, results) {
      const extractedRanges = results
        .map((result) => {
          if (Array.isArray(result)) {
            return result.map((match) => ({
              range: match.range,
              channelName: match.channelName,
              shotNumber: match.shotNumber,
              confidence: match.confidence,
            }));
          } else {
            return {
              range: result.range,
              channelName: result.channelName,
              shotNumber: result.shotNumber,
              confidence: result.confidence,
            };
          }
        })
        .flat();

      state.matchedResults = extractedRanges;
    },
    updateChannelName(state, channelName) {
      state.clickedChannelNames = channelName;
    },
    setClickedChannelNames(state, value) {
      state.clickedChannelNames = value;
    },
    addClickedShownChannelList(state, channel) {
      state.clickedShownChannelList.push(channel);
    },
    updatebrush(state, { begin, end }) {
      state.brush_begin = begin;
      state.brush_end = end;
    },
    updateSelectedChannels(state, channels) {
      state.selectedChannels = channels.map((channel) => ({
        channel_key: channel.channel_key, // 添加 channel_key
        channel_name: channel.channel_name,
        shot_number: channel.shot_number,
        color: channel.color,
        channel_type: channel.channel_type,
        errors: channel.errors.map((error) => ({
          error_key: error.error_key, // 添加 error_key
          error_name: error.error_name,
          color: error.color,
        })),
      }));
    },

    updateSelectedChannelsAfterProcessing(state) {
      const updatedSelectedChannels = [];

      const structTreeChannelKeys = new Set();

      if (state.StructTree && state.StructTree.length > 0) {
        state.StructTree.forEach((channelTypeEntry) => {
          if (
            channelTypeEntry.channels &&
            channelTypeEntry.channels.length > 0
          ) {
            channelTypeEntry.channels.forEach((channelEntry) => {
              structTreeChannelKeys.add(channelEntry.channel_key);
            });
          }
        });
      }

      state.selectedChannels.forEach((selectedChannel) => {
        const channelKey = selectedChannel.channel_key;
        if (structTreeChannelKeys.has(channelKey)) {
          updatedSelectedChannels.push(selectedChannel);
        }
      });

      state.selectedChannels = updatedSelectedChannels;

      // 同步 StructTree 中的 channel.checked 状态
      if (state.StructTree) {
        state.StructTree.forEach((channelTypeEntry) => {
          if (channelTypeEntry.channels) {
            channelTypeEntry.channels.forEach((channelEntry) => {
              const isSelected = state.selectedChannels.some(
                (sc) => sc.channel_key === channelEntry.channel_key
              );
              channelEntry.checked = isSelected;
            });
          }
        });
      }
    },
    updateCalculateResult(state, CalculateResult) {
      state.CalculateResult = CalculateResult;
    },
    clearMatchedResults(state) {
      state.matchedResults = [];
    },
    updateTimeBegin(state, value) {
      state.time_begin = value;
    },
    updateTimeDuring(state, value) {
      state.time_during = value;
    },
    updateTimeEnd(state, value) {
      state.time_end = value;
    },
    updateUpperBound(state, value) {
      state.upper_bound = value;
    },
    updateScopeBound(state, value) {
      state.scope_bound = value;
    },
    updateLowerBound(state, value) {
      state.lower_bound = value;
    },
    updateIsBoxSelect(state, value) {
      state.isBoxSelect = value;
    },
    updateDomains(state, { channelName, xDomain, yDomain }) {
      if (xDomain) {
        state.xDomains[channelName] = xDomain;
      }
      if (yDomain) {
        state.yDomains[channelName] = yDomain;
      }
    },
    UPDATE_PREVIOUS_BOX_SELECT_STATE(state, value) {
      state.previousBoxSelectState = value;
    },
    setRawData(state, data) {
      state.rawData = data;
    },
    setDisplayedData(state, data) {
      state.displayedData = data;
    },
    incrementPage(state) {
      state.currentPage += 1;
    },
    setHasMoreData(state, value) {
      state.hasMoreData = value;
    },
    setCurrentPage(state, value) {
      state.currentPage = value;
    },
    setUserMessage(state, message) {
      state.userMessage = message;
    },
    refreshStructTree(state, data) {
      // 保存当前选中状态
      const selectedStates = new Map();
      if (state.displayedData) {
        state.displayedData.forEach(item => {
          if (item.channels) {
            item.channels.forEach(channel => {
              const key = `${channel.channel_name}_${channel.shot_number}`;
              selectedStates.set(key, {
                channelChecked: channel.checked,
                typeChecked: item.checked,
                showAllErrors: channel.showAllErrors
              });
            });
          }
        });
      }

      // 更新数据
      state.rawData = data;
      
      // 恢复选中状态
      if (state.displayedData) {
        state.displayedData.forEach(item => {
          if (item.channels) {
            item.channels.forEach(channel => {
              const key = `${channel.channel_name}_${channel.shot_number}`;
              const savedState = selectedStates.get(key);
              if (savedState) {
                channel.checked = savedState.channelChecked;
                item.checked = savedState.typeChecked;
                channel.showAllErrors = savedState.showAllErrors;
                if (channel.showAllErrors) {
                  channel.displayedErrors = channel.errors;
                } else {
                  channel.displayedErrors = channel.errors.slice(0, 1);
                }
              }
            });
          }
        });
      }
    },
    updateChannelDataCache(state, { channelKey, data }) {
      // 确保数据结构完整
      const safeData = {
        X_value: data?.X_value || [],
        Y_value: data?.Y_value || [],
        ...data
      };
      
      dataCache.put(channelKey, {
        data: reactive(safeData),
        timestamp: Date.now()
      });
    },
    clearChannelDataCache(state) {
      dataCache.removeAll();
    }
  },
  actions: {
    async fetchStructTree({ commit, dispatch }, indices = []) {
      try {
        let url = "https://10.1.108.19:5000/api/struct-tree";
        if (indices.length > 0) {
          const indicesParam = indices.join(",");
          url += `?indices=${encodeURIComponent(indicesParam)}`;
        }
        const response = await fetch(url);
        const rawData = await response.json();
        
        commit("setRawData", rawData);
        commit("setHasMoreData", true);
        commit("setDisplayedData", []);
        commit("setCurrentPage", 1);
        
        // 初始化显示第一页数据
        await dispatch("loadMoreData", true);
      } catch (error) {
        console.error("Failed to fetch data:", error);
      }
    },
    
    async loadMoreData({ state, commit }, isInitial = false) {
      if (!state.hasMoreData && !isInitial) return;
      
      if (isInitial) {
        commit("setDisplayedData", []);
        commit("setCurrentPage", 1);
        commit("setHasMoreData", true);
      }
      
      const startIndex = (state.currentPage - 1) * state.pageSize;
      const endIndex = startIndex + state.pageSize;
      const newData = state.rawData.slice(startIndex, endIndex);
      
      if (newData.length === 0) {
        commit("setHasMoreData", false);
        return;
      }
      
      // 处理新数据
      const processedNewData = processData(newData);
      
      // 合并数据
      let updatedData;
      if (isInitial) {
        updatedData = processedNewData;
      } else {
        updatedData = mergeChannelTypeData(state.displayedData, processedNewData);
      }
        
      commit("setDisplayedData", updatedData);
      commit("incrementPage");
      
      // 检查是否还有更多数据
      commit("setHasMoreData", endIndex < state.rawData.length);
    },
    updateSampling({ commit }, value) {
      commit("setSampling", value);
    },
    updateSmoothness({ commit }, value) {
      commit("setSmoothness", value);
    },
    addAnomaly({ commit }, payload) {
      commit("addAnomaly", payload);
    },
    updateAnomaly({ commit }, payload) {
      commit("updateAnomaly", payload);
    },
    deleteAnomaly({ commit }, payload) {
      commit("deleteAnomaly", payload);
    },
    updateMatchedResults({ commit }, results) {
      commit("setMatchedResults", results);
    },
    updatebrush({ commit }, payload) {
      commit("updatebrush", payload);
    },
    clearMatchedResults({ commit }) {
      commit("clearMatchedResults");
    },
    updateTimeBegin({ commit }, value) {
      commit('updateTimeBegin', value);
    },
    updateTimeDuring({ commit }, value) {
      commit('updateTimeDuring', value);
    },
    updateTimeEnd({ commit }, value) {
      commit('updateTimeEnd', value);
    },
    updateUpperBound({ commit }, value) {
      commit('updateUpperBound', value);
    },
    updateScopeBound({ commit }, value) {
      commit('updateScopeBound', value);
    },
    updateLowerBound({ commit }, value) {
      commit('updateLowerBound', value);
    },
    updateIsBoxSelect({ commit }, value) {
      commit('updateIsBoxSelect', value);
    },
    updateDomains({ commit }, payload) {
      commit('updateDomains', payload);
    },
    updatePreviousBoxSelectState({ commit }, value) {
      commit('UPDATE_PREVIOUS_BOX_SELECT_STATE', value);
    },
    async refreshStructTreeData({ commit, dispatch }) {
      try {
        const response = await fetch("https://10.1.108.19:5000/api/struct-tree");
        const data = await response.json();
        commit("refreshStructTree", data);
        await dispatch("loadMoreData", true);
      } catch (error) {
        console.error("Failed to refresh data:", error);
      }
    },
    async fetchChannelData({ state, commit }, { channel, forceRefresh = false }) {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;
      
      // 使用缓存工厂检查数据
      const cached = dataCache.get(channelKey);
      if (!forceRefresh && cached && Date.now() - cached.timestamp < 300000) {
        return cached.data;
      }

      const params = {
        channel_key: channelKey,
        channel_type: channel.channel_type
      };

      const response = await axios.get(`https://10.1.108.19:5000/api/channel-data/`, { params });
      const data = response.data;

      // 计算原始采样频率
      const timeRange = Math.abs(data.X_value[data.X_value.length - 1] - data.X_value[0]);
      data.originalFrequency = data.X_value.length / timeRange / 1000;
      data.originalDataPoints = data.X_value.length;

      // 存入缓存
      commit('updateChannelDataCache', { channelKey, data });
      return data;
    },
    
    // 添加获取所有错误数据的 action
    async fetchAllErrorData({ state }, channel) {
      try {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        const errorResults = [];

        // 对每个错误类型进行处理
        for (const [errorIndex, error] of channel.errors.entries()) {
          // 如果是 NO ERROR，跳过
          if (error.error_name === "NO ERROR") continue;

          // 构建缓存键
          const errorCacheKey = `${channelKey}-error-${error.error_name}-${errorIndex}-heatmap`;

          // 检查缓存中是否已有数据（使用新的缓存工厂）
          if (dataCache.get(errorCacheKey)) {
            errorResults.push(dataCache.get(errorCacheKey).data);
            continue;
          }

          try {
            // 构建请求参数
            const params = {
              channel_key: channelKey,
              channel_type: channel.channel_type,
              error_name: error.error_name,
              error_index: errorIndex
            };

            // 发送请求获取错误数据
            const response = await fetch(
              `https://10.1.108.19:5000/api/error-data/?${new URLSearchParams(params).toString()}`
            );
            
            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const errorData = await response.json();

            // 将数据存入缓存
            dataCache.put(errorCacheKey, {
              data: reactive(errorData),
              timestamp: Date.now()
            });
            errorResults.push(errorData);
          } catch (err) {
            console.warn(`Failed to fetch error data for ${error.error_name}:`, err);
            // 继续处理下一个错误，而不是中断整个过程
            continue;
          }
        }

        return errorResults;
      } catch (error) {
        console.error('Error fetching all error data:', error);
        throw error;
      }
    }
  },
});

// 添加新的合并函数
function mergeChannelTypeData(existingData, newData) {
  const mergedMap = new Map();
  
  // 首先处理现有数据
  existingData.forEach(item => {
    mergedMap.set(item.channel_type, item);
  });
  
  // 合并新数据
  newData.forEach(newItem => {
    if (mergedMap.has(newItem.channel_type)) {
      // 如果已存在该通道类型，合并channels
      const existingItem = mergedMap.get(newItem.channel_type);
      newItem.channels.forEach(newChannel => {
        // 检查是否已存在相同的channel
        const existingChannel = existingItem.channels.find(
          ch => ch.channel_key === newChannel.channel_key
        );
        if (!existingChannel) {
          existingItem.channels.push(newChannel);
        }
      });
      // 更新通道类型的选中状态
      existingItem.checked = existingItem.channels.every(channel => channel.checked);
    } else {
      // 如果是新的通道类型，直接添加
      mergedMap.set(newItem.channel_type, newItem);
    }
  });
  
  // 转换回数组并返回
  return Array.from(mergedMap.values());
}

function processData(rawData) {
  const groupedData = [];
  const channelTypeMap = {};

  // 获取当前选中的通道
  const selectedChannelKeys = new Set(
    store.state.selectedChannels.map(channel => channel.channel_key)
  );

  rawData.forEach((item) => {
    const channelType = item.channel_type;
    const channelName = item.channel_name;
    const shotNumber = item.shot_number;
    const errorNames = item.error_name && item.error_name.length > 0 ? item.error_name : ["NO ERROR"];

    const channelKey = `${channelName}_${shotNumber}`;

    if (!channelTypeMap[channelType]) {
      channelTypeMap[channelType] = {
        channel_type: channelType,
        color: "",
        checked: false,
        channels: [],
      };
      groupedData.push(channelTypeMap[channelType]);
    }

    const channelTypeEntry = channelTypeMap[channelType];

    // 检查是否已存在相同的channel
    let channelEntry = channelTypeEntry.channels.find(
      (c) => c.channel_key === channelKey
    );

    if (!channelEntry) {
      let colorArray;
      if (channelColorMap.has(channelKey)) {
        colorArray = channelColorMap.get(channelKey);
      } else {
        colorArray = colors[colorIndex % colors.length];
        channelColorMap.set(channelKey, colorArray);
        colorIndex += 1;
      }

      const [r, g, b] = colorArray.map((value) => Math.min(value, 255));
      const colorString = `rgb(${r}, ${g}, ${b})`;

      channelEntry = {
        channel_key: channelKey,
        channel_name: channelName,
        channel_type: channelType,
        shot_number: shotNumber,
        color: colorString,
        // 如果通道之前被选中，保持选中状态
        checked: selectedChannelKeys.has(channelKey),
        errors: [],
        displayedErrors: [],
        showAllErrors: false,
      };
      channelTypeEntry.channels.push(channelEntry);
    }

    // 清空之前的错误
    channelEntry.errors = [];
    
    // 处理错误
    errorNames.forEach((errorName) => {
      const error = {
        error_name: errorName,
        color: errorName === "NO ERROR" ? 'rgba(0, 0, 0, 0)' : 'rgba(220, 20, 60, 0.3)',
      };
      channelEntry.errors.push(error);
    });

    // 更新 displayedErrors
    channelEntry.displayedErrors = channelEntry.errors.slice(0, 1);
  });

  // 更新通道类型的选中状态
  groupedData.forEach(item => {
    if (item.channels.length > 0) {
      item.checked = item.channels.every(channel => channel.checked);
    }
  });

  return groupedData;
}

export default store;
