import param
import panel as pn
from model.data_manager import DataManager
from model.data_container import DataContainer # 只导入基类
from view.process_view import ProcessView
from services.registry import PREPROCESSORS
from typing import List, Dict, Optional, Any, Type, Tuple
import traceback
from .base_service_controller import BaseServiceController # 导入基类

class ProcessController(BaseServiceController):
    """处理 ProcessView 的交互，调用预处理服务。继承自 BaseServiceController。"""

    # data_manager, view, is_processing 由基类提供

    # --- BaseServiceController 接口实现 ---

    @property
    def registry(self) -> dict:
        return PREPROCESSORS

    def _get_config_from_view(self) -> Optional[Dict[str, Any]]:
        config = self.view.get_process_config()
        if not config:
            self.view.show_status("配置错误或未选择服务/数据。", alert_type='danger')
            return None
        if 'service_name' not in config or 'selected_data_ids' not in config or 'params' not in config:
             self.view.show_status("视图返回的配置不完整。", alert_type='danger')
             return None
        return config

    def _get_service_button(self) -> Optional[pn.widgets.Button]:
        return getattr(self.view, 'preprocess_button', None)

    def _get_output_area(self) -> Optional[pn.layout.Panel]:
        # 使用 preprocess_status 作为输出区域来显示消息
        return getattr(self.view, 'preprocess_status', None)
        
    def _validate_list_input(self, service_name: str, selected_ids: List[str], input_type: Any) -> Tuple[bool, List[str], List[DataContainer]]:
        """验证服务要求的列表输入。"""
        data_containers_list = []
        errors = []
        valid = True
        
        for data_id in selected_ids:
            dc = self.data_manager.get_data(data_id)
            if not dc:
                 errors.append(f"未找到 ID: {data_id}")
                 valid = False
                 continue
            data_containers_list.append(dc)
        
        if valid and not data_containers_list:
            errors.append("没有有效的输入数据可用于列表处理服务。")
            valid = False
            
        return valid, errors, data_containers_list

    def _validate_single_input(self, service_name: str, selected_ids: List[str], input_type: Type[DataContainer]) -> Tuple[bool, List[str], Optional[DataContainer]]:
        """验证服务要求的单个输入。"""
        data_container = None
        errors = []
        valid = True
        
        if len(selected_ids) != 1:
             errors.append(f"服务 '{service_name}' 一次只能处理一个数据项，但选择了 {len(selected_ids)} 个。")
             valid = False
        else:
             data_id = selected_ids[0]
             data_container = self.data_manager.get_data(data_id)
             if not data_container:
                 errors.append(f"未找到 ID {data_id}")
                 valid = False
                 
        return valid, errors, data_container

    def _validate_config_and_get_payload(self, config: Dict, service_info: Dict) -> tuple[bool, Dict[str, Any]]:
        """验证预处理配置和数据，准备 payload。"""
        service_name = config['service_name']
        selected_ids = config['selected_data_ids']
        input_type = service_info.get('input_type')
        accepts_list_flag = service_info.get('accepts_list', False)
        
        default_list_param = 'data_containers'
        default_single_param = 'data_container'
        input_param_name = service_info.get('input_param_name', 
                                         default_list_param if accepts_list_flag else default_single_param)

        payload = {}
        errors = []

        if not selected_ids:
            errors.append("未选择要处理的数据项。")
        else:
            valid = False # 初始化为 False
            if accepts_list_flag:
                valid, list_errors, data_list = self._validate_list_input(service_name, selected_ids, input_type)
                errors.extend(list_errors)
                if valid:
                    payload[input_param_name] = data_list
            
            elif input_type and isinstance(input_type, type) and issubclass(input_type, DataContainer):
                valid, single_errors, data_single = self._validate_single_input(service_name, selected_ids, input_type)
                errors.extend(single_errors)
                if valid:
                    payload[input_param_name] = data_single
            
            elif not accepts_list_flag: 
                 errors.append(f"服务 '{service_name}' 的输入配置无效：期望单个 DataContainer 输入，但注册信息不匹配 ({input_type})。")

        if errors:
            error_summary = "数据验证失败:\n" + "\n".join(f"- {e}" for e in errors)
            self._handle_service_error(error_summary, service_name)
            return False, {}

        # 验证通过且 payload 已准备好
        return True, payload

    def _handle_service_result(self, result: Any, service_name: str, config: Dict):
        """处理预处理服务的结果：添加新数据并显示状态。"""
        results_added = 0
        errors_occurred = []
        new_data_info = []

        # 服务可能返回单个 DataContainer 或列表
        results_to_process = []
        if isinstance(result, DataContainer):
            results_to_process.append(result)
        elif isinstance(result, list) and all(isinstance(item, DataContainer) for item in result):
            results_to_process = result
        elif result is not None:
             # 如果服务返回了非 None 但不是预期类型的结果
             errors_occurred.append(f"服务 '{service_name}' 返回了意外类型的结果: {type(result)}。")

        # 处理有效结果
        for res_data in results_to_process:
            try:
                new_id = self.data_manager.add_data(res_data)
                results_added += 1
                new_data_info.append(f"- {res_data.name} (ID: {new_id[:8]})")
            except Exception as add_e:
                 errors_occurred.append(f"添加结果数据 '{getattr(res_data, 'name', '未知')}' 时出错: {add_e}")

        # 显示最终状态
        if results_added > 0:
            status_msg = f"处理成功: 服务 '{service_name}' 完成。添加了 {results_added} 个新数据项:\n" + "\n".join(new_data_info)
            alert_type = 'success'
            if errors_occurred:
                status_msg += "\n\n但也发生以下问题:\n" + "\n".join(f"- {e}" for e in errors_occurred)
                alert_type = 'warning' # 部分成功
            self.view.show_status(status_msg, alert_type=alert_type)
        elif errors_occurred:
             status_msg = f"处理失败: 服务 '{service_name}' 未成功添加任何数据。\n发生以下问题:\n" + "\n".join(f"- {e}" for e in errors_occurred)
             self.view.show_status(status_msg, alert_type='danger')
        else:
             # 没有添加结果，也没有错误 (例如，服务没返回任何东西)
             self.view.show_status(f"服务 '{service_name}' 执行完毕，但未添加任何新数据。", alert_type='info')


    # --- 特定于 ProcessController 的方法 ---

    def __init__(self, data_manager: DataManager, **params):
        # 实例化视图
        view_instance = ProcessView(data_manager=data_manager)
        # 调用基类初始化
        super().__init__(data_manager=data_manager, view=view_instance, **params)
        # _bind_button_event 已由基类处理

    # 由 AppController 调用，设置视图中选定的数据
    def set_selected_data(self, selected_ids: List[str]):
        # 直接更新视图的参数，视图的 watcher 会处理后续更新
        self.view.selected_data_ids = selected_ids

    # --- 移除的方法 (移至 BaseServiceController 或不再需要) ---
    # _handle_preprocess -> 由基类 _handle_service_call_base 替代
    # _bind_events -> 由基类处理
    # _show_error_and_reset -> 由基类 _show_error_and_reset 替代
    # get_view_panel -> 由基类 get_view_panel 替代 