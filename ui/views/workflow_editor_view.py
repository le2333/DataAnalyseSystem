import panel as pn
import param
import logging
from typing import Optional

# 核心模型
from core.workflow import Workflow
# UI 子组件
from ui.components.node_palette import NodePalette
from ui.components.workflow_visualizer import WorkflowVisualizer
from ui.components.node_management_panel import NodeManagementPanel
from ui.components.connection_management_panel import ConnectionManagementPanel
# ViewModel
from viewmodels import WorkflowViewModel

logger = logging.getLogger(__name__)

class WorkflowEditorView(param.Parameterized):
    """
    工作流编辑器的主视图 (View)。
    负责组装 UI 子面板，并将用户交互转发给 ViewModel 处理。
    通过监听 ViewModel 的状态变化来更新自身和子组件。
    """
    # --- ViewModel ---
    # 持有 ViewModel 实例
    view_model = param.ClassSelector(class_=WorkflowViewModel)

    # --- UI Components (Child Panels) ---
    node_palette: NodePalette = None
    visualizer: WorkflowVisualizer = None
    node_management_panel: NodeManagementPanel = None
    connection_management_panel: ConnectionManagementPanel = None

    # --- Layout Panes ---
    # Keep as Parameter holding the container
    _right_pane_container = param.Parameter(default=pn.Column("选择一个节点以查看其配置", sizing_mode='stretch_width', styles={'padding': '10px'}))

    def __init__(self, workflow: Optional[Workflow] = None, **params):
        # Ensure ViewModel is created or used
        vm = params.get('view_model')
        if vm is None:
            vm = WorkflowViewModel(workflow=workflow)
            params['view_model'] = vm
        super().__init__(**params)

        # --- Initialize Child Components ---
        self.node_palette = NodePalette(view_model=self.view_model)
        self.visualizer = WorkflowVisualizer(workflow=self.view_model.model, view_model=self.view_model)
        self.node_management_panel = NodeManagementPanel(view_model=self.view_model)
        self.connection_management_panel = ConnectionManagementPanel(view_model=self.view_model)

        # === Bind ViewModel State Changes to View Updates ===
        # Update Right Pane based on ViewModel content
        self.view_model.param.watch(self._update_right_pane_display, 'right_pane_content')
        # Refresh Visualizer when ViewModel signals
        self.view_model.param.watch(self._refresh_visualizer, 'visualizer_needs_refresh')
        # Update Visualizer's model when ViewModel's model changes
        self.view_model.param.watch(self._update_visualizer_model, 'model')
        
        logger.info(f"WorkflowEditorView initialized. ViewModel has workflow: {self.view_model.model.name if self.view_model.model else 'None'}")

    # ===============================================
    # == Request Handlers (Interacting with ViewModel) ==
    # ===============================================

    # ===========================================
    # == View Update Handlers (Driven by ViewModel) ==
    # ===========================================
    def _update_right_pane_display(self, event: param.parameterized.Event):
        logger.debug("WorkflowEditorView: Updating right pane display based on ViewModel change.")
        content = event.new
        # Use slice assignment to update the *contents* of the container Parameter
        container = self._right_pane_container # Get the actual Column object
        if content:
            container[:] = [content]
        else:
            container[:] = [pn.pane.Markdown("_在图中或列表中选择一个节点以查看其配置。_")]
        # Trigger the parameter holding the container to potentially force redraw
        self.param.trigger('_right_pane_container')

    def _refresh_visualizer(self, event: param.parameterized.Event):
        if event.new:
            logger.debug("WorkflowEditorView: Refreshing visualizer based on ViewModel signal.")
            self.visualizer.refresh()
            self.view_model.visualizer_needs_refresh = False # Reset the event trigger

    def _update_visualizer_model(self, event: param.parameterized.Event):
        new_model = event.new
        logger.debug(f"WorkflowEditorView: ViewModel model changed to: {new_model.name if new_model else 'None'}. Updating visualizer.")
        if self.visualizer.workflow is not new_model:
            self.visualizer.workflow = new_model

    # ===============================================
    # == Layout Definition ==
    # ===============================================

    def panel(self) -> pn.viewable.Viewable:
        """返回编辑器的主 Panel 布局。"""
        logger.debug("WorkflowEditorView: Building main panel layout.")
        left_pane = pn.Column(self.node_palette.panel(), width=250, styles={'background':'#fafafa'})
        center_top_pane = pn.Column(self.visualizer.panel(), min_height=300, sizing_mode='stretch_both')
        management_panel = pn.Column(
            self.node_management_panel.panel(),
            pn.layout.Divider(),
            self.connection_management_panel.panel(),
            sizing_mode='stretch_width',
            styles={'padding': '10px'}
        )
        center_pane = pn.Column(center_top_pane, management_panel, sizing_mode='stretch_width')
        # Use the container Parameter directly in the layout
        right_pane = pn.Column(self._right_pane_container, width=300, sizing_mode='stretch_height') 
        main_layout = pn.Row(
            left_pane,
            center_pane,
            right_pane,
            sizing_mode='stretch_both'
        )
        return main_layout

# 注意：旧的 _handle_... 方法和直接修改 workflow 的方法已被移除或重构。
# WorkflowEditorView 现在主要作为 View 层，负责 UI 组装和事件转发。 