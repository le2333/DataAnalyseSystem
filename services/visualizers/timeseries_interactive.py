import panel as pn
import holoviews as hv
import hvplot.pandas # noqa: F401 - 确保导入 hvplot 扩展
# from model.data_container import DataContainer # 不直接使用基类
from model.timeseries_container import TimeSeriesContainer # 明确使用 TimeSeriesContainer
from ..registry import VISUALIZERS, register_service # 调整导入路径
from typing import Tuple, Optional, Any, Union
import pandas as pd
import datetime as dt
from holoviews import streams

# === 辅助函数 ===

def _safe_min_max(series: pd.Series) -> Tuple[Optional[Any], Optional[Any]]:
    """安全地获取 Pandas Series 的最小值和最大值。

    处理空 Series、全为 NaN/NaT 的 Series 或包含无法比较类型的 Series。

    Args:
        series: 输入的 Pandas Series。

    Returns:
        包含 (min, max) 的元组。如果无法获取有效范围，则返回 (None, None)。
    """
    if series.empty or series.isnull().all():
        return None, None
    try:
        return series.min(), series.max()
    except TypeError:
        print(f"警告: 无法安全地获取 Series '{series.name}' 的 min/max (可能是类型错误或包含 NaT)。")
        return None, None

def _dates_to_xlim(
    date_range: Optional[Tuple[Optional[dt.date], Optional[dt.date]]]
) -> Optional[Tuple[pd.Timestamp, pd.Timestamp]]:
    """将日期范围元组转换为适用于 HoloViews xlim 的时间戳元组。

    Args:
        date_range: 一个包含两个日期对象 (或 None) 的元组，通常来自 DateRangeSlider。

    Returns:
        一个包含 (开始时间戳, 结束时间戳) 的元组，结束时间戳设置为当天结束。
        如果输入无效或转换失败，则返回 None。
    """
    if date_range is None:
        return None

    start_date, end_date = date_range
    # 必须同时有开始和结束日期
    if start_date is None or end_date is None:
        return None

    try:
        # 确保输入是 date 对象，如果是 datetime 则取 date 部分
        if isinstance(start_date, dt.datetime):
             start_date = start_date.date()
        if isinstance(end_date, dt.datetime):
             end_date = end_date.date()
             
        # 转换为 Pandas Timestamp 对象
        start_ts = pd.Timestamp(start_date)
        # 将结束时间戳设为当天的最后一微秒，以确保包含结束日期当天的数据
        end_ts = pd.Timestamp(end_date) + pd.Timedelta(days=1, microseconds=-1)

        # 确保 start <= end
        if start_ts > end_ts:
            print(f"警告: 日期范围起始 {start_ts} 大于结束 {end_ts}，已自动交换。")
            return end_ts, start_ts # 交换顺序
        else:
            return start_ts, end_ts
    except Exception as e:
        print(f"错误: 转换日期范围 {date_range} 为时间戳时出错: {e}")
        return None

# === 可视化服务 ===

