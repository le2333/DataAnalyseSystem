import param
import panel as pn
from model.data_manager import DataManager
from model.data_container import DataContainer # For type hint
from model.timeseries_data import TimeSeriesData
from model.multidim_data import MultiDimData
from view.process_view import ProcessView
from services.registry import PREPROCESSORS
from typing import List, Dict, Optional, Any
import traceback

class ProcessController(param.Parameterized):
    """处理 ProcessView 的交互，调用预处理服务。"""

    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)

    # 内部状态
    is_processing = param.Boolean(default=False, precedence=-1)

    def __init__(self, data_manager: DataManager, **params):
        view_instance = ProcessView(data_manager=data_manager)
        super().__init__(data_manager=data_manager, view=view_instance, **params)
        self._bind_events()

    def _bind_events(self):
        self.view.preprocess_button.on_click(self._handle_preprocess)

    # 由 AppController 调用，设置视图中选定的数据
    def set_selected_data(self, selected_ids: List[str]):
        self.view.selected_data_ids = selected_ids

    def _handle_preprocess(self, event):
        if self.is_processing:
            self.view.show_status("正在处理中，请稍候...", alert_type='warning')
            return

        config = self.view.get_process_config()
        if not config:
            self.view.show_status("配置错误或未选择服务/数据。", alert_type='danger')
            return

        self.is_processing = True
        self.view.preprocess_button.loading = True
        self.view.hide_status() # 清除旧状态

        service_name = config['service_name']
        selected_ids = config['selected_data_ids']
        params = config['params']

        service_info = PREPROCESSORS.get(service_name)
        if not service_info:
            self._show_error_and_reset(f"未找到服务: {service_name}")
            return

        service_func = service_info['function']
        input_type = service_info.get('input_type') # 可能为 None
        accepts_list_flag = service_info.get('accepts_list', False) # Get the flag

        try:
            # --- 处理接受列表输入的服务 --- #
            if accepts_list_flag:
                # 验证输入类型 (假设服务文档或 input_type 提供了预期类型)
                # 这里我们仍然硬编码检查 TimeSeriesData，因为该服务特定需要它
                # 更通用的方法可能需要更丰富的类型系统或服务元数据
                data_containers_list = []
                valid = True
                for data_id in selected_ids:
                    dc = self.data_manager.get_data(data_id)
                    if not isinstance(dc, TimeSeriesData):
                        self._show_error_and_reset(f"'{service_name}' 要求所有输入都是时间序列数据，但 '{dc.name}' ({dc.data_type}) 不是。")
                        valid = False
                        break
                    data_containers_list.append(dc)
                if not valid:
                    return

                # 调用服务，传递列表和从 params 获取的额外参数
                # 服务的第一个参数预期是列表 (e.g., data_containers=...)
                # 我们需要知道参数名，假设是 'data_containers'
                # 更健壮的方式是约定或从服务元数据获取参数名
                payload = {'data_containers': data_containers_list}
                result_data = service_func(**payload, **params)

                # 处理单个结果
                if isinstance(result_data, DataContainer):
                    new_id = self.data_manager.add_data(result_data)
                    self.view.show_status(f"成功: 操作 '{service_name}' 完成。新数据 '{result_data.name}' ({new_id[:8]}) 已添加。", alert_type='success')
                else:
                     self.view.show_status(f"警告: '{service_name}' 未返回有效的数据容器。", alert_type='warning')

            # --- 处理接受单个输入的标准服务 --- #
            elif input_type and issubclass(input_type, DataContainer):
                results_added = 0
                errors_occurred = []
                for data_id in selected_ids:
                    data_container = self.data_manager.get_data(data_id)
                    if not data_container:
                        errors_occurred.append(f"跳过: 未找到 ID {data_id}")
                        continue
                    if not isinstance(data_container, input_type):
                        errors_occurred.append(f"跳过: '{service_name}' 不适用于 '{data_container.name}' (类型 {data_container.data_type})，需要 {input_type.__name__}。")
                        continue
                    try:
                        # 服务的第一个参数预期是单个对象 (e.g., data_container=...)
                        # 假设参数名为 'data_container'
                        payload = {'data_container': data_container}
                        result_data = service_func(**payload, **params)

                        if isinstance(result_data, DataContainer):
                            new_id = self.data_manager.add_data(result_data)
                            results_added += 1
                        else:
                             errors_occurred.append(f"警告: '{service_name}' 应用于 '{data_container.name}' 后未返回有效数据容器。")
                    except Exception as item_e:
                        tb_str_item = traceback.format_exc()
                        print(f"Error processing item {data_container.name} with {service_name}:\n{tb_str_item}")
                        errors_occurred.append(f"错误: 应用 '{service_name}' 于 '{data_container.name}' 时失败: {item_e}")

                # 显示最终状态
                status_msg = f"处理完成。成功添加 {results_added} 个新数据项。"
                if errors_occurred:
                    status_msg += "\n发生以下问题:\n" + "\n".join(f"- {e}" for e in errors_occurred)
                    self.view.show_status(status_msg, alert_type='warning')
                elif results_added > 0:
                    self.view.show_status(status_msg, alert_type='success')
                else:
                    self.view.show_status("没有数据被处理或添加（可能由于类型不匹配或处理失败）。", alert_type='info')

            # --- 处理 input_type 为 None 且 accepts_list 为 False 的情况 --- #
            # (或者其他未明确处理的情况，例如服务期望原始类型如 DataFrame?)
            else:
                 # This case needs clarification: what kind of service fits here?
                 # Maybe a service operating without specific DataContainer input?
                 # Or a service whose input type wasn't registered correctly?
                 self._show_error_and_reset(f"无法处理服务 '{service_name}'：输入类型定义不清晰或不受支持 ({input_type})。")
                 return

        except Exception as e:
            tb_str = traceback.format_exc()
            print(f"Error during preprocessing service '{service_name}':\n{tb_str}")
            self._show_error_and_reset(f"执行服务 '{service_name}' 时出错: {e}")

        finally:
            self.is_processing = False
            self.view.preprocess_button.loading = False

    def _show_error_and_reset(self, message: str):
        """显示错误消息并重置状态。"""
        self.view.show_status(message, alert_type='danger')
        self.is_processing = False
        self.view.preprocess_button.loading = False

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 