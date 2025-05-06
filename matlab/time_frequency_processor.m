classdef time_frequency_processor < handle
    %TIME_FREQUENCY_PROCESSOR 时频数据处理类
    %   此类负责数据加载、滤波、频谱分析和切片处理等后端功能
    
    properties
        % 数据属性
        time            % 时间数组
        value           % 原始数值数组
        filtered_value  % 滤波后的数值数组
        fs              % 采样率
        
        % 滤波参数
        enable_filter = false  % 是否启用滤波
        filter_type = 1        % 滤波类型：1=均值降采样, 2=低通滤波
        filter_window = 5      % 滤波窗口大小/截止频率
        
        % 切片参数
        slice_duration    % 每个切片的持续时间（秒）
        overlap_ratio     % 重叠比例（0-1）
        slice_points      % 每个切片的采样点数
        step_points       % 每次移动的采样点数
        num_slices        % 切片总数
        
        % 频率分析设置
        freq_range = [0, 0.001]  % 频率范围 [Hz]
        
        % 瀑布图设置
        waterfall_history = []  % 存储瀑布图历史频谱数据
        waterfall_times = []    % 存储瀑布图对应的时间点
        waterfall_history_size = 20  % 瀑布图历史大小
    end
    
    methods
        function obj = time_frequency_processor()
            % 构造函数，初始化默认参数
        end
        
        function load_data(obj, filename)
            % 加载并解析数据文件
            [obj.time, obj.value] = obj.load_and_parse_data(filename);
            obj.filtered_value = obj.value;  % 初始时滤波值与原始值相同
            
            % 计算采样率
            obj.fs = 1/seconds(median(diff(obj.time)));
            
            % 初始化默认切片参数
            obj.set_default_slice_params();
        end
        
        function set_default_slice_params(obj)
            % 设置默认切片参数
            % 默认24小时，50%重叠
            obj.slice_duration = 24*60*60;  % 默认24小时
            obj.overlap_ratio = 0.5;        % 默认50%重叠
            
            % 计算切片参数
            obj.update_slice_params();
        end
        
        function update_slice_params(obj)
            % 更新切片相关参数
            obj.slice_points = round(obj.slice_duration * obj.fs);
            obj.step_points = round(obj.slice_points * (1 - obj.overlap_ratio));
            
            % 计算切片数量
            data_length = length(obj.value);
            obj.num_slices = obj.calculate_num_slices(data_length, obj.slice_points, obj.step_points);
        end
        
        function set_slice_params(obj, duration_seconds, overlap_ratio)
            % 设置切片参数
            obj.slice_duration = duration_seconds;
            obj.overlap_ratio = overlap_ratio;
            
            % 更新切片相关参数
            obj.update_slice_params();
            
            % 清空瀑布图历史
            obj.waterfall_history = [];
            obj.waterfall_times = [];
        end
        
        function apply_filter(obj)
            % 根据当前设置应用滤波
            if obj.enable_filter
                if obj.filter_type == 1
                    % 均值降采样
                    obj.filtered_value = obj.downsample_mean(obj.value, round(obj.filter_window));
                else
                    % 低通滤波 (巴特沃斯滤波器)
                    [b, a] = butter(4, obj.filter_window/(obj.fs/2), 'low');
                    obj.filtered_value = filtfilt(b, a, obj.value);
                end
            else
                % 不启用滤波时，恢复原始数据
                obj.filtered_value = obj.value;
            end
        end
        
        function set_filter_params(obj, enable, type, window)
            % 设置滤波参数
            obj.enable_filter = enable;
            obj.filter_type = type;
            obj.filter_window = window;
            
            % 应用新的滤波设置
            obj.apply_filter();
        end
        
        function [slice_data, freq_data] = get_slice_data(obj, slice_idx)
            % 获取指定切片的时域和频域数据
            % 计算当前切片的索引范围
            start_idx = (slice_idx-1) * obj.step_points + 1;
            end_idx = min(start_idx + obj.slice_points - 1, length(obj.value));
            
            if end_idx <= length(obj.value)
                % 提取切片时间和数据
                current_time = obj.time(start_idx:end_idx);
                
                % 根据滤波设置选择数据
                if obj.enable_filter
                    current_value = obj.filtered_value(start_idx:end_idx);
                else
                    current_value = obj.value(start_idx:end_idx);
                end
                
                % 构造时域数据结构
                slice_data.time = current_time;
                slice_data.value = current_value;
                slice_data.time_range_str = sprintf('%s 到 %s', ...
                    datestr(current_time(1), 'yyyy-mm-dd HH:MM:SS'), ...
                    datestr(current_time(end), 'yyyy-mm-dd HH:MM:SS'));
                
                % 计算频域数据
                freq_data = obj.calculate_frequency_data(current_value);
                
                % 更新瀑布图历史
                obj.update_waterfall_history(freq_data.P1_plot, current_time(1));
            else
                slice_data = [];
                freq_data = [];
            end
        end
        
        function update_waterfall_history(obj, spectrum_data, time_point)
            % 更新瀑布图历史数据
            if isempty(obj.waterfall_history)
                obj.waterfall_history = zeros(1, length(spectrum_data));
                obj.waterfall_times = time_point;
            end
            
            % 添加新的频谱数据到瀑布图历史
            obj.waterfall_history = [obj.waterfall_history; spectrum_data'];
            obj.waterfall_times = [obj.waterfall_times; time_point];
            
            % 如果历史数据超过设定的大小，则移除最早的数据
            if size(obj.waterfall_history, 1) > obj.waterfall_history_size
                obj.waterfall_history = obj.waterfall_history(end-obj.waterfall_history_size+1:end, :);
                obj.waterfall_times = obj.waterfall_times(end-obj.waterfall_history_size+1:end);
            end
        end
        
        function set_waterfall_history_size(obj, size)
            % 设置瀑布图历史大小
            obj.waterfall_history_size = size;
            
            % 调整历史数据大小
            if ~isempty(obj.waterfall_history)
                if size(obj.waterfall_history, 1) > obj.waterfall_history_size
                    % 如果历史数据过多，只保留最新的
                    obj.waterfall_history = obj.waterfall_history(end-obj.waterfall_history_size+1:end, :);
                    obj.waterfall_times = obj.waterfall_times(end-obj.waterfall_history_size+1:end);
                end
            end
        end
        
        function waterfall_data = get_waterfall_data(obj)
            % 获取瀑布图数据
            waterfall_data.history = obj.waterfall_history;
            waterfall_data.times = obj.waterfall_times;
            waterfall_data.size = size(obj.waterfall_history, 1);
        end
        
        function set_freq_range(obj, range)
            % 设置频率范围
            obj.freq_range = range;
        end
        
        function times = get_slice_start_times(obj)
            % 获取所有切片的开始时间（用于日期选择）
            times = obj.calculate_slice_start_times(obj.time, obj.num_slices, obj.step_points);
        end
        
        function idx = find_closest_slice(obj, target_time)
            % 找到最接近指定时间点的切片索引
            idx = obj.find_closest_slice_idx(target_time, obj.time, obj.step_points, obj.num_slices);
        end
    end
    
    methods (Access = private)
        function [time, value] = load_and_parse_data(~, filename)
            % 加载并解析数据文件
            % 设置导入选项
            opts = delimitedTextImportOptions('NumVariables', 2);
            opts.VariableNames = {'Time', 'Value'};
            opts.VariableTypes = {'string', 'double'};
            opts.Delimiter = ',';
            opts.DataLines = [2, inf]; % 从第2行开始读取
            
            % 读取数据
            T = readtable(filename, opts);
            
            % 解析时间字符串为datetime对象
            time_str = T.Time;
            time = datetime(time_str, 'InputFormat', 'yyyy-MM-dd HH:mm:ss.SSS');
            
            % 提取值
            value = T.Value;
        end
        
        function freq_data = calculate_frequency_data(obj, current_value)
            % 计算频域数据
            % 去除直流分量
            current_value = current_value - mean(current_value);
            
            % 获取当前切片长度
            N = length(current_value);
            
            % 实现ZoomFFT - 放大低频区域
            % 1. 生成时间向量
            t_vec = (0:N-1)' / obj.fs;
            
            % 2. 计算中心频率
            center_freq = (obj.freq_range(1) + obj.freq_range(2)) / 2;
            
            % 3. 将信号搬移到中心频率
            shifted_signal = current_value .* exp(-1i * 2 * pi * center_freq * t_vec);
            
            % 4. 对搬移信号进行FFT
            N_fft = 2^nextpow2(N)*8; % 增加FFT点数提高分辨率
            Y = fft(shifted_signal, N_fft);
            
            % 5. 计算新频率向量（放大后的频率区间）
            freq_zoom = obj.fs/N_fft * (-(N_fft/2):(N_fft/2-1)) + center_freq;
            
            % 6. 重新排列结果以获得正确顺序
            Y = fftshift(Y);
            
            % 7. 计算幅值谱
            P_zoom = abs(Y)/N;
            
            % 8. 选择感兴趣的频率范围
            idx = (freq_zoom >= obj.freq_range(1)) & (freq_zoom <= obj.freq_range(2));
            f_plot = freq_zoom(idx);
            P1_plot = P_zoom(idx);
            
            % 9. 避免对数坐标下的零值问题
            f_plot = max(f_plot, eps); % 确保没有零频率
            P1_plot = max(P1_plot, eps); % 确保没有零幅值
            
            % 返回频域数据结构
            freq_data.f_plot = f_plot;
            freq_data.P1_plot = P1_plot;
        end
        
        function y = downsample_mean(~, x, window)
            % 均值降采样函数
            % 对信号x进行窗口大小为window的均值降采样
            n = length(x);
            % 计算降采样后的长度
            m = floor(n / window);
            % 初始化输出
            y = zeros(m, 1);
            
            % 对每个窗口计算均值
            for i = 1:m
                start_idx = (i-1)*window + 1;
                end_idx = min(start_idx + window - 1, n);
                y(i) = mean(x(start_idx:end_idx));
            end
            
            % 插值回原始长度
            t_orig = 1:n;
            t_down = linspace(1, n, m);
            y = interp1(t_down, y, t_orig, 'linear', 'extrap');
        end
        
        function num = calculate_num_slices(~, data_len, slice_pts, step_pts)
            % 计算切片数量
            num = floor((data_len - slice_pts) / step_pts) + 1;
            if num < 1
                num = 1;
            end
        end
        
        function times = calculate_slice_start_times(~, time_data, num_slices, step_pts)
            % 计算切片开始时间
            times = cell(num_slices, 1);
            for i = 1:num_slices
                start_idx = (i-1) * step_pts + 1;
                if start_idx <= length(time_data)
                    times{i} = datestr(time_data(start_idx), 'yyyy-mm-dd');
                else
                    break;
                end
            end
            times = unique(times);
        end
        
        function idx = find_closest_slice_idx(~, target_time, time_data, step_pts, num_slices)
            % 找到最接近指定时间点的切片索引
            idx = 1;
            min_diff = inf;
            
            for i = 1:min(num_slices, length(time_data))
                start_idx = (i-1) * step_pts + 1;
                if start_idx > length(time_data)
                    break;
                end
                
                current_diff = abs(seconds(time_data(start_idx) - target_time));
                if current_diff < min_diff
                    min_diff = current_diff;
                    idx = i;
                end
            end
        end
    end
end