import numpy as np
import pandas as pd
from scipy.fft import fft, ifft
from scipy.signal import find_peaks as scipy_find_peaks  # 重命名以避免与自定义函数冲突
from typing import Optional  # 为了类型提示 Optional[int]

# 基于 MATLAB 实现的常量
EXCLUSION_ZONE_RATIO = 0.25  # MATLAB 中用于自连接排除区域的 round(SubsequenceLength/4)
NORM_CROSSCOUNT_EXCLUSION_FACTOR = (
    5  # MATLAB 中 norm_crosscount_all 排除区域的 slWindow*5
)


def _sliding_window_view(arr, window_shape, step_shape=None):
    """
    创建数组的滑动窗口视图。
    对于某些操作，这比在循环中手动切片更有效。
    这是一个辅助函数，并非直接来自 MATLAB，但对 numpy 操作很有用。
    """
    if step_shape is None:
        step_shape = (1,) * len(window_shape)

    if isinstance(window_shape, int):
        window_shape = (window_shape,)
    if isinstance(step_shape, int):
        step_shape = (step_shape,)

    arr_shape = np.array(arr.shape)
    window_shape = np.array(window_shape, dtype=arr_shape.dtype)

    if ((arr_shape - window_shape) < 0).any():
        raise ValueError("window_shape 对于 arr_shape 来说太大了")

    new_shape = tuple((arr_shape - window_shape) // step_shape + 1) + tuple(
        window_shape
    )

    new_strides = tuple(np.array(arr.strides) * step_shape) + arr.strides

    return np.lib.stride_tricks.as_strided(arr, shape=new_shape, strides=new_strides)


def _normalize_series(series):
    """对时间序列进行Z标准化。"""
    mean = np.mean(series)
    std = np.std(series)
    if std < 1e-8:  # 避免除以零或非常小的标准差
        return series - mean  # 或者返回 np.zeros_like(series)
    return (series - mean) / std


def fast_find_nn_pre_matlab(A, subsequence_length):
    """
    对应 MATLAB 中的 fastfindNNPre。
    为快速最近邻搜索预计算值。
    """
    n = len(A)
    if n < subsequence_length:
        raise ValueError("时间序列长度必须 >= 子序列长度。")

    # MATLAB 为 FFT 填充到 2*n
    A_padded = np.zeros(2 * n)
    A_padded[:n] = A

    X = fft(A_padded)  # 填充后时间序列的 FFT

    # 用于滚动均值和标准差的累积和
    cum_sum_A = np.cumsum(A)
    cum_sum_A_sq = np.cumsum(A**2)

    # 每个子序列的和
    # MATLAB: sumx2 = cum_sumx2(m:n)-[0;cum_sumx2(1:n-m)];
    # Python: sum_A_sq[subsequence_length-1:] - np.concatenate(([0], cum_sum_A_sq[:-subsequence_length]))
    sum_A2 = cum_sum_A_sq[subsequence_length - 1 :] - np.concatenate(
        ([0], cum_sum_A_sq[:-subsequence_length])
    )
    sum_A = cum_sum_A[subsequence_length - 1 :] - np.concatenate(
        ([0], cum_sum_A[:-subsequence_length])
    )

    mean_A = sum_A / subsequence_length
    # MATLAB 的 (sumx2./m)-(meanx.^2) 是有偏方差（除以N）
    # np.std 默认也是有偏的（总体标准差）
    sig_A2_biased = (sum_A2 / subsequence_length) - (mean_A**2)
    sig_A2 = np.maximum(sig_A2_biased, 1e-8)  # 确保非负，避免 sqrt(0) 问题
    sig_A = np.sqrt(sig_A2)

    return X, n, sum_A2, sum_A, mean_A, sig_A2, sig_A


