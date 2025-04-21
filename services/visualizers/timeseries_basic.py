import panel as pn
import holoviews as hv
import hvplot.pandas # noqa: F401 - 确保导入 hvplot 扩展以注册 .hvplot accessor
from holoviews.plotting.links import RangeToolLink
# from model.data_container import DataContainer # 基类通常不需要直接导入
from ..registry import VISUALIZERS, register_service # 调整导入路径
from typing import List, Tuple, Any, Optional, Union
import pandas as pd
from holoviews.operation.datashader import rasterize # 只导入 rasterize，通常足够
# from holoviews.streams import RangeX # 当前未使用
import numpy as np
from model.timeseries_container import TimeSeriesContainer # 导入具体容器
# from config.constants import DATA_TYPE_TIMESERIES, DATA_TYPE_MULTIDIM_TIMESERIES # 常量在此文件未使用

# === 辅助函数 ===

def _prepare_timeseries_df(data_container: TimeSeriesContainer, value_col_name: str = 'value') -> Optional[pd.DataFrame]:
    """准备用于 hvPlot 绘图的时间序列 DataFrame。

    从 TimeSeriesContainer 中提取数据，确保索引为 DatetimeIndex，
    处理 Series 和 DataFrame 的情况，并将数据转换为适合绘图的格式
    (包含 'time' 列和数值数据列)。

    Args:
        data_container: 包含时间序列数据的 TimeSeriesContainer 对象。
        value_col_name: 如果输入数据是 Series，指定转换后值列的名称。

    Returns:
        包含 'time' 列和数据列的 DataFrame，如果数据无效或无法处理则返回 None。
    """
    data = data_container.get_data()

    # 检查数据类型和索引类型
    if isinstance(data, pd.Series):
        if not isinstance(data.index, pd.DatetimeIndex):
            print(f"警告 (数据: '{data_container.name}'): Series 索引不是 DatetimeIndex，跳过。")
            return None
        # 将 Series 转换为 DataFrame
        df = data.to_frame(name=value_col_name)
    elif isinstance(data, pd.DataFrame):
        if not isinstance(data.index, pd.DatetimeIndex):
            print(f"警告 (数据: '{data_container.name}'): DataFrame 索引不是 DatetimeIndex，跳过。")
            return None
        df = data.copy()
    else:
        # 如果不是 Series 或 DataFrame (理论上 TimeSeriesContainer 会阻止)
        print(f"警告 (数据: '{data_container.name}'): 包含不支持的数据类型 {type(data)}，跳过。")
        return None

    # 确保索引名符合 hvplot 预期 (通常是 'time')
    if df.index.name != 'time':
        df.index.name = 'time'

    # 检查数据是否为空
    if df.empty:
         print(f"警告 (数据: '{data_container.name}'): 数据为空，跳过。")
         return None

    # 检查是否包含数值列
    numeric_cols = df.select_dtypes(include=np.number).columns
    if not numeric_cols.any():
        print(f"警告 (数据: '{data_container.name}'): 不包含可绘制的数值列，跳过。")
        return None

    # 修正：如果原始数据是 Series，确保转换后的 DataFrame 列名正确
    if isinstance(data, pd.Series) and value_col_name not in df.columns and len(df.columns) == 1:
         df.rename(columns={df.columns[0]: value_col_name}, inplace=True)

    # 确保 'time' 索引作为列存在，以便 hvplot(x='time', ...) 工作
    if 'time' not in df.columns:
        df.reset_index(inplace=True)

    return df

def _plot_base_timeseries(df: Optional[pd.DataFrame], value_col: str, x_col: str = 'time', **hvplot_opts) -> Optional[hv.Element]:
    """使用 hvPlot 绘制基础的时间序列图 (如 Curve, Points)。

    Args:
        df: 包含绘图数据的 DataFrame (应包含 x_col 和 value_col 列)。
        value_col: 要绘制的值列 (Y 轴) 的名称。
        x_col: 用作 X 轴的列名称 (默认为 'time')。
        **hvplot_opts: 传递给 `df.hvplot()` 的其他关键字参数，例如 height, width, title。

    Returns:
        HoloViews 图表元素 (hv.Element) 或 None (如果无法绘制)。
    """
    # 基本验证
    if df is None or df.empty:
        return None
    if value_col not in df.columns:
        print(f"警告: Y 轴列 '{value_col}' 不在 DataFrame 中。可用列: {list(df.columns)}")
        return None
    if x_col not in df.columns:
        print(f"警告: X 轴列 '{x_col}' 不在 DataFrame 中。可用列: {list(df.columns)}")
        return None

    try:
        # 调用 hvplot 进行绘图
        plot = df.hvplot(x=x_col, y=value_col, **hvplot_opts)
        # 验证返回的是有效的 HoloViews Element
        if isinstance(plot, hv.Element):
             return plot
        else:
             # hvplot 在某些情况下可能不直接返回 Element (例如某些复杂的组合)
             print(f"警告: hvplot 未返回有效的 HoloViews Element (得到 {type(plot)})。")
             return None # 或者尝试处理 plot 对象？目前返回 None
    except Exception as e:
        # 捕获 hvplot 执行期间的任何错误
        print(f"错误: 绘制基础时间序列图时出错 (x='{x_col}', y='{value_col}'): {e}")
        return None

