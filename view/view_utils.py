import panel as pn
from typing import Dict, List, Optional, Any
import holoviews as hv
import param

def create_param_widgets(
    service_name: str,
    registry: dict,
    target_area: pn.Column,
    skipped_params: Optional[List[str]] = None
) -> Dict[str, pn.widgets.Widget]:
    """根据服务注册表中的参数规范动态创建 Panel 输入控件。

    Args:
        service_name (str): 已选择的服务名称 (主要用于错误/警告信息)。
        registry (dict): 包含服务注册信息 (包括 params_spec) 的字典。
        target_area (pn.Column): 用于放置生成的控件的 Panel Column 容器。
                                 此函数会先清空该容器。
        skipped_params (Optional[List[str]]): 需要跳过创建控件的参数名称列表。
                                              默认为 None (不跳过)。

    Returns:
        Dict[str, pn.widgets.Widget]: 一个字典，将参数名称映射到已创建的 Panel 控件实例。

    Raises:
        (打印错误/警告信息，但通常不直接引发异常，除非控件创建失败)

    params_spec 格式示例:
        {
            'window': {'type': 'integer', 'label': '窗口大小', 'default': 5, 'min': 1},
            'center': {'type': 'boolean', 'label': '中心对齐', 'default': False},
            'mode': {'type': 'select', 'label': '模式', 'options': ['A', 'B'], 'default': 'A'},
            'text': {'type': 'string', 'label': '标签', 'default': ''}
        }
    支持的类型字符串: 'integer', 'float', 'string', 'boolean', 'select', 'multiselect'。
    """
    target_area.clear() # 清空目标区域
    widgets = {}
    if skipped_params is None:
        skipped_params = []

    # 获取参数规范
    params_spec = registry.get(service_name, {}).get('params', {})

    # 处理没有参数或未选择服务的情况
    if not service_name:
        target_area.append(pn.pane.Markdown("请先选择一个操作。"))
        return widgets
    if not params_spec:
        target_area.append(pn.pane.Markdown("此操作无需额外参数。"))
        return widgets

    # 遍历参数规范，创建控件
    for name, spec in params_spec.items():
        # 跳过指定的参数
        if name in skipped_params:
            continue

        widget_type = spec.get('type', 'string').lower()
        label = spec.get('label', name) # 优先使用 label，否则使用参数名
        default = spec.get('default')
        
        # 准备控件的通用关键字参数
        # 对于 Checkbox，name 是标签，value 直接用布尔值
        # 对于其他大多数控件，name 是标签，value 是默认值
        kwargs = {'name': label} if widget_type != 'boolean' else {}

        widget: Optional[pn.widgets.Widget] = None
        try:
            # 根据类型创建不同的控件
            if widget_type == 'integer':
                num_kwargs = {'value': int(default) if default is not None else 0}
                if 'min' in spec: num_kwargs['start'] = spec['min']
                if 'max' in spec: num_kwargs['end'] = spec['max']
                if 'step' in spec: num_kwargs['step'] = spec['step']
                widget = pn.widgets.IntInput(**kwargs, **num_kwargs)
            elif widget_type == 'float':
                num_kwargs = {'value': float(default) if default is not None else 0.0}
                # FloatInput 不直接支持 min/max，但可以设置 start/end (范围)
                if 'min' in spec: num_kwargs['start'] = spec['min']
                if 'max' in spec: num_kwargs['end'] = spec['max']
                if 'step' in spec: num_kwargs['step'] = spec['step']
                widget = pn.widgets.FloatInput(**kwargs, **num_kwargs)
            elif widget_type == 'boolean':
                # Checkbox 特殊处理
                widget = pn.widgets.Checkbox(name=label, value=bool(default))
            elif widget_type == 'string':
                str_val = str(default) if default is not None else ''
                widget = pn.widgets.TextInput(**kwargs, value=str_val)
            elif widget_type == 'select' and 'options' in spec:
                opts = spec['options']
                # 确保默认值在选项中，否则使用第一个选项
                val = default if default in opts else (opts[0] if opts else None)
                widget = pn.widgets.Select(**kwargs, options=opts, value=val)
            elif widget_type == 'multiselect' and 'options' in spec:
                opts = spec['options']
                # 确保默认值是列表且在选项中
                val = default if isinstance(default, list) and all(v in opts for v in default) else []
                widget = pn.widgets.MultiSelect(**kwargs, options=opts, value=val)
            else:
                # 未知类型，回退到字符串输入
                print(f"警告：服务 \'{service_name}\' 的参数 \'{name}\' 遇到未知类型 \'{widget_type}\'，将使用文本输入框。")
                str_val = str(default) if default is not None else ''
                widget = pn.widgets.TextInput(**kwargs, value=str_val) # Fallback to TextInput

            # 如果成功创建了控件，添加到目标区域和字典中
            if widget:
                target_area.append(widget)
                widgets[name] = widget
        except Exception as e:
            # 处理控件创建过程中的错误
            print(f"错误：为服务 \'{service_name}\' 创建参数控件 \'{name}\' ({label}) 时失败: {e}")
            target_area.append(pn.pane.Alert(f"创建参数 \'{label}\' 失败: {e}", alert_type='danger'))
            
    return widgets

