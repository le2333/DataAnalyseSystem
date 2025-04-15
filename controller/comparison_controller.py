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
from typing import List, Dict, Optional, Any, Type
import traceback

class ComparisonController(param.Parameterized):
    """处理 ComparisonView 的交互，调用可视化服务。"""

    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)

    # 内部状态
    is_processing = param.Boolean(default=False, precedence=-1)

    def __init__(self, data_manager: DataManager, **params):
        # Use ComparisonView
        view_instance = ComparisonView(data_manager=data_manager)
        super().__init__(data_manager=data_manager, view=view_instance, **params)
        self._bind_events()

    def _bind_events(self):
        self.view.visualize_button.on_click(self._handle_visualize)

    # 由 AppController 调用，设置视图中选定的数据
    def set_selected_data(self, selected_ids: List[str]):
        self.view.selected_data_ids = selected_ids

    def _handle_visualize(self, event):
        if self.is_processing:
            pn.state.notifications.warning("正在处理中，请稍候...")
            return

        config = self.view.get_visualization_config()
        if not config:
            pn.state.notifications.error("获取可视化配置失败。", duration=5000)
            return

        visualize_results_area = self.view.visualization_area
        visualize_results_area.clear()
        visualize_results_area.loading = True
        self.view.visualize_button.loading = True
        self.is_processing = True

        service_name = config['service_name']
        selected_ids = config['selected_data_ids']
        user_params = config['params']

        service_info = VISUALIZERS.get(service_name)
        if not service_info:
            self._show_error_and_reset(f"未找到可视化服务: {service_name}")
            visualize_results_area.append(pn.pane.Alert(f"服务 '{service_name}' 不可用", alert_type='danger'))
            return

        service_func = service_info.get('function')
        # Assume service input_type is List[ExpectedType]
        expected_input_type_info = service_info.get('input_type')
        expected_item_type: Optional[Type] = None
        if isinstance(expected_input_type_info, list) and expected_input_type_info:
            expected_item_type = expected_input_type_info[0]
        elif isinstance(expected_input_type_info, type):
             # This comparison view expects services that take lists
             self._show_error_and_reset(f"服务 '{service_name}' 配置错误：比较视图需要处理列表的服务。")
             return

        if not service_func or not callable(service_func):
            self._show_error_and_reset(f"服务 '{service_name}' 配置错误，缺少有效函数。")
            return

        # --- Prepare Data List and Validate Types --- #
        data_containers_list: List[DataContainer] = []
        errors = []

        if not selected_ids or len(selected_ids) < 2:
            errors.append("可视化比较需要至少选择两个数据项。")

        first_type = None
        for i, data_id in enumerate(selected_ids):
            data_container = self.data_manager.get_data(data_id)
            if not data_container:
                errors.append(f"数据项 ID: {data_id} 未找到")
                continue

            # Check type consistency
            if i == 0:
                first_type = type(data_container)
                # Check if the first item matches the expected type
                if expected_item_type and not isinstance(data_container, expected_item_type):
                     errors.append(f"可视化 '{service_name}' 需要 {expected_item_type.__name__} 类型的数据，但第一个是 {first_type.__name__}。")
                     # Stop validation early if the first is wrong
                     break
            elif type(data_container) != first_type:
                errors.append("可视化比较要求所有选定数据类型相同。")
                # Stop validation early on type mismatch
                break

            data_containers_list.append(data_container)

        # If expected_item_type is set, ensure the found type matches
        if expected_item_type and first_type != expected_item_type:
             # Error message might have been added already, but double check
             if not any(f"需要 {expected_item_type.__name__}" in e for e in errors):
                 errors.append(f"可视化 '{service_name}' 需要 {expected_item_type.__name__} 类型的数据，但找到的是 {first_type.__name__ if first_type else '未知'}。")

        # --- Handle Validation Errors --- #
        if errors:
             pn.state.notifications.error("数据验证失败:\n" + "\n".join(f"- {e}" for e in errors), duration=10000)
             visualize_results_area.append(pn.Column(*[pn.pane.Alert(e, alert_type='danger') for e in errors]))
             self._reset_visualize_state()
             return

        # --- Call the Service --- #
        try:
            final_layout = service_func(
                data_containers=data_containers_list,
                **user_params
            )
            self.view.update_visualization_area(final_layout)
            pn.state.notifications.success(f"可视化 '{service_name}' 已生成。", duration=5000)

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error during comparison visualization service '{service_name}':\n{tb_str}")
            error_msg = f"执行可视化服务 '{service_name}' 时出错: {e}"
            self._show_error_and_reset(error_msg)
            visualize_results_area.append(pn.pane.Alert(error_msg, alert_type='danger'))

        finally:
            self._reset_visualize_state()

    def _show_error_and_reset(self, message: str):
        """Helper to show error notification and reset state."""
        pn.state.notifications.error(message, duration=8000)
        self.is_processing = False
        self.view.visualize_button.loading = False
        self.view.visualization_area.loading = False

    def _reset_visualize_state(self):
        """Helper to reset loading state."""
        self.is_processing = False
        self.view.visualize_button.loading = False
        self.view.visualization_area.loading = False

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 