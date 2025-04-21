import pandas as pd
from .data_container import DataContainer
from typing import Any, Optional, Dict, Union, List

class TimeSeriesContainer(DataContainer):
    """存储一维或多维时间序列数据的容器。

    继承自 DataContainer，专门处理 Pandas Series 或 DataFrame 格式的时间序列，
    并强制要求索引为 DatetimeIndex 且按时间排序。
    """

    DATA_TYPE = "timeseries" 

    def __init__(self, 
                 data: Union[pd.Series, pd.DataFrame], 
                 name: str, 
                 source_ids: Optional[List[str]] = None, 
                 operation_info: Optional[Dict[str, Any]] = None):
        """初始化时间序列数据容器。

        Args:
            data: 包含时间序列数据的 Pandas Series 或 DataFrame。
                  如果索引不是 DatetimeIndex，会尝试进行转换。
                  数据将按时间索引排序。
            name: 用户可读的数据名称。
            source_ids: (可选) 生成此数据的源数据 ID 列表。
            operation_info: (可选) 生成此数据的操作信息。

        Raises:
            TypeError: 如果传入的 data 不是 Pandas Series 或 DataFrame。
            ValueError: 如果数据的索引无法转换为 DatetimeIndex。
        """
        if not isinstance(data, (pd.Series, pd.DataFrame)):
            raise TypeError("时间序列数据必须是 Pandas Series 或 DataFrame 类型。")

        processed_data = data.copy() # 避免修改原始传入的数据

        # 尝试将索引转换为 DatetimeIndex
        if not isinstance(processed_data.index, pd.DatetimeIndex):
            print(f"信息: 数据 '{name}' 的索引不是 DatetimeIndex，尝试转换...")
            try:
                original_index_name = processed_data.index.name # 保留原始索引名
                processed_data.index = pd.to_datetime(processed_data.index, errors='raise')
                if not isinstance(processed_data.index, pd.DatetimeIndex):
                     # 这通常不应发生，因为 errors='raise'
                     raise ValueError("数据索引转换后未知错误，不是 DatetimeIndex 类型。") 
                # 恢复索引名（如果原来有的话）
                processed_data.index.name = original_index_name
                print(f"信息: 数据 '{name}' 的索引已成功转换为 DatetimeIndex。")
            except (TypeError, ValueError, OverflowError) as e:
                raise ValueError(f"数据 '{name}' 的索引无法转换为 DatetimeIndex: {e}") from e
        
        # 确保数据按时间排序
        if not processed_data.index.is_monotonic_increasing:
            processed_data = processed_data.sort_index()
            print(f"信息: 数据 '{name}' 已按时间索引排序。")

        # 调用基类构造函数，传递处理后的数据和固定的 data_type
        super().__init__(processed_data, name, self.DATA_TYPE, source_ids, operation_info)

    # 可以添加特定 getter 属性
    @property
    def series(self) -> Optional[pd.Series]:
        """如果内部数据是 Series，则返回它，否则返回 None。"""
        return self._data if isinstance(self._data, pd.Series) else None

    @property
    def dataframe(self) -> Optional[pd.DataFrame]:
        """如果内部数据是 DataFrame，则返回它，否则返回 None。"""
        return self._data if isinstance(self._data, pd.DataFrame) else None
        
    # get_summary 可以被重写以添加更具体的信息，但基类已包含大部分
    # def get_summary(self) -> Dict[str, Any]:
    #     summary = super().get_summary()
    #     # 可以添加例如维度信息等
    #     if self.dataframe is not None:
    #          summary['dimension'] = self.dataframe.shape[1] 
    #     else:
    #          summary['dimension'] = 1
    #     return summary 