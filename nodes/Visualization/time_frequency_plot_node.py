import numpy as np
import plotly.graph_objects as go
from typing import Dict, Optional, Any, Union
from core.node.base_node import BaseNode

class TimeFrequencyPlotNode(BaseNode):
    """时频图可视化节点，专注于时频谱图可视化"""
    
    def process(
        self,
        frequencies: np.ndarray,
        times: np.ndarray,
        spectrogram: np.ndarray,
        title: Optional[str] = "时频图",
        x_axis_title: str = "时间 (秒)",
        y_axis_title: str = "频率 (Hz)",
        log_scale: bool = True,
        colorscale: str = "Jet",
        template: str = "plotly_white"
    ) -> Dict[str, Any]:
        """
        生成时频谱图的交互式图表
        
        Args:
            frequencies: 频率数组
            times: 时间数组
            spectrogram: 时频谱图数据，形状为(频率点数, 时间点数)
            title: 图表标题
            x_axis_title: X轴标题
            y_axis_title: Y轴标题
            log_scale: 是否使用对数频率轴
            colorscale: 热图颜色映射
            template: Plotly模板
            
        Returns:
            Dict: 包含Plotly图表数据的字典
        """
        # 确保频率非零以便使用对数轴
        if log_scale and np.any(frequencies <= 0):
            # 过滤掉零和负频率
            valid_idx = frequencies > 0
            frequencies = frequencies[valid_idx]
            spectrogram = spectrogram[valid_idx, :] if spectrogram.shape[0] == len(frequencies) else spectrogram
        
        # 获取非零的最小值作为颜色映射的最小值，避免对数为负无穷
        non_zero_min = np.min(spectrogram[spectrogram > 0]) if np.any(spectrogram > 0) else 1e-10
        
        # 创建时频热图
        fig = go.Figure()
        
        # 使用对数刻度进行可视化以增强对比度
        if np.all(spectrogram >= 0):  # 确保全部为正
            z_data = np.log10(np.maximum(spectrogram, non_zero_min))
        else:
            z_data = spectrogram  # 如果有负值，则使用原始数据
            
        fig.add_trace(go.Heatmap(
            z=z_data,
            x=times,
            y=frequencies,
            colorscale=colorscale,
            colorbar=dict(title="幅值 (log10)"),
        ))
        
        # 设置频率轴为对数刻度
        if log_scale:
            fig.update_yaxes(type="log")
        
        fig.update_layout(
            title=title,
            xaxis_title=x_axis_title,
            yaxis_title=y_axis_title,
            template=template
        )
        
        # 优化布局
        fig.update_layout(
            autosize=True,
            margin=dict(l=50, r=50, t=50, b=50),
        )
        
        # 返回图表数据
        return {
            "plot_type": "time_frequency",
            "figure": fig.to_json(),
            "title": title
        } 