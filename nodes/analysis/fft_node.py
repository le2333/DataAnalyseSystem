import pandas as pd
import numpy as np
from scipy.signal import welch
import param
from typing import Dict, Type
from core.node.base_node import BaseNode
from core.node.registry import NodeRegistry


@NodeRegistry.register_node
class FftNode(BaseNode):
    """
    对输入的时间序列（可带分片ID）做FFT，输出频谱或功率谱密度。
    """

    value_column = param.String(default="value", doc="要进行FFT的数值列名")
    sampling_rate = param.Number(default=1.0, bounds=(0, None), doc="采样率 (Hz)")
    psd_method = param.Selector(
        default="fft_magnitude", objects=["fft_magnitude", "welch"], doc="频谱计算方法"
    )
    segment_id_column = param.String(default="segment_id", doc="分片ID列名（可选）")

    @classmethod
    def define_inputs(cls) -> Dict[str, Type]:
        return {"input_data": pd.DataFrame}

    @classmethod
    def define_outputs(cls) -> Dict[str, Type]:
        return {"fft_results": pd.DataFrame}

    def run(self, inputs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = inputs["input_data"]
        col = self.value_column
        rate = self.sampling_rate
        method = self.psd_method
        seg_col = self.segment_id_column
        # 判断是否有分片ID
        if seg_col in df.columns:
            results = []
            for seg_id, seg_df in df.groupby(seg_col):
                arr = seg_df[col].to_numpy()
                if len(arr) == 0:
                    continue
                if method == "fft_magnitude":
                    fft_vals = np.fft.fft(arr)
                    fft_freq = np.fft.fftfreq(len(arr), d=1.0 / rate)
                    pos_idx = fft_freq >= 0
                    freq = fft_freq[pos_idx]
                    mag = np.abs(fft_vals[pos_idx]) / len(arr)
                    res = pd.DataFrame(
                        {
                            "frequency": freq,
                            "magnitude": mag,
                            seg_col: [seg_id] * len(freq),
                        }
                    )
                else:
                    freq, psd = welch(arr, fs=rate)
                    res = pd.DataFrame(
                        {"frequency": freq, "psd": psd, seg_col: [seg_id] * len(freq)}
                    )
                results.append(res)
            if not results:
                return {"fft_results": pd.DataFrame({})}
            out = pd.concat(results, ignore_index=True)
        else:
            arr = df[col].to_numpy()
            if len(arr) == 0:
                return {"fft_results": pd.DataFrame({})}
            if method == "fft_magnitude":
                fft_vals = np.fft.fft(arr)
                fft_freq = np.fft.fftfreq(len(arr), d=1.0 / rate)
                pos_idx = fft_freq >= 0
                freq = fft_freq[pos_idx]
                mag = np.abs(fft_vals[pos_idx]) / len(arr)
                out = pd.DataFrame({"frequency": freq, "magnitude": mag})
            else:
                freq, psd = welch(arr, fs=rate)
                out = pd.DataFrame({"frequency": freq, "psd": psd})
        return {"fft_results": out}