def update_visualization_area(target_area: pn.Column, content: Any) -> None:
    """更新目标 Panel Column 以显示可视化内容。

    智能处理不同类型的内容，如 HoloViews 对象、其他 Panel 对象、
    字符串 (视为消息) 或 None。

    Args:
        target_area (pn.Column): 需要更新内容的 Panel Column 容器。
                                此函数会先清空该容器并关闭加载指示器。
        content (Any): 要显示的可视化内容或消息。
    """
    target_area.clear()
    # 确保加载状态关闭
    if hasattr(target_area, 'loading'):
         target_area.loading = False 

    try:
        # 根据内容类型选择合适的 Panel Pane
        if isinstance(content, (hv.Layout, hv.NdLayout, hv.DynamicMap, hv.HoloMap, hv.Overlay, hv.Element)):
            # 对于 HoloViews 对象，使用 pn.pane.HoloViews
            target_area.append(pn.pane.HoloViews(content, sizing_mode='stretch_width'))
        elif isinstance(content, pn.viewable.Viewable):
            # 对于已经是 Panel 对象 (包括 Alert, Markdown, Column, Row 等)，直接添加
            target_area.append(content)
        elif isinstance(content, str):
            # 字符串视为普通消息或警告
            target_area.append(pn.pane.Alert(content, alert_type='warning')) # 默认为警告
        elif content is None:
            # None 表示没有内容生成
             target_area.append(pn.pane.Alert("未生成可视化内容。", alert_type='info'))
        else:
            # 尝试直接添加未知类型的内容，并打印警告
            print(f"警告: 尝试在可视化区域显示未知类型的内容: {type(content)}")
            target_area.append(content)
            
    except Exception as e:
        # 处理添加内容到 target_area 时可能发生的错误
        print(f"错误: 更新可视化区域时失败: {e}, 内容类型: {type(content)}")
        # 在目标区域显示错误信息
        try:
            target_area.clear() # 再次清空以防部分内容已添加
            target_area.append(pn.pane.Alert(f"无法显示结果 (类型: {type(content).__name__})\\n错误详情: {e}", alert_type='danger'))
        except Exception as fallback_e:
            # 如果连显示错误信息都失败，打印最终错误
            print(f"错误: 连显示错误 Alert 都失败: {fallback_e}")


# === 通用 UI 组件 ===