def plot_timeseries_complex_layout(
    data_container: TimeSeriesContainer, # 输入必须是 TimeSeriesContainer
    line_width: float = 1.0,
    cmap: Optional[List[str]] = None # 允许 cmap 为 None 或列表
) -> Union[pn.layout.Panel, pn.pane.Alert]:
    """创建包含全局预览、日期滑块、局部导航和细节聚焦视图的交互式布局。

    用于探索单列时间序列数据。

    - 全局预览: 显示整个时间序列的静态概览 (rasterized)。
    - 日期滑块: 控制下方两个图表的默认时间范围。
    - 局部导航图: 显示由滑块确定的时间范围内的概览 (rasterized)，
                   允许用户在此图上通过框选放大。
    - 细节聚焦图: 显示由局部导航图框选或滑块确定的详细区域 (rasterized)。

    Args:
        data_container (TimeSeriesContainer): 包含单列时间序列数据的容器。
        line_width (float): 图表线条宽度。
        cmap (Optional[List[str]]): 图表颜色映射列表 (例如 ['blue', 'red'])。
                                   如果为 None，使用 hvplot 默认颜色。

    Returns:
        Union[pn.layout.Panel, pn.pane.Alert]: 
            一个 Panel 布局对象，包含交互式图表。
            如果在数据准备阶段发生严重错误，则返回一个 Panel Alert。
            动态图表函数内部的错误也会尝试返回 Alert。
    """
    # --- 1. 输入验证和数据准备 ---
    if not isinstance(data_container, TimeSeriesContainer):
        # 类型提示应阻止此情况，但作为防御性检查
        return pn.pane.Alert("输入错误：期望 TimeSeriesContainer 对象。", alert_type='danger')
    if data_container.is_multidim:
         return pn.pane.Alert(f"输入错误：此可视化仅支持单列时间序列，'{data_container.name}' 是多维的。", alert_type='danger')
    
    series = data_container.series # 获取内部 Series
    if series is None: # 进一步检查
         return pn.pane.Alert(f"内部错误：无法从 '{data_container.name}' 获取 Series 数据。", alert_type='danger')
    if series.empty:
        return pn.pane.Alert(f"数据 '{data_container.name}' 为空，无法生成可视化。", alert_type='warning')

    try:
        # 确保索引是 DatetimeIndex 并命名为 'time'
        series_processed = series.copy()
        if not isinstance(series_processed.index, pd.DatetimeIndex):
            # TimeSeriesContainer 的 __init__ 应该已确保这一点，但再次检查
            print(f"警告：输入序列 '{data_container.name}' 索引非 DatetimeIndex，尝试转换。")
            series_processed.index = pd.to_datetime(series_processed.index, errors='raise')
            series_processed = series_processed.sort_index()
        series_processed.index.name = 'time'
        
        # 将 Series 转换为 hvplot 需要的 DataFrame (重置索引使 'time' 成为列)
        df = series_processed.reset_index()
        value_col_name = 'value' # 定义值列的名称
        # 重命名数据列为 'value'
        if series_processed.name and series_processed.name != 'time':
            df = df.rename(columns={series_processed.name: value_col_name})
        elif len(df.columns) == 2: # 假设第二列是数据
            df.columns = ['time', value_col_name]
        else:
            # 如果无法确定值列（例如，转换后列数不为2且原始name为None或time）
            raise ValueError(f"无法从 Series '{data_container.name}' 确定值列。可用列: {list(df.columns)}")

        # 安全地获取时间和值的完整范围
        min_date_ts, max_date_ts = _safe_min_max(df['time'])
        min_val, max_val = _safe_min_max(df[value_col_name])

        if min_date_ts is None or max_date_ts is None:
            raise ValueError("无法确定有效的时间范围 (min/max date)。")
        
        # 如果值范围无效 (例如全 NaN)，打印警告，让 HoloViews 自动处理 Y 轴范围
        if min_val is None or max_val is None:
             print(f"警告: 无法确定 '{data_container.name}' 的有效值范围 (min/max value)。将由 HoloViews 自动确定 Y 轴。")
             # 将 min_val, max_val 保持为 None

        # 用于日期滑块的范围 (date 对象)
        min_date_slider = min_date_ts.date()
        max_date_slider = max_date_ts.date()
        
    except Exception as e:
        # 如果数据准备阶段出错，返回错误 Alert
        return pn.pane.Alert(f"准备数据 '{data_container.name}' 或计算范围时出错: {e}", alert_type='danger')

    # --- 2. 创建静态全局预览图 ---
    try:
        hvplot_opts_global = {
            'rasterize': True, 'responsive': True, 'sizing_mode': 'stretch_width',
            'height': 100, 'shared_axes': False, 'line_width': line_width,
            'cmap': cmap, 'colorbar': False, 'title': f"{data_container.name} - 全局预览"
        }
        global_preview = df.hvplot(x='time', y=value_col_name, **hvplot_opts_global)\
                           .opts(toolbar=None, yaxis=None, xaxis=None)
    except Exception as e:
         print(f"警告: 创建全局预览图失败: {e}")
         # 创建失败不阻止后续，但在布局中显示警告信息
         global_preview = pn.pane.Alert(f"创建全局预览失败: {e}", alert_type='warning', sizing_mode='stretch_width')

    # --- 3. 创建日期范围滑块 --- 
    try:
        date_slider = pn.widgets.DateRangeSlider(
            name='时间范围选择',
            start=min_date_slider,
            end=max_date_slider,
            value=(min_date_slider, max_date_slider),
            sizing_mode='stretch_width',
            margin=(5, 10) # 上下边距5，左右边距10
        )
    except Exception as e:
        # 滑块创建失败是严重问题
        return pn.pane.Alert(f"创建日期滑块失败: {e}", alert_type='danger')

    # --- 4. 创建 HoloViews 框选流 --- 
    selection_stream = streams.BoundsXY(bounds=None)

    # --- 5. 定义动态局部导航图创建函数 --- 
    # 使用 @pn.depends 装饰器，使函数在滑块值变化时重新执行
    @pn.depends(date_range=date_slider.param.value)
    def create_area_nav(date_range):
        """动态创建局部导航图，其 X 轴范围由日期滑块控制。"""
        # 将滑块的日期范围转换为绘图所需的时间戳范围
        current_xlim = _dates_to_xlim(date_range)
        # 如果转换失败或滑块范围无效，使用数据的完整时间范围
        if current_xlim is None:
             current_xlim = (min_date_ts, max_date_ts)

        try:
            # 定义导航图的 hvplot 选项
            hvplot_opts_nav = {
                'rasterize': True, 'responsive': True, 'sizing_mode': 'stretch_width',
                'height': 350, 'shared_axes': False, 'line_width': line_width,
                'cmap': cmap, 'colorbar': False, 'tools': ['hover', 'box_select']
            }
            # 定义 .opts 选项
            opts_nav = {
                'show_grid': True, 'title': "局部导航 (框选 -> 更新细节图)",
                'xlim': current_xlim,
                'ylim': (min_val, max_val) if min_val is not None else None # Y轴使用完整范围或自动
            }
            # 创建绘图对象
            area_nav_plot = df.hvplot(x='time', y=value_col_name, **hvplot_opts_nav).opts(**opts_nav)
            
            # 将框选流 (selection_stream) 的源设置为此导航图
            selection_stream.source = area_nav_plot
            return area_nav_plot
        except Exception as e:
             # 如果动态创建导航图失败，返回错误 Alert
             print(f"错误: 创建局部导航图失败 (范围: {current_xlim}): {e}")
             return pn.pane.Alert(f"创建局部导航图失败: {e}", alert_type='danger', sizing_mode='stretch_width')

    # --- 6. 定义动态细节聚焦图创建函数 --- 
    # 使用 @pn.depends 装饰器，使函数在框选流的 bounds 变化时重新执行
    @pn.depends(bounds=selection_stream.param.bounds)
    def create_dynamic_detail_view(bounds):
        """动态创建细节聚焦图，其 X/Y 轴范围由框选或滑块控制。"""
        # 默认范围由日期滑块决定 X 轴，Y 轴为完整范围
        detail_xlim = _dates_to_xlim(date_slider.value) 
        detail_ylim = (min_val, max_val) if min_val is not None else None 
        title = "细节聚焦 (滑块范围)"

        # 如果有有效的框选范围 (bounds)
        if bounds and len(bounds) == 4:
            x_min_b, y_min_b, x_max_b, y_max_b = bounds
            try:
                # 尝试将 bounds 转换为时间戳和数值
                # bounds 的 X 值可能是毫秒时间戳 (来自 JS) 或其他可解析格式
                x_start_ts = pd.Timestamp(x_min_b, unit='ms') if isinstance(x_min_b, (int, float)) else pd.Timestamp(x_min_b)
                x_end_ts = pd.Timestamp(x_max_b, unit='ms') if isinstance(x_max_b, (int, float)) else pd.Timestamp(x_max_b)

                # 检查转换后的选区是否有效 (起始 < 结束)
                if x_start_ts < x_end_ts and y_min_b < y_max_b:
                    detail_xlim = (x_start_ts, x_end_ts)
                    detail_ylim = (y_min_b, y_max_b)
                    title = "细节聚焦 (选区范围)"
                else:
                    print(f"警告: 无效的框选范围 bounds={bounds} (起始不小于结束)。")
                    title = "细节聚焦 (滑块范围 - 无效选区)"
            except Exception as e:
                # 处理 bounds 转换错误
                print(f"警告: 处理选区 bounds={bounds} 时出错: {e}")
                title = "细节聚焦 (滑块范围 - Bounds 处理错误)"

        # 如果滑块范围转换失败，则使用完整时间范围作为回退
        if detail_xlim is None:
            detail_xlim = (min_date_ts, max_date_ts)
            title = "细节聚焦 (完整范围 - 滑块错误)"
            
        try:
            # 定义细节图的 hvplot 选项
            hvplot_opts_detail = {
                'rasterize': True, 'responsive': True, 'sizing_mode': 'stretch_width',
                'height': 350, 'shared_axes': False, 'line_width': line_width,
                'cmap': cmap, 'colorbar': False
            }
            # 定义 .opts 选项
            opts_detail = {
                'show_grid': True, 'xlim': detail_xlim, 'ylim': detail_ylim, 'title': title
            }
            # 创建绘图对象
            detail_plot = df.hvplot(x='time', y=value_col_name, **hvplot_opts_detail).opts(**opts_detail)
            return detail_plot
        except Exception as e:
             # 如果动态创建细节图失败，返回错误 Alert
             print(f"错误: 创建细节聚焦图失败 (xlim={detail_xlim}, ylim={detail_ylim}): {e}")
             return pn.pane.Alert(f"创建细节聚焦图失败: {e}", alert_type='danger', sizing_mode='stretch_width')

    # --- 7. 组装最终布局 --- 
    try:
        # 将两个动态图放入一行
        plots_row = pn.Row(
            create_area_nav,        # 直接传递依赖函数
            create_dynamic_detail_view, # 直接传递依赖函数
            sizing_mode='stretch_width'
        )

        # 将所有组件垂直排列
        final_layout = pn.Column(
            global_preview, # 可能是一个图，也可能是一个 Alert
            date_slider,
            plots_row,      # 包含两个动态图或其错误 Alert
            sizing_mode='stretch_width',
            name=f"交互式探索 - {data_container.name}"
        )
        return final_layout
    except Exception as e:
         # 如果最终布局组装失败
         print(f"错误: 组装最终布局面板时出错: {e}")
         return pn.pane.Alert(f"组装最终可视化布局失败: {e}", alert_type='danger')

# --- 服务注册 --- 
register_service(
    registry=VISUALIZERS,
    name="时序图-交互式缩放详情",
    function=plot_timeseries_complex_layout,
    input_type=TimeSeriesContainer, # 明确输入类型
    output_type=pn.layout.Panel, # 输出是一个 Panel 布局 (Column)
    params_spec={
        'line_width': {'type': 'float', 'label': '线宽', 'default': 1.0, 'min': 0.1, 'max': 10},
        # cmap 不适合作为简单参数，保持默认或未来通过高级配置
        # 'cmap': {'type': 'string', 'label': '颜色映射(列表)', 'default': '["darkblue"]'} # 字符串表示的列表?
    },
    accepts_list=False, # 这个服务处理单个输入
    input_param_name='data_container' # 函数期望的参数名
) 