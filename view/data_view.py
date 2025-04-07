import panel as pn
import holoviews as hv
import hvplot.pandas
import datashader
import param
from holoviews.plotting.links import RangeToolLink
import pandas as pd

class DataView:
    """数据视图：负责数据可视化展示"""
    
    def __init__(self):
        # 初始化HoloViews和Datashader
        hv.extension('bokeh')
        self.renderer = hv.renderer('bokeh')
        self.renderer.webgl = True  # 启用WebGL加速
    
    def create_plot(self, df, columns, use_datashader=None):
        """创建时间序列可视化"""
        if df is None or not columns:
            return pn.Row("没有数据或未选择列")
        
        try:
            # 自动决定渲染策略
            if use_datashader is None:
                # 根据数据量自动决定是否使用Datashader
                use_datashader = len(df) > 100000
            
            plots = []
            for column in columns:
                if use_datashader:
                    # 使用Datashader渲染大数据量
                    plot = self._create_datashader_plot(df, column)
                else:
                    # 使用HoloViews渲染小数据量
                    plot = self._create_hvplot(df, column)
                # 将图表包装在Card中
                card = pn.Card(plot, title=column, sizing_mode='stretch_width')
                plots.append(card)
            
            # 将所有图表垂直组合在一起
            combined_plot = pn.Column(*plots, sizing_mode='stretch_width')
            return combined_plot
        
        except Exception as e:
            return pn.Row(f"创建可视化失败: {str(e)}")
    

    
    def _create_datashader_plot(self, df, column):
        """创建基于Datashader的时间序列图"""
        # 主图使用Datashader栅格化
        main_plot = df[column].hvplot(
            title=column,
            min_height=600,
            responsive=True,
            colorbar=False, 
            line_width=1,
            rasterize=True  # 启用Datashader栅格化
        ).opts(
            backend_opts={
                # 限制可查看的最大范围为数据范围
                "x_range.bounds": (df.index.min(), df.index.max()) if hasattr(df.index, 'min') else None,
                "y_range.bounds": (df[column].min()-1, df[column].max()+1)
            }
        )
        
        # 创建底部的缩略图
        minimap = df[column].hvplot(
            height=200,
            padding=(0, 0.1), 
            rasterize=True,
            responsive=True,
            color='darkblue', 
            colorbar=False, 
            line_width=1
        ).opts(toolbar='disable')
        
        # 链接主图和缩略图
        link = RangeToolLink(minimap, main_plot, axes=["x", "y"])
        
        # 组合主图和缩略图，设置不共享坐标轴
        combined = (main_plot + minimap).opts(shared_axes=False).cols(1)
        
        # 将HoloViews对象转换为Panel对象
        return pn.pane.HoloViews(combined, sizing_mode='stretch_width')
    

