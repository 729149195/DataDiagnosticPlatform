// store.js
import { createStore } from "vuex";
import { reactive, ref } from "vue";
import colors from "./color.json"; // 导入 color.json 文件
import axios from "axios";
import { dataCache, isChannelSelected } from "./services/cacheManager";
import indexedDBService from "./services/indexedDBService"; // 导入IndexedDB服务

// 定义一个映射，用于存储每个 channel_key 分配的颜色
const channelColorMap = new Map();
let colorIndex = 0;

// 添加一个用于跟踪进行中的请求的映射
const pendingRequests = new Map();

// 从IndexedDB加载缓存数据到内存缓存
async function loadCacheFromIndexedDB() {
  if (!indexedDBService.isSupported) {
    console.log("当前浏览器不支持IndexedDB，跳过加载缓存数据");
    return;
  }
  try {
    const keys = await indexedDBService.getAllKeys();

    for (const key of keys) {
      const cacheItem = await indexedDBService.getChannelData(key);
      if (cacheItem && cacheItem.data) {
        // 检查数据是否在有效期内（7天）
        if (Date.now() - cacheItem.timestamp < 7 * 24 * 60 * 60 * 1000) {
          // 将数据放入内存缓存，使用当前时间戳
          dataCache.put(key, {
            data: reactive(cacheItem.data),
            timestamp: Date.now(), // 使用当前时间戳，而不是原始时间戳
          });
        } else {
          console.log(`跳过过期的缓存数据: ${key}`);
        }
      }
    }
  } catch (error) {
    console.error("从IndexedDB加载缓存数据失败:", error);
  }
}

// 页面加载时从IndexedDB加载缓存
loadCacheFromIndexedDB();

