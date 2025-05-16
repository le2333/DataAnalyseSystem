classdef ProcessorNode < handle
    %PROCESSORNODE 数据处理节点基类
    %   所有数据处理节点的基类，定义了节点的基本接口和属性
    
    properties
        Name = ''           % 节点名称
        Inputs = struct()   % 输入数据
        Outputs = struct()  % 输出数据
        Parameters = struct() % 节点参数
        IsExecuted = false  % 节点是否已执行
        Dependencies = {}   % 依赖的节点
    end
    
    methods
        function obj = ProcessorNode(name)
            %PROCESSORNODE 构造函数
            %   创建一个处理节点
            if nargin > 0
                obj.Name = name;
            else
                obj.Name = class(obj);
            end
        end
        
        function reset(obj)
            %RESET 重置节点状态
            %   清空输出并将执行状态设置为未执行
            obj.Outputs = struct();
            obj.IsExecuted = false;
        end
        
        function addDependency(obj, node)
            %ADDDEPENDENCY 添加依赖节点
            %   添加一个此节点依赖的节点
            if ~any(cellfun(@(n) n == node, obj.Dependencies))
                obj.Dependencies{end+1} = node;
            end
        end
        
        function setParameter(obj, name, value)
            %SETPARAMETER 设置节点参数
            %   设置指定名称的参数值
            obj.Parameters.(name) = value;
            % 修改参数后重置执行状态
            obj.reset();
        end
        
        function value = getParameter(obj, name)
            %GETPARAMETER 获取节点参数
            %   获取指定名称的参数值
            if isfield(obj.Parameters, name)
                value = obj.Parameters.(name);
            else
                value = [];
            end
        end
        
        function setInput(obj, name, value)
            %SETINPUT 设置输入数据
            %   设置指定名称的输入数据
            obj.Inputs.(name) = value;
            % 修改输入后重置执行状态
            obj.reset();
        end
        
        function value = getOutput(obj, name)
            %GETOUTPUT 获取输出数据
            %   获取指定名称的输出数据，如果节点未执行则先执行
            if ~obj.IsExecuted
                obj.execute();
            end
            
            if isfield(obj.Outputs, name)
                value = obj.Outputs.(name);
            else
                error('输出 %s 不存在', name);
            end
        end
        
        function execute(obj)
            %EXECUTE 执行节点
            %   执行节点的处理逻辑，子类必须重写此方法
            error('子类必须实现execute方法');
        end
        
        function validateInputs(obj)
            %VALIDATEINPUTS 验证输入是否有效
            %   检查必要的输入是否存在，子类可重写此方法
        end
    end
end