def fast_find_nn_matlab(
    X_fft_padded_A,
    query_subsequence,
    n_original_A,
    subsequence_length,
    sum_A2,
    sum_A,
    mean_A,
    sig_A2_biased,
    sig_A_biased,
):
    """
    对应 MATLAB 中的 fastfindNN。
    计算 z-标准化欧氏距离轮廓。
    X_fft_padded_A 是原始时间序列 A (填充到 2*n) 的 FFT。
    query_subsequence 是当前子序列 (长度 m)。
    n_original_A 是 A 的原始长度 (填充 FFT 之前)。
    subsequence_length 是 m。
    其他参数是 A 的子序列的预计算统计量。
    """
    m = subsequence_length

    # 标准化查询: y = (y-mean(y))./std(y,1);
    # MATLAB 的 std(y,1) 用 N 进行归一化。np.std 默认也用 N。
    query_norm = _normalize_series(query_subsequence)

    # 反转查询: y = y(end:-1:1);
    query_reversed = query_norm[::-1]

    # 为 FFT 填充查询: y(m+1:2*n) = 0;
    query_padded = np.zeros(2 * n_original_A)
    query_padded[:m] = query_reversed

    # 填充后查询的 FFT
    Y_fft = fft(query_padded)

    # 频域中的逐元素乘积: Z = X.*Y;
    Z_fft = X_fft_padded_A * Y_fft

    # 逆 FFT 得到卷积: z = ifft(Z);
    z_conv = ifft(Z_fft)

    # 卷积中与点积相关的部分
    # MATLAB: z(m:n), Python: z_conv[m-1:n_original_A] 因为 MATLAB 是1-索引的
    dot_products = z_conv[m - 1 : n_original_A].real  # 取实部

    # 计算 y 的统计量 (query_norm 已经标准化, 所以 sumy 约等于 0, sumy2 约等于 m)
    # MATLAB 的 std(y,1) 使用 N, 所以标准化后 sumy2 实际上是 m。
    sumy2 = m  # sum(query_norm**2) 近似为 m

    # 距离计算:
    # MATLAB 公式: dist = (sumx2 - 2*sumx.*meanx + m*(meanx.^2))./sigmax2 - 2*(z(m:n) - sumy.*meanx)./sigmax + sumy2;
    # `y` 是标准化的查询 `query_norm`，其 `sumy` (均值) 约等于 0。
    # 所以，公式近似为: dist_approx = (sum_A2 - 2*sum_A.*mean_A + m*(mean_A**2))./sig_A2_biased - 2*dot_products./sig_A_biased + sumy2;
    # 第一项 (sum_A2 - 2*sum_A.*mean_A + m*(mean_A**2)) 是 m * var_A_biased (即 m * sig_A2_biased)。
    # 所以，dist_approx = (m * sig_A2_biased)./sig_A2_biased - 2*dot_products./sig_A_biased + m;
    # dist_approx = 2*m - 2*dot_products./sig_A_biased;
    # 这等于 2*m*(1 - (dot_products / (m * sig_A_biased)))。
    # 如果 dot_products 是 sum(A_sub_i * query_i)，那么 dot_products / (m * sig_A_biased) 就是相关系数。
    # 这里的 `dot_products` 来自 ifft(fft(A_padded)*fft(query_norm_reversed_padded))，是互相关。
    # 对于 z-标准化序列，欧氏距离 D = sqrt(2*m*(1-correlation_coefficient))。

    # MATLAB 代码中的 `dist` 变量在 `sqrt(dist)` 之前实际上是 `distance_squared`。
    # 它似乎直接计算 z-标准化查询与 A 的 z-标准化子序列之间的平方欧氏距离。
    # D^2 = sum((Q_norm_i - T_norm_i)^2)
    #     = sum(Q_norm_i^2) + sum(T_norm_i^2) - 2 * sum(Q_norm_i * T_norm_i)
    # sum(Q_norm_i^2) = m (因为查询已标准化)
    # sum(T_norm_i^2) = m (因为 A 的子序列通过 mean_A, sig_A 实际上也标准化了)
    # sum(Q_norm_i * T_norm_i) = 互相关结果

    # 我们假设 MATLAB 的 `dist` 公式对于 z-标准化序列的 D^2 是正确的。
    # `sumy` (标准化查询的均值) 效应上为0。
    # 第一项 `(sum_A2 - 2*sum_A.*mean_A + m*(mean_A**2))./sig_A2_biased` 等于 `m`。
    dist_sq = m - 2 * dot_products / sig_A_biased + m
    dist_sq = np.maximum(dist_sq, 0)  # 在 sqrt 前确保非负
    distances = np.sqrt(dist_sq)

    return distances


