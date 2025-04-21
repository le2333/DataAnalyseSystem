import param
import panel as pn
from model.data_manager import DataManager
from model.data_container import DataContainer # 类型提示
from view.unified_visualization_view import UnifiedVisualizationView # 导入统一视图
from services.registry import VISUALIZERS
from typing import List, Dict, Optional, Any, Type, get_origin, Tuple, Union
import traceback
# 导入基类控制器
from .base_visualization_controller import BaseVisualizationController

class UnifiedVisualizationController(BaseVisualizationController):
    """处理 UnifiedVisualizationView 的交互，调用单输入或列表输入的可视化服务。"""

    def __init__(self, data_manager: DataManager, **params):
        """初始化控制器和统一可视化视图。"""
        # 实例化视图，并将控制器自身传递给视图
        view_instance = UnifiedVisualizationView(data_manager=data_manager, controller=self)
        # 调用基类初始化
        super().__init__(data_manager=data_manager, view_instance=view_instance, **params)
        # 视图内部负责监听控制器 visualization_content 的变化来更新显示区域

    # 实现基类定义的抽象方法
    def set_selected_data(self, selected_ids: Union[List[str], str]):
        """设置视图中选定的数据 ID（单个或多个）。"""
        if self.view:
            if isinstance(selected_ids, str):
                self.view.selected_data_ids = [selected_ids] # 统一为列表
            elif isinstance(selected_ids, list):
                self.view.selected_data_ids = selected_ids
            else:
                 print(f"警告: 在 {self.__class__.__name__} 中设置 selected_ids 时收到无效类型: {type(selected_ids)}。将被清空。")
                 self.view.selected_data_ids = [] # 无效类型则清空
        else:
            print(f"警告: 无法在 {self.__class__.__name__} 中设置选定数据 ID，视图尚未初始化。")

    def _validate_list_input_for_visualization(self, service_name: str, selected_ids: List[str], 
                                                 expected_input_type_info: Any) -> Tuple[bool, List[str], List[DataContainer]]:
        """验证服务要求的列表输入 (可视化/比较模式)。"""
        num_selected = len(selected_ids)
        data_containers_list: List[DataContainer] = []
        errors = []
        valid = True

        if num_selected < 2:
            errors.append(f"服务 '{service_name}' (比较模式) 需要至少选择两个数据项。")
            valid = False
        else:
            first_data_type: Optional[str] = None # 改为比较 data_type 字符串
            # expected_item_type = self._get_expected_list_item_type(expected_input_type_info) # 基类已移除此方法
            
            for i, data_id in enumerate(selected_ids):
                dc = self.data_manager.get_data(data_id)
                if not dc:
                    errors.append(f"数据项 ID: {data_id} 未找到。")
                    valid = False; continue # 标记无效，继续检查其他ID
                
                current_data_type = dc.data_type # 获取 data_type
                # 检查与第一个元素的 data_type 是否一致
                if i == 0:
                    first_data_type = current_data_type
                    # 移除基于 expected_item_type 的检查
                    # if expected_item_type and not issubclass(first_type, expected_item_type):
                    #     errors.append(f"服务 '{service_name}' 需要 {expected_item_type.__name__} 类型，但第一个数据项是 {first_type.__name__}。")
                    #     valid = False; break
                elif current_data_type != first_data_type:
                    errors.append(f"比较模式要求所有选定数据项具有相同的类型 (data_type)，发现 '{first_data_type}' 和 '{current_data_type}'。")
                    valid = False; break # 类型不一致，无需继续比较
                    
                data_containers_list.append(dc)
            
            # 如果循环因为 break 提前结束，或者中途 valid 被设为 False，这里 data_containers_list 可能不完整或无效
            if not valid:
                 data_containers_list.clear() # 清空可能不完整的列表

        return valid, errors, data_containers_list

    def _validate_single_input_for_visualization(self, service_name: str, selected_ids: List[str], 
                                                   expected_input_type_info: Any) -> Tuple[bool, List[str], Optional[DataContainer]]:
        """验证服务要求的单个输入 (可视化/探索模式)。"""
        num_selected = len(selected_ids)
        data_container: Optional[DataContainer] = None
        errors = []
        valid = True

        if num_selected != 1:
            errors.append(f"服务 '{service_name}' (探索模式) 一次只能处理一个数据项，但选择了 {num_selected} 个。")
            valid = False
        else:
            data_id = selected_ids[0]
            dc = self.data_manager.get_data(data_id)
            if not dc:
                errors.append(f"数据项 ID: {data_id} 未找到。")
                valid = False
            # 移除基于 expected_input_type_info 的 isinstance 检查
            # elif expected_input_type_info and isinstance(expected_input_type_info, type) and not isinstance(dc, expected_input_type_info):
            #      errors.append(f"服务 '{service_name}' 需要 {expected_input_type_info.__name__} 类型，但选择的数据项是 {type(dc).__name__}。")
            #      valid = False
            else:
                data_container = dc
                
        return valid, errors, data_container

    # 实现基类定义的抽象方法
    def _validate_config_and_get_payload(self, config: Dict, service_info: Dict) -> tuple[bool, Dict[str, Any]]:
        """根据服务要求（单个或列表输入）验证选定的数据。"""
        selected_ids = config.get('selected_data_ids', [])
        service_name = config.get('service_name')
        expected_input_type_info = service_info.get('input_type')
        accepts_list_flag = service_info.get('accepts_list', False)
        # 获取服务期望的输入参数名 (强制服务注册时提供可能更佳)
        default_list_param = 'data_containers'
        default_single_param = 'data_container'
        input_param_name = service_info.get('input_param_name', 
                                         default_list_param if accepts_list_flag else default_single_param)

        errors = []
        payload = {}
        valid = False
        
        # 判断服务是否期望列表输入
        # 注意: 这里的 expected_input_type_info 现在通常是 DataContainer 或 List[DataContainer]
        # 因此 get_origin(expected_input_type_info) is list 可能不再可靠地指示服务期望列表
        # 强烈依赖 accepts_list_flag
        expects_list = accepts_list_flag
        # 也可以保留 get_origin 检查作为辅助判断，但 accepts_list 优先级更高
        # expects_list = accepts_list_flag or (get_origin(expected_input_type_info) is list)

        if expects_list:
            valid, list_errors, data_list = self._validate_list_input_for_visualization(
                service_name, selected_ids, expected_input_type_info # expected_input_type_info 仍然传递，但内部不再使用它进行类型检查
            )
            errors.extend(list_errors)
            if valid:
                # 使用服务定义的列表输入参数名
                list_input_param_name = service_info.get('input_param_name', default_list_param)
                payload[list_input_param_name] = data_list
        else:
            # 假设服务期望单个 DataContainer
            valid, single_errors, data_single = self._validate_single_input_for_visualization(
                service_name, selected_ids, expected_input_type_info # 同样，内部不再检查 expected_input_type_info
            )
            errors.extend(single_errors)
            if valid:
                 # 使用服务定义的单输入参数名
                 single_input_param_name = service_info.get('input_param_name', default_single_param)
                 payload[single_input_param_name] = data_single
        
        # 处理验证错误
        if not valid or errors:
            # 如果 valid 为 False 但 errors 为空 (例如，列表输入少于2个)，确保有错误信息
            if not errors:
                errors.append("未知数据验证错误。") # 或者更具体的默认错误
            error_summary = "数据验证失败:\n" + "\n".join(f"- {e}" for e in errors)
            # 通过基类方法更新 visualization_content 和显示通知
            self._handle_service_error(error_summary, service_name)
            return False, {}

        # 验证通过
        return True, payload

    # _handle_service_result 方法由 BaseVisualizationController 处理
    # 它会更新 self.visualization_content，视图应监听此参数

    def get_view_panel(self) -> pn.layout.Panel:
        """获取视图面板，确保视图已初始化。"""
        return self.view.get_panel() if self.view else pn.pane.Alert("统一可视化视图尚未初始化。", alert_type='danger') 