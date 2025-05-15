import panel as pn
import param
from typing import List, Dict, Any, Callable
from viewmodel.process_viewmodel import ProcessViewModel


def create_process_view(
    viewmodel: ProcessViewModel, navigate_callback: Callable
) -> pn.Column:
    """创建数据处理视图

    Args:
        viewmodel: 数据处理视图模型
        navigate_callback: 导航回调函数

    Returns:
        Panel布局组件
    """
    # --- 选中数据信息区域 ---
    selected_data_info = pn.pane.Markdown(
        viewmodel.get_selected_data_info(), sizing_mode="stretch_width"
    )

    # 更新数据信息
    def update_data_info(event=None):
        selected_data_info.object = viewmodel.get_selected_data_info()

    viewmodel.param.watch(update_data_info, "selected_data_ids")

    # --- 服务选择区域 ---
    # 预处理器选择
    preprocessor_options = [
        (name, name) for name in viewmodel.get_preprocessor_services().keys()
    ]
    service_selector = pn.widgets.Select(
        name="选择处理方法",
        options=preprocessor_options if preprocessor_options else [("", "")],
    )

    # 监听预处理器选择变化
    def on_service_select(event):
        if event.new:
            viewmodel.selected_service_name = event.new

    service_selector.param.watch(on_service_select, "value")

    # --- 参数配置区域 ---
    # 动态参数面板容器
    params_container = pn.Column(sizing_mode="stretch_width")

    # 更新参数面板
    def update_params(event=None):
        service_name = viewmodel.selected_service_name
        if service_name:
            params_spec = viewmodel.get_service_params(service_name)
            params_container.clear()
            params_container.append(pn.pane.Markdown("### 处理参数"))

            # 为每个参数创建对应的输入组件
            param_widgets = create_param_widgets(params_spec)
            for widget in param_widgets:
                params_container.append(widget)
             else:
            params_container.clear()

    # 监听服务选择变化更新参数面板
    viewmodel.param.watch(update_params, "selected_service_name")

    # --- 状态和操作区域 ---
    status_alert = pn.pane.Alert(
        viewmodel.status_message,
        alert_type=viewmodel.status_type,
        visible=viewmodel.status_visible,
    )

    # 更新状态信息
    def update_status(event=None):
        status_alert.object = viewmodel.status_message
        status_alert.alert_type = viewmodel.status_type
        status_alert.visible = viewmodel.status_visible

    viewmodel.param.watch(
        update_status, ["status_message", "status_type", "status_visible"]
    )

    # 处理按钮
    process_button = pn.widgets.Button(
        name="执行处理", button_type="success", disabled=True
    )

    # 更新按钮状态
    def update_button_state(event=None):
        process_button.disabled = not viewmodel.can_process

    viewmodel.param.watch(update_button_state, "can_process")

    # 处理按钮点击事件
    def on_process_click(event):
        # 收集参数
        params = collect_param_values(params_container)

        # 执行处理
        added_ids = viewmodel.process_data(params)

        # 如果成功添加了数据，导航回数据管理视图
        if added_ids:
            navigate_callback("data_manager")

    process_button.on_click(on_process_click)

    # --- 组装最终布局 ---
        return pn.Column(
        pn.pane.Markdown("## 数据处理与转换", sizing_mode="stretch_width"),
        selected_data_info,
            pn.layout.Divider(),
        pn.Column(
            pn.pane.Markdown("### 选择处理方法", sizing_mode="stretch_width"),
            service_selector,
            sizing_mode="stretch_width",
        ),
        params_container,
        pn.Row(process_button, sizing_mode="stretch_width"),
        status_alert,
        sizing_mode="stretch_both",
    )


# --- 辅助函数 ---
def create_param_widgets(params_spec: Dict[str, Dict[str, Any]]):
    """根据参数规范创建对应的输入组件"""
    widgets = []

    for param_name, param_spec in params_spec.items():
        param_type = param_spec.get("type", "string")
        label = param_spec.get("label", param_name)
        default = param_spec.get("default")

        if param_type == "string":
            options = param_spec.get("options")
            if options:
                widget = pn.widgets.Select(
                    name=label,
                    options=options,
                    value=default if default in options else options[0],
                )
            else:
                widget = pn.widgets.TextInput(
                    name=label, value=default or "", placeholder=f"输入{label}..."
                )
        elif param_type == "integer":
            min_val = param_spec.get("min")
            max_val = param_spec.get("max")
            step = param_spec.get("step", 1)
            widget = pn.widgets.IntSlider(
                name=label,
                start=min_val if min_val is not None else -100,
                end=max_val if max_val is not None else 100,
                step=step,
                value=default or 0,
            )
        elif param_type == "float":
            min_val = param_spec.get("min")
            max_val = param_spec.get("max")
            step = param_spec.get("step", 0.1)
            widget = pn.widgets.FloatSlider(
                name=label,
                start=min_val if min_val is not None else -100.0,
                end=max_val if max_val is not None else 100.0,
                step=step,
                value=default or 0.0,
            )
        elif param_type == "boolean":
            widget = pn.widgets.Checkbox(
                name=label, value=default if default is not None else False
            )
        elif param_type == "multiselect":
            options = param_spec.get("options", [])
            widget = pn.widgets.MultiSelect(
                name=label, options=options, value=default or []
            )
        else:
            # 默认为文本输入
            widget = pn.widgets.TextInput(
                name=label,
                value=str(default) if default is not None else "",
                placeholder=f"输入{label}...",
            )

        widget.param_name = param_name  # 添加自定义属性记录参数名
        widgets.append(widget)

    return widgets


def collect_param_values(container):
    """从参数容器中收集参数值"""
    params = {}

    for widget in container:
        if hasattr(widget, "param_name"):
            params[widget.param_name] = widget.value

    return params
