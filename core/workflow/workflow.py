import json
import logging
from typing import Dict, Any, List, Tuple, Optional

import networkx as nx
import polars as pl # 导入 polars 以备将来可能的类型提示或验证

from core.node import NodeRegistry, BaseNode

logger = logging.getLogger(__name__)

class Workflow:
    """管理工作流的图结构，包含节点和边。"""

    def __init__(self, name: str = "Untitled Workflow"):
        self.name = name
        self._graph = nx.DiGraph() # 使用 NetworkX 有向图存储工作流
        self._nodes: Dict[str, BaseNode] = {} # 存储节点实例，键是 node_id

    @property
    def graph(self) -> nx.DiGraph:
        """返回内部的 NetworkX 图对象。"""
        return self._graph

    @property
    def nodes(self) -> Dict[str, BaseNode]:
        """返回包含节点实例的字典 (只读访问)。"""
        # 返回副本或视图更安全，但这里简单返回引用
        return self._nodes

    def add_node(self, node_id: str, node_type: str, params: Optional[Dict[str, Any]] = None, position: Optional[Tuple[float, float]] = (0,0)) -> BaseNode:
        """
        向工作流中添加一个节点。

        Args:
            node_id: 节点的唯一标识符。
            node_type: 节点的类型 (必须已在 NodeRegistry 注册)。
            params: 节点的配置参数。
            position: 节点在 UI 上的位置 (可选, 用于序列化)。

        Returns:
            创建的节点实例。

        Raises:
            ValueError: 如果 node_id 已存在。
            KeyError: 如果 node_type 未注册。
        """
        if node_id in self._nodes:
            raise ValueError(f"节点 ID '{node_id}' 已存在于工作流中。")

        # 从注册表中创建节点实例
        try:
            node_instance = NodeRegistry.create_node_instance(node_type, node_id, params or {})
        except KeyError as e:
            logger.error(f"尝试添加未注册的节点类型: {node_type}")
            raise e

        self._nodes[node_id] = node_instance
        # 在 NetworkX 图中添加节点，可以附带属性
        self._graph.add_node(node_id, type=node_type, pos=position, label=f"{node_type}\n({node_id})") # 添加 type 和 position 属性
        logger.info(f"节点 '{node_id}' (类型: {node_type}) 已添加到工作流 '{self.name}'")
        return node_instance

    def remove_node(self, node_id: str):
        """
        从工作流中移除一个节点及其相关的边。

        Args:
            node_id: 要移除的节点的 ID。

        Raises:
            KeyError: 如果节点 ID 不存在。
        """
        if node_id not in self._nodes:
            raise KeyError(f"节点 ID '{node_id}' 在工作流中不存在。")

        del self._nodes[node_id]
        self._graph.remove_node(node_id) # NetworkX 会自动移除相关边
        logger.info(f"节点 '{node_id}' 已从工作流 '{self.name}' 移除。")

    def add_edge(self, source_node_id: str, source_port: str, target_node_id: str, target_port: str):
        """
        在两个节点之间添加一条边（连接）。

        Args:
            source_node_id: 源节点的 ID。
            source_port: 源节点的输出端口名称。
            target_node_id: 目标节点的 ID。
            target_port: 目标节点的输入端口名称。

        Raises:
            KeyError: 如果任一节点 ID 不存在。
            ValueError: 如果端口名称无效或连接已存在。
        """
        if source_node_id not in self._nodes:
            raise KeyError(f"源节点 ID '{source_node_id}' 在工作流中不存在。")
        if target_node_id not in self._nodes:
            raise KeyError(f"目标节点 ID '{target_node_id}' 在工作流中不存在。")

        source_node = self.get_node(source_node_id)
        target_node = self.get_node(target_node_id)

        # 验证端口是否存在
        if source_port not in source_node.define_outputs():
             raise ValueError(f"源节点 '{source_node_id}' (类型: {source_node.node_type}) 没有名为 '{source_port}' 的输出端口。")
        if target_port not in target_node.define_inputs():
             raise ValueError(f"目标节点 '{target_node_id}' (类型: {target_node.node_type}) 没有名为 '{target_port}' 的输入端口。")

        # 检查目标端口是否已被连接 (假设一个输入端口只能有一个连接)
        for u, v, data in self._graph.in_edges(target_node_id, data=True):
             if data.get('target_port') == target_port:
                 raise ValueError(f"目标节点 '{target_node_id}' 的输入端口 '{target_port}' 已被节点 '{u}' 的端口 '{data.get('source_port')}' 连接。")

        # 在 NetworkX 图中添加边，并存储端口信息
        self._graph.add_edge(source_node_id, target_node_id, source_port=source_port, target_port=target_port)
        logger.info(f"已添加连接：从 '{source_node_id}.{source_port}' 到 '{target_node_id}.{target_port}'")

    def remove_edge(self, source_node_id: str, target_node_id: str, target_port: str):
        """
        移除两个节点之间指定目标端口的连接。
        注意：NetworkX 的 remove_edge 需要源和目标 ID。我们通过 target_port 确保移除正确的边（以防多重边）。

        Args:
            source_node_id: 源节点的 ID。
            target_node_id: 目标节点的 ID。
            target_port: 目标节点的输入端口名称，用于标识要删除的特定连接。

        Raises:
            KeyError: 如果边不存在或不匹配。
        """
        edge_data = self._graph.get_edge_data(source_node_id, target_node_id)
        # NetworkX 图可能有多条边，但我们这里不允许。如果允许多重边，需要传入 key。
        if edge_data and edge_data.get('target_port') == target_port:
            self._graph.remove_edge(source_node_id, target_node_id)
            logger.info(f"已移除连接：从 '{source_node_id}' 到 '{target_node_id}' (目标端口: {target_port})")
        else:
            raise KeyError(f"在 '{source_node_id}' 和 '{target_node_id}' 之间找不到指向目标端口 '{target_port}' 的连接。")

    def get_node(self, node_id: str) -> BaseNode:
        """
        获取指定 ID 的节点实例。

        Args:
            node_id: 节点 ID。

        Returns:
            对应的 BaseNode 实例。

        Raises:
            KeyError: 如果节点 ID 不存在。
        """
        try:
            return self._nodes[node_id]
        except KeyError:
            raise KeyError(f"节点 ID '{node_id}' 在工作流中不存在。")

    def update_node_params(self, node_id: str, params: Dict[str, Any]):
        """
        更新指定节点的参数。

        Args:
            node_id: 要更新的节点 ID。
            params: 新的参数字典。

        Raises:
            KeyError: 如果节点 ID 不存在。
        """
        node = self.get_node(node_id)
        node.set_params(params)
        logger.info(f"节点 '{node_id}' 的参数已更新。")

    def get_node_params(self, node_id: str) -> Dict[str, Any]:
        """获取节点的当前参数。"""
        return self.get_node(node_id).params

    def get_node_position(self, node_id: str) -> Optional[Tuple[float, float]]:
        """获取节点的位置信息。"""
        if node_id in self._graph:
            return self._graph.nodes[node_id].get('pos')
        return None

    def update_node_position(self, node_id: str, position: Tuple[float, float]):
        """更新节点的位置信息。"""
        if node_id in self._graph:
            self._graph.nodes[node_id]['pos'] = position
        else:
             raise KeyError(f"节点 ID '{node_id}' 在工作流图结构中不存在。")

    def serialize(self) -> str:
        """
        将工作流结构序列化为 JSON 字符串。
        """
        workflow_data = {
            'name': self.name,
            'nodes': [],
            'edges': []
        }

        for node_id, node_instance in self._nodes.items():
            workflow_data['nodes'].append({
                'id': node_id,
                'type': node_instance.node_type,
                'params': node_instance.params,
                'position': self.get_node_position(node_id) # 从图中获取位置
            })

        for u, v, data in self._graph.edges(data=True):
            workflow_data['edges'].append({
                'source_id': u,
                'source_port': data.get('source_port'),
                'target_id': v,
                'target_port': data.get('target_port')
            })

        return json.dumps(workflow_data, indent=4)

    @classmethod
    def deserialize(cls, json_data: str) -> 'Workflow':
        """
        从 JSON 字符串反序列化创建 Workflow 实例。
        """
        data = json.loads(json_data)
        workflow = cls(name=data.get('name', "Untitled Workflow"))

        # 先添加所有节点
        for node_info in data.get('nodes', []):
            try:
                workflow.add_node(
                    node_id=node_info['id'],
                    node_type=node_info['type'],
                    params=node_info.get('params'),
                    position=tuple(node_info.get('position', [0, 0])) # JSON不支持元组，转回来
                )
            except Exception as e:
                logger.error(f"反序列化节点 '{node_info.get('id')}' 失败: {e}")
                # 可以选择跳过或抛出异常
                continue

        # 再添加所有边
        for edge_info in data.get('edges', []):
            try:
                workflow.add_edge(
                    source_node_id=edge_info['source_id'],
                    source_port=edge_info['source_port'],
                    target_node_id=edge_info['target_id'],
                    target_port=edge_info['target_port']
                )
            except Exception as e:
                logger.error(f"反序列化边 {edge_info} 失败: {e}")
                # 可以选择跳过或抛出异常
                continue

        return workflow

    def validate(self) -> bool:
        """
        验证工作流的有效性。
        目前只检查是否存在循环。
        未来可以添加更多检查，如输入输出类型匹配等。
        """
        try:
            cycles = list(nx.simple_cycles(self._graph))
            if cycles:
                logger.error(f"工作流 '{self.name}' 包含循环: {cycles}")
                return False
        except nx.NetworkXException as e:
             logger.error(f"检查工作流 '{self.name}' 循环时出错: {e}")
             return False # 如果图操作出错，也认为无效

        # TODO: 添加更多验证逻辑，例如：
        # 1. 检查所有节点的必需输入是否都已连接
        # 2. 检查连接的端口类型是否匹配 (需要更详细的类型信息)

        logger.info(f"工作流 '{self.name}' 验证通过 (无循环)。")
        return True

    def get_topological_order(self) -> List[str]:
        """
        返回节点的拓扑排序列表。
        """
        if not nx.is_directed_acyclic_graph(self._graph):
            raise ValueError("工作流包含循环，无法进行拓扑排序。")
        return list(nx.topological_sort(self._graph))

    def get_node_predecessors(self, node_id: str) -> List[Tuple[str, str, str]]:
        """
        获取一个节点的所有直接前驱节点及其连接信息。

        Args:
            node_id: 目标节点的 ID。

        Returns:
            一个列表，每个元素是一个元组 (predecessor_id, source_port, target_port)。
        """
        predecessors = []
        for u, v, data in self.graph.in_edges(node_id, data=True):
            predecessors.append((u, data['source_port'], data['target_port']))
        return predecessors

    def __repr__(self) -> str:
        return f"<Workflow name='{self.name}' nodes={len(self._nodes)} edges={self._graph.number_of_edges()}>"

    def clear(self):
        """清空工作流中的所有节点和边。"""
        self._graph.clear()
        self._nodes.clear()
        logger.info(f"工作流 '{self.name}' 已被清空。") 