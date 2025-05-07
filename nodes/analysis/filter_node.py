import numpy as np
from scipy import signal
from typing import Tuple, Optional, Dict, List, Any, Union
from core.node.base_node import BaseNode

class FilterNode(BaseNode):
    """滤波节点，专注于信号滤波处理"""
    
    def process(
        self,
        time_array: np.ndarray,
        value_array: np.ndarray,
        filter_type: str = 'mean',  # 'mean' 均值降采样, 'lowpass' 低通滤波
        filter_param: float = 5,    # 均值降采样时为窗口大小，低通时为截止频率(Hz)
        sampling_rate: Optional[float] = None  # 采样率，如果为None则从time_array计算
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        对信号进行滤波处理
        
        Args:
            time_array: 时间数组
            value_array: 值数组
            filter_type: 滤波类型，'mean'或'lowpass'
            filter_param: 滤波参数，对于'mean'是窗口大小，对于'lowpass'是截止频率
            sampling_rate: 采样率，如果为None则从time_array计算
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: (滤波后的时间数组, 滤波后的值数组)
        """
        # 确保输入数组长度相同
        assert len(time_array) == len(value_array), "时间数组和值数组长度必须相同"
        
        # 如果未提供采样率，则计算采样率
        if sampling_rate is None:
            time_diff = np.diff(time_array)
            try:
                # 尝试使用pandas.Series.dt方法 (如果time_array是pandas日期时间)
                import pandas as pd
                if isinstance(time_array, pd.Series):
                    median_diff_seconds = time_array.diff().dt.total_seconds().median()
                else:
                    # 尝试用datetime类型计算秒数差
                    median_diff_seconds = pd.Series(time_diff).dt.total_seconds().median()
            except (AttributeError, ImportError):
                # 如果不是pandas日期时间，假设已经是秒数
                median_diff_seconds = np.median(time_diff)
            
            sampling_rate = 1 / median_diff_seconds
        
        # 应用对应的滤波方法
        if filter_type.lower() == 'mean':
            # 均值降采样
            filtered_values = self._downsample_mean(value_array, int(filter_param))
            return time_array, filtered_values
            
        elif filter_type.lower() == 'lowpass':
            # 低通滤波 (巴特沃斯滤波器)
            nyquist = sampling_rate / 2
            cutoff = float(filter_param) / nyquist  # 归一化截止频率
            
            # 设计巴特沃斯低通滤波器
            b, a = signal.butter(4, cutoff, 'low')
            
            # 应用滤波器 (使用零相位滤波)
            filtered_values = signal.filtfilt(b, a, value_array)
            return time_array, filtered_values
            
        else:
            raise ValueError(f"不支持的滤波类型: {filter_type}")
    
    def _downsample_mean(self, x: np.ndarray, window: int) -> np.ndarray:
        """
        对信号x进行窗口大小为window的均值降采样
        
        Args:
            x: 输入信号
            window: 窗口大小
            
        Returns:
            np.ndarray: 降采样处理后的信号
        """
        n = len(x)
        
        # 如果窗口大小为1或0，直接返回原始信号
        if window <= 1:
            return x
            
        # 计算降采样后的长度
        m = n // window
        
        if m == 0:  # 处理信号长度小于窗口大小的情况
            return np.array([np.mean(x)])
            
        # 初始化输出
        y = np.zeros(m)
        
        # 对每个窗口计算均值
        for i in range(m):
            start_idx = i * window
            end_idx = min(start_idx + window, n)
            y[i] = np.mean(x[start_idx:end_idx])
        
        # 处理剩余的点
        if n % window != 0:
            remainder = x[m*window:]
            if len(remainder) > 0:
                y = np.append(y, np.mean(remainder))
        
        # 如果需要，插值回原始长度（保持滤波后的时间对齐）
        t_orig = np.arange(n)
        t_down = np.linspace(0, n-1, len(y))
        y_interp = np.interp(t_orig, t_down, y)
        
        return y_interp 