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
        # 注意：width 可能需要调整，或依赖 responsive
        # shared_axes=True 是 subplots 的默认行为，提供内部联动
        main_plots_layout = combined_df.hvplot(
            x='time', y='value',
            by=category_col,
            subplots=True,
            rasterize=True,
            line_width=1,
            width=width, # 每个子图的宽度，hvplot 会尝试适应
            height=plot_height, # 每个子图的高度
            responsive=True, # 让布局尝试响应式调整
            shared_axes=True, # 确保轴联动（默认）
            legend=False, # 通常子图标题已足够，隐藏图例
            padding=(0.05, 0.1) # 添加一些内边距
        ).cols(1) # 强制单列垂直布局

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

            shared_minimap = df_minimap.hvplot(x="time", y=value_col_name_map,
                                             rasterize=True,
                                             min_width=width, height=minimap_height,
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
    base_main_plot = df.hvplot(x='time', y=value_col_name,
                             rasterize=True,
                             width=width, height=height,
                             line_width=line_width,
                             cmap=cmap,
                             colorbar=False # Explicitly disable colorbar for main plot too
                             )

    # Apply opts to the main plot, including range bounds and NO autorange
    main_plot = base_main_plot.opts(
            title=data_container.name,
        show_grid=True,
        # Remove autorange='y' as y-axis will be linked
            backend_opts={
            "x_range.bounds": (df['time'].min(), df['time'].max()),
            # Restore y_range.bounds
            "y_range.bounds": (df[value_col_name].min() - df[value_col_name].std()*0.1, df[value_col_name].max() + df[value_col_name].std()*0.1)
        }
    )

    # --- Create Minimap Plot (using rasterize=True, similar to docs) --- #
    base_minimap = df.hvplot(x="time", y=value_col_name,
                           height=minimap_height, width=width,
                           responsive=False,
                           rasterize=True, # Use rasterize for minimap as in docs
                           padding=(0, 0.1),
                           line_width=line_width, # Match line width potentially
                           color='darkgrey', # Use a distinct color for minimap
                           colorbar=False)
    # Disable toolbar for minimap
    minimap_plot = base_minimap.opts(toolbar=None, default_tools=[]) # Remove yticks=None, title='' for now

    # --- Link Main Plot and Minimap (linking X and Y as in docs) --- #
    range_link = RangeToolLink(minimap_plot, main_plot, axes=["x", "y"])

    # --- Combine into Layout (remains the same) --- #
    final_layout = (main_plot + minimap_plot).opts(shared_axes=False).cols(1)

    return final_layout

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

# Keep other visualizers if they exist...