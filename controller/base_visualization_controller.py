from abc import abstractmethod
import param
import panel as pn
import traceback
import holoviews as hv
from typing import Optional, Dict, Any, List, Type
from model.data_manager import DataManager
from model.data_container import DataContainer
from services.registry import VISUALIZERS # 导入可视化服务注册表
# Import view base or specific views if needed for type hinting
# from view.base_view import BaseView # Assuming a base view exists or use Any
from .base_service_controller import BaseServiceController # 导入新的基类

class BaseVisualizationController(BaseServiceController):
    """可视化控制器的抽象基类，继承自 BaseServiceController。
    
    使用 `visualization_content` 参数来传递可视化结果或错误信息给视图。
    """

    # data_manager, view, is_processing 由基类提供

    # 用于存放可视化结果或错误信息的参数 (视图应监听此参数)
    visualization_content = param.Parameter(precedence=-1)

    # --- BaseServiceController 接口实现 ---

    @property
    def registry(self) -> dict:
        return VISUALIZERS

    def _get_config_from_view(self) -> Optional[Dict[str, Any]]:
        """获取可视化配置。"""
        config = None
        # 假设所有相关视图都已更新为使用 get_visualization_config
        if hasattr(self.view, 'get_visualization_config') and callable(self.view.get_visualization_config):
            config = self.view.get_visualization_config()
        # 移除对旧方法 get_exploration_config 的兼容性检查
        # elif hasattr(self.view, 'get_exploration_config') and callable(self.view.get_exploration_config):
        #     config = self.view.get_exploration_config()
        
        if not config:
            # 配置失败时，设置错误内容以通知视图
            error_panel = pn.pane.Alert("获取可视化配置失败或视图不兼容。", alert_type='warning')
            self.visualization_content = error_panel 
            self._notify("error", "获取可视化配置失败或视图不兼容。", duration=5000)
            return None
            
        # 确保配置包含 service_name 和 params
        if 'service_name' not in config or 'params' not in config:
             error_panel = pn.pane.Alert("视图返回的配置缺少 'service_name' 或 'params'。", alert_type='warning')
             self.visualization_content = error_panel
             self._notify("error", "视图返回的配置缺少 'service_name' 或 'params'。", duration=5000)
             return None

        return config

    def _get_service_button(self) -> Optional[pn.widgets.Button]:
        """获取触发可视化服务的按钮。"""
        return getattr(self.view, 'visualize_button', None)

    # 移除 _get_output_area 方法，因为结果通过 visualization_content 传递
    # def _get_output_area(self) -> Optional[pn.layout.Panel]:
    #     return getattr(self.view, 'visualization_area', None)

    # 子类必须实现具体的验证和数据准备逻辑
    @abstractmethod
    def _validate_config_and_get_payload(self, config: Dict, service_info: Dict) -> tuple[bool, Dict[str, Any]]:
        raise NotImplementedError("可视化控制器子类必须实现 _validate_config_and_get_payload")

    def _handle_service_result(self, result: Any, service_name: str, config: Dict):
        """将可视化服务成功执行的结果设置到 visualization_content 参数。"""
        if result is not None:
             # 检查结果是否是可显示的对象
             if isinstance(result, (pn.viewable.Viewable, pn.layout.Panel, hv.Element)):
                  self.visualization_content = result
                  self._notify("success", f"服务 '{service_name}' 执行成功。")
             else:
                  # 如果结果类型不合适，显示警告
                  error_msg = f"服务 '{service_name}' 返回了无法直接显示的类型: {type(result)}。"
                  print(f"警告: {error_msg}")
                  self.visualization_content = pn.pane.Alert(error_msg, alert_type='warning')
                  self._notify("warning", error_msg)
        else:
             # 服务成功执行但未返回任何内容
             info_msg = f"服务 '{service_name}' 执行成功，但未返回可视化内容。"
             self.visualization_content = pn.pane.Alert(info_msg, alert_type='info')
             self._notify("info", info_msg)

    # 重写错误处理，将错误信息也设置到 visualization_content
    def _handle_service_error(self, error_message: str, service_name: str):
        """处理服务执行期间发生的错误，更新通知和 visualization_content。"""
        # 调用基类的 _notify 方法来显示瞬时通知 (基类 _handle_service_error 也会调用 _notify, 但我们在这里接管)
        # super()._handle_service_error(error_message, service_name) # 避免重复通知
        self._notify("error", f"服务 '{service_name}' 执行失败: {error_message}")
        # 同时更新可视化内容区域显示持久的错误信息
        self.visualization_content = pn.pane.Alert(f"执行服务 '{service_name}' 时出错:\n{error_message}", alert_type='danger')


    # --- 特定于可视化控制器的其他方法 --- #

    def __init__(self, data_manager: DataManager, view_instance, **params):
        """初始化，并检查视图实例是否符合基本要求。"""
        # 检查视图是否具有触发按钮和获取配置的方法
        required_methods = [
            'get_visualization_config', 
        ]
        required_attrs = [
            'visualize_button',
            # 移除了对 'visualization_area' 的检查
        ]
        if not all(hasattr(view_instance, method) and callable(getattr(view_instance, method)) for method in required_methods):
            missing = [method for method in required_methods if not (hasattr(view_instance, method) and callable(getattr(view_instance, method)))]
            raise TypeError(f"视图实例 {type(view_instance)} 缺少必需方法: {missing}。")
        if not all(hasattr(view_instance, attr) for attr in required_attrs):
            missing = [attr for attr in required_attrs if not hasattr(view_instance, attr)]
            raise TypeError(f"视图实例 {type(view_instance)} 缺少必需属性: {missing}。")
        
        # 移除了对旧配置方法的检查
        # if not hasattr(view_instance, 'get_visualization_config') and not hasattr(view_instance, 'get_exploration_config'):
        #      raise TypeError("视图实例必须提供 'get_visualization_config' 或 'get_exploration_config' 方法。")

        # 调用基类初始化
        super().__init__(data_manager=data_manager, view=view_instance, **params)

    # 子类仍需实现此方法来接收 AppController 传递的数据 ID
    @abstractmethod
    def set_selected_data(self, selected_ids: List[str] | str):
        raise NotImplementedError("可视化控制器子类必须实现 set_selected_data")

    # (已移除不再需要的注释)

    # --- 移除的方法 (已移至 BaseServiceController 或不再需要) ---
    # _handle_service_result 处理方式改变
    # _get_output_area 可能不再需要

    # --- 移除的方法 (已移至 BaseServiceController) ---
    # _bind_events -> 由基类 __init__ 调用 _bind_button_event
    # _handle_visualize_base -> 由基类 _handle_service_call_base 替代
    # _set_loading_state -> 由基类 _set_loading_state 替代
    # _reset_loading_state -> 由基类 _reset_loading_state 替代
    # _notify -> 由基类 _notify 替代
    # _show_error_and_reset -> 由基类 _show_error_and_reset 替代
    # get_view_panel -> 由基类 get_view_panel 替代 (如果视图有 get_panel) 