import pandas as pd
import param
from typing import Dict, Type
from core.node.base_node import BaseNode
from core.node.registry import NodeRegistry


@NodeRegistry.register_node
class SegmentNode(BaseNode):
    """
    对时间序列按窗口大小和步长进行分片，输出带分片ID的DataFrame。
    """

    window_size = param.Integer(
        default=256, bounds=(1, None), doc="每个分片的长度（行数）"
    )
    step = param.Integer(default=256, bounds=(1, None), doc="分片步长（行数）")
    value_column = param.String(default="value", doc="要分片的数值列名")

    @classmethod
    def define_inputs(cls) -> Dict[str, Type]:
        return {"input_data": pd.DataFrame}

    @classmethod
    def define_outputs(cls) -> Dict[str, Type]:
        return {"segmented": pd.DataFrame}

    def run(self, inputs: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        df = inputs["input_data"]
        col = self.value_column
        win = self.window_size
        step = self.step
        if col not in df.columns:
            raise ValueError(f"列 {col} 不存在于输入数据中")
        values = df[col].to_numpy()
        n = len(values)
        segments = []
        for i in range(0, n - win + 1, step):
            seg = values[i : i + win]
            seg_id = i // step
            seg_df = pd.DataFrame({col: seg})
            seg_df["segment_id"] = seg_id
            segments.append(seg_df)
        if not segments:
            return {"segmented": pd.DataFrame({col: [], "segment_id": []})}
        result = pd.concat(segments, ignore_index=True)
        return {"segmented": result}
