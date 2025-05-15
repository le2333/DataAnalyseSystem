from typing import Dict, Any, ClassVar, List, Type, Optional, Set
import pandas as pd
from abc import ABC, abstractmethod


class ServiceBase(ABC):
    """所有服务的抽象基类"""

    # 类变量用于存储所有服务类
    service_registry: ClassVar[Dict[str, Type["ServiceBase"]]] = {}

    # 服务名称和描述
    name: ClassVar[str] = ""
    description: ClassVar[str] = ""

    @classmethod
    def __init_subclass__(cls, **kwargs):
        """当一个子类被创建时，自动注册到注册表中"""
        super().__init_subclass__(**kwargs)
        if cls.name:  # 只有设置了name的具体服务类才会注册
            ServiceBase.service_registry[cls.name] = cls
            print(f"注册服务: {cls.name}")

    @classmethod
    def get_all_services(cls) -> Dict[str, Type["ServiceBase"]]:
        """获取所有注册的服务"""
        return cls.service_registry

    @classmethod
    @abstractmethod
    def get_param_specs(cls) -> Dict[str, Dict[str, Any]]:
        """返回该服务需要的参数规范，用于UI生成"""
        return {}


class DataLoader(ServiceBase):
    """数据加载服务的基类"""

    @classmethod
    @abstractmethod
    def load(cls, file_path: str, **params) -> pd.DataFrame:
        """加载数据文件"""
        pass


class DataStructurer(ServiceBase):
    """数据结构化服务的基类"""

    @classmethod
    @abstractmethod
    def structure(cls, input_data: Any, **params) -> Any:
        """对数据进行结构化处理"""
        pass


class DataVisualizer(ServiceBase):
    """数据可视化服务的基类"""

    # 可视化器支持的数据类型
    supported_data_types: ClassVar[Set[str]] = set()

    @classmethod
    @abstractmethod
    def visualize(cls, data: Any, **params) -> Any:
        """创建可视化结果"""
        pass


class DataPreprocessor(ServiceBase):
    """数据预处理服务的基类"""

    @classmethod
    @abstractmethod
    def preprocess(cls, data: Any, **params) -> Any:
        """预处理数据"""
        pass
