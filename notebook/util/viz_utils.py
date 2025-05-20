import hvplot.pandas  # noqa: F401
import panel as pn
import matplotlib.pyplot as plt
import pandas as pd
from typing import List, Dict

def line_chart(dfs, height: int = 400):
    """
    多列折线图，可用于多维时间序列可视化。
    """
    selector = pn.widgets.Select(name='选择数据')
    if type(dfs) == dict:
        selector.options = list(dfs.keys())
        selector.value = list(dfs.keys())[0]
    elif type(dfs) == pd.DataFrame:
        selector.options = dfs.columns
        selector.value = dfs.columns[0]
    @pn.depends(selector.param.value)
    def plot_line(value):
        df=dfs[value]
        plot = df.hvplot.line(
            # height=height,
            # responsive=True,
            downsample=True
        ).opts(
            backend_opts={
                "x_range.bounds": (df.index.min(), df.index.max()), # optional: limit max viewable x-extent to data
                "y_range.bounds": (df.columns[0].min()-1, df.columns[0].max()+1), # optional: limit max viewable y-extent to data
            }
        )
        return plot
    panel = pn.Column(selector, plot_line)
    return panel

def plot_histogram(df: pd.DataFrame, column: str, bins: int = 100, logy: bool = False, height: int = 400):
    """
    单列直方图，可选对数y轴。
    """
    plot = df[column].hvplot.hist(
        bins=bins,
        logy=logy,
        height=height,
        xlabel=column,
        ylabel='频数',
        title=f'{column} 分布直方图'
    )
    return plot

def plot_with_matplotlib(df: pd.DataFrame, columns: List[str] = None, title: str = '', figsize=(12, 6)):
    """
    用matplotlib画多列折线图。
    """
    if columns is None:
        columns = list(df.columns)
    plt.figure(figsize=figsize)
    for col in columns:
        plt.plot(df.index, df[col], label=col)
    plt.title(title)
    plt.xlabel('时间')
    plt.ylabel('数值')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show() 