def time_series_self_join_fast_matlab(A, subsequence_length):
    """
    对应 MATLAB 中的 Time_series_Self_Join_Fast。
    计算 Matrix Profile 和 Matrix Profile Index。
    MATLAB 代码的循环 `for i = 1:MatrixProfileLength` 和更新逻辑
    `updatePos = distanceProfile < MatrixProfile;` 表明是完整计算，
    而不是像纯 STAMP 那样的随机化。
    `pickedIdx = randperm(MatrixProfileLength)` 用于选择 *查询* 子序列，
    但其距离轮廓是针对 *所有* 其他子序列计算的。
    为了确定性行为和匹配标准 MP 计算（如MATLAB代码结构所示），我们按顺序迭代。
    """
    n_A = len(A)
    if subsequence_length > n_A / 2:
        raise ValueError("时间序列相对于子序列长度太短。")
    if subsequence_length < 4:
        raise ValueError("子序列长度必须至少为4。")

    if not isinstance(A, np.ndarray):
        A = np.array(A)
    if A.ndim > 1 and A.shape[1] == 1:
        A = A.flatten()  # 确保为1D数组
    elif A.ndim > 1 and A.shape[0] == 1:
        A = A.flatten()
    if A.ndim > 1:
        raise ValueError("输入 A 必须是1D时间序列。")

    matrix_profile_len = n_A - subsequence_length + 1
    matrix_profile = np.full(matrix_profile_len, np.inf)
    mp_index = np.zeros(matrix_profile_len, dtype=int)

    # A 的子序列的预计算
    (
        X_fft_padded_A,
        n_padded_A_original,
        sum_A2,
        sum_A,
        mean_A,
        sig_A2_biased,
        sig_A_biased,
    ) = fast_find_nn_pre_matlab(A, subsequence_length)

    # 平凡匹配的排除区域
    # MATLAB: exclusionZone = round(SubsequenceLength/4);
    exclusion_zone = int(round(subsequence_length * EXCLUSION_ZONE_RATIO))

    for i in range(matrix_profile_len):
        query_idx = i  # 当前查询子序列的索引
        current_query_subsequence = A[query_idx : query_idx + subsequence_length]

        distance_profile = fast_find_nn_matlab(
            X_fft_padded_A,
            current_query_subsequence,
            n_A,
            subsequence_length,
            sum_A2,
            sum_A,
            mean_A,
            sig_A2_biased,
            sig_A_biased,
        )

        # 应用排除区域 (围绕 query_idx)
        # distance_profile 与 A 的子序列对齐
        zone_start = max(0, query_idx - exclusion_zone)
        zone_end = min(
            matrix_profile_len, query_idx + exclusion_zone + 1
        )  # Python 切片 +1
        distance_profile[zone_start:zone_end] = np.inf

        # MATLAB 代码的更新逻辑:
        # if i == 1 (first picked_idx)
        #    MatrixProfile = distanceProfile; MPindex(:) = idx;
        #    [MatrixProfile(idx), MPindex(idx)] = min(distanceProfile); % 此行是关键
        # else
        #    updatePos = distanceProfile < MatrixProfile;
        #    MPindex(updatePos) = idx; MatrixProfile(updatePos) = distanceProfile(updatePos);
        #    [MatrixProfile(idx), MPindex(idx)] = min(distanceProfile); % 此处也有
        # 这意味着对于每个查询 `idx` (在我们的Python实现中是 `i`)：
        # 1. 我们找到它自己的最近邻及其在 `distance_profile` 中的距离，并更新 `matrix_profile[i]`。
        # 2. 如果这个 `distance_profile` 为其他子序列提供了更好的候选者，我们也更新全局 `matrix_profile`。

        # 1. 更新 matrix_profile[i] 和 mp_index[i]
        #    直接赋值，因为 distance_profile 是针对当前 query_idx (i) 计算的。
        matrix_profile[i] = np.min(distance_profile)
        mp_index[i] = np.argmin(distance_profile)

        # 2. 如果 A[i:i+m] 对它们来说是更好的最近邻，则更新 MatrixProfile 中的其他条目
        #    这对应 MATLAB 中的 `updatePos` 逻辑。
        #    distance_profile[j] 是 dist(A[j:j+m], A[i:i+m])
        #    matrix_profile[j] 是 A[j:j+m] 当前的最小距离
        #    通过向量化操作替换原来的 for j 循环
        update_indices = distance_profile < matrix_profile
        matrix_profile[update_indices] = distance_profile[update_indices]
        mp_index[update_indices] = (
            i  # A[i:i+m] 现在是 A[j:j+m] (j in update_indices) 的最近邻
        )

    # 如果存在 inf (例如，非常短的序列或大的排除区)，则替换为一个大数
    finite_vals = matrix_profile[np.isfinite(matrix_profile)]
    if np.any(np.isinf(matrix_profile)):
        replace_val = np.nanmax(finite_vals) if len(finite_vals) > 0 else 0
        matrix_profile[np.isinf(matrix_profile)] = replace_val

    return matrix_profile, mp_index


