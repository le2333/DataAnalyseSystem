import param
import panel as pn
import pandas as pd
import os
import traceback # 用于打印详细错误堆栈
from typing import Optional, List, Dict, Any, Tuple
from model.data_manager import DataManager
from model.data_container import DataContainer # 导入基类
from model.timeseries_container import TimeSeriesContainer # 导入具体容器类
# 导入服务注册表
from services.registry import LOADERS, STRUCTURERS
# 导入基类控制器
from .base_service_controller import BaseServiceController 

class LoadController(BaseServiceController): # 继承自 BaseServiceController
    """处理 LoadView 交互，读取文件，调用加载和结构化服务，并将结果添加到 DataManager。"""

    # data_manager, view, is_processing (现在叫 is_loading) 由基类提供

    # 在基类中查找可用的加载器和结构化器
    # registry = LOADERS # 通过 get_available_services 获取
    
    # --- 初始化和事件绑定 ---

    def __init__(self, data_manager: DataManager, view_instance: Any, **params):
        """初始化加载控制器。

        Args:
            data_manager: 数据管理器实例。
            view_instance: 视图实例 (应包含 file_selector, load_button, update_status 等)。
            **params: 其他 param 参数。
        """
        # 检查视图实例是否符合要求
        required_attrs = ['file_selector', 'load_button', 'update_status', 'get_loader_options', 'get_structurer_options', 'get_loader_params', 'get_structurer_params']
        if not all(hasattr(view_instance, attr) for attr in required_attrs):
            missing = [attr for attr in required_attrs if not hasattr(view_instance, attr)]
            raise TypeError(f"LoadView 实例缺少必需属性或方法: {missing}。")
            
        # 使用 super() 调用基类初始化，传递必要的参数
        # 注意：BaseServiceController 需要 registry，但 LoadController 可能需要访问多个 registry (LOADERS, STRUCTURERS)
        # 这里我们将 registry 设为 None，并在需要时显式访问 LOADERS 和 STRUCTURERS
        super().__init__(data_manager=data_manager, view=view_instance, registry=None, service_type_name="加载", **params)
        
        # 特定于加载的事件绑定 (基类处理通用按钮和状态)
        self._bind_load_event()

    def _bind_load_event(self):
        """绑定加载按钮的点击事件到处理函数。"""
        self.view.load_button.on_click(self._handle_load_wrapper)

    # --- Service Discovery (Overriding base class methods or providing specifics) ---

    def get_available_loaders(self) -> Dict[str, Dict]:
        """获取当前注册的所有可用文件加载服务。"""
        return LOADERS
        
    def get_available_structurers(self) -> Dict[str, Dict]:
        """获取当前注册的所有可用数据结构化服务。"""
        return STRUCTURERS

    # --- 核心加载逻辑 ---

    def _handle_load_wrapper(self, event):
        """加载按钮事件的包装器，调用基类的服务调用逻辑。"""
        
        selected_files = self.view.file_selector.value
        if not selected_files:
            self._notify("info", "请先选择要加载的文件。")
            return

        loader_name = self.view.get_loader_options().get('selected_loader')
        structurer_name = self.view.get_structurer_options().get('selected_structurer')
        
        if not loader_name:
             self._notify("warning", "请选择一个文件加载器。")
             return
        if not structurer_name:
             self._notify("warning", "请选择一个数据结构化器。")
             return

        loader_params = self.view.get_loader_params(loader_name)
        structurer_params = self.view.get_structurer_params(structurer_name)
        
        # 准备传递给核心处理函数的参数
        # 注意：这里我们将文件列表和其他参数捆绑在一起
        # 基类的 _handle_service_call_base 需要一个 'config' 字典和一个主输入
        # 我们需要调整 _load_and_structure 来适应这种模式，或者在这里处理循环
        
        # === 采用循环处理文件列表，每次调用服务 ===
        self._set_loading_state(True) # 标记开始处理
        self.view.update_status("开始加载文件...", alert_type='info')
        
        success_count = 0
        error_count = 0
        error_messages = []
        
        # 获取加载器和服务函数
        loader_info = LOADERS.get(loader_name)
        structurer_info = STRUCTURERS.get(structurer_name)

        if not loader_info:
            self._show_error_and_reset(f"未找到加载器 '{loader_name}'。", "文件加载")
            return
        if not structurer_info:
            self._show_error_and_reset(f"未找到结构化器 '{structurer_name}'。", "数据结构化")
            return

        loader_func = loader_info['function']
        structurer_func = structurer_info['function']
        
        # --- 文件处理循环 ---
        for file_path in selected_files:
            file_name = os.path.basename(file_path)
            self.view.update_status(f"正在处理: {file_name}...", alert_type='info')
            
            try:
                # --- 1. 调用加载器服务 ---
                # 这里直接调用函数，如果加载器需要复杂配置，可能需要调整
                # 假设加载器只接收文件路径和 loader_params
                loader_input_param_name = loader_info.get('input_param_name', 'file_path') # 获取期望的参数名
                loader_call_params = {loader_input_param_name: file_path, **loader_params}
                
                # print(f"调试: 调用加载器 {loader_name} 使用参数: {loader_call_params}") # 调试信息
                loaded_data = loader_func(**loader_call_params)
                # print(f"调试: 加载器 {loader_name} 返回类型: {type(loaded_data)}") # 调试信息

                # --- 2. 调用结构化器服务 ---
                # 假设结构化器接收加载的数据和 structurer_params
                structurer_input_param_name = structurer_info.get('input_param_name', 'input_data') # 获取期望的参数名
                
                # 特殊处理：为 structure_df_to_timeseries 传递 base_name_for_naming
                if structurer_name == "从DataFrame结构化为时间序列":
                    structurer_params['base_name_for_naming'] = os.path.splitext(file_name)[0]
                
                structurer_call_params = {structurer_input_param_name: loaded_data, **structurer_params}
                
                # print(f"调试: 调用结构化器 {structurer_name} 使用参数: {structurer_call_params}") # 调试信息
                structured_container = structurer_func(**structurer_call_params)
                # print(f"调试: 结构化器 {structurer_name} 返回类型: {type(structured_container)}") # 调试信息

                # --- 3. 添加到 DataManager ---
                if isinstance(structured_container, DataContainer):
                    # 确保名称是唯一的（DataManager 应该处理这个，但这里可以加一层）
                    new_id = self.data_manager.add_data(structured_container)
                    self._notify("success", f"成功加载并结构化 '{file_name}' 为 '{structured_container.name}' (ID: {new_id})。")
                    success_count += 1
                else:
                    raise TypeError(f"结构化器 '{structurer_name}' 未返回有效的 DataContainer 对象 (返回了 {type(structured_container)})。")

            except Exception as e:
                # 使用基类的错误处理
                error_msg = f"处理文件 '{file_name}' 时出错: {e}"
                # 这里不直接调用 _handle_service_error 因为错误可能发生在服务调用之间
                # 而是记录错误并继续处理下一个文件
                print(f"错误: {error_msg}\n{traceback.format_exc()}") # 打印详细错误
                error_messages.append(f"{file_name}: {e}")
                error_count += 1
                # 可以在这里用 _notify 显示单文件错误，但最终会汇总
                # self._notify("error", error_msg) 

        # --- 循环结束，报告最终结果 ---
        final_status = f"处理完成: 成功加载 {success_count} 个文件"
        if error_count > 0:
             final_status += f"，失败 {error_count} 个。"
        else:
             final_status += "。"

        alert_type = 'success'
        if error_count > 0:
            final_status += "\\n错误详情:\\n" + "\\n".join(f"- {msg}" for msg in error_messages)
            alert_type = 'warning' if success_count > 0 else 'danger'
        elif success_count == 0:
             final_status = "处理完成：未成功加载任何数据。"
             alert_type = 'info'
        
        # 更新视图的最终状态
        self.view.update_status(final_status, alert_type=alert_type)
        self._set_loading_state(False) # 标记处理结束
        
        # 清空文件选择器，以便下次使用 (如果需要)
        # self.view.file_selector.value = []


    # get_view_panel 由基类提供，如果视图有 get_panel 方法

# 移除了旧的 _read_file, _load_and_structure 方法，逻辑已整合到 _handle_load_wrapper

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel 对象，用于在 UI 中展示。"""
        if self.view and hasattr(self.view, 'get_panel') and callable(self.view.get_panel):
             return self.view.get_panel()
        else:
             # 如果视图无效或缺少必要方法，返回一个错误提示 Panel
             return pn.pane.Alert(f"{self.__class__.__name__} 的视图无效或缺少 get_panel 方法。", alert_type='danger') 