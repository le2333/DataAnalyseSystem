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

