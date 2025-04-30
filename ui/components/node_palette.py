import panel as pn
import param
from typing import Dict, Any, List
import logging # 添加 logging

from core.node import NodeRegistry
from .base_panel import BasePanelComponent # 导入基类
# 需要导入 ViewModel 类型提示
from viewmodels import WorkflowViewModel

logger = logging.getLogger(__name__)

class NodePalette(BasePanelComponent):
    """
    显示可用节点的面板，并允许用户选择要添加的节点类型。
    现在直接调用 ViewModel 的 add_node 方法。
    """
    # --- 输入参数 --- (从基类继承 view_model)
    # 移除 node_registry 参数定义
    # node_registry: NodeRegistry = param.ClassSelector(class_=NodeRegistry, is_instance=False, doc="节点注册表类")

    # --- 输出参数 / 事件 ---
    # 已移除: selected_node_type 不再用于信号传递
    # selected_node_type = param.String(default=None, doc="当用户点击按钮时，设置此参数为节点类型")

    # --- 内部状态 ---
    _node_buttons: Dict[str, pn.widgets.Button] = {}
    _layout = param.Parameter() # 使用 param.Parameter 处理布局
    # 添加普通实例属性来存储 NodeRegistry 类
    node_registry: type = None

    def __init__(self, view_model: WorkflowViewModel, node_registry: type, **params):
        # 将 node_registry 存储为普通属性
        self.node_registry = node_registry
        # 将 view_model 放入 params 供基类使用
        params['view_model'] = view_model
        # 不再将 node_registry 传递给 super().__init__
        # if 'node_registry' in params: del params['node_registry']
        super().__init__(**params) # 调用基类 __init__

        # 在 super().__init__() 后初始化布局
        # self._layout = pn.Column(pn.pane.Markdown("**可用节点**"), sizing_mode='stretch_width', min_height=300)
        # 使用 param.Parameter() 的正确方式是设置它的值
        # 可以在 __init__ 或之后设置
        self.param.update(_layout=pn.Column(pn.pane.Markdown("**可用节点**"), sizing_mode='stretch_width', min_height=300))
        self._update_palette()

    def _update_palette(self):
        """从 NodeRegistry 加载节点并创建按钮。"""
        # 检查布局是否已初始化
        if self._layout is None:
             self._layout = pn.Column(pn.pane.Markdown("**可用节点**"), sizing_mode='stretch_width', min_height=300)

        self._node_buttons.clear()
        # 从实例变量访问 node_registry (现在是普通属性)
        available_nodes = self.node_registry.list_available_nodes()
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
        # 在访问布局对象的 objects 属性前确保其存在
        if self._layout.objects:
            self._layout.objects = [self._layout.objects[0]] + buttons
        else:
             self._layout.objects = [pn.pane.Markdown("**可用节点**")] + buttons

    def _on_node_select(self, node_type: str):
        """当节点按钮被点击时调用，直接调用 ViewModel。"""
        if self.view_model:
            try:
                # 直接调用 ViewModel 命令
                self.view_model.add_node(node_type)
            except Exception as e:
                logger.error(f"NodePalette: 调用 view_model.add_node 处理 {node_type} 时出错: {e}", exc_info=True)
                if pn.state.notifications:
                    pn.state.notifications.error(f"添加节点 '{node_type}' 失败: {e}", duration=3000)
        else:
            logger.warning("NodePalette: 无法添加节点，ViewModel 不可用。")

    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 表示。"""
        return self._layout

    def refresh(self):
        """重新加载节点列表。"""
        logger.info("NodePalette: 刷新节点列表...") # 添加日志
        self._update_palette()
        logger.info("NodePalette: 节点列表已刷新。") # 添加日志

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