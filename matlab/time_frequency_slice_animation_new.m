function time_frequency_slice_animation_new()
%% 时频切片动画 (新版)
% 本脚本对原始数据进行切片，并展示每个片段的时域和频域信息，支持手动播放控制
% 基于节点+工作流架构的前端UI界面

% 1. 创建时频分析工作流
workflow = TimeFrequencyWorkflow();

% 2. 加载数据
filename = fullfile('..', 'data', 'sat1', '5_2025031706435044765.csv');
workflow.loadData(filename);

% 3. 创建主图形窗口
main_fig = figure('Position', [100, 100, 1200, 800], 'Name', '时频切片分析', ...
    'NumberTitle', 'off', 'MenuBar', 'none', 'Resize', 'on');

% 4. 定义全局状态变量
is_playing = false;
pause_time = 0.2; % 默认暂停时间

% 5. 创建UI控件面板
control_panel = uipanel('Parent', main_fig, 'Position', [0, 0, 1, 0.2], ...
    'Title', '控制面板');

% 6. 创建绘图区域
time_ax = subplot('Position', [0.1, 0.65, 0.8, 0.25]);
waterfall_ax = subplot('Position', [0.1, 0.25, 0.8, 0.3]);

% 7. 获取初始数据
slice_data = workflow.getSliceData();
slice_settings = workflow.getSliceSettings();
filter_settings = workflow.getFilterSettings();

% 创建UI子面板 - 播放控制
play_panel = uipanel('Parent', control_panel, 'Title', '播放控制', ...
    'Position', [0.01, 0.5, 0.98, 0.5]);

% 开始/暂停按钮
play_btn = uicontrol('Parent', play_panel, 'Style', 'togglebutton', ...
    'String', '播放', 'Position', [20, 40, 80, 30]);

% 日期选择下拉菜单
date_select = uicontrol('Parent', play_panel, 'Style', 'popupmenu', ...
    'String', slice_settings.slice_start_times, 'Position', [120, 40, 150, 30]);

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
    'Min', 1, 'Max', slice_data.num_slices, 'Value', slice_data.current_slice, ...
    'Position', [650, 40, 250, 30]);

% 创建UI子面板 - 参数设置
param_panel = uipanel('Parent', control_panel, 'Title', '参数设置', ...
    'Position', [0.01, 0, 0.98, 0.5]);

% 窗口长度输入框（小时）
duration_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '窗口长度(小时):', ...
    'Position', [20, 40, 100, 20], 'HorizontalAlignment', 'left');

duration_edit = uicontrol('Parent', param_panel, 'Style', 'edit', ...
    'String', num2str(slice_settings.slice_duration/3600, '%.1f'), ...
    'Position', [130, 40, 60, 20], 'Callback', @duration_callback);

% 重叠比例输入框(%)
overlap_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '重叠比例(%):', ...
    'Position', [220, 40, 80, 20], 'HorizontalAlignment', 'left');

overlap_edit = uicontrol('Parent', param_panel, 'Style', 'edit', ...
    'String', num2str(slice_settings.overlap_ratio*100, '%.0f'), ...
    'Position', [310, 40, 60, 20], 'Callback', @overlap_callback);

% 添加窗口长度范围提示
min_duration = 1*60*60; % 最小1小时
max_duration = 7*24*60*60; % 最大7天
duration_range = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', sprintf('有效范围: %.1f-%.1f 小时', min_duration/3600, max_duration/3600), ...
    'Position', [20, 15, 170, 20], 'HorizontalAlignment', 'left', ...
    'ForegroundColor', [0.5, 0.5, 0.5]);

% 添加重叠比例范围提示
min_overlap = 0; % 最小0%重叠
max_overlap = 0.9; % 最大90%重叠
overlap_range = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', sprintf('有效范围: %.0f-%.0f%%', min_overlap*100, max_overlap*100), ...
    'Position', [220, 15, 150, 20], 'HorizontalAlignment', 'left', ...
    'ForegroundColor', [0.5, 0.5, 0.5]);

% 瀑布图历史长度输入框
waterfall_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '瀑布图历史长度:', ...
    'Position', [400, 40, 120, 20], 'HorizontalAlignment', 'left');

