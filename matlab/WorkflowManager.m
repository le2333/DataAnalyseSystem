classdef WorkflowManager < handle
    %WORKFLOWMANAGER 工作流管理器
    %   管理数据处理节点之间的连接和执行流程
    
    properties
        Nodes = {}        % 所有节点
        Connections = []  % 节点间的连接
        IsExecuted = false % 工作流是否已执行
    end
    
    methods
        function obj = WorkflowManager()
            %WORKFLOWMANAGER 构造函数
            %   创建一个新的工作流管理器
            obj.Connections = struct('SourceNode', {}, 'SourceOutput', {}, ...
                'TargetNode', {}, 'TargetInput', {});
        end
        
        function addNode(obj, node)
            %ADDNODE 添加节点到工作流
            %   将一个处理节点添加到工作流中
            if ~isa(node, 'ProcessorNode')
                error('节点必须是ProcessorNode的子类');
            end
            
            % 检查是否已存在同名节点
            for i = 1:length(obj.Nodes)
                if strcmp(obj.Nodes{i}.Name, node.Name)
                    error('已存在同名节点: %s', node.Name);
                end
            end
            
            obj.Nodes{end+1} = node;
            obj.IsExecuted = false;
        end
        
        function connect(obj, sourceNode, sourceOutput, targetNode, targetInput)
            %CONNECT 连接两个节点
            %   将源节点的输出连接到目标节点的输入
            
            % 确保节点在工作流中
            if ~any(cellfun(@(n) n == sourceNode, obj.Nodes))
                error('源节点不在工作流中');
            end
            if ~any(cellfun(@(n) n == targetNode, obj.Nodes))
                error('目标节点不在工作流中');
            end
            
            % 添加连接
            connection = struct(...
                'SourceNode', sourceNode, ...
                'SourceOutput', sourceOutput, ...
                'TargetNode', targetNode, ...
                'TargetInput', targetInput);
            
            obj.Connections(end+1) = connection;
            
            % 添加依赖关系
            targetNode.addDependency(sourceNode);
            
            obj.IsExecuted = false;
        end
        
        function execute(obj)
            %EXECUTE 执行工作流
            %   按拓扑排序执行所有节点
            
            % 重置所有节点
            for i = 1:length(obj.Nodes)
                obj.Nodes{i}.reset();
            end
            
            % 获取执行顺序
            executionOrder = obj.getExecutionOrder();
            
            % 执行每个节点
            for i = 1:length(executionOrder)
                node = executionOrder{i};
                
                % 更新节点间的数据连接
                obj.updateNodeInputs(node);
                
                % 执行节点
                if ~node.IsExecuted
                    node.execute();
                end
            end
            
            obj.IsExecuted = true;
        end
        
        function reset(obj)
            %RESET 重置工作流
            %   重置工作流中所有节点的状态
            for i = 1:length(obj.Nodes)
                obj.Nodes{i}.reset();
            end
            obj.IsExecuted = false;
        end
        
        function node = getNodeByName(obj, name)
            %GETNODEBYNAME 通过名称获取节点
            %   获取指定名称的节点
            for i = 1:length(obj.Nodes)
                if strcmp(obj.Nodes{i}.Name, name)
                    node = obj.Nodes{i};
                    return;
                end
            end
            error('未找到名为 %s 的节点', name);
        end
        
        function data = getNodeOutput(obj, nodeName, outputName)
            %GETNODEOUTPUT 获取节点输出
            %   获取指定节点的指定输出
            
            % 如果工作流未执行，先执行
            if ~obj.IsExecuted
                obj.execute();
            end
            
            % 获取节点
            node = obj.getNodeByName(nodeName);
            
            % 获取输出
            data = node.getOutput(outputName);
        end
        
        function removeConnection(obj, sourceNode, sourceOutput, targetNode, targetInput)
            %REMOVECONNECTION 移除节点间的连接
            %   移除指定的连接
            for i = 1:length(obj.Connections)
                conn = obj.Connections(i);
                if conn.SourceNode == sourceNode && ...
                        strcmp(conn.SourceOutput, sourceOutput) && ...
                        conn.TargetNode == targetNode && ...
                        strcmp(conn.TargetInput, targetInput)
                    % 移除连接
                    obj.Connections(i) = [];
                    
                    % 更新依赖关系
                    % 这里需要更全面的依赖管理，简化版只检查是否还有其他连接
                    hasDependency = false;
                    for j = 1:length(obj.Connections)
                        if obj.Connections(j).SourceNode == sourceNode && ...
                                obj.Connections(j).TargetNode == targetNode
                            hasDependency = true;
                            break;
                        end
                    end
                    
                    if ~hasDependency
                        % 移除依赖关系，找到依赖索引并删除
                        deps = targetNode.Dependencies;
                        for j = 1:length(deps)
                            if deps{j} == sourceNode
                                targetNode.Dependencies(j) = [];
                                break;
                            end
                        end
                    end
                    
                    obj.IsExecuted = false;
                    return;
                end
            end
            warning('未找到指定的连接');
        end
    end
    
    methods (Access = private)
        function updateNodeInputs(obj, node)
            %UPDATENODEINPUTS 更新节点的输入数据
            %   根据连接关系，将源节点的输出设置为目标节点的输入
            for i = 1:length(obj.Connections)
                conn = obj.Connections(i);
                if conn.TargetNode == node
                    % 确保源节点已执行
                    if ~conn.SourceNode.IsExecuted
                        conn.SourceNode.execute();
                    end
                    
                    % 获取源节点输出
                    sourceOutput = conn.SourceNode.getOutput(conn.SourceOutput);
                    
                    % 设置目标节点输入
                    node.setInput(conn.TargetInput, sourceOutput);
                end
            end
        end
        
        function executionOrder = getExecutionOrder(obj)
            %GETEXECUTIONORDER 获取节点的执行顺序
            %   使用拓扑排序算法获取节点的执行顺序
            
            % 创建临时变量存储节点和其入度
            nodeCount = length(obj.Nodes);
            inDegree = zeros(1, nodeCount);
            
            % 计算每个节点的入度（依赖数量）
            for i = 1:nodeCount
                inDegree(i) = length(obj.Nodes{i}.Dependencies);
            end
            
            % 拓扑排序
            executionOrder = {};
            while ~isempty(executionOrder) || length(executionOrder) < nodeCount
                % 查找入度为0的节点
                zeroInDegree = find(inDegree == 0);
                
                % 如果没有入度为0的节点但还有节点未处理，说明有环
                if isempty(zeroInDegree) && length(executionOrder) < nodeCount
                    error('工作流中存在环，无法确定执行顺序');
                end
                
                % 将入度为0的节点添加到执行顺序中
                for i = 1:length(zeroInDegree)
                    nodeIndex = zeroInDegree(i);
                    executionOrder{end+1} = obj.Nodes{nodeIndex};
                    inDegree(nodeIndex) = -1; % 标记为已处理
                    
                    % 减少依赖此节点的节点的入度
                    for j = 1:nodeCount
                        if any(cellfun(@(n) n == obj.Nodes{nodeIndex}, obj.Nodes{j}.Dependencies))
                            inDegree(j) = inDegree(j) - 1;
                        end
                    end
                end
                
                % 如果所有节点都已处理，退出循环
                if all(inDegree == -1)
                    break;
                end
            end
            
            % 如果还有未处理的节点（可能是孤立的），按原顺序添加
            for i = 1:nodeCount
                if inDegree(i) >= 0
                    executionOrder{end+1} = obj.Nodes{i};
                end
            end
        end
    end
end