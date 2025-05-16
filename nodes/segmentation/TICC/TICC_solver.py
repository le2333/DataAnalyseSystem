import numpy as np
import math, time, collections, os, errno, sys, code, random
# import matplotlib # Removed plotting
# matplotlib.use('Agg')
# import matplotlib.pyplot as plt # Removed plotting
from sklearn import mixture
from sklearn.cluster import KMeans
import pandas as pd
from multiprocessing import Pool

from .TICC_helper import *
from .admm_solver import ADMMSolver



class TICC:
    def __init__(self, window_size=10, number_of_clusters=5, lambda_parameter=11e-2,
                 beta=400, maxIters=1000, threshold=2e-5, # Removed write_out_file, prefix_string
                 num_proc=1, compute_BIC=False, cluster_reassignment=20, biased=False):
        """
        Parameters:
            - window_size: size of the sliding window
            - number_of_clusters: number of clusters
            - lambda_parameter: sparsity parameter
            - switch_penalty: temporal consistency parameter
            - maxIters: number of iterations
            - threshold: convergence threshold
            - num_proc: number of processes for parallel computation
            - compute_BIC: (bool) whether to compute BIC
            - cluster_reassignment: number of points to reassign to a 0 cluster
            - biased: Using the biased or the unbiased covariance
        """
        self.window_size = window_size
        self.number_of_clusters = number_of_clusters
        self.lambda_parameter = lambda_parameter
        self.switch_penalty = beta
        self.maxIters = maxIters
        self.threshold = threshold
        # self.write_out_file = write_out_file # Removed
        # self.prefix_string = prefix_string # Removed
        self.num_proc = num_proc
        self.compute_BIC = compute_BIC
        self.cluster_reassignment = cluster_reassignment
        self.num_blocks = self.window_size + 1
        self.biased = biased
        pd.set_option('display.max_columns', 500)
        np.set_printoptions(formatter={'float': lambda x: "{0:0.4f}".format(x)})
        np.random.seed(102)
        self.original_data = None
        self.input_type = None # Store input type (df or np)

    def fit(self, input_data):
        """
        Main method for TICC solver.
        Parameters:
            - input_data: 只能是pandas DataFrame或numpy数组
        Returns:
            - DataFrame (if input_data is DataFrame) or NumPy array (if input_data is ndarray) containing cluster assignments.
            - Dictionary containing the inverse covariance matrix for each cluster.
            - BIC score (if compute_BIC is True).
        """
        assert self.maxIters > 0  # must have at least one iteration
        self.log_parameters()

        # Get data into proper format
        times_series_arr, time_series_rows_size, time_series_col_size = self.load_data(input_data)

        ############
        # The basic folder to be created
        # str_NULL = self.prepare_out_directory()

        # Train test split
        training_indices = getTrainTestSplit(time_series_rows_size, self.num_blocks,
                                             self.window_size)  # indices of the training samples
        num_train_points = len(training_indices)

        # Stack the training data
        complete_D_train = self.stack_training_data(times_series_arr, time_series_col_size, num_train_points,
                                                    training_indices)

        # Initialization
        # Gaussian Mixture
        gmm = mixture.GaussianMixture(n_components=self.number_of_clusters, covariance_type="full")
        gmm.fit(complete_D_train)
        clustered_points = gmm.predict(complete_D_train)
        gmm_clustered_pts = clustered_points + 0
        # K-means
        kmeans = KMeans(n_clusters=self.number_of_clusters, random_state=0).fit(complete_D_train)
        clustered_points_kmeans = kmeans.labels_  # todo, is there a difference between these two?
        kmeans_clustered_pts = kmeans.labels_

        train_cluster_inverse = {}
        log_det_values = {}  # log dets of the thetas
        computed_covariance = {}
        cluster_mean_info = {}
        cluster_mean_stacked_info = {}
        old_clustered_points = None  # points from last iteration

        empirical_covariances = {}

        # PERFORM TRAINING ITERATIONS
        pool = Pool(processes=self.num_proc)  # multi-threading
        for iters in range(self.maxIters):
            print("\n\n\nITERATION ###", iters)
            # Get the train and test points
            train_clusters_arr = collections.defaultdict(list)  # {cluster: [point indices]}
            for point, cluster_num in enumerate(clustered_points):
                train_clusters_arr[cluster_num].append(point)

            len_train_clusters = {k: len(train_clusters_arr[k]) for k in range(self.number_of_clusters)}

            # train_clusters holds the indices in complete_D_train
            # for each of the clusters
            opt_res = self.train_clusters(cluster_mean_info, cluster_mean_stacked_info, complete_D_train,
                                          empirical_covariances, len_train_clusters, time_series_col_size, pool,
                                          train_clusters_arr)

            self.optimize_clusters(computed_covariance, len_train_clusters, log_det_values, opt_res,
                                   train_cluster_inverse)

            # update old computed covariance
            old_computed_covariance = computed_covariance

            print("UPDATED THE OLD COVARIANCE")

            self.trained_model = {'cluster_mean_info': cluster_mean_info,
                                 'computed_covariance': computed_covariance,
                                 'cluster_mean_stacked_info': cluster_mean_stacked_info,
                                 'complete_D_train': complete_D_train,
                                 'time_series_col_size': time_series_col_size}
            clustered_points = self.predict_clusters()

            # recalculate lengths
            new_train_clusters = collections.defaultdict(list) # {cluster: [point indices]}
            for point, cluster in enumerate(clustered_points):
                new_train_clusters[cluster].append(point)

            len_new_train_clusters = {k: len(new_train_clusters[k]) for k in range(self.number_of_clusters)}

            before_empty_cluster_assign = clustered_points.copy()



            if iters != 0:
                cluster_norms = [(np.linalg.norm(old_computed_covariance[self.number_of_clusters, i]), i) for i in
                                 range(self.number_of_clusters)]
                norms_sorted = sorted(cluster_norms, reverse=True)
                # clusters that are not 0 as sorted by norm
                valid_clusters = [cp[1] for cp in norms_sorted if len_new_train_clusters[cp[1]] != 0]

                # Add a point to the empty clusters
                # assuming more non empty clusters than empty ones
                counter = 0
                for cluster_num in range(self.number_of_clusters):
                    if len_new_train_clusters[cluster_num] == 0:
                        cluster_selected = valid_clusters[counter]  # a cluster that is not len 0
                        counter = (counter + 1) % len(valid_clusters)
                        print("cluster that is zero is:", cluster_num, "selected cluster instead is:", cluster_selected)
                        start_point = np.random.choice(
                            new_train_clusters[cluster_selected])  # random point number from that cluster
                        for i in range(0, self.cluster_reassignment):
                            # put cluster_reassignment points from point_num in this cluster
                            point_to_move = start_point + i
                            if point_to_move >= len(clustered_points):
                                break
                            clustered_points[point_to_move] = cluster_num
                            computed_covariance[self.number_of_clusters, cluster_num] = old_computed_covariance[
                                self.number_of_clusters, cluster_selected]
                            cluster_mean_stacked_info[self.number_of_clusters, cluster_num] = complete_D_train[
                                                                                              point_to_move, :]
                            cluster_mean_info[self.number_of_clusters, cluster_num] \
                                = complete_D_train[point_to_move, :][
                                  (self.window_size - 1) * time_series_col_size:self.window_size * time_series_col_size]

            for cluster_num in range(self.number_of_clusters):
                print("length of cluster #", cluster_num, "-------->", sum([x == cluster_num for x in clustered_points]))

            # self.write_plot(clustered_points, str_NULL, training_indices) # Removed plotting

            # TEST SETS STUFF
            # LLE + swtiching_penalty
            # Segment length
            # Create the F1 score from the graphs from k-means and GMM
            # # Get the train and test points
            # train_confusion_matrix_EM = compute_confusion_matrix(self.number_of_clusters, clustered_points,
            #                                                      training_indices)
            # train_confusion_matrix_GMM = compute_confusion_matrix(self.number_of_clusters, gmm_clustered_pts,
            #                                                       training_indices)
            # train_confusion_matrix_kmeans = compute_confusion_matrix(self.number_of_clusters, kmeans_clustered_pts,
            #                                                          training_indices)
            ###compute the matchings
            # matching_EM, matching_GMM, matching_Kmeans = self.compute_matches(train_confusion_matrix_EM,
            #                                                                   train_confusion_matrix_GMM,
            #                                                                   train_confusion_matrix_kmeans)

            print("\n\n\n")

            if np.array_equal(old_clustered_points, clustered_points):
                print("\n\n\n\nCONVERGED!!! BREAKING EARLY!!!")
                break
            old_clustered_points = before_empty_cluster_assign
            # end of training
        if pool is not None:
            pool.close()
            pool.join()
        train_confusion_matrix_EM = compute_confusion_matrix(self.number_of_clusters, clustered_points, # Removed performance evaluation
                                                             training_indices)
        train_confusion_matrix_GMM = compute_confusion_matrix(self.number_of_clusters, gmm_clustered_pts,
                                                              training_indices)
        train_confusion_matrix_kmeans = compute_confusion_matrix(self.number_of_clusters, clustered_points_kmeans,
                                                                 training_indices)

        self.compute_f_score(matching_EM, matching_GMM, matching_Kmeans, train_confusion_matrix_EM, # Removed performance evaluation
                             train_confusion_matrix_GMM, train_confusion_matrix_kmeans)

        # 保存聚类结果
        self.cluster_assignments = np.zeros(time_series_rows_size)
        for i in range(len(clustered_points)):
            self.cluster_assignments[training_indices[i]] = clustered_points[i]

        # 根据输入类型决定输出格式
        if self.input_type == 'df':
            result = self.to_dataframe(clustered_points, training_indices)
        else: # self.input_type == 'np'
            result = self.cluster_assignments # Return raw numpy array

        if self.compute_BIC:
            bic = computeBIC(self.number_of_clusters, time_series_rows_size, clustered_points, train_cluster_inverse,
                             empirical_covariances)
            return result, train_cluster_inverse, bic

        return result, train_cluster_inverse

    def to_dataframe(self, clustered_points, training_indices):
        """
        将聚类结果转换为DataFrame格式
        """
        if self.original_data is None:
            # 如果没有保存原始数据，创建一个简单的输出
            result = pd.DataFrame({
                'index': training_indices[:len(clustered_points)],
                'cluster': clustered_points
            })
            return result
        else:
            # 如果有原始DataFrame，添加聚类结果作为新列
            result = self.original_data.copy()
            result['cluster'] = pd.Series(self.cluster_assignments, index=result.index)
            return result

    def smoothen_clusters(self, cluster_mean_info, computed_covariance,
                          cluster_mean_stacked_info, complete_D_train, n):
        clustered_points_len = len(complete_D_train)
        inv_cov_dict = {}  # cluster to inv_cov
        log_det_dict = {}  # cluster to log_det
        for cluster in range(self.number_of_clusters):
            cov_matrix = computed_covariance[self.number_of_clusters, cluster][0:(self.num_blocks - 1) * n,
                         0:(self.num_blocks - 1) * n]
            inv_cov_matrix = np.linalg.inv(cov_matrix)
            log_det_cov = np.log(np.linalg.det(cov_matrix))  # log(det(sigma2|1))
            inv_cov_dict[cluster] = inv_cov_matrix
            log_det_dict[cluster] = log_det_cov
        # For each point compute the LLE
        print("beginning the smoothening ALGORITHM")
        LLE_all_points_clusters = np.zeros([clustered_points_len, self.number_of_clusters])
        for point in range(clustered_points_len):
            if point + self.window_size - 1 < complete_D_train.shape[0]:
                for cluster in range(self.number_of_clusters):
                    cluster_mean = cluster_mean_info[self.number_of_clusters, cluster]
                    cluster_mean_stacked = cluster_mean_stacked_info[self.number_of_clusters, cluster]
                    x = complete_D_train[point, :] - cluster_mean_stacked[0:(self.num_blocks - 1) * n]
                    inv_cov_matrix = inv_cov_dict[cluster]
                    log_det_cov = log_det_dict[cluster]
                    lle = np.dot(x.reshape([1, (self.num_blocks - 1) * n]),
                                 np.dot(inv_cov_matrix, x.reshape([n * (self.num_blocks - 1), 1]))) + log_det_cov
                    LLE_all_points_clusters[point, cluster] = lle

        return LLE_all_points_clusters

    def optimize_clusters(self, computed_covariance, len_train_clusters, log_det_values, optRes, train_cluster_inverse):
        for cluster in range(self.number_of_clusters):
            if optRes[cluster] == None:
                continue
            val = optRes[cluster].get()
            print("OPTIMIZATION for Cluster #", cluster, "DONE!!!")
            # THIS IS THE SOLUTION
            S_est = upperToFull(val, 0)
            X2 = S_est
            u, _ = np.linalg.eig(S_est)
            cov_out = np.linalg.inv(X2)

            # Store the log-det, covariance, inverse-covariance, cluster means, stacked means
            log_det_values[self.number_of_clusters, cluster] = np.log(np.linalg.det(cov_out))
            computed_covariance[self.number_of_clusters, cluster] = cov_out
            train_cluster_inverse[cluster] = X2
        for cluster in range(self.number_of_clusters):
            print("length of the cluster ", cluster, "------>", len_train_clusters[cluster])

    def train_clusters(self, cluster_mean_info, cluster_mean_stacked_info, complete_D_train, empirical_covariances,
                       len_train_clusters, n, pool, train_clusters_arr):
        optRes = [None for i in range(self.number_of_clusters)]
        for cluster in range(self.number_of_clusters):
            cluster_length = len_train_clusters[cluster]
            if cluster_length != 0:
                size_blocks = n
                indices = train_clusters_arr[cluster]
                D_train = np.zeros([cluster_length, self.window_size * n])
                for i in range(cluster_length):
                    point = indices[i]
                    D_train[i, :] = complete_D_train[point, :]

                cluster_mean_info[self.number_of_clusters, cluster] = np.mean(D_train, axis=0)[
                                                                      (
                                                                          self.window_size - 1) * n:self.window_size * n].reshape(
                    [1, n])
                cluster_mean_stacked_info[self.number_of_clusters, cluster] = np.mean(D_train, axis=0)
                ##Fit a model - OPTIMIZATION
                probSize = self.window_size * size_blocks
                lamb = np.zeros((probSize, probSize)) + self.lambda_parameter
                S = np.cov(np.transpose(D_train), bias=self.biased)
                empirical_covariances[cluster] = S

                rho = 1
                solver = ADMMSolver(lamb, self.window_size, size_blocks, 1, S)
                # apply to process pool
                optRes[cluster] = pool.apply_async(solver, (1000, 1e-6, 1e-6, False,))
        return optRes

    def stack_training_data(self, Data, n, num_train_points, training_indices):
        complete_D_train = np.zeros([num_train_points, self.window_size * n])
        for i in range(num_train_points):
            for k in range(self.window_size):
                if i + k < num_train_points:
                    idx_k = training_indices[i + k]
                    complete_D_train[i][k * n:(k + 1) * n] = Data[idx_k][0:n]
        return complete_D_train

    def load_data(self, input_data):
        """
        加载数据，仅支持pandas DataFrame或numpy数组
        """
        if isinstance(input_data, pd.DataFrame):
            self.input_type = 'df' # Store input type
            # 检查数据是否全部为数值型
            non_numeric_cols = input_data.select_dtypes(exclude=['number']).columns
            if len(non_numeric_cols) > 0:
                # 过滤掉非数值列
                print(f"警告：以下列包含非数值数据并将被过滤：{list(non_numeric_cols)}")
                numeric_df = input_data.select_dtypes(include=['number'])
                if numeric_df.empty:
                    raise ValueError("没有可用的数值列进行聚类")
                self.original_data = input_data
                Data = numeric_df.values
            else:
                self.original_data = input_data
                Data = input_data.values
            
            (m, n) = Data.shape  # m: 观测数, n: 观测向量大小
            print("完成从DataFrame获取数据，形状:", Data.shape)
        elif isinstance(input_data, np.ndarray):
            self.input_type = 'np' # Store input type
            # 处理numpy数组
            if not np.issubdtype(input_data.dtype, np.number):
                raise ValueError("numpy数组必须包含数值数据")
            
            Data = input_data
            (m, n) = Data.shape
            self.original_data = pd.DataFrame(Data)
            print("完成从numpy数组获取数据，形状:", Data.shape)
        else:
            raise TypeError("输入数据必须是pandas DataFrame或numpy数组")
        
        return Data, m, n

    def log_parameters(self):
        print("lam_sparse", self.lambda_parameter)
        print("switch_penalty", self.switch_penalty)
        print("num_cluster", self.number_of_clusters)
        print("num stacked", self.window_size)

    def predict_clusters(self, test_data = None):
        '''
        预测时间序列数据的聚类。如果聚类分割尚未优化，则此函数将作为迭代过程的一部分运行。

        Args:
            test_data: 用于预测聚类的数据。可以是numpy数组或pandas DataFrame。列是数据的维度，每行是不同的时间戳。

        Returns:
            预测的聚类向量，如果输入是DataFrame，则返回带有聚类结果的DataFrame
        '''
        # 处理不同类型的输入
        if test_data is not None:
            if isinstance(test_data, pd.DataFrame):
                # 检查数据是否全部为数值型
                non_numeric_cols = test_data.select_dtypes(exclude=['number']).columns
                if len(non_numeric_cols) > 0:
                    print(f"警告：以下列包含非数值数据并将被过滤：{list(non_numeric_cols)}")
                    test_data_numeric = test_data.select_dtypes(include=['number'])
                    if test_data_numeric.empty:
                        raise ValueError("没有可用的数值列进行聚类")
                    input_data = test_data_numeric.values
                else:
                    input_data = test_data.values
            elif isinstance(test_data, np.ndarray):
                if not np.issubdtype(test_data.dtype, np.number):
                    raise ValueError("numpy数组必须包含数值数据")
                input_data = test_data
            else:
                raise TypeError("输入必须是numpy数组或pandas DataFrame!")
        else:
            input_data = self.trained_model['complete_D_train']

        # SMOOTHENING
        lle_all_points_clusters = self.smoothen_clusters(self.trained_model['cluster_mean_info'],
                                                        self.trained_model['computed_covariance'],
                                                        self.trained_model['cluster_mean_stacked_info'],
                                                        input_data,
                                                        self.trained_model['time_series_col_size'])

        # Update cluster points - using NEW smoothening
        clustered_points = updateClusters(lle_all_points_clusters, switch_penalty=self.switch_penalty)

        # 如果输入是DataFrame，返回带有聚类结果的DataFrame
        if isinstance(test_data, pd.DataFrame):
            result_df = test_data.copy()
            result_df['cluster'] = clustered_points
            return result_df
        
        return clustered_points

