import abc
import logging # 添加 logging
import polars as pl
from typing import Dict, List, Any, Type
import panel as pn # 导入 panel
import param # 导入 param 以支持默认实现
# 导入 param 的元类
from param.parameterized import ParameterizedMetaclass

logger = logging.getLogger(__name__) # 获取 logger

# 定义合并后的元类
class NodeMeta(ParameterizedMetaclass, abc.ABCMeta):
    """元类，结合 ParameterizedMetaclass 和 ABCMeta 以解决冲突。"""
    pass

# BaseNode 使用新的元类，并调整基类顺序
class BaseNode(param.Parameterized, abc.ABC, metaclass=NodeMeta):
    """
    节点的基础抽象类。
    所有具体节点都应继承此类并实现抽象方法。
    继承自 param.Parameterized 以方便使用 pn.Param。
    使用 NodeMeta 解决 abc.ABC 和 param.Parameterized 的元类冲突。
    """
    # node_id 不应是 param，因为它在初始化后通常是固定的
    # params 可以是 param.Dict，但更灵活的方式是节点自己定义参数
    # _node_id: str 
    # params: Dict[str, Any] = param.Dict(default={}, doc="节点的配置参数")

    # 添加一些通用的、不应出现在配置面板中的参数
    # 子类应该将自己的配置参数定义为 Parameterized 参数
    position = param.Tuple(default=(0.0, 0.0), length=2, precedence=-1, doc="节点在画布上的位置")
    workflow_runner = param.Parameter(default=None, precedence=-1, doc="工作流运行器的引用 (可选)")

    def __init__(self, node_id: str, params: Dict[str, Any] = None, **param_params):
        """
        初始化节点。

        Args:
            node_id: 节点的唯一标识符。
            params: 节点的配置参数字典 (用于初始化 param 参数)。
            param_params: 其他传递给 param.Parameterized 的关键字参数。
        """
        # 检查是否有 'position' 在 params 中，并单独处理
        position = params.pop('position', None) if params else None
        if position is not None:
            param_params['position'] = position # 传递给 super init
            
        # 使用 name 参数存储 node_id，因为 param.Parameterized 有 name 属性
        # 注意：需要确保这里的 name 不会与其他 param 参数冲突
        super().__init__(name=node_id, **param_params)
        # self._node_id = node_id
        
        # 将传入的 params 设置到对应的 Parameterized 参数上
        if params:
            # 检查 params 中的 key 是否与 BaseNode 或其子类中定义的 param 参数匹配
            valid_params = {k: v for k, v in params.items() if k in self.param}
            if len(valid_params) != len(params):
                invalid_keys = set(params.keys()) - set(valid_params.keys())
                # 使用 logger
                logger.warning(f"节点 '{node_id}': 初始化时提供了无效或未定义的参数: {invalid_keys}")
            if valid_params:
                 self.param.update(**valid_params)
             
        # self.params = params if params is not None else {}
        # self._validate_params() # 初始化时校验参数 (param 库会自动处理一些校验)

    @property
    def node_id(self) -> str:
        """返回节点的唯一ID（使用 Parameterized 的 name 属性）。"""
        return self.name

    @property
    def node_type(self) -> str:
        """返回节点的类型（通常是类名）。"""
        return self.__class__.__name__

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

    # set_params 不再需要，直接修改实例的 param 属性即可
    # def set_params(self, params: Dict[str, Any]):
    #     """
    #     更新节点的参数。
    #     """
    #     # self.params = params if params is not None else {}
    #     self.param.update(**params)
    #     # self._validate_params() # 更新后再次校验

    # _validate_params 也不再显式需要，param 库会处理
    # def _validate_params(self):
    #     # ...
    #     pass 

    # validate_inputs 保持不变
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
            # 基础类型检查
            if not isinstance(inputs[name], expected_type):
                # 考虑更灵活的检查，例如允许 None 或子类？目前严格匹配
                raise ValueError(f"节点 '{self.node_type}' (ID: {self.node_id}) 输入端口 '{name}' 的类型错误。期望 {expected_type.__name__}, 得到 {type(inputs[name]).__name__}")

    # --- 配置面板生成 (模板方法模式) ---

    def get_config_panel(self) -> pn.viewable.Viewable:
        """
        获取节点的配置面板 (模板方法)。
        
        **重要**: 此方法保证返回一个全新的顶层 Panel 容器 (`pn.Column`)，
        以避免 Bokeh 的 "already in a doc" 错误。
        
        实际的 UI 内容由 `_build_config_panel_content` 方法构建。
        子类通常只需要覆盖 `_build_config_panel_content`。
        
        Returns:
            一个新的 Panel Viewable 对象，包含配置 UI。
        """
        logger.debug(f"Node '{self.node_id}': Calling get_config_panel (Template Method)")
        try:
            # 调用由子类实现（或默认）的内容构建方法
            content = self._build_config_panel_content()
            # 总是将内容包装在一个新的 Column 中返回
            # name 属性有助于调试时识别 Panel 对象
            wrapper_name = f"{self.node_id}_config_wrapper"
            logger.debug(f"Node '{self.node_id}': Wrapping content in new pn.Column: {wrapper_name}")
            return pn.Column(content, name=wrapper_name, sizing_mode='stretch_width')
        except Exception as e:
            logger.error(f"节点 '{self.node_id}' 在 get_config_panel 中构建包装器时出错: {e}", exc_info=True)
            return pn.pane.Alert(f"无法为节点 '{self.node_id}' 构建配置面板包装器: {e}", alert_type='danger')

    def _build_config_panel_content(self) -> Any:
        """
        构建配置面板的实际 UI 内容 (由子类覆盖)。
        
        **重要**: 子类实现此方法时，应确保返回的任何 Panel 组件
        (特别是包含复杂布局或自定义模型的) 都是新创建的实例，
        而不是缓存的或共享的实例。
        
        默认实现使用 `pn.Param` 自动显示节点的可配置参数。
        
        Returns:
            配置面板的内容 (单个 Panel 对象或列表)。
        """
        logger.debug(f"Node '{self.node_id}': Using default _build_config_panel_content (pn.Param)")
        try:
            # 定义不应出现在自动配置面板中的参数名称
            excluded_params = ['name', 'position', 'workflow_runner']
            # 获取所有非隐藏 (-1) 且不在排除列表中的参数
            params_to_show = [
                p for p in self.param 
                if self.param[p].precedence != -1 and p not in excluded_params
            ]
            
            if params_to_show:
                # pn.Param 应该每次都生成新的视图元素
                logger.debug(f"Node '{self.node_id}': Generating pn.Param for: {params_to_show}")
                return pn.Param(self.param, parameters=params_to_show, name=f"参数: {self.node_type}")
            else:
                logger.debug(f"Node '{self.node_id}': No configurable parameters found for default panel.")
                return pn.pane.Markdown("_此节点没有可配置参数。_")
        except Exception as e:
            logger.error(f"节点 '{self.node_id}' 生成默认配置内容 (pn.Param) 失败: {e}", exc_info=True)
            return pn.pane.Alert(f"无法为节点 '{self.node_id}' 生成默认配置内容: {e}", alert_type='danger')

    def __repr__(self) -> str:
        return f"<{self.node_type} node_id={self.node_id}>" 