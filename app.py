import panel as pn
from view.panels.data_management import DataManagementPanel
from view.panels.node_library import NodeLibraryPanel
from view.panels.node_config import NodeConfigPanel
from view.panels.data_info import DataInfoPanel
from view.panels.data_visualization import DataVisualizationPanel

# 初始化 Panel 扩展
pn.extension()

# 设置卡片样式，增加阴影和内边距
CARD_STYLE = """
:host {
  box-shadow: rgba(50, 50, 93, 0.25) 0px 6px 12px -2px, rgba(0, 0, 0, 0.3) 0px 3px 7px -3px;
  padding: 10px;
  overflow: auto;
  height: 100%;
}
"""

# 设置响应式布局的媒体查询，当屏幕宽度小于 1000px 时改变布局
RESPONSIVE_STYLE = """
@media screen and (max-width: 1000px) {
  div[id^="top-panel"] {
    flex-flow: column !important;
  }
  div[id^="bottom-panel"] {
    flex-flow: column !important;
  }
}
"""

# 创建上层面板组件 - 数据与处理管理面板
# 注意这里为每个面板传递了自定义的 style 参数
data_manager = DataManagementPanel().view(style={"flex": "1 1 40%"})
node_library = NodeLibraryPanel().view(style={"flex": "1 1 30%"})
node_config = NodeConfigPanel().view(style={"flex": "1 1 30%"})

# 创建上层面板布局 - 明确设置为水平排列
top_panel = pn.FlexBox(
    data_manager,
    node_library,
    node_config,
    flex_direction="row",  # 明确设置为水平排列
    flex_wrap="nowrap",  # 不换行
    sizing_mode="stretch_both",
    height=300,
    styles={"align-items": "stretch", "gap": "10px"},
    name="top-panel",
)

# 创建下层面板组件 - 数据可视化面板
data_info = DataInfoPanel().view(style={"flex": "1 1 40%"})
data_visualization = DataVisualizationPanel().view(style={"flex": "1 1 60%"})

# 创建下层面板布局 - 明确设置为水平排列
bottom_panel = pn.FlexBox(
    data_info,
    data_visualization,
    flex_direction="row",  # 明确设置为水平排列
    flex_wrap="nowrap",  # 不换行
    sizing_mode="stretch_both",
    height=350,
    styles={"align-items": "stretch", "gap": "10px"},
    name="bottom-panel",
)

top_panel.styles.update({"flex": "4 1 0%"})
bottom_panel.styles.update({"flex": "6 1 0%"})

# 创建主界面
main_layout = pn.FlexBox(
    pn.pane.Markdown(
        "# 数据可视化探索与算法开发系统",
        styles={"text-align": "center", "flex": "0 0 auto"},
    ),
    top_panel,
    bottom_panel,
    flex_direction="column",
    sizing_mode="stretch_both",
    styles={"gap": "10px", "padding": "10px"},
    stylesheets=[RESPONSIVE_STYLE],
)

# 显示界面
main_layout.servable()
