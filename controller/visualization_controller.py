import param
import panel as pn
import holoviews as hv
from model.data_manager import DataManager
from model.timeseries_data import TimeSeriesData
from model.data_container import DataContainer # For typing
from view.visualization_view import VisualizationView # Updated import
from services.registry import VISUALIZERS, PREPROCESSORS # 访问注册表
from typing import List, Dict, Optional, Callable, Type
import traceback # For detailed error logging

class VisualizationController(param.Parameterized):
    """处理 VisualizationView 的交互，调用服务并更新 DataManager (同步版本)。"""

    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)

    # 处理状态
    is_processing = param.Boolean(default=False, precedence=-1)

    def __init__(self, data_manager: DataManager, **params):
        # 传递注册表给 View 用于生成选项
        view_instance = VisualizationView(data_manager=data_manager,
                                       visualizers=VISUALIZERS,
                                       preprocessors=PREPROCESSORS)
        super().__init__(data_manager=data_manager, view=view_instance, **params)
        self._bind_events()

    def _bind_events(self):
        self.view.visualize_button.on_click(self._handle_visualize)
        self.view.preprocess_button.on_click(self._handle_preprocess)

    def _call_service(self,
                            service_registry: dict,
                            config: dict,
                            success_callback: Optional[Callable] = None,
                            error_callback: Optional[Callable] = None):
        """通用服务调用逻辑。"""
        if self.is_processing or service_registry != PREPROCESSORS:
            return
        
        selected_ids = config.get('selected_data_ids', [])
        service_name = config.get('service_name')
        params = config.get('params', {})

        if not selected_ids:
            pn.state.notifications.warning("请至少选择一个数据项进行预处理。")
            return
        if not service_name:
            pn.state.notifications.warning("请选择要执行的预处理操作。")
            return

        service_info = service_registry.get(service_name)
        if not service_info:
            pn.state.notifications.error(f"未找到服务: {service_name}")
            return

        service_func = service_info['function']
        input_type = service_info.get('input_type')

        self.is_processing = True
        self.view.preprocess_button.loading = True

        errors = []
        all_success_callbacks_completed = True

        for selected_item in selected_ids:
            if isinstance(selected_item, tuple) and len(selected_item) == 2:
                data_id = selected_item[1]
                data_name_for_error = selected_item[0]
            else:
                errors.append(f"无效的选择项格式: {selected_item}")
                continue

            data_container = self.data_manager.get_data(data_id)
            if not data_container:
                errors.append(f"数据项 '{data_name_for_error}' ({data_id[:8]}...) 未找到")
                continue

            if input_type and not isinstance(data_container, input_type):
                 errors.append(f"操作 '{service_name}' 不适用于数据类型 '{data_container.data_type}' (来自: {data_container.name})")
                 continue

            try:
                current_params = params.copy()
                result_data = service_func(data_container=data_container, **current_params)

                if success_callback:
                    try:
                         success_callback(result_data, data_container, service_name, current_params)
                    except Exception as cb_e:
                         errors.append(f"处理服务 '{service_name}' 成功回调时出错 (数据: {data_container.name}): {cb_e}")
                         all_success_callbacks_completed = False

            except Exception as e:
                 error_msg = f"执行 '{service_name}' 于 '{data_container.name}' 时失败: {e}"
                 errors.append(error_msg)
                 if error_callback:
                     try:
                          error_callback(e, data_container, service_name, current_params)
                     except Exception as cb_e:
                          print(f"执行服务 '{service_name}' 的错误回调时出错: {cb_e}")

        self.is_processing = False
        self.view.preprocess_button.loading = False

        if errors:
            pn.state.notifications.error("预处理过程中发生错误:\n" + "\n".join(f"- {e}" for e in errors), duration=10000)
        elif all_success_callbacks_completed:
             pn.state.notifications.success(f"预处理操作 '{service_name}' 已成功应用于所选数据项。", duration=5000)

    # --- Visualization Handler (Simplified) --- #

    def _handle_visualize(self, event):
        if self.is_processing:
            pn.state.notifications.warning("正在处理中，请稍候...")
            return

        config = self.view.get_visualization_config()
        visualize_results_area = self.view.visualization_area
        visualize_results_area.clear()
        visualize_results_area.loading = True
        self.view.visualize_button.loading = True
        self.is_processing = True

        selected_ids_tuples = config.get('selected_data_ids', [])
        service_name = config.get('service_name')
        user_params = config.get('params', {})

        # --- Basic Input Validation --- #
        if not selected_ids_tuples:
            pn.state.notifications.warning("请至少选择一个数据项进行可视化。")
            self._reset_visualize_state()
            visualize_results_area.append(pn.pane.Alert("请先选择数据", alert_type='warning'))
            return

        if not service_name:
            pn.state.notifications.warning("请选择要使用的可视化方法。")
            self._reset_visualize_state()
            visualize_results_area.append(pn.pane.Alert("请先选择可视化方法", alert_type='warning'))
            return

        service_info = VISUALIZERS.get(service_name)
        if not service_info:
            pn.state.notifications.error(f"未找到可视化服务: {service_name}")
            self._reset_visualize_state()
            visualize_results_area.append(pn.pane.Alert(f"服务 '{service_name}' 不可用", alert_type='danger'))
            return

        # --- Get Service Info and Expected Input Type --- #
        service_func = service_info.get('function')
        # Check the registered input_type (assuming it's List[SpecificType] or SpecificType)
        expected_input_type_info = service_info.get('input_type')

        if not service_func or not callable(service_func):
            pn.state.notifications.error(f"服务 '{service_name}' 配置错误，缺少有效函数。")
            self._reset_visualize_state()
            return

        # --- Prepare Data List and Validate Types --- #
        data_containers_list: List[DataContainer] = []
        errors = []
        expected_item_type: Optional[Type] = None

        # Determine the expected *item* type if input is List[Type]
        # This is a simple check; more robust checking might use typing.get_args
        if isinstance(expected_input_type_info, list) and expected_input_type_info: # Basic check for List[Type]
             expected_item_type = expected_input_type_info[0]
        elif isinstance(expected_input_type_info, type):
             expected_item_type = expected_input_type_info # Service expects single item
             # If service expects single item but multiple selected, maybe error or take first?
             # For this specific refactor, we assume the service handles a list.

        for item_tuple in selected_ids_tuples:
            if not (isinstance(item_tuple, tuple) and len(item_tuple) == 2):
                 errors.append(f"错误的数据选择格式: {item_tuple}")
                 continue
            data_id = item_tuple[1]
            data_name = item_tuple[0]
            data_container = self.data_manager.get_data(data_id)

            if not data_container:
                errors.append(f"数据项 '{data_name}' ({data_id[:8]}...) 未找到")
                continue

            # Check if the item type matches what the service expects
            if expected_item_type and not isinstance(data_container, expected_item_type):
                errors.append(f"可视化 '{service_name}' 不适用于数据类型 '{data_container.data_type}' (来自: {data_container.name})。需要: {expected_item_type.__name__}")
                continue # Skip this item

            data_containers_list.append(data_container)

        # --- Handle Validation Errors --- #
        if errors:
             # Show all errors collected during data preparation
             pn.state.notifications.error("数据准备阶段出错:\n" + "\n".join(f"- {e}" for e in errors), duration=10000)
             visualize_results_area.append(pn.Column(*[pn.pane.Alert(e, alert_type='danger') for e in errors]))
             self._reset_visualize_state()
             return

        if not data_containers_list:
            pn.state.notifications.warning("没有找到适用于所选可视化操作的有效数据。")
            visualize_results_area.append(pn.pane.Alert("无有效数据可供显示", alert_type='warning'))
            self._reset_visualize_state()
            return

        # --- Call the Service (Once) --- #
        try:
            # Pass the prepared list and user parameters
            final_layout = service_func(
                data_containers=data_containers_list,
                **user_params
            )

            # --- Update View --- #
            self.view.update_visualization_area(final_layout)
            pn.state.notifications.success(f"可视化 '{service_name}' 已生成。", duration=5000)

        except Exception as e:
            # --- Handle Service Execution Error --- #
            tb_str = traceback.format_exc()
            print(f"Error during visualization service '{service_name}':\n{tb_str}")
            error_msg = f"执行可视化服务 '{service_name}' 时出错: {e}"
            errors.append(error_msg)
            pn.state.notifications.error(error_msg, duration=8000)
            visualize_results_area.append(pn.pane.Alert(error_msg, alert_type='danger'))

        finally:
            # --- Reset State --- #
            self._reset_visualize_state()

    def _reset_visualize_state(self):
        """Helper to reset loading state."""
        self.is_processing = False
        self.view.visualize_button.loading = False
        self.view.visualization_area.loading = False

    # --- Preprocessing Handler (Keep as is or adapt if needed) --- #
    def _handle_preprocess(self, event):
        # Use the generic _call_service for preprocessing
        config = self.view.get_preprocess_config()
        self.view.hide_preprocess_status()

        def success_cb(new_data_container, source_container, service_name, params):
            if isinstance(new_data_container, DataContainer):
                new_name = f"{source_container.name}_{service_name}"
                new_data_container._source_ids = [source_container.id]
                new_data_container._operation_info = {'name': service_name, 'params': params}
                new_id = self.data_manager.add_data(new_data_container)
                self.view.show_preprocess_status(f"成功: '{service_name}' 应用于 '{source_container.name}'。新数据 '{new_data_container.name}' ({new_id[:8]}) 已添加。", alert_type='success') # Slightly shorter msg
            else:
                 self.view.show_preprocess_status(f"警告: 服务 '{service_name}' 未返回有效数据容器 (数据: {source_container.name})。", alert_type='warning')

        def error_cb(error, source_container, service_name, params):
            self.view.show_preprocess_status(f"错误: 执行 '{service_name}' 于 '{source_container.name}' 时失败: {error}", alert_type='danger')

        # Ensure _call_service handles PREPROCESSORS correctly
        self._call_service(PREPROCESSORS, config, success_callback=success_cb, error_callback=error_cb)

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 