import panel as pn
import param

from view.base_panel import CARD_STYLE


class NodeLibraryPanel(param.Parameterized):
    def view(self, style={"flex": "1 1 auto"}):
        return pn.Column(
            pn.pane.Markdown(
                "## 节点库\n\n这里是节点库面板，显示可用的处理节点。\n\n* 数据加载节点\n* 数据清洗节点\n* 特征提取节点\n* 模型训练节点"
            ),
            sizing_mode="stretch_both",
            styles=style,
            stylesheets=[CARD_STYLE],
        )
