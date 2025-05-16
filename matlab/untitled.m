% 1. 加载数据
filename = '..\data\raw\sat3\5_2025031706435044765.csv';
[time, value] = load_and_parse_data(filename);

% 4. 计算采样率
fs = 1/seconds(median(diff(time))); % 采样率（假设等间隔采样）
% 5. 以一天为窗口做全年STFT（不重叠）
period = 1*60*60;

window_len = period; % 窗口长度
win = round(period*fs); % 窗口采样点数

% 7. 绘制全年时频谱
figure;
subplot(2,1,1); % CWT
[cfs, freq_cwt] = cwt(value, fs);
t_cwt = (0:length(value)-1)/fs/86400; % 换算为天
imagesc(t_cwt, freq_cwt, abs(cfs));
axis xy;
xlabel('天');
ylabel('频率 (Hz)');
title('全年小波时频谱');
colorbar;

subplot(2,1,2); % STFT
[s_val, f_stft, t_stft] = stft(value, fs, 'Window', hamming(win), 'OverlapLength', 0, 'FFTLength', win);
imagesc(t_stft/86400, f_stft, abs(s_val));
axis xy;
xlabel('天');
ylabel('频率 (Hz)');
title('全年STFT时频谱');
colorbar;

