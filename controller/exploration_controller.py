import param
import panel as pn
import holoviews as hv
from model.data_manager import DataManager
from model.data_container import DataContainer
from view.exploration_view import ExplorationView # Use the new view
from services.registry import VISUALIZERS
from typing import List, Dict, Optional, Any, Type
import traceback
# Import the base controller
from .base_visualization_controller import BaseVisualizationController

class ExplorationController(BaseVisualizationController):
    """处理 ExplorationView 的交互，调用处理单个输入的动态可视化服务。"""

    def __init__(self, data_manager: DataManager, **params):
        # Instantiate the specific view for this controller
        view_instance = ExplorationView(data_manager=data_manager)
        # Pass the view instance and the VISUALIZERS registry to the base class
        super().__init__(data_manager=data_manager, view_instance=view_instance, registry=VISUALIZERS, **params)
        # Base class constructor now calls _bind_events

    # Implement the required set_selected_data method
    def set_selected_data(self, selected_id: str):
        """Sets the single selected data ID in the view."""
        if self.view:
            self.view.selected_data_id = selected_id
        else:
            print(f"Warning: Cannot set selected data ID in {self.__class__.__name__}, view not initialized.")

    # Implement the specific data validation and payload preparation
    def _validate_data_and_get_payload(self, config: Dict, service_info: Dict) -> tuple[bool, Dict[str, Any]]:
        """Validates the single selected data item and prepares the payload."""
        selected_id = config.get('selected_data_id')
        service_name = config.get('service_name')
        expected_input_type = service_info.get('input_type')
        errors = []
        data_container = None

        if not selected_id:
            errors.append("没有选择要探索的数据项。")
        else:
            data_container = self.data_manager.get_data(selected_id)
            if not data_container:
                errors.append(f"数据项 ID: {selected_id} 未找到")
            elif expected_input_type and not isinstance(data_container, expected_input_type):
                errors.append(f"可视化 '{service_name}' 需要 {expected_input_type.__name__} 类型数据，但选择的是 {type(data_container).__name__}。")

        if errors:
            error_summary = "数据验证失败:\n" + "\n".join(f"- {e}" for e in errors)
            self._notify("error", error_summary, duration=10000)
            if self.view and self.view.visualization_area:
                self.view.update_visualization_area_display(pn.Column(*[pn.pane.Alert(e, alert_type='danger') for e in errors]))
            return False, {}

        # Prepare payload for single-input service
        payload = {"data_container": data_container}
        return True, payload

    # The _handle_visualize_base method from the base class will handle the rest
    # Remove the old _handle_visualize, _show_error_and_reset, _reset_visualize_state methods

    def get_view_panel(self) -> pn.layout.Panel:
        # Ensure view exists before getting panel
        return self.view.get_panel() if self.view else pn.pane.Alert("Exploration View not initialized.", alert_type='danger') 