def segment_time_series_matlab(mp_index, subsequence_length):
    """
    对应 MATLAB 中的 SegmentTimeSeries。
    基于 Matrix Profile Index 计算 'crosscount'。
    """
    l_mp = len(mp_index)
    if l_mp == 0:
        return np.array([])

    # MATLAB: threshold = prctile(abs(MPindex - (1:l)'), 100);
    # 这个 threshold 的定义使得 `if abs_diff[i] <= threshold:` 条件总是为真。
    # 因此，可以移除这个条件判断，除非为了严格匹配 MATLAB 由于浮点不精确可能产生的边缘行为。
    # 为了简化和潜在的微小加速，我们移除它。
    # abs_diff = np.abs(mp_index - np.arange(l_mp))
    # threshold = np.max(abs_diff) if len(abs_diff) > 0 else 0

    nn_mark = np.zeros(l_mp, dtype=int)  # 使用整数类型，因为是计数

    # 向量化 nn_mark 的计算
    # 确保 mp_index 中的值是有效的索引 (0 到 l_mp-1)
    # 如果 mp_index 中的值可能超出范围，需要添加剪裁或检查
    # 假设 mp_index 是由 time_series_self_join_fast_matlab 正确生成的，其值在 [0, l_mp-1] 区间内
    indices1 = np.arange(l_mp)
    indices2 = mp_index.astype(int)  # 确保 mp_index 是整数类型用于索引

    small_indices = np.minimum(indices1, indices2)
    large_indices = np.maximum(indices1, indices2)

    # 使用 np.add.at 进行原地、无缓冲的增量操作，这对于重复索引是安全的
    np.add.at(nn_mark, small_indices, 1)
    # 对于 large_indices，它们也应该是 nn_mark 的有效索引，即 < l_mp。
    # 因为 indices1 和 indices2 都在 [0, l_mp-1] 内, 所以 large_indices 也在这个范围内。
    np.add.at(nn_mark, large_indices, -1)

    # 累积和得到 crosscount
    # crosscount 的长度是 l_mp - 1
    if l_mp <= 1:  # 如果 l_mp 是 0 或 1, crosscount 是空的
        return np.array([])

    crosscount = np.cumsum(nn_mark[:-1])  # nn_mark[:-1] 的长度是 l_mp-1

    return crosscount


