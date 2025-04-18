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
             print("Warning: DataManagerController initialized without a navigation_callback.")
        self._bind_events()

    def _bind_events(self):
        """监听视图触发的操作事件。"""
        self.view.param.watch(self._handle_load_request, 'load_request')
        self.view.param.watch(self._handle_explore_request, 'explore_request')
        self.view.param.watch(self._handle_process_request, 'process_request')
        self.view.param.watch(self._handle_compare_request, 'compare_request')
        self.view.param.watch(self._handle_remove_request, 'remove_request')

    # Handle remove request directly (no navigation)
    def _handle_remove_request(self, event):
        """处理删除请求。"""
        if not event.new or not self.view.selected_data_ids:
            return
        ids_to_remove = list(self.view.selected_data_ids)
        removed_count = 0
        errors = []
        # Consider adding confirmation dialog here
        for data_id in ids_to_remove:
            data_obj = self.data_manager.get_data(data_id)
            name = data_obj.name if data_obj else f"ID {data_id[:8]}..."
            if self.data_manager.remove_data(data_id):
                removed_count += 1
            else:
                errors.append(name)
        if removed_count > 0:
             try: pn.state.notifications.success(f"成功删除了 {removed_count} 个数据项。")
             except: pass
        if errors:
             try: pn.state.notifications.error(f"无法删除以下数据项: {', '.join(errors)}。")
             except: pass

    # --- Navigation Callbacks --- #
    def _invoke_navigation(self, view_name: str, params: Dict[str, Any]):
        """Invokes the navigation_callback with the view name and parameters."""
        if self.navigation_callback:
            try:
                 self.navigation_callback(view_name, **params)
            except Exception as e:
                 print(f"Error invoking navigation callback: {e}")
        else:
             print("Error: navigation_callback is not set in DataManagerController.")

    # Add handler for load request
    def _handle_load_request(self, event):
        """Handles load request event and invokes navigation callback."""
        if event.new:
             print(f"DataManagerController: Load request received.")
             self._invoke_navigation('load', params={})

    def _handle_explore_request(self, event):
        """Handles explore request event and invokes navigation callback."""
        # Check if event was triggered (value is True)
        if event.new:
            if self.view.selected_data_ids:
                # Get the single ID from the view's state
                data_id = self.view.selected_data_ids[0]
                print(f"DataManagerController: Explore request for {data_id}")
                self._invoke_navigation('explore', params={'data_id': data_id})
            else:
                 print("Warning: Explore request triggered but no data selected in view.")

    def _handle_process_request(self, event):
        """Handles process request event and invokes navigation callback."""
        # Check if event was triggered (value is True)
        if event.new:
            if self.view.selected_data_ids:
                # Get the list of IDs from the view's state
                selected_ids = list(self.view.selected_data_ids)
                print(f"DataManagerController: Process request for {selected_ids}")
                self._invoke_navigation('process', params={'selected_ids': selected_ids})
            else:
                 print("Warning: Process request triggered but no data selected in view.")

    def _handle_compare_request(self, event):
        """Handles compare request event and invokes navigation callback."""
        # Check if event was triggered (value is True)
        if event.new:
            if self.view.selected_data_ids:
                # Get the list of IDs from the view's state
                selected_ids = list(self.view.selected_data_ids)
                print(f"DataManagerController: Compare request for {selected_ids}")
                self._invoke_navigation('compare', params={'selected_ids': selected_ids})
            else:
                 print("Warning: Compare request triggered but no data selected in view.")

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 