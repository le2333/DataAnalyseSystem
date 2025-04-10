import pandas as pd
from .data_container import DataContainer
from typing import Any, Optional

class TimeSeriesData(DataContainer):
    """存储一维时间序列数据的容器。"""

    DATA_TYPE = "timeseries"

    def __init__(self, data: pd.Series, name: str, source_ids: Optional[list[str]] = None, operation_info: Optional[dict] = None):
        """
        初始化时间序列数据容器。

        Args:
            data: 包含时间序列数据的 Pandas Series，索引应为 DatetimeIndex。
            name: 用户可读的数据名称。
            source_ids: (可选) 生成此数据的源数据 ID 列表。
            operation_info: (可选) 生成此数据的操作信息。

        Raises:
            ValueError: 如果传入的 data 不是 Pandas Series 或者索引不是 DatetimeIndex。
        """
        if not isinstance(data, pd.Series):
            raise ValueError("数据必须是 Pandas Series 类型。")
        if not isinstance(data.index, pd.DatetimeIndex):
            # 尝试转换，如果失败则报错
            try:
                data.index = pd.to_datetime(data.index)
                if not isinstance(data.index, pd.DatetimeIndex):
                     raise TypeError()
            except (TypeError, ValueError):
                raise ValueError("数据索引必须是 DatetimeIndex 或可以转换为 DatetimeIndex。")

        super().__init__(data, name, self.DATA_TYPE, source_ids, operation_info)

    @property
    def series(self) -> pd.Series:
        """明确返回 Pandas Series 类型的数据。"""
        return self._data # 在基类中是 _data

    def get_summary(self) -> dict:
        """获取用于列表展示的摘要信息（覆盖基类）。"""
        summary = super().get_summary()
        summary.update({
            'length': len(self.series),
            'start_time': self.series.index.min().strftime('%Y-%m-%d %H:%M:%S') if not self.series.empty else 'N/A',
            'end_time': self.series.index.max().strftime('%Y-%m-%d %H:%M:%S') if not self.series.empty else 'N/A'
        })
        return summary

# 可以在这里添加 MultiDimData 和 AnalysisResult 类，如果需要的话
# class MultiDimData(DataContainer):
#     DATA_TYPE = "multidim"
#     def __init__(self, data: pd.DataFrame, ...):
#         if not isinstance(data, pd.DataFrame):
#             raise ValueError("数据必须是 Pandas DataFrame 类型。")
#         super().__init__(data, ...)
#
# class AnalysisResult(DataContainer):
#     DATA_TYPE = "analysis_result"
#     def __init__(self, data: Any, ...):
#         super().__init__(data, ...) 