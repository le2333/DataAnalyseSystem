import pandas as pd
from model.timeseries_data import TimeSeriesData
from .registry import PREPROCESSORS, register_service
from typing import Optional

def moving_average(
    data_container: TimeSeriesData,
    window: int,
    center: bool = False # 新增参数：是否中心对齐
) -> TimeSeriesData:
    """
    计算时间序列的滑动平均值。

    Args:
        data_container: 包含原始时间序列的 TimeSeriesData 对象。
        window: 滑动窗口的大小 (整数)。
        center: 是否将标签设置在窗口中间 (False 表示设置在窗口右侧)。

    Returns:
        一个新的 TimeSeriesData 对象，包含滑动平均结果。

    Raises:
        ValueError: 如果 window 不是正整数或大于序列长度。
        TypeError: 如果输入不是 TimeSeriesData。
    """
    if not isinstance(data_container, TimeSeriesData):
        raise TypeError("输入数据必须是 TimeSeriesData 类型。")
    if not isinstance(window, int) or window <= 0:
        raise ValueError("窗口大小 (window) 必须是正整数。")
    
    series = data_container.series
    if window > len(series):
        raise ValueError(f"窗口大小 ({window}) 不能大于序列长度 ({len(series)})。")

    # 计算滑动平均，保留原始索引，丢弃因窗口产生的 NaN 值
    ma_series = series.rolling(window=window, center=center).mean().dropna()

    # 创建新的 TimeSeriesData 对象
    # 新名称可以基于原名称和操作
    new_name = f"{data_container.name}_MA{window}{'_centered' if center else ''}"
    
    # 设置新 Series 的名称属性，用于后续绘图等
    ma_series.name = series.name # 保留原始数据列的含义

    # source_ids 和 operation_info 将由 Controller 在调用后设置
    return TimeSeriesData(data=ma_series, name=new_name)

# 注册滑动平均服务
register_service(
    registry=PREPROCESSORS,
    name="Moving Average",
    function=moving_average,
    input_type=TimeSeriesData,
    output_type=TimeSeriesData,
    params_spec={
        'window': {'type': 'integer', 'label': '窗口大小', 'default': 5},
        'center': {'type': 'boolean', 'label': '中心对齐', 'default': False}
    }
)

# 可以在这里添加更多的预处理函数并注册...
# def another_preprocessor(...):
#     ...
# register_service(PREPROCESSORS, "Another Preprocessor", ...) 