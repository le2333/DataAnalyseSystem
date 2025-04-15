import panel as pn
import param
import holoviews as hv
from typing import Dict, Any, List, Optional, Type
from model.data_manager import DataManager
from services.registry import VISUALIZERS
# Import specific data types for filtering service list
from model.timeseries_data import TimeSeriesData
from model.multidim_data import MultiDimData

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
        self.visualization_area.clear()
        self.visualization_area.append(pn.pane.Alert("请选择可视化方法并点击生成。", alert_type='info'))
        self._current_visualizer_widgets = {}
        self.visualize_button.disabled = True

    # ... _update_selected_data_info, _filter_and_update_visualizer_options, _create_param_widgets, _on_visualizer_select, get_exploration_config methods remain the same ...

    # Re-introduce update_visualization_area method
    def update_visualization_area(self, content: Any):
        self.visualization_area.clear()
        try:
            if isinstance(content, (hv.Layout, hv.DynamicMap, hv.HoloMap, hv.Overlay, hv.Element)):
                # Ensure stretch_width for HoloViews pane
                self.visualization_area.append(pn.pane.HoloViews(content, sizing_mode='stretch_width'))
            elif isinstance(content, pn.viewable.Viewable):
                self.visualization_area.append(content)
            elif isinstance(content, str):
                # Assume string is a message (e.g., error)
                self.visualization_area.append(pn.pane.Alert(content, alert_type='warning'))
            else:
                # Try adding unknown content directly
                self.visualization_area.append(content)
        except Exception as e:
              print(f"更新可视化区域失败: {e}, 内容类型: {type(content)}")
              self.visualization_area.append(pn.pane.Alert(f"无法显示结果 (类型: {type(content).__name__})\n错误: {e}", alert_type='danger'))

    # Remove _update_plot_display method
    # @param.depends('current_plot', watch=True)
    # def _update_plot_display(self):
    #    ...

    # Add the missing _on_visualizer_select method back
    def _on_visualizer_select(self, event):
        """Called when a visualizer is selected from the dropdown."""
        service_name = self.visualizer_selector.value
        # Use the existing _create_param_widgets method to update the UI
        self._current_visualizer_widgets = self._create_param_widgets(service_name, VISUALIZERS, self.visualizer_params_area)
        # Enable button only if a valid service and data are selected
        self.visualize_button.disabled = not bool(service_name and self.selected_data_id)

    def get_exploration_config(self) -> Optional[Dict[str, Any]]:
        """获取当前探索配置。"""
        service_name = self.visualizer_selector.value
        # ... rest of the file ...

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