import pandas as pd
from abc import ABC, abstractmethod


class BaseData(ABC):
    """
    基础数据类，用于定义数据结构
    """

    def __init__(self, data: pd.DataFrame, dtype: str):
        self.data = data
        self.dtype = dtype

    def get_data(self):
        return self.data

    @abstractmethod
    def validate_data(self):
        pass
