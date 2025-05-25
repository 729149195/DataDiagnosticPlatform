<template>
  <div class="all-layout">
    <el-container>
      <AppHeader @button-change="selectButton" :initial-button="selectedButton" />
      <el-container>
        <el-aside class="aside">
          <div class="aside-content">
            <el-card class="filtandsearch" shadow="never">
              <span style="display: flex; margin-bottom: 5px; justify-content: space-between;">
                <span class="title">过滤器<el-tooltip placement="right" effect="light">
                    <template #content>
                      <div style="max-width: 320px">
                        <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">视图说明</div>
                        <div style="margin-bottom:8px;">用于筛选和加载实验数据，支持多条件组合查询。</div>
                        <hr style="margin:8px 0;">
                        <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
                        <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                          <li>数据库：制定要查询的数据库，确定待查炮号范围</li>
                          <li>炮号：输入要查询的具体炮号，支持打印机输入格式如1-5,7,9-12，输入完成后直接回车或点击确认炮号按钮即可自动返回通道名和异常名</li>
                          <li>通道名：选择要显示的通道，可多选</li>
                          <li>异常名：根据异常类型筛选数据，可多选</li>
                          点击过滤，可以在下方的可视化配置中显示过滤结果
                        </ul>
                        <hr style="margin:8px 0;">
                        <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">注意事项</div>
                        <ul style="margin:0 0 0 18px;padding:0;list-style:disc;">
                          <li>各个条件之间存在相关影响，比如选择了通道名，异常名会根据通道名进行自动筛选</li>
                          <li>如果想要取消选择，可以点击条件旁边的叉号</li>
                          <li>通道名和异常名选项可以为空</li>
                        </ul>
                      </div>
                    </template>
                    <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
                  </el-tooltip></span>
              </span>
              <Filter />
            </el-card>
            <el-card class="table" shadow="never" v-if="selectedButton === 'anay'">
              <span style="display: flex; align-items: center; margin-bottom: 5px;">
                <span class="title">可视化配置<el-tooltip placement="right" effect="light">
                    <template #content>
                      <div style="max-width: 320px">
                        <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">视图说明</div>
                        <div style="margin-bottom:8px;">管理和配置通道数据的显示。</div>
                        <hr style="margin:8px 0;">
                        <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
                        <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                          <li>通道类别：按类别组织通道，可一键全选/取消选择</li>
                          <li>通道名：选择要显示的具体通道</li>
                          <li>炮号：在矩形框中显示的数值为各个通道的炮号信息</li>
                          <li>异常类别：展示通道中的异常标记</li>
                          <li>颜色配置：点击圆形色块可自定义通道颜色</li>
                          <li>展开全部异常类别：默认只显示第一个异常类别，点击后可以展开全部异常类别</li>
                        </ul>
                      </div>
                    </template>
                    <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
                  </el-tooltip></span>
                <!-- <el-switch class="color_table_switch" v-model="color_table_value" style="--el-switch-on-color: #409EFF; --el-switch-off-color: #409EFF" active-text="通道颜色" inactive-text="异常颜色" /> -->
              </span>
              <div class="scrollbar-container">
                <el-scrollbar :always="false">
                  <div v-if="color_table_value === true">
                    <ChannelType />
                  </div>
                  <div v-if="color_table_value === false">
                    <ExceptionType />
                  </div>
                </el-scrollbar>
              </div>
            </el-card>
            <el-card class="table" shadow="never" v-if="selectedButton === 'channel'">
              <span style="display: flex;margin-bottom: 5px; justify-content: space-between;">
                <span class="title">可视化配置<el-tooltip placement="right" effect="light">
                    <template #content>
                      <div style="max-width: 320px">
                        <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">视图说明</div>
                        <div style="margin-bottom:8px;">管理和配置通道数据的显示。</div>
                        <hr style="margin:8px 0;">
                        <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
                        <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                          <li>通道类别：按类别组织通道，可一键全选/取消选择</li>
                          <li>通道名：选择要显示的具体通道</li>
                          <li>炮号：在矩形框中显示的数值为各个通道的炮号信息</li>
                          <li>异常类别：展示通道中的异常标记</li>
                          <li>颜色配置：点击圆形色块可自定义通道颜色</li>
                          <li>展开全部异常类别：默认只显示第一个异常类别，点击后可以展开全部异常类别</li>
                        </ul>
                        <hr style="margin:8px 0;">
                        <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">注意事项</div>
                        <ul style="margin:0 0 0 18px;padding:0;list-style:disc;">
                          <li>该模块下不支持改变通道颜色</li>
                        </ul>
                      </div>
                    </template>
                    <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
                  </el-tooltip></span>
              </span>
              <div class="scrollbar-container">
                <el-scrollbar :always="false">
                  <div>
                    <ChannelTypeP />
                  </div>
                </el-scrollbar>
              </div>
            </el-card>
          </div>
        </el-aside>
        <el-container>
          <!-- KeepAlive wraps the single el-main -->
          <keep-alive>
            <el-main :class="mainClass">
              <!-- Analysis/Labeling View ('anay') content -->
              <template v-if="selectedButton === 'anay'">
                <el-card class="data_exploration" shadow="never">
                  <span style="display: flex; align-items: center; justify-content: space-between; ">
                    <span class="title">实验数据探索<el-tooltip placement="right" effect="light">
                        <template #content>
                          <div style="max-width: 320px">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">视图说明</div>
                            <div style="margin-bottom:8px;">用于交互式查看、分析、标注以及导出实验数据曲线图。</div>
                            <hr style="margin:8px 0;">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
                            <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                              <li>显示/隐藏异常：控制异常区域的可见性</li>
                              <li>采样频率：调整数据采样频率，影响显示精度</li>
                              <li>框选标注/编辑：在图表上框选区域进行标注异常</li>
                              <li>单通道多行/多通道单行：切换数据显示模式</li>
                              <li>修改颜色：点击圆形色块可自定义通道颜色</li>
                              <li>导出：支持通过自定义选项灵活导出数据为图片或原始数据文件</li>
                              <li>局部缩放：对单个通道可以框选区域进行矩形区域放大查看，双击空白处复原</li>
                              <li>总览条：选框所有曲线显示的时间范围，双击复原</li>
                            </ul>
                            <hr style="margin:8px 0;">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">注意事项</div>
                            <ul style="margin:0 0 0 18px;padding:0;list-style:disc;">
                              <li>若弹出加载通道 XXXX 数据失败的报错提示一般由数据库中没有该通道数据导致</li>
                              <li>同时显示多条通道时，建议不要将采样频率调得太高，否则影响性能</li>
                            </ul>
                          </div>
                        </template>
                        <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
                      </el-tooltip></span>
                    <div class="control-panel">

                      <!-- 是否显示异常区域的按钮 -->
                      <div class="control-item">
                        <el-tooltip :content="showAnomaly ? '点击隐藏异常区域' : '点击显示异常区域'" placement="top">
                          <el-button circle :type="showAnomaly ? 'primary' : 'info'" @click="updateShowAnomaly(!showAnomaly)">
                            <el-icon>
                              <component :is="showAnomaly ? 'View' : 'Hide'" />
                            </el-icon>
                          </el-button>
                        </el-tooltip>
                      </div>

                      <div class="control-item">
                        <span class="control-label">采样频率</span>
                        <el-input-number v-model="sampling" :precision="2" :step="0.1" :min="0.1" :max="1000" @change="updateSampling" />
                        <span class="control-unit">KHz</span>
                      </div>

                      <div class="control-item">
                        <el-button-group>
                          <el-button :type="boxSelect ? 'primary' : 'default'" :plain="!boxSelect" @click="updateBoxSelect(true)" style="font-size: 0.9em;">
                            框选标注/编辑
                          </el-button>
                          <el-button :type="!boxSelect ? 'primary' : 'default'" :plain="boxSelect" @click="updateBoxSelect(false)" style="font-size: 0.9em;">
                            局部缩放
                          </el-button>
                        </el-button-group>
                      </div>

                      <div class="control-item">
                        <el-button-group>
                          <el-button type="primary" :plain="!SingleChannelMultiRow_channel_number" @click="toggleChannelDisplayMode(true)" style="font-size: 0.9em;">
                            单通道多行
                          </el-button>
                          <el-button type="primary" :plain="SingleChannelMultiRow_channel_number" @click="toggleChannelDisplayMode(false)" style="font-size: 0.9em;">
                            多通道单行
                          </el-button>
                        </el-button-group>
                      </div>

                      <div class="control-item">
                        <el-dropdown trigger="click" @command="handleExportCommand">
                          <el-button type="primary" class="menu-button" title="更多操作">
                            导出
                            <el-icon>
                              <Download />
                            </el-icon>
                          </el-button>
                          <template #dropdown>
                            <el-dropdown-menu>
                              <el-dropdown-item command="exportSvg">导出图片</el-dropdown-item>
                              <el-dropdown-item command="exportData">导出数据</el-dropdown-item>
                            </el-dropdown-menu>
                          </template>
                        </el-dropdown>
                      </div>
                    </div>
                  </span>
                  <div style="height: 100%; position: relative; display: flex; flex-direction: column;">
                    <el-scrollbar :height="chartAreaHeight" :always="false">
                      <template v-if="selectedChannels.length === 0">
                        <div :style="{ height: chartAreaHeight, display: 'flex', alignItems: 'center', justifyContent: 'center' }">
                          <el-empty description="请选择通道" />
                        </div>
                      </template>
                      <keep-alive v-else>
                        <SingleChannelMultiRow v-if="SingleChannelMultiRow_channel_number === true" />
                        <MultiChannelSingleRow v-else ref="MultiChannelRef" :containerRef="chartAreaRef" :height="chartAreaHeight" />
                      </keep-alive>
                    </el-scrollbar>
                    <OverviewBrush ref="overviewBrushRef" />
                  </div>
                </el-card>

                <div class="arc-toggle-container">
                  <div class="arc-toggle" @click="toggleCollapse">
                    <el-icon class="arc-toggle-icon">
                      <component :is="isSecondSectionCollapsed ? 'ArrowUp' : 'ArrowDown'" />
                    </el-icon>
                  </div>
                </div>
                <div class="two" v-show="!isSecondSectionCollapsed" v-if="selectedButton === 'anay'">
                  <el-card class="two_left" shadow="never">
                    <Sketch :key="selectedButton" />
                  </el-card>
                  <el-card class="two_right" shadow="never">
                    <HeatMap ref="heatMapRef" />
                  </el-card>
                </div>
              </template>

              <!-- Channel Analysis View ('channel') content -->
              <template v-else-if="selectedButton === 'channel'">
                <el-card class="operator">
                  <span style="display: flex;">
                    <span class="title">运算符列表<el-tooltip placement="top" effect="light">
                        <template #content>
                          <div style="max-width: 320px">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">视图说明</div>
                            <div style="margin-bottom:8px;">可用的运算符列表，包括算法、逻辑运算符、导入函数等</div>
                            <hr style="margin:8px 0;">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
                            <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                              <li>点击对应的运算类别，会展开对应的运算符，双击空白处收起</li>
                              <li>点击运算符添加到通道分析公式区域中的鼠标位置</li>
                              <li>算法导入按钮可以通过导入运算函数和诊断函数的 python 或 matlab 文件将算法加入可用列表</li>
                            </ul>
                          </div>
                        </template>
                        <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
                      </el-tooltip></span>
                    <ChannelOperator />
                  </span>
                </el-card>
                <div class="two">
                  <el-card class="two_left" shadow="never">
                    <span style="display: flex; justify-content: space-between;">
                      <span class="title">待选择通道<el-tooltip placement="right" effect="light">
                          <template #content>
                            <div style="max-width: 320px">
                              <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">控件说明</div>
                              <div style="margin-bottom:8px;">此处列出所有可用的数据通道。单击选择需要分析的通道可以将其添加到通道分析公式区域中的鼠标位置</div>
                              <hr style="margin:8px 0;">
                              <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
                              <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                                <li>选择通道，单击添加到公式</li>
                                <li>可统一设置采样频率</li>
                              </ul>
                            </div>
                          </template>
                          <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
                        </el-tooltip></span>
                      <span>统一频率 <el-input-number v-model="unit_sampling" :precision="1" :step="10" :max="200" />
                        KHz</span>
                    </span>
                    <div style="display: flex; justify-content: center; align-items: center;">
                      <ChannelCards />
                    </div>
                  </el-card>
                  <el-card class="two_right" shadow="never">
                    <span class="title">通道分析公式<el-tooltip placement="right" effect="light">
                        <template #content>
                          <div style="max-width: 320px">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">控件说明</div>
                            <div style="margin-bottom:8px;">在此构建您的分析表达式</div>
                            <hr style="margin:8px 0;">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
                            <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                              <li>可以通过点击运算符和待选择通道，或直接输入来创建通道分析公式</li>
                              <li>点击计算按钮即可对公式进行计算</li>
                            </ul>
                          </div>
                        </template>
                        <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
                      </el-tooltip></span>
                    <ChannelStr />
                  </el-card>
                </div>
                <el-card class="data_exploration" shadow="never">
                  <span style="display: flex; justify-content: space-between;">
                    <span class="title">通道分析结果<el-tooltip placement="right" effect="light">
                        <template #content>
                          <div style="max-width: 320px">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">控件说明</div>
                            <div style="margin-bottom:8px;">显示公式分析的结果。</div>
                            <hr style="margin:8px 0;">
                            <div style="font-weight:bold;font-size:15px;margin-bottom:4px;">交互功能</div>
                            <ul style="margin:0 0 8px 18px;padding:0;list-style:disc;">
                              <li>结果以图表展示，可用鼠标框选局部放大，双击复原</li>
                              <li>可以通过导出按钮导出结果数据或者svg、jpg、png格式的图表</li>
                            </ul>
                          </div>
                        </template>
                        <el-icon style="color: #409EFF"><InfoFilled /></el-icon>
                      </el-tooltip></span>
                    <span>
                      <el-dropdown trigger="click" @command="handleResultExportCommand">
                        <el-button type="primary" title="导出数据">
                          导出<el-icon class="el-icon--right">
                            <Upload />
                          </el-icon>
                        </el-button>
                        <template #dropdown>
                          <el-dropdown-menu>
                            <el-dropdown-item command="exportSvg">导出计算图片</el-dropdown-item>
                            <el-dropdown-item command="exportData">导出计算数据</el-dropdown-item>
                          </el-dropdown-menu>
                        </template>
                      </el-dropdown>
                      <!-- <el-button type="primary" :icon="FolderChecked">另存为新通道</el-button> -->
                    </span>
                  </span>
                  <div style="display: flex; justify-content: center; align-items: center;">
                    <div style="width: 100%">
                      <ChannelCalculationResults ref="resultRef" />
                    </div>
                  </div>
                </el-card>
              </template>

              <!-- Add v-else for other potential views if they exist -->
            </el-main>
          </keep-alive>
        </el-container>
      </el-container>
    </el-container>

    <!-- 添加导出配置对话框 -->
    <el-dialog v-model="showExportDialog" title="导出通道数据配置" width="900px" class="export-dialog">
      <div class="dialog-layout" style="flex-direction: column;">
        <!-- 上方布局：通道选择和参数设置 -->
        <div style="display: flex; gap: 20px;">
          <!-- 左侧：通道选择 -->
          <div class="left-section">
            <div class="section-title">选择通道</div>
            <div class="channel-selection">
              <div class="channel-header">
                <el-checkbox v-model="allChannelsSelected" @change="toggleAllChannels">全选</el-checkbox>
                <el-button size="small" @click="resetChannelNames" :icon="Refresh" :link="true">重置名称</el-button>
              </div>
              <el-scrollbar>
                <div v-for="(channel, index) in selectedChannels" :key="`${channel.channel_name}_${channel.shot_number}`" class="channel-item">
                  <el-checkbox v-model="exportConfig.selectedChannelIndices[index]"></el-checkbox>
                  <span class="channel-name">{{ channel.channel_name }}_{{ channel.shot_number }}</span>
                  <div class="filename-input-container">
                    <el-input v-model="exportConfig.channelRenames[index]" placeholder="自定义文件名" size="small"></el-input>
                    <span class="file-extension">.json</span>
                  </div>
                </div>
              </el-scrollbar>
            </div>
          </div>

          <!-- 右侧：参数配置 -->
          <div class="right-section">
            <div class="section-title">导出参数</div>
            <div class="param-form">
              <el-form :model="exportConfig" label-width="auto">
                <!-- 频率设置 -->
                <el-form-item label="数据频率" class="frequency-options">
                  <div class="frequency-radio-container">
                    <div class="radio-option">
                      <el-radio v-model="exportConfig.frequencyMode" label="current">
                        使用当前采样频率 ({{ sampling }}KHz)
                      </el-radio>
                    </div>

                    <div class="radio-option">
                      <div class="radio-with-tag">
                        <el-radio v-model="exportConfig.frequencyMode" label="original">
                          使用原始频率
                        </el-radio>
                        <el-tag type="warning" size="small">需要更多耗时</el-tag>
                      </div>
                    </div>

                    <div class="radio-option">
                      <div class="radio-with-tag">
                        <el-radio v-model="exportConfig.frequencyMode" label="custom">
                          使用自定义频率
                        </el-radio>
                        <el-tag type="warning" size="small">需要更多耗时</el-tag>
                      </div>

                      <div class="custom-frequency-control">
                        <el-input-number v-model="exportConfig.customFrequency" :precision="2" :step="0.5" :min="0.1" :max="1000" size="small" :disabled="exportConfig.frequencyMode !== 'custom'" />
                        <span class="unit-label">KHz</span>
                      </div>
                    </div>
                  </div>
                </el-form-item>
              </el-form>
            </div>
          </div>
        </div>

        <!-- 进度条部分，单独放在下面 -->
        <div class="progress-container" style="width: 100%;" v-if="exportProgress.isExporting">
          <!-- 进度条 -->
          <div class="export-progress">
            <p>
              <template v-if="exportProgress.stage === 'downloading'">
                正在下载数据: {{ exportProgress.currentChannel }} ({{ exportProgress.current }}/{{ exportProgress.total }})
              </template>
              <template v-else>
                正在打包数据: {{ exportProgress.currentChannel }} ({{ exportProgress.current }}/{{ exportProgress.total }})
              </template>
            </p>
            <el-progress :percentage="exportProgress.percentage" :format="percentageFormat"></el-progress>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showExportDialog = false">取消</el-button>
          <el-button type="primary" @click="startExportData" :loading="exportProgress.isExporting">
            导出
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 添加导出SVG配置对话框 -->
    <el-dialog v-model="showSvgExportDialog" title="导出通道图片配置" width="1000px" class="export-dialog">
      <div class="dialog-layout" style="flex-direction: column;">
        <!-- 上方布局：通道选择和参数设置 -->
        <div style="display: flex; gap: 20px;">
          <!-- 左侧：通道选择 -->
          <div class="left-section">
            <div class="section-title">选择通道</div>
            <div class="channel-selection">
              <div class="channel-header">
                <el-checkbox v-model="allSvgChannelsSelected" @change="toggleAllSvgChannels">全选</el-checkbox>
                <el-button size="small" @click="resetSvgChannelNames" :icon="Refresh" :link="true">重置名称</el-button>
              </div>
              <el-scrollbar>
                <div v-for="(channel, index) in selectedChannels" :key="`${channel.channel_name}_${channel.shot_number}`" class="channel-item">
                  <el-checkbox v-model="svgExportConfig.selectedChannelIndices[index]"></el-checkbox>
                  <span class="channel-name">{{ channel.channel_name }}_{{ channel.shot_number }}</span>
                  <div class="filename-input-container">
                    <el-input v-model="svgExportConfig.channelRenames[index]" placeholder="自定义文件名" size="small"></el-input>
                    <span v-if="svgExportConfig.exportFormat === 'png'" class="file-extension">.png</span>
                    <span v-if="svgExportConfig.exportFormat === 'jpg'" class="file-extension">.jpg</span>
                    <span v-if="svgExportConfig.exportFormat === 'svg'" class="file-extension">.svg</span>
                    <span v-if="!svgExportConfig.exportFormat" class="file-extension">请选择格式</span>
                  </div>
                </div>
              </el-scrollbar>
            </div>
          </div>

          <!-- 右侧：参数配置 -->
          <div class="right-section">
            <div class="section-title">导出参数</div>
            <div class="param-form">
              <el-form :model="svgExportConfig" label-width="auto">
                <!-- 导出模式选择 -->
                <el-form-item label="导出模式" class="mode-selection">
                  <div class="mode-radio-container">
                    <div class="radio-option">
                      <el-radio v-model="svgExportConfig.exportMode" label="singleChannel">
                        单通道多图（每个通道单独导出）
                      </el-radio>
                    </div>
                    <div class="radio-option">
                      <el-radio v-model="svgExportConfig.exportMode" label="multiChannel">
                        多通道单图（所有通道合并导出）
                      </el-radio>
                      <el-tag type="warning" size="small">原始 Y 数值，非归一化</el-tag>
                    </div>
                  </div>
                </el-form-item>

                <!-- 导出格式选择 -->
                <el-form-item label="导出格式" class="format-selection">
                  <div class="format-radio-container">
                    <el-radio v-model="svgExportConfig.exportFormat" label="png">PNG</el-radio>
                    <el-radio v-model="svgExportConfig.exportFormat" label="jpg">JPG</el-radio>
                    <el-radio v-model="svgExportConfig.exportFormat" label="svg">SVG</el-radio>
                  </div>
                </el-form-item>

                <!-- 图片尺寸设置 -->
                <el-form-item label="图片尺寸" class="size-controls-container">
                  <div class="size-controls" style="width: 100%;">
                    <div class="size-input-group" style="width: 48%;">
                      <span class="size-label">宽度:</span>
                      <el-input-number v-model="svgExportConfig.width" :min="300" :max="3000" :controls="false" size="small" />
                      <span class="size-unit">px</span>
                    </div>

                    <div class="size-input-group" style="width: 48%;">
                      <span class="size-label">高　　　度:</span>
                      <el-input-number v-model="svgExportConfig.height" :min="200" :max="2000" :controls="false" size="small" />
                      <span class="size-unit">px</span>
                    </div>
                  </div>
                </el-form-item>

                <!-- 字体大小设置 -->
                <el-form-item label="字体大小" class="font-size-container">
                  <div style="width: 100%;">
                    <div style="display: flex; justify-content: space-between; width: 100%; margin-bottom: 8px;">
                      <div style="display: flex; align-items: center; width: 48%;">
                        <span style="margin-right: 5px; text-align: left; font-size: 14px; white-space: nowrap;">标题:</span>
                        <el-input-number v-model="svgExportConfig.titleFontSize" :min="12" :max="36" :step="1" :controls="false" size="small" style="width: 70px;" />
                        <span style="margin-left: 5px; font-size: 14px;">px</span>
                      </div>
                      <div style="display: flex; align-items: center; width: 48%;">
                        <span style="margin-right: 5px; text-align: left; font-size: 14px; white-space: nowrap;">坐标轴标题:</span>
                        <el-input-number v-model="svgExportConfig.axisTitleFontSize" :min="10" :max="24" :step="1" :controls="false" size="small" style="width: 70px;" />
                        <span style="margin-left: 5px; font-size: 14px;">px</span>
                      </div>
                    </div>
                    <div style="display: flex; justify-content: space-between; width: 100%;">
                      <div style="display: flex; align-items: center; width: 48%;">
                        <span style="margin-right: 5px; text-align: left; font-size: 14px; white-space: nowrap;">图例:</span>
                        <el-input-number v-model="svgExportConfig.legendFontSize" :min="8" :max="20" :step="1" :controls="false" size="small" style="width: 70px;" />
                        <span style="margin-left: 5px; font-size: 14px;">px</span>
                      </div>
                      <div style="display: flex; align-items: center; width: 48%;">
                        <span style="margin-right: 5px; text-align: left; font-size: 14px; white-space: nowrap;">坐标轴标签:</span>
                        <el-input-number v-model="svgExportConfig.axisLabelFontSize" :min="8" :max="20" :step="1" :controls="false" size="small" style="width: 70px;" />
                        <span style="margin-left: 5px; font-size: 14px;">px</span>
                      </div>
                    </div>
                  </div>
                </el-form-item>

                <!-- 频率设置 -->
                <el-form-item label="数据频率" class="frequency-options">
                  <div class="frequency-radio-container">
                    <div class="radio-option">
                      <el-radio v-model="svgExportConfig.frequencyMode" label="current">
                        使用当前采样频率 ({{ sampling }}KHz)
                      </el-radio>
                    </div>

                    <div class="radio-option">
                      <div class="radio-with-tag">
                        <el-radio v-model="svgExportConfig.frequencyMode" label="original">
                          使用原始频率
                        </el-radio>
                        <el-tag type="warning" size="small">需要更多耗时</el-tag>
                      </div>
                    </div>

                    <div class="radio-option">
                      <div class="radio-with-tag">
                        <el-radio v-model="svgExportConfig.frequencyMode" label="custom">
                          使用自定义频率
                        </el-radio>
                        <el-tag type="warning" size="small">需要更多耗时</el-tag>
                      </div>

                      <div class="custom-frequency-control">
                        <el-input-number v-model="svgExportConfig.customFrequency" :precision="2" :step="0.5" :min="0.1" :max="1000" size="small" :disabled="svgExportConfig.frequencyMode !== 'custom'" />
                        <span class="unit-label">KHz</span>
                      </div>
                    </div>
                  </div>
                </el-form-item>
              </el-form>
            </div>
          </div>
        </div>

        <!-- 下方：进度条区域，仅在需要时显示 -->
        <div v-if="svgExportProgress.isExporting" style="width: 100%; margin-top: 2px;">
          <div class="export-progress" style="width: 100%;">
            <p>
              <template v-if="svgExportProgress.stage === 'downloading'">
                正在下载数据: {{ svgExportProgress.currentChannel }} ({{ svgExportProgress.current }}/{{ svgExportProgress.total }})
              </template>
              <template v-else-if="svgExportProgress.stage === 'rendering'">
                正在渲染图表: {{ svgExportProgress.currentChannel }} ({{ svgExportProgress.current }}/{{ svgExportProgress.total }})
              </template>
              <template v-else>
                正在打包图片: {{ svgExportProgress.currentChannel }} ({{ svgExportProgress.current }}/{{ svgExportProgress.total }})
              </template>
            </p>
            <el-progress :percentage="svgExportProgress.percentage" :format="percentageFormat"></el-progress>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showSvgExportDialog = false">取消</el-button>
          <el-button type="primary" @click="startExportSvg" :loading="svgExportProgress.isExporting">
            导出
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 添加导出结果图表配置对话框 -->
    <el-dialog v-model="showResultSvgExportDialog" title="导出计算结果图表" width="600px" class="export-dialog">
      <div class="dialog-layout" style="display: flex; flex-direction: column;">
        <!-- 参数配置部分 -->
        <div class="param-form" style="width: 100%;">
          <el-form :model="resultSvgExportConfig" label-width="auto">
            <!-- 图片尺寸设置 -->
            <el-form-item label="图片尺寸" class="size-controls-container">
              <div class="size-controls" style="display: flex; justify-content: space-between; width: 100%;">
                <div class="size-input-group" style="margin-bottom: 10px; display: flex; align-items: center; width: 48%;">
                  <span class="size-label" style=" text-align: left;">宽度:</span>
                  <el-input-number v-model="resultSvgExportConfig.width" :min="300" :max="3000" :controls="false" size="small" />
                  <span class="size-unit" style="margin-left: 5px;">px</span>
                </div>

                <div class="size-input-group" style="display: flex; align-items: center; width: 48%;">
                  <span class="size-label" style=" text-align: left;">高　　　度:</span>
                  <el-input-number v-model="resultSvgExportConfig.height" :min="200" :max="2000" :controls="false" size="small" />
                  <span class="size-unit" style="margin-left: 5px;">px</span>
                </div>
              </div>
            </el-form-item>

            <!-- 字体大小设置 -->
            <el-form-item label="字体大小" class="font-size-container">
              <div style="width: 100%;">
                <div style="display: flex; justify-content: space-between; width: 100%; margin-bottom: 8px;">
                  <div style="display: flex; align-items: center; width: 48%;">
                    <span style="margin-right: 5px; text-align: left; font-size: 14px; white-space: nowrap;">标题:</span>
                    <el-input-number v-model="resultSvgExportConfig.titleFontSize" :min="12" :max="36" :step="1" :controls="false" size="small" style="width: 70px;" />
                    <span style="margin-left: 5px; font-size: 14px;">px</span>
                  </div>
                  <div style="display: flex; align-items: center; width: 48%;">
                    <span style="margin-right: 5px; text-align: left; font-size: 14px; white-space: nowrap;">坐标轴标题:</span>
                    <el-input-number v-model="resultSvgExportConfig.axisTitleFontSize" :min="10" :max="24" :step="1" :controls="false" size="small" style="width: 70px;" />
                    <span style="margin-left: 5px; font-size: 14px;">px</span>
                  </div>
                </div>
                <div style="display: flex; justify-content: space-between; width: 100%;">
                  <div style="display: flex; align-items: center; width: 48%;">
                    <span style="margin-right: 5px; text-align: left; font-size: 14px; white-space: nowrap;">图例:</span>
                    <el-input-number v-model="resultSvgExportConfig.legendFontSize" :min="8" :max="20" :step="1" :controls="false" size="small" style="width: 70px;" />
                    <span style="margin-left: 5px; font-size: 14px;">px</span>
                  </div>
                  <div style="display: flex; align-items: center; width: 48%;">
                    <span style="margin-right: 5px; text-align: left; font-size: 14px; white-space: nowrap;">坐标轴标签:</span>
                    <el-input-number v-model="resultSvgExportConfig.axisLabelFontSize" :min="8" :max="20" :step="1" :controls="false" size="small" style="width: 70px;" />
                    <span style="margin-left: 5px; font-size: 14px;">px</span>
                  </div>
                </div>
              </div>
            </el-form-item>

            <!-- 导出格式选择 -->
            <el-form-item label="导出格式" class="format-selection">
              <div class="format-radio-container">
                <el-radio v-model="resultSvgExportConfig.exportFormat" label="png">PNG</el-radio>
                <el-radio v-model="resultSvgExportConfig.exportFormat" label="jpg">JPG</el-radio>
                <el-radio v-model="resultSvgExportConfig.exportFormat" label="svg">SVG</el-radio>
              </div>
            </el-form-item>

            <!-- 文件名设置 -->
            <el-form-item label="文 件 名" class="size-controls-container">
              <div class="filename-input-container" style="width: 100%; position: relative;">
                <el-input v-model="resultSvgExportConfig.fileName" placeholder="自定义文件名" style="width: 100%;" />
                <span v-if="resultSvgExportConfig.exportFormat === 'png'" class="file-extension" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%);">.png</span>
                <span v-if="resultSvgExportConfig.exportFormat === 'jpg'" class="file-extension" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%);">.jpg</span>
                <span v-if="resultSvgExportConfig.exportFormat === 'svg'" class="file-extension" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%);">.svg</span>
                <span v-if="!resultSvgExportConfig.exportFormat" class="file-extension" style="position: absolute; right: 10px; top: 50%; transform: translateY(-50%);">请选择格式</span>
              </div>
            </el-form-item>


          </el-form>
        </div>

        <!-- 进度条，仅在需要时显示 -->
        <div v-if="resultSvgExportProgress.isExporting" style="width: 100%; margin-top: 2px;">
          <div class="export-progress" style="width: 100%;">
            <p>正在导出图表...</p>
            <el-progress :percentage="resultSvgExportProgress.percentage" :format="percentageFormat"></el-progress>
          </div>
        </div>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="showResultSvgExportDialog = false">取消</el-button>
          <el-button type="primary" @click="startExportResultSvg" :loading="resultSvgExportProgress.isExporting">
            导出
          </el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, reactive, onBeforeUnmount, nextTick } from 'vue';
