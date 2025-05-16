classdef WaterfallNode < ProcessorNode
    %WATERFALLNODE 瀑布图处理节点
    %   存储和管理频谱历史数据，用于生成瀑布图
    
    methods
        function obj = WaterfallNode(name)
            %WATERFALLNODE 构造函数
            if nargin < 1
                name = 'Waterfall';
            end
            obj = obj@ProcessorNode(name);
            
            % 设置默认参数
            obj.Parameters.history_size = 20;  % 历史数据大小
            
            % 初始化存储
            obj.Parameters.history = [];       % 频谱历史数据
            obj.Parameters.times = [];         % 对应的时间点
        end
        
        function execute(obj)
            %EXECUTE 执行瀑布图处理
            obj.validateInputs();
            
            % 获取输入数据
            spectrum = obj.Inputs.spectrum;
            time_point = obj.Inputs.time_point;
            
            % 更新历史数据
            obj.update_history(spectrum, time_point);
            
            % 设置输出
            obj.Outputs.history = obj.Parameters.history;
            obj.Outputs.times = obj.Parameters.times;
            obj.Outputs.size = size(obj.Parameters.history, 1);
            obj.Outputs.log_history = log10(obj.Parameters.history); % 对数转换后的数据
            
            obj.IsExecuted = true;
        end
        
        function validateInputs(obj)
            %VALIDATEINPUTS 验证输入是否有效
            if ~isfield(obj.Inputs, 'spectrum') || isempty(obj.Inputs.spectrum)
                error('缺少输入数据: spectrum');
            end
            
            if ~isfield(obj.Inputs, 'time_point') || isempty(obj.Inputs.time_point)
                error('缺少输入数据: time_point');
            end
            
            % 验证参数
            if obj.Parameters.history_size < 2
                error('历史大小必须大于等于2');
            end
        end
        
        function clearHistory(obj)
            %CLEARHISTORY 清除历史数据
            obj.Parameters.history = [];
            obj.Parameters.times = [];
            obj.reset();
        end
        
        function setHistorySize(obj, size)
            %SETHISTORYSIZE 设置历史数据大小
            if size < 2
                error('历史大小必须大于等于2');
            end
            
            obj.Parameters.history_size = size;
            
            % 如果当前历史数据超过新的大小限制，则裁剪
            if ~isempty(obj.Parameters.history) && ...
                    size(obj.Parameters.history, 1) > size
                obj.Parameters.history = obj.Parameters.history(end-size+1:end, :);
                obj.Parameters.times = obj.Parameters.times(end-size+1:end);
            end
            
            obj.reset();
        end
    end
    
    methods (Access = private)
        function update_history(obj, spectrum, time_point)
            %UPDATE_HISTORY 更新历史数据
            % 如果历史为空，初始化
            if isempty(obj.Parameters.history)
                obj.Parameters.history = zeros(1, length(spectrum));
                obj.Parameters.times = time_point;
            end
            
            % 添加新数据
            obj.Parameters.history = [obj.Parameters.history; spectrum'];
            obj.Parameters.times = [obj.Parameters.times; time_point];
            
            % 如果历史数据超过设定的大小，则移除最早的数据
            if size(obj.Parameters.history, 1) > obj.Parameters.history_size
                obj.Parameters.history = obj.Parameters.history(end-obj.Parameters.history_size+1:end, :);
                obj.Parameters.times = obj.Parameters.times(end-obj.Parameters.history_size+1:end);
            end
        end
    end
end