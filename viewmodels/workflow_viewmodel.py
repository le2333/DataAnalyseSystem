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
    # --- 模型 ---
    # 持有核心的 Workflow 模型实例
    model = param.ClassSelector(class_=Workflow, precedence=-1)

    # --- 状态 (暴露给 View) ---
    # 当前选中的节点ID
    selected_node_id = param.String(default=None, doc="当前选中的节点ID")
    # 可用的节点ID列表 (用于下拉菜单等)
    available_node_ids = param.List(default=[], doc="当前工作流中所有节点的ID列表")
    # 连接列表数据 (用于显示现有连接)
    # 格式: List[Tuple[str, str, str, str]] -> (u, v, source_port, target_port)
    connection_list_data = param.List(default=[], doc="当前工作流中的连接列表")
    # 用于向 View 发送状态/通知消息 (可选)
    status_message = param.String(default="", doc="状态或通知消息")

    def __init__(self, workflow: Optional[Workflow] = None, **params):
        if workflow is None:
            # ViewModel 创建时必须有关联的 Model
            workflow = Workflow(name="New Workflow")
            logger.warning("WorkflowViewModel 在没有工作流的情况下初始化，已创建一个默认工作流。")
        params['model'] = workflow
        super().__init__(**params)
        logger.critical(f"WorkflowViewModel __init__: Initialized with model id: {id(self.model) if self.model else 'None'}")
        # 初始化时根据 model 更新状态
        self._update_state_from_model()
        # 监听 Model 对象本身的变化 (例如加载新工作流)
        self.param.watch(self._handle_model_change, 'model')

    def _handle_model_change(self, event=None):
        """当整个 Workflow 模型被替换时，更新所有依赖状态。"""
        logger.info(f"WorkflowViewModel: 模型实例更改为 {self.model.name}")
        self._update_state_from_model()
        # 清空选择
        self.selected_node_id = None

    def _update_state_from_model(self):
        """根据当前 model 的状态更新 ViewModel 的暴露状态。"""
        logger.debug("WorkflowViewModel: 正在从模型更新状态...")
        new_node_ids = []
        new_connections = []
        if self.model:
            # 更新可用节点 ID 列表
            new_node_ids = list(self.model._nodes.keys())
            # 更新连接列表数据
            edges = []
            if self.model.graph:
                for u, v, data in self.model.graph.edges(data=True):
                    edges.append((u, v, data.get('source_port', '?'), data.get('target_port', '?')))
            new_connections = edges
        
        # 显式触发列表更新 (如果直接赋值 param.List 可能不会触发)
        self.available_node_ids = new_node_ids
        self.connection_list_data = new_connections
        
        logger.debug(f"WorkflowViewModel: 状态已更新。节点列表触发更新: {self.available_node_ids}, 连接列表触发更新: {len(self.connection_list_data)}")

    # --- 命令 (由 View 触发) ---

    # 选择节点命令 (由 View 调用)
    def select_node(self, node_id: Optional[str]):
        """选择一个节点。"""
        logger.debug(f"WorkflowViewModel: 调用了 select_node 命令，ID 为: {node_id}")
        # 直接设置状态参数，watcher 会处理后续更新
        self.selected_node_id = node_id

    # 添加节点命令 (由 View 调用)
    def add_node(self, node_type: str):
        """添加一个新节点到工作流。"""
        if not node_type or not self.model:
            return
        logger.critical(f"WorkflowViewModel add_node: Modifying model with id: {id(self.model) if self.model else 'None'}")
        logger.info(f"WorkflowViewModel: 调用了 add_node 命令，类型为: {node_type}")
        try:
            node_id = f"{node_type.lower()}_{uuid.uuid4().hex[:6]}"
            # 获取下一个位置 (这个逻辑可以留在 ViewModel 或移到 Model)
            pos = self._get_next_node_position()
            # 调用 Model 修改状态
            self.model.add_node(node_id=node_id, node_type=node_type, position=pos)
            logger.info(f"WorkflowViewModel: 节点 '{node_id}' ({node_type}) 已添加到模型。")
            # 更新 ViewModel 的状态
            self._update_state_from_model()
            # 自动选择新节点
            self.select_node(node_id) # 这现在只会更新 selected_node_id, NodeConfigPanel 会负责响应
            self.status_message = f"已添加节点: {node_type}"
            if pn.state.notifications: pn.state.notifications.success(self.status_message, duration=2000)
        except Exception as e:
            logger.error(f"WorkflowViewModel: 添加节点 {node_type} 时出错: {e}", exc_info=True)
            self.status_message = f"添加节点失败: {e}"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)

    # 删除选中节点命令 (由 View 调用)
    def delete_node(self, node_id: str):
        """删除指定 ID 的节点。"""
        if not node_id or not self.model:
             logger.warning(f"WorkflowViewModel: delete_node 命令被忽略，node_id ({node_id}) 或模型无效。")
             return
        logger.info(f"WorkflowViewModel: 调用了 delete_node 命令，ID 为: {node_id}")
        try:
            # 调用 Model 修改状态
            self.model.remove_node(node_id)
            logger.info(f"WorkflowViewModel: 节点 '{node_id}' 已从模型中移除。")
            # 更新 ViewModel 的状态
            self._update_state_from_model()
            # 清空选择
            if self.selected_node_id == node_id: # 只有当删除的是当前选中的节点时才清空
                 self.select_node(None)
            self.status_message = f"节点 '{node_id}' 已删除。"
            if pn.state.notifications: pn.state.notifications.success(self.status_message, duration=2000)
        except KeyError:
            logger.error(f"WorkflowViewModel: 删除节点 '{node_id}' 失败：未找到。")
            self.status_message = f"删除失败：找不到节点 '{node_id}'。"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
            # 模型中节点已不存在，但仍需更新 ViewModel 状态以反映现实
            self._update_state_from_model()
        except Exception as e:
            logger.error(f"WorkflowViewModel: 删除节点 '{node_id}' 时出错: {e}", exc_info=True)
            self.status_message = f"删除节点时发生内部错误: {e}"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
            self._update_state_from_model() # 确保状态一致

    # 添加边命令 (由 View 调用)
    def add_edge(self, source_id: str, source_port: str, target_id: str, target_port: str):
        """向工作流添加一条边。"""
        if not all([source_id, source_port, target_id, target_port]) or not self.model:
            logger.warning(f"WorkflowViewModel: add_edge 命令被忽略，输入无效或模型不存在。")
             return
        logger.info(f"WorkflowViewModel: 调用了 add_edge 命令: {source_id}.{source_port} -> {target_id}.{target_port}")
        try:
            # 调用 Model 修改状态
            self.model.add_edge(source_id, source_port, target_id, target_port)
            logger.info("WorkflowViewModel: 边已添加到模型。")
            # 更新 ViewModel 的状态
            self._update_state_from_model() # 会更新 connection_list_data
            self.status_message = f"连接 {source_id} -> {target_id} 已添加。"
            if pn.state.notifications: pn.state.notifications.success(self.status_message, duration=2000)
        except ValueError as e: # Model 中定义的特定错误
            logger.error(f"WorkflowViewModel: 添加边失败: {e}")
            self.status_message = f"添加连接失败: {e}"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
        except Exception as e: # 其他意外错误
            logger.error(f"WorkflowViewModel: 添加边时出错: {e}", exc_info=True)
            self.status_message = "添加连接时发生内部错误。"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)

    # 删除边命令 (由 View 调用)
    def delete_edge(self, source_id: str, target_id: str, source_port: str, target_port: str):
        """从工作流移除一条边。"""
        if not all([source_id, target_id, source_port, target_port]) or not self.model:
             logger.warning(f"WorkflowViewModel: delete_edge 命令被忽略，输入无效或模型不存在。")
             return
        logger.info(f"WorkflowViewModel: 调用了 delete_edge 命令: {source_id}.{source_port} -> {target_id}.{target_port}")
        try:
            # 调用 Model 修改状态
            self.model.remove_edge(source_id, source_port, target_id, target_port)
            logger.info("WorkflowViewModel: 边已从模型中移除。")
            # 更新 ViewModel 的状态
            self._update_state_from_model()
            self.status_message = f"连接 {source_id} -> {target_id} 已删除。"
            if pn.state.notifications: pn.state.notifications.info(self.status_message, duration=2000)
        except Exception as e:
            logger.error(f"WorkflowViewModel: 移除边 {source_id} -> {target_id} 时出错: {e}", exc_info=True)
            self.status_message = f"移除连接失败: {e}"
            if pn.state.notifications: pn.state.notifications.error(self.status_message, duration=4000)
            # 即使出错也更新状态以确保一致性
            self._update_state_from_model()

    # 获取节点信息 (辅助方法)
    def get_node_info(self, node_id: str) -> Optional[Dict[str, Any]]:
         """获取指定节点的摘要信息 (类型、端口等)。"""
         if node_id and self.model and node_id in self.model._nodes:
             node = self.model.get_node(node_id)
             return {
                 'id': node.name, 
                 'type': node.node_type,
                 'inputs': node.define_inputs(), # 假设返回端口定义列表或字典
                 'outputs': node.define_outputs(),
                 # 可以添加更多信息，如参数摘要
             }
         return None

    # --- 辅助方法 ---
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
                     logger.warning(f"WorkflowViewModel: 计算下一个节点位置时出错: {e}")
        # 如果没有现有位置或计算出错，返回默认或随机位置
        return (max_x + offset_x, max_y) 