def norm_crosscount_all_matlab(crosscount_input, subsequence_length):
    """
    对应 MATLAB 中的 Norm_crosscount_all。
    对 crosscount 进行归一化并设置排除区域。
    """
    if not isinstance(crosscount_input, np.ndarray):
        crosscount = np.array(crosscount_input, dtype=float)
    else:
        crosscount = crosscount_input.astype(float)  # 操作副本

    l_cc = len(crosscount)
    if l_cc == 0:
        return np.array([])

    for i in range(l_cc):
        ac = crosscount[i]
        # MATLAB: ic = 2*(i_matlab)*(l_matlab-i_matlab)/l_matlab; (使用1基索引 i_matlab)
        # Python (0基索引 i): i_matlab = i + 1
        i_matlab = i + 1  # 当前的 MATLAB 索引 (1到l_cc)
        l_matlab = l_cc  # MATLAB 术语中的长度

        # MATLAB: ic=2*(i)*(l-i)/l; crosscount(i)=min(ac/ic, 1);
        # 如果 MATLAB 索引 i 是 l (长度), 那么 l-i 是 0, 所以 ic 是 0。
        # `min(ac/0, 1)`。MATLAB 将 ac/0 处理为 Inf, 然后 min(Inf,1)=1。
        # Python `finite/0` 是 `inf`。 `0/0` 是 `nan`.

        if l_matlab == 0:  # 不应发生，因为 l_cc > 0 已检查
            # 此情况由于上面的 l_cc == 0 检查，理论上不应到达
            ic = 1.0  # 默认为1.0以防止除以零，尽管不可达。
            crosscount[i] = min(
                ac / ic if ic != 0 else np.inf if ac != 0 else np.nan, 1.0
            )
            continue

        ic_numerator = 2.0 * float(i_matlab) * float(l_matlab - i_matlab)

        if ic_numerator == 0:  # 发生在边界 i_matlab=l_matlab (即 i = l_cc-1)
            if ac == 0:  # 0/0 情况
                crosscount[i] = np.nan  # MATLAB: min(NaN,1) -> NaN
            else:  # 非零/0 情况
                crosscount[i] = 1.0  # MATLAB: min(Inf,1) -> 1.0
            continue
        # else ic_numerator 不为零

        ic = ic_numerator / float(l_matlab)

        if ic == 0:  # 如果 ic_numerator 非零且 l_matlab 是有限非零数，则理论上不应发生
            # 这意味着如果我们到达这里，ac 也为0才能得到非inf/nan的结果。
            if ac == 0:
                crosscount[i] = np.nan  # 0/0
            else:
                crosscount[i] = 1.0  # X/0
            continue

        val = ac / ic
        if np.isnan(
            val
        ):  # 处理 ac 和 ic 导致的 0/0 情况 (例如 ic 非常小导致有效的 0/0)
            crosscount[i] = np.nan
        elif np.isinf(val) and val > 0:  # 处理 X/0 -> +Inf
            crosscount[i] = 1.0
        # 假设 ac 和 ic 是非负的, ac/ic 不会是 -Inf。
        else:  # 有限的非 NaN 结果
            crosscount[i] = min(val, 1.0)

    # 排除区域: zone = slWindow * 5;
    # MATLAB 使用 slWindow (subsequence_length)
    zone = subsequence_length * NORM_CROSSCOUNT_EXCLUSION_FACTOR

    # 确保 zone 不超过数组边界
    # MATLAB 将 1:zone 设置为 1。
    actual_zone_start = min(zone, l_cc)  # 开头区域
    if actual_zone_start > 0:  # 如果 zone 或 l_cc 为 0，确保切片有效
        crosscount[:actual_zone_start] = 1.0

    # MATLAB 将 l-zone:l 设置为 1 (1-based), 这是 zone+1 个元素。
    # Python 等效: 设置末尾的 zone+1 个元素。
    # 切片的起始索引 (0-based): max(0, l_cc - (zone + 1))
    # 切片的结束索引 (0-based, exclusive): l_cc
    num_elements_at_end = zone + 1
    actual_zone_end_slice_start = max(0, l_cc - num_elements_at_end)
    if actual_zone_end_slice_start < l_cc:  # 确保切片有效且包含元素
        crosscount[actual_zone_end_slice_start:] = 1.0

    return crosscount


