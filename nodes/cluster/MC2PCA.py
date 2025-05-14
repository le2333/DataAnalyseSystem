import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
from nodes.segmentation.slide_window import ts_window_segmentation, merge_segmented_ts


class MTS:
    def __init__(self, ts):
        self.ts = ts

    def cov_mat(self, centering=True):
        stdsc = StandardScaler()
        X = self.ts
        # 对于只有单个时间步的序列 (X.shape[0] == 1),
        # stdsc.fit_transform(X) 会将其所有元素变为0 (假设 with_mean=True).
        # 这会导致协方差矩阵为零。
        # Mc2PCA 算法通常期望序列有多个时间步。
        if X.shape[0] <= 1:
            # 或者返回一个特定的值/错误，或者允许但用户需注意
            # print(f"警告: 时间序列只有一个或零个时间步 (形状: {X.shape})。标准化后可能为零矩阵。")
            # 为了避免除以零的警告 (如果 with_std=True 且标准差为0)，可以特殊处理
            # 但根本问题是单点序列的协方差。
            # 目前保持原样，依赖后续逻辑或调用者确保序列长度。
            pass
        X = stdsc.fit_transform(X)
        self.ts = X
        return X.transpose() @ X


class CPCA:
    def __init__(self, epsilon=1e-5):
        self.cov = None
        self.epsilon = epsilon
        self.U = None
        self.V = None
        self.S = None

    def fit(self, listMTS):
        if len(listMTS) > 0:
            # 获取特征维度 P。假设所有 MTS 对象有相同的特征维度。
            # 第一次调用 cov_mat() 会标准化数据
            temp_cov_mat = listMTS[0].cov_mat()
            P = temp_cov_mat.shape[1]
            
            # 收集所有协方差矩阵
            # 注意：如果 listMTS[0] 在后续迭代中再次出现，其 ts 数据已经被标准化
            # 这是一个重要的副作用：fit会修改传入的listMTS中元素的数据
            cov_mat_list = [temp_cov_mat] # 第一个已经计算
            for i in range(1, len(listMTS)):
                cov_mat_list.append(listMTS[i].cov_mat())

            self.cov = sum(cov_mat_list) / len(cov_mat_list)
            # Add epsilon Id in order to ensure invertibility for SVD if needed,
            # though standard np.linalg.svd handles non-square and singular matrices.
            # The original code adds epsilon but then uses self.cov directly in svd.
            # For consistency with original, SVD is on self.cov.
            # cov_for_svd = self.cov + self.epsilon * np.eye(P) # This line was present but not used for SVD
            
            U, S, V = np.linalg.svd(self.cov)
            self.U = U
            self.S = S
            self.V = V

    def pred(self, listMTS, ncp):
        predicted = []
        if self.U is not None:
            # 假设 listMTS 中的 ts 数据已经被 fit 中的 cov_mat 调用标准化过
            predicted = [elem.ts @ self.U[:, :ncp] for elem in listMTS]
        return predicted

    def reconstitution_error(self, listMTS, ncp):
        mse = np.full(len(listMTS), np.inf)
        if self.U is not None:
            prediction = self.pred(listMTS, ncp)
            reconstit = [elem @ ((self.U)[:, :ncp].transpose()) for elem in prediction]
            # 确保 listMTS[i].ts 是与 prediction[i] 和 reconstit[i] 对齐的（即标准化过的）
            mse = [
                ((listMTS[i].ts - reconstit[i]) ** 2).sum()
                for i in range(len(prediction))
            ]
        return mse


