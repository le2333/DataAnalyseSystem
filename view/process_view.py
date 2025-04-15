import panel as pn
import param
from typing import List, Dict, Any, Optional
from model.data_manager import DataManager
from services.registry import PREPROCESSORS

pn.extension(sizing_mode="stretch_width")

class ProcessView(param.Parameterized):
    """执行数据处理与转换操作的视图。"""
    data_manager = param.Parameter(precedence=-1)
    # 由 AppController 设置当前选中的数据 ID
    selected_data_ids = param.List(default=[])

    # UI 组件
    selected_data_info = param.ClassSelector(class_=pn.pane.Markdown, is_instance=True)
    preprocessor_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True)
    preprocessor_params_area = param.ClassSelector(class_=pn.Column, is_instance=True)
    preprocess_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    preprocess_status = param.ClassSelector(class_=pn.pane.Alert, is_instance=True)

    # 存储动态生成的参数控件
    _current_preprocessor_widgets: Dict[str, pn.widgets.Widget] = param.Dict(default={})

    def __init__(self, data_manager: DataManager, **params):
        super().__init__(data_manager=data_manager, **params)
        self._create_ui_components()
        self._update_preprocessor_options()
        self._update_selected_data_info() # Initial update

    def _create_ui_components(self):
        self.selected_data_info = pn.pane.Markdown("未选择数据。")
        self.preprocessor_selector = pn.widgets.Select(name="选择处理方法", options=[])
        self.preprocessor_params_area = pn.Column(sizing_mode='stretch_width')
        self.preprocess_button = pn.widgets.Button(name="执行处理", button_type="success", disabled=True)
        self.preprocess_status = pn.pane.Alert("", alert_type='info', visible=False)

        # 监听选择变化
        self.preprocessor_selector.param.watch(self._on_preprocessor_select, 'value')

    @param.depends('selected_data_ids', watch=True)
    def _update_selected_data_info(self):
        """更新顶部显示已选数据的信息。"""
        if not self.selected_data_ids:
            self.selected_data_info.object = "**当前未选择数据**"
            self.preprocess_button.disabled = True
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
        # 只有选择了处理器才能启用按钮
        self.preprocess_button.disabled = not bool(self.preprocessor_selector.value)


    def _update_preprocessor_options(self):
        """从注册表更新预处理器选项。"""
        options = [''] + sorted(list(PREPROCESSORS.keys())) # 添加空选项并排序
        self.preprocessor_selector.options = options
        self._on_preprocessor_select(None) # 初始化参数区域

    def _on_preprocessor_select(self, event):
        """当预处理器选择变化时，动态生成参数 UI。"""
        service_name = self.preprocessor_selector.value
        self._current_preprocessor_widgets = self._create_param_widgets(service_name, PREPROCESSORS, self.preprocessor_params_area)
        # 启用/禁用按钮
        self.preprocess_button.disabled = not bool(service_name and self.selected_data_ids)

    # 基本复用 VisualizationView 中的参数生成逻辑
    def _create_param_widgets(self, service_name: str, registry: dict, target_area: pn.Column) -> Dict[str, pn.widgets.Widget]:
        target_area.clear()
        widgets = {}
        if not service_name:
             target_area.append(pn.pane.Markdown("请先选择一个处理方法。"))
             return widgets

        params_spec = registry.get(service_name, {}).get('params', {})
        if not params_spec:
            target_area.append(pn.pane.Markdown("此操作无需额外参数。"))
            return widgets

        for name, spec in params_spec.items():
            widget_type = spec.get('type', 'string').lower()
            label = spec.get('label', name)
            default = spec.get('default')
            kwargs = {'name': label, 'value': default}
            widget = None
            try:
                if widget_type == 'integer':
                    widget = pn.widgets.IntInput(**kwargs)
                elif widget_type == 'float':
                    widget = pn.widgets.FloatInput(**kwargs)
                elif widget_type == 'boolean':
                    widget = pn.widgets.Checkbox(name=label, value=bool(default))
                elif widget_type == 'string':
                    widget = pn.widgets.TextInput(**kwargs)
                # 可以添加更多类型，如 Select 等
                else:
                    print(f"警告：未知的参数类型 '{widget_type}' for {name} in service '{service_name}'")
                    widget = pn.widgets.TextInput(name=label, value=str(default))

                if widget:
                    target_area.append(widget)
                    widgets[name] = widget
            except Exception as e:
                 print(f"错误：创建参数控件 '{name}' ({label}) for service '{service_name}' 失败: {e}")
                 target_area.append(pn.pane.Alert(f"创建参数 '{label}' 失败: {e}", alert_type='danger'))
        return widgets

    def get_process_config(self) -> Optional[Dict[str, Any]]:
        """获取当前处理配置。"""
        service_name = self.preprocessor_selector.value
        if not service_name or not self.selected_data_ids:
            return None # Or raise error

        config = {
            'selected_data_ids': self.selected_data_ids,
            'service_name': service_name,
            'params': {}
        }
        for name, widget in self._current_preprocessor_widgets.items():
             try:
                 config['params'][name] = widget.value
             except Exception as e:
                 print(f"错误: 获取预处理参数 '{name}' 的值失败: {e}")
                 # 可以选择返回 None 或抛出异常
                 return None
        return config

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
            self.preprocessor_selector,
            self.preprocessor_params_area,
            self.preprocess_button,
            self.preprocess_status,
            sizing_mode='stretch_width'
        ) 