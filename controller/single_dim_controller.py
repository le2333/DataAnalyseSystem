import param
import panel as pn
import holoviews as hv
from model.data_manager import DataManager
from model.timeseries_data import TimeSeriesData
from model.data_container import DataContainer # For typing
from view.single_dim_view import SingleDimView # Updated import
from services.registry import VISUALIZERS, PREPROCESSORS # 访问注册表
from typing import List, Dict, Optional, Callable

class SingleDimController(param.Parameterized):
    """处理 SingleDimView 的交互，调用服务并更新 DataManager (同步版本)。"""

    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)

    # 处理状态
    is_processing = param.Boolean(default=False, precedence=-1)

    def __init__(self, data_manager: DataManager, **params):
        # 传递注册表给 View 用于生成选项
        view_instance = SingleDimView(data_manager=data_manager,
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
        if self.is_processing:
            return
        
        selected_ids = config.get('selected_data_ids', [])
        service_name = config.get('service_name')
        params = config.get('params', {})

        if not selected_ids:
            pn.state.notifications.warning("请至少选择一个数据项。")
            return
        if not service_name:
            pn.state.notifications.warning("请选择要执行的操作。")
            return

        service_info = service_registry.get(service_name)
        if not service_info:
            pn.state.notifications.error(f"未找到服务: {service_name}")
            return

        service_func = service_info['function']
        input_type = service_info.get('input_type')

        self.is_processing = True
        self.view.preprocess_button.loading = (service_registry == PREPROCESSORS)
        self.view.visualize_button.loading = (service_registry == VISUALIZERS)

        results = []
        errors = []
        all_success_callbacks_completed = True

        for selected_item in selected_ids:
            if isinstance(selected_item, tuple) and len(selected_item) == 2:
                data_id = selected_item[1] # 提取 ID (第二个元素)
                data_name_for_error = selected_item[0] # 用于错误消息
            else:
                # 如果 selected_ids 不是预期的元组列表，记录错误并跳过
                errors.append(f"无效的选择项格式: {selected_item}")
                continue

            data_container = self.data_manager.get_data(data_id) # 使用提取的 ID
            if not data_container:
                # 使用提取的名称显示错误
                errors.append(f"数据项 '{data_name_for_error}' ({data_id[:8]}...) 未找到")
                continue
            
            if input_type and not isinstance(data_container, input_type):
                 # 使用实际容器名称显示错误
                 errors.append(f"操作 '{service_name}' 不适用于数据类型 '{data_container.data_type}' (来自: {data_container.name})")
                 continue

            try:
                current_params = params.copy()
                
                # 直接同步调用服务
                result_data = service_func(
                    data_container=data_container,
                    **current_params 
                )
                results.append(result_data)
                
                if success_callback:
                    try:
                         # 直接同步调用回调
                         success_callback(result_data, data_container, service_name, current_params)
                    except Exception as cb_e:
                         errors.append(f"处理服务 '{service_name}' 成功回调时出错 (数据: {data_container.name}): {cb_e}")
                         all_success_callbacks_completed = False

            except Exception as e:
                 error_msg = f"执行 '{service_name}' 于 '{data_container.name}' 时失败: {e}"
                 errors.append(error_msg)
                 if error_callback:
                     try:
                          # 直接同步调用回调
                          error_callback(e, data_container, service_name, current_params)
                     except Exception as cb_e:
                          print(f"执行服务 '{service_name}' 的错误回调时出错: {cb_e}")

        self.is_processing = False
        self.view.preprocess_button.loading = False
        self.view.visualize_button.loading = False

        # 显示最终的错误信息
        if errors:
            pn.state.notifications.error("处理过程中发生错误:\n" + "\n".join(f"- {e}" for e in errors), duration=10000) 
        elif all_success_callbacks_completed and not errors: # Only show general success if no errors occurred
             pn.state.notifications.success(f"操作 '{service_name}' 已成功应用于所选数据项。", duration=5000)

        return results # 返回成功处理的结果列表

    # --- 具体操作的处理函数 --- #

    def _handle_visualize(self, event):
        config = self.view.get_visualization_config()
        visualize_results_area = self.view.visualization_area
        visualize_results_area.clear()
        visualize_results_area.loading = True
        
        # 回调改为 def
        def success_cb(plot_object, source_container, service_name, params):
            if isinstance(plot_object, (hv.Layout, hv.DynamicMap, hv.HoloMap)):
                 visualize_results_area.append(pn.pane.HoloViews(plot_object, sizing_mode='stretch_width'))
            elif isinstance(plot_object, pn.layout.Panel):
                 visualize_results_area.append(plot_object)
            else:
                 visualize_results_area.append(pn.pane.Alert(f"'{service_name}' 返回了无法显示的对象类型: {type(plot_object).__name__}", alert_type='warning'))
        
        # 回调改为 def
        def error_cb(error, source_container, service_name, params):
             visualize_results_area.append(pn.pane.Alert(f"为 '{source_container.name}' 生成可视化 '{service_name}' 失败: {error}", alert_type='danger'))

        self._call_service(VISUALIZERS, config, success_callback=success_cb, error_callback=error_cb)
        visualize_results_area.loading = False

    def _handle_preprocess(self, event):
        config = self.view.get_preprocess_config()
        self.view.hide_preprocess_status() # 开始处理前隐藏旧状态

        # 回调改为 def
        def success_cb(new_data_container, source_container, service_name, params):
            if isinstance(new_data_container, DataContainer):
                # 自动生成新名称
                new_name = f"{source_container.name}_{service_name}"
                # 传递源 ID 和操作信息
                new_data_container._source_ids = [source_container.id]
                new_data_container._operation_info = {'name': service_name, 'params': params}
                # 让 DataManager 处理重名
                new_id = self.data_manager.add_data(new_data_container)
                self.view.show_preprocess_status(f"成功执行 '{service_name}' 于 '{source_container.name}'。新数据项 '{new_data_container.name}' ({new_id[:8]}...) 已添加。", alert_type='success')
            else:
                 # 如果服务没按预期返回 DataContainer
                 self.view.show_preprocess_status(f"警告: 服务 '{service_name}' 在处理 '{source_container.name}' 后未返回有效的数据容器。", alert_type='warning')

        # 回调改为 def
        def error_cb(error, source_container, service_name, params):
            self.view.show_preprocess_status(f"错误: 执行 '{service_name}' 于 '{source_container.name}' 时失败: {error}", alert_type='danger')

        # 调用预处理服务
        self._call_service(PREPROCESSORS, config, success_callback=success_cb, error_callback=error_cb)

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 