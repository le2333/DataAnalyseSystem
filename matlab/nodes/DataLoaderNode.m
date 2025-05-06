classdef DataLoaderNode < ProcessorNode
    %DATALOADERNODE 数据加载节点
    %   负责加载原始数据文件并解析
    
    methods
        function obj = DataLoaderNode(name)
            %DATALOADERNODE 构造函数
            if nargin < 1
                name = 'DataLoader';
            end
            obj = obj@ProcessorNode(name);
            
            % 设置默认参数
            obj.Parameters.filename = '';
        end
        
        function execute(obj)
            %EXECUTE 执行数据加载
            obj.validateInputs();
            
            % 加载数据
            filename = obj.Parameters.filename;
            [time, value] = obj.load_and_parse_data(filename);
            
            % 计算采样率
            fs = 1/seconds(median(diff(time)));
            
            % 设置输出
            obj.Outputs.time = time;
            obj.Outputs.value = value;
            obj.Outputs.fs = fs;
            
            obj.IsExecuted = true;
        end
        
        function validateInputs(obj)
            %VALIDATEINPUTS 验证输入是否有效
            if isempty(obj.Parameters.filename)
                error('必须指定文件名');
            end
            
            if ~exist(obj.Parameters.filename, 'file')
                error('文件不存在: %s', obj.Parameters.filename);
            end
        end
    end
    
    methods (Access = private)
        function [time, value] = load_and_parse_data(~, filename)
            %LOAD_AND_PARSE_DATA 加载并解析数据文件
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
    end
end