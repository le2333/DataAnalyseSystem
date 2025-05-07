#!/usr/bin/env python3
"""时频分析工作流定义"""
import os
import sys

# 添加项目根目录到Python路径，确保能找到所有模块
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(current_file))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from prefect import flow
from nodes.io.load_data_node import LoadDataNode
from nodes.analysis.slice_node import SliceNode
from nodes.analysis.stft_node import STFTNode
from nodes.analysis.cwt_node import CWTNode
from nodes.analysis.filter_node import FilterNode
from nodes.Visualization.time_domain_plot_node import TimeDomainPlotNode
from nodes.Visualization.frequency_domain_plot_node import FrequencyDomainPlotNode
from nodes.Visualization.time_frequency_plot_node import TimeFrequencyPlotNode
from nodes.Visualization.waterfall_plot_node import WaterfallPlotNode

# 需要导入numpy来处理瀑布图数据
import numpy as np
import os

@flow(name="时频分析工作流")
def time_frequency_workflow(
    file_path: str,
    window_duration: float = 24*60*60,  # 24小时
    overlap_ratio: float = 0.5,         # 50%重叠
    freq_range: tuple = (0, 0.001),     # 频率范围
    analysis_method: str = 'stft',      # 分析方法, 'stft'或'cwt'
    slice_index: int = 0,               # 要分析的切片，-1表示全部
    filter_type: str = None,            # 滤波类型，'mean', 'lowpass'或None（不滤波）
    filter_param: float = 5,            # 滤波参数
    wavelet_type: str = 'morl'          # 小波类型 (仅用于CWT)
):
    """
    执行时频分析工作流
    
    Args:
        file_path: 数据文件路径
        window_duration: 窗口长度（秒）
        overlap_ratio: 重叠比例 [0,1)
        freq_range: 频率范围 (Hz)
        analysis_method: 分析方法 ('stft' 或 'cwt')
        slice_index: 要分析的切片，-1表示全部
        filter_type: 滤波类型，'mean', 'lowpass'或None（不滤波）
        filter_param: 滤波参数
        wavelet_type: 小波类型，如 'morl'(Morlet小波)，'mexh'(墨西哥帽小波)等
        
    Returns:
        Dict: 包含可视化结果的字典
    """
    # 创建节点
    load_node = LoadDataNode(name="数据加载")
    slice_node = SliceNode(name="数据切片", window_duration=window_duration, overlap_ratio=overlap_ratio)
    
    # 转换为Prefect任务
    load_task = load_node.as_task()
    slice_task = slice_node.as_task()
    
    # 执行数据加载
    time_array, value_array = load_task(file_path)
    
    # 如果需要滤波
    if filter_type:
        filter_node = FilterNode(name="数据滤波", filter_type=filter_type, filter_param=filter_param)
        filter_task = filter_node.as_task()
        time_array, value_array = filter_task(time_array, value_array)
    
    # 数据切片
    slice_data = slice_task(time_array, value_array)
    
    # 根据选择的分析方法创建相应节点
    if analysis_method.lower() == 'stft':
        tf_node = STFTNode(name="STFT分析", freq_range=freq_range, slice_index=slice_index)
    elif analysis_method.lower() == 'cwt':
        tf_node = CWTNode(name="小波分析", freq_range=freq_range, 
                          slice_index=slice_index, wavelet=wavelet_type)
    else:
        raise ValueError(f"不支持的分析方法: {analysis_method}")
    
    tf_task = tf_node.as_task()
    tf_result = tf_task(slice_data)
    
    # 创建时频图可视化
    tf_plot_node = TimeFrequencyPlotNode(name="时频图")
    tf_plot_task = tf_plot_node.as_task()
    
    # 根据tf_result的结构选择正确的参数
    if isinstance(tf_result["spectrograms"], list):
        # 多个切片情况
        spectrogram = tf_result["spectrograms"][0]  # 仅可视化第一个
    else:
        # 单个切片情况
        spectrogram = tf_result["spectrograms"]
    
    tf_plot = tf_plot_task(
        frequencies=tf_result["frequencies"],
        times=tf_result["times"] if not isinstance(tf_result["times"], list) else tf_result["times"][0],
        spectrogram=spectrogram
    )
    
    results = {
        "time_frequency": tf_plot,
        "slice_data": slice_data
    }
    
    # 如果处理了所有切片，则创建瀑布图
    if slice_index == -1 and isinstance(tf_result["spectrograms"], list):
        waterfall_node = WaterfallPlotNode(name="瀑布图")
        waterfall_task = waterfall_node.as_task()
        
        # 准备瀑布图数据
        waterfall_spectrograms = np.array([spec for spec in tf_result["spectrograms"]])
        
        waterfall_plot = waterfall_task(
            frequencies=tf_result["frequencies"],
            slice_times=tf_result["slice_times"],
            spectrograms=waterfall_spectrograms
        )
        
        results["waterfall"] = waterfall_plot
    
    # 添加时域图
    time_plot_node = TimeDomainPlotNode(name="时域图")
    time_plot_task = time_plot_node.as_task()
    
    # 选择当前切片数据来绘制时域图
    if slice_index >= 0 and slice_index < len(slice_data["slices"]):
        current_slice = slice_data["slices"][slice_index]
        time_plot = time_plot_task(time_array=current_slice[0], value_array=current_slice[1])
        results["time_domain"] = time_plot
    else:
        # 或者绘制完整的时域图
        time_plot = time_plot_task(time_array=time_array, value_array=value_array)
        results["time_domain"] = time_plot
    
    # 添加频域图（从时频图提取一个特定时间点的频谱）
    if tf_result["method"] == "stft":
        # 从STFT结果中提取中间时间点的频谱
        mid_time_idx = spectrogram.shape[1] // 2
        spectrum = spectrogram[:, mid_time_idx]
        
        freq_plot_node = FrequencyDomainPlotNode(name="频域图")
        freq_plot_task = freq_plot_node.as_task()
        
        freq_plot = freq_plot_task(
            frequencies=tf_result["frequencies"],
            spectrum=spectrum
        )
        
        results["frequency_domain"] = freq_plot
    
    return results

# 简单的运行示例
if __name__ == "__main__":
    # 查找实际存在的数据文件
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "sat1")
    data_files = os.listdir(data_dir)
    
    if data_files:
        # 使用找到的第一个文件
        example_file = os.path.join(data_dir, data_files[0])
        print(f"使用示例数据文件: {example_file}")
        
        # 示例：运行STFT分析
        print("\n运行STFT分析...")
        result_stft = time_frequency_workflow(
            file_path=example_file,
            window_duration=1*60*60,  # 1小时
            overlap_ratio=0.5,
            freq_range=(0, 0.001),
            analysis_method='stft',
            slice_index=0,
            filter_type='lowpass',  # 可选: 'mean', 'lowpass', None
            filter_param=0.01  # 低通滤波的截止频率 (Hz)
        )
        print(f"STFT分析完成，生成了 {len(result_stft)} 个结果")
        
        # 示例：运行CWT分析
        print("\n运行CWT分析...")
        result_cwt = time_frequency_workflow(
            file_path=example_file,
            window_duration=1*60*60,  # 1小时
            overlap_ratio=0.5,
            freq_range=(0, 0.001),
            analysis_method='cwt',
            slice_index=0,
            filter_type='lowpass',
            filter_param=0.01,
            wavelet_type='morl'  # 使用Morlet小波
        )
        print(f"CWT分析完成，生成了 {len(result_cwt)} 个结果")
    else:
        print(f"在 {data_dir} 中未找到数据文件") 