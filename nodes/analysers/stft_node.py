import numpy as np
from scipy import signal
from typing import Dict, Tuple, List, Optional, Union
from core.node.base_node import BaseNode


class STFTNode(BaseNode):
    """短时傅里叶变换节点，专注于STFT分析"""

    def process(
        self,
        slice_data: Dict,
        freq_range: Tuple[float, float] = (0, 0.001),  # 感兴趣的频率范围 (Hz)
        nperseg: Optional[int] = None,  # STFT的窗口长度
        noverlap: Optional[int] = None,  # STFT的重叠长度
        slice_index: int = 0,  # 要处理的切片索引，-1表示处理所有切片
    ) -> Dict:
        """
        对数据切片执行短时傅里叶变换

        Args:
            slice_data: 来自SliceNode的切片数据字典
            freq_range: 感兴趣的频率范围 (Hz)
            nperseg: STFT的窗口长度，默认为窗口点数的1/8
            noverlap: STFT的重叠长度，默认为nperseg的75%
            slice_index: 要处理的切片索引，-1表示处理所有切片

        Returns:
            Dict: STFT分析结果
                - method: str 'stft'
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

        # 设置STFT参数
        if nperseg is None:
            nperseg = slice_data["window_points"] // 8
            nperseg = max(nperseg, 64)  # 至少64点

        if noverlap is None:
            noverlap = int(nperseg * 0.75)

        spectrograms = []
        all_frequencies = None
        all_times = []

        for time_slice, value_slice in slices_to_process:
            # 去除均值（直流分量）
            value_slice = value_slice - np.mean(value_slice)

            # 短时傅里叶变换
            f, t, Zxx = signal.stft(
                value_slice,
                fs=sampling_rate,
                window="hann",
                nperseg=nperseg,
                noverlap=noverlap,
                nfft=None,
                detrend=False,
            )

            # 取幅值谱
            spectrogram = np.abs(Zxx)

            # 选择感兴趣的频率范围
            freq_mask = (f >= freq_range[0]) & (f <= freq_range[1])
            spectrogram = spectrogram[freq_mask, :]
            frequencies = f[freq_mask]
            times = t

            spectrograms.append(spectrogram)

            # 保存频率数组（所有切片共用）
            if all_frequencies is None:
                all_frequencies = frequencies

            # 收集时间数组
            all_times.append(times)

        # 构造返回结果
        result = {
            "method": "stft",
            "frequencies": all_frequencies,
            "times": all_times[0] if len(all_times) == 1 else all_times,
            "spectrograms": spectrograms[0] if len(spectrograms) == 1 else spectrograms,
            "slice_times": slice_times,
        }

        return result