class Mc2PCA:
    def __init__(self, K, ncp, itermax=1000, conv_crit=1e-5):
        """
        MC2PCA算法初始化

        参数:
        K: 聚类数量
        ncp: 主成分数量
        itermax: 最大迭代次数
        conv_crit: 收敛阈值
        """
        self.K = K
        self.N = None
        self.ncp = ncp
        self.iter_max = itermax
        self.converged = False
        self.CPCA_final = None
        self.conv_crit = conv_crit
        self.pred = None

    def fit(self, X_orig):
        """
        训练MC2PCA模型

        参数:
        X_orig: 列表，包含MTS对象。注意：此方法可能会修改MTS对象内部的 .ts 数据（通过标准化）。
                为了避免副作用，最好传入MTS对象的深拷贝列表。
                或者，确保调用者知晓数据会被修改。
                为了与原始代码行为一致，我们假设允许修改。

        返回:
        index_cluster: 聚类结果索引
        """
        if not X_orig:
            self.pred = np.array([], dtype=int)
            self.CPCA_final = []
            self.converged = True
            return self.pred

        X = X_orig 
        N = len(X)
        index_cluster = np.tile(np.arange(self.K), int(N / self.K) + 1)[:N]
        to_continue = True
        i = 0
        old_error = -np.inf

        while to_continue:
            MTS_by_cluster = [
                [X[idx] for idx in list(np.where(index_cluster == j)[0])]
                for j in range(self.K)
            ]

            CPCA_by_cluster = [CPCA() for _ in range(self.K)]

            for cluster_idx in range(self.K):
                if MTS_by_cluster[cluster_idx]:
                    CPCA_by_cluster[cluster_idx].fit(MTS_by_cluster[cluster_idx])
            res_list = []
            for cpca_model in CPCA_by_cluster:
                if cpca_model.U is not None:
                    res_list.append(cpca_model.reconstitution_error(X, self.ncp))
                else:
                    res_list.append(np.full(N, np.inf))
            if not res_list:
                break
            res = np.array(res_list)
            index_cluster_new = res.argmin(axis=0)
            if np.array_equal(index_cluster, index_cluster_new) and old_error != -np.inf :
                 pass
            index_cluster = index_cluster_new
            new_error = res.min(axis=0).sum()
            if old_error == -np.inf:
                error_change = np.inf
            else:
                error_change = abs(old_error - new_error)
            
            # 打印进度
            if i % 10 == 0 or i == self.iter_max - 1 or error_change <= self.conv_crit:
                print(f"MC2PCA 迭代 {i}: 当前误差={new_error:.6f}, 误差变化={error_change:.6f}")

            if error_change <= self.conv_crit:
                self.converged = True
                to_continue = False
            elif i >= self.iter_max -1:
                self.converged = False
                to_continue = False
            old_error = new_error
            i += 1
        self.CPCA_final = CPCA_by_cluster
        self.pred = index_cluster
        return index_cluster

    def precision(self, gt_cluster):
        """
        计算聚类准确率

        参数:
        gt_cluster: 真实标签

        返回:
        precision: 聚类准确率
        """
        if self.pred is None:
            # 模型未训练或未产生预测
            return 0.0 
        if len(self.pred) != len(gt_cluster):
            # 预测数量和真实标签数量不匹配
            # raise ValueError("预测标签和真实标签的长度不一致。")
            return 0.0 # Or handle error appropriately

        index_cluster = self.pred
        N = gt_cluster.shape[0]
        if N == 0:
            return 1.0 # Or 0.0, debatable for empty sets. Assume 1.0 if no data to misclassify.

        g = np.unique(gt_cluster)
        nb_g = g.shape[0]

        G = [np.where(gt_cluster == val)[0] for val in g] # Use actual unique values from gt_cluster
        C = [np.where(index_cluster == i)[0] for i in range(self.K)]

        # to handle case where a cluster is empty
        max_part = list()
        for j in range(self.K):
            l = list()
            if len(C[j]) == 0: # 空簇
                l.append(0) # 对准确率贡献为0，或者不计入prop_part
            else:
                for i_g in range(nb_g): # Iterate over ground truth clusters
                    l.append(np.intersect1d(G[i_g], C[j]).shape[0] / C[j].shape[0])
            
            if not l: # C[j]为空，导致l也为空 (e.g. if K=0 or some other edge case)
                 max_part.append(0)
            else:
                 max_part.append(np.max(l) if l else 0) # np.max of empty list causes error

        max_part = np.array(max_part)
        
        # prop_part: 每个预测簇的大小占比
        prop_part = np.array([C[j].shape[0] / N for j in range(self.K)])
        
        # 对于C[j]为空的情况，max_part[j]为0，prop_part[j]也为0，所以它们的点积贡献为0.
        return max_part.dot(prop_part)


