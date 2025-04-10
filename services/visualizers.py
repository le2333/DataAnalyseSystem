import panel as pn
import holoviews as hv
import hvplot.pandas # 确保导入了 hvplot 扩展
import datashader as ds
from holoviews.operation.datashader import datashade, rasterize
from holoviews.plotting.links import RangeToolLink
from model.timeseries_data import TimeSeriesData
from model.data_container import DataContainer # 用于类型提示
from .registry import VISUALIZERS, register_service
from typing import Optional, Tuple, Any

def plot_timeseries(
    data_container: TimeSeriesData,
    use_datashader: Optional[bool] = None,
    add_minimap: bool = True,
    width: int = 800,
    height: int = 400,
    minimap_height: int = 100
) -> hv.Layout | hv.DynamicMap:
    """
    为 TimeSeriesData 对象创建交互式时间序列图。

    Args:
        data_container: 包含时间序列数据的 TimeSeriesData 对象。
        use_datashader: 是否强制使用 Datashader。如果为 None，则自动判断。
        add_minimap: 是否添加范围选择缩略图 (仅当使用 Datashader 时有效)。
        width: 主图宽度。
        height: 主图高度。
        minimap_height: 缩略图高度。

    Returns:
        一个 HoloViews 图表对象 (可能是 Layout 或 DynamicMap)。

    Raises:
        ValueError: 如果输入不是 TimeSeriesData。
        TypeError: 如果数据格式不适合绘图。
    """
    if not isinstance(data_container, TimeSeriesData):
        raise ValueError("输入数据必须是 TimeSeriesData 类型。")

    series = data_container.series
    if series.empty:
        # 返回一个空图或提示信息可能比抛出错误更好
        return hv.Curve([]).opts(title=f"{data_container.name} (空)")

    # 决定是否使用 Datashader
    _use_ds = use_datashader
    if _use_ds is None:
        _use_ds = len(series) > 100_000 # 自动判断阈值

    # 准备绘图选项
    opts = hv.opts.Curve(width=width, height=height, tools=['hover'],
                         xlabel="时间", ylabel=series.name or "值",
                         title=data_container.name, show_grid=True)
    if _use_ds:
        opts = hv.opts.RGB(width=width, height=height, tools=['hover'],
                           xlabel="时间", ylabel=series.name or "值",
                           title=data_container.name, show_grid=True)

    # 创建主图
    if _use_ds:
        # 使用 datashade 创建动态图
        main_plot = datashade(hv.Curve(series), cmap="viridis").opts(opts)
    else:
        main_plot = hv.Curve(series).opts(opts)

    # 添加缩略图 (Minimap)
    if _use_ds and add_minimap:
        minimap_opts = hv.opts.Curve(width=width, height=minimap_height,
                                     yaxis=None, labelled=[], axiswise=True,
                                     toolbar=None, default_tools=[])
        # 对于 datashader 图，缩略图通常用普通 Curve 显示概览
        minimap = hv.Curve(series).opts(minimap_opts)
        # 链接主图和缩略图的范围
        RangeToolLink(minimap, main_plot)
        # 将主图和缩略图组合在布局中
        layout = (main_plot + minimap).cols(1)
        return layout
    else:
        # 如果不使用 Datashader 或不添加缩略图，只返回主图
        return main_plot

# 注册可视化服务
register_service(
    registry=VISUALIZERS,
    name="Plot Time Series",
    function=plot_timeseries,
    input_type=TimeSeriesData,
    output_type=hv.Layout | hv.DynamicMap, # 输出是 HoloViews 对象
    params_spec={
        'use_datashader': {'type': 'boolean', 'label': '使用 Datashader', 'default': None}, # None 表示自动
        'add_minimap': {'type': 'boolean', 'label': '显示缩略图', 'default': True},
        'width': {'type': 'integer', 'label': '图表宽度', 'default': 800},
        'height': {'type': 'integer', 'label': '图表高度', 'default': 400},
    }
) 