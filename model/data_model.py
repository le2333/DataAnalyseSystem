import pandas as pd
import numpy as np
import os
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.csv as csv
import time

class DataModel:
    """数据模型：负责数据的加载、存储和处理"""
    
    def __init__(self):
        self.data = None
        self.metadata = {}
        self.cache = {}  # 用于存储不同采样级别的数据缓存
    
    def load_csv(self, file_path):
        """使用pyarrow高效加载CSV文件"""
        try:
            # 使用pyarrow加速CSV读取
            table = csv.read_csv(file_path)
            self.data = table.to_pandas()
            
            # 记录元数据
            self.metadata['file_path'] = file_path
            self.metadata['rows'] = len(self.data)
            self.metadata['columns'] = list(self.data.columns)
            self.metadata['memory_usage'] = self.data.memory_usage(deep=True).sum()
            
            # 清空缓存
            self.cache = {}
            
            return self.data
        except Exception as e:
            raise Exception(f"加载CSV文件失败: {str(e)}")
    
    def get_data(self, sample_rate=None):
        """获取数据，支持采样"""
        if self.data is None:
            return None
            
        if sample_rate is None:
            return self.data
            
        # 检查缓存
        if sample_rate in self.cache:
            return self.cache[sample_rate]
            
        # 根据数据量和采样率决定采样方法
        if sample_rate < 0.01 or len(self.data) > 1000000:
            # 对于非常大的数据集或很小的采样率，使用系统采样
            sampled_data = self.data.sample(frac=sample_rate)
        else:
            # 使用LTTB算法进行降采样，保留数据形状特征
            sampled_size = int(len(self.data) * sample_rate)
            sampled_data = self._lttb_downsample(self.data, sampled_size)
        
        # 缓存结果
        self.cache[sample_rate] = sampled_data
        
        return sampled_data
    
    def _lttb_downsample(self, data, target_points):
        """简化的LTTB降采样算法实现"""
        # 这里是简化版，实际应该使用专门的库或完整实现
        if len(data) <= target_points:
            return data
            
        # 简单的等距采样作为示例
        indices = np.linspace(0, len(data) - 1, target_points, dtype=int)
        return data.iloc[indices]
