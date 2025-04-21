import pandas as pd
from model.timeseries_container import TimeSeriesContainer
# Import from parent directory registry
from ..registry import PREPROCESSORS, register_service
from typing import List, Dict, Any, Optional

def moving_average(
    data_container: TimeSeriesContainer,
    window: int,
    center: bool = False
) -> TimeSeriesContainer:
    """计算单列时间序列的滑动平均值。

    Args:
        data_container (TimeSeriesContainer): 包含原始单列时间序列数据的容器。
                                            其内部数据必须是 pd.Series。
        window (int): 滑动窗口的大小 (必须是正整数)。
        center (bool): 是否将窗口标签设置在窗口中间。
                       False (默认) 表示标签在窗口右侧。

    Returns:
        TimeSeriesContainer: 一个新的容器，包含计算得到的滑动平均序列。
                           结果序列的名称将在原名称基础上添加后缀。

    Raises:
        TypeError: 如果输入不是 TimeSeriesContainer 或包含多维数据 (DataFrame)。
        ValueError: 如果 window 不是正整数或大于序列长度。
        RuntimeError: 如果 pandas 计算过程中发生错误。
    """
    # --- 输入验证 ---
    if not isinstance(data_container, TimeSeriesContainer):
        raise TypeError("输入数据必须是 TimeSeriesContainer 类型。")
    if data_container.is_multidim:
        raise TypeError("滑动平均目前仅支持单列时间序列 (Series)，不支持多列 (DataFrame)。")

    series = data_container.series
    assert series is not None, "内部错误：is_multidim=False 但 series is None"

    if not isinstance(window, int) or window <= 0:
        raise ValueError("滑动窗口大小 (window) 必须是正整数。")

    # --- 处理特殊情况：窗口过大或序列为空 ---
    if window > len(series):
        raise ValueError(f"窗口大小 ({window}) 不能大于序列长度 ({len(series)})。")

    if series.empty:
         print(f"警告: 输入序列 '{data_container.name}' 为空，无法计算滑动平均。返回空结果。")
         empty_series = pd.Series([], index=pd.DatetimeIndex([]), dtype=series.dtype, name=series.name)
         return TimeSeriesContainer(
             data=empty_series,
             name=f"{data_container.name}_MA{window}_empty",
             source_ids=[data_container.id],
             operation_info={'name': 'moving_average_empty', 'params': {'window': window, 'center': center}}
         )

    # --- 执行计算 ---
    try:
        ma_series = series.rolling(window=window, center=center).mean().dropna()
    except Exception as e:
         raise RuntimeError(f"计算滑动平均时出错: {e}") from e

    # --- 创建并返回结果容器 ---
    new_name = f"{data_container.name}_MA{window}{'_centered' if center else ''}"

    if ma_series.name is None:
        ma_series.name = series.name

    return TimeSeriesContainer(
        data=ma_series,
        name=new_name,
        source_ids=[data_container.id],
        operation_info={'name': 'moving_average', 'params': {'window': window, 'center': center}}
    )

# --- 服务注册：滑动平均 ---
register_service(
    registry=PREPROCESSORS,
    name="滑动平均 (Moving Average)",
    function=moving_average,
    input_type=TimeSeriesContainer,
    output_type=TimeSeriesContainer,
    params_spec={
        'window': {'type': 'integer', 'label': '窗口大小', 'default': 5, 'min': 1},
        'center': {'type': 'boolean', 'label': '中心对齐', 'default': False}
    },
    accepts_list=False,
    input_param_name='data_container'
) 