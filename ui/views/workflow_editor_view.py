import panel as pn
import logging
from viewmodels.workflow_viewmodel import WorkflowViewModel
from ui.components import (
    NodePalette,
    WorkflowVisualizer,
    ConnectionManagementPanel,
    NodeManagementPanel,
    NodeConfigPanel
)
from core.node import NodeRegistry

logger = logging.getLogger(__name__)

class WorkflowEditorView(pn.viewable.Viewer):
    """
    工作流编辑界面的主视图。
    负责组装各个子组件 (面板) 并定义整体布局。
    """
    view_model: WorkflowViewModel
    node_registry: NodeRegistry

    # 子组件实例
    node_palette: NodePalette
    workflow_visualizer: WorkflowVisualizer
    connection_manager: ConnectionManagementPanel
    node_manager: NodeManagementPanel
    node_config_panel: NodeConfigPanel

    def __init__(self, view_model: WorkflowViewModel, node_registry: NodeRegistry, **params):
        super().__init__(**params)
        logger.critical(f"WorkflowEditorView __init__: Received view_model with id: {id(view_model)}, model id: {id(view_model.model) if view_model.model else 'None'}")
        self.view_model = view_model
        self.node_registry = node_registry

        # --- 初始化子组件 ---
        # 注意: 这里将 view_model 传递给所有需要它的组件
        self.node_palette = NodePalette(self.view_model, self.node_registry)
        self.workflow_visualizer = WorkflowVisualizer(self.view_model)
        self.connection_manager = ConnectionManagementPanel(self.view_model)
        self.node_manager = NodeManagementPanel(self.view_model)
        self.node_config_panel = NodeConfigPanel(self.view_model)

        # --- 绑定视图事件到 ViewModel 命令 (如果需要) ---
        # 例如，如果可视化器直接暴露节点选择事件
        # self.workflow_visualizer.param.watch(self._on_node_selected_from_graph, 'selected_node_id')
        # 目前节点选择逻辑在 ViewModel 内部通过 workflow_visualizer 回调处理, 或者通过 NodeManagementPanel 触发
        # NodeManagementPanel 内部已经绑定了删除按钮到 view_model.delete_node
        # ConnectionManagementPanel 内部已经绑定了添加/删除连接按钮到 view_model 的方法
        # NodePalette 内部已经绑定了添加按钮到 view_model.add_node

        # --- 监听 ViewModel 状态变化以更新非自治组件 (如果还有的话) ---
        # (目前所有主要面板都已自治或由 ViewModel 直接管理其内容 Panel 对象)
        # self.view_model.param.watch(self._update_some_part, 'some_view_model_param')

        logger.info("WorkflowEditorView initialized.")

    # def _on_node_selected_from_graph(self, event):
    #     """处理来自可视化器的节点选择事件。"""
    #     logger.debug(f"WorkflowEditorView: Node selection event from graph: {event.new}")
    #     self.view_model.select_node(event.new) # 调用 ViewModel 的命令

    def _build_layout(self):
        """构建编辑器的布局。"""
        logger.debug("Building WorkflowEditorView layout...")

        # 左侧面板: 节点库
        left_sidebar = self.node_palette.panel()
        left_sidebar.width = 250

        # 中间面板: 可视化 + 连接/节点管理
        # 上部：可视化器
        visualizer_panel = self.workflow_visualizer.panel()
        # 下部：标签页管理 连接 和 节点列表
        management_tabs = pn.Tabs(
            ("连接管理", self.connection_manager.panel()),
            ("节点管理", self.node_manager.panel()),
            tabs_location='above',
            height=300, # 固定下部高度
            sizing_mode='stretch_width'
        )

        middle_panel = pn.Column(
            visualizer_panel,
            management_tabs,
            sizing_mode='stretch_both' # 让 middle_panel 填满分配的空间
        )

        # 右侧面板: 节点配置
        # 直接使用新的 NodeConfigPanel 组件的 panel() 方法
        right_sidebar = self.node_config_panel.panel()
        right_sidebar.width = 350
        right_sidebar.sizing_mode = 'stretch_height' # 让其高度可伸展

        # 整体布局: 三栏式
        main_layout = pn.Row(
            left_sidebar,
            middle_panel,
            right_sidebar,
            sizing_mode='stretch_both' # 让主布局填满可用空间
        )
        logger.debug("WorkflowEditorView layout built.")
        return main_layout

    def __panel__(self):
        """返回 Panel 布局。这是 Viewer 类要求的。"""
        return self._build_layout()

    # 如果有需要手动触发更新的逻辑
    # def update_view(self):
    #     logger.debug("WorkflowEditorView: Manual view update triggered.")
    #     # 通常 Panel 的响应式系统会自动处理更新
    #     # 但如果需要，可以在这里强制更新某些非响应式部分
    #     # 例如，如果 _build_layout 依赖了非 param 参数的状态
    #     # self.param.trigger('view') # 假设有一个 view 参数可以触发刷新
    #     pass
