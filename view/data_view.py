import panel as pn
import holoviews as hv
import datashader as ds
from holoviews.operation.datashader import datashade, dynspread, rasterize, spread, shade
from holoviews.plotting.links import RangeToolLink
import pandas as pd
import numpy as np
try:
    import dask.dataframe as dd
    DASK_AVAILABLE = True
except ImportError:
    DASK_AVAILABLE = False

# 初始化Holoviews
hv.extension('bokeh')

class DataView:
    def __init__(self):
        self.main_view = None
        # 定义配色方案
        self.colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
        # 默认数据处理阈值
        self.datashade_threshold = 10000
        # 默认聚合器类型
        self.default_aggregator = 'mean'
        # 默认是否使用预计算
        self.use_precompute = True
        # 默认是否使用Dask
        self.use_dask = DASK_AVAILABLE
        # 默认后处理类型
        self.post_process = 'dynspread'
        
    def get_aggregator(self, agg_type='mean'):
        """获取聚合器
        
        Args:
            agg_type: 聚合器类型，可选 'mean', 'min', 'max', 'count', 'sum', 'std', 'first', 'last', 'summary'
        """
        agg_map = {
            'mean': ds.mean,
            'min': ds.min,
            'max': ds.max,
            'count': ds.count,
            'sum': ds.sum,
            'std': ds.std,
            'first': ds.first,
            'last': ds.last,
            'summary': lambda field: ds.summary(field, [ds.min(), ds.max(), ds.mean()])
        }
        return agg_map.get(agg_type, ds.mean)()
    
    def apply_datashader(self, plot, df, y_column, agg_type='mean', spread_type='dynspread', 
                         spread_px=1, min_alpha=0.5, use_cuda=False):
        """应用datashader优化
        
        Args:
            plot: holoviews plot
            df: 数据源
            y_column: 使用的列名
            agg_type: 聚合器类型
            spread_type: 扩散类型，'dynspread'或'spread'
            spread_px: 扩散像素数
            min_alpha: 最小透明度
            use_cuda: 是否使用CUDA加速
        """
        # 获取聚合器
        aggregator = self.get_aggregator(agg_type)
        
        # 应用datashade
        shaded = datashade(
            plot, 
            aggregator=aggregator,
            precompute=self.use_precompute,
            min_alpha=min_alpha
        )
        
        # 应用扩散效果
        if spread_type == 'dynspread':
            return dynspread(shaded, max_px=spread_px)
        elif spread_type == 'spread':
            return spread(shaded, px=spread_px)
        else:
            return shaded
        
    def optimize_dataframe(self, df, threshold=1000000):
        """优化DataFrame，大数据集转为Dask
        
        Args:
            df: pandas DataFrame
            threshold: 转换为Dask的阈值
        """
        if not self.use_dask or not DASK_AVAILABLE:
            return df
            
        # 大数据集使用Dask优化
        if len(df) > threshold:
            try:
                return dd.from_pandas(df, npartitions=max(1, len(df) // 500000))
            except Exception as e:
                print(f"转换Dask出错: {str(e)}")
                return df
        return df
        
    def create_plot(self, df, y_columns, agg_type='mean', use_dask=None, spread_px=2, min_alpha=0.5):
        """创建时间序列可视化
        
        Args:
            df: pandas DataFrame with DatetimeIndex
            y_columns: list of column names to plot
            agg_type: 聚合器类型，可选 'mean', 'min', 'max', 'count', 'sum', 'std', 'first', 'last', 'summary'
            use_dask: 是否使用Dask优化
            spread_px: 扩散像素数
            min_alpha: 最小透明度
        """
        if not isinstance(df, pd.DataFrame):
            raise ValueError("输入数据必须是DataFrame格式")
        
        # 确保有时间索引
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("数据必须设置时间索引")
        
        # 更新Dask使用设置
        if use_dask is not None:
            self.use_dask = use_dask and DASK_AVAILABLE
            
        try:
            # 数据量大时进行优化
            data_size = len(df)
            is_large_data = data_size > self.datashade_threshold
            
            # 大数据集且启用Dask时优化DataFrame
            if is_large_data and self.use_dask:
                df = self.optimize_dataframe(df)
            
            # 创建叠加的curves
            curves = []
            for i, col in enumerate(y_columns):
                curve = hv.Curve(df[col], 'Time', col).opts(
                    color=self.colors[i % len(self.colors)],
                    line_width=1.5
                )
                curves.append(curve)
            
            # 合并所有曲线
            overlay = hv.Overlay(curves)
            
            # 主图配置
            main_plot = overlay.opts(
                responsive=True,
                height=600, 
                show_grid=True,
                tools=['hover', 'box_zoom', 'reset', 'save'],
                active_tools=['box_zoom']
            )
            
            # 对大数据集使用datashade
            if is_large_data:
                main_plot = self.apply_datashader(
                    main_plot, 
                    df, 
                    y_columns[0], 
                    agg_type=agg_type,
                    spread_px=spread_px,
                    min_alpha=min_alpha
                )
            
            # 创建导航图 (使用第一个选中的列)
            nav_curve = hv.Curve(df[y_columns[0]], 'Time', y_columns[0])
            minimap = nav_curve.opts(
                responsive=True,
                height=150,
                show_grid=True,
                toolbar=None,
                xlabel='',
                ylabel='',
                yaxis=None,
                color=self.colors[0]
            )
            
            # 对导航图也使用datashade
            if is_large_data:
                minimap = self.apply_datashader(
                    minimap, 
                    df, 
                    y_columns[0], 
                    agg_type='mean',  # 导航图使用均值聚合
                    spread_px=1
                )
            
            # 创建链接
            self.range_link = RangeToolLink(minimap, main_plot, axes=["x","y"])
            
            # 创建布局
            self.main_view = pn.Column(
                pn.pane.HoloViews(
                    main_plot,
                    sizing_mode='stretch_width'
                ),
                pn.pane.HoloViews(
                    minimap,
                    sizing_mode='stretch_width'
                ),
                sizing_mode='stretch_width',
                css_classes=['plot-container']
            )
            
            return self.main_view
            
        except Exception as e:
            print(f"可视化错误: {str(e)}")
            return pn.Column(f"可视化错误: {str(e)}", sizing_mode='stretch_width')
    
    def create_interactive_plot(self, df, y_columns):
        """创建带有交互控件的时间序列可视化
        
        Args:
            df: pandas DataFrame with DatetimeIndex
            y_columns: list of column names to plot
        """
        # 聚合方式选择
        agg_select = pn.widgets.Select(
            name='聚合方式',
            options={
                '均值': 'mean', 
                '最小值': 'min', 
                '最大值': 'max',
                '计数': 'count',
                '求和': 'sum',
                '标准差': 'std',
                '第一个': 'first',
                '最后一个': 'last'
            },
            value='mean'
        )
        
        # 扩散像素调整
        spread_slider = pn.widgets.IntSlider(
            name='扩散像素',
            start=1,
            end=10,
            step=1,
            value=2
        )
        
        # 透明度调整
        alpha_slider = pn.widgets.FloatSlider(
            name='最小透明度',
            start=0.1,
            end=1.0,
            step=0.1,
            value=0.5
        )
        
        # Dask使用选项
        dask_toggle = pn.widgets.Checkbox(
            name='使用Dask优化',
            value=self.use_dask and DASK_AVAILABLE,
            disabled=not DASK_AVAILABLE
        )
        
        # 创建控件回调函数
        def update_plot(event):
            return self.create_plot(
                df, 
                y_columns, 
                agg_type=agg_select.value,
                use_dask=dask_toggle.value,
                spread_px=spread_slider.value,
                min_alpha=alpha_slider.value
            )
        
        # 连接控件事件
        agg_select.param.watch(update_plot, 'value')
        spread_slider.param.watch(update_plot, 'value')
        alpha_slider.param.watch(update_plot, 'value')
        dask_toggle.param.watch(update_plot, 'value')
        
        # 初始创建图表
        plot_view = self.create_plot(
            df, 
            y_columns, 
            agg_type=agg_select.value,
            use_dask=dask_toggle.value,
            spread_px=spread_slider.value,
            min_alpha=alpha_slider.value
        )
        
        # 控件面板
        controls = pn.Row(
            agg_select,
            spread_slider,
            alpha_slider,
            dask_toggle
        )
        
        # 创建最终布局
        self.main_view = pn.Column(
            controls,
            plot_view,
            sizing_mode='stretch_width'
        )
        
        return self.main_view
    
    def get_view(self):
        """返回主视图"""
        if self.main_view is None:
            return pn.Column("还未创建可视化", sizing_mode='stretch_width')
        return self.main_view 