import { useStore } from 'vuex';
import { Upload, Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import Highcharts from 'highcharts';
import 'highcharts/modules/boost';
import 'highcharts/modules/exporting';
import JSZip from 'jszip'; // 导入JSZip库
import dayjs from "dayjs";
import isBetween from "dayjs/plugin/isBetween";
dayjs.extend(isBetween);
// 导入AppHeader组件
import AppHeader from '@/components/AppHeader.vue';
// 颜色配置及通道选取组件
import ChannelType from '@/components/Channel-Type.vue';
import ExceptionType from '@/components/Exception-Type.vue';
import ChannelTypeP from '@/components/Channel-Type-P.vue';
import Filter from './Filter/Filter.vue';

import MultiChannelSingleRow from '@/views/AnomalyLabelView/DataExploration/MultiChannelSingleRow.vue';
import SingleChannelMultiRow from '@/views/AnomalyLabelView/DataExploration/SingleChannelMultiRow.vue';

import HeatMap from '@/views/AnomalyLabelView/LabelResult/HeatMapResult.vue';

import Sketch from '@/views/AnomalyLabelView/Sketch/Sketch.vue';

import ChannelCards from '@/views/ChannelAnalysisView/ChannelList/ChannelCards.vue';
import ChannelOperator from '../ChannelAnalysisView/ChannelOperator/ChannelOperator.vue';
import ChannelStr from '../ChannelAnalysisView/ChannelStr/ChannelStr.vue';
import ChannelCalculationResults from '@/views/ChannelAnalysisView/ChannelCalculation/ChannelCalculationResults.vue';

import OverviewBrush from '@/components/OverviewBrush.vue';

import { ElDialog, ElForm, ElFormItem, ElCheckbox, ElRadio, ElTag, ElScrollbar, ElProgress } from 'element-plus'

// 设置Highcharts全局配置
Highcharts.setOptions({
  accessibility: {
    enabled: false // 禁用无障碍功能，避免相关错误
  }
});

// 计算属性，用于动态设置 el-main 的 class
const mainClass = computed(() => {
  return selectedButton.value === 'anay' ? 'test_main' : (selectedButton.value === 'channel' ? 'channel_main' : '');
});

let chartAreaResizeObserver = null

const store = useStore()
const sampling = ref(5)
const isSecondSectionCollapsed = ref(true) // 默认为折叠状态
const showAnomaly = ref(true) // 是否显示异常区域，默认显示
const chartObserver = ref(null) // 添加MutationObserver引用

const color_table_value = ref(true)
const SingleChannelMultiRow_channel_number = ref(true)
const unit_sampling = ref(10)
const selectedButton = ref('anay');

// 添加监听函数，当unit_sampling改变时更新store
watch(unit_sampling, (newValue) => {
  store.dispatch('updateUnitSampling', newValue);
});

const MultiChannelRef = ref(null)
const resultRef = ref(null)
const heatMapRef = ref(null)
const selectedChannels = computed(() => store.state.selectedChannels);

const boxSelect = computed({
  get: () => {
    if (store.state.authority === '0') {
      return false;
    }
    return store.state.isBoxSelect;
  },
  set: (value) => {
    if (store.state.authority === '0' && value === true) {
      ElMessage({
        message: '您当前为查看者权限，无法进行标注操作',
        type: 'warning'
      });
      return;
    }
    store.dispatch('updateIsBoxSelect', value);
  }
});

// 监听权限变化，自动更新isBoxSelect状态
watch(() => store.state.authority, (newValue) => {
  if (newValue === '0') {
    store.dispatch('updateIsBoxSelect', false);
  }
});

// 确保在组件挂载时设置正确的初始状态
onMounted(() => {
  // 每次挂载时都强制切换到实验数据分析模块
  selectedButton.value = 'anay';
  localStorage.setItem('selectedButton', 'anay');

  // 恢复通道显示模式
  const savedChannelMode = localStorage.getItem('channelDisplayMode');
  if (savedChannelMode !== null) {
    SingleChannelMultiRow_channel_number.value = savedChannelMode === 'true';
  }

  // 恢复异常区域显示状态
  const savedShowAnomaly = localStorage.getItem('showAnomaly');
  if (savedShowAnomaly !== null) {
    showAnomaly.value = savedShowAnomaly === 'true';
  }

  // 创建并启动MutationObserver，监听图表变化
  setupChartObserver();

  if (chartAreaRef.value) {
    chartAreaResizeObserver = new ResizeObserver(() => {
      updateChartAreaSize()
    })
    chartAreaResizeObserver.observe(chartAreaRef.value)
    // 首次也要手动算一次
    nextTick(() => {
      updateChartAreaSize()
    })
  }
});

// 监听登录状态变化，确保重定向后状态正确恢复
watch(() => store.state.person, (newPerson, oldPerson) => {
  // 当用户重新登录时，强制切换到实验数据分析模块
  if (newPerson && !oldPerson) {
    nextTick(() => {
      selectedButton.value = 'anay';
      localStorage.setItem('selectedButton', 'anay');
    });
  }
  // 当用户登出时，也确保切换到实验数据分析模块
  if (!newPerson && oldPerson) {
    selectedButton.value = 'anay';
    localStorage.setItem('selectedButton', 'anay');
  }
}, { immediate: false });

onBeforeUnmount(() => {
  // 移除强制重置逻辑，保持状态一致性
  if (chartAreaResizeObserver && chartAreaRef.value) {
    chartAreaResizeObserver.unobserve(chartAreaRef.value)
    chartAreaResizeObserver.disconnect()
  }
})

const selectButton = (button) => {
  selectedButton.value = button;
  localStorage.setItem('selectedButton', button);
  
  // 确保状态变化能触发组件重新渲染
  nextTick(() => {
    // 强制更新相关的计算属性
    if (button === 'anay' || button === 'channel') {
      // 触发响应式更新
      console.log(`切换到 ${button} 模式`);
    }
  });
};

// 添加保存通道显示模式的函数
const toggleChannelDisplayMode = (value) => {
  SingleChannelMultiRow_channel_number.value = value;
  localStorage.setItem('channelDisplayMode', value);
};

// 添加更新框选模式的函数
const updateBoxSelect = (value) => {
  if (store.state.authority === '0' && value === true) {
    ElMessage({
      message: '您当前为查看者权限，无法进行标注操作',
      type: 'warning'
    });
    return;
  }
  store.dispatch('updateIsBoxSelect', value);
};

// 修改通用的下载函数以使用传统的文件下载方式
const downloadFile = async (blob, suggestedName, fileType = 'json') => {
  try {
    // 创建一个下载链接
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = suggestedName;

    // 模拟点击链接进行下载
    document.body.appendChild(link);
    link.click();

    // 清理
    setTimeout(() => {
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }, 100);

    // 显示成功提示
    ElMessage({
      message: '文件保存成功',
      type: 'success',
    });
  } catch (err) {
    console.error('保存文件时出错:', err);
    ElMessage({
      message: '保存文件失败，请重试',
      type: 'error',
    });
  }
};

// 添加设置MutationObserver的函数
const setupChartObserver = () => {
  // 如果已经存在观察者，先断开连接
  if (chartObserver.value) {
    chartObserver.value.disconnect();
  }

  // 创建新的MutationObserver
  chartObserver.value = new MutationObserver((mutations) => {
    // 如果图表发生变化，应用当前的显示/隐藏状态到所有异常区域
    applyAnomalyVisibility();
  });

  // 开始观察整个文档，关注子节点的添加
  chartObserver.value.observe(document.body, {
    childList: true,
    subtree: true
  });
};

// 应用异常区域可见性的函数，可以单独调用
const applyAnomalyVisibility = () => {
  const currentVisibility = showAnomaly.value;

  if (SingleChannelMultiRow_channel_number.value) {
    // 单通道多行模式
    const allCharts = document.querySelectorAll('[id^="chart-"]');
    allCharts.forEach(chartElement => {
      const chartInstance = Highcharts.charts.find(c => c && c.renderTo === chartElement);
      if (chartInstance) {
        chartInstance.xAxis[0].plotLinesAndBands.forEach(band => {
          if (band.id && (band.id.startsWith('band-') || band.id.startsWith('error-band-'))) {
            // 不影响现场标注的异常(橙色)
            if (band.id.startsWith('band-') && !band.options.color.includes('255, 0, 0')) {
              return;
            }
            const element = band.svgElem;
            if (element) {
              element.attr({
                fill: currentVisibility ? (band.options.color || 'rgba(255, 0, 0, 0.2)') : 'rgba(0, 0, 0, 0)'
              });
            }
          }
        });
      }
    });
  } else if (MultiChannelRef.value) {
    // 多通道单行模式实现类似逻辑
    const chartInstance = MultiChannelRef.value.chartInstance;
    if (chartInstance) {
      // 实现与单通道多行模式类似的透明度控制
      chartInstance.xAxis[0].plotLinesAndBands.forEach(band => {
        if (band.id && (band.id.startsWith('band-') || band.id.startsWith('error-band-'))) {
          // 不影响现场标注的异常(橙色)
          if (band.id.startsWith('band-') && !band.options.color.includes('255, 0, 0')) {
            return;
          }
          const element = band.svgElem;
          if (element) {
            element.attr({
              fill: currentVisibility ? (band.options.color || 'rgba(255, 0, 0, 0.2)') : 'rgba(0, 0, 0, 0)'
            });
          }
        }
      });
    }
  }
};

const updateShowAnomaly = (value) => {
  showAnomaly.value = value;
  localStorage.setItem('showAnomaly', value.toString());
  // 调用统一的应用函数
  applyAnomalyVisibility();
};

const exportChannelSVG = () => {
  // 检查是否有通道被选中
  if (!selectedChannels.value || selectedChannels.value.length === 0) {
    ElMessage.warning('请先选择至少一个通道')
    return
  }

  // 初始化配置并打开对话框
  initSvgExportConfig()
  showSvgExportDialog.value = true
}

// 导出SVG配置对话框状态
const showSvgExportDialog = ref(false)
const svgExportConfig = reactive({
  selectedChannelIndices: [],
  channelRenames: [],
  frequencyMode: 'current',
  customFrequency: 10.0,
  width: 1200, // 默认宽度，像素
  height: 600,  // 默认高度，像素
  exportMode: 'singleChannel', // 默认为单通道多图模式
  exportFormat: 'png', // 默认导出PNG格式，改为单选
  titleFontSize: 18, // 标题字号，像素
  axisTitleFontSize: 18, // 坐标轴标题字号，像素
  axisLabelFontSize: 16, // 坐标轴标签字号，像素
  legendFontSize: 14 // 图例字号，像素
})

// 导出SVG进度状态
const svgExportProgress = reactive({
  isExporting: false,
  current: 0,
  total: 0,
  percentage: 0,
  currentChannel: '',
  stage: 'rendering' // 'rendering' 或 'packaging'
})

// 全选SVG通道状态
const allSvgChannelsSelected = computed({
  get: () => {
    if (!selectedChannels.value || selectedChannels.value.length === 0) return false
    return svgExportConfig.selectedChannelIndices.every(selected => selected)
  },
  set: (value) => {
    toggleAllSvgChannels(value)
  }
})

// 全选/取消全选SVG通道
const toggleAllSvgChannels = (value) => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    svgExportConfig.selectedChannelIndices = selectedChannels.value.map(() => value)
  }
}