def _create_minimap(
    df: Optional[pd.DataFrame], 
    value_col: str, 
    x_col: str = 'time', 
    height: int = 100, 
    use_rasterize: bool = True, 
    **hvplot_opts
) -> Optional[hv.Element]:
    """创建用于导航的时间序列缩略图 (minimap)。

    Args:
        df: 包含绘图数据的 DataFrame。
        value_col: 要在缩略图中绘制的值列名称。
        x_col: 时间列名称 (默认为 'time')。
        height: 缩略图的高度 (像素)。
        use_rasterize: 是否对缩略图应用 `holoviews.operation.datashader.rasterize`。
        **hvplot_opts: 传递给底层 `_plot_base_timeseries` 函数的其他 hvplot 选项。

    Returns:
        HoloViews 缩略图元素 (hv.Element) 或 None。
    """
    if df is None or df.empty:
        return None

    # 缩略图的默认样式选项
    default_opts = {
        'height': height,
        'responsive': True,
        'shared_axes': False,
        'toolbar': None,
        'default_tools': [],
        'xaxis': None,
        'yaxis': None,
        'padding': 0.01,
        'line_width': 1,
        'cmap': ['lightgray'],
        'colorbar': False,
        'title': ''
    }
    # 合并默认选项和用户传入的选项
    final_opts = {**default_opts, **hvplot_opts}

    # 绘制基础缩略图
    plot = _plot_base_timeseries(df, value_col, x_col, **final_opts)

    # 如果绘图成功且需要光栅化
    if plot and use_rasterize:
        try:
            # 应用 rasterize 操作
            plot = rasterize(plot, cmap=final_opts.get('cmap'))
        except Exception as ds_e:
            print(f"警告: 对缩略图应用 rasterize 失败: {ds_e}。将使用原始图。")
            # 光栅化失败，继续使用未光栅化的图

    return plot

# === 可视化服务 ===

