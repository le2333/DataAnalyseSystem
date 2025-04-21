import panel as pn
import pandas as pd
import param
import io
import os # 导入 os 以使用 expanduser
from typing import List, Optional, Dict, Any
from services.registry import LOADERS, STRUCTURERS # 需要导入注册表
from .view_utils import ServiceSelector, ParameterPanel # 导入通用组件

pn.extension(sizing_mode="stretch_width")

class LoadView(param.Parameterized):
    """数据加载与结构化视图。

    构建用户界面，允许用户选择本地文件、配置加载器和结构化器，
    并触发数据处理流程。提供文件预览（目前仅限CSV）、列选择和状态反馈。
    """

    # --- 内部参数化属性，用于存储和管理UI组件实例 --- 
    file_selector = param.ClassSelector(class_=pn.widgets.FileSelector, is_instance=True, 
                                      doc="文件选择器实例")
    loader_selector = param.ClassSelector(class_=ServiceSelector, is_instance=True, 
                                        doc="加载器服务选择器实例")
    loader_parameter_panel = param.ClassSelector(class_=ParameterPanel, is_instance=True, 
                                             doc="加载器参数面板实例")
    preview_area = param.ClassSelector(class_=pn.pane.DataFrame, is_instance=True, 
                                     doc="文件预览区域实例 (DataFrame)")
    time_column_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True, 
                                           doc="时间列选择器实例")
    data_column_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True, 
                                           doc="数据列选择器实例")
    structurer_selector = param.ClassSelector(class_=ServiceSelector, is_instance=True, 
                                            doc="结构化器服务选择器实例")
    structurer_parameter_panel = param.ClassSelector(class_=ParameterPanel, is_instance=True, 
                                                 doc="结构化器参数面板实例")
    load_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True, 
                                    doc="加载并结构化按钮实例")
    load_status = param.ClassSelector(class_=pn.pane.Alert, is_instance=True, 
                                    doc="状态信息显示区域实例 (Alert)")

    def __init__(self, **params):
        """初始化 LoadView。

        创建所有 UI 组件并设置它们之间的依赖关系。

        Args:
            **params: param.Parameterized 的标准参数。
        """
        super().__init__(**params)
        self._create_ui_components()
        self._bind_param_dependencies()
        self._update_button_state(None) # 初始化按钮状态检查

    def _create_ui_components(self):
        """实例化所有 Panel UI 组件。"""
        self.file_selector = pn.widgets.FileSelector(
            'data/', # TODO: 考虑将默认目录设为可配置
            name='选择文件 (可多选)',
            only_files=True,
            sizing_mode='stretch_width'
        )
        
        # 加载器选择和参数
        self.loader_selector = ServiceSelector(registry=LOADERS, selector_label="选择文件加载器")
        self.loader_parameter_panel = ParameterPanel() 
        
        # 预览和列选择 - 初始禁用，依赖文件选择和可能的加载器
        self.preview_area = pn.pane.DataFrame(None, height=150, sizing_mode='stretch_width')
        self.time_column_selector = pn.widgets.Select(name="时间列", options=[], disabled=True)
        self.data_column_selector = pn.widgets.Select(name="数据列 (可选)", options=[], disabled=True)
        
        # 结构化器选择和参数
        self.structurer_selector = ServiceSelector(registry=STRUCTURERS, selector_label="选择数据结构化器")
        self.structurer_parameter_panel = ParameterPanel() 
        
        self.load_button = pn.widgets.Button(name="加载并结构化数据", button_type="primary", disabled=True)
        self.load_status = pn.pane.Alert("请按步骤选择文件、加载器和结构化器后点击加载。", alert_type='info', visible=True)
        
        # 监听文件选择变化 -> 更新预览和列选项 (简化版预览)
        self.file_selector.param.watch(self._on_file_select, 'value')
        # 监听时间列选择 -> 更新按钮状态
        self.time_column_selector.param.watch(self._update_button_state, 'value')
        
    def _bind_param_dependencies(self):
        """设置组件之间的依赖关系，主要通过 param.watch 实现。"""
        # 绑定加载器
        self.loader_selector.param.watch(self._update_loader_parameter_panel, 'selected_service_info')
        self._update_loader_parameter_panel(None) # Initial call
        
        # 绑定结构化器
        self.structurer_selector.param.watch(self._update_structurer_parameter_panel, 'selected_service_info')
        self._update_structurer_parameter_panel(None) # Initial call
        
        # 按钮状态依赖于文件、加载器、(时间列)、结构化器
        self.loader_selector.param.watch(self._update_button_state, 'selected_service_name')
        self.structurer_selector.param.watch(self._update_button_state, 'selected_service_name')
        # 文件选择器和时间列选择器的 watcher 在 _create_ui_components 中设置

    def _on_file_select(self, event):
        """文件选择器的回调函数。

        当用户选择文件时触发。
        - 如果选择了文件：
            - 尝试预览第一个文件（目前仅限CSV），更新预览区域和列选择器。
            - 更新状态信息。
        - 如果没有选择文件：
            - 清空并禁用预览和列选择器。
            - 更新状态信息。
        - 最后总是更新加载按钮的状态。
        
        Args:
            event: param 事件对象，包含新选择的文件路径列表 (event.new)。
        """
        selected_paths = event.new
        if selected_paths:
            first_path = selected_paths[0]
            # 尝试对 CSV 文件进行预览
            if first_path.lower().endswith('.csv'):
                try:
                    # 读取少量数据用于预览和获取列名
                    df_preview = pd.read_csv(first_path, nrows=5)
                    columns = list(df_preview.columns)
                    self.preview_area.object = df_preview
                    # 更新列选择器选项，添加空/默认选项
                    self.time_column_selector.options = [''] + columns
                    self.data_column_selector.options = ['[自动选择]'] + columns
                    self.time_column_selector.disabled = False
                    self.data_column_selector.disabled = False
                    self.update_status(f"已选择 {len(selected_paths)} 个文件。预览首个CSV，请选择时间/数据列和结构化器。", 'info')
                except Exception as e:
                    self.update_status(f"警告：无法预览CSV文件 '{os.path.basename(first_path)}': {e}", 'warning')
                    self._disable_preview_and_columns()
            else:
                 # 对非 CSV 文件提供提示，不进行预览
                 self.update_status(f"已选择 {len(selected_paths)} 个文件。非CSV文件无法预览列名，请确保加载器/结构化器配置正确。", 'info')
                 self._disable_preview_and_columns()
        else:
            # 没有选择文件的情况
            self.update_status("请在上方选择文件...", 'info')
            self._disable_preview_and_columns()
            
        # 文件选择状态改变，需要重新评估加载按钮状态
        self._update_button_state(None)

    def _disable_preview_and_columns(self):
        """辅助函数：清空并禁用预览区域和列选择器。"""
        self.preview_area.object = None
        self.time_column_selector.options = []
        self.data_column_selector.options = []
        self.time_column_selector.disabled = True
        self.data_column_selector.disabled = True

    def _update_loader_parameter_panel(self, event):
        """加载器选择器的回调函数：更新加载器参数面板。"""
        service_info = self.loader_selector.selected_service_info
        params_spec = service_info.get('params', {})
        self.loader_parameter_panel.params_spec = params_spec

    def _update_structurer_parameter_panel(self, event):
        """结构化器选择器的回调函数：更新结构化器参数面板。
        
        注意：过滤掉 'time_column_name' 和 'data_column_name'，
        因为它们由专门的下拉框控制。
        """
        service_info = self.structurer_selector.selected_service_info
        params_spec = service_info.get('params', {})
        # 过滤掉由专用选择器管理的参数
        filtered_params_spec = {k: v for k, v in params_spec.items()
                                if k not in ['time_column_name', 'data_column_name']}
        self.structurer_parameter_panel.params_spec = filtered_params_spec

    def _update_button_state(self, event):
        """多个组件状态变化时的回调函数：更新加载按钮的启用/禁用状态。"""
        # 基本条件：必须选择文件、加载器和结构化器
        base_enable = bool(self.file_selector.value and
                           self.loader_selector.selected_service_name and
                           self.structurer_selector.selected_service_name)

        # 附加条件：如果时间列选择器已启用（通常在CSV预览后），则必须选择一个非空值
        time_col_required_and_missing = (not self.time_column_selector.disabled and
                                          not self.time_column_selector.value)

        # 最终状态：满足基本条件且不缺少必要的时间列选择
        enable = base_enable and not time_col_required_and_missing
        self.load_button.disabled = not enable

    # --- 供 Controller 使用的公共方法 --- 

    def get_selected_files(self) -> List[str]:
        """获取用户选择的文件路径列表。"""
        return self.file_selector.value or []

    def get_loader_options(self) -> Dict[str, Any]:
        """返回加载器的基本选项（当前仅包含选择的服务名称）。

        Returns:
            Dict[str, Any]: 包含 'selected_loader' 键的字典。
        """
        return {
            'selected_loader': self.loader_selector.selected_service_name
        }

    def get_loader_params(self, loader_name: str) -> Dict[str, Any]:
        """获取当前为指定加载器配置的参数。

        Args:
            loader_name (str): 需要获取参数的加载器名称。

        Returns:
            Dict[str, Any]: 加载器的参数字典。

        Raises:
            ValueError: 如果请求的加载器与视图中当前选择的不符。
            Exception: 如果从参数面板获取参数时发生错误。
        """
        if self.loader_selector.selected_service_name == loader_name:
            try:
                return self.loader_parameter_panel.get_params()
            except Exception as e:
                self.update_status(f"错误：获取加载器 '{loader_name}' 参数失败: {e}", alert_type='danger')
                raise # 将异常传递给 Controller 处理
        else:
            msg = f"请求的加载器参数 '{loader_name}' 与视图中选中的 ('{self.loader_selector.selected_service_name}') 不符。"
            print(f"警告: {msg}")
            raise ValueError(msg)

    def get_structurer_options(self) -> Dict[str, Any]:
        """返回结构化器的基本选项（当前仅包含选择的服务名称）。

        Returns:
            Dict[str, Any]: 包含 'selected_structurer' 键的字典。
        """
        return {
            'selected_structurer': self.structurer_selector.selected_service_name
        }

    def get_structurer_params(self, structurer_name: str) -> Dict[str, Any]:
        """获取当前为指定结构化器配置的参数，并合并时间/数据列的选择。

        Args:
            structurer_name (str): 需要获取参数的结构化器名称。

        Returns:
            Dict[str, Any]: 结构化器的参数字典，包含从参数面板和列选择器获取的值。
                          'time_column_name' 和 'data_column_name' 会被添加。
                          如果 data_column_name 选择为 '[自动选择]'，则其值为 None。

        Raises:
            ValueError: 如果请求的结构化器与视图中当前选择的不符。
            Exception: 如果从参数面板或列选择器获取参数时发生错误。
        """
        if self.structurer_selector.selected_service_name == structurer_name:
            try:
                # 获取基础参数
                base_params = self.structurer_parameter_panel.get_params()
                
                # 合并时间列参数 (如果可用且已选择)
                if not self.time_column_selector.disabled and self.time_column_selector.value:
                    base_params['time_column_name'] = self.time_column_selector.value
                
                # 合并数据列参数 (如果可用且已选择)
                data_col_option = self.data_column_selector.value
                if not self.data_column_selector.disabled and data_col_option:
                    # 将 "[自动选择]" 映射为 None
                    base_params['data_column_name'] = None if data_col_option == '[自动选择]' else data_col_option
                
                return base_params
            except Exception as e:
                self.update_status(f"错误：获取结构化器 '{structurer_name}' 参数失败: {e}", alert_type='danger')
                raise # 将异常传递给 Controller 处理
        else:
            msg = f"请求的结构化器参数 '{structurer_name}' 与视图中选中的 ('{self.structurer_selector.selected_service_name}') 不符。"
            print(f"警告: {msg}")
            raise ValueError(msg)

    def update_status(self, message: str, alert_type: str = 'info'):
        """更新底部状态显示区域的消息和类型。

        Args:
            message (str): 要显示的消息文本。
            alert_type (str): Panel Alert 的类型 ('info', 'warning', 'danger', 'success')。
        """
        self.load_status.object = message
        self.load_status.alert_type = alert_type
        self.load_status.visible = True # 确保状态区域可见

    def get_panel(self) -> pn.layout.Panel:
        """构建并返回加载视图的完整 Panel 布局。
        
        将所有 UI 组件按照逻辑顺序排列。
        
        Returns:
            pn.layout.Panel: 包含所有加载和结构化控件的 Panel Column 布局。
        """
        layout = pn.Column(
            pn.pane.Markdown("## 数据加载与结构化"),
            
            pn.pane.Markdown("**1. 选择本地文件:**"),
            self.file_selector,
            
            pn.pane.Markdown("**2. 选择文件加载器:**"),
            self.loader_selector.get_panel(),
            pn.pane.Markdown("**3. (可选) 配置加载器参数:**"),
            self.loader_parameter_panel.get_panel(),
            
            pn.layout.Divider(),
            
            pn.pane.Markdown("**4. 文件预览与列选择 (仅限CSV):**"),
            self.preview_area,
            pn.Row(
                self.time_column_selector,
                self.data_column_selector,
                sizing_mode='stretch_width'
            ),
            
            pn.pane.Markdown("**5. 选择数据结构化器:**"),
            self.structurer_selector.get_panel(),
            pn.pane.Markdown("**6. (可选) 配置结构化器参数:**"),
            self.structurer_parameter_panel.get_panel(),
            
            pn.layout.Divider(),
            self.load_button,
            self.load_status, # 状态显示区域
            sizing_mode='stretch_width'
        )
        return layout 