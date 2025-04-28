import importlib
import inspect
import pkgutil
import logging
from pathlib import Path
from typing import Dict, Type, List, Any
import param # 导入 param

from .base_node import BaseNode

logger = logging.getLogger(__name__)

class NodeRegistry:
    """节点注册与发现类。"""
    _registry: Dict[str, Type[BaseNode]] = {}
    _node_metadata: Dict[str, Dict[str, Any]] = {} # 存储节点的元数据

    @classmethod
    def register_node(cls, node_cls: Type[BaseNode]):
        """
        注册一个节点类。
        通常用作装饰器 (@NodeRegistry.register_node)。
        现在从 cls.param 而不是 get_params_schema() 获取参数信息。
        """
        if not issubclass(node_cls, param.Parameterized):
             # 由于 BaseNode 继承了 param.Parameterized，这里理论上不需要检查
             # 但保留以防万一
             logger.warning(f"尝试注册的类 {node_cls.__name__} 未继承自 param.Parameterized，可能无法正确提取参数。")
             # raise TypeError(f"类 {node_cls.__name__} 必须是 param.Parameterized 的子类")
        
        if not issubclass(node_cls, BaseNode):
            raise TypeError(f"类 {node_cls.__name__} 必须是 BaseNode 的子类")
        if not inspect.isclass(node_cls) or inspect.isabstract(node_cls):
             return node_cls

        node_type = node_cls.__name__
        if node_type in cls._registry:
            logger.warning(f"节点类型 '{node_type}' 已被注册，将被覆盖。来自 {node_cls.__module__}")

        cls._registry[node_type] = node_cls
        
        # --- 提取并存储元数据 --- 
        try:
            # 不再调用 get_params_schema() 
            # schema = node_cls.get_params_schema()
            
            # 从 cls.param 提取参数信息
            params_info = {}
            # 迭代类上定义的 param.Parameter 对象
            for pname, pobj in node_cls.param.objects('existing').items():
                if pname == 'name': # 排除内置的 'name' 参数 (即 node_id)
                    continue
                # 提取信息 (简化版，可以根据需要添加更多属性)
                param_data = {
                     'type': type(pobj).__name__, # 参数类型 (如 String, Integer)
                     'label': pobj.label or pname, # 优先使用 label
                     'doc': pobj.doc,
                     'default': pobj.default,
                     # 可以尝试获取更多信息，如 bounds, allow_None, objects (for Selector)
                }
                # 处理 Selector 的选项
                if isinstance(pobj, param.Selector):
                     param_data['enum'] = pobj.objects
                # 处理 Number 的范围
                if isinstance(pobj, param.Number):
                    bounds = pobj.bounds or (None, None)
                    param_data['minimum'] = bounds[0]
                    param_data['maximum'] = bounds[1]
                    param_data['allow_None'] = pobj.allow_None # 对 Integer/Number
                # 其他类型特定的属性...
                params_info[pname] = param_data

            inputs = node_cls.define_inputs()
            outputs = node_cls.define_outputs()
            cls._node_metadata[node_type] = {
                'type': node_type,
                'description': inspect.getdoc(node_cls) or node_type,
                'module': node_cls.__module__,
                # 'params_schema': schema, # 使用新的 params_info
                'params_info': params_info, # 存储从 param 对象提取的信息
                'inputs': {k: v.__name__ for k, v in inputs.items()},
                'outputs': {k: v.__name__ for k, v in outputs.items()}
            }
            logger.info(f"成功注册节点类型: {node_type} 从 {node_cls.__module__}")
        except NotImplementedError:
             logger.error(f"节点类 {node_type} 未完全实现抽象方法 (如 define_inputs, define_outputs)，无法存储完整元数据。")
        except Exception as e:
            # 这里捕获更具体的异常可能更好
            logger.error(f"注册节点 {node_type} 时提取元数据失败: {e}", exc_info=True) # 添加 exc_info

        return node_cls

    @classmethod
    def discover_nodes(cls, nodes_package_dir: str = "nodes") -> int:
        """
        动态发现并加载指定包目录下的所有节点模块。

        Args:
            nodes_package_dir: 包含节点模块的包目录路径 (相对于项目根目录)。

        Returns:
            成功加载的模块数量。
        """
        count = 0
        package_path = Path(nodes_package_dir)
        if not package_path.is_dir() or not (package_path / '__init__.py').exists():
            logger.error(f"提供的节点路径 '{nodes_package_dir}' 不是一个有效的 Python 包目录。")
            return 0

        logger.info(f"开始从 '{package_path}' 发现节点...")
        # 使用 pkgutil 遍历包及其子包中的所有模块
        for module_info in pkgutil.walk_packages([str(package_path)], prefix=f"{package_path.name}."):
            if not module_info.ispkg: # 只导入非包模块
                try:
                    # 清空之前的注册信息？(可选，看是否需要热重载)
                    # cls._registry = {}
                    # cls._node_metadata = {}
                    importlib.import_module(module_info.name)
                    logger.debug(f"成功导入模块: {module_info.name}")
                    count += 1
                except ImportError as e:
                    logger.error(f"导入节点模块 '{module_info.name}' 失败: {e}")
                except Exception as e:
                    logger.error(f"加载模块 '{module_info.name}' 时发生未知错误: {e}")

        logger.info(f"节点发现完成。共尝试加载 {count} 个模块。已注册 {len(cls._registry)} 种节点类型。")
        return count

    @classmethod
    def get_node_class(cls, node_type: str) -> Type[BaseNode]:
        """
        根据节点类型字符串获取对应的节点类。

        Args:
            node_type: 节点类型名称 (通常是类名)。

        Returns:
            对应的 BaseNode 子类。

        Raises:
            KeyError: 如果找不到该类型的节点。
        """
        try:
            return cls._registry[node_type]
        except KeyError:
            raise KeyError(f"未注册的节点类型: '{node_type}'")

    @classmethod
    def list_available_nodes(cls) -> Dict[str, Dict[str, Any]]:
        """
        返回所有已注册节点的元数据字典，用于 UI 展示。

        Returns:
            一个字典，键是节点类型字符串，值是包含节点元数据 (如描述, 参数结构, 输入/输出) 的字典。
        """
        return cls._node_metadata.copy() # 返回副本以防外部修改

    @classmethod
    def list_node_types(cls) -> List[str]:
        """返回所有已注册节点的类型名称列表。"""
        return list(cls._registry.keys())

    @classmethod
    def create_node_instance(cls, node_type: str, node_id: str, params: Dict[str, Any]) -> BaseNode:
        """
        创建指定类型节点的一个实例。

        Args:
            node_type: 节点类型名称。
            node_id: 要分配给新节点的唯一 ID。
            params: 节点的初始化参数。

        Returns:
            创建的 BaseNode 实例。

        Raises:
            KeyError: 如果节点类型未注册。
        """
        NodeClass = cls.get_node_class(node_type)
        # params 字典现在直接用于初始化 param.Parameterized 的参数
        return NodeClass(node_id=node_id, params=params) 