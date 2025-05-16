classdef SpectrumNode < ProcessorNode
    %SPECTRUMNODE 频谱分析节点
    %   计算输入信号的频谱，支持Zoom FFT功能
    
    methods
        function obj = SpectrumNode(name)
            %SPECTRUMNODE 构造函数
            if nargin < 1
                name = 'Spectrum';
            end
            obj = obj@ProcessorNode(name);
            
            % 设置默认参数
            obj.Parameters.freq_range = [0, 0.001]; % 频率范围 [Hz]
            obj.Parameters.fft_size_factor = 8;     % FFT大小倍数（相对于信号长度的2的幂次方）
        end
        
        function execute(obj)
            %EXECUTE 执行频谱分析
            obj.validateInputs();
            
            % 获取输入数据
            value = obj.Inputs.value;
            fs = obj.Inputs.fs;
            
            % 去除直流分量
            value = value - mean(value);
            
            % 计算频谱
            [f_plot, P1_plot] = obj.calculate_spectrum(value, fs);
            
            % 设置输出
            obj.Outputs.f_plot = f_plot;      % 频率数组
            obj.Outputs.P1_plot = P1_plot;    % 幅值谱
            obj.Outputs.freq_range = obj.Parameters.freq_range; % 频率范围
            
            obj.IsExecuted = true;
        end
        
        function validateInputs(obj)
            %VALIDATEINPUTS 验证输入是否有效
            if ~isfield(obj.Inputs, 'value') || isempty(obj.Inputs.value)
                error('缺少输入数据: value');
            end
            
            if ~isfield(obj.Inputs, 'fs') || isempty(obj.Inputs.fs)
                error('缺少输入数据: fs');
            end
            
            % 验证频率范围
            if length(obj.Parameters.freq_range) ~= 2 || ...
                    obj.Parameters.freq_range(1) < 0 || ...
                    obj.Parameters.freq_range(2) <= obj.Parameters.freq_range(1) || ...
                    obj.Parameters.freq_range(2) > obj.Inputs.fs/2
                error('频率范围必须为[fmin, fmax]，其中0 <= fmin < fmax <= fs/2');
            end
        end
    end
    
    methods (Access = private)
        function [f_plot, P1_plot] = calculate_spectrum(obj, value, fs)
            %CALCULATE_SPECTRUM 计算频谱
            % 获取信号长度
            N = length(value);
            
            % 计算中心频率
            center_freq = (obj.Parameters.freq_range(1) + obj.Parameters.freq_range(2)) / 2;
            
            % 实现ZoomFFT - 放大低频区域
            % 1. 生成时间向量
            t_vec = (0:N-1)' / fs;
            
            % 2. 将信号搬移到中心频率
            shifted_signal = value .* exp(-1i * 2 * pi * center_freq * t_vec);
            
            % 3. 对搬移信号进行FFT
            N_fft = 2^nextpow2(N) * obj.Parameters.fft_size_factor;
            Y = fft(shifted_signal, N_fft);
            
            % 4. 计算新频率向量（放大后的频率区间）
            freq_zoom = fs/N_fft * (-(N_fft/2):(N_fft/2-1)) + center_freq;
            
            % 5. 重新排列结果以获得正确顺序
            Y = fftshift(Y);
            
            % 6. 计算幅值谱
            P_zoom = abs(Y)/N;
            
            % 7. 选择感兴趣的频率范围
            idx = (freq_zoom >= obj.Parameters.freq_range(1)) & ...
                (freq_zoom <= obj.Parameters.freq_range(2));
            f_plot = freq_zoom(idx);
            P1_plot = P_zoom(idx);
            
            % 8. 避免对数坐标下的零值问题
            f_plot = max(f_plot, eps); % 确保没有零频率
            P1_plot = max(P1_plot, eps); % 确保没有零幅值
        end
    end
end