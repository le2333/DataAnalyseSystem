classdef SliceNode < ProcessorNode
    %SLICENODE 数据切片处理节点
    %   将整体数据按照时间切片，支持设置切片长度和重叠比例
    
    methods
        function obj = SliceNode(name)
            %SLICENODE 构造函数
            if nargin < 1
                name = 'Slicer';
            end
            obj = obj@ProcessorNode(name);
            
            % 设置默认参数
            obj.Parameters.slice_duration = 24*60*60; % 默认切片时长为24小时（秒）
            obj.Parameters.overlap_ratio = 0.5;       % 默认重叠比例为50%
            obj.Parameters.current_slice = 1;         % 当前选中的切片索引
        end
        
        function execute(obj)
            %EXECUTE 执行切片处理
            obj.validateInputs();
            
            % 获取输入数据
            time = obj.Inputs.time;
            value = obj.Inputs.value;
            fs = obj.Inputs.fs;
            
            % 计算切片参数
            slice_points = round(obj.Parameters.slice_duration * fs);
            step_points = round(slice_points * (1 - obj.Parameters.overlap_ratio));
            
            % 计算总切片数量
            data_length = length(value);
            num_slices = obj.calculate_num_slices(data_length, slice_points, step_points);
            
            % 计算每个切片的起始时间
            slice_start_times = obj.calculate_slice_start_times(time, num_slices, step_points);
            
            % 校正当前切片索引
            current_slice = min(max(1, obj.Parameters.current_slice), num_slices);
            
            % 获取当前切片数据
            [slice_data, slice_info] = obj.get_slice_data(time, value, current_slice, slice_points, step_points);
            
            % 设置输出
            obj.Outputs.time = slice_data.time;
            obj.Outputs.value = slice_data.value;
            obj.Outputs.fs = fs;
            obj.Outputs.num_slices = num_slices;
            obj.Outputs.slice_start_times = slice_start_times;
            obj.Outputs.current_slice = current_slice;
            obj.Outputs.slice_index = [slice_info.start_idx, slice_info.end_idx];
            obj.Outputs.slice_time_range = slice_info.time_range_str;
            obj.Outputs.slice_points = slice_points;
            obj.Outputs.step_points = step_points;
            
            obj.IsExecuted = true;
        end
        
        function validateInputs(obj)
            %VALIDATEINPUTS 验证输入是否有效
            if ~isfield(obj.Inputs, 'time') || isempty(obj.Inputs.time)
                error('缺少输入数据: time');
            end
            
            if ~isfield(obj.Inputs, 'value') || isempty(obj.Inputs.value)
                error('缺少输入数据: value');
            end
            
            if ~isfield(obj.Inputs, 'fs') || isempty(obj.Inputs.fs)
                error('缺少输入数据: fs');
            end
            
            % 验证切片参数
            if obj.Parameters.slice_duration <= 0
                error('切片时长必须为正值');
            end
            
            if obj.Parameters.overlap_ratio < 0 || obj.Parameters.overlap_ratio >= 1
                error('重叠比例必须在[0, 1)范围内');
            end
        end
        
        function setCurrentSlice(obj, slice_idx)
            %SETCURRENTSLICE 设置当前切片索引
            obj.Parameters.current_slice = slice_idx;
            obj.reset(); % 重置执行状态
        end
    end
    
    methods (Access = private)
        function num = calculate_num_slices(~, data_len, slice_pts, step_pts)
            %CALCULATE_NUM_SLICES 计算总切片数量
            num = floor((data_len - slice_pts) / step_pts) + 1;
            if num < 1
                num = 1;
            end
        end
        
        function times = calculate_slice_start_times(~, time_data, num_slices, step_pts)
            %CALCULATE_SLICE_START_TIMES 计算每个切片的起始时间（日期）
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
        
        function [slice_data, slice_info] = get_slice_data(~, time, value, slice_idx, slice_points, step_points)
            %GET_SLICE_DATA 获取指定索引的切片数据
            % 计算切片的起始和结束索引
            start_idx = (slice_idx-1) * step_points + 1;
            end_idx = min(start_idx + slice_points - 1, length(value));
            
            % 提取切片数据
            slice_data.time = time(start_idx:end_idx);
            slice_data.value = value(start_idx:end_idx);
            
            % 记录切片信息
            slice_info.start_idx = start_idx;
            slice_info.end_idx = end_idx;
            slice_info.time_range_str = sprintf('%s 到 %s', ...
                datestr(slice_data.time(1), 'yyyy-mm-dd HH:MM:SS'), ...
                datestr(slice_data.time(end), 'yyyy-mm-dd HH:MM:SS'));
        end
    end
end