const store = createStore({
  state() {
    return {
      person: "",
      authority: 0,
      StructTree: null,
      selectedChannels: [],
      sampling: 5,
      smoothness: 0,
      anomalies: {},
      matchedResults: [],
      matchedResultsCleared: null,
      clickedChannelNames: "",
      clickedShownChannelList: [],
      ErrorLineXScopes: [],
      brush_begin: -2,
      brush_end: 5,
      unit_sampling: 10,

      channelSvgElementsRefs: [],
      channelDataCache: reactive({
        // 仅存储缓存元数据
        getCacheInfo: () => ({
          size: dataCache.info().size,
          keys: dataCache.keys(),
        }),
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
      isBoxSelect: false,
      previousBoxSelectState: false,
      rawData: [],
      displayedData: [],
      pageSize: 15,
      currentPage: 1,
      hasMoreData: true,
      userMessage: "",
      isCalculating: false,
      calculatingProgress: {
        step: "",
        progress: 0,
      },
      queryPattern: null,
      samplingVersion: 0,
      visibleMatchedResultIds: [],
      errorNamesVersion: { version: 0, channels: [] }, // 新增：异常名索引版本号，包含变动通道key数组
      showFFT: false, // 新增：是否显示FFT数据，默认为false
      calculationErrorRanges: [], // 新增：计算结果的异常区域数据
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
    getQueryPattern(state) {
      return state.queryPattern;
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
      state.samplingVersion++;
    },
    setSamplingVersion(state, newVersion) {
      state.samplingVersion = newVersion;
    },
    setSmoothness(state, value) {
      state.smoothness = value;
    },
    setSelectedChannels(state, channels) {
      state.selectedChannels = channels;

      // 触发缓存重新评估
      dataCache.keys().forEach((key) => {
        dataCache.touch(key);
      });
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
      // console.log(state.anomalies);
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
        // 查找要删除的异常，以获取更多信息
        const anomalyToDelete = state.anomalies[channelName].find(
          (a) => a.id === anomalyId
        );

        // 删除内存中的异常
        state.anomalies[channelName] = state.anomalies[channelName].filter(
          (a) => a.id !== anomalyId
        );

        // 如果找到了异常
        if (anomalyToDelete) {
          // 构造异常缓存的key
          const channelKey = channelName; // 通道key就是channelName

          // 尝试找到与该异常相关的所有缓存，并删除它们
          dataCache.keys().forEach((key) => {
            // 检查是否是该通道的异常缓存
            if (key.startsWith(`error-${channelKey}`)) {
              // 从内存缓存中移除
              dataCache.remove(key);

              // 异步从IndexedDB中移除
              setTimeout(() => {
                indexedDBService.deleteChannelData(key).catch((error) => {
                  console.error(
                    `从IndexedDB中删除异常缓存失败 (${key}):`,
                    error
                  );
                });
              }, 0);
            }
          });
        }
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
              smoothLevel: match.smoothLevel, // 加上这一行
            }));
          } else {
            return {
              range: result.range,
              channelName: result.channelName,
              shotNumber: result.shotNumber,
              confidence: result.confidence,
              smoothLevel: result.smoothLevel, // 加上这一行
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
      // 清空数组，然后添加新的通道
      state.clickedShownChannelList = [channel];
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

      // 触发缓存重新评估
      dataCache.keys().forEach((key) => {
        dataCache.touch(key);
      });
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

      // 触发缓存重新评估
      dataCache.keys().forEach((key) => {
        dataCache.touch(key);
      });
    },
    updateCalculateResult(state, CalculateResult) {
      state.CalculateResult = CalculateResult;
    },
    clearMatchedResults(state) {
      // 先将数组清空
      state.matchedResults.length = 0;

      // 然后重新赋值为空数组，确保引用也更新
      state.matchedResults = [];

      // 添加一个特殊标记，表示这是一次清除操作，而不是普通的更新
      state.matchedResultsCleared = Date.now();
    },
    setQueryPattern(state, patternData) {
      state.queryPattern = patternData;
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
    setVisibleMatchedResultIds(state, ids) {
      state.visibleMatchedResultIds = ids;
    },
    refreshStructTree(state, data) {
      // 保存当前选中状态和异常展示状态
      const selectedStates = new Map();

      // 1. 首先从displayedData中获取当前可见通道的选中状态和异常展示状态
      if (state.displayedData) {
        state.displayedData.forEach((item) => {
          if (item.channels) {
            item.channels.forEach((channel) => {
              const key = `${channel.channel_name}_${channel.shot_number}`;
              selectedStates.set(key, {
                channelChecked: channel.checked,
                typeChecked: item.checked,
                showAllErrors: channel.showAllErrors,
                displayedErrors: channel.displayedErrors.map(
                  (e) => e.error_name
                ), // 保存显示的异常类别
                errors: channel.errors.map((e) => ({
                  error_name: e.error_name,
                  color: e.color,
                })), // 保存完整的异常信息
              });
            });
          }
        });
      }

      // 2. 从selectedChannels中获取额外的选中状态信息
      // 这确保了不在当前显示页面的选中通道信息也被保存
      if (state.selectedChannels && state.selectedChannels.length > 0) {
        state.selectedChannels.forEach((channel) => {
          const key = `${channel.channel_name}_${channel.shot_number}`;
          if (!selectedStates.has(key)) {
            selectedStates.set(key, {
              channelChecked: true, // 如果在selectedChannels中，那么它一定是选中的
              typeChecked: false, // 先设为false，后面会根据通道类型进行更新
              showAllErrors: false,
              displayedErrors: [],
              errors:
                channel.errors?.map((e) => ({
                  error_name: e.error_name,
                  color: e.color,
                })) || [],
            });
          } else {
            // 更新selectedStates中的errors，确保使用最新的错误数据
            const stateEntry = selectedStates.get(key);
            stateEntry.errors =
              channel.errors?.map((e) => ({
                error_name: e.error_name,
                color: e.color,
              })) || [];
          }
        });
      }

      // 更新数据
      state.rawData = data;

      // 恢复选中状态
      if (state.displayedData) {
        state.displayedData.forEach((item) => {
          if (item.channels) {
            // 记录该通道类型中有选中通道的数量
            let checkedChannelsCount = 0;
            let totalChannelsCount = item.channels.length;

            item.channels.forEach((channel) => {
              const key = `${channel.channel_name}_${channel.shot_number}`;
              const savedState = selectedStates.get(key);
              if (savedState) {
                // 保留之前的选中状态，但空数据通道不能被选中
                if (channel.status === 'empty_data') {
                  channel.checked = false;
                } else {
                  channel.checked = savedState.channelChecked;
                  if (channel.checked) {
                    checkedChannelsCount++;
                  }
                }

                // 保留展开/折叠状态
                channel.showAllErrors = savedState.showAllErrors;

                // 如果新数据中存在之前保存的错误，则优先使用新数据中的错误
                // 否则保留原来的错误信息
                if (savedState.errors && savedState.errors.length > 0) {
                  // 查找新数据中相同名称的错误类别
                  channel.errors.forEach((newError, index) => {
                    const matchingError = savedState.errors.find(
                      (e) => e.error_name === newError.error_name
                    );
                    if (matchingError) {
                      // 保留颜色信息
                      newError.color = matchingError.color;
                    }
                  });
                }

                // 恢复显示的错误类别
                if (channel.showAllErrors) {
                  channel.displayedErrors = channel.errors;
                } else {
                  // 如果之前有显示特定的错误，尝试恢复相同名称的错误
                  if (
                    savedState.displayedErrors &&
                    savedState.displayedErrors.length > 0
                  ) {
                    channel.displayedErrors = channel.errors.filter((error) =>
                      savedState.displayedErrors.includes(error.error_name)
                    );
                    // 如果没有匹配的错误，显示第一个错误
                    if (
                      channel.displayedErrors.length === 0 &&
                      channel.errors.length > 0
                    ) {
                      channel.displayedErrors = [channel.errors[0]];
                    }
                  } else {
                    channel.displayedErrors = channel.errors.slice(0, 1);
                  }
                }
              } else {
                // 没有保存状态的新通道，默认只显示第一个错误
                channel.displayedErrors = channel.errors.slice(0, 1);
              }
            });

            // 只考虑非空数据的通道
            const validChannels = item.channels.filter(channel => channel.status !== 'empty_data');
            if (checkedChannelsCount > 0) {
              item.checked = checkedChannelsCount === validChannels.length;
            } else {
              item.checked = false;
            }
            // 检查是否所有通道都是空数据
            item.allChannelsEmpty = item.channels.every(channel => channel.status === 'empty_data');
          }
        });
      }
    },
    updateChannelDataCache(state, { channelKey, data }) {
      // 使用Object.assign进行浅拷贝，比创建新对象更高效
      // 只设置必要的默认值，减少属性访问和条件判断
      const enhancedData = Object.assign(
        {
          X_value: data.X_value || [],
          Y_value: data.Y_value || [],
          originalFrequency: data.originalFrequency || 1.0,
          originalDataPoints: data.points || 0,
          channel_number: data.channel_number || channelKey.split("_")[0],
          X_unit: data.X_unit || "s",
          Y_unit: data.Y_unit || "",
        },
        data
      );

      const timestamp = Date.now();

      // 更新内存缓存
      dataCache.put(channelKey, {
        data: reactive(enhancedData),
        timestamp: timestamp,
      });

      // 异步保存到IndexedDB，不阻塞UI线程
      setTimeout(() => {
        indexedDBService
          .saveChannelData(channelKey, enhancedData, timestamp)
          .catch((error) => {
            console.error(
              `保存通道数据到IndexedDB失败 (${channelKey}):`,
              error
            );
          });
      }, 0);
    },
    clearChannelDataCache(state) {
      // 清空内存缓存
      dataCache.removeAll();

      // 异步清空IndexedDB缓存，不阻塞UI线程
      setTimeout(() => {
        indexedDBService.clearAllChannelData().catch((error) => {
          console.error("清空IndexedDB缓存失败:", error);
        });
      }, 0);
    },
    removeChannelDataCache(state, channelKey) {
      // 从内存缓存中移除
      dataCache.remove(channelKey);

      // 异步从IndexedDB中移除，不阻塞UI线程
      setTimeout(() => {
        indexedDBService.deleteChannelData(channelKey).catch((error) => {
          console.error(`从IndexedDB中删除缓存失败 (${channelKey}):`, error);
        });
      }, 0);
    },
    clearAnomalies(state) {
      // 获取所有通道keys
      const channelKeys = Object.keys(state.anomalies);

      // 清空内存中的 anomalies 对象
      state.anomalies = {};

      // 清理相关缓存
      channelKeys.forEach((channelKey) => {
        // 查找并删除该通道相关的所有异常缓存
        dataCache.keys().forEach((key) => {
          if (key.startsWith(`error-${channelKey}`)) {
            // 从内存缓存中移除
            dataCache.remove(key);

            // 异步从IndexedDB中移除
            setTimeout(() => {
              indexedDBService.deleteChannelData(key).catch((error) => {
                console.error(`从IndexedDB中删除异常缓存失败 (${key}):`, error);
              });
            }, 0);
          }
        });
      });
    },
    setCalculatingStatus(state, status) {
      state.isCalculating = status;
    },
    setCalculatingProgress(state, { step, progress }) {
      state.calculatingProgress = { step, progress };
    },
    setUnitSampling(state, value) {
      state.unit_sampling = value;
    },
    updateChannelErrors(state, { channelName, shotNumber, errors }) {
      // 更新选中通道中的错误数据
      if (state.selectedChannels && state.selectedChannels.length > 0) {
        state.selectedChannels.forEach((channel) => {
          if (
            channel.channel_name === channelName &&
            channel.shot_number === shotNumber
          ) {
            channel.errors = errors.map((error) => ({
              error_key: error.error_key || null,
              error_name: error.error_name,
              color: error.color || "rgba(220, 20, 60, 0.3)",
            }));
          }
        });
      }

      // 更新显示数据中的错误信息
      if (state.displayedData && state.displayedData.length > 0) {
        state.displayedData.forEach((item) => {
          if (item.channels && item.channels.length > 0) {
            item.channels.forEach((channel) => {
              if (
                channel.channel_name === channelName &&
                channel.shot_number === shotNumber
              ) {
                // 保存当前显示状态
                const showAllErrors = channel.showAllErrors;
                const oldDisplayedErrorNames = channel.displayedErrors.map(
                  (error) => error.error_name
                );

                // 更新错误列表
                channel.errors = errors.map((error) => ({
                  error_name: error.error_name,
                  color: error.color || "rgba(220, 20, 60, 0.3)",
                }));

                // 恢复显示状态
                if (showAllErrors) {
                  channel.displayedErrors = channel.errors;
                } else {
                  // 尝试保留之前显示的错误类别
                  channel.displayedErrors = channel.errors.filter((error) =>
                    oldDisplayedErrorNames.includes(error.error_name)
                  );

                  // 如果没有匹配的错误，显示第一个错误
                  if (
                    channel.displayedErrors.length === 0 &&
                    channel.errors.length > 0
                  ) {
                    channel.displayedErrors = [channel.errors[0]];
                  }
                }
              }
            });
          }
        });
      }
    },
    incrementErrorNamesVersion(state, payload = { channels: [] }) {
      // 递增版本号，并记录本次变动的通道key数组
      state.errorNamesVersion = {
        version: (state.errorNamesVersion.version || 0) + 1,
        channels: payload.channels || [],
      };
      // console.log(state.errorNamesVersion);
    },

    updateShowFFT(state, value) {
      state.showFFT = value;
    },
    setCalculationErrorRanges(state, ranges) {
      state.calculationErrorRanges = ranges || [];
    },
  },
  actions: {
    async fetchStructTree({ commit, dispatch }, filterParams = []) {
      try {
        let url = "http://192.168.20.49:5000/api/struct-tree";
        let params = [];
        // 兼容老用法：如果传的是数组，视为shot_numbers
        if (Array.isArray(filterParams)) {
          if (filterParams.length > 0) {
            params.push(`shot_numbers=${filterParams.join(",")}`);
          }
        } else if (typeof filterParams === 'object' && filterParams !== null) {
          if (filterParams.shot_numbers && filterParams.shot_numbers.length > 0) {
            params.push(`shot_numbers=${filterParams.shot_numbers.join(",")}`);
          }
          if (filterParams.channel_names && filterParams.channel_names.length > 0) {
            params.push(`channel_names=${filterParams.channel_names.join(",")}`);
          }
          if (filterParams.error_names && filterParams.error_names.length > 0) {
            params.push(`error_names=${filterParams.error_names.join(",")}`);
          }
          
        }
        if (params.length > 0) {
          url += "?" + params.join("&");
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
        updatedData = mergeChannelTypeData(
          state.displayedData,
          processedNewData
        );
      }

      commit("setDisplayedData", updatedData);
      commit("incrementPage");

      // 检查是否还有更多数据
      commit("setHasMoreData", endIndex < state.rawData.length);
    },
    updateSampling({ commit, state, dispatch }, value) {
      commit("setSampling", value);

      // 当采样率更改时，刷新所有选定通道的数据
      if (state.selectedChannels && state.selectedChannels.length > 0) {
        // console.log(`采样率更改为 ${value} KHz，重新加载所有选定通道数据`);

        // 为每个选定的通道创建强制刷新请求
        const refreshPromises = state.selectedChannels.map((channel) => {
          return dispatch("fetchChannelData", {
            channel,
            forceRefresh: true,
          }).catch((error) => {
            console.error(
              `刷新通道 ${channel.channel_name}_${channel.shot_number} 数据失败:`,
              error
            );
            return null;
          });
        });

        // 无需等待所有请求完成，让它们并行执行
        // 各个组件会通过监听数据缓存的变化来更新自己
        return Promise.all(refreshPromises).then(() => {
          // console.log('所有通道数据已更新完成');
        });
      }
    },
    updateSmoothness({ commit }, value) {
      commit("setSmoothness", value);
    },
    updateUnitSampling({ commit }, value) {
      commit("setUnitSampling", value);
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
      commit("updateTimeBegin", value);
    },
    updateTimeDuring({ commit }, value) {
      commit("updateTimeDuring", value);
    },
    updateTimeEnd({ commit }, value) {
      commit("updateTimeEnd", value);
    },
    updateUpperBound({ commit }, value) {
      commit("updateUpperBound", value);
    },
    updateScopeBound({ commit }, value) {
      commit("updateScopeBound", value);
    },
    updateLowerBound({ commit }, value) {
      commit("updateLowerBound", value);
    },
    updateIsBoxSelect({ commit }, value) {
      commit("updateIsBoxSelect", value);
    },
    updateDomains({ commit }, payload) {
      commit("updateDomains", payload);
    },
    updatePreviousBoxSelectState({ commit }, value) {
      commit("UPDATE_PREVIOUS_BOX_SELECT_STATE", value);
    },
    async refreshStructTreeData({ commit, dispatch }) {
      try {
        const response = await fetch(
          "http://192.168.20.49:5000/api/struct-tree"
        );
        const data = await response.json();
        commit("refreshStructTree", data);
        await dispatch("loadMoreData", true);
      } catch (error) {
        console.error("Failed to refresh data:", error);
      }
    },
    async fetchChannelData(
      { state, commit },
      {
        channel,
        forceRefresh = false,
        sample_mode = "downsample",
        sample_freq = null,
      }
    ) {
      const channelKey = `${channel.channel_name}_${channel.shot_number}`;

      // 如果需要原始频率数据，使用新的缓存键
      const useOriginalFrequency = sample_mode === "full";
      // 为自定义频率创建特定的缓存键
      const hasCustomFreq =
        sample_freq !== null && sample_mode === "downsample";
      const cacheKey = useOriginalFrequency
        ? `original_${channelKey}`
        : hasCustomFreq
        ? `custom_${sample_freq}_${channelKey}`
        : `${channelKey}`;

      // 如果强制刷新，跳过所有缓存检查
      if (forceRefresh) {
        // console.log(`强制刷新通道数据: ${channelKey}`);
      } else {
        // 首先检查内存缓存 - 内存缓存是最快的
        const cached = dataCache.get(cacheKey);
        if (cached) {
          // 内存缓存存在，检查是否在有效期内（30分钟）
          if (Date.now() - cached.timestamp < 30 * 60 * 1000) {
            // console.log(`使用内存缓存数据: ${channelKey}`);
            return cached.data;
          } else {
            // console.log(`内存缓存已过期: ${channelKey}，检查IndexedDB`);
          }
        }

        // 内存缓存不存在或已过期，尝试从IndexedDB获取
        try {
          const dbCached = await indexedDBService.getChannelData(cacheKey);
          if (dbCached && dbCached.data) {
            // 检查IndexedDB缓存是否在有效期内（7天）
            if (Date.now() - dbCached.timestamp < 7 * 24 * 60 * 60 * 1000) {
              // console.log(`从IndexedDB加载通道数据: ${channelKey}`);

              // 直接使用缓存数据，不做额外处理
              const cachedData = dbCached.data;

              // 将数据放入内存缓存，更新时间戳为当前时间
              // 使用reactive包装，但不做额外处理
              const reactiveData = reactive(cachedData);

              // 异步更新内存缓存，不阻塞主流程
              setTimeout(() => {
                dataCache.put(cacheKey, {
                  data: reactiveData,
                  timestamp: Date.now(),
                });
              }, 0);

              return reactiveData;
            } else {
              // console.log(`IndexedDB缓存已过期: ${channelKey}，从服务器获取`);
            }
          }
        } catch (error) {
          console.error(`从IndexedDB获取通道数据失败 (${channelKey}):`, error);
        }
      }

      // 检查是否有相同的请求正在进行中
      const pendingKey = `${cacheKey}_${sample_mode}`;
      if (pendingRequests.has(pendingKey)) {
        // console.log(`复用进行中的请求: ${channelKey}`);
        return pendingRequests.get(pendingKey);
      }

      // console.log(`从服务器获取通道数据: ${channelKey}`);
      const params = {
        channel_key: channelKey,
        channel_type: channel.channel_type,
        sample_mode: sample_mode, // 添加采样模式参数
      };

      // 使用传入的自定义频率或当前状态的采样率
      if (sample_freq !== null) {
        params.sample_freq = sample_freq;
      } else {
        params.sample_freq = state.sampling;
      }

      // 创建请求的 Promise 并将其存储
      const requestPromise = new Promise(async (resolve, reject) => {
        try {
          const response = await axios.get(
            `http://192.168.20.49:5000/api/channel-data`,
            { params }
          );
          // 获取原始数据
          const originalData = response.data;

          // 直接使用后端返回的数据，不做额外处理
          // 使用后端预计算的统计数据
          const enhancedData = {
            ...originalData,
            // 确保这些字段存在，即使后端没有提供
            channel_number: originalData.channel_number || channel.channel_name,
            originalDataPoints: originalData.points || 0,
            originalFrequency: originalData.originalFrequency || 1.0,
            X_unit: originalData.X_unit || "s",
            Y_unit: originalData.Y_unit || "",
            // 如果后端提供了统计数据，直接使用
            stats: originalData.stats || {
              y_min: 0,
              y_max: 0,
              y_mean: 0,
              y_median: 0,
              y_std: 0,
              x_min: 0,
              x_max: 0,
              y_axis_min: 0,
              y_axis_max: 0,
            },
            channel_type: originalData.channel_type || channel.channel_type,
            is_digital: originalData.is_digital || false,
            Y_normalized: originalData.Y_normalized || [],
            // 确保FFT相关字段被正确保存
            freq: originalData.freq || null,
            amplitude: originalData.amplitude || null,
          };

          // 异步存储到缓存，不阻塞主流程
          setTimeout(() => {
            commit("updateChannelDataCache", {
              channelKey: cacheKey,
              data: enhancedData,
            });
          }, 0);

          resolve(enhancedData);
        } catch (error) {
          reject(error);
        } finally {
          // 无论成功或失败，都从进行中的请求映射中移除
          pendingRequests.delete(pendingKey);
        }
      });

      // 将请求存储到进行中的请求映射
      pendingRequests.set(pendingKey, requestPromise);

      return requestPromise;
    },

    // 添加获取所有错误数据的 action
    async fetchAllErrorData({ state, commit }, channel) {
      try {
        const channelKey = `${channel.channel_name}_${channel.shot_number}`;
        const errorResults = [];

        // 对每个错误类型进行处理
        for (const [errorIndex, error] of channel.errors.entries()) {
          // 如果是 NO ERROR，跳过
          if (error.error_name === "NO ERROR") continue;

          // 构建缓存键
          const errorCacheKey = `error-${channelKey}-${error.error_name}-${errorIndex}`;

          // 检查内存缓存中是否已有数据
          const cached = dataCache.get(errorCacheKey);
          if (cached) {
            // 检查内存缓存是否在有效期内（30分钟）
            if (Date.now() - cached.timestamp < 30 * 60 * 1000) {
              // console.log(`使用内存缓存的错误数据: ${errorCacheKey}`);
              errorResults.push(cached.data);
              continue;
            } else {
              // console.log(`内存缓存的错误数据已过期: ${errorCacheKey}，检查IndexedDB`);
            }
          }

          // 如果内存中没有缓存或已过期，尝试从IndexedDB获取
          try {
            const dbCached = await indexedDBService.getChannelData(
              errorCacheKey
            );
            if (dbCached && dbCached.data) {
              // 检查IndexedDB缓存是否在有效期内（7天）
              if (Date.now() - dbCached.timestamp < 7 * 24 * 60 * 60 * 1000) {
                // console.log(`从IndexedDB加载错误数据: ${errorCacheKey}`);

                // 将数据放入内存缓存，更新时间戳为当前时间
                const reactiveData = reactive(dbCached.data);
                dataCache.put(errorCacheKey, {
                  data: reactiveData,
                  timestamp: Date.now(), // 更新时间戳为当前时间
                });
                errorResults.push(reactiveData);
                continue;
              } else {
                // console.log(`IndexedDB缓存的错误数据已过期: ${errorCacheKey}，从服务器获取`);
              }
            }
          } catch (error) {
            console.error(
              `从IndexedDB获取错误数据失败 (${errorCacheKey}):`,
              error
            );
          }

          try {
            // console.log(`从服务器获取错误数据: ${errorCacheKey}`);
            // 构建请求参数
            const params = {
              channel_key: channelKey,
              channel_type: channel.channel_type,
              error_name: error.error_name,
              error_index: errorIndex,
            };

            // 发送请求获取错误数据
            const response = await fetch(
              `http://192.168.20.49:5000/api/error-data?${new URLSearchParams(
                params
              ).toString()}`
            );

            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }

            const errorData = await response.json();

            // 处理错误数据中的错误范围
            if (errorData && Array.isArray(errorData)) {
              // 处理人工标注和机器识别的错误数据
              errorData.forEach((errorTypeGroup) => {
                if (Array.isArray(errorTypeGroup)) {
                  errorTypeGroup.forEach((error) => {
                    if (
                      error &&
                      error.X_error &&
                      Array.isArray(error.X_error)
                    ) {
                      // 处理每个错误范围
                      error.X_error = error.X_error.map((range) => {
                        // 如果是包含多个连续值的数组，只保留第一个和最后一个值
                        if (Array.isArray(range) && range.length > 2) {
                          return [range[0], range[range.length - 1]];
                        }
                        // 如果已经是标准格式或其他格式，保持不变
                        return range;
                      });
                    }
                  });
                }
              });
            }

            // 将处理后的数据存入缓存
            const timestamp = Date.now();
            const reactiveErrorData = reactive(errorData);

            // 更新内存缓存
            dataCache.put(errorCacheKey, {
              data: reactiveErrorData,
              timestamp: timestamp,
            });

            // 同时保存到IndexedDB
            indexedDBService
              .saveChannelData(errorCacheKey, errorData, timestamp)
              .catch((error) => {
                console.error(
                  `保存错误数据到IndexedDB失败 (${errorCacheKey}):`,
                  error
                );
              });

            errorResults.push(reactiveErrorData);
          } catch (err) {
            console.warn(
              `Failed to fetch error data for ${error.error_name}:`,
              err
            );
            // 继续处理下一个错误，而不是中断整个过程
            continue;
          }
        }

        return errorResults;
      } catch (error) {
        console.error("Error fetching all error data:", error);
        throw error;
      }
    },
    // 管理缓存存储
    async manageCacheStorage({ state, commit }) {
      try {
        // 获取IndexedDB存储使用情况
        const usage = await indexedDBService.getStorageUsage();
        // console.log('IndexedDB存储使用情况:', usage);

        // 如果存储超过100MB，清理过期数据
        if (usage.size > 100 * 1024 * 1024) {
          // console.log('IndexedDB存储超过100MB，开始清理过期数据...');
          const cleanedCount = await indexedDBService.cleanupExpiredData(
            3 * 24 * 60 * 60 * 1000
          ); // 3天
          // console.log(`清理了 ${cleanedCount} 条过期数据`);
        }

        return usage;
      } catch (error) {
        console.error("管理缓存存储失败:", error);
        return { count: 0, size: 0 };
      }
    },
    updateQueryPattern({ commit }, patternData) {
      commit("setQueryPattern", patternData);
    },
    updateChannelErrors({ commit }, { channelName, shotNumber, errors }) {
      commit("updateChannelErrors", { channelName, shotNumber, errors });
    },
    /**
     * 更新通道异常数据而不刷新整个表格
     * 这个方法用于异常添加/删除后只更新相关通道的异常数据
     */
    async updateChannelErrorsData({ commit, state }) {
      try {
        // 获取当前显示的所有通道
        const displayedChannels = [];
        
        if (state.displayedData) {
          state.displayedData.forEach((item) => {
            if (item.channels) {
              item.channels.forEach((channel) => {
                displayedChannels.push({
                  channel_name: channel.channel_name,
                  shot_number: channel.shot_number,
                  channel_type: item.channel_type,
                });
              });
            }
          });
        }

        // 获取通道异常数据
        if (displayedChannels.length > 0) {
          const response = await fetch(
            "http://192.168.20.49:5000/api/get-channels-errors",
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
              },
              body: JSON.stringify({ 
                channels: displayedChannels
              }),
            }
          );

          if (!response.ok) {
            throw new Error(`获取通道异常数据失败: ${response.statusText}`);
          }

          const data = await response.json();

          // 更新每个通道的异常数据
          data.forEach((channelData) => {
            const { channel_name, shot_number, errors } = channelData;
            // 使用刚刚创建的updateChannelErrors操作更新异常数据
            commit("updateChannelErrors", {
              channelName: channel_name,
              shotNumber: shot_number,
              errors: errors || [],
            });
          });
        }
      } catch (error) {
        console.error("Failed to update channel errors:", error);
      }
    },
    async refreshErrorNames({ commit, state }, shotNumbers = null) {
      try {
        let url = "http://192.168.20.49:5000/api/get-errors-name-index";
        const params = {};
        
        // 如果提供了炮号参数，添加到请求中
        if (shotNumbers && shotNumbers.length > 0) {
          params.shot_numbers = shotNumbers.join(',');
        }
        
        const response = await axios.get(url, { params });
        return response.data;
      } catch (error) {
        console.error("异常名索引获取失败:", error);
        throw error;
      }
    },
    updateShowFFT({ commit }, value) {
      commit("updateShowFFT", value);
    },
  },
});

