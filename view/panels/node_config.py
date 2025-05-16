import panel as pn
import param

from view.base_panel import CARD_STYLE


class NodeConfigPanel(param.Parameterized):
    def view(self, style={"flex": "1 1 auto"}):
        return pn.Column(
            pn.pane.Markdown(
                "## 节点配置面板\n\n这里是节点配置面板，用于配置所选节点的参数。\n\n* 参数1: 值1\n* 参数2: 值2\n* 参数3: 值3"
            ),
            sizing_mode="stretch_both",
            styles=style,
            stylesheets=[CARD_STYLE],
        )
