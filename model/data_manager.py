import param
import uuid
import pandas as pd
from typing import Dict, List, Optional, Type, Union, Tuple
from .data_container import DataContainer
from .timeseries_data import TimeSeriesData
from .multidim_data import MultiDimData # 导入新类型

# 定义支持的数据容器类型联合
SupportedData = Union[TimeSeriesData, MultiDimData]

class DataManager(param.Parameterized):
    """管理应用中的所有数据容器。"""

    # 使用字典存储数据，键为 ID，值为 DataContainer 对象
    _data_store: Dict[str, SupportedData] = param.Dict(default={}, precedence=-1)

    # 用于通知视图数据已更新的事件
    _data_updated = param.Event(default=False, precedence=-1)

    def add_data(self, data_container: SupportedData) -> str:
        """
        向管理器添加新的数据容器。

        Args:
            data_container: 要添加的数据容器实例 (TimeSeriesData 或 MultiDimData)。

        Returns:
            分配给数据容器的唯一 ID。

        Raises:
            TypeError: 如果传入的对象不是支持的数据容器类型。
            ValueError: 如果 data_container 的 ID 已存在 (理论上不应发生)。
        """
        if not isinstance(data_container, (TimeSeriesData, MultiDimData)):
            raise TypeError("只能添加 TimeSeriesData 或 MultiDimData 类型的对象。")

        # 确保 ID 唯一 (虽然 UUID 碰撞概率极低)
        while data_container.id in self._data_store:
            data_container._id = str(uuid.uuid4())

        # 检查名称是否重复，如果重复则自动添加后缀
        original_name = data_container.name
        count = 1
        while any(dc.name == data_container.name for dc in self._data_store.values()):
            data_container.name = f"{original_name}_{count}"
            count += 1

        # 存储数据并触发更新事件
        # 使用 param.Dict 的方式更新以触发依赖
        new_store = self._data_store.copy()
        new_store[data_container.id] = data_container
        self._data_store = new_store

        self.param.trigger('_data_updated')
        return data_container.id

    def get_data(self, data_id: str) -> Optional[SupportedData]:
        """根据 ID 获取数据容器。"""
        return self._data_store.get(data_id)

    def remove_data(self, data_id: str) -> bool:
        """
        根据 ID 删除数据容器。

        Returns:
            如果成功删除返回 True，否则 False。
        """
        if data_id in self._data_store:
            new_store = self._data_store.copy()
            del new_store[data_id]
            self._data_store = new_store
            self.param.trigger('_data_updated')
            return True
        return False

    def get_all_data(self) -> List[SupportedData]:
        """获取所有数据容器的列表。"""
        return list(self._data_store.values())

    def get_data_options(self, filter_type: Optional[Type[SupportedData]] = None) -> List[Tuple[str, str]]:
        """
        获取用于选择器的数据选项列表 (显示名称, ID)。

        Args:
            filter_type: (可选) 只包含指定类型的数据容器 (例如 TimeSeriesData)。
                       如果为 None，则包含所有类型。

        Returns:
            一个元组列表，每个元组是 (显示名称, 数据 ID)。
        """
        options = []
        # 按名称排序以获得一致的顺序
        sorted_items = sorted(self._data_store.values(), key=lambda dc: dc.name)
        for dc in sorted_items:
            if filter_type is None or isinstance(dc, filter_type):
                # 格式化显示名称以包含类型信息
                display_name = f"{dc.name} ({dc.data_type})"
                options.append((display_name, dc.id))
        return options

    def get_summary_list(self) -> List[Dict]:
        """
        获取所有数据容器的摘要信息列表，用于表格显示。
        现在会包含不同类型的摘要。
        """
        summaries = []
        # 按名称排序
        sorted_items = sorted(self._data_store.values(), key=lambda dc: dc.name)
        for dc in sorted_items:
            try:
                # 调用各自的 get_summary 方法
                summary = dc.get_summary()
                summaries.append(summary)
            except Exception as e:
                print(f"获取数据 '{dc.name}' ({dc.id}) 的摘要时出错: {e}")
                # 添加一个错误条目，以便在 UI 中看到问题
                summaries.append({
                    'id': dc.id,
                    'name': dc.name,
                    'type': dc.data_type,
                    'status': f'Error getting summary: {e}'
                })
        return summaries

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

    def list_data_summaries(self, filter_type: Optional[Type[SupportedData]] = None) -> List[Dict]:
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