def run_matlab_segmentation(ts_input, subsequence_length):
    """
    主函数，模拟 MATLAB 的 RunSegmentation。
    输入:
        ts_input: 1D 时间序列 (list, numpy array, 或 pandas Series)
        subsequence_length: 整数, 子序列长度
    输出:
        final_crosscount: 归一化后的 crosscount 数组，与 MATLAB 输出类似
    """
    if isinstance(ts_input, pd.Series):
        ts = ts_input.values
    elif isinstance(ts_input, list):
        ts = np.array(ts_input)
    elif isinstance(ts_input, np.ndarray):
        ts = ts_input
    else:
        raise TypeError("ts_input 必须是 list, numpy array, 或 pandas Series。")

    if ts.ndim > 1:
        ts = ts.squeeze()  # 如果有，移除多余维度
    if ts.ndim == 0:  # 处理标量输入情况
        raise ValueError("输入时间序列必须是1D且长度 >= subsequence_length。")
    if ts.ndim > 1:
        raise ValueError("输入时间序列必须是1D。")

    # MATLAB 的 Time_series_Self_Join_Fast 在 SubsequenceLength > length(A)/2 或 < 4 时会报错。
    # 我们让 time_series_self_join_fast_matlab 处理这些。
    # 这里只确保基本长度。如果 mp_index 为空，segment_time_series_matlab 返回空。
    # 如果 norm_crosscount_all_matlab 得到空，它返回空。
    if len(ts) < subsequence_length:
        return np.array([])

    # MATLAB: [MatrixProfile, MPindex] = Time_series_Self_Join_Fast(ts, slWindow);
    _, mp_index = time_series_self_join_fast_matlab(ts, subsequence_length)

    # MATLAB: [crosscount] = SegmentTimeSeries(slWindow, MPindex);
    # 注意: MATLAB 中的 SegmentTimeSeries 接收 slWindow 和 MPindex。
    # 我们的 Python 版本接收 mp_index 和 subsequence_length。
    crosscount_raw = segment_time_series_matlab(mp_index, subsequence_length)

    # MATLAB: [crosscount] = Norm_crosscount_all(crosscount, slWindow);
    final_crosscount = norm_crosscount_all_matlab(crosscount_raw, subsequence_length)

    return final_crosscount


# --- 原来的 Python FLOSS 函数现在实际上已被类似 MATLAB 的函数取代 ---
# --- 如果需要，我们可以保留原始的 `floss_score` 作为一个单独的工具，或者移除它。 ---
# --- 对于此任务，我们假设用 MATLAB 的逻辑替换 FLOSS 逻辑。 ---


def floss_score(
    df_input,
    subsequence_length,
    find_peaks_on_crosscount=True,
    peak_distance_factor=3,
    num_minima_to_find: Optional[int] = None,  # 新增参数
):
    """
    将类似 MATLAB 的分割输出调整为与原始 floss_score 类似的格式。
    'score' 将是来自 MATLAB 逻辑的 final_crosscount。
    'is_change_point' 通过在 final_crosscount 上寻找局部最小值来派生。
    如果提供了 `num_minima_to_find`，则使用迭代方法查找固定数量的最小值，
    类似于 MATLAB 的 `flossScore.m` 中的 `findLocalMinimums`。
    否则，使用 `scipy.signal.find_peaks`。
    """
    if not isinstance(df_input, pd.DataFrame) and not isinstance(df_input, pd.Series):
        raise TypeError("输入必须是 pandas DataFrame 或 Series。")

    if isinstance(df_input, pd.DataFrame):
        if len(df_input.columns) > 1:
            print("警告: DataFrame 有多个列。仅处理第一列。")
        ts_values = df_input.iloc[:, 0].values
        ts_index = df_input.index
    else:  # pandas Series
        ts_values = df_input.values
        ts_index = df_input.index

    final_crosscount = run_matlab_segmentation(ts_values, subsequence_length)

    # 将 final_crosscount 与原始索引对齐:
    output_scores = np.full(len(ts_values), np.nan)
    start_index_for_scores = 0
    if len(final_crosscount) > 0:
        start_index_for_scores = subsequence_length - 1
        if start_index_for_scores < 0:
            start_index_for_scores = 0

        end_index_for_scores = start_index_for_scores + len(final_crosscount)
        if end_index_for_scores <= len(output_scores):
            output_scores[start_index_for_scores:end_index_for_scores] = (
                final_crosscount
            )
        elif len(final_crosscount) == len(
            output_scores
        ):  # 特殊情况如 subsequence_length = 1
            output_scores[:] = final_crosscount

    is_change_point = np.zeros(len(ts_values), dtype=int)
    minima_indices_in_final_crosscount = np.array([], dtype=int)

    if find_peaks_on_crosscount and len(final_crosscount) > 0:
        if num_minima_to_find is not None and num_minima_to_find > 0:
            # 使用新的迭代方法，如果指定了 num_minima_to_find
            exclusion_half_width = subsequence_length * peak_distance_factor
            # 确保 exclusion_half_width 是整数且非负，这已在辅助函数中处理

            minima_indices_in_final_crosscount, _ = (
                _find_local_minimums_iterative_matlab(
                    final_crosscount,
                    num_minima_to_find,
                    int(exclusion_half_width),  # 确保为整数传递
                )
            )
        else:
            # 使用 scipy.signal.find_peaks (原有逻辑)
            # MATLAB flossScore.m 使用 stepSize = 3, findLocalMinimums 的排除长度
            # 是 stepSize*subSequnceLength。这对应于 scipy_find_peaks 中的 `distance`。
            min_dist_between_minima = subsequence_length * peak_distance_factor
            if min_dist_between_minima < 1 and subsequence_length > 0:
                min_dist_between_minima = 1  # scipy_find_peaks 的 distance 必须至少为 1

            if min_dist_between_minima > 0:  # 仅当 distance 有效时寻峰
                # final_crosscount 中的 NaN需要在反转寻峰之前处理。
                # 将 NaN 替换为一个在反转信号中不会成为峰值的值 (例如，一个大的正数如 2.0,
                # 因为分数 <=1.0, 所以 -2.0 将小于其他反转后的分数)。
                crosscount_for_scipy_finding = np.nan_to_num(final_crosscount, nan=2.0)

                # 在处理后的 crosscount 的负值上寻找峰值，以找到局部最小值。
                indices, _ = scipy_find_peaks(
                    -crosscount_for_scipy_finding,
                    distance=min_dist_between_minima,
                )
                minima_indices_in_final_crosscount = indices

        # 将这些峰值索引映射回原始时间序列索引
        if len(minima_indices_in_final_crosscount) > 0:
            mapped_minima_indices = (
                minima_indices_in_final_crosscount + start_index_for_scores
            )
            valid_mapped_minima = mapped_minima_indices[
                mapped_minima_indices < len(ts_values)
            ]
            is_change_point[valid_mapped_minima] = 1

    result_df = pd.DataFrame(
        {
            "matlab_cross_score": output_scores,
            "is_change_point": is_change_point,
        },
        index=ts_index,
    )

    return result_df


