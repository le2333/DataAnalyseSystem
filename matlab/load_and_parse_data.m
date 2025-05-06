function [time, value] = load_and_parse_data(filename)
% LOAD_AND_PARSE_DATA 从CSV文件加载并解析时间序列数据
%   [time, value] = LOAD_AND_PARSE_DATA(filename) 从指定的CSV文件加载数据。
%   文件应包含两列：第一列为时间戳 (yyyy-MM-dd HH:mm:ss.SSS)，
%   第二列为数值。函数返回排序后的时间和对应的数值。

opts = delimitedTextImportOptions('NumVariables', 2);
opts.DataLines = 1; % 无表头
opts.Delimiter = ',';
opts.VariableTypes = {'string', 'double'};
T = readtable(filename, opts);

% 解析时间戳
time_str = T{:,1};
time = datetime(time_str, 'InputFormat', 'yyyy-MM-dd HH:mm:ss.SSS');
value = T{:,2};

% 按时间排序
[time, sort_idx] = sort(time);
value = value(sort_idx);

end