import numpy as np
import pywt
from typing import Dict, Tuple, List, Optional, Union
from core.node.base_node import BaseNode


class CWTNode(BaseNode):
    """连续小波变换节点，专注于CWT分析，使用PyWavelets库"""

    def process(
        self,
        slice_data: Dict,
        freq_range: Tuple[float, float] = (0, 0.001),  # 感兴趣的频率范围 (Hz)
        num_freqs: int = 100,  # 频率点数
        wavelet: str = "morl",  # 小波类型 ('morl'=Morlet, 'mexh'=Mexican Hat 等)
        slice_index: int = 0,  # 要处理的切片索引，-1表示处理所有切片
    ) -> Dict:
        """
        对数据切片执行连续小波变换

        Args:
            slice_data: 来自SliceNode的切片数据字典
            freq_range: 感兴趣的频率范围 (Hz)
            num_freqs: 频率点数
            wavelet: 小波类型，如 'morl'(Morlet), 'mexh'(Mexican Hat), 'gaus8'(高斯8阶)等
            slice_index: 要处理的切片索引，-1表示处理所有切片

        Returns:
            Dict: CWT分析结果
                - method: str 'cwt'
                - frequencies: np.ndarray 频率数组
                - times: np.ndarray 时间数组
                - spectrograms: List[np.ndarray] 谱图列表（多切片时）或单个谱图
                - slice_times: List[pd.Timestamp] 每个切片的开始时间
        """
        sampling_rate = slice_data["sampling_rate"]

        # 确定要处理的切片
        if slice_index == -1:
            # 处理所有切片
            slices_to_process = slice_data["slices"]
            slice_times = slice_data["slice_times"]
        else:
            # 处理单个切片
            slices_to_process = [slice_data["slices"][slice_index]]
            slice_times = [slice_data["slice_times"][slice_index]]

        # 定义分析频率的范围 - 从Hz转换为PyWavelets使用的尺度
        freqs = np.linspace(freq_range[0], freq_range[1], num_freqs)
        freqs = freqs[freqs > 0]  # 确保频率大于0

        # 将频率转换为尺度 (scale = central_frequency / (frequency * dt))
        # 获取小波的中心频率
        central_freq = pywt.central_frequency(wavelet)
        dt = 1.0 / sampling_rate
        scales = central_freq / (freqs * dt)

        spectrograms = []
        all_times = []

        for time_slice, value_slice in slices_to_process:
            # 去除均值（直流分量）
            value_slice = value_slice - np.mean(value_slice)

            # 执行CWT
            # PyWavelets的cwt返回: (coefficients, frequencies)
            coefficients, _ = pywt.cwt(value_slice, scales, wavelet, dt)

            # 取幅值谱
            spectrogram = np.abs(coefficients)

            # 生成时间数组
            times = np.linspace(0, len(value_slice) / sampling_rate, len(value_slice))

            spectrograms.append(spectrogram)
            all_times.append(times)

        # 构造返回结果
        result = {
            "method": "cwt",
            "frequencies": freqs,
            "times": all_times[0] if len(all_times) == 1 else all_times,
            "spectrograms": spectrograms[0] if len(spectrograms) == 1 else spectrograms,
            "slice_times": slice_times,
        }

        return result
