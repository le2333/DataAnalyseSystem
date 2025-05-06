import pandas as pd
import param
from typing import Dict, Type
from core.node.base_node import BaseNode
from core.node.registry import NodeRegistry


@NodeRegistry.register_node
class MergeAlignNode(BaseNode):
    """
    合并并按时间戳对齐多个时间序列（pandas DataFrame）。
    支持动态输入，按指定时间列和对齐方式（inner/outer/left/right）合并。
    """

    time_column = param.String(default="timestamp", doc="用于对齐的时间戳列名")
    how = param.Selector(
        default="outer", objects=["inner", "outer", "left", "right"], doc="合并方式"
    )

    @classmethod
    def define_inputs(cls) -> Dict[str, Type]:
        # 单一字典输入，键为序列名，值为 DataFrame
        return {"inputs": dict}

    @classmethod
    def define_outputs(cls) -> Dict[str, Type]:
        return {"merged": pd.DataFrame}

    def run(self, inputs: Dict[str, dict]) -> Dict[str, pd.DataFrame]:
        # inputs["inputs"] 是 Dict[str, pd.DataFrame]
        input_dfs = inputs["inputs"]
        if not isinstance(input_dfs, dict) or len(input_dfs) < 2:
            raise ValueError(
                "请提供至少两个待合并的 DataFrame，格式为 Dict[str, pd.DataFrame]"
            )
        time_col = self.time_column
        how = self.how
        # 依次合并
        items = list(input_dfs.items())
        merged = items[0][1]
        for idx, (name, df) in enumerate(items[1:], start=2):
            # 避免列名冲突，自动重命名
            suffix = f"_{name}"
            right_cols = [c for c in df.columns if c != time_col]
            rename_map = {c: c + suffix for c in right_cols}
            df_renamed = df.rename(columns=rename_map)
            merged = pd.merge(merged, df_renamed, on=time_col, how=how)
        return {"merged": merged}
