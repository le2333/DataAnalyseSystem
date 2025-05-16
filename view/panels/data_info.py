import panel as pn
import param

from view.base_panel import CARD_STYLE


class DataInfoPanel(param.Parameterized):
    def view(self, style={"flex": "1 1 auto"}):
        return pn.Column(
            pn.pane.Markdown(
                "## 数据特征\n\n这里是数据特征面板，展示数据的统计特征。\n\n* 特征1: 值1\n* 特征2: 值2\n* 特征3: 值3\n* 特征4: 值4"
            ),
            sizing_mode="stretch_both",
            styles=style,
            stylesheets=[CARD_STYLE],
        )
