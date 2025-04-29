import panel as pn
import param
import logging
import uuid
from typing import Optional, List, Dict, Any, Tuple
import networkx as nx

from core.workflow import Workflow
from core.node import NodeRegistry # ViewModel 需要访问 Registry 来获取配置面板

logger = logging.getLogger(__name__)

class WorkflowViewModel(param.Parameterized):
    """
    Workflow Editor 的 ViewModel。
    负责管理 Workflow 状态、处理业务逻辑 (用户操作命令)、
    并暴露需要在 View 中展示或绑定的状态。
    """
    # --- Model ---
    # 持有核心的 Workflow 模型实例
    model = param.ClassSelector(class_=Workflow, precedence=-1)

    # --- State (暴露给 View) ---
    # 当前选中的节点ID
    selected_node_id = param.String(default=None, doc="当前选中的节点ID")
    # 可用的节点ID列表 (用于下拉菜单等)
    available_node_ids = param.List(default=[], doc="当前工作流中所有节点的ID列表")
    # 连接列表数据 (用于显示现有连接)
    # 格式: List[Tuple[str, str, str, str]] -> (u, v, source_port, target_port)
    connection_list_data = param.List(default=[], doc="当前工作流中的连接列表")
    # 右侧配置面板的内容 (Panel 对象)
    right_pane_content = param.Parameter(default=pn.Column("选择一个节点以查看其配置", sizing_mode='stretch_width', styles={'padding': '10px'}), doc="右侧配置面板的内容")
    # 用于向 View 发送状态/通知消息 (可选)
    status_message = param.String(default="", doc="状态或通知消息")
    # 用于通知 View 刷新 Visualizer 的事件
    visualizer_needs_refresh = param.Event(doc="当需要刷新可视化时触发")

    def __init__(self, workflow: Optional[Workflow] = None, **params):
        if workflow is None:
            # ViewModel 创建时必须有关联的 Model
            workflow = Workflow(name="New Workflow")
            logger.warning("WorkflowViewModel initialized without a workflow, created a default one.")
        params['model'] = workflow
        super().__init__(**params)
        # 初始化时根据 model 更新状态
        self._update_state_from_model()
        # 监听 Model 对象本身的变化 (例如加载新工作流)
        self.param.watch(self._handle_model_change, 'model')

    def _handle_model_change(self, event=None):
        """当整个 Workflow 模型被替换时，更新所有依赖状态。"""
        logger.info(f"WorkflowViewModel: Model instance changed to {self.model.name}")
        self._update_state_from_model()
        # 清空选择
        self.selected_node_id = None
        # 触发可视化刷新
        self.visualizer_needs_refresh = True

    def _update_state_from_model(self):
        """根据当前 model 的状态更新 ViewModel 的暴露状态。"""
        logger.debug("WorkflowViewModel: Updating state from model...")
        if self.model:
            # 更新可用节点 ID 列表
            self.available_node_ids = list(self.model._nodes.keys())
            # 更新连接列表数据
            edges = []
            if self.model.graph:
                for u, v, data in self.model.graph.edges(data=True):
                    edges.append((u, v, data.get('source_port', '?'), data.get('target_port', '?')))
            self.connection_list_data = edges
        else:
            self.available_node_ids = []
            self.connection_list_data = []
        logger.debug(f"WorkflowViewModel: State updated. Nodes: {self.available_node_ids}, Edges: {len(self.connection_list_data)}")

    def _update_right_pane_content(self):
        """根据 selected_node_id 更新右侧面板内容。"""
        node_id = self.selected_node_id
        logger.info(f"WorkflowViewModel: Updating right pane for selected_node_id: {node_id}")
        new_pane_content = None
        if node_id and self.model:
            # --- 恢复调用 node.get_config_panel() --- 
            try:
                node = self.model.get_node(node_id)
                # 调用节点的 get_config_panel (现在是模板方法)
                if hasattr(node, 'get_config_panel'):
                    logger.info(f"WorkflowViewModel: Getting config panel for node '{node_id}'...")
                    # BaseNode.get_config_panel() 会确保返回新实例
                    config_panel = node.get_config_panel()
                    logger.info(f"WorkflowViewModel: Got config panel of type: {type(config_panel)}")
                    # 直接使用返回的面板 (它已经是 pn.Column 了)
                    new_pane_content = config_panel 
                else:
                    # 这个分支理论上不应该发生，因为 BaseNode 总是有 get_config_panel
                    logger.error(f"WorkflowViewModel: Node '{node_id}' missing get_config_panel method?! This should not happen.")
                    new_pane_content = pn.pane.Alert(f"节点 '{node_id}' 缺少配置面板方法！", alert_type='danger')
            except KeyError:
                logger.warning(f"WorkflowViewModel: Node '{node_id}' not found when updating right pane.")
                new_pane_content = pn.Column("错误：找不到选中的节点", sizing_mode='stretch_width')
            except Exception as e:
                 # 捕获在 get_config_panel 或 _build_config_panel_content 中可能发生的错误
                logger.error(f"WorkflowViewModel: Error getting/building config panel for node '{node_id}': {e}", exc_info=True)
                new_pane_content = pn.pane.Alert(f"加载节点 '{node_id}' 配置时出错: {e}", alert_type='danger')
        else:
            logger.info("WorkflowViewModel: No node selected, setting default message for right pane.")
            new_pane_content = pn.Column("选择一个节点以查看其配置", sizing_mode='stretch_width', styles={'padding': '10px'})

        # 更新参数以通知 View
        self.right_pane_content = new_pane_content

    # --- Commands (triggered by View) ---

    @param.depends('selected_node_id', watch=True)
    def _selected_node_id_changed(self):
        """监听 selected_node_id 变化，自动更新右侧面板内容。"""
        self._update_right_pane_content()

    # 选择节点命令 (由 View 调用)
    def select_node(self, node_id: Optional[str]):
        """选择一个节点。"""
        logger.debug(f"WorkflowViewModel: select_node command called with id: {node_id}")
        # 直接设置状态参数，watcher 会处理后续更新
        self.selected_node_id = node_id

    # 添加节点命令 (由 View 调用)
    def add_node(self, node_type: str):
        """添加一个新节点到工作流。"""
        if not node_type or not self.model:
            return
        logger.info(f"WorkflowViewModel: add_node command called for type: {node_type}")
        try:
            node_id = f"{node_type.lower()}_{uuid.uuid4().hex[:6]}"
            # 获取下一个位置 (这个逻辑可以留在 ViewModel 或移到 Model)
            pos = self._get_next_node_position()
            # 调用 Model 修改状态
            self.model.add_node(node_id=node_id, node_type=node_type, position=pos)
            logger.info(f"WorkflowViewModel: Node '{node_id}' ({node_type}) added to model.")
            # 更新 ViewModel 的状态
            self._update_state_from_model()
            # 自动选择新节点
            self.select_node(node_id) # 这会触发 right_pane 更新
            # 通知 View 刷新可视化
            self.visualizer_needs_refresh = True
            self.status_message = f"已添加节点: {node_type}"
            if pn.state.notifications: pn.state.notifications.success(self.status_message, duration=2000)
        except Exception as e:
            logger.error(f"WorkflowViewModel: Error adding node {node_type}: {e}", exc_info=True)
            self.status_message = f"添加节点失败: {e}"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)

    # 删除选中节点命令 (由 View 调用)
    def delete_node(self, node_id: str):
        """删除指定 ID 的节点。"""
        # node_id = self.selected_node_id # 不再依赖内部状态，由调用者提供
        if not node_id or not self.model:
             logger.warning(f"WorkflowViewModel: delete_node command ignored, node_id ({node_id}) or model is invalid.")
             return
        logger.info(f"WorkflowViewModel: delete_node command called for id: {node_id}")
        try:
            # 调用 Model 修改状态
            self.model.remove_node(node_id)
            logger.info(f"WorkflowViewModel: Node '{node_id}' removed from model.")
            # 更新 ViewModel 的状态
            self._update_state_from_model()
            # 清空选择
            if self.selected_node_id == node_id: # 只有当删除的是当前选中的节点时才清空
                 self.select_node(None)
            # 通知 View 刷新可视化
            self.visualizer_needs_refresh = True
            self.status_message = f"节点 '{node_id}' 已删除。"
            if pn.state.notifications: pn.state.notifications.success(self.status_message, duration=2000)
        except KeyError:
            logger.error(f"WorkflowViewModel: Failed to delete node '{node_id}': Not found.")
            self.status_message = f"删除失败：找不到节点 '{node_id}'。"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
            # Model 中节点已不存在，但仍需更新 ViewModel 状态以反映 reality
            self._update_state_from_model()
        except Exception as e:
            logger.error(f"WorkflowViewModel: Error deleting node '{node_id}': {e}", exc_info=True)
            self.status_message = f"删除节点时发生内部错误: {e}"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
            self._update_state_from_model() # 确保状态一致

    # 添加边命令 (由 View 调用)
    def add_edge(self, edge_data: Tuple[str, str, str, str]):
        """添加一条边到工作流。"""
        if not edge_data or len(edge_data) != 4 or not self.model:
             logger.warning(f"WorkflowViewModel: add_edge command ignored, invalid edge_data: {edge_data}")
             return
        source_node, source_port, target_node, target_port = edge_data
        logger.info(f"WorkflowViewModel: add_edge command called: {source_node}.{source_port} -> {target_node}.{target_port}")
        try:
            # 调用 Model 修改状态
            self.model.add_edge(source_node, source_port, target_node, target_port)
            logger.info("WorkflowViewModel: Edge added to model.")
            # 更新 ViewModel 的状态
            self._update_state_from_model() # 会更新 connection_list_data
            # 通知 View 刷新可视化
            self.visualizer_needs_refresh = True
            self.status_message = f"连接 {source_node} -> {target_node} 已添加"
            if pn.state.notifications: pn.state.notifications.success(self.status_message, duration=2000)
        except ValueError as e:
            logger.error(f"WorkflowViewModel: Failed to add edge: {e}")
            self.status_message = f"添加连接失败: {e}"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
        except Exception as e:
            logger.error(f"WorkflowViewModel: Error adding edge: {e}", exc_info=True)
            self.status_message = "添加连接时发生内部错误。"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)

    # 删除边命令 (由 View 调用)
    def remove_edge(self, edge_data: Tuple[str, str, str, str]):
        """从工作流移除一条边。"""
        if not edge_data or len(edge_data) != 4 or not self.model:
             logger.warning(f"WorkflowViewModel: remove_edge command ignored, invalid edge_data: {edge_data}")
             return
        u, v, source_port, target_port = edge_data
        logger.info(f"WorkflowViewModel: remove_edge command called: {u}.{source_port} -> {v}.{target_port}")
        try:
            # 调用 Model 修改状态
            self.model.remove_edge(u, source_port, v, target_port)
            logger.info("WorkflowViewModel: Edge removed from model.")
            # 更新 ViewModel 的状态
            self._update_state_from_model()
            # 通知 View 刷新可视化
            self.visualizer_needs_refresh = True
            self.status_message = f"连接 {u} -> {v} 已删除。"
            if pn.state.notifications: pn.state.notifications.info(self.status_message, duration=2000)
        except NotImplementedError:
            logger.error("WorkflowViewModel: Workflow.remove_edge(u, sport, v, tport) method not implemented!")
            self.status_message = "删除连接的功能尚未完全实现。"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
        except Exception as e:
            logger.error(f"WorkflowViewModel: Error removing edge {u} -> {v}: {e}", exc_info=True)
            self.status_message = f"移除连接失败: {e}"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
            # 即使出错也更新状态
            self._update_state_from_model()

    # --- Helper Methods ---
    def _get_next_node_position(self, offset_x=0.5, offset_y=0.5):
        """计算新节点的简单位置 (如果需要，可以移到 Model)。"""
        # 这个逻辑比较简单，暂时留在 ViewModel
        max_x, max_y = 0.0, 0.0
        if self.model and self.model.graph:
             positions = nx.get_node_attributes(self.model.graph, 'pos')
             if positions:
                 try:
                     valid_pos = [p for p in positions.values() if p is not None and len(p) == 2]
                     if valid_pos:
                         max_x = max(p[0] for p in valid_pos)
                         max_y = max(p[1] for p in valid_pos)
                         # 稍微错开一点，而不是严格在右下方
                         return (max_x + offset_x, max_y)
                 except (ValueError, TypeError) as e:
                     logger.warning(f"Error calculating max position: {e}. Using default.")
                     pass
        return (0.0, 0.0) # Default position if no nodes or error 