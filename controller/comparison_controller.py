import param
import panel as pn
import holoviews as hv
from model.data_manager import DataManager
from model.data_container import DataContainer # For type hint
# Import specific types if needed for validation, e.g.:
from model.timeseries_data import TimeSeriesData
from model.multidim_data import MultiDimData
from view.comparison_view import ComparisonView # Updated view name
from services.registry import VISUALIZERS
from typing import List, Dict, Optional, Any, Type, get_origin
import traceback
# Import the base controller
from .base_visualization_controller import BaseVisualizationController

class ComparisonController(BaseVisualizationController):
    """处理 ComparisonView 的交互，调用处理列表输入的可视化服务。"""

    def __init__(self, data_manager: DataManager, **params):
        # Instantiate the specific view
        view_instance = ComparisonView(data_manager=data_manager)
        # Pass the view instance and VISUALIZERS registry to the base class
        super().__init__(data_manager=data_manager, view_instance=view_instance, registry=VISUALIZERS, **params)

    # Implement the required set_selected_data method
    def set_selected_data(self, selected_ids: List[str]):
        """Sets the list of selected data IDs in the view."""
        if self.view:
            self.view.selected_data_ids = selected_ids
        else:
            print(f"Warning: Cannot set selected data IDs in {self.__class__.__name__}, view not initialized.")

    # Implement the specific data validation and payload preparation
    def _validate_data_and_get_payload(self, config: Dict, service_info: Dict) -> tuple[bool, Dict[str, Any]]:
        """Validates the list of selected data items and prepares the payload."""
        selected_ids = config.get('selected_data_ids', [])
        service_name = config.get('service_name')
        expected_input_type_info = service_info.get('input_type')

        # --- Check if service expects a List input using typing.get_origin --- #
        if get_origin(expected_input_type_info) is not list:
            # This service is not designed for comparison view (doesn't accept a list)
            error_msg = f"服务 '{service_name}' 不适用于比较视图（其注册的输入类型不是列表）。请在探索视图中使用此服务。"
            self._notify("error", error_msg, duration=8000)
            if self.view and self.view.visualization_area:
                 self.view.update_visualization_area_display(pn.pane.Alert(error_msg, alert_type='danger'))
            return False, {}
        
        # Extract the expected item type from the list args if available
        expected_item_type: Optional[Type] = None
        args = getattr(expected_input_type_info, '__args__', None)
        if args:
            expected_item_type = args[0]
        # If no specific item type within the list (e.g. List without args), we skip item type validation
        # but still proceed as it expects a list.

        data_containers_list: List[DataContainer] = []
        errors = []
        first_type = None

        if not selected_ids or len(selected_ids) < 2:
            errors.append("可视化比较需要至少选择两个数据项。")
        
        # --- Validate selected items --- #
        for i, data_id in enumerate(selected_ids):
            data_container = self.data_manager.get_data(data_id)
            if not data_container:
                errors.append(f"数据项 ID: {data_id} 未找到")
                continue

            current_type = type(data_container)
            if i == 0:
                first_type = current_type
                # Check if the first item matches the expected item type (if specified in registry)
                if expected_item_type and not issubclass(first_type, expected_item_type):
                     errors.append(f"可视化 '{service_name}' 需要 {expected_item_type.__name__} 类型的数据，但第一个是 {first_type.__name__}。")
                     break # Stop early
            elif current_type != first_type:
                errors.append("可视化比较要求所有选定数据类型相同。")
                break # Stop early

            data_containers_list.append(data_container)

        # Check again if expected type was set and didn't match the found type
        if expected_item_type and first_type and not issubclass(first_type, expected_item_type):
            if not any(f"需要 {expected_item_type.__name__}" in e for e in errors):
                 errors.append(f"可视化 '{service_name}' 需要 {expected_item_type.__name__} 类型的数据，但找到的是 {first_type.__name__}。")

        if errors:
            error_summary = "数据验证失败:\n" + "\n".join(f"- {e}" for e in errors)
            self._notify("error", error_summary, duration=10000)
            if self.view and self.view.visualization_area:
                 self.view.update_visualization_area_display(pn.Column(*[pn.pane.Alert(e, alert_type='danger') for e in errors]))
            return False, {}

        # Prepare payload for list-input service
        payload = {"data_containers": data_containers_list}
        return True, payload

    # The _handle_visualize_base method from the base class will handle the rest
    # Remove the old _handle_visualize, _show_error_and_reset, _reset_visualize_state methods

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 