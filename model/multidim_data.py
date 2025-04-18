import pandas as pd
from .data_container import DataContainer
from typing import Any, Optional

class MultiDimData(DataContainer):
    """存储多维数据的容器，通常是 DataFrame。"""

    DATA_TYPE = "multidim"

    def __init__(self, data: pd.DataFrame, name: str, source_ids: Optional[list[str]] = None, operation_info: Optional[dict] = None):
        """
        初始化多维数据容器。

        Args:
            data: 包含多维数据的 Pandas DataFrame。
            name: 用户可读的数据名称。
            source_ids: (可选) 生成此数据的源数据 ID 列表。
            operation_info: (可选) 生成此数据的操作信息。

        Raises:
            ValueError: 如果传入的 data 不是 Pandas DataFrame。
        """
        if not isinstance(data, pd.DataFrame):
            raise ValueError("数据必须是 Pandas DataFrame 类型。")
        # 可以添加更多验证，例如索引类型等

        super().__init__(data, name, self.DATA_TYPE, source_ids, operation_info)

    @property
    def dataframe(self) -> pd.DataFrame:
        """明确返回 Pandas DataFrame 类型的数据。"""
        # Assuming self._data stores the DataFrame in the base class
        return self._data

    # Override base data property to return specific type
    @property
    def data(self) -> pd.DataFrame:
        """返回 Pandas DataFrame 类型的数据 (覆盖基类属性)。"""
        return self._data

    def get_summary(self) -> dict:
        """获取用于列表展示的摘要信息。"""
        summary = super().get_summary()
        df = self.dataframe
        summary.update({
            'shape': df.shape,
            'columns': list(df.columns),
            'index_type': type(df.index).__name__,
            # 添加更多你认为有用的摘要信息
        })
        return summary 