def plot_timeseries_linked_view(
    data_containers: List[TimeSeriesContainer],
    width: int = 800,
    main_height: int = 400,
    minimap_height: int = 100
) -> Union[hv.Layout, pn.Column]: # 返回 Panel Column 以便包含 Alert
    """为多个时间序列数据集创建带有共享缩略图的联动视图。

    Args:
        data_containers (List[TimeSeriesContainer]): 包含待可视化时间序列数据的容器列表。
        width (int): 图表宽度。
        main_height (int): 每个主图的高度。
        minimap_height (int): 共享缩略图的高度。

    Returns:
        Union[hv.Layout, pn.Column]: HoloViews 布局对象或 Panel Column 对象。
                                     如果发生错误，Column 可能包含图表和错误提示。
                                     如果完全无法生成图表，只返回包含错误的 Column。
    """
    main_plots = []
    error_messages = [] # 用于收集处理过程中的非阻塞性错误/警告
    valid_dfs = [] # 存储成功准备好的 DataFrame
    # 标准化值列名，因为 Series 转 DataFrame 时会用到
    value_col_name_default = 'value'

    # --- 1. 准备数据并创建主图 --- 
    for data_container in data_containers:
        df = _prepare_timeseries_df(data_container, value_col_name=value_col_name_default)
        if df is None:
            error_messages.append(f"数据 '{data_container.name}' 无效或无法准备，已跳过。")
            continue

        # 检查 DataFrame 是否包含有效的数值列
        numeric_cols = df.select_dtypes(include=np.number).columns
        if numeric_cols.empty:
             error_messages.append(f"数据 '{data_container.name}' 准备后不含数值列，已跳过。")
             continue
        
        # 如果有多列，选择第一列进行绘制，并记录警告
        # TODO: 未来可以提供选择列的参数
        plot_col = numeric_cols[0]
        if len(numeric_cols) > 1:
            warn_msg = f"数据 '{data_container.name}' 含多列 ({list(numeric_cols)})，仅绘制 '{plot_col}'。"
            print(f"警告: {warn_msg}")
            error_messages.append(warn_msg) # 也将其添加到摘要错误中

        # 存储有效的 DataFrame 供缩略图使用
        valid_dfs.append(df)
        plot_title = data_container.name # 使用数据名称作为图表标题

        # 创建主图
        main_plot = _plot_base_timeseries(
            df, 
            value_col=plot_col, 
            x_col='time', 
            height=main_height, 
            width=width,
            responsive=True, 
            shared_axes=False, # 主图不共享 Y 轴
            title=plot_title,
            tools=['hover'], # 启用悬停工具
            line_width=1.5
            # 考虑是否默认启用 rasterize 或根据数据量决定
            # rasterize=len(df) > 10000 
        )
        if main_plot:
            main_plots.append(main_plot)
        else:
            # 如果 _plot_base_timeseries 返回 None，记录错误
            error_messages.append(f"无法为 '{data_container.name}' 创建主图。")

    # --- 处理完全没有有效数据的情况 --- 
    if not main_plots:
        error_summary = "没有有效的可绘制数据。"
        if error_messages:
            error_summary += "\n详情:\n" + "\n".join(f"- {e}" for e in error_messages)
        # 返回一个仅包含错误提示的 Panel Column
        return pn.Column(pn.pane.Alert(error_summary, alert_type='danger'))

    # --- 2. 创建共享缩略图 (如果至少有一个有效 DataFrame) --- 
    shared_minimap = None
    if valid_dfs:
        # 使用第一个有效 DataFrame 创建缩略图
        shared_minimap = _create_minimap(
            valid_dfs[0],
            value_col=value_col_name_default, # 使用转换后的标准列名
            x_col='time',
            height=minimap_height, 
            width=width,
            use_rasterize=True, # 缩略图通常适合光栅化
            cmap=['lightgrey']
        )
        if shared_minimap is None:
            error_messages.append("无法创建共享缩略图。")

    # --- 3. 链接缩略图和主图 (如果缩略图创建成功) --- 
    if shared_minimap:
        try:
            # 使用 RangeToolLink 将缩略图的 X 轴范围链接到所有主图的 X 轴
            RangeToolLink(shared_minimap, main_plots, axes=['x'])
        except Exception as link_e:
             link_error_msg = f"链接缩略图到主图时出错: {link_e}"
             print(f"警告: {link_error_msg}")
             error_messages.append(link_error_msg)
             # 链接失败不阻止显示，但记录错误

    # --- 4. 构建最终布局 --- 
    try:
        # 将所有主图垂直排列
        main_layout = hv.Layout(main_plots).cols(1)
        # 如果有缩略图，则将其添加到主图下方
        final_layout_content = [main_layout]
        if shared_minimap:
            final_layout_content.append(shared_minimap)
            
        # 使用 Panel Column 来组合 HoloViews 对象和可能的错误 Alert
        final_column = pn.Column(*final_layout_content)
        
        # 如果在处理过程中有任何错误/警告，附加一个 Alert
        if error_messages:
             error_panel = pn.pane.Alert("可视化过程中出现问题:\n" + "\n".join(f"- {e}" for e in error_messages), alert_type='warning')
             final_column.append(error_panel)
             
        return final_column

    except Exception as layout_e:
         # 处理布局构建本身可能出现的错误
         print(f"错误: 创建最终布局时出错: {layout_e}")
         # 返回包含布局错误的 Alert
         return pn.Column(pn.pane.Alert(f"创建图表布局失败: {layout_e}", alert_type='danger'))

# --- 服务注册 --- 
register_service(
    registry=VISUALIZERS,
    name="基础时序图 (联动缩略图)",
    function=plot_timeseries_linked_view,
    input_type=List[TimeSeriesContainer], # 明确输入是 TimeSeriesContainer 列表
    output_type=pn.Column, # 最终返回的是 Panel Column (可能包含 hv.Layout 和/或 pn.Alert)
    accepts_list=True, # 明确服务接受列表
    input_param_name='data_containers', # 函数期望的列表参数名
    params_spec={ # 允许用户在 UI 配置这些参数
        'width': {'type': 'integer', 'label': '图表宽度', 'default': 800, 'min': 100},
        'main_height': {'type': 'integer', 'label': '主图高度', 'default': 400, 'min': 50},
        'minimap_height': {'type': 'integer', 'label': '缩略图高度', 'default': 100, 'min': 30},
    }
)

# 移除了 plot_timeseries_dynamic_rasterized，其功能可由 plot_timeseries_complex_layout_refactored 替代
# 或作为单独的基础可视化服务（如果需要）

# === 可视化服务 === END === 