class ServiceSelector(param.Parameterized):
    """通用服务选择器组件。

    封装一个 `pn.widgets.Select` 用于从服务注册表中选择服务。
    提供 `selected_service_name` 和 `selected_service_info` 参数供外部监听。
    """
    registry = param.Dict({}, doc="服务注册表字典")
    selector_label = param.String("选择服务", doc="下拉选择器的标签文本")
    allow_none = param.Boolean(True, doc="是否允许不选择任何服务 (显示空选项)")

    # 输出参数 (供外部监听)
    selected_service_name = param.String(default=None, readonly=True, doc="当前选择的服务名称")
    selected_service_info = param.Dict(default={}, readonly=True, doc="当前选择的服务完整信息")

    # 内部 UI 组件 (不应直接从外部访问)
    _selector = param.Parameter() # 使用 param.Parameter 存储控件实例

    def __init__(self, **params):
        """初始化 ServiceSelector。

        Args:
            registry (dict): 包含服务名称到服务信息映射的服务注册表。
            selector_label (str): 选择器的标签。
            allow_none (bool): 是否允许空选项。
            **params: 其他 param.Parameterized 参数。
        """
        super().__init__(**params)
        self._selector = pn.widgets.Select(name=self.selector_label, sizing_mode='stretch_width')
        self._update_options() # 根据 registry 更新选项
        # 监听内部选择器值的变化，并更新输出参数
        self._selector.param.watch(self._on_select_change, 'value')
        # 首次触发以设置初始状态
        self._update_selected_service(self._selector.value)

    @param.depends('registry', watch=True)
    def _update_options(self):
        """当注册表变化时，更新下拉选项。"""
        options = sorted(list(self.registry.keys()))
        current_value = self._selector.value
        
        if self.allow_none:
             # 如果允许空选项，确保它在列表开头
             if ' ' not in options:
                 options.insert(0, ' ')
        else:
            # 如果不允许，移除可能存在的空选项
            options = [opt for opt in options if opt != ' ']
            
        self._selector.options = options
        
        # 尝试恢复之前的选项，如果不存在或不允许则设为默认
        if current_value in options:
            self._selector.value = current_value
        elif options and not self.allow_none:
            self._selector.value = options[0]
        elif self.allow_none:
            self._selector.value = ' '
        else: # 没有选项且不允许为空
             self._selector.value = None

    def _on_select_change(self, event):
        """当内部选择器值变化时，更新输出参数。"""
        self._update_selected_service(event.new)

    def _update_selected_service(self, service_name):
        """根据选择的名称更新 selected_service_name 和 selected_service_info。"""
        valid_name = service_name if service_name and service_name != ' ' else None
        # 使用 internal _setattr 来设置 readonly 参数
        self.param.update(
            selected_service_name=valid_name,
            selected_service_info=self.registry.get(valid_name, {}) if valid_name else {}
        )

    def get_panel(self) -> pn.widgets.Select:
        """返回内部的 Panel Select 控件。"""
        return self._selector

class ParameterPanel(param.Parameterized):
    """根据参数规范动态生成参数输入 UI 的 Panel 组件。"""
    params_spec = param.Dict(default={}, doc="服务的参数规范字典 (params_spec)")

    # 内部状态
    _param_widgets = param.Dict(default={}, readonly=True, doc="参数名到控件实例的映射")
    _container = param.Parameter() # 存储 Panel Column 容器

    def __init__(self, **params):
        """初始化 ParameterPanel。

        Args:
            params_spec (dict): 初始的参数规范字典。
            **params: 其他 param.Parameterized 参数。
        """
        super().__init__(**params)
        self._container = pn.Column(sizing_mode='stretch_width')
        # 监视 params_spec 参数的变化，变化时自动更新 UI
        self.param.watch(self._regenerate_ui, 'params_spec')
        # 初始生成一次 UI
        self._regenerate_ui()

    def _regenerate_ui(self, *events):
        """当 params_spec 变化时，重新生成参数 UI。"""
        # 使用 create_param_widgets 函数来实际创建控件
        # 注意：这里 service_name 和 registry 只是为了满足函数签名，
        # 实际的 params_spec 来自 self.params_spec
        new_widgets = create_param_widgets(
            service_name="_ParameterPanel_", # 提供虚拟名称
            registry={"_ParameterPanel_": {"params": self.params_spec}}, # 包装 spec
            target_area=self._container # 在内部容器中生成
        )
        # 更新内部只读参数
        self.param.update(_param_widgets=new_widgets)


    def get_params(self) -> Dict[str, Any]:
        """从当前显示的控件中获取所有参数的值。

        Returns:
            一个字典，将参数名称映射到其当前值。

        Raises:
            AttributeError: 如果某个控件没有 'value' 属性 (理论上不应发生)。
            Exception: 获取控件值时发生的其他潜在错误。
        """
        params = {}
        for name, widget in self._param_widgets.items():
            try:
                # 特别处理 CheckboxGroup 和 MultiSelect (它们的值已经是列表)
                if isinstance(widget, (pn.widgets.CheckboxGroup, pn.widgets.MultiSelect)):
                    params[name] = widget.value
                # 对于其他控件，直接获取 value
                elif hasattr(widget, 'value'):
                     params[name] = widget.value
                else:
                     print(f"警告: 控件 \'{name}\' ({type(widget)}) 没有 \'value\' 属性。")
                     params[name] = None # 或者跳过？
            except Exception as e:
                print(f"错误: 获取参数 \'{name}\' 的值时出错: {e}")
                # 可以选择：抛出异常 / 返回部分结果 / 返回 None 表示失败
                raise  # 重新抛出异常，让调用者知道获取参数失败
        return params

    def get_panel(self) -> pn.Column:
        """返回包含动态生成参数控件的 Panel Column 容器。"""
        return self._container

# 移除文件末尾的组件注释 