def _find_local_minimums_iterative_matlab(
    data_array, num_minima_to_find, exclusion_half_width
):
    """
    模拟 MATLAB 的 findLocalMinimums 函数，迭代地寻找局部最小值。
    参数:
        data_array (np.ndarray): 从中寻找最小值的数据数组 (例如 final_crosscount)。
        num_minima_to_find (int): 要寻找的最小值的数量。
        exclusion_half_width (int): 在找到的每个最小值周围排除区域的半宽度。
                                     (MATLAB findLocalMinimums 的 'length' 参数)
    返回:
        tuple (np.ndarray, np.ndarray): (min_indices, min_values)
                                        min_indices 是在 data_array 中的索引。
    """
    if not isinstance(data_array, np.ndarray):
        data_array = np.array(data_array)

    # 创建一个可修改的副本进行搜索，并将 NaN 替换为无穷大，这样它们不会被选为最小值
    search_data = np.array(data_array, dtype=float)
    search_data[np.isnan(search_data)] = np.inf

    if len(search_data) == 0 or num_minima_to_find <= 0:
        return np.array([], dtype=int), np.array([])  # 返回空的 minima 数组

    min_indices_list = []
    min_values_list = []

    # 确保 exclusion_half_width 是非负整数
    exclusion_half_width = max(0, int(exclusion_half_width))

    for _ in range(num_minima_to_find):
        try:
            # 在当前 search_data 中寻找全局最小值
            current_min_idx = np.argmin(search_data)
        except ValueError:
            # 如果 search_data 为空或只包含 inf/nan (理论上被上面的 len 和 nan 处理覆盖)
            break

        current_min_val = search_data[current_min_idx]

        if current_min_val == np.inf:
            # 如果找到的最小值是无穷大，意味着没有更多有效的（有限的）最小值可选
            break

        min_indices_list.append(current_min_idx)
        # 存储原始 data_array 中的值，而不是可能已被修改的 search_data 中的值（尽管此处它们应相同）
        min_values_list.append(data_array[current_min_idx])

        # 在 search_data 中应用排除区域，以防止在下次迭代中再次选择此区域内的点
        zone_start = max(0, current_min_idx - exclusion_half_width)
        # zone_end 是包含性的，所以 Python 切片需要 +1
        zone_end = min(len(search_data) - 1, current_min_idx + exclusion_half_width)
        search_data[zone_start : zone_end + 1] = np.inf

    return np.array(min_indices_list, dtype=int), np.array(min_values_list)