// 重置SVG通道名称
const resetSvgChannelNames = () => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    svgExportConfig.channelRenames = selectedChannels.value.map((channel) =>
      `${channel.channel_name}_${channel.shot_number}_image`
    )
  }
}

// 初始化SVG导出配置
const initSvgExportConfig = () => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    svgExportConfig.selectedChannelIndices = selectedChannels.value.map(() => true)
    svgExportConfig.channelRenames = selectedChannels.value.map((channel) =>
      `${channel.channel_name}_${channel.shot_number}_image`
    )
    svgExportConfig.frequencyMode = 'current'
    svgExportConfig.customFrequency = 10.0

    // 根据当前显示模式设置默认尺寸
    if (SingleChannelMultiRow_channel_number.value) {
      // 单通道多行模式
      svgExportConfig.width = 1200
      svgExportConfig.height = 600
    } else {
      // 多通道单行模式
      svgExportConfig.width = 1600
      svgExportConfig.height = 800
    }

    // 设置默认导出模式为当前显示模式
    svgExportConfig.exportMode = SingleChannelMultiRow_channel_number.value ? 'singleChannel' : 'multiChannel'

    // 设置默认导出格式
    svgExportConfig.exportFormat = 'png'

    // 设置默认字体大小
    svgExportConfig.titleFontSize = 18
    svgExportConfig.axisTitleFontSize = 18
    svgExportConfig.axisLabelFontSize = 16
    svgExportConfig.legendFontSize = 14
  }
}

