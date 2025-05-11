import numpy as np
import plotly.graph_objects as go
from typing import Dict, Optional, Any, Union, List
from core.node.base_node import BaseNode


class WaterfallPlotNode(BaseNode):
    """瀑布图可视化节点，专注于频谱瀑布图可视化"""

    def process(
        self,
        frequencies: np.ndarray,
        slice_times: List,  # 可以是时间戳或字符串列表
        spectrograms: np.ndarray,  # 形状为(时间切片数, 频率点数)或3D数组
        title: Optional[str] = "频谱瀑布图",
        x_axis_title: str = "频率 (Hz)",
        y_axis_title: str = "时间",
        log_scale: bool = True,
        colorscale: str = "Jet",
        template: str = "plotly_white",
    ) -> Dict[str, Any]:
        """
        生成频谱瀑布图的交互式图表

        Args:
            frequencies: 频率数组
            slice_times: 时间切片的时间点列表
            spectrograms: 多个切片的频谱数据
            title: 图表标题
            x_axis_title: X轴标题
            y_axis_title: Y轴标题
            log_scale: 是否使用对数频率轴和幅值
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

            # 调整spectrograms维度，根据其实际形状
            if spectrograms.ndim == 2:  # (时间切片数, 频率点数)
                spectrograms = spectrograms[:, valid_idx]
            elif spectrograms.ndim == 3:  # (时间切片数, 频率点数, ...)
                spectrograms = spectrograms[:, valid_idx, :]

        # 转换时间标签为字符串
        time_labels = [str(t) for t in slice_times]

        # 处理spectrograms的维度
        if spectrograms.ndim == 3:
            # 如果是3D，转换为2D (计算每个频率点的均值或最大值)
            spectrograms = np.mean(spectrograms, axis=2)

        # 获取非零的最小值
        non_zero_min = (
            np.min(spectrograms[spectrograms > 0])
            if np.any(spectrograms > 0)
            else 1e-10
        )

        # 应用对数变换增强可见性
        if log_scale:
            z_data = np.log10(np.maximum(spectrograms, non_zero_min))
        else:
            z_data = spectrograms

        # 创建瀑布图（使用热图表示）
        fig = go.Figure()

        fig.add_trace(
            go.Heatmap(
                z=z_data,
                x=frequencies,
                y=time_labels,
                colorscale=colorscale,
                colorbar=dict(title="幅值" + (" (log10)" if log_scale else "")),
            )
        )

        # 设置频率轴为对数刻度
        if log_scale:
            fig.update_xaxes(type="log")

        # 反转Y轴，使最新的数据在底部
        fig.update_layout(yaxis=dict(autorange="reversed"))

        fig.update_layout(
            title=title,
            xaxis_title=x_axis_title,
            yaxis_title=y_axis_title,
            template=template,
        )

        # 优化布局
        fig.update_layout(
            autosize=True,
            margin=dict(l=50, r=50, t=50, b=50),
        )

        # 返回图表数据
        return {"plot_type": "waterfall", "figure": fig.to_json(), "title": title}
