import param
import panel as pn
import holoviews as hv
from model.data_manager import DataManager
from model.data_container import DataContainer
from view.exploration_view import ExplorationView # Use the new view
from services.registry import VISUALIZERS
from typing import List, Dict, Optional, Any, Type
import traceback

class ExplorationController(param.Parameterized):
    """处理 ExplorationView 的交互，调用动态可视化服务。"""

    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)

    # 内部状态
    is_processing = param.Boolean(default=False, precedence=-1)

    def __init__(self, data_manager: DataManager, **params):
        view_instance = ExplorationView(data_manager=data_manager)
        super().__init__(data_manager=data_manager, view=view_instance, **params)
        self._bind_events()

    def _bind_events(self):
        # Ensure view and button exist before binding
        if self.view and hasattr(self.view, 'visualize_button') and self.view.visualize_button:
             self.view.visualize_button.on_click(self._handle_visualize)
        else:
             print("Warning: ExplorationView or visualize_button not ready for binding.")

    # 由 AppController 调用，设置视图中选定的单个数据 ID
    def set_selected_data(self, selected_id: str):
        if self.view:
             self.view.selected_data_id = selected_id

    def _handle_visualize(self, event):
        if self.is_processing:
            # Use defensive pn.state access for notification
            try:
                 pn.state.notifications.warning("正在处理中，请稍候...")
            except AttributeError:
                 print("Warning: Cannot show processing notification (pn.state is None).")
            return

        # Ensure view exists before accessing config
        if not self.view:
             print("Error: ExplorationView is not available.")
             return

        config = self.view.get_exploration_config()
        if not config:
            try:
                 pn.state.notifications.error("获取探索配置失败。", duration=5000)
            except AttributeError:
                 print("Error: Cannot show config error notification (pn.state is None).")
            return

        visualize_results_area = self.view.visualization_area
        # Clear area directly instead of relying on watcher
        if visualize_results_area:
             visualize_results_area.clear()
             visualize_results_area.loading = True
        if self.view.visualize_button:
             self.view.visualize_button.loading = True
        self.is_processing = True

        service_name = config['service_name']
        selected_id = config['selected_data_id']
        user_params = config['params']

        service_info = VISUALIZERS.get(service_name)
        if not service_info:
            error_msg = f"未找到可视化服务: {service_name}"
            self._show_error_and_reset(error_msg)
            if visualize_results_area:
                 visualize_results_area.append(pn.pane.Alert(f"服务 '{service_name}' 不可用", alert_type='danger'))
            return

        service_func = service_info.get('function')
        expected_input_type = service_info.get('input_type')
        if not service_func or not callable(service_func):
            error_msg = f"服务 '{service_name}' 配置错误，缺少有效函数。"
            self._show_error_and_reset(error_msg)
            return

        data_container = self.data_manager.get_data(selected_id)
        errors = []
        if not data_container:
            errors.append(f"数据项 ID: {selected_id} 未找到")
        elif expected_input_type and not isinstance(data_container, expected_input_type):
            errors.append(f"可视化 '{service_name}' 需要 {expected_input_type.__name__} 类型数据，但选择的是 {type(data_container).__name__}。")

        if errors:
            error_summary = "数据验证失败:\n" + "\n".join(f"- {e}" for e in errors)
            try:
                 pn.state.notifications.error(error_summary, duration=10000)
            except AttributeError:
                 print(f"Error: Cannot show validation error notification (pn.state is None). Details:\n{error_summary}")
            if visualize_results_area:
                 visualize_results_area.append(pn.Column(*[pn.pane.Alert(e, alert_type='danger') for e in errors]))
            self._reset_visualize_state()
            return

        try:
            # Call the service
            final_layout = service_func(
                data_container=data_container,
                **user_params
            )
            # Directly update the view content
            if self.view:
                 self.view.update_visualization_area(final_layout)

            # Defensive success notification
            try:
                 pn.state.notifications.success(f"可视化 '{service_name}' 已生成。", duration=5000)
            except AttributeError:
                 print(f"Info: Visualization '{service_name}' generated (pn.state was None for notification).")

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error during exploration visualization service '{service_name}':\n{tb_str}")
            error_msg = f"执行可视化服务 '{service_name}' 时出错: {e}"
            self._show_error_and_reset(error_msg)
            if visualize_results_area:
                 # Use update_visualization_area to display the error message pane
                 self.view.update_visualization_area(pn.pane.Alert(error_msg, alert_type='danger'))

        finally:
            self._reset_visualize_state()

    def _show_error_and_reset(self, message: str):
        # Defensive error notification
        try:
             pn.state.notifications.error(message, duration=8000)
        except AttributeError:
             print(f"Error: Cannot show error notification (pn.state is None). Message: {message}")
        self._reset_visualize_state()

    def _reset_visualize_state(self):
        self.is_processing = False
        if self.view and self.view.visualize_button:
             self.view.visualize_button.loading = False
        if self.view and self.view.visualization_area:
             self.view.visualization_area.loading = False

    def get_view_panel(self) -> pn.layout.Panel:
        # Ensure view exists before getting panel
        return self.view.get_panel() if self.view else pn.pane.Alert("Exploration View not initialized.", alert_type='danger') 