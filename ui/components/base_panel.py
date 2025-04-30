import abc
import param
import panel as pn
from abc import ABCMeta

# 直接导入 WorkflowViewModel
from viewmodels import WorkflowViewModel

# --- 组合元类解决冲突 ---
# 直接使用 type() 获取 Parameterized 的元类
class AbstractParameterizedMeta(type(param.Parameterized), ABCMeta):
    """组合 param.Parameterized 和 abc.ABC 的元类。"""
    pass

class BasePanelComponent(param.Parameterized, abc.ABC, metaclass=AbstractParameterizedMeta):
    """
    所有 UI 组件面板的基类。
    强制要求提供 ViewModel 实例，并定义了 panel() 抽象方法。
    """
    # --- 输入参数 ---
    # 直接使用导入的类，并更新类型提示
    view_model: WorkflowViewModel = param.ClassSelector(class_=WorkflowViewModel, doc="关联的 WorkflowViewModel")

    def __init__(self, **params):
        # 确保 view_model 存在
        if 'view_model' not in params or params['view_model'] is None:
            raise ValueError(f"{type(self).__name__} 需要一个有效的 WorkflowViewModel 实例。")
        super().__init__(**params)

    @abc.abstractmethod
    def panel(self) -> pn.viewable.Viewable:
        """
        返回此组件的 Panel 布局表示。
        子类必须实现此方法。
        """
        raise NotImplementedError