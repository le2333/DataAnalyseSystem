function time_frequency_slice_animation()
%% 时频切片动画
% 本脚本对原始数据进行切片，并展示每个片段的时域和频域信息，支持手动播放控制

% 1. 加载数据
filename = '..\data\sat1\5_2025031706435044765.csv';
[time, value] = load_and_parse_data(filename);

% 2. 数据预处理参数
% 数据处理默认参数
enable_filter = false; % 默认不启用滤波
filter_type = 1; % 1: 均值降采样, 2: 低通滤波
filter_window = 5; % 默认滤波窗口大小/截止频率(Hz)
filtered_value = value; % 初始时与原始数据相同

% 3. 计算采样率
fs = 1/seconds(median(diff(time))); % 采样率（假设等间隔采样）

% 4. 设置切片参数的默认值和范围
default_duration = 24*60*60; % 默认24小时
min_duration = 1*60*60; % 最小1小时
max_duration = 7*24*60*60; % 最大7天
slice_duration = default_duration; % 每个切片的持续时间（秒）

default_overlap = 0.5; % 默认50%重叠
min_overlap = 0; % 最小0%重叠
max_overlap = 0.9; % 最大90%重叠
overlap_ratio = default_overlap; % 重叠比例

% 计算初始切片点数
slice_points = round(slice_duration * fs); % 每个切片的采样点数
step_points = round(slice_points * (1 - overlap_ratio)); % 每次移动的采样点数

% 频率分析设置
freq_range = [0, 0.001]; % Hz
center_freq = (freq_range(1) + freq_range(2)) / 2; % 中心频率

% 瀑布图设置
waterfall_history_size = 20; % 瀑布图显示的历史频谱数量
waterfall_history = []; % 存储瀑布图的历史频谱数据
waterfall_times = []; % 存储瀑布图对应的时间点

% 5. 计算切片数量和日期数组
data_length = length(value);
num_slices = calculate_num_slices(data_length, slice_points, step_points);

% 6. 预计算每个切片的开始时间，用于日期选择
slice_start_times = calculate_slice_start_times(time, num_slices, step_points);

% 7. 创建主图形窗口
main_fig = figure('Position', [100, 100, 1200, 800], 'Name', '时频切片分析', ...
    'NumberTitle', 'off', 'MenuBar', 'none', 'Resize', 'on');

% 8. 创建UI控件面板
control_panel = uipanel('Parent', main_fig, 'Position', [0, 0, 1, 0.2], ...
    'Title', '控制面板');

% 9. 定义全局状态变量
current_slice = 1;
current_time_point = time(1); % 记录当前时间点，用于参数变化时保持位置
is_playing = false;
pause_time = 0.2; % 默认暂停时间

% 10. 创建绘图区域
time_ax = subplot('Position', [0.1, 0.65, 0.8, 0.25]);
waterfall_ax = subplot('Position', [0.1, 0.25, 0.8, 0.3]);

% 创建UI子面板 - 播放控制
play_panel = uipanel('Parent', control_panel, 'Title', '播放控制', ...
    'Position', [0.01, 0.5, 0.98, 0.5]);

% 开始/暂停按钮
play_btn = uicontrol('Parent', play_panel, 'Style', 'togglebutton', ...
    'String', '播放', 'Position', [20, 40, 80, 30]);

% 日期选择下拉菜单
date_select = uicontrol('Parent', play_panel, 'Style', 'popupmenu', ...
    'String', slice_start_times, 'Position', [120, 40, 150, 30]);

% 速度控制滑块
speed_slider = uicontrol('Parent', play_panel, 'Style', 'slider', ...
    'Min', 0.05, 'Max', 1, 'Value', 0.2, ...
    'Position', [290, 40, 120, 30]);
speed_label = uicontrol('Parent', play_panel, 'Style', 'text', ...
    'String', '播放速度', 'Position', [290, 70, 120, 15]);

% 当前播放位置文本
position_text = uicontrol('Parent', play_panel, 'Style', 'text', ...
    'String', '0/0', 'Position', [430, 40, 200, 30], ...
    'HorizontalAlignment', 'left');

% 播放进度滑块
progress_slider = uicontrol('Parent', play_panel, 'Style', 'slider', ...
    'Min', 1, 'Max', num_slices, 'Value', 1, ...
    'Position', [650, 40, 250, 30]);

% 创建UI子面板 - 参数设置
param_panel = uipanel('Parent', control_panel, 'Title', '参数设置', ...
    'Position', [0.01, 0, 0.98, 0.5]);

