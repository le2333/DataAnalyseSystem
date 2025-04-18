import panel as pn
from typing import Dict, List, Optional, Any
import holoviews as hv

def create_param_widgets(
    service_name: str,
    registry: dict,
    target_area: pn.Column,
    skipped_params: Optional[List[str]] = None
) -> Dict[str, pn.widgets.Widget]:
    """
    Dynamically creates Panel widgets based on parameter specifications from a service registry.

    Args:
        service_name: The name of the selected service.
        registry: The dictionary containing service registrations.
        target_area: The Panel Column container where widgets will be added.
        skipped_params: A list of parameter names to skip creating widgets for.

    Returns:
        A dictionary mapping parameter names to their created widgets.
    """
    target_area.clear()
    widgets = {}
    if skipped_params is None:
        skipped_params = []

    if not service_name:
        target_area.append(pn.pane.Markdown("请先选择一个操作方法。")) # Generic message
        return widgets

    params_spec = registry.get(service_name, {}).get('params', {})
    if not params_spec:
        target_area.append(pn.pane.Markdown("此操作无需额外参数。"))
        return widgets

    for name, spec in params_spec.items():
        if name in skipped_params:
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
                # Checkbox uses name for label, value directly
                widget = pn.widgets.Checkbox(name=label, value=bool(default))
            elif widget_type == 'string':
                 # Ensure value is string for TextInput
                kwargs['value'] = str(default) if default is not None else ''
                widget = pn.widgets.TextInput(**kwargs)
            # Can add more types here, e.g., Select
            else:
                print(f"警告：未知的参数类型 '{widget_type}' for {name} in service '{service_name}'")
                widget = pn.widgets.TextInput(name=label, value=str(default) if default is not None else '') # Fallback to TextInput

            if widget:
                target_area.append(widget)
                widgets[name] = widget
        except Exception as e:
            print(f"错误：创建参数控件 '{name}' ({label}) for service '{service_name}' 失败: {e}")
            target_area.append(pn.pane.Alert(f"创建参数 '{label}' 失败: {e}", alert_type='danger'))
    return widgets

def update_visualization_area(target_area: pn.Column, content: Any):
    """
    Updates the target Panel Column with the provided visualization content.
    Handles different types of content like HoloViews objects, Panel viewables, or strings.

    Args:
        target_area: The Panel Column where the content should be displayed.
        content: The visualization content to display.
    """
    target_area.clear()
    target_area.loading = False # Ensure loading indicator is off
    try:
        # Attempt to handle different content types intelligently
        if isinstance(content, (hv.Layout, hv.NdLayout, hv.DynamicMap, hv.HoloMap, hv.Overlay, hv.Element)):
            target_area.append(pn.pane.HoloViews(content, sizing_mode='stretch_width'))
        elif isinstance(content, pn.viewable.Viewable):
            target_area.append(content)
        elif isinstance(content, str):
            # Assume string is a warning or error message
            target_area.append(pn.pane.Alert(content, alert_type='warning'))
        elif content is None:
             target_area.append(pn.pane.Alert("未生成可视化内容。", alert_type='info'))
        else:
            # Try adding unknown content directly
            print(f"Warning: Attempting to display unknown content type: {type(content)}")
            target_area.append(content)
    except Exception as e:
        print(f"更新可视化区域失败: {e}, 内容类型: {type(content)}")
        # Display error within the target area
        target_area.clear()
        target_area.append(pn.pane.Alert(f"无法显示结果 (类型: {type(content).__name__})\n错误: {e}", alert_type='danger'))

# Add update_visualization_area here in the next step if desired 