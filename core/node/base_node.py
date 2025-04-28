import abc
import polars as pl
from typing import Dict, List, Any, Type

class BaseNode(abc.ABC):
    """
    节点的基础抽象类。
    所有具体节点都应继承此类并实现抽象方法。
    """
    def __init__(self, node_id: str, params: Dict[str, Any]):
        """
        初始化节点。

        Args:
            node_id: 节点的唯一标识符。
            params: 节点的配置参数。
        """
        self._node_id = node_id
        self.params = params if params is not None else {}
        self._validate_params() # 初始化时校验参数

    @property
    def node_id(self) -> str:
        """返回节点的唯一ID。"""
        return self._node_id

    @property
    def node_type(self) -> str:
        """返回节点的类型（通常是类名）。"""
        return self.__class__.__name__

    @classmethod
    @abc.abstractmethod
    def get_params_schema(cls) -> Dict[str, Any]:
        """
        返回描述该节点可配置参数的 JSON Schema 或类似结构的字典。
        用于 UI 自动生成配置表单。
        例如:
        {
            'param_name': {'type': 'integer', 'default': 10, 'title': '参数说明'},
            'file_path': {'type': 'string', 'format': 'path', 'title': '文件路径'}
        }
        """
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def define_inputs(cls) -> Dict[str, Type]:
        """
        定义节点期望的输入端口名称及其期望的数据类型（目前主要用 pl.DataFrame）。
        返回一个字典，键是端口名，值是期望的类型。
        例如: {'input_data': pl.DataFrame, 'reference_data': pl.DataFrame}
        如果节点没有输入，返回空字典 {}。
        """
        raise NotImplementedError

    @classmethod
    @abc.abstractmethod
    def define_outputs(cls) -> Dict[str, Type]:
        """
        定义节点产生的输出端口名称及其产生的数据类型（目前主要用 pl.DataFrame）。
        返回一个字典，键是端口名，值是产生的类型。
        例如: {'processed_data': pl.DataFrame, 'summary': pl.DataFrame}
        """
        raise NotImplementedError

    @abc.abstractmethod
    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        """
        执行节点的核心逻辑。

        Args:
            inputs: 一个字典，包含来自上游节点的输入数据。
                    键是当前节点定义的输入端口名，值是对应的 Polars DataFrame。

        Returns:
            一个字典，包含当前节点的输出数据。
            键是当前节点定义的输出端口名，值是对应的 Polars DataFrame。
        """
        raise NotImplementedError

    def set_params(self, params: Dict[str, Any]):
        """
        更新节点的参数。
        """
        self.params = params if params is not None else {}
        self._validate_params() # 更新后再次校验

    def _validate_params(self):
        """
        (内部方法) 验证当前参数是否符合 get_params_schema() 定义的规范。
        子类可以重写此方法以实现更复杂的验证逻辑。
        基础实现可以检查必需参数是否存在，类型是否匹配等。
        """
        schema = self.get_params_schema()
        for name, definition in schema.items():
            # 简单示例：检查必需参数是否存在 (假设 'required' 标志)
            # if definition.get('required') and name not in self.params:
            #     raise ValueError(f"节点 '{self.node_type}' (ID: {self.node_id}) 缺少必需参数: {name}")
            # 可以添加类型检查等
            pass # 暂不实现具体验证逻辑

    def validate_inputs(self, inputs: Dict[str, pl.DataFrame]):
        """
        验证输入数据是否符合 define_inputs() 定义的规范。
        基础实现检查必需的输入是否存在以及类型是否大致匹配。

        Args:
            inputs: 提供的输入数据字典。

        Raises:
            ValueError: 如果输入不符合规范。
        """
        expected_inputs = self.define_inputs()
        for name, expected_type in expected_inputs.items():
            if name not in inputs:
                raise ValueError(f"节点 '{self.node_type}' (ID: {self.node_id}) 缺少输入端口: {name}")
            if not isinstance(inputs[name], expected_type):
                 # 注意：这里类型检查可能需要更灵活，例如允许子类
                 # 但对于 Polars DataFrame，目前直接比较类型即可
                raise ValueError(f"节点 '{self.node_type}' (ID: {self.node_id}) 输入端口 '{name}' 的类型错误。期望 {expected_type}, 得到 {type(inputs[name])}")

        # 也可以检查是否有未定义的额外输入，根据需要决定是否报错
        # for name in inputs:
        #     if name not in expected_inputs:
        #         print(f"警告：节点 '{self.node_type}' (ID: {self.node_id}) 收到未定义的输入端口: {name}")

    def __repr__(self) -> str:
        return f"<{self.node_type} node_id={self.node_id}>" 