// store.js
import { createStore } from "vuex";
import { reactive, ref } from "vue";
import colors from "./color.json"; // 导入 color.json 文件

// 定义一个映射，用于存储每个 channel_key 分配的颜色
const channelColorMap = new Map();
let colorIndex = 0;

const store = createStore({
  state() {
    return {
      person: "玛卡巴卡",
      authority: 0,
      StructTree: null,
      selectedChannels: [],
      sampling: 0.1,
      smoothness: 0,
      anomalies: {},
      matchedResults: [],
      clickedChannelNames: "",
      clickedShownChannelList: [],
      ErrorLineXScopes: [],
      brush_begin: -2,
      brush_end: 6,

      channelSvgElementsRefs: [],
      channelDataCache: reactive({}),
      dataCache: ref(new Map()),

      CalculateResult: {},
      time_begin: -0.25,
      time_during: 0,
      time_end: 1.0,
      upper_bound: 0.1,
      scope_bound: 0,
      lower_bound: -2.4,
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
  },
  actions: {
    async fetchStructTree({ commit }, indices = []) {
      try {
        let url = "http://localhost:5000/api/struct-tree";
        if (indices.length > 0) {
          const indicesParam = indices.join(",");
          url += `?indices=${encodeURIComponent(indicesParam)}`;
        }
        const response = await fetch(url);
        const rawData = await response.json();
        const processedData = processData(rawData);

        commit("setStructTree", processedData);

        commit("updateSelectedChannelsAfterProcessing");
      } catch (error) {
        console.error("Failed to fetch data:", error);
      }
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
  },
});

// store.js
function processData(rawData) {
  const groupedData = [];
  const channelTypeMap = {};

  rawData.forEach((item) => {
    const channelType = item.channel_type;
    const channelName = item.channel_name;
    const shotNumber = item.shot_number;
    const errorName = item.error_name;
    const errorOriginArray = item.error_origin;

    const channelKey = `${channelName}_${shotNumber}`; // 确保唯一

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

    let channelEntry = channelTypeEntry.channels.find(
      (c) => c.channel_key === channelKey
    );

    if (!channelEntry) {
      // 分配颜色
      let colorArray;
      if (channelColorMap.has(channelKey)) {
        colorArray = channelColorMap.get(channelKey);
      } else {
        colorArray = colors[colorIndex % colors.length];
        channelColorMap.set(channelKey, colorArray);
        colorIndex += 1;
      }

      // 确保颜色值不超过255
      const [r, g, b] = colorArray.map((value) => Math.min(value, 255));
      const colorString = `rgb(${r}, ${g}, ${b})`;

      channelEntry = {
        channel_key: channelKey, // 添加 channel_key
        channel_name: channelName,
        channel_type: channelType,
        shot_number: shotNumber,
        color: colorString, // 使用分配的颜色
        checked: false,
        errors: [],
        displayedErrors: [],
        showAllErrors: false,
      };
      channelTypeEntry.channels.push(channelEntry);
    }

    errorOriginArray.forEach((origin) => {
      const error = {
        error_name: errorName,
        color: origin ? "rgba(220, 20, 60, 0.3)" : "rgba(220, 20, 60, 0.3)", // 这里保持不变
      };
      channelEntry.errors.push(error);
    });

    if (channelEntry.displayedErrors.length === 0) {
      channelEntry.displayedErrors = channelEntry.errors.slice(0, 1);
    }
  });

  return groupedData;
}

export default store;
