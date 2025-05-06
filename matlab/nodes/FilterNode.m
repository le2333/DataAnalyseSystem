classdef FilterNode < ProcessorNode
    %FILTERNODE 滤波处理节点
    %   支持均值降采样和低通滤波两种处理方式
    
    properties (Constant)
        MEAN_DOWNSAMPLE = 1 % 均值降采样模式
        LOWPASS_FILTER = 2  % 低通滤波模式
    end
    
    methods
        function obj = FilterNode(name)
            %FILTERNODE 构造函数
            if nargin < 1
                name = 'Filter';
            end
            obj = obj@ProcessorNode(name);
            
            % 设置默认参数
            obj.Parameters.enable = false;      % 是否启用滤波
            obj.Parameters.filter_type = obj.MEAN_DOWNSAMPLE; % 默认使用均值降采样
            obj.Parameters.window = 5;          % 均值降采样窗口大小
            obj.Parameters.cutoff_freq = 0.01;  % 低通滤波截止频率(Hz)
            obj.Parameters.filter_order = 4;    % 低通滤波器阶数
        end
        
        function execute(obj)
            %EXECUTE 执行滤波处理
            obj.validateInputs();
            
            % 获取输入数据
            value = obj.Inputs.value;
            
            % 根据参数决定是否执行滤波
            if obj.Parameters.enable
                if obj.Parameters.filter_type == obj.MEAN_DOWNSAMPLE
                    % 均值降采样
                    filtered_value = obj.downsample_mean(value, round(obj.Parameters.window));
                else
                    % 低通滤波
                    fs = obj.Inputs.fs;
                    [b, a] = butter(obj.Parameters.filter_order, ...
                        obj.Parameters.cutoff_freq/(fs/2), 'low');
                    filtered_value = filtfilt(b, a, value);
                end
            else
                % 不滤波，直接传递原值
                filtered_value = value;
            end
            
            % 设置输出
            obj.Outputs.value = filtered_value;
            obj.Outputs.time = obj.Inputs.time;
            obj.Outputs.fs = obj.Inputs.fs;
            obj.Outputs.is_filtered = obj.Parameters.enable;
            obj.Outputs.filter_type = obj.Parameters.filter_type;
            
            if obj.Parameters.filter_type == obj.MEAN_DOWNSAMPLE
                obj.Outputs.filter_info = sprintf('均值降采样, 窗口=%d', obj.Parameters.window);
            else
                obj.Outputs.filter_info = sprintf('低通滤波, 截止频率=%.3fHz', obj.Parameters.cutoff_freq);
            end
            
            obj.IsExecuted = true;
        end
        
        function validateInputs(obj)
            %VALIDATEINPUTS 验证输入是否有效
            if ~isfield(obj.Inputs, 'value') || isempty(obj.Inputs.value)
                error('缺少输入数据: value');
            end
            
            if ~isfield(obj.Inputs, 'time') || isempty(obj.Inputs.time)
                error('缺少输入数据: time');
            end
            
            if ~isfield(obj.Inputs, 'fs') || isempty(obj.Inputs.fs)
                error('缺少输入数据: fs');
            end
            
            % 验证滤波参数
            if obj.Parameters.filter_type == obj.MEAN_DOWNSAMPLE
                if obj.Parameters.window < 1 || mod(obj.Parameters.window, 1) ~= 0
                    error('均值降采样窗口大小必须为正整数');
                end
            else
                fs = obj.Inputs.fs;
                if obj.Parameters.cutoff_freq <= 0 || obj.Parameters.cutoff_freq >= fs/2
                    error('低通滤波截止频率必须在(0, fs/2)范围内');
                end
                
                if obj.Parameters.filter_order < 1 || mod(obj.Parameters.filter_order, 1) ~= 0
                    error('滤波器阶数必须为正整数');
                end
            end
        end
    end
    
    methods (Access = private)
        function y = downsample_mean(~, x, window)
            %DOWNSAMPLE_MEAN 均值降采样函数
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
    end
end