import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist

def self_join(values, window_size, step):
    """
    生成所有历史滑动窗口
    """
    return np.array([values[j:j+window_size] for j in range(0, len(values)-window_size+1, step)])

def norm_crosscount(cur_win, past_windows):
    """
    计算当前窗口与历史窗口的最小归一化欧氏距离
    """
    if len(past_windows) == 0:
        return 0.0
    dists = cdist([cur_win.flatten()], past_windows.reshape(len(past_windows), -1), metric='euclidean')
    norm = np.linalg.norm(cur_win) + 1e-8
    return (dists.min() / norm) if norm > 0 else dists.min()

def compute_floss_scores(df, window_size=20, step=1):
    """
    计算多维时间序列的 FLOSS 分数
    返回分数数组，与df长度一致
    """
    values = df.values
    n = len(df)
    scores = np.zeros(n)
    for i in range(window_size, n - window_size, step):
        cur_win = values[i:i+window_size]
        past_windows = self_join(values[:i], window_size, step)
        scores[i+window_size//2] = norm_crosscount(cur_win, past_windows)
    return scores

def detect_change_points(scores, window_size=20, threshold=None, find_peaks=True):
    """
    根据分数检测分段点，返回分段点标志数组
    """
    n = len(scores)
    is_change_point = np.zeros(n, dtype=int)
    if find_peaks:
        from scipy.signal import find_peaks
        peaks, _ = find_peaks(scores, distance=window_size)
        is_change_point[peaks] = 1
    elif threshold is not None:
        is_change_point[scores > threshold] = 1
    return is_change_point

def floss_score(df, window_size=20, step=1, threshold=None, find_peaks=True):
    """
    主流程：计算分数并检测分段点，返回包含 index, floss_score, is_change_point 的 DataFrame
    """
    scores = compute_floss_scores(df, window_size, step)
    is_change_point = detect_change_points(scores, window_size, threshold, find_peaks)
    result_df = pd.DataFrame({
        'floss_score': scores,
        'is_change_point': is_change_point
    }, index=df.index)
    return result_df
