import param
import panel as pn
import traceback
from typing import Optional, Dict, Any, List, Type
from model.data_manager import DataManager
from model.data_container import DataContainer
# Import view base or specific views if needed for type hinting
# from view.base_view import BaseView # Assuming a base view exists or use Any

class BaseVisualizationController(param.Parameterized):
    """Base controller for handling visualization views and services."""

    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1) # Should be a view with specific methods
    registry = param.Parameter(precedence=-1) # Service registry (e.g., VISUALIZERS)

    is_processing = param.Boolean(default=False, precedence=-1)

    def __init__(self, data_manager: DataManager, view_instance, registry: dict, **params):
        # Ensure view has the necessary methods/attributes before assigning
        required_attrs = [
            # 'get_visualization_config', # Check replaced below
            'update_visualization_area_display',
            'visualization_area',
            'visualize_button'
        ]
        if not all(hasattr(view_instance, attr) for attr in required_attrs):
            missing = [attr for attr in required_attrs if not hasattr(view_instance, attr)]
            raise TypeError(f"View instance missing required attributes: {missing}.")
        
        # Check for at least one config getter method
        if not hasattr(view_instance, 'get_visualization_config') and not hasattr(view_instance, 'get_exploration_config'):
             raise TypeError("View instance must provide either 'get_visualization_config' or 'get_exploration_config' method.")

        super().__init__(data_manager=data_manager, view=view_instance, registry=registry, **params)
        self._bind_events()

    def _bind_events(self):
        # Ensure view and button exist before binding
        if self.view and hasattr(self.view, 'visualize_button') and self.view.visualize_button:
             self.view.visualize_button.on_click(self._handle_visualize_base)
        else:
             # This might happen if view init is complex/delayed
             print(f"Warning: View or visualize_button not ready for binding in {self.__class__.__name__}.")
             # Optionally schedule re-binding
             # pn.state.schedule_task(0.1, self._bind_events) # Example retry

    # Method to be implemented by subclasses for data setup
    def set_selected_data(self, selected_ids: List[str] | str):
        raise NotImplementedError("Subclasses must implement set_selected_data")

    # Base handler calling subclass implementation for validation and service call
    def _handle_visualize_base(self, event):
        if self.is_processing:
            self._notify("warning", "正在处理中，请稍候...")
            return

        # Get config using the appropriate method name
        config = None
        if hasattr(self.view, 'get_visualization_config'):
            config = self.view.get_visualization_config()
        elif hasattr(self.view, 'get_exploration_config'):
            config = self.view.get_exploration_config()
        
        if not config:
            self._notify("error", "获取可视化配置失败或视图不兼容。", duration=5000)
            return

        # Set loading state
        self._set_loading_state(True)

        try:
            service_name = config['service_name']
            user_params = config['params']

            service_info = self.registry.get(service_name)
            if not service_info:
                self._show_error_and_reset(f"未找到可视化服务: {service_name}")
                self.view.update_visualization_area_display(pn.pane.Alert(f"服务 '{service_name}' 不可用", alert_type='danger'))
                return

            service_func = service_info.get('function')
            if not service_func or not callable(service_func):
                self._show_error_and_reset(f"服务 '{service_name}' 配置错误，缺少有效函数。")
                return

            # --- Subclass specific logic --- #
            is_valid, data_payload = self._validate_data_and_get_payload(config, service_info)
            if not is_valid:
                # Error messages handled within _validate_data_and_get_payload
                self._reset_loading_state()
                return
            # --- End Subclass specific logic --- #

            # Call the service function with validated data payload
            final_layout = service_func(**data_payload, **user_params) # Pass data payload and user params

            self.view.update_visualization_area_display(final_layout)
            self._notify("success", f"可视化 '{service_name}' 已生成。", duration=5000)

        except Exception as e:
            tb_str = traceback.format_exc()
            # Attempt to get service_name again for error message, handle if config failed early
            failed_service_name = config.get('service_name', '未知')
            print(f"Error during visualization service '{failed_service_name}':\n{tb_str}")
            error_msg = f"执行可视化服务 '{failed_service_name}' 时出错: {e}"
            self._show_error_and_reset(error_msg)
            self.view.update_visualization_area_display(pn.pane.Alert(error_msg, alert_type='danger'))

        finally:
            self._reset_loading_state()

    # Method to be implemented by subclasses for data validation and payload preparation
    def _validate_data_and_get_payload(self, config: Dict, service_info: Dict) -> tuple[bool, Dict[str, Any]]:
        """Validates data based on config/service_info and prepares the data payload for the service.
           Returns (is_valid, data_payload)
        """
        raise NotImplementedError("Subclasses must implement _validate_data_and_get_payload")

    # --- Helper Methods --- #
    def _set_loading_state(self, loading: bool):
        self.is_processing = loading
        if self.view:
            if hasattr(self.view, 'visualization_area') and self.view.visualization_area:
                self.view.visualization_area.loading = loading
            if hasattr(self.view, 'visualize_button') and self.view.visualize_button:
                self.view.visualize_button.loading = loading

    def _reset_loading_state(self):
        self._set_loading_state(False)

    def _notify(self, level: str, message: str, duration: int = 4000):
        """Safely send notifications using pn.state."""
        try:
            if level == "error":
                pn.state.notifications.error(message, duration=duration)
            elif level == "warning":
                pn.state.notifications.warning(message, duration=duration)
            elif level == "success":
                pn.state.notifications.success(message, duration=duration)
            else:
                pn.state.notifications.info(message, duration=duration)
        except AttributeError:
            print(f"Info ({level}): {message} (pn.state unavailable for notification)")
        except Exception as e:
            print(f"Error sending notification: {e}")

    def _show_error_and_reset(self, message: str):
        self._notify("error", message, duration=8000)
        self._reset_loading_state()

    def get_view_panel(self) -> pn.layout.Panel:
        # Ensure view exists before getting panel
        return self.view.get_panel() if self.view else pn.pane.Alert(f"{self.__class__.__name__} View not initialized.", alert_type='danger') 