import panel as pn
import param
import logging
from typing import Dict, Any, Optional

from core.workflow import Workflow
from core.node import BaseNode

logger = logging.getLogger(__name__)

class NodeConfigPanel(param.Parameterized):
    """
    为选定的节点动态生成配置面板。
    """
    workflow = param.ClassSelector(class_=Workflow, precedence=-1) # 传入工作流对象
    selected_node_id = param.String(default=None, doc="当前选中的节点ID")

    # 内部状态
    _config_layout = param.Parameter(default=pn.Column("请先在画布中选择一个节点", sizing_mode='stretch_width'), precedence=-1)
    _current_widgets: Dict[str, pn.widgets.Widget] = {}

    def __init__(self, **params):
        super().__init__(**params)
        # self._config_layout = pn.Column("请先在画布中选择一个节点")

    @param.depends('selected_node_id', 'workflow', watch=True)
    def _update_panel(self):
        """当选中的节点 ID 或工作流变化时，重新生成配置面板。"""
        if not self.workflow or not self.selected_node_id:
            self._config_layout = pn.Column("请先在画布中选择一个节点", sizing_mode='stretch_width')
            self._current_widgets = {}
            self.param.trigger('_config_layout') # 手动触发更新
            return

        try:
            node = self.workflow.get_node(self.selected_node_id)
        except KeyError:
            logger.warning(f"选中的节点 ID '{self.selected_node_id}' 在工作流中未找到。")
            self._config_layout = pn.Column(f"错误：找不到节点 '{self.selected_node_id}'", sizing_mode='stretch_width')
            self._current_widgets = {}
            self.param.trigger('_config_layout')
            return

        logger.info(f"为节点 '{self.selected_node_id}' (类型: {node.node_type}) 生成配置面板。")
        schema = node.get_params_schema()
        current_params = node.params
        self._current_widgets = {}
        widgets_list = [
            pn.pane.Markdown(f"### 配置: {node.node_type} ({self.selected_node_id})"),
            pn.pane.HTML("<hr>")
        ]

        if not schema:
             widgets_list.append(pn.pane.Markdown("_此节点类型没有可配置参数。_"))
        else:
            for param_name, param_info in schema.items():
                widget = self._create_widget(param_name, param_info, current_params.get(param_name))
                if widget:
                    widgets_list.append(widget)
                    self._current_widgets[param_name] = widget
                    # 监听 widget 值的变化，以便更新 workflow 中的节点参数
                    # 使用 param.bind 或 widget.param.watch
                    widget.param.watch(self._on_widget_change, 'value')

        self._config_layout = pn.Column(*widgets_list, sizing_mode='stretch_width')
        self.param.trigger('_config_layout') # 触发 panel 更新

    def _create_widget(self, name: str, info: Dict[str, Any], current_value: Any) -> Optional[pn.widgets.Widget]:
        """根据参数模式信息创建 Panel 小部件。"""
        widget_type = info.get('type', 'string').lower()
        title = info.get('title', name)
        default = info.get('default')
        value = current_value if current_value is not None else default
        options = info.get('enum') # 用于下拉选择
        widget = None

        # 基础类型映射
        if options:
             # 如果提供了枚举值，使用下拉选择框
             widget = pn.widgets.Select(name=title, options=options, value=value)
        elif widget_type == 'string':
            # 可以根据 format 细化，例如 'path' 可能用 FileInput
            if info.get('format') == 'path':
                 # 注意：FileInput 在服务器环境中可能行为不同
                 widget = pn.widgets.TextInput(name=title, value=value or "", placeholder="输入路径...")
                 # widget = pn.widgets.FileInput(name=title) # FileInput 返回的是内容bytes，可能不合适
            elif info.get('format') == 'text-area':
                 widget = pn.widgets.TextAreaInput(name=title, value=value or "", placeholder="输入文本...")
            else:
                widget = pn.widgets.TextInput(name=title, value=value or "", placeholder=f"输入{title}...")
        elif widget_type == 'integer':
            step = info.get('step', 1)
            widget = pn.widgets.IntInput(name=title, value=int(value) if value is not None else None, step=step, start=info.get('minimum'), end=info.get('maximum'))
        elif widget_type == 'number':
             step = info.get('step', 0.1)
             widget = pn.widgets.FloatInput(name=title, value=float(value) if value is not None else None, step=step, start=info.get('minimum'), end=info.get('maximum'))
        elif widget_type == 'boolean':
            widget = pn.widgets.Checkbox(name=title, value=bool(value) if value is not None else False)
        # elif widget_type == 'array': # 数组/列表比较复杂，可能需要 TextInput + 解析，或 MultiSelect 等
        #     widget = pn.widgets.TextInput(name=title, value=",".join(map(str, value or [])), placeholder="输入列表项，逗号分隔...")
        else:
            logger.warning(f"节点 '{self.selected_node_id}' 的参数 '{name}' 类型 '{widget_type}' 无法直接映射到标准 Panel Widget。")
            # 可以用 TextInput 作为回退
            widget = pn.widgets.TextInput(name=title, value=str(value) if value is not None else "", placeholder=f"输入 {widget_type} 值...")

        # 添加描述信息 (如果 Panel widget 支持)
        # if widget and 'description' in info:
            # widget.description = info['description'] # 大部分 widget 没有 description 参数

        return widget

    def _on_widget_change(self, event: param.parameterized.Event):
        """当某个配置小部件的值发生变化时调用。"""
        if not self.workflow or not self.selected_node_id:
            return
        
        # 找到是哪个参数的小部件触发了事件
        changed_param = None
        for param_name, widget in self._current_widgets.items():
            if widget is event.obj:
                changed_param = param_name
                break
        
        if changed_param:
            new_value = event.new
            logger.debug(f"节点 '{self.selected_node_id}' 参数 '{changed_param}' 值改变为: {new_value} (类型: {type(new_value)})")
            try:
                current_params = self.workflow.get_node_params(self.selected_node_id)
                # 更新参数字典
                updated_params = current_params.copy()
                updated_params[changed_param] = new_value
                # 通过 workflow 更新节点参数 (会触发节点的 _validate_params)
                self.workflow.update_node_params(self.selected_node_id, updated_params)
                logger.info(f"节点 '{self.selected_node_id}' 参数 '{changed_param}' 已更新。")
            except KeyError:
                 logger.error(f"尝试更新参数时未找到节点 '{self.selected_node_id}'")
            except ValueError as e:
                 logger.error(f"更新节点 '{self.selected_node_id}' 参数 '{changed_param}' 失败: {e}")
                 # 可以考虑将小部件的值重置回旧值，或者显示错误信息
            except Exception as e:
                 logger.error(f"更新节点 '{self.selected_node_id}' 参数时发生未知错误: {e}", exc_info=True)
        else:
             logger.warning(f"收到未知小部件的值改变事件: {event}")

    @param.depends('_config_layout')
    def view(self) -> pn.viewable.Viewable:
        """返回动态生成的配置布局。"""
        return self._config_layout

    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 表示。"""
        # 返回 self.view 方法的输出，因为它依赖于 _config_layout
        return self.view

# # 示例用法
# if __name__ == '__main__':
#     import logging
#     logging.basicConfig(level=logging.INFO)
#     pn.extension()

#     # --- 模拟 Node 和 Workflow --- 
#     class MockNode(BaseNode):
#         def __init__(self, node_id, params):
#             super().__init__(node_id, params)

#         @classmethod
#         def get_params_schema(cls) -> Dict[str, Any]:
#             return {
#                 'file_path': {'type': 'string', 'format': 'path', 'title': '文件路径', 'default': 'data.csv'},
#                 'delimiter': {'type': 'string', 'title': '分隔符', 'default': ','},
#                 'max_rows': {'type': 'integer', 'title': '最大行数', 'default': 100, 'minimum': 0},
#                 'use_header': {'type': 'boolean', 'title': '使用表头', 'default': True},
#                 'mode': {'type': 'string', 'title': '模式', 'enum': ['read', 'write'], 'default': 'read'}
#             }
#         @classmethod
#         def define_inputs(cls) -> Dict[str, type]: return {}
#         @classmethod
#         def define_outputs(cls) -> Dict[str, type]: return {'output': pl.DataFrame}
#         def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]: return {}
    
#     # 模拟注册
#     NodeRegistry._registry['MockNode'] = MockNode

#     # 创建工作流并添加节点
#     wf = Workflow(name="Test Workflow")
#     node1 = wf.add_node('node_1', 'MockNode', params={'delimiter': ';'})

#     # --- 创建配置面板实例 --- 
#     config_panel = NodeConfigPanel(workflow=wf)

#     # --- 模拟选择节点 --- 
#     selector = pn.widgets.Select(name="Select Node", options=list(wf._nodes.keys()))
#     # 将选择器的值绑定到配置面板的 selected_node_id
#     selector.link(config_panel, value='selected_node_id')
    
#     # --- 布局 --- 
#     app_layout = pn.Column(
#         "## Workflow Config Test",
#         selector,
#         config_panel.panel # 注意这里是 .panel() 获取 viewable
#     )

#     app_layout.servable()

#     # 或者直接运行服务
#     # pn.serve(app_layout) 