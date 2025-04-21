import param
import panel as pn
from model.data_manager import DataManager
from view.data_manager_view import DataManagerView
from typing import Dict, Any, List, Callable, Optional

class DataManagerController(param.Parameterized):
    """处理 DataManagerView 交互的控制器。"""

    # 依赖注入
    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)
    navigation_callback = param.Callable(default=None)

    def __init__(self, data_manager: DataManager, navigation_callback: Optional[Callable] = None, **params):
        view_instance = DataManagerView(data_manager=data_manager)
        super().__init__(data_manager=data_manager, view=view_instance, navigation_callback=navigation_callback, **params)
        if not self.navigation_callback:
             print("警告: DataManagerController 初始化时未提供 navigation_callback。")
        self._bind_events()

    def _bind_events(self):
        """监听视图触发的操作事件。"""
        self.view.param.watch(self._handle_load_request, 'load_request')
        self.view.param.watch(self._handle_explore_request, 'explore_request')
        self.view.param.watch(self._handle_process_request, 'process_request')
        self.view.param.watch(self._handle_compare_request, 'compare_request')
        self.view.param.watch(self._handle_remove_request, 'remove_request')

    # 直接处理删除请求 (无需导航)
    def _handle_remove_request(self, event):
        """处理删除请求。"""
        if not event.new or not self.view.selected_data_ids:
            return
        ids_to_remove = list(self.view.selected_data_ids)
        removed_count = 0
        errors = []
        # TODO: 在此添加确认对话框
        for data_id in ids_to_remove:
            data_obj = self.data_manager.get_data(data_id)
            name = data_obj.name if data_obj else f"ID {data_id[:8]}..."
            if self.data_manager.remove_data(data_id):
                removed_count += 1
            else:
                errors.append(name)
        if removed_count > 0:
             # 尝试显示成功通知 (移除 try/except pass)
             pn.state.notifications.success(f"成功删除了 {removed_count} 个数据项。")
        if errors:
             # 尝试显示错误通知 (移除 try/except pass)
             pn.state.notifications.error(f"无法删除以下数据项: {', '.join(errors)}。")

    # --- 导航回调相关方法 --- #
    def _invoke_navigation(self, view_name: str, params: Dict[str, Any]):
        """调用 navigation_callback 以导航到指定视图。"""
        if self.navigation_callback:
            try:
                 self.navigation_callback(view_name, **params)
            except Exception as e:
                 print(f"错误: 调用导航回调时出错: {e}")
        else:
             print("错误: DataManagerController 中未设置 navigation_callback。")

    # 处理加载请求
    def _handle_load_request(self, event):
        """处理加载请求事件并调用导航回调。"""
        if event.new:
             print(f"DataManagerController: 收到加载请求。")
             self._invoke_navigation('load', params={})

    def _handle_explore_request(self, event):
        """处理探索 (可视化单个) 请求事件并调用导航回调。"""
        if event.new:
            if self.view.selected_data_ids:
                data_id = self.view.selected_data_ids[0]
                print(f"DataManagerController: 收到可视化请求 (单个): {data_id}")
                # 导航到统一视图，传递单个 ID
                self._invoke_navigation('visualize', params={'selected_ids': data_id})
            else:
                 print("警告: 触发了可视化请求，但视图中未选择任何数据。")

    def _handle_process_request(self, event):
        """处理处理请求事件并调用导航回调。"""
        if event.new:
            if self.view.selected_data_ids:
                selected_ids = list(self.view.selected_data_ids)
                print(f"DataManagerController: 收到处理请求: {selected_ids}")
                self._invoke_navigation('process', params={'selected_ids': selected_ids})
            else:
                 print("警告: 触发了处理请求，但视图中未选择任何数据。")

    def _handle_compare_request(self, event):
        """处理比较 (可视化多个) 请求事件并调用导航回调。"""
        if event.new:
            if self.view.selected_data_ids:
                selected_ids = list(self.view.selected_data_ids)
                print(f"DataManagerController: 收到可视化请求 (多个): {selected_ids}")
                # 导航到统一视图，传递 ID 列表
                self._invoke_navigation('visualize', params={'selected_ids': selected_ids})
            else:
                 print("警告: 触发了比较请求，但视图中未选择任何数据。")

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 