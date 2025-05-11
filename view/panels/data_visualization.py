import panel as pn
import param

from view.base_panel import CARD_STYLE


class DataVisualizationPanel(param.Parameterized):
    def view(self, style={"flex": "1 1 auto"}):
        return pn.Column(
            pn.pane.Markdown(
                "## 数据可视化\n\n这里是数据可视化面板，用于展示数据的可视化图表。\n\n[图表占位区域]"
            ),
            sizing_mode="stretch_both",
            styles=style,
            stylesheets=[CARD_STYLE],
        )
