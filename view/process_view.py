import panel as pn
import param
from typing import List, Dict, Any, Optional
from model.data_manager import DataManager
from services.registry import PREPROCESSORS
from .view_utils import create_param_widgets

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
        self._current_preprocessor_widgets = create_param_widgets(
            service_name=service_name,
            registry=PREPROCESSORS,
            target_area=self.preprocessor_params_area
        )
        # 启用/禁用按钮
        self.preprocess_button.disabled = not bool(service_name and self.selected_data_ids)

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