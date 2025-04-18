import panel as pn
import holoviews as hv
import hvplot.pandas # 确保导入了 hvplot 扩展
# import datashader as ds # Not needed for basic curve
# from holoviews.operation.datashader import datashade, rasterize # Not needed
from holoviews.plotting.links import RangeToolLink # 需要在这里导入
from model.timeseries_data import TimeSeriesData
from model.data_container import DataContainer # 用于类型提示
from .registry import VISUALIZERS, register_service
from typing import List, Tuple, Any # 导入 List
import pandas as pd # Import pandas
import traceback # 用于调试
from holoviews.operation.datashader import datashade
from holoviews.streams import RangeX
import datetime as dt # Import datetime
import param # For reactive programming if needed

# Helper class to bridge HoloViews stream and Panel parameter
class PlotStateManager(param.Parameterized):
    current_x_range = param.Tuple(default=None, length=2, precedence=-1)

    def __init__(self, range_x_stream, default_range, **params):
        super().__init__(**params)
        self.default_range = default_range
        # Initialize with default
        self.current_x_range = default_range
        # Link the HoloViews stream to update our parameter
        # Use watch=True for continuous updates might be better? Or .param.watch?
        # Using .param.watch seems more standard for stream parameters
        range_x_stream.param.watch(self._update_x_range, 'x_range')

    # Callback function for the watcher
    def _update_x_range(self, event):
        new_range = event.new
        # Ensure it's a tuple before setting
        if isinstance(new_range, tuple) and len(new_range) == 2:
            self.current_x_range = new_range
        elif self.current_x_range != self.default_range: # Avoid loops if already default
            # Reset to default if the new value is invalid or None
             self.current_x_range = self.default_range

