import pandas as pd
from model.timeseries_data import TimeSeriesData
from model.multidim_data import MultiDimData
from model.data_container import DataContainer # For type hint
from .registry import PREPROCESSORS, register_service
from typing import List, Dict, Any, Optional

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

# --- 示例：一个简单的一维数据预处理器 --- #

def simple_moving_average(data_container: TimeSeriesData, window: int = 5) -> TimeSeriesData:
    """计算简单移动平均。"""
    if not isinstance(data_container, TimeSeriesData):
        raise ValueError("输入必须是 TimeSeriesData 类型")
    if window <= 0:
        raise ValueError("窗口大小必须为正整数")

    series = data_container.series
    smoothed_series = series.rolling(window=window, center=True, min_periods=1).mean()

    # 创建新的数据容器，继承源信息
    new_name = f"{data_container.name}_SMA{window}"
    operation_info = {'name': 'simple_moving_average', 'params': {'window': window}}
    return TimeSeriesData(smoothed_series, name=new_name,
                          source_ids=[data_container.id],
                          operation_info=operation_info)

register_service(
    registry=PREPROCESSORS,
    name="Simple Moving Average",
    function=simple_moving_average,
    input_type=TimeSeriesData,
    output_type=TimeSeriesData,
    params_spec={
        'window': {'type': 'integer', 'label': '窗口大小', 'default': 5}
    }
)

# --- 新增：合并服务 --- #

def merge_1d_to_multidim(
    data_containers: List[TimeSeriesData],
    new_multidim_name: str,
    # 可以添加更多参数，如对齐方式 ('inner', 'outer') 等
) -> MultiDimData:
    """
    将多个一维时间序列合并为一个多维 DataFrame。
    使用时间作为索引进行外部连接。
    """
    if not data_containers:
        raise ValueError("至少需要提供一个时间序列进行合并。")
    if not new_multidim_name:
         raise ValueError("必须为新的多维数据指定名称。")

    all_series = {}
    source_ids = []
    for dc in data_containers:
        if not isinstance(dc, TimeSeriesData):
            # 或者可以选择跳过非 TimeSeriesData
            raise ValueError("所有输入数据都必须是 TimeSeriesData 类型。")
        # 使用数据容器的 name 作为列名，如果重复可能需要处理
        # 更健壮的方式可能是允许用户指定列名映射
        col_name = dc.name
        count = 1
        while col_name in all_series:
            col_name = f"{dc.name}_{count}"
            count += 1
        all_series[col_name] = dc.series
        source_ids.append(dc.id)

    # 合并 Series 到 DataFrame，按时间索引对齐 (外部连接保留所有时间点)
    try:
        merged_df = pd.concat(all_series, axis=1, join='outer')
        merged_df.index.name = 'time' # 保持索引名称
    except Exception as e:
        raise RuntimeError(f"合并 Series 时出错: {e}")

    operation_info = {
        'name': 'merge_1d_to_multidim',
        'params': {'new_multidim_name': new_multidim_name}
        # 将来可以添加 'join_method' 等参数
    }
    return MultiDimData(merged_df, name=new_multidim_name,
                      source_ids=source_ids,
                      operation_info=operation_info)

# 注意：这个服务的调用方式与之前的单输入服务不同
# 控制器需要特殊处理来收集 data_containers 列表和 new_multidim_name 参数
register_service(
    registry=PREPROCESSORS,
    name="Merge 1D to MultiD",
    function=merge_1d_to_multidim,
    # input_type 可以用 List[TimeSeriesData] 更精确地描述
    # 但由于控制器仍需特殊逻辑来构建列表，保持 None 或用 accepts_list 更清晰
    input_type=None, # 保持 None，由 accepts_list 标志处理
    output_type=MultiDimData,
    params_spec={
        # new_multidim_name 需要从 UI 获取
        'new_multidim_name': {'type': 'string', 'label': '新多维数据名称', 'default': 'MergedData'}
        # 未来可以添加 'join_method': {'type': 'select', 'options': ['outer', 'inner'], ...}
    },
    accepts_list=True # Explicitly mark this service as accepting a list
)

# --- 可以添加更多预处理器 --- #
# def extract_features(data_container: TimeSeriesData, ...) -> MultiDimData: ...
# def scale_multidim(data_container: MultiDimData, ...) -> MultiDimData: ... 