% 窗口长度输入框（小时）
duration_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '窗口长度(小时):', ...
    'Position', [20, 40, 100, 20], 'HorizontalAlignment', 'left');

duration_edit = uicontrol('Parent', param_panel, 'Style', 'edit', ...
    'String', num2str(slice_duration/3600, '%.1f'), ...
    'Position', [130, 40, 60, 20], 'Callback', @duration_callback);

% 重叠比例输入框(%)
overlap_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '重叠比例(%):', ...
    'Position', [220, 40, 80, 20], 'HorizontalAlignment', 'left');

overlap_edit = uicontrol('Parent', param_panel, 'Style', 'edit', ...
    'String', num2str(overlap_ratio*100, '%.0f'), ...
    'Position', [310, 40, 60, 20], 'Callback', @overlap_callback);

% 添加窗口长度范围提示
duration_range = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', sprintf('有效范围: %.1f-%.1f 小时', min_duration/3600, max_duration/3600), ...
    'Position', [20, 15, 170, 20], 'HorizontalAlignment', 'left', ...
    'ForegroundColor', [0.5, 0.5, 0.5]);

% 添加重叠比例范围提示
overlap_range = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', sprintf('有效范围: %.0f-%.0f%%', min_overlap*100, max_overlap*100), ...
    'Position', [220, 15, 150, 20], 'HorizontalAlignment', 'left', ...
    'ForegroundColor', [0.5, 0.5, 0.5]);

% 瀑布图历史长度输入框
waterfall_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '瀑布图历史长度:', ...
    'Position', [400, 40, 120, 20], 'HorizontalAlignment', 'left');

waterfall_edit = uicontrol('Parent', param_panel, 'Style', 'edit', ...
    'String', num2str(waterfall_history_size), ...
    'Position', [520, 40, 60, 20], 'Callback', @waterfall_size_callback);

% 数据处理控件 - 滤波器类型选择
filter_checkbox = uicontrol('Parent', param_panel, 'Style', 'checkbox', ...
    'String', '启用数据处理', 'Value', enable_filter, ...
    'Position', [600, 40, 150, 20], 'Callback', @filter_checkbox_callback);

filter_type_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '处理类型:', ...
    'Position', [750, 40, 60, 20], 'HorizontalAlignment', 'left');

filter_type_popup = uicontrol('Parent', param_panel, 'Style', 'popupmenu', ...
    'String', {'均值降采样', '低通滤波'}, 'Value', filter_type, ...
    'Position', [820, 40, 100, 20], 'Callback', @filter_type_callback);

filter_param_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '窗口大小:', ...
    'Position', [930, 40, 60, 20], 'HorizontalAlignment', 'left');

filter_param_edit = uicontrol('Parent', param_panel, 'Style', 'edit', ...
    'String', num2str(filter_window), ...
    'Position', [1000, 40, 60, 20], 'Callback', @filter_param_callback);

% 应用按钮
apply_btn = uicontrol('Parent', param_panel, 'Style', 'pushbutton', ...
    'String', '应用参数', 'Position', [1070, 40, 80, 20]);

% 11. 设置回调函数
set(play_btn, 'Callback', @play_callback);
set(date_select, 'Callback', @date_select_callback);
set(speed_slider, 'Callback', @speed_callback);
set(progress_slider, 'Callback', @progress_callback);
set(apply_btn, 'Callback', @apply_callback);

% 12. 显示第一帧
updateDisplay(current_slice);

% 瀑布图历史长度回调
    function waterfall_size_callback(hObject, ~)
        try
            new_size = str2double(get(hObject, 'String'));
            if isnan(new_size) || new_size < 2 || new_size > 100 || mod(new_size, 1) ~= 0
                % 如果输入无效，恢复原值
                set(hObject, 'String', num2str(waterfall_history_size));
                warndlg('请输入2到100之间的整数', '无效输入');
            else
                waterfall_history_size = new_size;
                % 调整历史数据大小
                if ~isempty(waterfall_history)
                    if size(waterfall_history, 1) > waterfall_history_size
                        % 如果历史数据过多，只保留最新的
                        waterfall_history = waterfall_history(end-waterfall_history_size+1:end, :);
                        waterfall_times = waterfall_times(end-waterfall_history_size+1:end);
                    end
                end
                updateDisplay(current_slice);
            end
        catch
            % 错误处理
            set(hObject, 'String', num2str(waterfall_history_size));
            warndlg('请输入有效的整数', '无效输入');
        end
    end

