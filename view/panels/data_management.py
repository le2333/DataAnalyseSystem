import panel as pn
import param

from view.base_panel import CARD_STYLE


class DataManagementPanel(param.Parameterized):
    def view(self, style={"flex": "1 1 auto"}):
        return pn.Column(
            pn.pane.Markdown(
                "## 数据管理\n\n这里是数据管理面板，用于展示和管理可用数据集。\n\n* 数据集1\n* 数据集2\n* 数据集3"
            ),
            sizing_mode="stretch_both",
            styles=style,
            stylesheets=[CARD_STYLE],
        )
