import pandas as pd
import os
from model.timeseries_data import TimeSeriesData
from .registry import STRUCTURERS, register_service
from typing import Optional

def structure_df_to_timeseries(
    input_df: pd.DataFrame,
    time_column_name: str,
    data_column_name: Optional[str] = None,
    base_name_for_naming: str = "structured",
    name_prefix: str = "Structured"
) -> TimeSeriesData:
    """
    将输入的 DataFrame 结构化为 TimeSeriesData 对象。

    Args:
        input_df: 包含数据的 Pandas DataFrame。
        time_column_name: 作为时间索引的列名。
        data_column_name: (可选) 要加载的数据列名。如果为 None，尝试使用第一列非时间列。
        base_name_for_naming: 用于构成最终对象名称的基础部分（通常来自文件名）。
        name_prefix: 新创建的 TimeSeriesData 对象的名称前缀。

    Returns:
        一个 TimeSeriesData 对象。

    Raises:
        ValueError: 如果时间列或数据列无效，或无法结构化数据。
    """
    # 复制一份以避免修改原始 DF
    df = input_df.copy()

    if time_column_name not in df.columns:
         raise ValueError(f"时间列 '{time_column_name}' 不在 DataFrame 中。")

    # 将时间列设为索引
    df = df.set_index(time_column_name)
    if not isinstance(df.index, pd.DatetimeIndex):
         try:
             # 确保在转换前是 datetime 类型（read_csv 时已 parse_dates）
             # df[time_column_name] = pd.to_datetime(df[time_column_name], errors='coerce')
             # df = df.dropna(subset=[time_column_name])
             # df = df.set_index(time_column_name)
             
             # 如果索引不是 datetime，尝试转换索引
             df.index = pd.to_datetime(df.index, errors='coerce')
             df = df.dropna(axis=0, subset=[df.index.name])
             if not isinstance(df.index, pd.DatetimeIndex):
                  raise TypeError()
         except (TypeError, ValueError) as e:
              raise ValueError(f"列 '{time_column_name}' 或其索引未能成功解析/转换成时间索引: {e}")

    # 选择数据列
    if data_column_name:
        if data_column_name not in df.columns:
            raise ValueError(f"数据列 '{data_column_name}' 不在 DataFrame 中。")
        series = df[data_column_name]
    else:
        if df.columns.empty:
             raise ValueError("DataFrame 除了时间索引外没有其他数据列。")
        actual_data_col_name = df.columns[0]
        series = df[actual_data_col_name]

    # 确保 series 是 pd.Series
    if not isinstance(series, pd.Series):
        if isinstance(series, pd.DataFrame) and len(series.columns) == 1:
            series = series.iloc[:, 0]
        else:
            raise ValueError("未能提取有效的单列时间序列数据。")
    
    # 确保列名在 Series 上
    if series.name is None and 'actual_data_col_name' in locals():
        series.name = actual_data_col_name
    elif series.name is None and data_column_name:
         series.name = data_column_name
    elif series.name is None: # 如果都没有，给个默认名
        series.name = 'data'

    # 创建 TimeSeriesData 对象，使用实际列名
    data_name = f"{name_prefix}_{base_name_for_naming}_{series.name}"

    series = series.sort_index()

    return TimeSeriesData(data=series, name=data_name)

# 注册数据结构化服务
register_service(
    registry=STRUCTURERS,
    name="Structure DataFrame to Time Series",
    function=structure_df_to_timeseries,
    input_type=pd.DataFrame, # 输入是 DataFrame
    output_type=TimeSeriesData,
    params_spec={ # 参数是控制器从 UI 获取并传递的
        # 'input_df' 不在这里定义，它是函数的第一个参数
        'time_column_name': {'type': 'string', 'label': '时间列名'},
        'data_column_name': {'type': 'string', 'label': '数据列名 (可选)', 'default': None},
        'base_name_for_naming': {'type': 'string', 'label': '基础名称', 'default': 'structured'},
        'name_prefix': {'type': 'string', 'label': '名称前缀', 'default': 'Structured'}
    }
) 