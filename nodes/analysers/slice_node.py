import numpy as np
import pandas as pd
from typing import Tuple, List, Dict, Optional, Union
from core.node.base_node import BaseNode


class SliceNode(BaseNode):
    """数据切片节点，将长时间序列切分为多个重叠窗口"""

    def process(
        self,
        time_array: np.ndarray,
        value_array: np.ndarray,
        window_duration: float = 24 * 60 * 60,  # 默认24小时，单位：秒
        overlap_ratio: float = 0.5,  # 默认50%重叠
        sampling_rate: Optional[float] = None,
    ) -> Dict:
        """
        将时间序列切分为多个重叠窗口

        Args:
            time_array: 时间数组
            value_array: 值数组
            window_duration: 窗口长度（秒）
            overlap_ratio: 重叠比例 [0,1)
            sampling_rate: 采样率（Hz）。如果不提供，将根据time_array计算

        Returns:
            Dict: 包含切片相关信息和数据的字典
                - slices: List[Tuple[np.ndarray, np.ndarray]] 切片列表 (time, value)
                - slice_indices: List[Tuple[int, int]] 每个切片的起止索引
                - slice_times: List[pd.Timestamp] 每个切片的开始时间
                - num_slices: int 切片数量
                - window_points: int 每个窗口的点数
        """
        # 确保输入数组长度相同
        assert len(time_array) == len(value_array), "时间数组和值数组长度必须相同"

        # 如果未提供采样率，则计算采样率
        if sampling_rate is None:
            time_diff = np.diff(time_array)
            try:
                # 如果是datetime64类型，转换为秒
                if np.issubdtype(time_array.dtype, np.datetime64):
                    time_diff_seconds = time_diff.astype("timedelta64[s]").astype(float)
                else:
                    # 尝试使用pandas.Series.dt方法
                    time_diff_seconds = (
                        pd.Series(time_diff).dt.total_seconds().to_numpy()
                    )
            except (AttributeError, TypeError):
                # 如果上述方法都失败，假设time_array已经是数值类型（秒）
                time_diff_seconds = time_diff

            median_diff_seconds = np.median(time_diff_seconds)
            sampling_rate = 1 / median_diff_seconds

        # 计算窗口大小和步长（点数）
        window_points = int(window_duration * sampling_rate)
        step_points = int(window_points * (1 - overlap_ratio))

        # 计算总切片数
        data_length = len(value_array)
        num_slices = max(1, ((data_length - window_points) // step_points) + 1)

        # 创建切片
        slices = []
        slice_indices = []
        slice_times = []

        for i in range(num_slices):
            start_idx = i * step_points
            end_idx = min(start_idx + window_points, data_length)

            # 如果剩余点数不足窗口大小的一半，则停止
            if end_idx - start_idx < window_points // 2:
                break

            time_slice = time_array[start_idx:end_idx]
            value_slice = value_array[start_idx:end_idx]

            slices.append((time_slice, value_slice))
            slice_indices.append((start_idx, end_idx))
            slice_times.append(time_array[start_idx])

        return {
            "slices": slices,
            "slice_indices": slice_indices,
            "slice_times": slice_times,
            "num_slices": len(slices),
            "window_points": window_points,
            "step_points": step_points,
            "sampling_rate": sampling_rate,
        }