waterfall_edit = uicontrol('Parent', param_panel, 'Style', 'edit', ...
    'String', num2str(workflow.Waterfall.getParameter('history_size')), ...
    'Position', [520, 40, 60, 20], 'Callback', @waterfall_size_callback);

% 数据处理控件 - 滤波器类型选择
filter_checkbox = uicontrol('Parent', param_panel, 'Style', 'checkbox', ...
    'String', '启用数据处理', 'Value', filter_settings.enable, ...
    'Position', [600, 40, 150, 20], 'Callback', @filter_checkbox_callback);

filter_type_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '处理类型:', ...
    'Position', [750, 40, 60, 20], 'HorizontalAlignment', 'left');

filter_type_popup = uicontrol('Parent', param_panel, 'Style', 'popupmenu', ...
    'String', {'均值降采样', '低通滤波'}, 'Value', filter_settings.filter_type, ...
    'Position', [820, 40, 100, 20], 'Callback', @filter_type_callback);

filter_param_label = uicontrol('Parent', param_panel, 'Style', 'text', ...
    'String', '参数值:', ...
    'Position', [930, 40, 60, 20], 'HorizontalAlignment', 'left');

% 根据当前滤波类型设置参数标签和值
if filter_settings.filter_type == workflow.Filter.MEAN_DOWNSAMPLE
    param_value = filter_settings.window;
    set(filter_param_label, 'String', '窗口大小:');
else
    param_value = filter_settings.cutoff_freq;
    set(filter_param_label, 'String', '截止频率(Hz):');
end

filter_param_edit = uicontrol('Parent', param_panel, 'Style', 'edit', ...
    'String', num2str(param_value), ...
    'Position', [1000, 40, 60, 20], 'Callback', @filter_param_callback);

% 应用按钮
apply_btn = uicontrol('Parent', param_panel, 'Style', 'pushbutton', ...
    'String', '应用参数', 'Position', [1070, 40, 80, 20]);

% 8. 设置回调函数
set(play_btn, 'Callback', @play_callback);
set(date_select, 'Callback', @date_select_callback);
set(speed_slider, 'Callback', @speed_callback);
set(progress_slider, 'Callback', @progress_callback);
set(apply_btn, 'Callback', @apply_callback);

% 9. 显示第一帧
updateDisplay();

% 瀑布图历史长度回调
    function waterfall_size_callback(hObject, ~)
        try
            new_size = str2double(get(hObject, 'String'));
            if isnan(new_size) || new_size < 2 || new_size > 100 || mod(new_size, 1) ~= 0
                % 如果输入无效，恢复原值
                set(hObject, 'String', num2str(workflow.Waterfall.getParameter('history_size')));
                warndlg('请输入2到100之间的整数', '无效输入');
            else
                % 设置新的瀑布图历史大小
                workflow.setWaterfallHistorySize(new_size);
                updateDisplay();
            end
        catch
            % 错误处理
            set(hObject, 'String', num2str(workflow.Waterfall.getParameter('history_size')));
            warndlg('请输入有效的整数', '无效输入');
        end
    end

% 滤波启用/禁用复选框回调
    function filter_checkbox_callback(hObject, ~)
        enable_filter = get(hObject, 'Value');
        filter_type = get(filter_type_popup, 'Value');
        filter_param = str2double(get(filter_param_edit, 'String'));
        
        % 更新滤波设置
        workflow.setFilterParameters(enable_filter, filter_type, filter_param);
        
        % 更新显示
        updateDisplay();
    end

% 滤波类型回调
    function filter_type_callback(hObject, ~)
        filter_type = get(hObject, 'Value');
        
        % 更新参数标签
        if filter_type == workflow.Filter.MEAN_DOWNSAMPLE
            set(filter_param_label, 'String', '窗口大小:');
            % 默认窗口大小
            set(filter_param_edit, 'String', num2str(workflow.Filter.getParameter('window')));
        else
            set(filter_param_label, 'String', '截止频率(Hz):');
            % 默认截止频率
            set(filter_param_edit, 'String', num2str(workflow.Filter.getParameter('cutoff_freq')));
        end
        
        % 如果滤波已启用，更新滤波参数
        if get(filter_checkbox, 'Value')
            filter_param = str2double(get(filter_param_edit, 'String'));
            workflow.setFilterParameters(true, filter_type, filter_param);
            updateDisplay();
        end
    end