% 滤波启用/禁用复选框回调
    function filter_checkbox_callback(hObject, ~)
        enable_filter = get(hObject, 'Value');
        if enable_filter
            % 应用滤波
            applyFilter();
        else
            % 恢复原始数据
            filtered_value = value;
        end
        % 更新显示
        updateDisplay(current_slice);
    end

% 滤波类型回调
    function filter_type_callback(hObject, ~)
        filter_type = get(hObject, 'Value');
        % 更新参数标签
        if filter_type == 1
            set(filter_param_label, 'String', '窗口大小:');
        else
            set(filter_param_label, 'String', '截止频率(Hz):');
        end
        
        % 如果已启用滤波，则重新应用
        if enable_filter
            applyFilter();
            updateDisplay(current_slice);
        end
    end

% 滤波参数输入框回调
    function filter_param_callback(hObject, ~)
        try
            new_param = str2double(get(hObject, 'String'));
            if filter_type == 1 % 均值降采样
                if isnan(new_param) || new_param < 1 || new_param > 100 || mod(new_param, 1) ~= 0
                    % 如果输入无效，恢复原值
                    set(hObject, 'String', num2str(filter_window));
                    warndlg('请输入1到100之间的整数', '无效输入');
                    return;
                end
            else % 低通滤波
                if isnan(new_param) || new_param <= 0 || new_param > fs/2
                    % 如果输入无效，恢复原值
                    set(hObject, 'String', num2str(filter_window));
                    warndlg(sprintf('请输入0到%.3f之间的数值', fs/2), '无效输入');
                    return;
                end
            end
            
            filter_window = new_param;
            if enable_filter
                % 如果滤波已启用，应用新参数
                applyFilter();
                updateDisplay(current_slice);
            end
        catch
            % 错误处理
            set(hObject, 'String', num2str(filter_window));
            warndlg('请输入有效的数值', '无效输入');
        end
    end

% 应用数据处理
    function applyFilter()
        if filter_type == 1
            % 均值降采样
            filtered_value = downsample_mean(value, round(filter_window));
        else
            % 低通滤波 (巴特沃斯滤波器)
            [b, a] = butter(4, filter_window/(fs/2), 'low');
            filtered_value = filtfilt(b, a, value);
        end
    end

% 均值降采样函数
    function y = downsample_mean(x, window)
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

% 窗口长度输入框回调
    function duration_callback(hObject, ~)
        try
            new_duration = str2double(get(hObject, 'String'));
            % 验证输入值是否在有效范围内
            if isnan(new_duration) || new_duration < min_duration/3600 || new_duration > max_duration/3600
                % 如果输入无效，恢复原值
                set(hObject, 'String', num2str(slice_duration/3600, '%.1f'));
                warndlg(sprintf('请输入 %.1f 到 %.1f 之间的有效小时数', ...
                    min_duration/3600, max_duration/3600), '无效输入');
            end
        catch
            % 错误处理
            set(hObject, 'String', num2str(slice_duration/3600, '%.1f'));
            warndlg('请输入有效的数字', '无效输入');
        end
    end

% 重叠比例输入框回调
    function overlap_callback(hObject, ~)
        try
            new_overlap = str2double(get(hObject, 'String')) / 100; % 将百分比转换为小数
            % 验证输入值是否在有效范围内
            if isnan(new_overlap) || new_overlap < min_overlap || new_overlap > max_overlap
                % 如果输入无效，恢复原值
                set(hObject, 'String', num2str(overlap_ratio*100, '%.0f'));
                warndlg(sprintf('请输入 %.0f 到 %.0f 之间的有效百分比', ...
                    min_overlap*100, max_overlap*100), '无效输入');
            end
        catch
            % 错误处理
            set(hObject, 'String', num2str(overlap_ratio*100, '%.0f'));
            warndlg('请输入有效的数字', '无效输入');
        end
    end

