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
    _right_pane_container = param.Parameter(default=pn.Column(sizing_mode='stretch_width', styles={'padding': '10px'}))

    def __init__(self, workflow: Optional[Workflow] = None, **params):
        # Ensure ViewModel is created or used
        vm = params.get('view_model')
        if vm is None:
            vm = WorkflowViewModel(workflow=workflow)
            params['view_model'] = vm
        super().__init__(**params)

        # --- Initialize Child Components ---
        self.node_palette = NodePalette()
        self.visualizer = WorkflowVisualizer(workflow=self.view_model.model)
        self.node_management_panel = NodeManagementPanel(view_model=self.view_model)
        self.connection_management_panel = ConnectionManagementPanel(view_model=self.view_model)

        # === Bind View Actions to ViewModel Commands ===
        # Node Palette -> Add Node Command
        self.node_palette.param.watch(self._forward_add_node_request, 'selected_node_type')
        # Visualizer Tap -> Select Node Command 
        self.visualizer.param.watch(self._handle_visualizer_tap, 'tapped_node_id')
        # Management Panels -> Delete/Add/Remove Requests (Editor still handles these requests)
        self.node_management_panel.param.watch(self._handle_node_deletion_request, 'request_delete_node_id')
        self.connection_management_panel.param.watch(self._handle_add_edge_request, 'request_add_edge_data')
        self.connection_management_panel.param.watch(self._handle_remove_edge_request, 'request_remove_edge_data')

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

    # --- Action Requests from Child Panels --- 
    def _handle_node_deletion_request(self, event: param.parameterized.Event):
        node_id = event.new
        if node_id:
            logger.info(f"WorkflowEditorView: Handling node deletion request for: {node_id}")
            try:
                self.view_model.delete_node(node_id)
            except Exception as e:
                logger.error(f"WorkflowEditorView: Error deleting node via ViewModel: {e}", exc_info=True)
                if pn.state.notifications: pn.state.notifications.error(f"删除节点失败: {e}")
            # No need to clear request_delete_node_id here, let NodeManagementPanel do it

    def _handle_add_edge_request(self, event: param.parameterized.Event):
        edge_data = event.new
        if edge_data:
            logger.info(f"WorkflowEditorView: Handling add edge request: {edge_data}")
            try:
                self.view_model.add_edge(edge_data)
            except ValueError as ve:
                 logger.warning(f"WorkflowEditorView: Failed to add edge: {ve}")
                 if pn.state.notifications: pn.state.notifications.warning(f"添加连接失败: {ve}")
            except Exception as e:
                logger.error(f"WorkflowEditorView: Error adding edge via ViewModel: {e}", exc_info=True)
                if pn.state.notifications: pn.state.notifications.error(f"添加连接时发生错误: {e}")
            finally:
                # Clear the signal in ConnectionManagementPanel after handling
                if hasattr(self.connection_management_panel, 'request_add_edge_data'):
                     self.connection_management_panel.request_add_edge_data = None

    def _handle_remove_edge_request(self, event: param.parameterized.Event):
        edge_data = event.new
        if edge_data:
            logger.info(f"WorkflowEditorView: Handling remove edge request: {edge_data}")
            try:
                self.view_model.remove_edge(edge_data)
            except Exception as e:
                logger.error(f"WorkflowEditorView: Error removing edge via ViewModel: {e}", exc_info=True)
                if pn.state.notifications: pn.state.notifications.error(f"移除连接时发生错误: {e}")
            finally:
                # Clear the signal in ConnectionManagementPanel after handling
                 if hasattr(self.connection_management_panel, 'request_remove_edge_data'):
                      self.connection_management_panel.request_remove_edge_data = None

    # --- Forwarding User Actions to ViewModel --- 
    def _forward_add_node_request(self, event: param.parameterized.Event):
        node_type = event.new
        if node_type:
            logger.debug(f"WorkflowEditorView: Forwarding add node request: {node_type}")
            try:
                self.view_model.add_node(node_type)
            except Exception as e:
                 logger.error(f"WorkflowEditorView: Error adding node '{node_type}': {e}", exc_info=True)
                 if pn.state.notifications: pn.state.notifications.error(f"添加节点 '{node_type}' 失败: {e}")
            finally:
                 self.node_palette.selected_node_type = None

    def _handle_visualizer_tap(self, event: param.parameterized.Event):
        """Handles node tap from WorkflowVisualizer, forwards to ViewModel."""
        node_id = event.new
        logger.info(f"WorkflowEditorView: Node tapped on Visualizer: {node_id}. Forwarding to ViewModel.")
        # ONLY call ViewModel's select_node
        if self.view_model.selected_node_id != node_id:
            self.view_model.select_node(node_id)

    # ===========================================
    # == View Update Handlers (Driven by ViewModel) ==
    # ===========================================
    def _update_right_pane_display(self, event: param.parameterized.Event):
        logger.debug("WorkflowEditorView: Updating right pane display based on ViewModel change.")
        content = event.new
        if content:
            self._right_pane_container.objects = [content]
        else:
            self._right_pane_container.objects = [pn.pane.Markdown("_在图中或列表中选择一个节点以查看其配置。_")] 
        
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
            # Optionally clear ViewModel selection when model changes? ViewModel does this.
            # self.view_model.select_node(None)

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