def search_ncp(X, K, ncp_list, y_true):
    """
    搜索最佳主成分数量

    参数:
    X: 列表，包含MTS对象
    K: 聚类数量
    ncp_list: 要测试的主成分数量列表
    y_true: 真实标签

    返回:
    best_ncp: 最佳主成分数量
    pre: 对应的准确率
    """
    if not X:
        # Handle empty X if necessary, though Mc2PCA might handle it
        # Or raise error here
        return None, 0.0

    pres = np.zeros(len(ncp_list)) # Use len(ncp_list) instead of ncp_list.shape[0] for lists
    for i in range(len(ncp_list)):
        current_ncp = ncp_list[i]
        if not isinstance(current_ncp, (int, np.integer)) or current_ncp <= 0 : # ncp必须是正整数
            pres[i] = -1 # 表示无效ncp
            continue
        # 每次都创建新的模型实例
        # 注意：Mc2PCA.fit 会修改传入的 X 中 MTS 对象的 .ts 属性。
        # 如果希望每次 search_ncp 都从原始数据开始，需要传入 X 的深拷贝。
        # 为了与原始行为一致，这里不进行深拷贝。
        m = Mc2PCA(K, current_ncp)
        m.fit(X) # X (list of MTS objects) might be modified here.
        pres[i] = m.precision(y_true)
    
    if not np.any(pres > -1): # 所有ncp都无效或没有ncp_list
        return None, 0.0

    valid_pres_mask = pres > -1
    if not np.any(valid_pres_mask): # Should be caught by previous if, but for safety
        return None, 0.0

    pre = np.max(pres[valid_pres_mask]) # 只在有效精度中找最大值
    
    # Find the index corresponding to the max valid precision
    # np.argmax on pres[valid_pres_mask] gives index within that slice
    best_ncp_slice_idx = np.argmax(pres[valid_pres_mask])
    
    ncp_list_arr = np.array(ncp_list)
    valid_ncps = ncp_list_arr[valid_pres_mask]
    best_ncp = valid_ncps[best_ncp_slice_idx] if len(valid_ncps) > 0 else None
    
    return best_ncp, pre


def mc2pca_cluster_from_sequences(list_of_sequences, K, ncp, itermax=1000, conv_crit=1e-5):
    """
    使用MC2PCA对一个预先分割好的时间序列列表进行聚类。
    参数:
    list_of_sequences (list): 每个元素为有时间索引的df。
    K (int): 聚类数量。
    ncp (int): 主成分数量。
    itermax (int): 最大迭代次数。
    conv_crit (float): 收敛阈值。
    返回:
    tuple: (cluster_labels, model_instance)
    """
    list_of_numpy_sequences = [seg.values for seg in list_of_sequences]
    list_of_mts = [MTS(seq.copy()) for seq in list_of_numpy_sequences]
    model = Mc2PCA(K=K, ncp=ncp, itermax=itermax, conv_crit=conv_crit)
    cluster_labels = model.fit(list_of_mts)
    return cluster_labels, model


def mc2pca_clustering(df, window_size, step_size, K, ncp, itermax=1000, conv_crit=1e-5):
    """
    对时间索引的多维DataFrame按滑动窗口切片，并对每个窗口进行MC2PCA聚类。
    只对数值型特征聚类，输出为原始数据加cluster列。
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("输入 'df' 必须是 Pandas DataFrame。")
    
    numeric_df = df.select_dtypes(include=np.number)
    segments = ts_window_segmentation(numeric_df, window_size, step_size)
    final_cluster_labels, _ = mc2pca_cluster_from_sequences(
        list_of_sequences=segments, K=K, ncp=ncp,
            itermax=itermax, conv_crit=conv_crit
        )
    merged = merge_segmented_ts(segments)
    # 生成与merged行数一致的聚类标签
    cluster_col = []
    for label, seg in zip(final_cluster_labels, segments):
        cluster_col.extend([label] * len(seg))
    merged['cluster'] = cluster_col
    return merged