def plot_timeseries_linked_view(
    data_containers: List[TimeSeriesData], # 接收列表
    width: int = 1500,
    # height is now internal logic, defined per plot
) -> hv.Layout: # 返回最终布局
    """
    为多个 TimeSeriesData 对象创建带联动缩略图的垂直布局视图。
    使用 hvplot 的 subplots=True 和 by 参数生成主图，利用其内置轴联动。

    Args:
        data_containers: 包含时间序列数据的 TimeSeriesData 对象列表。
        width: 整体图表宽度。

    Returns:
        一个包含所有主图子图和共享缩略图的 HoloViews Layout 对象。
        如果出错或无有效数据，返回一个空的 Layout 或包含错误信息的 Panel。
    """
    if not data_containers:
        return pn.pane.Alert("没有提供数据进行可视化。", alert_type='warning')

    dfs_to_combine = []
    valid_containers_for_minimap = []
    errors = []
    plot_height = 400
    minimap_height = 150
    category_col = 'data_source' # 用于 'by' 参数的列名

    # --- 1. 准备合并的 DataFrame --- #
    for data_container in data_containers:
        if not isinstance(data_container, TimeSeriesData):
            errors.append(f"跳过非时间序列数据: {data_container.name} (类型: {data_container.data_type})")
            continue

        series = data_container.series
        if series.empty:
            # 忽略空数据，避免影响 hvplot
            continue

        # 准备 DataFrame
        series.index.name = 'time'
        df = series.reset_index()
        value_col_name = 'value'
        if series.name:
            df = df.rename(columns={series.name: value_col_name})
        elif len(df.columns) == 2: # Assume time, value if no name
             df.columns = ['time', value_col_name]
        else:
             errors.append(f"无法确定 '{data_container.name}' 的值列，跳过。")
             continue

        # 添加类别列
        # 使用 name 作为类别，如果名称可能重复，考虑使用 id 或更唯一的标识符
        df[category_col] = data_container.name
        dfs_to_combine.append(df)

        # 收集第一个有效数据用于缩略图
        if not valid_containers_for_minimap:
            valid_containers_for_minimap.append(data_container)

    if not dfs_to_combine:
        error_message = "没有有效的可用于绘制图表的数据。"
        if errors:
            error_message += "\n详情:\n" + "\n".join(f"- {e}" for e in errors)
        return pn.pane.Alert(error_message, alert_type='danger')

    try:
        combined_df = pd.concat(dfs_to_combine, ignore_index=True)
    except Exception as e:
        errors.append(f"合并数据时出错: {e}")
        return pn.pane.Alert("合并数据失败。" + ("\n错误: " + str(e) if e else ""), alert_type='danger')

    # --- 2. 使用 subplots=True 和 by 参数绘制主图布局 --- #
    main_plots_layout = None
    try:
        # Remove fixed width and height, rely on responsive=True and sizing_mode
        main_plots_layout = combined_df.hvplot(
            x='time', y='value',
            by=category_col,
            subplots=True,
            rasterize=True,
            line_width=1,
            height=plot_height, # 每个子图的高度
            responsive=True, # Keep responsive
            shared_axes=True,
            legend=False,
            padding=(0.05, 0.1)
        ).cols(1)

        if not main_plots_layout:
             raise ValueError("hvplot 未能生成有效的子图布局。")

    except Exception as e:
         tb_str = traceback.format_exc()
         print(f"Error creating subplots:\\n{tb_str}")
         errors.append(f"创建主图子图时出错: {e}")
         # 如果主图失败，无法继续
         error_panel = pn.Column(*[pn.pane.Alert(e, alert_type='danger') for e in errors])
         return error_panel

    # --- 3. 创建并链接共享缩略图 (如果可能) --- #
    shared_minimap = None
    if valid_containers_for_minimap:
        try:
            # --- (缩略图创建逻辑保持不变) ---
            first_valid_container = valid_containers_for_minimap[0]
            series_map = first_valid_container.series
            series_map.index.name = 'time'
            df_minimap = series_map.reset_index()
            value_col_name_map = 'value'
            if series_map.name:
                df_minimap = df_minimap.rename(columns={series_map.name: value_col_name_map})
            elif len(df_minimap.columns) == 2:
                df_minimap.columns = ['time', value_col_name_map]
            else:
                raise ValueError("无法确定缩略图的值列")

            # Remove fixed width and height for minimap as well
            shared_minimap = df_minimap.hvplot(x="time", y=value_col_name_map,
                                             rasterize=True,
                                             height=minimap_height,
                                             responsive=True, padding=(0, 0.1), colorbar=False,
                                             color='darkgrey', line_width=1
                                             ).opts(toolbar=None, title='', yticks=None)
            # --- (结束：缩略图创建逻辑) ---

            # --- 链接缩略图到每个子图 --- #
            # 需要迭代 main_plots_layout 中的实际图表对象
            if isinstance(main_plots_layout, hv.Layout):
                 # 如果 hvplot 返回 Layout, 迭代其中的元素
                 for subplot in main_plots_layout:
                     if hasattr(subplot, 'main'): # NdOverlay structure? Access .main
                         plot_obj = subplot.main
                     else:
                         plot_obj = subplot
                     # 确保链接到有效的 DynamicMap 或 Curve
                     if isinstance(plot_obj, (hv.DynamicMap, hv.Curve)):
                          RangeToolLink(shared_minimap, plot_obj, axes=["x"])
                     else:
                          print(f"警告：无法将 RangeToolLink 应用于类型 {type(plot_obj)}")
            elif isinstance(main_plots_layout, (hv.DynamicMap, hv.Curve)):
                 # 如果 hvplot 只返回单个图 (例如只有一个类别时)
                 RangeToolLink(shared_minimap, main_plots_layout, axes=["x"])
            else:
                print(f"警告：未知的 main_plots_layout 类型 {type(main_plots_layout)}，无法应用 RangeToolLink。")

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error creating or linking minimap:\\n{tb_str}")
            errors.append(f"创建或链接导航缩略图时出错: {e}")
            # 即使缩略图/链接失败，也要尝试返回主图布局

    # --- 4. 组合最终布局 --- #
    if shared_minimap:
        # 确保主图布局不是 None
        # final_layout = (main_plots_layout + shared_minimap).opts(shared_axes=False).cols(1)
        final_layout = (main_plots_layout + shared_minimap).opts().cols(1)
    else:
        final_layout = main_plots_layout # 如果无缩略图，只返回主图布局

    # --- 5. 如果过程中有错误，附加错误信息 ---
    if errors:
        error_panel = pn.Column(*[pn.pane.Alert(e, alert_type='warning') for e in errors])
        # 如果 final_layout 有效，将错误和图表一起显示
        if final_layout:
             return pn.Column(error_panel, final_layout)
        else: # 如果连主图布局都没有，只显示错误
             return error_panel
    else:
        return final_layout # 返回最终的、可能包含缩略图的布局


