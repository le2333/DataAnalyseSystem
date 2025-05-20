import os
import pandas as pd
import numpy as np
from typing import Dict, Any

def load_csv_folder(dir_path: str) -> Dict[str, pd.DataFrame]:
    """
    批量读取指定文件夹下所有csv文件，返回以文件名为key的DataFrame字典。
    自动将time_col设为索引，并去重。
    """
    dataframes = {}
    for file in os.listdir(dir_path):
        if file.endswith('.csv'):
            file_path = os.path.join(dir_path, file)
            df = pd.read_csv(file_path)
            df.columns = ['timestamp', file]
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            df = df.loc[~df.index.duplicated(keep='first')]
            dataframes[file] = df
    return dataframes

def align_and_merge_dataframes(dataframes: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    对齐并合并多个DataFrame（以index为时间戳），每个DataFrame的value列重命名为文件名。
    返回合并后的DataFrame。
    """
    if not dataframes:
        return pd.DataFrame()
    first_key = list(dataframes.keys())[0]
    reference_df = dataframes[first_key].copy()
    reference_df = reference_df.rename(columns={col: f"{first_key}_{col}" for col in reference_df.columns})
    aligned_df = reference_df.copy()
    for key in list(dataframes.keys())[1:]:
        df = dataframes[key].copy()
        # 最近邻对齐
        aligned = df.reindex(aligned_df.index, method='nearest')
        df_renamed = aligned.rename(columns={'value': key})
        aligned_df = aligned_df.join(df_renamed, how='outer')
    return aligned_df

def group_by_timestamp_pattern(dataframes: Dict[str, pd.DataFrame]) -> Dict[str, list]:
    """
    按第一个时间戳的格式分组，返回pattern->[(file,df), ...]的字典。
    """
    from collections import defaultdict
    grouped = defaultdict(list)
    for file, df in dataframes.items():
        if not df.empty:
            timestamp_pattern = df.index[0].strftime('%Y-%m-%d %H:%M:%S')
            grouped[timestamp_pattern].append((file, df))
    return grouped

def merge_dataframes_by_timestamp(dataframes: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    """
    按时间戳pattern分组后合并，返回pattern->合并后DataFrame的字典。
    """
    grouped = group_by_timestamp_pattern(dataframes)
    merged_results = {}
    for pattern, dfs in grouped.items():
        if len(dfs) <= 1:
            continue
        merged_df = pd.DataFrame()
        for file, df in dfs:
            df_renamed = df.rename(columns={'value': file})
            if merged_df.empty:
                merged_df = df_renamed
            else:
                merged_df = merged_df.join(df_renamed, how='outer')
        merged_results[pattern] = merged_df
    return merged_results 