// 渲染通道为指定格式的图像
const renderChannelImage = async (channel, fileName, width, height, frequencyParams, channelData = null) => {
  try {
    // 使用预先获取的数据或者重新获取
    const data = channelData || await store.dispatch('fetchChannelData', {
      channel,
      ...frequencyParams
    })

    // 创建临时容器来渲染图表
    const container = document.createElement('div')
    container.style.width = `${width}px`
    container.style.height = `${height}px`
    container.style.position = 'absolute'
    container.style.top = '-9999px'
    container.style.left = '-9999px'
    container.style.zIndex = '-1000'
    container.style.opacity = '0'
    container.style.pointerEvents = 'none'
    document.body.appendChild(container)

    // 创建图表配置
    const options = {
      chart: {
        type: 'line',
        width: width,
        height: height,
        animation: false,
        backgroundColor: '#ffffff',
        style: {
          fontFamily: 'Arial, Helvetica, sans-serif'
        },
        spacing: [30, 10, 30, 60] // 上、右、下、左的边距
      },
      title: {
        text: `${channel.channel_name}_${channel.shot_number}`,
        align: 'center',
        style: {
          fontSize: `${svgExportConfig.titleFontSize}px`,
          fontWeight: 'bold',
          color: '#000000'
        },
        margin: 20
      },
      credits: {
        enabled: false
      },
      xAxis: {
        title: {
          text: 'Time (s)',
          style: {
            fontSize: `${svgExportConfig.axisTitleFontSize}px`,
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 15
        },
        min: data.X_value[0],
        max: data.X_value[data.X_value.length - 1],
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: `${svgExportConfig.axisLabelFontSize}px`,
            color: '#000000'
          }
        }
      },
      yAxis: {
        title: {
          text: data.Y_unit || 'Value',
          style: {
            fontSize: `${svgExportConfig.axisTitleFontSize}px`,
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 15
        },
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: `${svgExportConfig.axisLabelFontSize}px`,
            color: '#000000'
          }
        }
      },
      legend: {
        enabled: true,
        align: 'right',
        verticalAlign: 'top',
        layout: 'vertical',
        backgroundColor: '#FFFFFF',
        borderWidth: 1,
        borderColor: '#E0E0E0',
        borderRadius: 5,
        itemStyle: {
          fontSize: `${svgExportConfig.legendFontSize}px`,
          fontWeight: 'normal',
          color: '#000000'
        },
        itemHoverStyle: {
          color: '#4572A7'
        },
        // 将图例放置在图表内部
        floating: true,
        x: -30,
        y: 60
      },
      series: [{
        name: channel.channel_name,
        data: data.X_value.map((x, i) => [x, data.Y_value[i]]),
        color: channel.color || '#4572A7',
        lineWidth: 1.5,
        marker: {
          enabled: false,
          radius: 3,
          symbol: 'circle'
        },
        states: {
          hover: {
            lineWidth: 2
          }
        },
        boostThreshold: 1000
      }],
      plotOptions: {
        series: {
          animation: false,
          turboThreshold: 0,
          shadow: false,
          stickyTracking: false
        },
        line: {
          marker: {
            enabled: false
          }
        }
      },
      tooltip: {
        enabled: false
      },
      boost: {
        useGPUTranslations: true,
        seriesThreshold: 1
      },
      exporting: {
        enabled: false // 确保不显示导出按钮
      }
    }

    // 渲染图表
    const chart = Highcharts.chart(container, options)

    // 等待图表渲染完成
    await new Promise(resolve => setTimeout(resolve, 500))

    // 获取SVG源码
    const svgElement = container.querySelector('svg')
    const serializedSvg = new XMLSerializer().serializeToString(svgElement)

    // 使用canvas直接从DOM中获取图表并转换为PNG/JPG
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')

    // 准备结果对象
    const result = {
      svg: null,
      png: null,
      jpg: null
    }

    // 获取SVG数据
    const svgBlob = new Blob([serializedSvg], { type: 'image/svg+xml' })
    result.svg = svgBlob

    // 使用Promise包装图像加载，获取PNG和JPG
    const imagePromise = new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => {
        // 清理背景
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, width, height)

        // 绘制图表
        ctx.drawImage(img, 0, 0, width, height)

        // 转换为PNG blob
        canvas.toBlob(pngBlob => {
          result.png = pngBlob

          // 转换为JPG blob (质量0.9)
          canvas.toBlob(jpgBlob => {
            result.jpg = jpgBlob
            resolve(result)
          }, 'image/jpeg', 0.9)
        }, 'image/png')
      }
      img.onerror = reject
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(serializedSvg)
    })

    const imageResult = await imagePromise

    // 清理
    chart.destroy()
    document.body.removeChild(container)

    return imageResult
  } catch (error) {
    console.error('渲染通道图片失败:', error)
    throw error
  }
}

