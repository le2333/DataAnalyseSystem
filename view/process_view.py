import panel as pn
import param
from typing import List, Dict, Any, Optional
from model.data_manager import DataManager
from services.registry import PREPROCESSORS
from .view_utils import ServiceSelector, ParameterPanel # 导入通用组件

pn.extension(sizing_mode="stretch_width")

class ProcessView(param.Parameterized):
    """执行数据处理与转换操作的视图。"""
    data_manager = param.Parameter(precedence=-1)
    # 由 AppController 设置当前选中的数据 ID
    selected_data_ids = param.List(default=[])

    # --- 使用通用 UI 组件 --- #
    service_selector = param.ClassSelector(class_=ServiceSelector, is_instance=True)
    parameter_panel = param.ClassSelector(class_=ParameterPanel, is_instance=True)
    preprocess_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    preprocess_status = param.ClassSelector(class_=pn.pane.Alert, is_instance=True)
    selected_data_info = param.ClassSelector(class_=pn.pane.Markdown, is_instance=True)
    
    # 移除旧的 _current_preprocessor_widgets

    def __init__(self, data_manager: DataManager, **params):
        super().__init__(data_manager=data_manager, **params)
        self._create_ui_components()
        self._bind_param_dependencies()
        self._update_selected_data_info() # Initial update

    def _create_ui_components(self):
        self.selected_data_info = pn.pane.Markdown("未选择数据。")
        self.service_selector = ServiceSelector(registry=PREPROCESSORS, selector_label="选择处理方法")
        self.parameter_panel = ParameterPanel() # params_spec 将通过 watcher 更新
        self.preprocess_button = pn.widgets.Button(name="执行处理", button_type="success", disabled=True)
        self.preprocess_status = pn.pane.Alert("", alert_type='info', visible=False)

    def _bind_param_dependencies(self):
        """绑定服务选择器到参数面板。"""
        # 当 service_selector.selected_service_info 变化时，更新 parameter_panel.params_spec
        self.service_selector.param.watch(self._update_parameter_panel, 'selected_service_info')
        # 初始调用一次，以防 ServiceSelector 已经有默认值
        self._update_parameter_panel(None)
        
        # 按钮的 disabled 状态依赖于服务选择和数据选择
        self.service_selector.param.watch(self._update_button_state, 'selected_service_name')
        self.param.watch(self._update_button_state, 'selected_data_ids')
        # 初始调用一次
        self._update_button_state(None)

    def _update_parameter_panel(self, event):
        """Watcher: 更新参数面板的 params_spec。"""
        service_info = self.service_selector.selected_service_info
        self.parameter_panel.params_spec = service_info.get('params', {})

    def _update_button_state(self, event):
         """Watcher: 更新处理按钮的禁用状态。"""
         self.preprocess_button.disabled = not bool(self.service_selector.selected_service_name and self.selected_data_ids)

    @param.depends('selected_data_ids', watch=True)
    def _update_selected_data_info(self):
        """更新顶部显示已选数据的信息。"""
        if not self.selected_data_ids:
            self.selected_data_info.object = "**当前未选择数据**"
            # self.preprocess_button.disabled = True # 由 _update_button_state 控制
            return

        info_str = f"**选定数据 ({len(self.selected_data_ids)} 项):**\n"
        names = []
        types = set()
        for data_id in self.selected_data_ids:
             dc = self.data_manager.get_data(data_id)
             if dc:
                 names.append(f"- {dc.name} ({dc.data_type})")
                 types.add(dc.data_type)
             else:
                 names.append(f"- ID: {data_id} (未找到)")
        info_str += "\n".join(names)
        self.selected_data_info.object = info_str
        # self.preprocess_button.disabled = not bool(self.service_selector.selected_service_name) # 由 _update_button_state 控制

    # 移除旧的 _update_preprocessor_options 和 _on_preprocessor_select

    def get_process_config(self) -> Optional[Dict[str, Any]]:
        """获取当前处理配置。"""
        service_name = self.service_selector.selected_service_name
        if not service_name or not self.selected_data_ids:
            self._show_temporary_error("请选择处理服务和至少一个数据项。")
            return None

        try:
            params = self.parameter_panel.get_params()
        except Exception as e:
             self._show_temporary_error(f"获取服务参数时出错: {e}")
             return None

        config = {
            'selected_data_ids': self.selected_data_ids,
            'service_name': service_name,
            'params': params
        }
        return config
        
    def _show_temporary_error(self, message: str):
        """在状态区域临时显示错误。"""
        self.preprocess_status.object = message
        self.preprocess_status.alert_type = 'warning'
        self.preprocess_status.visible = True
        # 可以考虑用 pn.state.schedule_task 延迟隐藏

    def show_status(self, message: str, alert_type: str = 'info'):
        """显示处理状态信息。"""
        self.preprocess_status.object = message
        self.preprocess_status.alert_type = alert_type
        self.preprocess_status.visible = True

    def hide_status(self):
        """隐藏状态信息。"""
        self.preprocess_status.visible = False

    def get_panel(self) -> pn.layout.Panel:
        """返回处理视图的布局。"""
        return pn.Column(
            pn.pane.Markdown("## 数据处理与转换"),
            self.selected_data_info,
            pn.layout.Divider(),
            self.service_selector.get_panel(), # 使用 ServiceSelector 的 panel
            self.parameter_panel.get_panel(), # 使用 ParameterPanel 的 panel
            self.preprocess_button,
            self.preprocess_status,
            sizing_mode='stretch_width'
        ) 