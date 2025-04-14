import panel as pn
import param
import holoviews as hv
from typing import Dict, Any, List
# 假设 DataManager 和服务注册表会被 Controller 注入
# 导入 TimeSeriesData 用于类型提示
from model.timeseries_data import TimeSeriesData

pn.extension(sizing_mode="stretch_width")

class VisualizationView(param.Parameterized):
    """数据可视化视图。"""
    data_manager = param.Parameter(precedence=-1)
    available_visualizers = param.Dict(default={}, precedence=-1) # 可用的可视化服务
    available_preprocessors = param.Dict(default={}, precedence=-1) # 可用的预处理服务

    # UI 组件
    data_selector = param.ClassSelector(class_=pn.widgets.MultiSelect, is_instance=True)
    visualizer_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True)
    visualizer_params_area = param.ClassSelector(class_=pn.Column, is_instance=True)
    visualize_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    visualization_area = param.ClassSelector(class_=pn.Column, is_instance=True)
    # 添加预处理部分
    preprocessor_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True)
    preprocessor_params_area = param.ClassSelector(class_=pn.Column, is_instance=True)
    preprocess_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    preprocess_status = param.ClassSelector(class_=pn.pane.Alert, is_instance=True)

    # 存储动态生成的参数控件
    _current_visualizer_widgets: Dict[str, pn.widgets.Widget] = param.Dict(default={})
    _current_preprocessor_widgets: Dict[str, pn.widgets.Widget] = param.Dict(default={})

    def __init__(self, data_manager, visualizers, preprocessors, **params):
        super().__init__(data_manager=data_manager, available_visualizers=visualizers, available_preprocessors=preprocessors, **params)
        self._create_ui_components()
        self._update_data_options()
        self._update_service_options()

    def _create_ui_components(self):
        self.data_selector = pn.widgets.MultiSelect(name="选择一维数据", options=[], size=8)
        # 可视化
        self.visualizer_selector = pn.widgets.Select(name="选择可视化方法", options=[])
        self.visualizer_params_area = pn.Column(sizing_mode='stretch_width')
        self.visualize_button = pn.widgets.Button(name="生成可视化", button_type="primary")
        self.visualization_area = pn.Column(pn.pane.Alert("可视化结果将显示在此处。", alert_type='info'), sizing_mode='stretch_width')
        # 预处理
        self.preprocessor_selector = pn.widgets.Select(name="选择预处理方法", options=[])
        self.preprocessor_params_area = pn.Column(sizing_mode='stretch_width')
        self.preprocess_button = pn.widgets.Button(name="执行预处理", button_type="success")
        self.preprocess_status = pn.pane.Alert("", alert_type='info', visible=False)

        # 监听选择变化
        self.visualizer_selector.param.watch(self._on_visualizer_select, 'value')
        self.preprocessor_selector.param.watch(self._on_preprocessor_select, 'value')

    @param.depends('data_manager._data_updated', watch=True)
    def _update_data_options(self):
        # 从 DataManager 获取 TimeSeriesData 选项
        options = self.data_manager.get_data_options(filter_type=TimeSeriesData)
        current_selection = self.data_selector.value
        self.data_selector.options = options
        # 尝试保留之前的选择
        valid_selection = [s for s in current_selection if s in dict(options)]
        self.data_selector.value = valid_selection

    def _update_service_options(self):
        vis_options = [''] + list(self.available_visualizers.keys()) # 添加空选项
        prep_options = [''] + list(self.available_preprocessors.keys()) # 添加空选项
        self.visualizer_selector.options = vis_options
        self.preprocessor_selector.options = prep_options
        # 初始化参数区域
        self._on_visualizer_select(None)
        self._on_preprocessor_select(None)

    def _create_param_widgets(self, service_name: str, registry: dict, target_area: pn.Column) -> Dict[str, pn.widgets.Widget]:
        target_area.clear()
        widgets = {}
        if not service_name:
             target_area.append(pn.pane.Markdown("请先选择一个操作。"))
             return widgets
             
        params_spec = registry.get(service_name, {}).get('params', {})
        if not params_spec:
            target_area.append(pn.pane.Markdown("此操作无需额外参数。"))
            return widgets

        for name, spec in params_spec.items():
            # Skip height and add_minimap for the specific Plot Time Series service
            if service_name == "Plot Time Series" and name in ['height', 'add_minimap']:
                continue

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
                    if spec.get('widget') == 'file': # 文件选择特殊处理
                        widget = pn.widgets.FileInput(name=label, multiple=False) # 假设服务只处理单个文件
                    else:
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

    def _on_visualizer_select(self, event):
        service_name = self.visualizer_selector.value
        self._current_visualizer_widgets = self._create_param_widgets(service_name, self.available_visualizers, self.visualizer_params_area)

    def _on_preprocessor_select(self, event):
        service_name = self.preprocessor_selector.value
        self._current_preprocessor_widgets = self._create_param_widgets(service_name, self.available_preprocessors, self.preprocessor_params_area)

    def get_visualization_config(self) -> Dict[str, Any]:
        """获取当前可视化配置。"""
        config = {
            'selected_data_ids': self.data_selector.value,
            'service_name': self.visualizer_selector.value,
            'params': {}
        }
        for name, widget in self._current_visualizer_widgets.items():
            try:
                 config['params'][name] = widget.value
            except Exception as e:
                 print(f"错误: 获取可视化参数 '{name}' 的值失败: {e}")
                 # 可以选择抛出异常或给默认值
        return config

    def get_preprocess_config(self) -> Dict[str, Any]:
        """获取当前预处理配置。"""
        config = {
            'selected_data_ids': self.data_selector.value,
            'service_name': self.preprocessor_selector.value,
            'params': {}
        }
        for name, widget in self._current_preprocessor_widgets.items():
             try:
                 config['params'][name] = widget.value
             except Exception as e:
                 print(f"错误: 获取预处理参数 '{name}' 的值失败: {e}")
        return config

    def update_visualization_area(self, content: pn.layout.Panel | hv.Layout | hv.DynamicMap | hv.HoloMap | str):
        self.visualization_area.clear()
        if isinstance(content, str):
            self.visualization_area.append(pn.pane.Alert(content, alert_type='warning'))
        elif isinstance(content, (hv.Layout, hv.DynamicMap, hv.HoloMap)):
             # 确保 HoloViews 对象正确渲染
             try:
                 hv_pane = pn.pane.HoloViews(content, sizing_mode='stretch_width')
                 self.visualization_area.append(hv_pane)
             except Exception as e:
                  print(f"渲染 HoloViews 对象失败: {e}")
                  self.visualization_area.append(pn.pane.Alert(f"渲染图表失败: {e}", alert_type='danger'))
        elif isinstance(content, pn.layout.Panel):
            self.visualization_area.append(content)
        else:
             # 尝试直接添加未知类型，如果失败则显示错误
             try:
                 self.visualization_area.append(content)
             except Exception as e:
                  print(f"更新可视化区域失败，内容类型不支持: {type(content)}, error: {e}")
                  self.visualization_area.append(pn.pane.Alert(f"无法显示结果 (类型: {type(content).__name__})", alert_type='danger'))

    def show_preprocess_status(self, message: str, alert_type: str = 'info'):
        self.preprocess_status.object = message
        self.preprocess_status.alert_type = alert_type
        self.preprocess_status.visible = True

    def hide_preprocess_status(self):
        self.preprocess_status.visible = False

    def get_panel(self) -> pn.layout.Panel:
        """返回一维处理与可视化页面的布局。"""
        preprocess_card = pn.Card(
            pn.Column(
                self.preprocessor_selector,
                self.preprocessor_params_area,
                self.preprocess_button,
                self.preprocess_status
            ),
            title="数据预处理",
            collapsed=False,
            sizing_mode='stretch_width'
        )
        
        visualize_card = pn.Card(
            pn.Column(
                self.visualizer_selector,
                self.visualizer_params_area,
                self.visualize_button
            ),
            title="数据可视化",
            collapsed=False,
            sizing_mode='stretch_width'
        )
        
        main_layout = pn.Row(
            pn.Column( # 左侧：数据选择和操作
                pn.pane.Markdown("### 1. 选择数据"),
                self.data_selector,
                pn.pane.Markdown("### 2. 执行操作"),
                preprocess_card,
                visualize_card,
                width=400 # 固定左侧宽度
            ),
            pn.Column( # 右侧：可视化结果
                 pn.pane.Markdown("### 可视化结果"),
                 self.visualization_area,
                 sizing_mode='stretch_both' # 占据剩余空间
            ),
            sizing_mode='stretch_width'
        )
        
        return pn.Column(
            pn.pane.Markdown("## 一维数据处理与可视化"),
            main_layout,
            sizing_mode='stretch_width'
        ) 