import panel as pn
import param
from view.data_manager_view import create_data_manager_view, create_visualization_panel
from view.ui_components import VisMainOptions, VisRenderingOptions, TimeAlignmentOptions
from viewmodel.data_manager_viewmodel import DataManagerViewModel


def create_flexbox_layout(app_viewmodel) -> pn.Column:
    """创建基于FlexBox的上下两层布局

    Args:
        app_viewmodel: 应用视图模型

    Returns:
        pn.Column: 主布局容器
    """
    # 获取数据管理视图模型
    data_manager_viewmodel = app_viewmodel.data_manager_viewmodel

    # --- 创建各个面板 ---

    # 1. 数据选择面板
    data_selector = pn.widgets.MultiSelect(
        name="选择数据",
        options=data_manager_viewmodel.get_data_options(),
        size=8,
        width=200,
    )

    data_selection_panel = pn.Column(
        pn.pane.Markdown("### 数据选择", styles={"text-align": "center"}),
        data_selector,
        width=250,
        min_height=250,
        sizing_mode="fixed",
    )

    # 2. 服务选择面板
    service_types = ["预处理", "特征提取", "分析", "可视化"]
    service_selector = pn.widgets.RadioButtonGroup(
        name="服务类型",
        options=service_types,
        button_type="primary",
        orientation="horizontal",
        width=400,
    )

    services = {
        "预处理": ["移动平均", "降采样", "去噪", "中值滤波", "数据填充"],
        "特征提取": ["趋势分析", "周期性检测", "异常检测", "拐点检测"],
        "分析": ["相关性分析", "回归分析", "聚类分析", "主成分分析"],
        "可视化": ["时序图", "散点图", "热力图", "箱线图"],
    }

    service_list = pn.widgets.Select(
        name="选择服务", options=services["预处理"], size=5, width=200
    )

    def update_service_list(event):
        service_list.options = services[event.new]

    service_selector.param.watch(update_service_list, "value")

    service_selection_panel = pn.Column(
        pn.pane.Markdown("### 服务选择", styles={"text-align": "center"}),
        service_selector,
        service_list,
        width=450,
        min_height=250,
        sizing_mode="fixed",
    )

    # 3. 服务参数面板
    param_widgets = pn.Column(
        pn.widgets.FloatSlider(
            name="窗口大小", start=3, end=51, step=2, value=7, width=250
        ),
        pn.widgets.Select(
            name="平均方式",
            options=["简单平均", "指数加权", "三角加权"],
            value="简单平均",
            width=250,
        ),
        pn.widgets.Checkbox(name="应用于所有列", value=True),
        pn.widgets.IntSlider(name="展示精度", start=0, end=6, value=2, width=250),
        width=300,
    )

    service_config_panel = pn.Column(
        pn.pane.Markdown("### 参数配置", styles={"text-align": "center"}),
        param_widgets,
        width=350,
        min_height=250,
        sizing_mode="fixed",
    )

    # --- 构建页面布局 ---

    # 创建带背景色的标题栏（使用Div嵌套Markdown的方式）
    def create_header(title, width):
        return pn.Row(
            pn.pane.Markdown(
                f"## {title}",
                styles={
                    "color": "white",
                    "text-align": "center",
                    "font-weight": "bold",
                    "margin": "0px",
                },
            ),
            width=width,
            height=30,
            styles={
                "background-color": "#0072B2",
                "justify-content": "center",
                "align-items": "center",
            },
            sizing_mode="fixed",
        )

    # 上层面板（数据选择、服务选择、参数配置）
    top_header = create_header("数据选择", 500)
    top_right_header = create_header("服务选择", 850)

    top_header_row = pn.Row(
        top_header,
        top_right_header,
        styles={"gap": "0px"},
        sizing_mode="fixed",
        height=30,
        width=1350,
    )

    top_left_panel = pn.Column(
        data_selection_panel,
        width=250,
        sizing_mode="fixed",
        styles={"border": "1px solid #ddd", "background-color": "white"},
    )

    top_right_panel = pn.Row(
        service_selection_panel,
        service_config_panel,
        width=850,
        sizing_mode="fixed",
        styles={"border": "1px solid #ddd", "background-color": "white"},
    )

    top_row = pn.Row(
        top_left_panel, top_right_panel, width=1350, height=250, sizing_mode="fixed"
    )

    # 运行按钮
    run_button = pn.widgets.Button(
        name="运行服务", button_type="success", width=150, align="center"
    )

    button_row = pn.Row(
        pn.Spacer(width=10),
        run_button,
        pn.Spacer(width=10),
        height=40,
        width=1350,
        styles={
            "background-color": "#E3F2FD",
            "justify-content": "center",
            "align-items": "center",
        },
        sizing_mode="fixed",
    )

    # 下层面板（数据表格、可视化）
    bottom_header = create_header("数据管理", 1350)

    # 数据表格
    data_table_view = create_data_manager_view(data_manager_viewmodel)

    # 数据可视化
    visualization_panel = create_visualization_panel()
    visualization_header = create_header("数据可视化", 1350)

    # 完整布局
    layout = pn.Column(
        # 顶部标题
        pn.pane.Markdown("# 数据分析系统", styles={"text-align": "center"}),
        # 上层
        top_header_row,
        top_row,
        # 按钮
        button_row,
        # 下层
        bottom_header,
        data_table_view,
        visualization_header,
        visualization_panel,
        width=1350,
        sizing_mode="fixed",
        styles={"margin": "0 auto", "background-color": "#f8f9fa"},
    )

    return layout
