import panel as pn

# 设置卡片样式，增加阴影和内边距
CARD_STYLE = """
:host {
  box-shadow: rgba(50, 50, 93, 0.25) 0px 6px 12px -2px, rgba(0, 0, 0, 0.3) 0px 3px 7px -3px;
  padding: 10px;
  overflow: auto;
  height: 100%;
}
"""


class BasePanel:
    def __init__(self, title, description, icon):
        self.title = title
        self.description = description
        self.icon = icon

    def view(self, style={"flex": "1 1 auto"}):
        return pn.Column(
            pn.pane.Markdown(self.title),
            pn.pane.Markdown(self.description),
            sizing_mode="stretch_both",
            styles=style,
            stylesheets=[CARD_STYLE],
        )
