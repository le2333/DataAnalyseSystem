import panel as pn
import param
import holoviews as hv
from typing import Dict, Any, List, Optional, Type
from model.data_manager import DataManager
from services.registry import VISUALIZERS
# Import specific data types for filtering service list
from model.timeseries_data import TimeSeriesData
from model.multidim_data import MultiDimData
# Import the new utility functions
from .view_utils import create_param_widgets, update_visualization_area

pn.extension(sizing_mode="stretch_width")

class ExplorationView(param.Parameterized):
    """提供单个数据的交互式、动态更新可视化探索。"""
    data_manager = param.Parameter(precedence=-1)
    selected_data_id = param.String(default="")

    # UI 组件
    selected_data_info = param.ClassSelector(class_=pn.pane.Markdown, is_instance=True)
    visualizer_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True)
    visualizer_params_area = param.ClassSelector(class_=pn.Column, is_instance=True)
    visualize_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    visualization_area = param.ClassSelector(class_=pn.Column, is_instance=True)

    # Remove current_plot parameter
    # current_plot = param.Parameter()

    _current_visualizer_widgets: Dict[str, pn.widgets.Widget] = param.Dict(default={})
    _available_visualizers_for_current_data: List[str] = param.List(default=[])

    def __init__(self, data_manager: DataManager, **params):
        super().__init__(data_manager=data_manager, **params)
        self._create_ui_components()
        self._update_selected_data_info() # Initial update

    def _create_ui_components(self):
        self.selected_data_info = pn.pane.Markdown("未选择数据。")
        self.visualizer_selector = pn.widgets.Select(name="选择可视化方法", options=[])
        self.visualizer_params_area = pn.Column(sizing_mode='stretch_width')
        self.visualize_button = pn.widgets.Button(name="生成/更新可视化", button_type="primary", disabled=True)
        # Initialize visualization_area with placeholder
        self.visualization_area = pn.Column(pn.pane.Alert("可视化结果将显示在此处。", alert_type='info'), sizing_mode='stretch_both')

        self.visualizer_selector.param.watch(self._on_visualizer_select, 'value')
        # Remove watcher for current_plot

    @param.depends('selected_data_id', watch=True)
    def _update_on_data_selection(self):
        """数据选择变化时，更新信息、过滤可视化选项、重置状态。"""
        self._update_selected_data_info()
        self._filter_and_update_visualizer_options()
        self.visualizer_params_area.clear()
        # Reset visualization area directly here
        update_visualization_area(self.visualization_area, pn.pane.Alert("请选择可视化方法并点击生成。", alert_type='info'))
        self._current_visualizer_widgets = {}
        self.visualize_button.disabled = True

    def _update_selected_data_info(self):
        if not self.selected_data_id:
            self.selected_data_info.object = "**当前未选择数据**"
            self.visualize_button.disabled = True
            return
        dc = self.data_manager.get_data(self.selected_data_id)
        if dc:
            info_str = f"**选定数据:** {dc.name} ({dc.data_type})"
        else:
            info_str = f"**错误:** 未找到数据 ID {self.selected_data_id}"
            self.selected_data_id = "" # Reset if not found?
        self.selected_data_info.object = info_str
        # Enable button only if service is also selected
        self.visualize_button.disabled = not bool(self.visualizer_selector.value)

    def _filter_and_update_visualizer_options(self):
        options = ['']
        data_container = self.data_manager.get_data(self.selected_data_id)
        if data_container:
            current_data_type = type(data_container)
            for name, info in VISUALIZERS.items():
                input_type = info.get('input_type')
                # Check if service expects single item and type matches
                if isinstance(input_type, type) and issubclass(current_data_type, input_type):
                    options.append(name)
                # Allow services with no specific input type (generic?)
                # elif input_type is None:
                #     options.append(name)
        self.visualizer_selector.options = sorted(list(set(options))) # Ensure unique & sorted
        # Reset selection if current selection is no longer valid
        if self.visualizer_selector.value not in options:
             self.visualizer_selector.value = '' # Reset to blank
        self._on_visualizer_select(None) # Trigger param update

    def _on_visualizer_select(self, event):
        service_name = self.visualizer_selector.value
        # Call the utility function, skipping 'width'
        self._current_visualizer_widgets = create_param_widgets(
            service_name=service_name,
            registry=VISUALIZERS,
            target_area=self.visualizer_params_area,
            skipped_params=['width'] # Skip width for visualizers
        )
        self.visualize_button.disabled = not bool(service_name and self.selected_data_id)

    def update_visualization_area_display(self, content: Any):
        """Updates the visualization display area using the utility function."""
        update_visualization_area(self.visualization_area, content)

    def get_exploration_config(self) -> Optional[Dict[str, Any]]:
        """获取当前探索配置。"""
        service_name = self.visualizer_selector.value
        # Basic check - ensure data ID exists
        if not service_name or not self.selected_data_id:
            return None
        # Double check data exists in manager before returning config
        if not self.data_manager.get_data(self.selected_data_id):
            print(f"Warning: Data ID {self.selected_data_id} no longer valid in get_exploration_config.")
            return None

        config = {
            'selected_data_id': self.selected_data_id,
            'service_name': service_name,
            'params': {}
        }
        for name, widget in self._current_visualizer_widgets.items():
            try:
                 config['params'][name] = widget.value
            except Exception as e:
                 print(f"错误: 获取探索参数 '{name}' 的值失败: {e}")
                 return None
        return config

    def get_panel(self) -> pn.layout.Panel:
        # ... layout remains the same ...
        controls_column = pn.Column(
            pn.pane.Markdown("### 可视化方法与参数"),
            self.visualizer_selector,
            self.visualizer_params_area,
            self.visualize_button,
            sizing_mode='stretch_width'
        )
        controls_card = pn.Card(
            controls_column,
            title="可视化设置",
            collapsible=True,
            sizing_mode='stretch_width'
        )
        layout = pn.Column(
            pn.pane.Markdown("## 数据探索"),
            self.selected_data_info,
            pn.layout.Divider(),
            controls_card,
            self.visualization_area,
            sizing_mode='stretch_width'
        )
        self.visualization_area.sizing_mode = 'stretch_width'
        return layout 