import panel as pn
import param
from typing import Dict, Any, List

from core.node import NodeRegistry
# Import ViewModel
from viewmodels import WorkflowViewModel

class NodePalette(param.Parameterized):
    """
    显示可用节点的面板，并允许用户选择要添加的节点类型。
    现在直接调用 ViewModel 的 add_node 方法。
    """
    # --- Input Parameters ---
    view_model = param.ClassSelector(class_=WorkflowViewModel, doc="关联的 WorkflowViewModel")

    # --- Output Parameters / Events ---
    # REMOVED: selected_node_type is no longer used for signaling
    # selected_node_type = param.String(default=None, doc="当用户点击按钮时，设置此参数为节点类型")

    # --- Internal State ---
    _node_buttons: Dict[str, pn.widgets.Button] = {}
    _layout = param.Parameter() # Use param.Parameter for layout

    def __init__(self, **params):
        # Explicitly check for view_model
        if 'view_model' not in params or params['view_model'] is None:
            raise ValueError("NodePalette requires a valid WorkflowViewModel instance.")
        super().__init__(**params)
        # Initialize layout after super().__init__
        self._layout = pn.Column(pn.pane.Markdown("**可用节点**"), sizing_mode='stretch_width', min_height=300)
        self._update_palette()

    def _update_palette(self):
        """从 NodeRegistry 加载节点并创建按钮。"""
        # Check if layout has been initialized
        if self._layout is None:
             self._layout = pn.Column(pn.pane.Markdown("**可用节点**"), sizing_mode='stretch_width', min_height=300)

        self._node_buttons.clear()
        available_nodes = NodeRegistry.list_available_nodes()
        buttons = []
        # 按节点类型排序，使列表稳定
        for node_type in sorted(available_nodes.keys()):
            node_meta = available_nodes[node_type]
            button = pn.widgets.Button(
                name=node_type,
                button_type='primary',
                height=40,
                margin=(5, 10),
            )
            # 使用 lambda 捕获当前的 node_type
            button.on_click(lambda event, nt=node_type: self._on_node_select(nt))
            self._node_buttons[node_type] = button
            buttons.append(button)

        # 更新 Column 内容，保留标题
        # Ensure layout object exists before accessing its objects attribute
        if self._layout.objects:
            self._layout.objects = [self._layout.objects[0]] + buttons
        else:
             self._layout.objects = [pn.pane.Markdown("**可用节点**")] + buttons

    def _on_node_select(self, node_type: str):
        """当节点按钮被点击时调用，直接调用 ViewModel。"""
        if self.view_model:
            try:
                # Directly call the ViewModel command
                self.view_model.add_node(node_type)
            except Exception as e:
                logger.error(f"NodePalette: Error calling view_model.add_node for {node_type}: {e}", exc_info=True)
                # Optionally show notification via pn.state if available
                if pn.state.notifications:
                    pn.state.notifications.error(f"添加节点 '{node_type}' 失败: {e}", duration=3000)
        else:
             logger.error("NodePalette: Cannot add node, ViewModel is not available.")


    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 表示。"""
        return self._layout

    def refresh(self):
        """重新加载节点列表。"""
        self._update_palette()

# # 示例用法 (需要先发现节点)
# if __name__ == '__main__':
#     import logging
#     logging.basicConfig(level=logging.INFO)
#     # 假设 NodeRegistry 已经发现了一些节点
#     # from core.node import NodeRegistry
#     # NodeRegistry.discover_nodes() # 需要在项目根目录运行

#     # 模拟几个节点被注册
#     NodeRegistry._node_metadata = {
#         'LoadCSV': {'type': 'LoadCSV', 'description': 'Loads data from CSV'}, 
#         'FilterRows': {'type': 'FilterRows', 'description': 'Filters rows based on condition'}
#     }

#     palette = NodePalette()
    
#     # 监视选择变化
#     def print_selection(event):
#         print(f"Event: {event.name} changed to {event.new}")
#         # 模拟处理后重置
#         palette.selected_node_type = None 

#     palette.param.watch(print_selection, 'selected_node_type')

#     pn.serve(palette.panel()) 