# 注册新的"智能"服务
register_service(
    registry=VISUALIZERS,
    name="Plot Linked Time Series View", # 新名称
    function=plot_timeseries_linked_view, # 指向新函数
    input_type=List[TimeSeriesData], # 表明接受列表 (类型提示用)
    # 可以添加一个自定义标志，如果注册表系统支持的话，例如: accepts_list=True
    output_type=hv.Layout, # 输出是最终布局
    params_spec={
        # 只保留对整体视图有意义的参数
        # 'width' is handled by responsive=True inside the function now
        # 'height' is handled internally per plot type
    }
)

# --- MODIFIED: Service for Dynamic Rasterized Time Series Exploration WITH MINIMAP (Following Docs) --- #

def plot_timeseries_dynamic_rasterized(
    data_container: TimeSeriesData,
    width: int = 1500,
    height: int = 500,
    minimap_height: int = 100,
    line_width: float = 1, # Both plots use line_width
    cmap: list = ['darkblue'] # Pass cmap to hvplot
) -> hv.Layout:
    """
    为单个 TimeSeriesData 创建带导航缩略图的动态栅格化视图 (更接近 hvPlot 文档示例)。
    """
    if not isinstance(data_container, TimeSeriesData):
        raise TypeError("输入必须是 TimeSeriesData 对象")

    series = data_container.series
    if series.empty:
         return hv.Layout([]).opts(title=f"{data_container.name} (空)")

    # Prepare DataFrame
    series.index.name = 'time'
    df = series.reset_index()
    value_col_name = 'value'
    if series.name:
        df = df.rename(columns={series.name: value_col_name})
    else:
        if len(df.columns) == 2:
             df.columns = ['time', value_col_name]
        else:
             raise ValueError(f"无法确定 '{data_container.name}' 的值列。")

    # --- Create Main Plot using hvplot(rasterize=True) --- #
    main_plot = df.hvplot(x='time', y=value_col_name,
                             rasterize=True,
                            #  downsample=True,
                             resample_when=2000,
                             height=height,
                             responsive=True, # Add responsive
                             line_width=line_width,
                             cmap=cmap,
                             colorbar=False # Explicitly disable colorbar for main plot too
                             ).opts(
        show_grid=True,
            backend_opts={
            "x_range.bounds": (df['time'].min(), df['time'].max()),
            # Restore y_range.bounds
            "y_range.bounds": (df[value_col_name].min(), df[value_col_name].max())
        }
    )

    # --- Create Minimap --- #
    minimap = df.hvplot(x='time', y=value_col_name,
                        height=minimap_height,
                        rasterize=True,
                        # downsample=True,
                        responsive=True, # Add responsive
                        shared_axes=False,
                        colorbar=False,
                        line_width=line_width,
                        padding=(0, 0.1),
                        cmap=cmap).opts(toolbar='disable', height=minimap_height)
        
    link = RangeToolLink(minimap, main_plot, axes=["x", "y"])
    
    # Layout
    layout = (main_plot + minimap).cols(1)

    return layout