% 滤波参数输入框回调
    function filter_param_callback(hObject, ~)
        try
            new_param = str2double(get(hObject, 'String'));
            filter_type = get(filter_type_popup, 'Value');
            
            if filter_type == workflow.Filter.MEAN_DOWNSAMPLE
                if isnan(new_param) || new_param < 1 || new_param > 100 || mod(new_param, 1) ~= 0
                    % 如果输入无效，恢复原值
                    set(hObject, 'String', num2str(workflow.Filter.getParameter('window')));
                    warndlg('请输入1到100之间的整数', '无效输入');
                    return;
                end
            else
                fs = workflow.getSamplingRate();
                if isnan(new_param) || new_param <= 0 || new_param >= fs/2
                    % 如果输入无效，恢复原值
                    set(hObject, 'String', num2str(workflow.Filter.getParameter('cutoff_freq')));
                    warndlg(sprintf('请输入0到%.3f之间的数值', fs/2), '无效输入');
                    return;
                end
            end
            
            % 如果滤波已启用，应用新参数
            if get(filter_checkbox, 'Value')
                workflow.setFilterParameters(true, filter_type, new_param);
                updateDisplay();
            end
        catch
            % 错误处理
            if filter_type == workflow.Filter.MEAN_DOWNSAMPLE
                set(hObject, 'String', num2str(workflow.Filter.getParameter('window')));
            else
                set(hObject, 'String', num2str(workflow.Filter.getParameter('cutoff_freq')));
            end
            warndlg('请输入有效的数值', '无效输入');
        end
    end

% 窗口长度输入框回调
    function duration_callback(hObject, ~)
        try
            new_duration = str2double(get(hObject, 'String'));
            % 验证输入值是否在有效范围内
            if isnan(new_duration) || new_duration < min_duration/3600 || new_duration > max_duration/3600
                % 如果输入无效，恢复原值
                slice_settings = workflow.getSliceSettings();
                set(hObject, 'String', num2str(slice_settings.slice_duration/3600, '%.1f'));
                warndlg(sprintf('请输入 %.1f 到 %.1f 之间的有效小时数', ...
                    min_duration/3600, max_duration/3600), '无效输入');
            end
        catch
            % 错误处理
            slice_settings = workflow.getSliceSettings();
            set(hObject, 'String', num2str(slice_settings.slice_duration/3600, '%.1f'));
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
                slice_settings = workflow.getSliceSettings();
                set(hObject, 'String', num2str(slice_settings.overlap_ratio*100, '%.0f'));
                warndlg(sprintf('请输入 %.0f 到 %.0f 之间的有效百分比', ...
                    min_overlap*100, max_overlap*100), '无效输入');
            end
        catch
            % 错误处理
            slice_settings = workflow.getSliceSettings();
            set(hObject, 'String', num2str(slice_settings.overlap_ratio*100, '%.0f'));
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
            
            % 更新切片参数
            workflow.setSliceParameters(new_duration, new_overlap);
            
            % 更新UI
            slice_data = workflow.getSliceData();
            slice_settings = workflow.getSliceSettings();
            
            % 更新进度滑块范围
            set(progress_slider, 'Max', slice_data.num_slices);
            set(progress_slider, 'Value', slice_data.current_slice);
            
            % 更新日期选择下拉菜单
            set(date_select, 'String', slice_settings.slice_start_times);
            
            % 更新显示
            updateDisplay();
        catch
            warndlg('处理参数时出错，请检查输入', '错误');
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
        slice_settings = workflow.getSliceSettings();
        slice_data = workflow.getSliceData();
        
        date_idx = get(hObject, 'Value');
        selected_date = slice_settings.slice_start_times{date_idx};
        
        % 根据日期找到第一个对应的切片
        found = false;
        for i = 1:slice_data.num_slices
            workflow.setCurrentSlice(i);
            updated_slice_data = workflow.getSliceData();
            time_part = updated_slice_data.time(1);
            if strcmpi(datestr(time_part, 'yyyy-mm-dd'), selected_date)
                found = true;
                break;
            end
        end
        
        if found
            % 更新进度滑块
            set(progress_slider, 'Value', i);
            updateDisplay();
        end
    end

