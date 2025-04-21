import param
import panel as pn
import traceback
from typing import Dict, Any, Optional, Type, Callable
from abc import ABC, abstractmethod
from model.data_manager import DataManager

class BaseServiceController(param.Parameterized):
    """服务控制器抽象基类。

    封装了调用注册表中服务（如预处理、可视化等）的通用流程，
    包括获取配置、查找服务、验证输入、调用服务、处理结果/错误以及更新 UI 状态。
    子类需要实现特定的抽象方法来适配具体的服务类型和视图。
    """

    # 子类需要通过初始化提供 DataManager 实例
    data_manager: DataManager = param.Parameter(precedence=-1, doc="数据管理器实例")
    # 子类需要通过初始化提供关联的视图实例
    view: Any = param.Parameter(precedence=-1, doc="关联的视图实例")

    # 内部状态
    is_processing = param.Boolean(default=False, precedence=-1, doc="指示服务是否正在处理中")

    # --- 抽象属性/方法 (子类必须实现) ---

    @property
    @abstractmethod
    def registry(self) -> dict:
        """返回此控制器使用的服务注册表字典 (例如 PREPROCESSORS, VISUALIZERS)。"""
        raise NotImplementedError

    @abstractmethod
    def _get_config_from_view(self) -> Optional[Dict[str, Any]]:
        """从关联的视图获取服务调用所需的配置。

        配置字典应至少包含 'service_name' 和 'params' (用户在 UI 设置的参数)。
        对于需要输入数据的服务，还应包含相关的数据标识符。
        如果配置无效或不完整，应在视图中显示提示并返回 None。

        Returns:
            包含配置的字典，或在失败时返回 None。
        """
        raise NotImplementedError

    @abstractmethod
    def _get_service_button(self) -> Optional[pn.widgets.Button]:
        """获取触发服务调用的视图按钮实例。

        Returns:
            触发按钮的 Panel Widget 实例，或 None。
        """
        raise NotImplementedError

    @abstractmethod
    def _get_output_area(self) -> Optional[Any]:
        """获取用于显示服务结果或状态/错误消息的视图区域 Panel 组件。
        
        Returns:
            用于显示输出的 Panel 组件实例，或 None。
        """
        raise NotImplementedError

    @abstractmethod
    def _validate_config_and_get_payload(self, config: Dict, service_info: Dict) -> tuple[bool, Dict[str, Any]]:
        """
        验证从视图获取的配置和相关数据，并准备传递给服务函数的实际数据参数 payload。

        子类需要根据服务类型（单输入、列表输入等）和服务注册信息中的
        `input_type`, `accepts_list`, `input_param_name` 来实现具体的验证逻辑。

        Args:
            config: 从 _get_config_from_view 获取的配置字典。
            service_info: 从注册表获取的所选服务的信息字典。

        Returns:
            一个元组 (is_valid, payload)。
            is_valid: 布尔值，指示验证是否通过。如果为 False，应已通过 _notify 或
                      _handle_service_error 在 UI 上显示错误。
            payload: 字典，包含准备好传递给服务函数的 *非用户参数* 部分，通常是处理后的数据。
                     例如: {'data_container': dc_object} 或 {'data_containers': [dc1, dc2]}。
                     键名应与服务函数期望的参数名匹配（参考 input_param_name）。
        """
        raise NotImplementedError

    @abstractmethod
    def _handle_service_result(self, result: Any, service_name: str, config: Dict):
        """
        处理服务函数成功执行后返回的结果。

        子类需要根据服务类型实现具体逻辑，例如：
        - 对于可视化服务：更新视图的显示区域。
        - 对于处理服务：将新生成的数据添加到 DataManager。

        Args:
            result: 服务函数返回的结果。
            service_name: 被调用的服务名称。
            config: 调用服务时使用的原始配置字典，可能包含上下文信息。
        """
        raise NotImplementedError

    # --- 具体方法 (通用逻辑) ---

    def __init__(self, data_manager: DataManager, view: Any, **params):
        """初始化基类控制器。
        
        Args:
            data_manager: DataManager 实例。
            view: 关联的视图实例。
            **params: 其他传递给 param.Parameterized 的参数。
            
        Raises:
            ValueError: 如果 data_manager 或 view 未提供。
        """
        if data_manager is None or view is None:
            raise ValueError(f"{self.__class__.__name__} 必须在初始化时提供 data_manager 和 view 实例。")
        super().__init__(data_manager=data_manager, view=view, **params)
        self._bind_button_event()

    def _bind_button_event(self):
        """绑定服务按钮的点击事件到通用的服务调用处理函数。"""
        button = self._get_service_button()
        if button:
            button.on_click(self._handle_service_call_base)
        else:
            print(f"警告: 在 {self.__class__.__name__} 中未找到服务按钮，无法绑定点击事件。")

    def _handle_service_call_base(self, event):
        """处理服务调用按钮点击事件的基础逻辑。"""
        if self.is_processing:
            self._notify("warning", "正在处理中，请稍候...")
            return

        # 1. 获取配置
        config = self._get_config_from_view()
        if not config:
            # 获取配置失败，_get_config_from_view 应该已经显示了错误
            return

        service_name = config.get('service_name')
        user_params = config.get('params', {})

        if not service_name:
            self._notify("error", "未选择服务。")
            return

        # 2. 查找服务
        service_info = self.registry.get(service_name)
        if not service_info:
            self._handle_service_error(f"系统错误：未在注册表中找到服务 '{service_name}'。", service_name) # 使用错误处理函数
            self._reset_loading_state() # 确保重置状态
            return

        service_func = service_info.get('function')
        if not callable(service_func):
             self._handle_service_error(f"系统错误：服务 '{service_name}' 配置无效 (缺少可调用函数)。", service_name) # 使用错误处理函数
             self._reset_loading_state() # 确保重置状态
             return

        # --- 准备执行 --- #
        self._set_loading_state(True)
        self._clear_output_area() # 清除旧输出

        try:
            # 3. 子类验证配置和准备数据 Payload
            is_valid, data_payload = self._validate_config_and_get_payload(config, service_info)
            if not is_valid:
                # 验证失败，错误信息应已由 _validate_... 处理
                # 不需要在这里再次显示错误，但需要重置状态
                self._reset_loading_state()
                return

            # 4. 合并参数并执行服务
            # 优先级：用户参数 > 数据 payload (如果 key 相同)
            # 服务函数签名应接受 **kwargs 或明确定义的参数
            final_args = {**data_payload, **user_params}

            print(f"调试: 调用服务 '{service_name}' 使用参数: {list(final_args.keys())}") # 调试
            result = service_func(**final_args)

            # 5. 子类处理结果
            self._handle_service_result(result, service_name, config)
            # 可选：成功时显示通用通知
            # self._notify("success", f"服务 '{service_name}' 执行成功。")

        except Exception as e:
            # 捕获服务执行或结果处理中的任何异常
            tb_str = traceback.format_exc()
            print(f"错误: 执行服务 '{service_name}' 或处理其结果时出错:\n{tb_str}")
            error_msg = f"执行服务 '{service_name}' 时发生错误: {e}"
            # 使用统一的错误处理方法
            self._handle_service_error(error_msg, service_name)

        finally:
            # 无论成功或失败，最终都要重置加载状态
            self._reset_loading_state()

    def _clear_output_area(self):
        """尝试清除输出区域的内容。"""
        output_area = self._get_output_area()
        if output_area is None:
            return
        try:
            # 不同的 Panel 组件清除方式不同
            if hasattr(output_area, 'object'): # Markdown, HTML, Alert 等
                output_area.object = ""
            if hasattr(output_area, 'clear'): # Column, Row 等布局组件
                output_area.clear()
            if hasattr(output_area, 'visible'): # Alert 可以隐藏
                output_area.visible = False
        except Exception as e:
            print(f"调试: 清除输出区域 ({type(output_area)}) 时出错: {e}")

    def _handle_service_error(self, error_message: str, service_name: str):
        """处理服务执行期间发生的错误，默认将错误信息显示在输出区域。

        子类可以覆盖此方法以实现特定的错误处理逻辑。

        Args:
            error_message: 错误信息字符串。
            service_name: 发生错误的服务名称。
        """
        output_area = self._get_output_area()
        alert_msg = f"服务 '{service_name}' 执行失败: {error_message}"
        
        if output_area:
            try:
                # 优先使用 Alert 显示错误
                if isinstance(output_area, pn.pane.Alert):
                    output_area.object = alert_msg
                    output_area.alert_type = 'danger'
                    output_area.visible = True
                elif hasattr(output_area, 'object'): # 尝试更新其他窗格
                     output_area.object = f"<p style='color:red;'><b>错误:</b> {alert_msg}</p>"
                     if hasattr(output_area, 'visible'): output_area.visible = True
                elif hasattr(output_area, 'clear'): # 对于布局，添加 Alert
                    output_area.clear()
                    output_area.append(pn.pane.Alert(alert_msg, alert_type='danger'))
                    if hasattr(output_area, 'visible'): output_area.visible = True
                else:
                     # 如果都失败，回退到通知
                     self._notify("error", alert_msg)
            except Exception as e:
                 print(f"错误: 在 _handle_service_error 中更新输出区域时出错: {e}")
                 self._notify("error", alert_msg) # 回退到通知
        else:
            self._notify("error", alert_msg)

    def _set_loading_state(self, loading: bool):
        """设置加载状态 (按钮和可选的输出区域)。
        
        Args:
            loading: 是否处于加载状态。
        """
        self.is_processing = loading
        button = self._get_service_button()
        if button:
            try:
                button.loading = loading
            except Exception as e:
                 print(f"错误: 设置按钮 loading 状态失败: {e}")

        output_area = self._get_output_area()
        if output_area and hasattr(output_area, 'loading'):
             try:
                 output_area.loading = loading
             except Exception as e:
                  print(f"警告: 设置输出区域 loading 状态失败: {e}")

    def _reset_loading_state(self):
        """重置加载状态。"""
        self._set_loading_state(False)

    def _notify(self, level: str, message: str, duration: int = 5000):
        """显示短暂的状态通知。
        
        Args:
            level: 通知级别 ('success', 'info', 'warning', 'error')。
            message: 通知消息内容。
            duration: 显示时长（毫秒）。
        """
        try:
            if level == 'success':
                pn.state.notifications.success(message, duration=duration)
            elif level == 'info':
                pn.state.notifications.info(message, duration=duration)
            elif level == 'warning':
                pn.state.notifications.warning(message, duration=duration)
            elif level == 'error':
                pn.state.notifications.error(message, duration=duration)
            else:
                 pn.state.notifications.info(message, duration=duration) # 默认为 info
        except Exception as e:
             print(f"错误: 显示通知失败: {e}. 消息: {level} - {message}")

    def _show_error_and_reset(self, message: str):
        """(已弃用，逻辑合并到 _handle_service_error 和 finally 块) 显示错误通知并重置状态。"""
        # self._notify("error", message)
        # self._reset_loading_state()
        pass

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel (如果视图提供 get_panel 方法)。
        
        Returns:
            视图的 Panel 布局。
            
        Raises:
            AttributeError: 如果视图没有 get_panel 方法。
            TypeError: 如果视图的 get_panel 不是可调用方法。
        """
        if hasattr(self.view, 'get_panel') and callable(self.view.get_panel):
             return self.view.get_panel()
        else:
             # 或者返回一个错误面板
             # return pn.pane.Alert(f"{self.__class__.__name__} 的视图无效或缺少 get_panel 方法。", alert_type='danger')
             raise TypeError(f"{type(self.view)} 实例缺少可调用的 get_panel 方法。") 