# Register the updated dynamic service (output type is still Layout)
# Params spec might need adjustment if cmap is configurable
register_service(
    registry=VISUALIZERS,
    name="Plot Time Series (Dynamic Rasterized)",
    function=plot_timeseries_dynamic_rasterized,
    input_type=TimeSeriesData,
    output_type=hv.Layout,
    params_spec={
        'height': {'type': 'integer', 'label': '主图高度', 'default': 500},
        'minimap_height': {'type': 'integer', 'label': '导航图高度', 'default': 100},
        'line_width': {'type': 'float', 'label': '线宽', 'default': 1},
        # Consider adding cmap if needed
    }
)

# --- REFACTORING with @pn.depends: Service returns pn.layout.Panel --- #

def plot_timeseries_complex_layout(
    data_container: TimeSeriesData,
    line_width: float = 1,
    cmap: list = ['darkblue']
) -> pn.layout.Panel:
    """
    创建包含全局预览、日期滑块、区域导航和细节聚焦视图的 Panel 布局。
    区域导航图的 X 轴范围由日期滑块动态控制，但不筛选数据。
    """
    if not isinstance(data_container, TimeSeriesData):
        raise TypeError("输入必须是 TimeSeriesData 对象")

    series = data_container.series
    if series.empty:
        return pn.pane.Alert(f"{data_container.name} (空数据)", alert_type='warning')

    # Prepare DataFrame
    series.index.name = 'time'
    df = series.reset_index()
    value_col_name = 'value'
    if series.name:
        df = df.rename(columns={series.name: value_col_name})
    else:
        if len(df.columns) == 2:
            df.columns = ['time', value_col_name]
        else:
            raise ValueError(f"无法确定 '{data_container.name}' 的值列。")

    min_date = df['time'].min()
    max_date = df['time'].max()
    # --- Calculate full value range for bounds --- #
    if not df.empty and value_col_name in df.columns:
        min_val = df[value_col_name].min()
        max_val = df[value_col_name].max()
    else:
        min_val, max_val = None, None # Handle case of empty df or missing column

    # --- 1. 全局预览图 (Static) ---
    global_preview = df.hvplot(
        x='time', y=value_col_name,
        rasterize=True,
        responsive=True, sizing_mode='stretch_width',
        height=150,
        shared_axes=False,
        line_width=line_width,
        cmap=cmap,
        colorbar=False,
    ).opts(
        toolbar='disable',
        yticks=None, ylabel=None,
        xticks=None, xlabel=None,
    )

    # --- 2. 日期范围滑块 (Control Widget) ---
    date_slider = pn.widgets.DateRangeSlider(
        name='选择时间范围',
        start=min_date,
        end=max_date,
        value=(min_date, max_date),
        step=1,
        sizing_mode='stretch_width',
        margin=0
    )

    # --- 3. 创建交互式区域导航图 (通过 .interactive().pipe() 筛选数据) --- #

    # 定义用于 pipe 的筛选函数
    def filter_dataframe_by_date_range(df_to_filter, date_range):
        print(f"Interactive pipe: Filtering DF for range: {date_range}") # Debug print
        start_date, end_date = date_range
        # Handle potential None or NaT (though slider usually provides dates)
        if start_date is None: start_date = df_to_filter['time'].min().date() # Fallback
        if end_date is None: end_date = df_to_filter['time'].max().date() # Fallback

        try:
            # --- Convert date objects to Timestamps for comparison --- #
            # Convert start_date to Timestamp (start of the day)
            start_ts = pd.Timestamp(start_date)
            # Convert end_date to Timestamp (end of the day for inclusive range)
            # Add one day and subtract a nanosecond, or set time to 23:59:59.999... to include the whole end day
            end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
            # Alternative: end_ts = pd.Timestamp(end_date, hour=23, minute=59, second=59, microsecond=999999, nanosecond=999)

            print(f"Converted Timestamps for comparison: {start_ts} to {end_ts}")

            # Ensure start is not after end after conversion
            if start_ts > end_ts:
                start_ts = end_ts # Adjust if slider gives inverted range somehow

            # --- Perform filtering using Timestamps --- #
            filtered = df_to_filter[
                (df_to_filter['time'] >= start_ts) & (df_to_filter['time'] <= end_ts)
            ]

            if filtered.empty:
                print("Filtering resulted in empty DataFrame")
                # Return an empty DataFrame with correct columns
                return pd.DataFrame(columns=df_to_filter.columns)
            return filtered
        except Exception as e:
            print(f"Error during filtering/conversion in pipe: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for detailed error info
            return pd.DataFrame(columns=df_to_filter.columns) # Return empty on error

    # 创建交互式绘图对象
    # 注意：部件 (date_slider) 会被 .interactive() 自动管理并显示
    # 如果不希望自动显示，需要更复杂的布局控制 (interactive.widgets() / interactive.panel())
    # 这里我们先用简单的方式，让它自动处理
    interactive_area_nav = df.interactive(sizing_mode='stretch_width').pipe(
        filter_dataframe_by_date_range,
        date_range=date_slider # 将滑块的值绑定到函数的 date_range 参数
    ).hvplot(
        x='time', y=value_col_name,
        rasterize=True, height=400, responsive=True,
        shared_axes=False,
        line_width=line_width, cmap=cmap, colorbar=False
    ).opts(
        show_grid=True,
        tools=['hover'],
        # xlim 会自动根据筛选后的数据调整，无需手动设置
        title="区域导航 (交互式数据)",
        # --- Add backend_opts to set interaction bounds --- #
        backend_opts={
            # Set x-axis interaction bounds to the full data range
            "x_range.bounds": (min_date, max_date),
            # Set y-axis interaction bounds to the full data range
            "y_range.bounds": (min_val, max_val) if min_val is not None else None
        }
    )

    # --- 4. 细节聚焦图 (Static - Shows Full Data) ---
    # This plot remains static, showing the full dataset for context
    detail_view_plot = df.hvplot(
        x='time', y=value_col_name,
        rasterize=True,
        width=400, height=400, sizing_mode='fixed',
        shared_axes=False, # Keep independent axes
        line_width=line_width, cmap=cmap, colorbar=False
    ).opts(
        show_grid=True,
        title="细节聚焦 (全数据)",
        # Set xlim to show the full range initially and keep it static
        xlim=(min_date, max_date)
    )

    # --- 5. Layout --- Build the desired structure explicitly
    # .interactive() 通常会自己管理部件布局，但我们可以尝试显式控制
    # 如果直接使用 interactive_area_nav，它可能包含滑块和图表
    # 为了保持之前的布局结构，我们只放入图表部分 (panel)
    # 注意：这可能需要 Panel 版本支持良好

    # plots_row = pn.Row(
    #     interactive_area_nav, # 这可能会包含滑块和图表
    #     detail_view_plot,
    #     sizing_mode='stretch_width'
    # )
    # final_layout = pn.Column(
    #     global_preview,
    #     # date_slider, # 可能被 interactive_area_nav 包含，暂时注释掉
    #     plots_row,
    #     sizing_mode='stretch_width'
    # )

    # --- 更精细的布局控制 (推荐) --- #
    # 分开获取部件和绘图面板
    area_nav_widgets = interactive_area_nav.widgets()
    area_nav_panel = interactive_area_nav.panel()

    plots_row = pn.Row(
        area_nav_panel, # 只放入绘图面板
        detail_view_plot,
        sizing_mode='stretch_width'
    )

    final_layout = pn.Column(
        global_preview,
        date_slider,      # 显式放回我们的滑块控件
        plots_row,
        sizing_mode='stretch_width'
    )


    return final_layout

# Register the service returning Panel layout
register_service(
    registry=VISUALIZERS,
    name="Plot Time Series (Complex Layout - Interactive Pipe)", # Updated name
    function=plot_timeseries_complex_layout,
    input_type=TimeSeriesData,
    output_type=pn.layout.Panel,
    params_spec={
        'line_width': {'type': 'float', 'label': '线宽', 'default': 1},
    }
)

# Keep other visualizers if they exist...