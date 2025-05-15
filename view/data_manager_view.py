import panel as pn
import param
import pandas as pd
from viewmodel.data_manager_viewmodel import DataManagerViewModel

pn.extension("tabulator", "plotly")


def create_data_manager_view(viewmodel: DataManagerViewModel) -> pn.Column:
    """创建数据管理视图

    Args:
        viewmodel: 数据管理视图模型

    Returns:
        Panel布局组件
    """
    # 创建数据表格
    columns_list = ["id", "name", "type", "created_at", "shape", "sample"]

    # 确保传递DataFrame对象给Tabulator
    summary_df = pd.DataFrame(viewmodel.data_summary_list)

    # 创建数据表格，绑定到viewmodel的data_summary_list
    data_table = pn.widgets.Tabulator(
        value=summary_df
        if not summary_df.empty
        else pd.DataFrame(columns=columns_list),
        selectable=True,
        pagination="remote",
        page_size=10,
        width=1350,
        height=250,
        sizing_mode="fixed",
    )

    # 监听表格选择变化
    def on_selection_change(event):
        if event.new:
            selected_indices = event.new
            selected_rows = event.obj.value.iloc[selected_indices]
            selected_ids = selected_rows["id"].tolist()
            viewmodel.select_data(selected_ids)

    data_table.param.watch(on_selection_change, "selection")

    # 创建操作按钮
    rename_button = pn.widgets.Button(
        name="重命名", button_type="primary", disabled=True, width=100
    )
    remove_button = pn.widgets.Button(
        name="删除", button_type="danger", disabled=True, width=100
    )
    process_button = pn.widgets.Button(
        name="处理数据", button_type="success", disabled=True, width=100
    )
    visualize_button = pn.widgets.Button(
        name="可视化", button_type="warning", disabled=True, width=100
    )

    # 创建重命名输入框
    rename_input = pn.widgets.TextInput(
        placeholder="输入新名称...", disabled=True, width=200
    )

    # 更新按钮状态的函数
    def update_button_states(event=None):
        selected_count = len(viewmodel.selected_data_ids)
        rename_button.disabled = selected_count != 1
        rename_input.disabled = selected_count != 1
        remove_button.disabled = selected_count == 0
        process_button.disabled = selected_count == 0
        visualize_button.disabled = selected_count == 0

    # 监听选中数据变化
    viewmodel.param.watch(update_button_states, "selected_data_ids")

    # 重命名操作
    def rename_selected(event):
        if viewmodel.selected_data_ids and rename_input.value:
            data_id = viewmodel.selected_data_ids[0]
            success = viewmodel.rename_data(data_id, rename_input.value)
            if success:
                rename_input.value = ""

    rename_button.on_click(rename_selected)

    # 删除操作
    def remove_selected(event):
        for data_id in list(viewmodel.selected_data_ids):  # 使用列表副本防止迭代时修改
            viewmodel.remove_data(data_id)

    remove_button.on_click(remove_selected)

    # 监听数据更新事件，刷新表格
    def refresh_data_table(event=None):
        # 将列表转换为DataFrame后再赋值
        summary_df = pd.DataFrame(viewmodel.data_summary_list)
        data_table.value = (
            summary_df if not summary_df.empty else pd.DataFrame(columns=columns_list)
        )

    viewmodel.param.watch(refresh_data_table, "data_updated")

    # 创建操作按钮行
    controls = pn.Row(
        rename_input,
        rename_button,
        remove_button,
        process_button,
        visualize_button,
        width=1350,
        height=40,
        sizing_mode="fixed",
        styles={
            "background-color": "#f0f0f0",
            "padding": "5px",
            "justify-content": "flex-start",
        },
    )

    return pn.Column(data_table, controls, sizing_mode="fixed", width=1350)


def create_visualization_panel():
    """创建一个简单的可视化面板用于测试"""
    import numpy as np
    import plotly.graph_objects as go

    # 创建示例数据
    x = np.linspace(0, 10, 100)
    y = np.sin(x)

    # 创建Plotly图表
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", name="sin(x)"))
    fig.update_layout(title="示例可视化", xaxis_title="X", yaxis_title="Y")

    return pn.pane.Plotly(fig, width=1350, height=300, sizing_mode="fixed")
