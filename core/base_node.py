import pandas as pd
from abc import ABC, abstractmethod


class BaseNode(ABC):
    """
    基础节点类，用于定义节点结构
    """

    def __init__(
        self,
        name: str,
        description: str,
        params: dict,
        input_type: str,
        output_type: str,
    ):
        self.name = name
        self.description = description
        self.params = params
        self.input_type = input_type
        self.output_type = output_type

    @abstractmethod
    def method(self, data):
        pass

    @abstractmethod
    def set_params(self, params: dict):
        pass

    @abstractmethod
    def config_panel(self):
        pass
