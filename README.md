# 时间序列数据分析系统

一个简单的时间序列数据分析系统，使用pyarrow加载数据，datashader配合hvplot实现交互式可视化。

## 功能特点

- 使用pyarrow高效加载CSV数据
- 使用datashader实现大数据集的高效渲染
- 支持自适应y轴
- 支持通过rangetool调整x轴显示范围
- 支持datashader动态重绘

## 技术栈

- pyarrow: 高效加载CSV数据
- pandas: 数据处理
- datashader: 大数据可视化
- hvplot: 交互式绘图
- panel: 创建交互式界面

## 使用方法

### 运行应用

```bash
python app.py
```

应用会自动启动并打开浏览器。由于启用了热加载功能(auto_reload=True)，修改代码后，应用会自动刷新，无需手动重启服务器。

## 界面说明

1. 在文件选择器中选择data目录下的CSV文件
2. 点击"加载数据"按钮
3. 在时间列下拉框中选择包含时间信息的列
4. 在多选框中选择要可视化的数据列
5. 点击"可视化"按钮生成图表
6. 使用底部的滑块或小型预览图调整时间范围

## 系统架构

该系统采用MVC架构：

- 模型层(model/): 处理数据加载和处理
- 视图层(view/): 负责数据可视化
- 控制器层(controller/): 处理用户交互和业务逻辑

# 功能

数据分析平台
用于可视化分析多维时间序列，并开发分析模型
要求能存储和可视化每一步处理前后的数据

## 项目结构

```
DataAnalyseSystem/
├── ui/                       # 界面模块
│   ├── app.py     # 显示框架
│   ├── loder_ui.py     # 数据加载界面
│   ├── analyse_ui.py     # 数据分析与可视化界面
│   └── proccess_ui.py     # 数据处理与特征工程界面
├── main.py                 # 主应用入口
├── core/                  # 核心功能模块
│   ├── data_manager.py     # 数据管理
│   └── plugins_manager.py     # 插件管理
├── plugins/            # 插件目录
│   ├──  analysers  # 分析算法插件目录
│   ├──  procceers  # 特征工程插件目录
│   └──  loaders  # 加载器插件目录
├── utils/                     # 辅助代码
├── data/                      # 数据目录
└── requirements.txt           # 项目依赖
```

## 技术栈
pyarrow
parquet
perfect
dask

panel
datashader
holoviews

pytorch ligntning
optuna

tslearn
tsfresh
autots
darts
sktime
deeptime

