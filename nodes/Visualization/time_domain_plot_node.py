import numpy as np
import plotly.graph_objects as go
from typing import Dict, Optional, Any
from core.node.base_node import BaseNode

class TimeDomainPlotNode(BaseNode):
    """时域图可视化节点，专注于时域信号可视化"""
    
    def process(
        self,
        time_array: np.ndarray,
        value_array: np.ndarray,
        title: Optional[str] = "时域信号",
        x_axis_title: str = "时间",
        y_axis_title: str = "幅度",
        line_color: str = "blue",
        template: str = "plotly_white"
    ) -> Dict[str, Any]:
        """
        生成时域信号的交互式图表
        
        Args:
            time_array: 时间数组
            value_array: 值数组
            title: 图表标题
            x_axis_title: X轴标题
            y_axis_title: Y轴标题
            line_color: 线条颜色
            template: Plotly模板
            
        Returns:
            Dict: 包含Plotly图表数据的字典
        """
        # 创建时域图
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=time_array,
            y=value_array,
            mode='lines',
            name='时域信号',
            line=dict(color=line_color)
        ))
        
        fig.update_layout(
            title=title,
            xaxis_title=x_axis_title,
            yaxis_title=y_axis_title,
            template=template,
            hovermode="closest"
        )
        
        # 优化布局，确保图表美观
        fig.update_layout(
            autosize=True,
            margin=dict(l=50, r=50, t=50, b=50),
        )
        
        # 添加网格线使数据更易读
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='lightgray')
        
        # 返回图表数据
        return {
            "plot_type": "time_domain",
            "figure": fig.to_json(),
            "title": title
        } 