// 渲染多通道为指定格式的图像
const renderMultiChannelImage = async (channels, width, height, frequencyParams, channelDataMap = null) => {
  try {
    // 创建临时容器
    const container = document.createElement('div')
    container.style.width = `${width}px`
    container.style.height = `${height}px`
    container.style.position = 'absolute'
    container.style.top = '-9999px'
    container.style.left = '-9999px'
    container.style.zIndex = '-1000'
    container.style.opacity = '0'
    container.style.pointerEvents = 'none'
    document.body.appendChild(container)

    // 获取所有通道数据并准备系列
    const seriesData = []
    const xMin = [], xMax = []

    for (const channel of channels) {
      // 获取通道数据，优先使用预先获取的数据
      const data = channelDataMap ? channelDataMap.get(channel) : await store.dispatch('fetchChannelData', {
        channel,
        ...frequencyParams
      })

      // 记录x轴范围
      xMin.push(data.X_value[0])
      xMax.push(data.X_value[data.X_value.length - 1])

      // 添加系列
      seriesData.push({
        name: `${channel.channel_name}_${channel.shot_number}`,
        data: data.X_value.map((x, i) => [x, data.Y_value[i]]),
        color: channel.color || getRandomColor(channel.channel_name),
        lineWidth: 1.5,
        marker: {
          enabled: false,
          radius: 3,
          symbol: 'circle'
        },
        states: {
          hover: {
            lineWidth: 2
          }
        },
        boostThreshold: 1000
      })
    }

    // 创建图表配置
    const options = {
      chart: {
        type: 'line',
        width: width,
        height: height,
        animation: false,
        backgroundColor: '#ffffff',
        style: {
          fontFamily: 'Arial, Helvetica, sans-serif'
        },
        spacing: [30, 10, 30, 60] // 上、右、下、左的边距
      },
      title: {
        text: 'Multi-channel data view',
        align: 'center',
        style: {
          fontSize: `${svgExportConfig.titleFontSize}px`,
          fontWeight: 'bold',
          color: '#000000'
        },
        margin: 20
      },
      credits: {
        enabled: false
      },
      xAxis: {
        title: {
          text: 'Time (s)',
          style: {
            fontSize: `${svgExportConfig.axisTitleFontSize}px`,
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 15
        },
        min: Math.min(...xMin),
        max: Math.max(...xMax),
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: `${svgExportConfig.axisLabelFontSize}px`,
            color: '#000000'
          }
        }
      },
      yAxis: {
        title: {
          text: 'value',
          style: {
            fontSize: `${svgExportConfig.axisTitleFontSize}px`,
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 15
        },
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: `${svgExportConfig.axisLabelFontSize}px`,
            color: '#000000'
          }
        }
      },
      legend: {
        enabled: true,
        align: 'right',
        verticalAlign: 'top',
        layout: 'vertical',
        backgroundColor: '#FFFFFF',
        borderWidth: 1,
        borderColor: '#E0E0E0',
        borderRadius: 5,
        itemStyle: {
          fontSize: '12px',
          fontWeight: 'normal',
          color: '#000000'
        },
        itemHoverStyle: {
          color: '#4572A7'
        },
        // 将图例放置在图表内部
        floating: true,
        x: -30,
        y: 60
      },
      series: seriesData,
      plotOptions: {
        series: {
          animation: false,
          turboThreshold: 0,
          shadow: false,
          stickyTracking: false
        },
        line: {
          marker: {
            enabled: false
          }
        }
      },
      tooltip: {
        enabled: false
      },
      boost: {
        useGPUTranslations: true,
        seriesThreshold: 1
      },
      exporting: {
        enabled: false // 确保不显示导出按钮
      }
    }

    // 渲染图表
    const chart = Highcharts.chart(container, options)

    // 等待图表渲染完成
    await new Promise(resolve => setTimeout(resolve, 500))

    // 获取SVG源码
    const svgElement = container.querySelector('svg')
    const serializedSvg = new XMLSerializer().serializeToString(svgElement)

    // 使用canvas直接从DOM中获取图表并转换为PNG/JPG
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')

    // 准备结果对象
    const result = {
      svg: null,
      png: null,
      jpg: null
    }

    // 获取SVG数据
    const svgBlob = new Blob([serializedSvg], { type: 'image/svg+xml' })
    result.svg = svgBlob

    // 使用Promise包装图像加载
    const imagePromise = new Promise((resolve, reject) => {
      const img = new Image()
      img.onload = () => {
        // 清理背景
        ctx.fillStyle = '#ffffff'
        ctx.fillRect(0, 0, width, height)

        // 绘制图表
        ctx.drawImage(img, 0, 0, width, height)

        // 转换为PNG blob
        canvas.toBlob(pngBlob => {
          result.png = pngBlob

          // 转换为JPG blob (质量0.9)
          canvas.toBlob(jpgBlob => {
            result.jpg = jpgBlob
            resolve(result)
          }, 'image/jpeg', 0.9)
        }, 'image/png')
      }
      img.onerror = reject
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(serializedSvg)
    })

    const imageResult = await imagePromise

    // 清理
    chart.destroy()
    document.body.removeChild(container)

    return imageResult
  } catch (error) {
    console.error('渲染多通道图片失败:', error)
    throw error
  }
}

// 为多通道视图生成一致的颜色
const getRandomColor = (seed) => {
  // 使用简单的字符串哈希算法为通道名生成一致的颜色
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = seed.charCodeAt(i) + ((hash << 5) - hash);
  }

  // 预定义的MATLAB风格颜色
  const matlabColors = [
    '#0072BD', // 蓝色
    '#D95319', // 橙色
    '#EDB120', // 黄色
    '#7E2F8E', // 紫色
    '#77AC30', // 绿色
    '#4DBEEE', // 浅蓝色
    '#A2142F'  // 红褐色
  ];

  // 根据哈希值选择颜色
  return matlabColors[Math.abs(hash) % matlabColors.length];
}

const handleExportCommand = (command) => {
  if (command === 'exportSvg') {
    exportChannelSVG()
  } else if (command === 'exportData') {
    // 检查是否有通道被选中
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      ElMessage.warning('请先选择至少一个通道')
      return
    }

    // 打开导出配置对话框
    initExportConfig()
    showExportDialog.value = true
  }
}

const handleResultExportCommand = (command) => {
  if (command === 'exportSvg') {
    exportResultSVG();
  } else if (command === 'exportData') {
    // 检查是否有通道被选中
    if (!selectedChannels.value || selectedChannels.value.length === 0) {
      ElMessage.warning('请先选择至少一个通道')
      return
    }

    // 获取计算结果数据
    const calculationResult = store.state.CalculateResult
    if (!calculationResult) {
      ElMessage.warning('没有找到计算结果数据')
      return
    }

    try {
      // 获取计算结果数据的副本
      const calculationResultCopy = JSON.parse(JSON.stringify(calculationResult))

      // 移除channel_number字段
      if (calculationResultCopy.hasOwnProperty('channel_number')) {
        delete calculationResultCopy.channel_number
      }

      // 将处理后的计算结果数据转换为JSON
      const jsonData = JSON.stringify(calculationResultCopy, null, 2)

      // 创建Blob
      const blob = new Blob([jsonData], { type: 'application/json' })

      // 生成文件名
      const now = new Date()
      const timestamp = `${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}_${now.getHours().toString().padStart(2, '0')}${now.getMinutes().toString().padStart(2, '0')}`

      // 生成计算结果的文件名
      let fileName = 'calculation_result'
      if (calculationResult.channel_name) {
        fileName = `${calculationResult.channel_name}_calculation_result`
      }

      // 下载文件
      downloadFile(blob, `${fileName}_${timestamp}.json`, 'json')

      ElMessage.success('计算结果数据导出成功')
    } catch (error) {
      console.error('导出计算结果数据失败:', error)
      ElMessage.error('导出计算结果数据失败，请重试')
    }
  }
}

const toggleCollapse = () => {
  isSecondSectionCollapsed.value = !isSecondSectionCollapsed.value
}

const updateSampling = (value) => {
  store.dispatch('updateSampling', value)
  store.commit('setSamplingVersion', store.state.samplingVersion + 1)
}

// 导出配置对话框状态
const showExportDialog = ref(false)
const exportConfig = reactive({
  selectedChannelIndices: [],
  channelRenames: [],
  frequencyMode: 'current', // 改为三种模式：'current', 'original', 'custom'
  customFrequency: 10.0 // 默认自定义频率10KHz
})

// 导出进度状态
const exportProgress = reactive({
  isExporting: false,
  current: 0,
  total: 0,
  percentage: 0,
  currentChannel: '',
  stage: 'downloading' // 添加阶段标识: 'downloading' 或 'packaging'
})

// 全选状态
const allChannelsSelected = computed({
  get: () => {
    if (!selectedChannels.value || selectedChannels.value.length === 0) return false
    return exportConfig.selectedChannelIndices.every(selected => selected)
  },
  set: (value) => {
    toggleAllChannels(value)
  }
})

