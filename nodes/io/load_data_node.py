import pandas as pd
import numpy as np
from datetime import datetime
from typing import Tuple, Union, List, Optional
from core.node.base_node import BaseNode


class LoadDataNode(BaseNode):
    """数据加载节点，从CSV文件加载时序数据"""

    def process(
        self,
        file_path: str,
        time_column: Optional[str] = None,
        value_column: Optional[str] = None,
        datetime_format: Optional[str] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        从CSV文件加载时间序列数据

        Args:
            file_path: CSV文件路径
            time_column: 时间列名，若为None则使用第一列
            value_column: 值列名，若为None则使用第二列
            datetime_format: 日期时间格式，若为None则自动推断

        Returns:
            Tuple[np.ndarray, np.ndarray]: (时间数组, 值数组)
        """
        # 读取CSV文件
        df = pd.read_csv(file_path)

        # 确定时间列和值列
        if time_column is None:
            time_column = df.columns[0]

        if value_column is None:
            value_column = df.columns[1]

        # 转换时间列为datetime对象
        if datetime_format:
            df[time_column] = pd.to_datetime(df[time_column], format=datetime_format)
        else:
            df[time_column] = pd.to_datetime(df[time_column])

        # 提取时间和值数组
        time_array = df[time_column].to_numpy()
        value_array = df[value_column].to_numpy()

        # 计算采样率信息（可用于后续节点）
        time_diff = np.diff(time_array)
        median_diff_timedelta = np.median(time_diff)  # 这是一个numpy.timedelta64对象

        # 将 numpy.timedelta64 转换为总秒数（浮点数）
        # 首先转换为 timedelta64[ns] (纳秒)，然后除以 1e9 得到秒
        median_diff_seconds = (
            median_diff_timedelta.astype("timedelta64[ns]").astype(np.int64) / 1e9
        )

        fs = 1 / median_diff_seconds  # 采样率（Hz）

        # 记录元数据
        self.metadata = {
            "sampling_rate": fs,
            "start_time": time_array[0],
            "end_time": time_array[-1],
            "num_samples": len(time_array),
            "file_path": file_path,
        }

        return time_array, value_array
