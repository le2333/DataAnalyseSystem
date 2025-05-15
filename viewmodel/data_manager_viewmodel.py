import param
from typing import List, Dict, Any, Optional, Type
from model.data_manager import DataManager
from model.data_container import DataContainer
from model.timeseries_container import TimeSeriesContainer


class DataManagerViewModel(param.Parameterized):
    """数据管理视图模型，负责模型和视图之间的数据传递和处理"""

    # 持有数据管理器模型
    data_manager = param.ClassSelector(class_=DataManager)

    # 导出供视图直接监听的参数
    data_updated = param.Event(doc="数据更新事件")
    selected_data_ids = param.List(default=[], doc="当前选中的数据ID列表")
    data_summary_list = param.List(default=[], doc="数据摘要列表，用于表格显示")

    def __init__(self, data_manager: DataManager, **params):
        super().__init__(data_manager=data_manager, **params)

        # 监听数据变化
        self.data_manager.param.watch(self._handle_data_update, "_data_updated")

        # 初始加载数据摘要
        self._refresh_data_summary()

    def _handle_data_update(self, event):
        """处理模型数据更新事件"""
        self._refresh_data_summary()
        self.param.trigger("data_updated")

    def _refresh_data_summary(self):
        """刷新数据摘要列表"""
        self.data_summary_list = self.data_manager.get_summary_list()

    def get_data_options(self, filter_type: Optional[Type[DataContainer]] = None):
        """获取数据选项列表，用于下拉选择框"""
        return self.data_manager.get_data_options(filter_type)

    def select_data(self, data_ids: List[str]):
        """选择数据项"""
        self.selected_data_ids = data_ids

    def add_data(self, data_container: DataContainer) -> str:
        """添加数据容器"""
        return self.data_manager.add_data(data_container)

    def remove_data(self, data_id: str) -> bool:
        """移除数据容器"""
        result = self.data_manager.remove_data(data_id)
        # 如果删除的数据在选中列表中，需要更新选中状态
        if result and data_id in self.selected_data_ids:
            self.selected_data_ids = [
                id for id in self.selected_data_ids if id != data_id
            ]
        return result

    def rename_data(self, data_id: str, new_name: str) -> bool:
        """重命名数据容器"""
        return self.data_manager.update_name(data_id, new_name)

    def get_data(self, data_id: str) -> Optional[DataContainer]:
        """获取指定ID的数据容器"""
        return self.data_manager.get_data(data_id)

    def get_selected_data(self) -> List[DataContainer]:
        """获取所有选中的数据容器"""
        return [
            self.data_manager.get_data(id)
            for id in self.selected_data_ids
            if self.data_manager.get_data(id)
        ]
