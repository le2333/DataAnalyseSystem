import pandas as pd
from typing import Optional, Dict, Any, Union, List
import uuid
import datetime

class DataContainer:
    """数据容器基类，用于存储和管理不同类型的数据及其元数据。"""

    def __init__(self, \
                 data: Union[pd.Series, pd.DataFrame, Any], \
                 name: str, \
                 data_type: str, \
                 source_ids: Optional[List[str]] = None, \
                 operation_info: Optional[Dict[str, Any]] = None):
        """初始化数据容器。

        Args:
            data: 存储的数据，可以是 Series, DataFrame 或其他分析结果。
            name: 用户可读的数据名称。
            data_type: 数据类型标识 ('timeseries', 'multidim', 'image_set', 'analysis_result', etc.)。
            source_ids: 生成此数据的源数据 ID 列表，默认为空列表。
            operation_info: 生成此数据的操作信息，默认为空字典。
                            例如: {'name': 'Moving Average', 'params': {'window': 5}}。

        Raises:
            ValueError: 如果 name 不是非空字符串。
        """
        if not isinstance(name, str) or not name.strip():
            raise ValueError("DataContainer 名称必须是非空字符串。")
            
        self._id: str = str(uuid.uuid4())
        self._data: Union[pd.Series, pd.DataFrame, Any] = data
        self._name: str = name.strip()
        self._data_type: str = data_type
        self._source_ids: List[str] = source_ids if source_ids is not None else []
        self._operation_info: Dict[str, Any] = operation_info if operation_info is not None else {}
        self._created_at: datetime.datetime = datetime.datetime.now()
        self._metadata: Dict[str, Any] = {}

    @property
    def id(self) -> str:
        """返回数据容器的唯一 ID。"""
        return self._id

    @property
    def data(self) -> Union[pd.Series, pd.DataFrame, Any]:
        """返回容器中存储的数据。"""
        return self._data

    @property
    def name(self) -> str:
        """返回用户定义的数据名称。"""
        return self._name

    @name.setter
    def name(self, value: str):
        """设置数据名称。
        
        Args:
            value: 新的数据名称，必须是非空字符串。
            
        Raises:
            ValueError: 如果提供的名称无效 (非字符串或为空)。
        """
        if isinstance(value, str) and value.strip():
            self._name = value.strip()
        else:
            raise ValueError("名称必须是非空字符串。")

    @property
    def data_type(self) -> str:
        """返回数据类型标识符。"""
        return self._data_type

    @property
    def source_ids(self) -> List[str]:
        """返回生成此数据的源数据 ID 列表。"""
        return self._source_ids

    @property
    def operation_info(self) -> Dict[str, Any]:
        """返回生成此数据的操作信息。"""
        return self._operation_info

    @property
    def created_at(self) -> datetime.datetime:
        """返回数据容器的创建时间。"""
        return self._created_at

    @property
    def metadata(self) -> Dict[str, Any]:
        """返回额外元数据字典。"""
        return self._metadata

    def update_metadata(self, key: str, value: Any):
        """更新或添加元数据。

        Args:
            key: 元数据的键。
            value: 元数据的值。
        """
        self._metadata[key] = value
        
    def get_data(self) -> Union[pd.Series, pd.DataFrame, Any]:
        """显式获取内部数据的方法 (等同于访问 .data 属性)。"""
        return self._data
        
    # 添加一个辅助属性或方法来检查数据是否多维 (对子类或外部有用)
    @property
    def is_multidim(self) -> bool:
        """检查内部数据是否为 Pandas DataFrame (通常表示多维)。
        
        注意: 这只是一个基于类型的简单检查，具体含义可能取决于子类。
        """
        return isinstance(self._data, pd.DataFrame)
        

    def get_summary(self) -> Dict[str, Any]:
        """获取用于列表展示的摘要信息字典。

        包含基础信息以及根据数据类型（Series/DataFrame）和索引类型
        （DatetimeIndex）添加的特定摘要信息。

        Returns:
            包含摘要信息的字典。
        """
        summary = {
            'id': self.id,
            'name': self.name,
            'type': self.data_type,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'source_count': len(self.source_ids),
            'operation': self.operation_info.get('name', 'N/A')
        }
        
        data_instance = self.data
        shape_info = 'N/A'
        columns_info = 'N/A'
        index_type_info = 'N/A'
        length_info = 'N/A'
        start_time_str = 'N/A'
        end_time_str = 'N/A'

        # 添加 DataFrame 或 Series 特有的信息
        if isinstance(data_instance, (pd.Series, pd.DataFrame)):
            try:
                shape_info = str(data_instance.shape) # 确保是字符串
                index_type_info = type(data_instance.index).__name__
                length_info = data_instance.shape[0]
                
                if isinstance(data_instance, pd.DataFrame):
                    # 如果列太多，只显示数量
                    if data_instance.shape[1] > 10:
                         columns_info = f"{data_instance.shape[1]} 列"
                    else:
                         columns_info = str(list(data_instance.columns)) # 确保是字符串
                else: # Series
                    columns_info = '单列 (Series)'
                
                # 检查时间索引信息
                if isinstance(data_instance.index, pd.DatetimeIndex) and not data_instance.empty:
                    try:
                        min_time = data_instance.index.min()
                        max_time = data_instance.index.max()
                        # 使用更安全的格式化，避免毫秒等问题
                        start_time_str = min_time.strftime('%Y-%m-%d %H:%M:%S')
                        end_time_str = max_time.strftime('%Y-%m-%d %H:%M:%S')
                    except Exception as e:
                        print(f"警告: 格式化数据 (ID: {self.id}) 的时间戳时出错: {e}")
                        start_time_str = '时间格式错误'
                        end_time_str = '时间格式错误'
                       
            except AttributeError as ae:
                 # 处理可能的属性访问错误
                 print(f"警告: 获取数据 (ID: {self.id}) 的摘要属性时出错: {ae}")
                 shape_info = '摘要属性错误'
                 # 其他信息保持 'N/A' 或设为错误状态
            except Exception as general_e:
                 # 捕获其他可能的错误
                 print(f"警告: 获取数据 (ID: {self.id}) 的摘要时发生一般错误: {general_e}")
                 shape_info = '摘要计算错误'
                
        # 更新摘要字典
        summary.update({
            'shape': shape_info,
            'length': str(length_info), # 确保是字符串
            'columns': columns_info, 
            'index_type': index_type_info,
            'start_time': start_time_str,
            'end_time': end_time_str,
        })

        return summary 