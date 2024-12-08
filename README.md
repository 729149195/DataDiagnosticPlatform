# DataDiagnosticPlatform (数据诊断平台)

## 项目简介
DataDiagnosticPlatform 是一个专业的数据诊断和分析平台，基于 Vue.js + Django 开发，用于数据异常检测、数据分析和可视化展示。

## 技术栈
### 前端
- Vue 3
- Vuex
- Vue Router
- Element Plus
- D3.js
- Fabric.js
- Socket.io
- SCSS
- Vite

### 后端
- Django
- Django Channels
- Django REST framework
- NumPy
- ML libraries (ml-savitzky-golay等)

## 主要功能
- 数据异常检测
  - 时序数据异常识别
  - 多维数据分析
  - 自定义异常规则配置
  
- 数据可视化
  - 实时数据展示
  - 多维数据展示
  - 自定义图表配置
  
- 数据分析
  - 数据趋势分析
  - 相关性分析
  - 数据预处理

## 快速开始

### 环境要求
- Node.js >= 12.0.0
- Python >= 3.8
- Django >= 4.0

### 安装步骤

1. 克隆项目
```bash
git clone https://github.com/yourusername/DataDiagnosticPlatform.git
cd DataDiagnosticPlatform
```

2. 安装前端依赖
```bash
cd frontend
npm install
```

3. 安装后端依赖
```bash
cd backend
pip install -r requirements.txt
```

4. 启动项目
```bash
# 在项目根目录执行
./start.bat  # Windows
# 或
./start.sh   # Linux/Mac
```

## 项目结构
```
DataDiagnosticPlatform/
├── frontend/                # 前端项目
│   ├── src/                # 源代码
│   ├── public/             # 静态资源
│   └── package.json        # 项目配置
├── backend/                # 后端项目
│   ├── api/               # API接口
│   ├── config/            # 配置文件
│   └── manage.py          # Django管理脚本
├── start.bat              # Windows启动脚本
└── README.md              # 项目说明
```

## API文档
- GET /api/struct-tree/ - 获取结构树
- GET /api/channel-data/ - 获取通道数据
- GET /api/error-data/ - 获取错误数据
- POST /api/submit-data/ - 提交数据
- GET /api/operator-strs/ - 处理通道名称
- WebSocket /ws/progress/ - 进度通知

## 开发团队
待补充

## 许可证
MIT License

## 联系方式
待补充
