import numpy as np
import plotly.graph_objects as go
from typing import Dict, Optional, Any, Union
from core.node.base_node import BaseNode


class FrequencyDomainPlotNode(BaseNode):
    """频域图可视化节点，专注于频谱可视化"""

    def process(
        self,
        frequencies: np.ndarray,
        spectrum: np.ndarray,
        title: Optional[str] = "频域信号",
        x_axis_title: str = "频率 (Hz)",
        y_axis_title: str = "幅度",
        log_scale: bool = True,
        line_color: str = "blue",
        template: str = "plotly_white",
    ) -> Dict[str, Any]:
        """
        生成频域信号的交互式图表

        Args:
            frequencies: 频率数组
            spectrum: 频谱幅值
            title: 图表标题
            x_axis_title: X轴标题
            y_axis_title: Y轴标题
            log_scale: 是否使用对数频率轴
            line_color: 线条颜色
            template: Plotly模板

        Returns:
            Dict: 包含Plotly图表数据的字典
        """
        # 确保频率非零以便使用对数轴
        if log_scale and np.any(frequencies <= 0):
            # 过滤掉零和负频率
            valid_idx = frequencies > 0
            frequencies = frequencies[valid_idx]
            spectrum = (
                spectrum[valid_idx] if spectrum.ndim == 1 else spectrum[valid_idx, :]
            )

        # 创建频域图
        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=frequencies,
                y=spectrum,
                mode="lines",
                name="频谱",
                line=dict(color=line_color),
            )
        )

        # 设置对数刻度
        if log_scale:
            fig.update_xaxes(type="log")

        fig.update_layout(
            title=title,
            xaxis_title=x_axis_title,
            yaxis_title=y_axis_title,
            template=template,
            hovermode="closest",
        )

        # 优化布局
        fig.update_layout(
            autosize=True,
            margin=dict(l=50, r=50, t=50, b=50),
        )

        # 添加网格线
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor="lightgray")
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor="lightgray")

        # 返回图表数据
        return {
            "plot_type": "frequency_domain",
            "figure": fig.to_json(),
            "title": title,
        }
