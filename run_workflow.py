#!/usr/bin/env python3
"""
时频分析工作流启动脚本
确保Python能正确导入所有模块
"""
import os
import sys
import argparse

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# 导入工作流
from workflows.time_frequency_workflow import time_frequency_workflow

def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description='时频分析工作流')
    parser.add_argument('--method', type=str, choices=['stft', 'cwt'], default='stft',
                       help='分析方法: stft (短时傅里叶变换) 或 cwt (连续小波变换)')
    parser.add_argument('--window', type=float, default=3600,
                       help='窗口长度（秒），默认为1小时')
    parser.add_argument('--overlap', type=float, default=0.5,
                       help='重叠比例 [0-1)，默认为0.5')
    parser.add_argument('--filter', type=str, choices=['mean', 'lowpass', 'none'], default='lowpass',
                       help='滤波类型：mean (均值降采样)，lowpass (低通滤波)，none (不滤波)')
    parser.add_argument('--filter-param', type=float, default=0.01,
                       help='滤波参数，对于低通滤波是截止频率(Hz)，对于均值降采样是窗口大小')
    parser.add_argument('--wavelet', type=str, default='morl',
                       help='小波类型 (仅用于CWT)，如morl、mexh、gaus8等')
    parser.add_argument('--slice-index', type=int, default=0,
                       help='要分析的切片索引，-1表示所有切片')
    
    args = parser.parse_args()
    
    # 查找实际存在的数据文件
    data_dir = os.path.join(current_dir, "data", "sat1")
    
    if not os.path.exists(data_dir):
        print(f"错误: 数据目录 {data_dir} 不存在")
        return
    
    data_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    
    if not data_files:
        print(f"错误: 在 {data_dir} 中未找到CSV文件")
        return
    
    # 使用找到的第一个文件
    example_file = os.path.join(data_dir, data_files[0])
    print(f"使用示例数据文件: {example_file}")
    
    # 设置滤波类型
    filter_type = None if args.filter == 'none' else args.filter
    
    # 运行工作流
    print(f"开始执行时频分析工作流 (方法: {args.method})...")
    result = time_frequency_workflow(
        file_path=example_file,
        window_duration=args.window,
        overlap_ratio=args.overlap,
        freq_range=(0, 0.001),
        analysis_method=args.method,
        slice_index=args.slice_index,
        filter_type=filter_type,
        filter_param=args.filter_param,
        wavelet_type=args.wavelet
    )
    print(f"工作流执行完成，生成了 {len(result)} 个结果")
    
    # 输出结果中包含的图表类型
    print("生成的图表类型:")
    for key in result:
        if key != "slice_data":  # 排除非图表数据
            print(f"- {key}")

if __name__ == "__main__":
    main() 