% 应用参数按钮回调
    function apply_callback(~, ~)
        % 获取新参数值
        try
            new_duration = str2double(get(duration_edit, 'String')) * 3600; % 转换小时到秒
            new_overlap = str2double(get(overlap_edit, 'String')) / 100; % 转换百分比到小数
            
            % 验证参数是否在有效范围内
            if isnan(new_duration) || new_duration < min_duration || new_duration > max_duration
                warndlg(sprintf('窗口长度必须在 %.1f 到 %.1f 小时之间', ...
                    min_duration/3600, max_duration/3600), '无效参数');
                return;
            end
            
            if isnan(new_overlap) || new_overlap < min_overlap || new_overlap > max_overlap
                warndlg(sprintf('重叠比例必须在 %.0f%% 到 %.0f%% 之间', ...
                    min_overlap*100, max_overlap*100), '无效参数');
                return;
            end
            
            % 记录当前时间点（用于后续定位）
            if current_slice <= num_slices
                current_idx = (current_slice-1) * step_points + 1;
                if current_idx <= length(time)
                    current_time_point = time(current_idx);
                end
            end
            
            % 更新全局参数
            slice_duration = new_duration;
            overlap_ratio = new_overlap;
            
            % 重新计算切片点数
            slice_points = round(slice_duration * fs);
            step_points = round(slice_points * (1 - overlap_ratio));
            
            % 重新计算切片数量
            num_slices = calculate_num_slices(data_length, slice_points, step_points);
            
            % 更新进度滑块范围
            set(progress_slider, 'Max', num_slices);
            
            % 重新计算日期选择
            slice_start_times = calculate_slice_start_times(time, num_slices, step_points);
            set(date_select, 'String', slice_start_times);
            
            % 找到最接近当前时间点的新切片索引
            current_slice = find_closest_slice(current_time_point, time, step_points);
            if current_slice > num_slices
                current_slice = num_slices;
            end
            
            % 清空瀑布图历史
            waterfall_history = [];
            waterfall_times = [];
            
            % 更新进度滑块位置
            set(progress_slider, 'Value', current_slice);
            
            % 更新显示
            updateDisplay(current_slice);
        catch
            warndlg('处理参数时出错，请检查输入', '错误');
        end
    end

% 辅助函数：计算切片数量
    function num = calculate_num_slices(data_len, slice_pts, step_pts)
        num = floor((data_len - slice_pts) / step_pts) + 1;
        if num < 1
            num = 1;
        end
    end

% 辅助函数：计算切片开始时间
    function times = calculate_slice_start_times(time_data, num_slices, step_pts)
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

% 辅助函数：找到最接近指定时间点的切片索引
    function idx = find_closest_slice(target_time, time_data, step_pts)
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

% 播放按钮回调
    function play_callback(hObject, ~)
        is_playing = get(hObject, 'Value');
        if is_playing
            set(hObject, 'String', '暂停');
            playAnimation();
        else
            set(hObject, 'String', '播放');
        end
    end

% 日期选择回调
    function date_select_callback(hObject, ~)
        date_idx = get(hObject, 'Value');
        selected_date = slice_start_times{date_idx};
        % 查找日期对应的第一个切片
        for i = 1:num_slices
            start_idx = (i-1) * step_points + 1;
            if start_idx <= length(time)
                if strcmpi(datestr(time(start_idx), 'yyyy-mm-dd'), selected_date)
                    current_slice = i;
                    set(progress_slider, 'Value', current_slice);
                    updateDisplay(current_slice);
                    break;
                end
            end
        end
    end

% 速度控制回调
    function speed_callback(hObject, ~)
        pause_time = 1.05 - get(hObject, 'Value');
    end

% 进度回调
    function progress_callback(hObject, ~)
        current_slice = round(get(hObject, 'Value'));
        updateDisplay(current_slice);
    end

% 动画播放函数
    function playAnimation()
        while is_playing && current_slice < num_slices
            current_slice = current_slice + 1;
            set(progress_slider, 'Value', current_slice);
            updateDisplay(current_slice);
            pause(pause_time);
            drawnow;
            
            % 检查是否还在播放
            if ~is_playing || current_slice >= num_slices
                set(play_btn, 'Value', 0);
                set(play_btn, 'String', '播放');
                break;
            end
        end
    end

