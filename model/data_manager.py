from typing import Dict, List, Optional, Type
from .data_container import DataContainer
from .timeseries_data import TimeSeriesData # 导入具体的类型
import param # 使用 param 实现响应式

class DataManager(param.Parameterized):
    """集中管理所有 DataContainer 对象，并提供响应式接口。"""

    # 使用 param.Dict 实现数据存储，更改会自动触发事件
    _data_store: Dict[str, DataContainer] = param.Dict(default={}, precedence=-1) # 设为内部使用

    # 用于触发列表更新的参数
    _data_updated = param.Event(default=False, precedence=-1)

    def add_data(self, data_object: DataContainer) -> str:
        """
        添加一个新的 DataContainer 对象。

        Args:
            data_object: 要添加的数据容器实例。

        Returns:
            添加的数据对象的 ID。

        Raises:
            TypeError: 如果 data_object 不是 DataContainer 的实例。
            ValueError: 如果尝试添加一个 ID 已存在的对象。
        """
        if not isinstance(data_object, DataContainer):
            raise TypeError("只能添加 DataContainer 的实例。")

        if data_object.id in self._data_store:
            # 通常不应该发生，因为 ID 是 UUID
            raise ValueError(f"ID 为 '{data_object.id}' 的数据对象已存在。")

        # 生成唯一的名称 (如果需要)
        current_names = {d.name for d in self._data_store.values()}
        if data_object.name in current_names:
            data_object.name = self._generate_unique_name(data_object.name)

        # 直接修改 param.Dict 会触发事件
        new_store = self._data_store.copy()
        new_store[data_object.id] = data_object
        self._data_store = new_store # 触发更新
        self._trigger_update()
        return data_object.id

    def get_data(self, data_id: str) -> Optional[DataContainer]:
        """根据 ID 获取 DataContainer 对象。"""
        return self._data_store.get(data_id)

    def remove_data(self, data_id: str) -> bool:
        """根据 ID 删除 DataContainer 对象。"""
        if data_id in self._data_store:
            new_store = self._data_store.copy()
            del new_store[data_id]
            self._data_store = new_store # 触发更新
            self._trigger_update()
            return True
        return False

    def update_name(self, data_id: str, new_name: str) -> bool:
        """根据 ID 更新数据对象的名称。"""
        data_object = self.get_data(data_id)
        if data_object:
            # 检查新名称是否冲突
            current_names = {d.name for id, d in self._data_store.items() if id != data_id}
            if new_name in current_names:
                print(f"警告: 名称 '{new_name}' 已被使用，无法重命名。")
                return False
            if new_name != data_object.name:
                data_object.name = new_name
                self._trigger_update() # 触发列表更新
            return True
        return False

    def list_data_summaries(self, filter_type: Optional[Type[DataContainer]] = None) -> List[Dict]:
        """
        获取所有（或过滤后的）数据对象的摘要信息列表。

        Args:
            filter_type: (可选) 要包含的数据类型 (例如 TimeSeriesData)。

        Returns:
            一个包含每个数据对象摘要字典的列表。
        """
        summaries = []
        for data_object in self._data_store.values():
            if filter_type is None or isinstance(data_object, filter_type):
                summaries.append(data_object.get_summary())
        # 可以根据需要排序，例如按创建时间
        summaries.sort(key=lambda x: x['created_at'], reverse=True)
        return summaries

    def get_data_options(self, filter_type: Optional[Type[DataContainer]] = None) -> List[tuple[str, str]]:
        """
        获取用于下拉列表等选择器的数据选项 (名称, ID)。

        Args:
            filter_type: (可选) 要包含的数据类型。

        Returns:
            一个元组列表 [(name, id), ...]。
        """
        options = []
        # 按名称排序以便于查找
        sorted_items = sorted(self._data_store.values(), key=lambda d: d.name)
        for data_object in sorted_items:
            if filter_type is None or isinstance(data_object, filter_type):
                options.append((data_object.name, data_object.id))
        return options

    def _generate_unique_name(self, base_name: str) -> str:
        """生成一个在当前数据存储中唯一的名称。"""
        current_names = {d.name for d in self._data_store.values()}
        if base_name not in current_names:
            return base_name
        
        counter = 1
        while True:
            new_name = f"{base_name}_{counter}"
            if new_name not in current_names:
                return new_name
            counter += 1

    def _trigger_update(self):
        """触发数据更新事件。"""
        self.param.trigger('_data_updated') 