% 速度控制回调
    function speed_callback(hObject, ~)
        pause_time = 1.05 - get(hObject, 'Value');
    end

% 进度回调
    function progress_callback(hObject, ~)
        current_slice = round(get(hObject, 'Value'));
        workflow.setCurrentSlice(current_slice);
        updateDisplay();
    end

% 动画播放函数
    function playAnimation()
        slice_data = workflow.getSliceData();
        current_slice = slice_data.current_slice;
        
        while is_playing && current_slice < slice_data.num_slices
            current_slice = current_slice + 1;
            workflow.setCurrentSlice(current_slice);
            
            % 更新UI
            set(progress_slider, 'Value', current_slice);
            updateDisplay();
            
            pause(pause_time);
            drawnow;
            
            % 检查是否还在播放
            slice_data = workflow.getSliceData();
            if ~is_playing || current_slice >= slice_data.num_slices
                set(play_btn, 'Value', 0);
                set(play_btn, 'String', '播放');
                break;
            end
        end
    end

% 更新显示函数
    function updateDisplay()
        % 获取最新数据
        slice_data = workflow.getSliceData();
        spectrum_data = workflow.getSpectrumData();
        waterfall_data = workflow.getWaterfallData();
        
        % 更新位置文本
        set(position_text, 'String', sprintf('%d/%d - %s - 窗口: %.1f小时 重叠: %.0f%%', ...
            slice_data.current_slice, slice_data.num_slices, ...
            datestr(slice_data.time(1), 'yyyy-mm-dd'), ...
            workflow.Slicer.getParameter('slice_duration')/3600, ...
            workflow.Slicer.getParameter('overlap_ratio')*100));
        
        % 绘制时域图（折线图）
        axes(time_ax);
        cla;
        plot(slice_data.time, slice_data.value, 'b-');
        
        % 更新时域图标题
        if ~isempty(slice_data.filter_info)
            title(sprintf('时域信号 (%s) (%s)', slice_data.filter_info, slice_data.time_range_str));
        else
            title(sprintf('时域信号 (%s)', slice_data.time_range_str));
        end
        
        xlabel('时间');
        ylabel('幅度');
        grid on;
        
        % 如果有瀑布图数据，则绘制
        if waterfall_data.size > 0
            % 绘制2D热力图瀑布图
            axes(waterfall_ax);
            cla;
            
            % 创建时间刻度标签
            y_labels = cell(size(waterfall_data.times));
            for i = 1:length(waterfall_data.times)
                if mod(i, max(1, round(length(waterfall_data.times)/5))) == 0 || i == 1 || i == length(waterfall_data.times)
                    y_labels{i} = datestr(waterfall_data.times(i), 'HH:MM:SS');
                else
                    y_labels{i} = '';
                end
            end
            
            % 使用imagesc创建热力图
            imagesc(spectrum_data.f_plot, 1:waterfall_data.size, waterfall_data.log_history);
            
            % 设置坐标轴为对数刻度
            set(gca, 'XScale', 'log');
            
            % 设置Y轴标签为时间
            yticks(1:waterfall_data.size);
            yticklabels(y_labels);
            
            % 反转Y轴，使最新的数据在底部
            set(gca, 'YDir', 'reverse');
            
            % 设置X轴范围
            xlim(spectrum_data.freq_range);
            
            % 添加颜色条
            cb = colorbar;
            cb.Label.String = '幅值(对数)';
            
            % 更新瀑布图标题
            if ~isempty(slice_data.filter_info)
                title(sprintf('频谱热力图（%s）', slice_data.filter_info));
            else
                title('频谱热力图');
            end
            
            xlabel('频率 (Hz)');
            ylabel('时间');
        end
    end
end