// 在store创建后，替换dataCache的onExpire函数
dataCache.setOptions({
  onExpire: (key, value, reason) => {
    // 检查通道是否在selectedChannels中
    const isSelected = isChannelSelected(key, store.state.selectedChannels);

    // 如果通道在selectedChannels中，则不允许过期（返回false）
    // 如果通道不在selectedChannels中，则允许从内存中过期（返回true）
    // 注意：这里只影响内存缓存，不会删除IndexedDB中的数据
    return !isSelected;
  },
});

// 定期检查和管理缓存存储（每小时一次）
setTimeout(() => {
  store.dispatch("manageCacheStorage");
}, 5000); // 页面加载5秒后进行第一次检查

setInterval(() => {
  store.dispatch("manageCacheStorage");
}, 60 * 60 * 1000); // 之后每小时检查一次

// 添加新的合并函数
function mergeChannelTypeData(existingData, newData) {
  const mergedMap = new Map();

  // 首先处理现有数据
  existingData.forEach((item) => {
    mergedMap.set(item.channel_type, item);
  });

  // 合并新数据
  newData.forEach((newItem) => {
    if (mergedMap.has(newItem.channel_type)) {
      // 如果已存在该通道类型，合并channels
      const existingItem = mergedMap.get(newItem.channel_type);
      newItem.channels.forEach((newChannel) => {
        // 检查是否已存在相同的channel
        const existingChannel = existingItem.channels.find(
          (ch) => ch.channel_key === newChannel.channel_key
        );
        if (!existingChannel) {
          existingItem.channels.push(newChannel);
        } else {
          // 如果通道已存在，更新状态字段
          existingChannel.status = newChannel.status;
          existingChannel.status_message = newChannel.status_message;
        }
      });
      // 更新通道类型的选中状态
      const validChannels = existingItem.channels.filter(channel => channel.status !== 'empty_data');
      existingItem.checked = validChannels.length > 0 && validChannels.every((channel) => channel.checked);
      // 检查是否所有通道都是空数据
      existingItem.allChannelsEmpty = existingItem.channels.every(channel => channel.status === 'empty_data');
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
    store.state.selectedChannels.map((channel) => channel.channel_key)
  );

  // 保存当前显示的通道的错误状态和颜色信息
  const existingErrorStates = new Map();
  if (store.state.displayedData) {
    store.state.displayedData.forEach((item) => {
      if (item.channels) {
        item.channels.forEach((channel) => {
          const key = `${channel.channel_name}_${channel.shot_number}`;
          existingErrorStates.set(key, {
            errors: channel.errors.map((e) => ({
              error_name: e.error_name,
              color: e.color,
            })),
            displayedErrors: channel.displayedErrors.map((e) => e.error_name),
            showAllErrors: channel.showAllErrors,
          });
        });
      }
    });
  }

  rawData.forEach((item) => {
    const channelType = item.channel_type;
    const channelName = item.channel_name;
    const shotNumber = item.shot_number;
    const errorNames =
      item.error_name && item.error_name.length > 0
        ? item.error_name
        : ["NO ERROR"];

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
        // 添加状态相关字段
        status: item.status,
        status_message: item.status_message,
      };
      channelTypeEntry.channels.push(channelEntry);
    }

    // 获取之前的错误状态
    const existingErrorState = existingErrorStates.get(channelKey);

    // 处理错误
    channelEntry.errors = [];
    errorNames.forEach((errorName) => {
      // 查找之前相同错误名称的错误对象
      let errorColor = "rgba(220, 20, 60, 0.3)";
      if (errorName === "NO ERROR") {
        errorColor = "rgba(0, 0, 0, 0)";
      } else if (existingErrorState) {
        const existingError = existingErrorState.errors.find(
          (e) => e.error_name === errorName
        );
        if (existingError) {
          errorColor = existingError.color;
        }
      }

      const error = {
        error_name: errorName,
        color: errorColor,
      };
      channelEntry.errors.push(error);
    });

    // 恢复之前的错误显示状态
    if (existingErrorState) {
      channelEntry.showAllErrors = existingErrorState.showAllErrors;

      if (channelEntry.showAllErrors) {
        channelEntry.displayedErrors = channelEntry.errors;
      } else {
        // 尝试恢复之前显示的错误
        const matchingErrors = channelEntry.errors.filter((error) =>
          existingErrorState.displayedErrors.includes(error.error_name)
        );

        if (matchingErrors.length > 0) {
          channelEntry.displayedErrors = matchingErrors;
        } else {
          channelEntry.displayedErrors = channelEntry.errors.slice(0, 1);
        }
      }
    } else {
      // 默认只显示第一个错误
      channelEntry.displayedErrors = channelEntry.errors.slice(0, 1);
    }
  });

  // 更新通道类型的选中状态
  groupedData.forEach((item) => {
    if (item.channels.length > 0) {
      // 只考虑非空数据的通道
      const validChannels = item.channels.filter(channel => channel.status !== 'empty_data');
      item.checked = validChannels.length > 0 && validChannels.every((channel) => channel.checked);
      // 检查是否所有通道都是空数据
      item.allChannelsEmpty = item.channels.every(channel => channel.status === 'empty_data');
    }
  });

  return groupedData;
}

export default store;
