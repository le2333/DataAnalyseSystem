import pandas as pd
from typing import Optional, Dict, Any
import uuid
import datetime

class DataContainer:
    """数据容器基类，用于存储和管理不同类型的数据及其元数据。"""

    def __init__(self, data: pd.Series | pd.DataFrame | Any, name: str, data_type: str, source_ids: Optional[list[str]] = None, operation_info: Optional[dict] = None):
        """
        初始化数据容器。

        Args:
            data: 存储的数据，可以是 Series, DataFrame 或其他分析结果。
            name: 用户可读的数据名称。
            data_type: 数据类型标识 ('timeseries', 'multidim', 'analysis_result', etc.)。
            source_ids: (可选) 生成此数据的源数据 ID 列表。
            operation_info: (可选) 生成此数据的操作信息 (例如: {'name': 'Moving Average', 'params': {'window': 5}})。
        """
        self._id: str = str(uuid.uuid4()) # 内部唯一 ID
        self._data: pd.Series | pd.DataFrame | Any = data
        self._name: str = name
        self._data_type: str = data_type
        self._source_ids: list[str] = source_ids if source_ids is not None else []
        self._operation_info: dict = operation_info if operation_info is not None else {}
        self._created_at: datetime.datetime = datetime.datetime.now()
        self._metadata: Dict[str, Any] = {} # 用于存储额外元数据

    @property
    def id(self) -> str:
        return self._id

    @property
    def data(self) -> pd.Series | pd.DataFrame | Any:
        return self._data

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str):
        if isinstance(value, str) and value.strip():
            self._name = value.strip()
        else:
            print("警告: 名称必须是非空字符串。")

    @property
    def data_type(self) -> str:
        return self._data_type

    @property
    def source_ids(self) -> list[str]:
        return self._source_ids

    @property
    def operation_info(self) -> dict:
        return self._operation_info

    @property
    def created_at(self) -> datetime.datetime:
        return self._created_at

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata

    def update_metadata(self, key: str, value: Any):
        """更新或添加元数据。"""
        self._metadata[key] = value

    def get_summary(self) -> dict:
        """获取用于列表展示的摘要信息。"""
        summary = {
            'id': self.id,
            'name': self.name,
            'type': self.data_type,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'source_count': len(self.source_ids),
            'operation': self.operation_info.get('name', 'N/A')
        }
        if isinstance(self.data, (pd.Series, pd.DataFrame)):
            summary['shape'] = self.data.shape
        return summary 