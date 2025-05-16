classdef TimeFrequencyWorkflow < handle
    %TIMEFREQUENCYWORKFLOW 时频分析工作流
    %   整合数据加载、滤波、切片、频谱分析、瀑布图等节点，组成完整的处理流程
    
    properties
        WorkflowManager    % 工作流管理器
        DataLoader         % 数据加载节点
        Filter             % 滤波处理节点
        Slicer             % 切片处理节点
        Spectrum           % 频谱分析节点
        Waterfall          % 瀑布图处理节点
    end
    
    methods
        function obj = TimeFrequencyWorkflow()
            %TIMEFREQUENCYWORKFLOW 构造函数
            % 初始化工作流管理器
            obj.WorkflowManager = WorkflowManager();
            
            % 创建所有节点
            obj.createNodes();
            
            % 建立节点间的连接
            obj.setupConnections();
        end
        
        function createNodes(obj)
            %CREATENODES 创建所有处理节点
            % 数据加载节点
            obj.DataLoader = DataLoaderNode('DataLoader');
            obj.WorkflowManager.addNode(obj.DataLoader);
            
            % 滤波处理节点
            obj.Filter = FilterNode('Filter');
            obj.WorkflowManager.addNode(obj.Filter);
            
            % 切片处理节点
            obj.Slicer = SliceNode('Slicer');
            obj.WorkflowManager.addNode(obj.Slicer);
            
            % 频谱分析节点
            obj.Spectrum = SpectrumNode('Spectrum');
            obj.WorkflowManager.addNode(obj.Spectrum);
            
            % 瀑布图处理节点
            obj.Waterfall = WaterfallNode('Waterfall');
            obj.WorkflowManager.addNode(obj.Waterfall);
        end
        
        function setupConnections(obj)
            %SETUPCONNECTIONS 建立节点间的连接
            % 数据加载 -> 滤波
            obj.WorkflowManager.connect(obj.DataLoader, 'time', obj.Filter, 'time');
            obj.WorkflowManager.connect(obj.DataLoader, 'value', obj.Filter, 'value');
            obj.WorkflowManager.connect(obj.DataLoader, 'fs', obj.Filter, 'fs');
            
            % 滤波 -> 切片
            obj.WorkflowManager.connect(obj.Filter, 'time', obj.Slicer, 'time');
            obj.WorkflowManager.connect(obj.Filter, 'value', obj.Slicer, 'value');
            obj.WorkflowManager.connect(obj.Filter, 'fs', obj.Slicer, 'fs');
            
            % 切片 -> 频谱分析
            obj.WorkflowManager.connect(obj.Slicer, 'value', obj.Spectrum, 'value');
            obj.WorkflowManager.connect(obj.Slicer, 'fs', obj.Spectrum, 'fs');
            
            % 频谱分析 -> 瀑布图
            obj.WorkflowManager.connect(obj.Spectrum, 'P1_plot', obj.Waterfall, 'spectrum');
            obj.WorkflowManager.connect(obj.Slicer, 'time', obj.Waterfall, 'time_point');
        end
        
        function loadData(obj, filename)
            %LOADDATA 加载数据文件
            obj.DataLoader.setParameter('filename', filename);
            
            % 执行数据加载，触发工作流
            obj.execute();
        end
        
        function setSliceParameters(obj, duration_seconds, overlap_ratio)
            %SETSLICEPARAMETERS 设置切片参数
            obj.Slicer.setParameter('slice_duration', duration_seconds);
            obj.Slicer.setParameter('overlap_ratio', overlap_ratio);
            
            % 切片参数变化后，清空瀑布图历史
            obj.Waterfall.clearHistory();
            
            % 执行工作流
            obj.execute();
        end
        
        function setFilterParameters(obj, enable, filter_type, param)
            %SETFILTERPARAMETERS 设置滤波参数
            obj.Filter.setParameter('enable', enable);
            obj.Filter.setParameter('filter_type', filter_type);
            
            if filter_type == obj.Filter.MEAN_DOWNSAMPLE
                obj.Filter.setParameter('window', param);
            else
                obj.Filter.setParameter('cutoff_freq', param);
            end
            
            % 执行工作流
            obj.execute();
        end
        
        function setFrequencyRange(obj, freq_range)
            %SETFREQUENCYRANGE 设置频率分析范围
            obj.Spectrum.setParameter('freq_range', freq_range);
            
            % 频率范围变化后，清空瀑布图历史
            obj.Waterfall.clearHistory();
            
            % 执行工作流
            obj.execute();
        end
        
        function setWaterfallHistorySize(obj, size)
            %SETWATERFALLHISTORYSIZE 设置瀑布图历史大小
            obj.Waterfall.setHistorySize(size);
            
            % 执行工作流
            obj.execute();
        end
        
        function setCurrentSlice(obj, slice_idx)
            %SETCURRENTSLICE 设置当前切片
            obj.Slicer.setCurrentSlice(slice_idx);
            
            % 执行工作流
            obj.execute();
        end
        
        function execute(obj)
            %EXECUTE 执行整个工作流
            obj.WorkflowManager.execute();
        end
        
        function reset(obj)
            %RESET 重置工作流
            obj.WorkflowManager.reset();
        end
        
        % 获取各种输出数据的访问方法
        function data = getSliceData(obj)
            %GETSLICEDATA 获取当前切片的时域数据
            data.time = obj.Slicer.getOutput('time');
            data.value = obj.Slicer.getOutput('value');
            data.time_range_str = obj.Slicer.getOutput('slice_time_range');
            data.current_slice = obj.Slicer.getOutput('current_slice');
            data.num_slices = obj.Slicer.getOutput('num_slices');
            
            % 添加滤波信息
            if obj.Filter.getOutput('is_filtered')
                data.filter_info = obj.Filter.getOutput('filter_info');
            else
                data.filter_info = '';
            end
        end
        
        function data = getSpectrumData(obj)
            %GETSPECTRUMDATA 获取频谱分析数据
            data.f_plot = obj.Spectrum.getOutput('f_plot');
            data.P1_plot = obj.Spectrum.getOutput('P1_plot');
            data.freq_range = obj.Spectrum.getOutput('freq_range');
        end
        
        function data = getWaterfallData(obj)
            %GETWATERFALLDATA 获取瀑布图数据
            data.history = obj.Waterfall.getOutput('history');
            data.times = obj.Waterfall.getOutput('times');
            data.size = obj.Waterfall.getOutput('size');
            data.log_history = obj.Waterfall.getOutput('log_history');
        end
        
        function data = getSliceSettings(obj)
            %GETSLICESETTINGS 获取切片设置
            data.slice_duration = obj.Slicer.getParameter('slice_duration');
            data.overlap_ratio = obj.Slicer.getParameter('overlap_ratio');
            data.slice_start_times = obj.Slicer.getOutput('slice_start_times');
            data.slice_points = obj.Slicer.getOutput('slice_points');
            data.step_points = obj.Slicer.getOutput('step_points');
        end
        
        function data = getFilterSettings(obj)
            %GETFILTERSETTINGS 获取滤波设置
            data.enable = obj.Filter.getParameter('enable');
            data.filter_type = obj.Filter.getParameter('filter_type');
            data.window = obj.Filter.getParameter('window');
            data.cutoff_freq = obj.Filter.getParameter('cutoff_freq');
            data.filter_order = obj.Filter.getParameter('filter_order');
        end
        
        function fs = getSamplingRate(obj)
            %GETSAMPLINGRATE 获取采样率
            fs = obj.DataLoader.getOutput('fs');
        end
    end
end