% 更新显示函数
    function updateDisplay(slice_idx)
        % 计算当前切片的索引
        start_idx = (slice_idx-1) * step_points + 1;
        end_idx = min(start_idx + slice_points - 1, length(value));
        
        if end_idx <= length(value)
            % 提取当前切片数据
            current_time = time(start_idx:end_idx);
            
            % 根据滤波设置选择数据
            if enable_filter
                current_value = filtered_value(start_idx:end_idx);
            else
                current_value = value(start_idx:end_idx);
            end
            
            % 计算当前切片的时间范围（用于标题）
            time_range_str = sprintf('%s 到 %s', ...
                datestr(current_time(1), 'yyyy-mm-dd HH:MM:SS'), ...
                datestr(current_time(end), 'yyyy-mm-dd HH:MM:SS'));
            
            % 更新位置文本
            set(position_text, 'String', sprintf('%d/%d - %s - 窗口: %.1f小时 重叠: %.0f%%', ...
                slice_idx, num_slices, ...
                datestr(current_time(1), 'yyyy-mm-dd'), ...
                slice_duration/3600, overlap_ratio*100));
            
            % 绘制时域图（折线图）
            axes(time_ax);
            cla;
            plot(current_time, current_value, 'b-');
            
            % 更新时域图标题
            filter_text = '';
            if enable_filter
                if filter_type == 1
                    filter_text = sprintf('(均值降采样, 窗口=%d)', filter_window);
                else
                    filter_text = sprintf('(低通滤波, 截止频率=%.3fHz)', filter_window);
                end
            end
            title(sprintf('时域信号 %s (%s)', filter_text, time_range_str));
            
            xlabel('时间');
            ylabel('幅度');
            grid on;
            
            % 计算频域数据
            % 去除直流分量
            current_value = current_value - mean(current_value);
            
            % 获取当前切片长度
            N = length(current_value);
            
            % 实现ZoomFFT - 放大低频区域
            % 1. 生成时间向量
            t_vec = (0:N-1)' / fs;
            
            % 2. 将信号搬移到中心频率
            shifted_signal = current_value .* exp(-1i * 2 * pi * center_freq * t_vec);
            
            % 3. 对搬移信号进行FFT
            N_fft = 2^nextpow2(N)*8; % 增加FFT点数提高分辨率
            Y = fft(shifted_signal, N_fft);
            
            % 4. 计算新频率向量（放大后的频率区间）
            freq_zoom = fs/N_fft * (-(N_fft/2):(N_fft/2-1)) + center_freq;
            
            % 5. 重新排列结果以获得正确顺序
            Y = fftshift(Y);
            
            % 6. 计算幅值谱
            P_zoom = abs(Y)/N;
            
            % 7. 选择感兴趣的频率范围
            idx = (freq_zoom >= freq_range(1)) & (freq_zoom <= freq_range(2));
            f_plot = freq_zoom(idx);
            P1_plot = P_zoom(idx);
            
            % 8. 避免对数坐标下的零值问题
            f_plot = max(f_plot, eps); % 确保没有零频率
            P1_plot = max(P1_plot, eps); % 确保没有零幅值
            
            % 9. 更新瀑布图历史数据
            if isempty(waterfall_history)
                waterfall_history = zeros(1, length(P1_plot));
                waterfall_times = current_time(1);
            end
            
            % 添加新的频谱数据到瀑布图历史
            waterfall_history = [waterfall_history; P1_plot'];
            waterfall_times = [waterfall_times; current_time(1)];
            
            % 如果历史数据超过设定的大小，则移除最早的数据
            if size(waterfall_history, 1) > waterfall_history_size
                waterfall_history = waterfall_history(end-waterfall_history_size+1:end, :);
                waterfall_times = waterfall_times(end-waterfall_history_size+1:end);
            end
            
            % 10. 绘制2D热力图瀑布图
            axes(waterfall_ax);
            cla;
            
            % 计算用于显示的对数频谱数据
            log_waterfall = log10(waterfall_history);
            
            % 创建时间刻度标签
            y_labels = cell(size(waterfall_times));
            for i = 1:length(waterfall_times)
                if mod(i, max(1, round(length(waterfall_times)/5))) == 0 || i == 1 || i == length(waterfall_times)
                    y_labels{i} = datestr(waterfall_times(i), 'HH:MM:SS');
                else
                    y_labels{i} = '';
                end
            end
            
            % 使用imagesc创建热力图
            imagesc(f_plot, 1:size(waterfall_history, 1), log_waterfall);
            
            % 设置坐标轴为对数刻度
            set(gca, 'XScale', 'log');
            
            % 设置Y轴标签为时间
            yticks(1:size(waterfall_history, 1));
            yticklabels(y_labels);
            
            % 反转Y轴，使最新的数据在底部
            set(gca, 'YDir', 'reverse');
            
            % 设置X轴范围
            xlim([freq_range(1), freq_range(2)]);
            
            % 添加颜色条
            cb = colorbar;
            cb.Label.String = '幅值(对数)';
            
            % 更新瀑布图标题
            if enable_filter
                if filter_type == 1
                    title(sprintf('频谱热力图（均值降采样, 窗口=%d）', filter_window));
                else
                    title(sprintf('频谱热力图（低通滤波, 截止频率=%.3fHz）', filter_window));
                end
            else
                title('频谱热力图');
            end
            
            xlabel('频率 (Hz)');
            ylabel('时间');
        end
    end
end