// 初始化导出配置
const initExportConfig = () => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    exportConfig.selectedChannelIndices = selectedChannels.value.map(() => true)
    exportConfig.channelRenames = selectedChannels.value.map((channel) =>
      `${channel.channel_name}_${channel.shot_number}_data`
    )
    exportConfig.frequencyMode = 'current'
    exportConfig.customFrequency = 10.0 // 默认值重置为10kHz
  }
}

// 全选/取消全选
const toggleAllChannels = (value) => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    exportConfig.selectedChannelIndices = selectedChannels.value.map(() => value)
  }
}

// 重置通道名称
const resetChannelNames = () => {
  if (selectedChannels.value && selectedChannels.value.length > 0) {
    exportConfig.channelRenames = selectedChannels.value.map((channel) =>
      `${channel.channel_name}_${channel.shot_number}_data`
    )
  }
}

// 格式化百分比显示
const percentageFormat = (percentage) => {
  return percentage === 100 ? '完成' : `${percentage}%`
}

// 开始导出数据
const startExportData = async () => {
  try {
    // 获取选中的通道
    const channelsToExport = []
    const fileNames = []

    selectedChannels.value.forEach((channel, index) => {
      if (exportConfig.selectedChannelIndices[index]) {
        channelsToExport.push(channel)
        fileNames.push(exportConfig.channelRenames[index] || `${channel.channel_name}_${channel.shot_number}_data`)
      }
    })

    if (channelsToExport.length === 0) {
      ElMessage.warning('请至少选择一个通道进行导出')
      return
    }

    // 创建新的zip实例
    const zip = new JSZip()

    // 设置进度状态
    exportProgress.isExporting = true
    exportProgress.current = 0
    exportProgress.total = channelsToExport.length
    exportProgress.percentage = 0
    exportProgress.stage = 'downloading'

    // 获取通道数据并添加到zip
    const missingChannels = []

    // --- 并发请求所有通道数据 ---
    // 构造请求参数数组
    const fetchParamsArr = channelsToExport.map(channel => {
      const params = { channel };
      if (exportConfig.frequencyMode === 'original') {
        params.sample_mode = 'full';
      } else if (exportConfig.frequencyMode === 'custom') {
        params.sample_mode = 'downsample';
        params.sample_freq = exportConfig.customFrequency;
      }
      return params;
    });

    // 实时推进进度条
    let finishedCount = 0;
    const total = fetchParamsArr.length;

    const results = await Promise.all(
      fetchParamsArr.map((params, i) =>
        store.dispatch('fetchChannelData', params)
          .then(data => {
            finishedCount++;
            exportProgress.current = finishedCount;
            exportProgress.currentChannel = `${channelsToExport[i].channel_name}_${channelsToExport[i].shot_number}`;
            exportProgress.percentage = Math.floor((finishedCount / total) * 100);
            return { data, index: i };
          })
          .catch(error => {
            finishedCount++;
            exportProgress.current = finishedCount;
            exportProgress.currentChannel = `${channelsToExport[i].channel_name}_${channelsToExport[i].shot_number}`;
            exportProgress.percentage = Math.floor((finishedCount / total) * 100);
            missingChannels.push(`${channelsToExport[i].channel_name}_${channelsToExport[i].shot_number}`);
            return { data: null, index: i };
          })
      )
    );

    // 处理结果，写入zip
    results.forEach(({ data, index }, i) => {
      exportProgress.current = i + 1;
      exportProgress.currentChannel = `${channelsToExport[index].channel_name}_${channelsToExport[index].shot_number}`;
      exportProgress.percentage = Math.floor((i / channelsToExport.length) * 100);
      if (data) {
        const jsonData = JSON.stringify(data, null, 2);
        zip.file(`${fileNames[index]}.json`, jsonData);
      } else {
        // 已在catch中统计missingChannels
      }
    });

    // 完成下载阶段
    exportProgress.percentage = 100;
    await new Promise(resolve => setTimeout(resolve, 500));

    // 开始打包阶段
    exportProgress.stage = 'packaging'
    exportProgress.percentage = 0
    exportProgress.currentChannel = '所有通道'

    // 检查是否有缺失的通道
    if (missingChannels.length > 0) {
      if (missingChannels.length === channelsToExport.length) {
        ElMessage.error('所有选中通道的数据都无法获取，导出取消')
        exportProgress.isExporting = false
        return
      } else {
        ElMessage.warning(`部分通道数据无法获取: ${missingChannels.join(', ')}`)
      }
    }

    // 显示打包进度
    for (let i = 0; i <= 90; i += 10) {
      exportProgress.percentage = i;
      await new Promise(resolve => setTimeout(resolve, 100));
    }

    // 生成文件名中包含频率信息
    let frequencyInfo = '';
    if (exportConfig.frequencyMode === 'current') {
      frequencyInfo = `_${sampling.value}kHz`;
    } else if (exportConfig.frequencyMode === 'custom') {
      frequencyInfo = `_${exportConfig.customFrequency}kHz`;
    } else {
      frequencyInfo = '_originalFrequency';
    }

    // 生成时间戳文件名并下载
    const now = new Date()
    const timestamp = `${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}_${now.getHours().toString().padStart(2, '0')}${now.getMinutes().toString().padStart(2, '0')}${now.getSeconds().toString().padStart(2, '0')}`
    const content = await zip.generateAsync({
      type: 'blob',
      compression: 'DEFLATE',
      compressionOptions: { level: 6 }
    })

    exportProgress.percentage = 100

    // 下载文件
    await downloadFile(content, `channel_data${frequencyInfo}_${timestamp}.zip`, 'zip')

    // 重置导出状态
    exportProgress.isExporting = false
    showExportDialog.value = false

  } catch (error) {
    console.error('导出通道数据失败:', error)
    ElMessage.error('导出通道数据失败，请重试')
    exportProgress.isExporting = false
  }
}

// 开始导出SVG为单一格式图片
const startExportSvg = async () => {
  try {
    // 检查是否选择了格式
    if (!svgExportConfig.exportFormat) {
      ElMessage.warning('请选择一种导出格式')
      return
    }

    // 获取选中的通道
    const channelsToExport = []
    const fileNames = []

    selectedChannels.value.forEach((channel, index) => {
      if (svgExportConfig.selectedChannelIndices[index]) {
        channelsToExport.push(channel)
        fileNames.push(svgExportConfig.channelRenames[index] || `${channel.channel_name}_${channel.shot_number}_image`)
      }
    })

    if (channelsToExport.length === 0) {
      ElMessage.warning('请至少选择一个通道进行导出')
      return
    }

    // 创建新的zip实例（仅在单通道多图模式下使用）
    const zip = new JSZip()

    // 设置进度状态 - 首先是下载数据阶段
    svgExportProgress.isExporting = true
    svgExportProgress.current = 0
    svgExportProgress.total = channelsToExport.length
    svgExportProgress.percentage = 0
    svgExportProgress.stage = 'downloading'

    // 设置频率参数
    const frequencyParams = {}
    if (svgExportConfig.frequencyMode === 'original') {
      frequencyParams.sample_mode = 'full'
    } else if (svgExportConfig.frequencyMode === 'custom') {
      frequencyParams.sample_mode = 'downsample'
      frequencyParams.sample_freq = svgExportConfig.customFrequency
    }

    // 下载所有需要的通道数据
    const fetchParamsArr = channelsToExport.map(channel => ({
      channel,
      ...frequencyParams
    }));

    const results = await Promise.all(
      fetchParamsArr.map((params, i) =>
        store.dispatch('fetchChannelData', params)
          .then(data => ({ data, channel: channelsToExport[i] }))
          .catch(error => {
            ElMessage.warning(`获取通道 ${channelsToExport[i].channel_name}_${channelsToExport[i].shot_number} 数据失败，将跳过此通道`)
            return { data: null, channel: channelsToExport[i] };
          })
      )
    );

    const channelDataMap = new Map();
    results.forEach(({ data, channel }, i) => {
      svgExportProgress.current = i + 1;
      svgExportProgress.currentChannel = `${channel.channel_name}_${channel.shot_number}`;
      svgExportProgress.percentage = Math.floor((i / channelsToExport.length) * 100);
      if (data) channelDataMap.set(channel, data);
    });

    // 完成下载阶段，进入渲染阶段
    svgExportProgress.percentage = 100
    await new Promise(resolve => setTimeout(resolve, 300))

    // 开始渲染阶段
    svgExportProgress.current = 0
    svgExportProgress.percentage = 0
    svgExportProgress.stage = 'rendering'

    // 生成频率信息用于文件名
    let frequencyInfo = ''
    if (svgExportConfig.frequencyMode === 'current') {
      frequencyInfo = `_${sampling.value}kHz`
    } else if (svgExportConfig.frequencyMode === 'custom') {
      frequencyInfo = `_${svgExportConfig.customFrequency}kHz`
    } else {
      frequencyInfo = '_originalFrequency'
    }

    // 生成时间戳
    const now = new Date()
    const timestamp = `${now.getFullYear()}${(now.getMonth() + 1).toString().padStart(2, '0')}${now.getDate().toString().padStart(2, '0')}_${now.getHours().toString().padStart(2, '0')}${now.getMinutes().toString().padStart(2, '0')}`

    // 根据选择的导出模式决定导出方式，而不是根据当前显示模式
    if (svgExportConfig.exportMode === 'singleChannel') {
      // 单通道多图模式：每个通道单独导出
      const validChannels = channelsToExport.filter(channel => channelDataMap.has(channel))
      svgExportProgress.total = validChannels.length

      for (let i = 0; i < validChannels.length; i++) {
        const channel = validChannels[i]
        const fileName = fileNames[channelsToExport.indexOf(channel)]

        // 更新进度
        svgExportProgress.current = i + 1
        svgExportProgress.currentChannel = `${channel.channel_name}_${channel.shot_number}`
        svgExportProgress.percentage = Math.floor((i / validChannels.length) * 100)

        try {
          // 渲染并获取图像
          const channelData = channelDataMap.get(channel)
          const imageResult = await renderChannelImage(
            channel,
            fileName,
            svgExportConfig.width,
            svgExportConfig.height,
            frequencyParams,
            channelData
          )

          // 根据选择的格式添加到zip
          switch (svgExportConfig.exportFormat) {
            case 'png':
              zip.file(`${fileName}.png`, imageResult.png)
              break
            case 'jpg':
              zip.file(`${fileName}.jpg`, imageResult.jpg)
              break
            case 'svg':
              zip.file(`${fileName}.svg`, imageResult.svg)
              break
          }
        } catch (error) {
          console.error(`导出通道 ${channel.channel_name}_${channel.shot_number} 图片失败:`, error)
          ElMessage.warning(`导出通道 ${channel.channel_name}_${channel.shot_number} 图片失败`)
        }

        // 等待一点时间以更新UI
        await new Promise(resolve => setTimeout(resolve, 100))
      }

      // 切换到打包阶段
      svgExportProgress.percentage = 100
      await new Promise(resolve => setTimeout(resolve, 300))

      svgExportProgress.current = 0
      svgExportProgress.percentage = 0
      svgExportProgress.stage = 'packaging'
      svgExportProgress.currentChannel = '所有通道'
      await new Promise(resolve => setTimeout(resolve, 300))
      svgExportProgress.percentage = 50

      // 生成zip包
      const content = await zip.generateAsync({
        type: 'blob'
      })

      svgExportProgress.percentage = 100

      // 下载文件
      const fileExtension = svgExportConfig.exportFormat
      await downloadFile(content, `channel_images_${fileExtension}${frequencyInfo}_${timestamp}.zip`, 'zip')

    } else {
      // 多通道单图模式：将所有通道一起导出为一个图片
      svgExportProgress.currentChannel = '多通道视图'
      svgExportProgress.percentage = 30
      svgExportProgress.total = 1
      svgExportProgress.current = 0

      try {
        // 过滤出有效的通道(已成功下载数据的)
        const validChannels = channelsToExport.filter(channel => channelDataMap.has(channel))

        if (validChannels.length === 0) {
          ElMessage.error('没有有效的通道数据可以导出')
          svgExportProgress.isExporting = false
          return
        }

        // 更新进度
        svgExportProgress.current = 1

        // 渲染并获取图像
        const imageResult = await renderMultiChannelImage(
          validChannels,
          svgExportConfig.width,
          svgExportConfig.height,
          frequencyParams,
          channelDataMap
        )

        // 多通道单图模式：直接导出图片
        svgExportProgress.percentage = 100
        svgExportProgress.stage = 'packaging'
        await new Promise(resolve => setTimeout(resolve, 300))

        // 为多通道图片生成文件名
        const fileName = validChannels.length === 1
          ? fileNames[channelsToExport.indexOf(validChannels[0])]
          : `multi_channel_image${frequencyInfo}_${timestamp}`

        // 根据选择的格式导出文件
        switch (svgExportConfig.exportFormat) {
          case 'png':
            await downloadFile(imageResult.png, `${fileName}.png`, 'png')
            break
          case 'jpg':
            await downloadFile(imageResult.jpg, `${fileName}.jpg`, 'jpg')
            break
          case 'svg':
            await downloadFile(imageResult.svg, `${fileName}.svg`, 'svg')
            break
        }
      } catch (error) {
        console.error('导出多通道图片失败:', error)
        ElMessage.error('导出多通道图片失败，请重试')
        svgExportProgress.isExporting = false
        return
      }
    }

    // 重置导出状态
    svgExportProgress.isExporting = false
    showSvgExportDialog.value = false
  } catch (error) {
    console.error('导出通道图片失败:', error)
    ElMessage.error('导出通道图片失败，请重试')
    svgExportProgress.isExporting = false
  }
}

