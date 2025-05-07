# TSAP - 时序分析处理平台

基于节点和工作流的架构，用于时序数据的处理、分析和可视化。从MATLAB代码迁移并现代化，采用Python实现。

## 项目结构

```
TSAP/
├── core/             # 核心基础类
│   └── node/         # 节点基类和工具
├── nodes/            # 节点实现
│   ├── io/           # 数据加载/保存节点
│   ├── analysis/     # 分析处理节点
│   └── visualization/# 可视化节点
├── workflows/        # 工作流定义
├── data/             # 数据目录
│   ├── sat1/         # 示例数据集1
│   └── sat2/         # 示例数据集2
└── ui/               # 前端界面（计划中）
```

## 功能特点

- **模块化**: 各功能以节点形式实现，可灵活组合
- **可扩展**: 易于添加新的节点和工作流
- **工作流**: 基于Prefect实现，支持任务调度和监控
- **可视化**: 使用Plotly生成交互式图表

## 当前实现的功能

1. **数据加载**: 支持CSV格式的时序数据
2. **数据预处理**: 
   - 滤波: 均值降采样、低通滤波
   - 数据切片: 支持可配置窗口长度和重叠比例
3. **时频分析**:
   - STFT (短时傅里叶变换)
   - CWT (连续小波变换)
4. **可视化**:
   - 时域图
   - 频域图
   - 时频谱图
   - 瀑布图

## 安装与使用

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行示例工作流

可以通过两种方式运行:

1. 使用启动脚本:

```bash
python run_workflow.py
```

2. 直接运行工作流模块:

```bash
python -m workflows.time_frequency_workflow
```

## 配置工作流参数

可以在 `run_workflow.py` 或 `workflows/time_frequency_workflow.py` 中修改以下参数:

```python
result = time_frequency_workflow(
    file_path="<数据文件路径>",          # 数据文件路径
    window_duration=1*60*60,           # 窗口长度（秒）
    overlap_ratio=0.5,                 # 重叠比例
    freq_range=(0, 0.001),             # 频率范围(Hz)
    analysis_method='stft',            # 分析方法: 'stft' 或 'cwt'
    slice_index=0,                     # 要分析的切片，-1表示全部
    filter_type='lowpass',             # 滤波类型: 'mean', 'lowpass', None
    filter_param=0.01                  # 滤波参数
)
```

## 未来计划

- 完善API接口
- 实现前端交互式界面
- 支持更多分析算法和可视化方式
- 支持持久化和导出结果

# 时间序列数据分析系统

DataAnalyseSystem/
├── model/
│   ├── data_container.py   # 定义 DataContainer 基类
│   ├── timeseries_data.py  # 定义 TimeSeriesData 类 (继承 DataContainer)
│   ├── multidim_data.py    # 定义 MultiDimData 类 (继承 DataContainer)
│   ├── analysis_result.py  # 定义 AnalysisResult 类 (继承 DataContainer)
│   └── data_manager.py     # 定义 DataManager 类 (核心管理逻辑)
│
├── view/
│   ├── pages/
│   │   ├── data_manager_page.py # Panel UI for DataManagerPage
│   │   ├── load_page.py
│   │   ├── single_dim_page.py
│   │   └── ...
│   └── widgets/
│       └── data_selector.py    # 可复用的 Panel 数据选择控件
│
├── controller/
│   ├── data_manager_controller.py # 控制器，处理 DataManagerPage 的交互逻辑
│   ├── load_controller.py
│   ├── single_dim_controller.py # 会与 DataManager 交互以获取可选数据和添加新数据
│   └── ...
│
├── services/
│   ├── base_processor.py      # (可选) 定义处理器基类或接口
│   ├── preprocessors.py       # 一维预处理函数/类
│   ├── analyzers.py           # 多维分析函数/类
│   ├── visualizers.py         # 可视化生成函数/类
│   ├── merger.py              # 数据合并逻辑
│   └── registry.py            # 处理器注册表和注册函数
│
└── main.py                     # 应用入口，组装 MVC 和 Panel 应用
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

