import pandas as pd
import panel as pn
import hvplot.pandas

# 初始化 Panel
pn.extension()

def line_chart(dataframes: dict):
    # 创建文件选择器控件
    hvplot.extension('bokeh')
    file_selector = pn.widgets.Select(
        name='选择数据文件',
        options=list(dataframes.keys()),
        value=list(dataframes.keys())[0]
    )

    # 创建交互式函数
    @pn.depends(file=file_selector)
    def plot_data(file):
        df = pd.DataFrame(dataframes[file])
        line = df.hvplot(
            responsive=True,
            downsample=True,
            height=500,
        )
        
        return line

    # 创建交互式面板
    dashboard = pn.Column(
        file_selector,
        plot_data
    )

    return dashboard

def hist_chart(dataframes):
    # 创建文件选择器控件
    hvplot.extension('plotly')
    file_selector = pn.widgets.Select(
        name='选择数据文件',
        options=list(dataframes.keys()),
        value=list(dataframes.keys())[0]
    )

    # 创建交互式函数
    @pn.depends(file=file_selector)
    def plot_data(file):
        df = dataframes[file]
        # print(df)
        plot = df.hvplot.hist(
            logy=True,
            # height=500,
            bins=1000
        )
        
        return plot

    # 创建交互式面板
    dashboard = pn.Column(
        file_selector,
        plot_data
    )
    
    return dashboard

def lag_chart(dataframes):
    hvplot.extension('bokeh')
    file_selector = pn.widgets.Select(
        name='选择数据文件',
        options=list(dataframes.keys()),
        value=list(dataframes.keys())[0]
    )

    lag_selector = pn.widgets.IntInput(
        name='选择滞后',
        value=1
    )

    # 创建交互式函数
    @pn.depends(file=file_selector,lag=lag_selector)
    def plot_data(file,lag):
        df = dataframes[file]
        # print(df)
        plot = hvplot.plotting.lag_plot(df, lag=lag)
        
        return plot

    # 创建交互式面板
    dashboard = pn.Column(
        pn.Row(file_selector, lag_selector),
        plot_data
    )
    
    return dashboard