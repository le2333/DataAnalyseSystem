import pandas as pd
import pyarrow.csv as csv
import os
import time

class DataModel:
    """数据模型：负责数据加载、处理和提供"""
    
    def __init__(self):
        self.data = None
        self.time_column = None
        self.file_path = None
    
    def load_csv(self, file_path, time_column=None):
        """加载CSV数据并可选设置时间索引"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        start_time = time.time()
        try:
            # 高效读取CSV
            parse_options = csv.ParseOptions(ignore_empty_lines=True)
            read_options = csv.ReadOptions(use_threads=True, block_size=2**22)
            
            # 读取为Arrow表，然后转换为pandas
            self.data = csv.read_csv(file_path, 
                                    parse_options=parse_options, 
                                    read_options=read_options).to_pandas()
            self.file_path = file_path
            
            # 处理时间列
            if time_column and time_column in self.data.columns:
                self.time_column = time_column
                self.data[time_column] = pd.to_datetime(self.data[time_column], errors='coerce')
                self.data.set_index(time_column, inplace=True)
            
            load_time = time.time() - start_time
            print(f"数据加载成功: {len(self.data)}行, {len(self.data.columns)}列, 耗时: {load_time:.2f}秒")
            return self.data
            
        except Exception as e:
            print(f"数据加载失败: {str(e)}")
            raise
    
    def get_data(self):
        """返回当前加载的数据"""
        if self.data is None:
            print("警告: 尚未加载数据")
            return pd.DataFrame()
        return self.data
    
    def get_data_stats(self):
        """获取数据的基本统计信息"""
        if self.data is None:
            return {}
        
        stats = {
            'rows': len(self.data),
            'columns': len(self.data.columns),
            'memory_usage': self.data.memory_usage(deep=True).sum() / (1024 * 1024),  # MB
            'column_types': {col: str(dtype) for col, dtype in self.data.dtypes.items()}
        }
        
        return stats 