import panel as pn
import param
from typing import Dict, Any, List

from core.node import NodeRegistry

class NodePalette(param.Parameterized):
    """
    显示可用节点的面板，并允许用户选择要添加的节点类型。
    """
    
    # 使用 param.Selector 或类似的参数来触发选择事件
    # 或者，我们直接生成按钮，按钮点击时通过回调通知父组件
    selected_node_type = param.String(default=None, doc="当用户点击按钮时，设置此参数为节点类型")

    def __init__(self, **params):
        super().__init__(**params)
        self._node_buttons: Dict[str, pn.widgets.Button] = {}
        self._layout = pn.Column(pn.pane.Markdown("**可用节点**"), sizing_mode='stretch_width', min_height=300)
        self._update_palette()

    def _update_palette(self):
        """从 NodeRegistry 加载节点并创建按钮。"""
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
                # 可以考虑添加 tooltip 显示描述
                # tooltips={'name': node_meta.get('description', '')} # Panel Button 不直接支持 tooltips
            )
            # 使用 lambda 捕获当前的 node_type
            button.on_click(lambda event, nt=node_type: self._on_node_select(nt))
            self._node_buttons[node_type] = button
            buttons.append(button)
        
        # 更新 Column 内容，保留标题
        self._layout.objects = [self._layout.objects[0]] + buttons 

    def _on_node_select(self, node_type: str):
        """当节点按钮被点击时调用。"""
        print(f"[NodePalette] Node selected: {node_type}") # DEBUG
        # 设置参数以通知监听者（例如主视图）
        self.selected_node_type = node_type 
        # 可能需要重置，以便下次点击仍然触发事件？取决于 Panel 的行为
        # 或者让父组件在处理后重置它 self.selected_node_type = None

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