// 导出结果图表配置对话框状态
const showResultSvgExportDialog = ref(false)
const resultSvgExportConfig = reactive({
  width: 1200, // 默认宽度，像素
  height: 600, // 默认高度，像素
  fileName: 'calculation_result_image', // 默认文件名
  exportFormat: 'png', // 默认导出PNG格式，改为单选
  titleFontSize: 18, // 标题字号，像素
  axisTitleFontSize: 18, // 坐标轴标题字号，像素
  axisLabelFontSize: 16, // 坐标轴标签字号，像素
  legendFontSize: 14 // 图例字号，像素
})

// 导出结果图表进度状态
const resultSvgExportProgress = reactive({
  isExporting: false,
  percentage: 0,
  stage: 'rendering' // 'rendering' 或 'saving'
})

const exportResultSVG = () => {
  // 初始化配置并打开对话框
  initResultSvgExportConfig()
  showResultSvgExportDialog.value = true
}

// 初始化结果SVG导出配置
const initResultSvgExportConfig = () => {
  // 设置默认尺寸和文件名
  resultSvgExportConfig.width = 2400
  resultSvgExportConfig.height = 600

  // 如果有计算结果，可以设置更有意义的默认文件名
  const calculationResult = store.state.CalculateResult
  if (calculationResult && calculationResult.channel_name) {
    resultSvgExportConfig.fileName = `${calculationResult.channel_name}_calculation_result`
  } else {
    resultSvgExportConfig.fileName = `calculation_result_${new Date().getTime()}`
  }

  // 设置默认导出格式
  resultSvgExportConfig.exportFormat = 'png'

  // 设置默认字体大小
  resultSvgExportConfig.titleFontSize = 18
  resultSvgExportConfig.axisTitleFontSize = 18
  resultSvgExportConfig.axisLabelFontSize = 16
  resultSvgExportConfig.legendFontSize = 14
}

// 开始导出结果SVG为单一格式图像
const startExportResultSvg = async () => {
  try {
    // 检查是否选择了格式
    if (!resultSvgExportConfig.exportFormat) {
      ElMessage.warning('请选择一种导出格式')
      return
    }

    // 获取计算结果数据
    const calculationResult = store.state.CalculateResult
    if (!calculationResult) {
      ElMessage.warning('没有找到计算结果数据')
      return
    }

    // 设置进度状态
    resultSvgExportProgress.isExporting = true
    resultSvgExportProgress.percentage = 0
    resultSvgExportProgress.stage = 'rendering'

    // 更新进度到10%
    resultSvgExportProgress.percentage = 10
    await new Promise(resolve => setTimeout(resolve, 100))

    // 准备渲染高质量的图表
    // 创建临时容器
    const container = document.createElement('div')
    container.style.width = `${resultSvgExportConfig.width}px`
    container.style.height = `${resultSvgExportConfig.height}px`
    container.style.visibility = 'hidden'
    document.body.appendChild(container)

    // 更新进度到20%
    resultSvgExportProgress.percentage = 20
    await new Promise(resolve => setTimeout(resolve, 100))

    // 为导出创建一个新的Highcharts图表
    const chart = new Highcharts.Chart({
      chart: {
        renderTo: container,
        type: 'line',
        animation: false,
        style: {
          fontFamily: 'Arial, Helvetica, sans-serif'
        }
      },
      title: {
        text: calculationResult.channel_name || '计算结果',
        style: {
          fontSize: `${resultSvgExportConfig.titleFontSize}px`,
          fontWeight: 'bold',
          color: '#333333'
        }
      },
      credits: {
        enabled: false
      },
      // 禁用Highcharts自带的导出按钮
      exporting: {
        enabled: false
      },
      xAxis: {
        title: {
          text: 'Time (s)',
          style: {
            fontSize: `${resultSvgExportConfig.axisTitleFontSize}px`,
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 20
        },
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: `${resultSvgExportConfig.axisLabelFontSize}px`,
            color: '#000000'
          }
        }
      },
      yAxis: {
        title: {
          text: calculationResult.Y_unit || 'Value',
          style: {
            fontSize: `${resultSvgExportConfig.axisTitleFontSize}px`,
            fontWeight: 'bold',
            color: '#000000'
          },
          margin: 20
        },
        lineWidth: 2,
        lineColor: '#000000',
        gridLineWidth: 1,
        gridLineColor: '#E0E0E0',
        tickWidth: 2,
        tickLength: 6,
        tickColor: '#000000',
        labels: {
          style: {
            fontSize: `${resultSvgExportConfig.axisLabelFontSize}px`,
            color: '#000000'
          }
        }
      },
      legend: {
        enabled: true,
        align: 'right',
        verticalAlign: 'top',
        layout: 'vertical',
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        borderWidth: 1,
        borderColor: '#E0E0E0',
        borderRadius: 5,
        // 将图例放置在图表内部
        x: -30,
        y: 50,
        floating: true,
        itemStyle: {
          fontSize: `${resultSvgExportConfig.legendFontSize}px`,
          fontWeight: 'normal',
          color: '#000000'
        },
        itemHoverStyle: {
          color: '#4572A7'
        }
      },
      tooltip: {
        enabled: false
      },
      plotOptions: {
        series: {
          animation: false,
          marker: {
            enabled: false
          },
          states: {
            hover: {
              enabled: false
            }
          },
          stickyTracking: false,
          turboThreshold: 0
        }
      },
      series: [{
        name: calculationResult.channel_name || '计算结果',
        data: calculationResult.X_value.map((x, i) => [x, calculationResult.Y_value[i]]),
        color: '#4572A7',
        lineWidth: 1.5,
        marker: {
          enabled: false
        }
      }]
    })

    // 更新进度到40%
    resultSvgExportProgress.percentage = 40
    await new Promise(resolve => setTimeout(resolve, 100))

    // 绘制异常区域（如果有）
    if (calculationResult.X_range && calculationResult.X_range.length > 0) {
      calculationResult.X_range.forEach((xRange, index) => {
        // 为每个异常区域创建一个新系列
        chart.addSeries({
          name: `异常区域 ${index + 1}`,
          data: calculationResult.X_value
            .map((x, i) => [x, calculationResult.Y_value[i]])
            .filter(([x]) => x >= xRange[0] && x <= xRange[1]),
          lineWidth: 2,
          color: '#FF6767',
          marker: {
            enabled: false
          }
        }, false)
      })

      // 重绘图表
      chart.redraw()
    }

    // 更新进度到60%
    resultSvgExportProgress.percentage = 60
    await new Promise(resolve => setTimeout(resolve, 100))

    // 获取SVG源码
    const svgElement = container.querySelector('svg')
    const serializedSvg = new XMLSerializer().serializeToString(svgElement)

    // 准备结果对象
    const result = {
      svg: null,
      png: null,
      jpg: null
    }

    // 获取SVG数据
    if (resultSvgExportConfig.exportFormat === 'svg') {
      const svgBlob = new Blob([serializedSvg], { type: 'image/svg+xml' })
      result.svg = svgBlob
    }

    // 创建Canvas
    const canvas = document.createElement('canvas')
    canvas.width = resultSvgExportConfig.width
    canvas.height = resultSvgExportConfig.height
    const ctx = canvas.getContext('2d')

    // 根据选择的格式处理
    switch (resultSvgExportConfig.exportFormat) {
      case 'svg':
        // SVG已在上面处理
        break
      case 'png':
      case 'jpg':
        // 处理需要Canvas的格式
        await new Promise((resolve, reject) => {
          const img = new Image()
          img.onload = () => {
            // 清理背景
            ctx.fillStyle = '#ffffff'
            ctx.fillRect(0, 0, resultSvgExportConfig.width, resultSvgExportConfig.height)

            // 绘制图表
            ctx.drawImage(img, 0, 0, resultSvgExportConfig.width, resultSvgExportConfig.height)

            // 转换为对应格式的blob
            canvas.toBlob(blob => {
              if (resultSvgExportConfig.exportFormat === 'png') {
                result.png = blob
              } else {
                result.jpg = blob
              }
              resolve()
            }, resultSvgExportConfig.exportFormat === 'png' ? 'image/png' : 'image/jpeg',
              resultSvgExportConfig.exportFormat === 'jpg' ? 0.9 : 1)
          }
          img.onerror = reject
          img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(serializedSvg)
        })
        break
    }

    // 下载文件
    const fileName = `${resultSvgExportConfig.fileName}.${resultSvgExportConfig.exportFormat}`
    let fileBlob = null

    switch (resultSvgExportConfig.exportFormat) {
      case 'png':
        fileBlob = result.png
        break
      case 'jpg':
        fileBlob = result.jpg
        break
      case 'svg':
        fileBlob = result.svg
        break
    }

    if (fileBlob) {
      await downloadFile(fileBlob, fileName, resultSvgExportConfig.exportFormat)
    }

    // 更新进度到80%
    resultSvgExportProgress.percentage = 80
    await new Promise(resolve => setTimeout(resolve, 100))

    // 更新进度到100%
    resultSvgExportProgress.percentage = 100
    await new Promise(resolve => setTimeout(resolve, 100))

    // 清理
    chart.destroy()
    document.body.removeChild(container)

    // 重置状态
    resultSvgExportProgress.isExporting = false
    showResultSvgExportDialog.value = false

  } catch (error) {
    console.error('导出计算结果图表失败:', error)
    ElMessage.error('导出计算结果图表失败，请重试')
    resultSvgExportProgress.isExporting = false
  }
}

// 用于监听多通道单行视图容器尺寸
const chartAreaRef = ref(null)
const overviewBrushRef = ref(null)

// 计算可用高度（减去OverviewBrush高度）
const updateChartAreaSize = () => {
  if (chartAreaRef.value) {
    const rect = chartAreaRef.value.getBoundingClientRect()
    let brushHeight = 0
    // 获取OverviewBrush真实高度
    if (overviewBrushRef.value && overviewBrushRef.value.$el) {
      brushHeight = overviewBrushRef.value.$el.offsetHeight || 0
    }
    chartAreaRef.value.style.height = `${rect.height - brushHeight}px`
  }
}

