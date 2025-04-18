import panel as pn
import param
import holoviews as hv
from typing import Dict, Any, List, Optional
from model.data_manager import DataManager
from services.registry import VISUALIZERS # 只需 VISUALIZERS
from .view_utils import create_param_widgets, update_visualization_area

pn.extension(sizing_mode="stretch_width")

class ComparisonView(param.Parameterized):
    """应用标准可视化模板比较多个同类型数据。"""
    data_manager = param.Parameter(precedence=-1)
    # 由 AppController 设置当前选中的数据 ID
    selected_data_ids = param.List(default=[])

    # UI 组件
    selected_data_info = param.ClassSelector(class_=pn.pane.Markdown, is_instance=True)
    visualizer_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True)
    visualizer_params_area = param.ClassSelector(class_=pn.Column, is_instance=True)
    visualize_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    visualization_area = param.ClassSelector(class_=pn.Column, is_instance=True)

    # 存储动态生成的参数控件
    _current_visualizer_widgets: Dict[str, pn.widgets.Widget] = param.Dict(default={})

    def __init__(self, data_manager: DataManager, **params):
        super().__init__(data_manager=data_manager, **params)
        self._create_ui_components()
        self._update_visualizer_options()
        self._update_selected_data_info() # Initial update

    def _create_ui_components(self):
        self.selected_data_info = pn.pane.Markdown("未选择数据。")
        self.visualizer_selector = pn.widgets.Select(name="选择可视化方法", options=[])
        self.visualizer_params_area = pn.Column(sizing_mode='stretch_width')
        self.visualize_button = pn.widgets.Button(name="生成可视化", button_type="primary", disabled=True)
        self.visualization_area = pn.Column(pn.pane.Alert("可视化结果将显示在此处。", alert_type='info'), sizing_mode='stretch_both')

        # 监听选择变化
        self.visualizer_selector.param.watch(self._on_visualizer_select, 'value')

    @param.depends('selected_data_ids', watch=True)
    def _update_selected_data_info(self):
        """更新顶部显示已选数据的信息。"""
        if not self.selected_data_ids:
            self.selected_data_info.object = "**当前未选择数据**"
            self.visualize_button.disabled = True
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
        # 只有选择了可视化器才能启用按钮 (还需要检查数据类型和数量是否匹配)
        self.visualize_button.disabled = not bool(self.visualizer_selector.value)
        # 可以在 Controller 中做更严格的检查来禁用按钮

    def _update_visualizer_options(self):
        """从注册表更新可视化器选项。"""
        options = [''] + sorted(list(VISUALIZERS.keys()))
        self.visualizer_selector.options = options
        self._on_visualizer_select(None) # 初始化参数区域

    def _on_visualizer_select(self, event):
        service_name = self.visualizer_selector.value
        self._current_visualizer_widgets = create_param_widgets(
            service_name=service_name,
            registry=VISUALIZERS,
            target_area=self.visualizer_params_area,
            skipped_params=['width'] # Skip width for visualizers
        )
        self.visualize_button.disabled = not bool(service_name and self.selected_data_ids)

    def get_visualization_config(self) -> Optional[Dict[str, Any]]:
        """获取当前可视化配置。"""
        service_name = self.visualizer_selector.value
        if not service_name or not self.selected_data_ids:
            return None

        config = {
            'selected_data_ids': self.selected_data_ids,
            'service_name': service_name,
            'params': {}
        }
        for name, widget in self._current_visualizer_widgets.items():
            try:
                 config['params'][name] = widget.value
            except Exception as e:
                 print(f"错误: 获取可视化参数 '{name}' 的值失败: {e}")
                 return None
        return config

    def update_visualization_area_display(self, content: Any):
        """Updates the visualization display area using the utility function."""
        update_visualization_area(self.visualization_area, content)

    def get_panel(self) -> pn.layout.Panel:
        """返回比较视图的布局。"""
        controls = pn.Column(
            pn.pane.Markdown("### 可视化设置"),
            self.visualizer_selector,
            self.visualizer_params_area,
            self.visualize_button
        )

        layout = pn.Row(
            pn.Column( # 左侧: 数据信息和控制
                pn.pane.Markdown("## 可视化比较"),
                self.selected_data_info,
                pn.layout.Divider(),
                controls,
                width=350 # 固定左侧宽度
            ),
            pn.Column( # 右侧: 可视化结果
                 self.visualization_area,
                 sizing_mode='stretch_both'
            ),
            sizing_mode='stretch_width'
        )
        return layout 