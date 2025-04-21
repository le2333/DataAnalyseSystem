import pandas as pd
import os
# 移除对 TimeSeriesData 的导入，使用 DataContainer
# from model.timeseries_data import TimeSeriesData
# 移除通用的 DataContainer 导入
# from model.data_container import DataContainer
# 导入具体的 TimeSeriesContainer
from model.timeseries_container import TimeSeriesContainer
from .registry import STRUCTURERS, register_service
from typing import Optional, List, Any # 确保导入 List, Any

def structure_df_to_timeseries(
    input_df: pd.DataFrame,
    time_column_name: str,
    data_column_name: Optional[str] = None,
    base_name_for_naming: str = "structured",
    name_prefix: str = "Structured"
) -> TimeSeriesContainer:
    """将输入的 DataFrame 结构化为单一时间序列的 TimeSeriesContainer。

    从原始 DataFrame 中提取指定的时间列和数据列，将时间列解析为 DatetimeIndex
    并设置为索引，然后使用数据列创建 Pandas Series。
    最终返回包含此 Series 的 TimeSeriesContainer 对象。

    Args:
        input_df (pd.DataFrame): 包含待结构化数据的 Pandas DataFrame。
        time_column_name (str): DataFrame 中用作时间索引的列名。
        data_column_name (Optional[str]): 要提取的数据列名。
            如果为 None (默认)，则自动选择第一个非时间索引列作为数据列。
        base_name_for_naming (str): 用于构成最终 TimeSeriesContainer 名称的
            基础部分，通常建议使用原始文件名（不含扩展名）。默认为 "structured"。
        name_prefix (str): 添加到最终 TimeSeriesContainer 名称开头的
            前缀。默认为 "Structured"。

    Returns:
        TimeSeriesContainer: 包含提取和处理后的单列时间序列数据的容器。

    Raises:
        ValueError: 如果指定的时间列或数据列无效、DataFrame 中缺少数据列、
                    无法将时间列解析为 DatetimeIndex，或者未能提取有效的单列数据。
        TypeError: 如果时间列转换后索引类型仍不正确 (理论上不应发生)。
    """
    # 创建副本以避免修改原始传入的 DataFrame
    df = input_df.copy()

    # --- 1. 验证和解析时间列 --- 
    if time_column_name not in df.columns:
         raise ValueError(f"时间列 '{time_column_name}' 不存在于 DataFrame 中。可用列: {list(df.columns)}")

    try:
        # 尝试将指定列转换为 datetime 对象
        df[time_column_name] = pd.to_datetime(df[time_column_name], errors='raise')
        # 将转换后的时间列设置为索引
        df = df.set_index(time_column_name)
        # 再次检查索引类型，确保是 DatetimeIndex
        if not isinstance(df.index, pd.DatetimeIndex):
             raise TypeError(f"列 '{time_column_name}' 转换后未能成为 DatetimeIndex。")
    except (ValueError, TypeError, OverflowError) as e:
        # 处理时间解析或索引设置错误
        error_detail = f"无法将列 '{time_column_name}' 解析为时间格式或设置为索引: {e}"
        # 尝试获取无法解析的示例值以辅助调试
        try:
            original_time_data = input_df[time_column_name]
            # 尝试强制转换，将无法转换的值变为 NaT
            failed_indices = pd.to_datetime(original_time_data, errors='coerce').isna()
            # 获取那些变成 NaT 的原始值中的唯一值
            non_parsable_samples = original_time_data[failed_indices].unique()
            sample_limit = 5
            if len(non_parsable_samples) > 0:
                error_detail += f" 示例值: {list(non_parsable_samples[:sample_limit])}"
                if len(non_parsable_samples) > sample_limit:
                    error_detail += " 等。"
        except Exception as sample_e:
            # 如果获取示例值失败，仅打印调试信息，不影响主错误报告
            print(f"调试: 获取时间列解析失败样本时出错: {sample_e}")
        # 抛出包含详细信息的 ValueError
        raise ValueError(error_detail) from e
    except KeyError as e:
        # 处理 set_index 时的列名不存在错误 (理论上已被前面检查覆盖)
        raise ValueError(f"设置索引时发生键错误: {e}") from e

    # --- 2. 选择数据列 --- 
    selected_col_name = ""
    if data_column_name:
        # 如果用户指定了数据列
        if data_column_name not in df.columns:
            raise ValueError(f"指定的数据列 '{data_column_name}' 不在 DataFrame 中。可用列: {list(df.columns)}")
        series = df[data_column_name]
        selected_col_name = data_column_name
    else:
        # 用户未指定，自动选择第一个非索引列
        if df.columns.empty:
             raise ValueError("DataFrame 中除了时间索引外，没有其他数据列可供选择。")
        selected_col_name = df.columns[0]
        series = df[selected_col_name]
        print(f"信息: 未指定数据列，自动选择第一列 '{selected_col_name}'。")

    # --- 3. 确保得到 Series 并设置名称 --- 
    if not isinstance(series, pd.Series):
        # 如果选中的列仍然是 DataFrame（例如，由于多级列索引），尝试提取第一列
        if isinstance(series, pd.DataFrame) and len(series.columns) == 1:
            series = series.iloc[:, 0]
        else:
            raise ValueError("未能从 DataFrame 中提取有效的单列时间序列数据。请检查数据结构或明确指定数据列。")

    # 如果提取的 Series 没有名称，尝试根据选择的列名设置
    if series.name is None:
        series.name = selected_col_name if selected_col_name else 'value'

    # --- 4. 创建并返回 TimeSeriesContainer 对象 --- 
    # 构造新容器的名称
    container_name = f"{name_prefix}_{base_name_for_naming}_{series.name}"

    # TimeSeriesContainer 的初始化方法会处理数据排序和进一步的索引验证
    return TimeSeriesContainer(
        data=series,
        name=container_name,
        source_ids=None, # 这是初始结构化，没有源 DataContainer ID
        operation_info={'name': 'structure_df_to_timeseries', 'params': {'time_column': time_column_name, 'data_column': selected_col_name}} # 记录操作信息
    )

# --- 服务注册 ---
register_service(
    registry=STRUCTURERS,
    name="从DataFrame结构化为时间序列",
    function=structure_df_to_timeseries,
    input_type=pd.DataFrame, # 输入是原始 DataFrame
    output_type=TimeSeriesContainer, # 输出是包含 Series 的 TimeSeriesContainer
    params_spec={ # 这些参数由 LoadController 内部处理，不在 UI 上直接配置
        # 'time_column_name': {'type': 'string', 'label': '时间列'}, # 通过 LoadView 的专用选择器获取
        # 'data_column_name': {'type': 'string', 'label': '数据列(可选)'}, # 通过 LoadView 的专用选择器获取
        # 'base_name_for_naming': {'type': 'string', 'label': '基础名称'}, # 由 LoadController 从文件名生成
        # 'name_prefix': {'type': 'string', 'label': '名称前缀'} # 通常是固定的或由 Controller 控制
    },
    accepts_list=False, # 只处理单个 DataFrame
    input_param_name='input_df' # 明确函数期望的 DataFrame 参数名
) 