onMounted(() => {
  if (chartAreaRef.value) {
    chartAreaResizeObserver = new ResizeObserver(() => {
      updateChartAreaSize()
    })
    chartAreaResizeObserver.observe(chartAreaRef.value)
    // 首次也要手动算一次
    nextTick(() => {
      updateChartAreaSize()
    })
  }
})

watch(
  () => [chartAreaRef.value, overviewBrushRef.value],
  () => {
    nextTick(() => {
      updateChartAreaSize()
    })
  }
)

const chartAreaHeight = computed(() => {
  // 使用减去一些像素的方式，确保高度略微小于容器，避免滚动条
  return isSecondSectionCollapsed.value ? 'calc(81vh - 5px)' : 'calc(50vh - 5px)';
})
</script>

<style scoped lang="scss">
.title {
  position: relative;
  font-size: 12pt;
  color: #333;
  font-weight: bold;
  margin-left: 5px;
  display: flex;
  gap: 5px;
  align-items: center;
  justify-content: center;
}

.el-card {
  --el-card-padding: 6px;
}

.el-main {
  padding: 0px !important;
}

.all-layout {
  width: 100vw;
  height: 100vh;
  background-color: #e2e2e2;
  overflow: hidden;
  user-select: none;
  -webkit-user-select: none;
  -moz-user-select: none;
  -ms-user-select: none;
}

.aside {
  width: 25vw;
  background-color: #e9e9e9;
  height: 95vh;
  box-sizing: border-box;
  display: flex;
}

// 添加这个样式确保el-container正确显示
:deep(.el-container) {
  height: 100%;
  flex-direction: column;
}

// 确保内部容器正确显示
:deep(.el-container .el-container) {
  flex-direction: row;
}

.aside-content,
.main {
  display: flex;
  flex-direction: column;
  height: 100%;
  width: 100%;
}

.jump_switch {
  margin-bottom: 5px;
  padding-bottom: 10px;
  display: flex;
  justify-content: center;
}

.filtandsearch {
  flex-shrink: 0;
}

.table {
  flex-grow: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  margin-top: 0;

  .color_table_switch {
    position: absolute;
    right: 10px;
  }

  .scrollbar-container {
    flex: 1;
    height: 100%;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  :deep(.el-scrollbar) {
    height: 100%;
    flex: 1;

    .el-scrollbar__wrap {
      overflow-x: hidden;
    }
  }

  .title-row {
    padding: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .table-container {
    flex: 1;
    position: relative;
    display: flex;
    flex-direction: column;
    height: calc(100% - 32px); // 减去title-row的高度
  }
}

.test_main {
  background-color: #e9e9e9;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;

  .data_exploration {
    margin-bottom: 0;
    width: 100%;
    height: 100%;
    flex: 2.1;
    position: relative;
  }

  .collapse-control {
    display: flex;
    justify-content: center;
    margin: 0 0 2px 0;

    .collapse-btn {
      padding: 2px 8px;
      font-size: 12px;
      display: flex;
      align-items: center;
      color: #909399;
      height: 24px;

      &:hover {
        color: #409EFF;
      }

      .el-icon {
        margin-right: 2px;
        font-size: 12px;
      }

      .collapse-text {
        font-size: 12px;
      }
    }
  }

  .collapse-bookmark {
    position: absolute;
    bottom: -12px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 10;

    .bookmark-btn {
      width: 24px;
      height: 16px;
      padding: 0;
      border-radius: 0 0 4px 4px;
      background-color: #f2f6fc;
      border: 1px solid #dcdfe6;
      border-top: none;
      box-shadow: 0 2px 2px rgba(0, 0, 0, 0.05);
      display: flex;
      justify-content: center;
      align-items: center;

      &:hover {
        background-color: #ecf5ff;
        color: #409EFF;
      }

      .el-icon {
        font-size: 12px;
        margin: 0;
      }
    }
  }

  .two {
    margin-top: 0;
    display: flex;
    flex: 1;
    flex-grow: 1;
    position: relative;
    transition: all 0.3s ease;
  }

  .two_left {
    flex: 1.5;
    position: relative;
    width: 100%;
  }

  .two_right {
    flex: 2;
    position: relative;
    width: 70%;
    height: 100%;
  }
}

.channel_main {
  background-color: #e9e9e9;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 100%;

  .operator {
    margin-bottom: 0;
  }

  .data_exploration {
    width: 100%;
    height: 100%;
    flex: 1.4;
  }

  .two {
    display: flex;
    flex: 1;
    flex-grow: 1;
    height: 100%;
  }

  .two_left {
    flex: 2.5;
    position: relative;
    height: 100%;
  }

  .two_right {
    flex: 1;
    position: relative;
    height: 100%;
  }
}

/* 让输入框内的文字可以选中 */
.el-input {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让输入框内的文字可以选中 */
.el-input__inner {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让对话框中的输入框文字可以选中 */
.el-dialog .el-input {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让数字输入框内的文字可以选中 */
.el-input-number {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

/* 让下拉菜单中的文字可以选中 */
.el-dropdown-menu {
  user-select: text;
  -webkit-user-select: text;
  -moz-user-select: text;
  -ms-user-select: text;
}

.arc-toggle-container {
  position: relative;
  display: flex;
  justify-content: center;
  height: 0;
  z-index: 999;
}

.arc-toggle {
  position: absolute;
  top: -20px;
  padding: 3px 20px 0px 20px;
  background-color: #f2f6fc;
  border-top-left-radius: 12px;
  border-top-right-radius: 12px;
  border-top: none;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;

  &:hover {
    box-shadow: 0 3px 6px rgba(0, 0, 0, 0.15);
    transform: translateY(1px);
  }

  .arc-toggle-icon {
    margin-right: 4px;
    font-size: 14px;
    color: #409EFF;
  }

  .arc-toggle-text {
    font-size: 12px;
    white-space: nowrap;
    /* 防止文本换行 */
  }
}

/* 三横线菜单按钮样式 */
.menu-button {
  padding: 8px;
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.menu-button .el-icon {
  font-size: 18px;
  margin: 0;
}


.el-button-group .el-button {
  font-size: 12px;
  padding: 6px 12px;
  transition: all 0.3s;
}

.el-button-group .el-button:not(:first-child):not(:last-child) {
  margin: 0 -1px;
}

/* 控制面板样式 */
.control-panel {
  display: flex;
  align-items: center;
  gap: 10px;
}

.control-item {
  display: flex;
  align-items: center;
}

.control-label {
  margin-right: 8px;
  font-size: 0.9em;
  color: #606266;
  white-space: nowrap;
}

.control-unit {
  margin-left: 4px;
  font-size: 0.9em;
  color: #606266;
}

/* 统一输入框样式 */
:deep(.el-input-number) {
  width: 140px;
}

:deep(.el-input-number .el-input__inner) {
  text-align: center;
}

/* 统一按钮组样式 */
:deep(.el-button-group .el-button) {
  font-size: 12px;
  padding: 6px 12px;
}

/* 导出配置对话框样式 */
.export-dialog {
  :deep(.el-dialog__body) {
    padding: 20px 25px;
    max-height: 650px;
    overflow-y: auto;
  }

  :deep(.el-dialog) {
    margin-top: 5vh !important;
    /* 将对话框位置上移 */
    margin-bottom: 5vh;
    height: auto;
    max-height: 90vh;
    /* 设置最大高度为视口的90% */
    display: flex;
    flex-direction: column;
  }

  :deep(.el-dialog__header) {
    padding-bottom: 15px;
  }

  :deep(.el-dialog__footer) {
    padding-top: 15px;
    border-top: 1px solid #e4e7ed;
  }
}

.channel-selection {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 15px;
  background-color: #f8f9fa;
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  /* 允许元素在容器中增长 */
  overflow: hidden;
  /* 防止内容溢出 */

  :deep(.el-scrollbar) {
    flex-grow: 1;
    /* 滚动区域可自动增长 */
    display: flex;
    flex-direction: column;
    height: 100%;
    /* 确保滚动区域填充整个容器 */
  }

  :deep(.el-scrollbar__wrap) {
    overflow-x: hidden;
    /* 隐藏水平滚动条 */
  }
}

.channel-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #e4e7ed;
}

.channel-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px dashed #ebeef5;
  justify-content: space-between;
}

.channel-name {
  margin-left: 10px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  width: 180px;
}

.filename-input-container {
  position: relative;
  width: 180px;

  .el-input {
    width: 100%;
  }

  .file-extension {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    pointer-events: none;
  }
}

/* 频率选项样式 */
.frequency-options {
  margin-top: 5px;
}

.frequency-radio-container {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.radio-option {
  display: flex;
  flex-direction: column;
  margin-bottom: 10px;

  &:last-child {
    margin-bottom: 0;
  }
}

.radio-with-tag {
  display: flex;
  align-items: center;
  height: 28px;
  line-height: 28px;

  .el-radio {
    margin-right: 8px;
  }

  .el-tag {
    margin-left: 8px;
  }
}

.custom-frequency-control {
  margin-top: 5px;
  margin-left: 23px;
  display: flex;
  align-items: center;

  .el-input-number {
    width: 110px;
  }

  .unit-label {
    margin-left: 5px;
    color: #606266;
  }
}

.export-progress {
  padding: 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
  border: 1px solid #e4e7ed;
  min-height: 70px;

  p {
    margin-bottom: 8px;
    color: #606266;
  }
}

/* 添加新的占位容器样式，用于保持对齐 */
.export-progress-placeholder {
  height: 70px;
  border: 1px solid transparent;
}

.progress-container {
  margin-top: auto;
  /* 将进度条区域推到底部 */
}

/* 添加导出模式相关样式 */
.mode-selection {
  margin-bottom: 10px;
}

.mode-radio-container {
  display: flex;
  flex-direction: column;
}

.mode-radio-container .radio-option {
  margin-bottom: 8px;
}

/* 导出对话框左右布局样式 */
.dialog-layout {
  display: flex;
  gap: 20px;
  height: auto;
}

.left-section {
  flex: 1;
  min-width: 400px;
  display: flex;
  flex-direction: column;
}

.right-section {
  flex: 1;
  min-width: 400px;
  display: flex;
  flex-direction: column;
}

.section-title {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 15px;
  color: #333;
}

.param-form {
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 15px;
  background-color: #f8f9fa;
  overflow-y: auto;
}

/* 添加新的占位容器样式，用于保持对齐 */
.export-progress-placeholder {
  height: 70px;
  border: 1px solid transparent;
}

/* 添加上边距类 */
.mt-10 {
  margin-top: 10px;
}

/* 调整尺寸控件容器 */
.size-controls-container {
  margin-bottom: 8px;
}

/* SVG导出对话框尺寸控件 */
.size-controls {
  display: flex;
  gap: 15px;
}

.size-input-group {
  display: flex;
  align-items: center;

  .size-label {
    margin-right: 5px;
    white-space: nowrap;
  }

  .size-unit {
    margin-left: 5px;
    color: #606266;
  }

  :deep(.el-input-number) {
    width: 70px;
  }
}

/* 添加导出格式选择样式 */
.format-selection {
  margin-bottom: 10px;
}

.format-radio-container {
  display: flex;
  gap: 20px;
}

.format-radio-container .el-radio {
  margin-right: 10px;
  border: 1px solid #ebeef5;
  padding: 6px 12px;
  border-radius: 4px;
  transition: all 0.3s;
}

.format-radio-container .el-radio.is-checked {
  background-color: #f0f7ff;
  border-color: #409eff;
}

.font-size-container {
  margin-top: 5px;
  margin-bottom: 12px;
}

:deep(.el-input-number.is-small) {
  width: 70px;
}

/* 优化表单项间距 */
:deep(.el-form-item) {
  margin-bottom: 12px;
}

:deep(.el-form-item__label) {
  padding-bottom: 4px;
  line-height: 30px;
}
</style>
