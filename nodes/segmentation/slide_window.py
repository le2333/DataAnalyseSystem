import pandas as pd
import numpy as np

def ts_window_segmentation(df: pd.DataFrame, window_size: int, step_size: int) -> list[pd.DataFrame]:
    """
    将时间索引的多维DataFrame按滑动窗口分割为子DataFrame列表。
    """
    num_rows = df.shape[0]
    return [df.iloc[i:i+window_size].copy() for i in range(0, num_rows - window_size + 1, step_size)]


def merge_segmented_ts(dfs: list[pd.DataFrame]) -> pd.DataFrame:
    """
    直接拼接所有片段，并按时间索引升序排列。
    """
    if not dfs:
        return pd.DataFrame()
    merged_df = pd.concat(dfs)
    merged_df = merged_df.sort_index()
    return merged_df
