import pandas as pd
from model.timeseries_container import TimeSeriesContainer
# Import from parent directory registry
from ..registry import PREPROCESSORS, register_service
from typing import List, Dict, Any, Optional

def merge_1d_to_multidim(
    data_containers: List[TimeSeriesContainer],
    new_multidim_name: str
) -> TimeSeriesContainer:
    """将多个单维时间序列合并为一个多维时间序列。

    输入为包含多个 TimeSeriesContainer (内部为 Series) 的列表。
    使用时间作为索引进行外部连接 (outer join)，保留所有时间点，缺失处填充 NaN。
    合并后的 DataFrame 列名将基于原始 TimeSeriesContainer 的名称，
    如果存在名称冲突，会自动添加数字后缀 (例如 `_1`, `_2`)。

    Args:
        data_containers (List[TimeSeriesContainer]):
            包含要合并的单维 TimeSeriesContainer 对象的列表。
        new_multidim_name (str): 新创建的多维 TimeSeriesContainer 对象的名称。
                                 必须提供一个非空字符串。

    Returns:
        TimeSeriesContainer: 一个包含合并后多维 DataFrame 的新容器。

    Raises:
        ValueError: 如果输入列表为空、新名称无效、或列表中包含非 TimeSeriesContainer
                    或多维 TimeSeriesContainer、或者所有输入序列都为空。
        RuntimeError: 如果在合并 Series 时发生 Pandas 内部错误。
    """
    # --- 输入验证 ---
    if not data_containers:
        raise ValueError("输入列表不能为空，至少需要一个时间序列才能进行合并。")
    if not new_multidim_name or not new_multidim_name.strip():
         raise ValueError("必须为合并后的新数据指定一个有效的名称。")

    all_series_to_merge = {}
    source_ids = []
    processed_names = set()

    # --- 遍历输入容器，准备待合并的 Series --- 
    for dc in data_containers:
        if not isinstance(dc, TimeSeriesContainer):
             raise ValueError(f"输入列表中的项必须是 TimeSeriesContainer 类型，但发现 {type(dc).__name__}。")
        if dc.is_multidim:
            raise ValueError(f"输入数据 '{dc.name}' ({dc.id}) 必须是单维时间序列 (Series)，但发现是多维。")

        series_data = dc.series
        assert series_data is not None, f"内部错误：容器 '{dc.name}' ({dc.id}) is_multidim=False 但 series is None"

        if series_data.empty:
             print(f"警告: 跳过空的时间序列 '{dc.name}' ({dc.id})。")
             continue

        original_name = dc.name
        col_name = original_name
        count = 1
        while col_name in all_series_to_merge or col_name in processed_names:
            col_name = f"{original_name}_{count}"
            count += 1

        all_series_to_merge[col_name] = series_data
        processed_names.add(col_name)
        source_ids.append(dc.id)

    if not all_series_to_merge:
        raise ValueError("所有输入的时间序列均为空，无法进行合并。")

    # --- 执行合并 --- 
    try:
        merged_df = pd.concat(all_series_to_merge, axis=1, join='outer')
        if merged_df.index.name is None:
             merged_df.index.name = 'time'

    except Exception as e:
        raise RuntimeError(f"合并时间序列时出错: {e}") from e

    # --- 创建并返回结果容器 --- 
    return TimeSeriesContainer(
        data=merged_df,
        name=new_multidim_name.strip(),
        source_ids=source_ids,
        operation_info={'name': 'merge_1d_to_multidim', 'params': {'input_count': len(source_ids)}}
    )

# --- 服务注册：合并 --- 
register_service(
    registry=PREPROCESSORS,
    name="合并一维时间序列为多维",
    function=merge_1d_to_multidim,
    input_type=TimeSeriesContainer,
    output_type=TimeSeriesContainer,
    params_spec={
        'new_multidim_name': {'type': 'string', 'label': '新数据名称', 'default': 'merged_data'}
    },
    accepts_list=True,
    input_param_name='data_containers'
) 