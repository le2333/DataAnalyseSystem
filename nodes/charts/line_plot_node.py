import panel as pn
import polars as pl
import hvplot.polars  # noqa
import holoviews as hv
import param
import numpy as np
from datetime import datetime

from core.node.base_node import BaseNode
from core.node.registry import NodeRegistry

# 启用 Panel 的 Param 和 HoloViews 扩展
pn.extension(
    "param", "plotly", "tabulator"
)  # 'plotly' 可能不是必需的，但通常与 hvplot 一起使用
hv.extension("bokeh", "matplotlib")  # 确保 bokeh 后端可用


@NodeRegistry.register_node
class LinePlotNode(BaseNode):
    """
    节点：使用 hvplot 和 rasterize 生成折线图，并在配置面板中提供预览。
    """

    _node_type = "Visualization"  # 分类
    _node_name = "Line Plot (hvplot)"

    # --- 配置参数 ---
    # 使用 param 定义节点的可配置参数
    # 参考: https://param.holoviz.org/user_guide/Parameters.html
    #      https://panel.holoviz.org/user_guide/Param.html

    # 输入数据 (假设只有一个输入)
    # 注意：实际的输入 DataFrame 不会直接作为 param 参数，而是在 run 方法中接收
    # 但我们需要知道可能的列名来填充下拉菜单

    x_col = param.Selector(default=None, objects=[], label="X 轴 (时间/索引)")
    y_cols = param.ListSelector(default=[], objects=[], label="Y 轴 (值)")
    title = param.String(default="Time Series Plot", label="图表标题")
    xlabel = param.String(default="X Axis", label="X 轴标签")
    ylabel = param.String(default="Y Axis", label="Y 轴标签")
    use_rasterize = param.Boolean(default=True, label="使用 Rasterize (用于大数据)")
    legend_position = param.Selector(
        default="top_left",
        objects=[
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "right",
            "left",
        ],
        label="图例位置",
    )
    width = param.Integer(default=800, bounds=(100, 2000), label="宽度")
    height = param.Integer(default=400, bounds=(100, 2000), label="高度")
    # TODO: 添加更多样式参数，如颜色、线型等

    # 内部状态，用于存储输入数据的列名
    _input_columns = param.List(
        default=[], precedence=-1
    )  # precedence=-1 使其不在UI中显示

    def __init__(self, **params):
        super().__init__(**params)
        # 在初始化时或数据更新时更新列选择器
        self._update_column_selectors()

    @classmethod
    def define_inputs(cls) -> dict:
        """定义此节点的输入。"""
        return {"input_data": pl.DataFrame}

    @classmethod
    def define_outputs(cls) -> dict:
        """定义此节点的输出。"""
        # hv.Layout 是一个更通用的容器类型，可以包含单个图或多个图
        return {"plot_object": hv.Layout}  # 或者 hv.Element 如果确定总是单个图

    def _update_column_selectors(self, input_df_sample: pl.DataFrame | None = None):
        """根据输入的（样本）数据更新列选择器的选项"""
        if input_df_sample is not None and not input_df_sample.is_empty():
            columns = input_df_sample.columns
            self._input_columns = columns

            # 保留当前选择（如果新列中仍然存在）
            current_x = self.x_col
            current_y = self.y_cols

            # 更新 param 对象的 objects 列表
            self.param.x_col.objects = [None] + columns
            self.param.y_cols.objects = columns

            # 尝试恢复之前的选择
            self.x_col = current_x if current_x in columns else None
            self.y_cols = [y for y in current_y if y in columns]
        else:
            # 没有有效数据时清空选项
            self._input_columns = []
            self.param.x_col.objects = [None]
            self.param.y_cols.objects = []
            self.x_col = None
            self.y_cols = []

    def _create_plot(
        self,
        df: pl.DataFrame,
        x_col: str,
        y_cols: list[str],
        title: str,
        xlabel: str,
        ylabel: str,
        use_rasterize: bool,
        legend_position: str,
        width: int,
        height: int,
    ):
        """核心绘图逻辑"""
        if (
            not x_col
            or not y_cols
            or df.is_empty()
            or x_col not in df.columns
            or not all(y in df.columns for y in y_cols)
        ):
            # 如果缺少必要信息或数据为空，返回空图或提示信息
            return hv.Text(
                width // 2,
                height // 2,
                """请选择有效的 X 和 Y 列
并确保输入数据已连接。""",
                halign="center",
                valign="center",
            ).opts(xaxis=None, yaxis=None, width=width, height=height)

        try:
            plot = df.hvplot.line(
                x=x_col,
                y=y_cols,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
                legend=legend_position,
                width=width,
                height=height,
                responsive=False,  # 在配置面板中通常使用固定大小
                # TODO: 添加更多从 param 获取的样式选项
            )

            if use_rasterize:
                # Rasterize 线条和点标记 (如果 hvplot 生成了点)
                plot = plot.opts(
                    hv.opts.Curve(rasterize=True), hv.opts.Scatter(rasterize=True)
                )

            return plot

        except Exception as e:
            # 处理绘图时可能发生的错误 (例如，数据类型不兼容)
            # 修正：使用三引号处理多行 f-string
            error_message = f"""创建绘图时出错: {e}
检查列选择和数据类型。"""
            return hv.Text(
                width // 2, height // 2, error_message, halign="center", valign="center"
            ).opts(xaxis=None, yaxis=None, width=width, height=height)

    def _generate_preview_plot(
        self,
        x_col: str | None,
        y_cols: list[str],
        title: str,
        xlabel: str,
        ylabel: str,
        use_rasterize: bool,
        legend_position: str,
        width: int,
        height: int,
    ):
        """为配置面板生成预览图"""
        # --- 预览数据获取逻辑 ---
        # !!! 关键点: 配置时无法直接访问工作流中的真实数据 !!!
        # 策略1: 使用固定的占位符/样本数据
        # 策略2: (更高级) 尝试从上游节点的缓存中获取少量样本 (如果平台支持)
        # 当前实现: 使用策略1 (占位符数据)

        # 创建一个简单的占位符 DataFrame
        # 注意：列名应与可能的输入匹配，但类型可能不完全一致
        if not self._input_columns:  # 如果没有从输入获取到列名，创建一些通用列名
            preview_df = pl.DataFrame(
                {
                    "time": pl.datetime_range(
                        start=datetime(2024, 1, 1, 0),
                        end=datetime(2024, 1, 1, 1),
                        interval="1m",
                        eager=True,
                    ),
                    "value_a": np.random.randn(61).cumsum(),
                    "value_b": np.random.rand(61) * 10,
                    "index": pl.arange(0, 61, eager=True),
                }
            )
            # 模拟更新列选择器 (通常这应该在数据输入时触发)
            # self._update_column_selectors(preview_df) # 在 __init__ 中调用，或需要外部触发
        else:
            # 如果有输入列名，尝试创建类型匹配的样本数据
            # (这是一个简化，实际类型可能需要更复杂的推断)
            data = {}
            n_rows = 50
            for col in self._input_columns:
                # 简单类型猜测 (需要改进)
                if "time" in col.lower() or "date" in col.lower():
                    data[col] = pl.datetime_range(
                        start=datetime(2024, 1, 1),
                        end=datetime(2024, 1, 2),
                        interval=f"{86400 // n_rows}s",
                        eager=True,
                    )[:n_rows]
                elif "index" in col.lower() or "id" in col.lower():
                    data[col] = pl.arange(0, n_rows, eager=True)
                else:  # 假设为数值型
                    data[col] = np.random.rand(n_rows)
            try:
                preview_df = pl.DataFrame(data)
            except Exception:  # 如果创建失败，回退
                preview_df = pl.DataFrame(
                    {  # 回退
                        "time": pl.datetime_range(
                            start=datetime(2024, 1, 1, 0),
                            end=datetime(2024, 1, 1, 1),
                            interval="1m",
                            eager=True,
                        ),
                        "value": np.random.randn(61).cumsum(),
                    }
                )
                self._update_column_selectors(preview_df)  # 使用回退列更新

        # 使用当前配置和预览数据生成图表
        if x_col is None or not y_cols:
            # 如果用户还未选择有效的列，显示提示信息而不是绘图
            return hv.Text(
                width // 2,
                height // 2,
                "为预览选择 X 和 Y 列。",
                halign="center",
                valign="center",
            ).opts(xaxis=None, yaxis=None, width=width, height=height)

        return self._create_plot(
            preview_df,
            x_col,
            y_cols,
            title,
            xlabel,
            ylabel,
            use_rasterize,
            legend_position,
            width,
            height,
        )

    def _build_config_panel_content(self) -> pn.viewable.Viewable:
        """
        构建此节点的 Panel 配置面板内容。
        **重要**: 此方法在每次需要显示配置时被调用，应返回新创建的 UI 元素。
        """
        # 使用 self.param 自动生成控件
        param_pane = pn.Param(
            self.param,
            widgets={
                "x_col": pn.widgets.Select,
                "y_cols": pn.widgets.CrossSelector,  # CrossSelector 适合多选
                # 可以为其他参数指定特定的小部件类型或选项
                "title": pn.widgets.TextInput,
                "xlabel": pn.widgets.TextInput,
                "ylabel": pn.widgets.TextInput,
                "legend_position": pn.widgets.Select,
                "width": pn.widgets.IntSlider,
                "height": pn.widgets.IntSlider,
            },
            show_name=False,  # 不显示参数名称旁边的默认标签
        )

        # 创建一个新的 HoloViews pane 每次调用
        # 将 pn.bind 返回的 *函数* 传递给 HoloViews pane
        preview_plot_func = pn.bind(
            self._generate_preview_plot,
            x_col=self.param.x_col,
            y_cols=self.param.y_cols,
            title=self.param.title,
            xlabel=self.param.xlabel,
            ylabel=self.param.ylabel,
            use_rasterize=self.param.use_rasterize,
            legend_position=self.param.legend_position,
            width=self.param.width,
            height=self.param.height,
        )
        # Create a NEW pane instance here!
        hv_preview_pane = pn.pane.HoloViews(
            preview_plot_func, sizing_mode="stretch_width"
        )

        # 将参数控件和新的预览图组合到布局中
        config_layout = pn.Column(
            pn.pane.Markdown("### 折线图配置"),
            param_pane,
            pn.pane.Markdown("### 预览"),
            hv_preview_pane,  # 使用新的 pane
            sizing_mode="stretch_width",
        )
        return config_layout

    # --- 工作流执行 ---
    def run(self, inputs: dict) -> dict:
        """
        工作流执行时调用的方法。
        接收真实的输入数据并生成最终的图表对象。
        """
        # 获取输入 DataFrame
        input_df = inputs.get("input_data")
        if input_df is None or not isinstance(input_df, pl.DataFrame):
            raise ValueError(
                f"节点 '{self.node_id}': 需要名为 'input_data' 的 Polars DataFrame 输入。"
            )

        # 1. (可选) 更新列选择器，以防输入数据的列与上次不同
        self._update_column_selectors(input_df)

        # 2. 使用当前的配置参数和接收到的真实数据生成图表
        final_plot = self._create_plot(
            df=input_df,
            x_col=self.x_col,
            y_cols=self.y_cols,
            title=self.title,
            xlabel=self.xlabel,
            ylabel=self.ylabel,
            use_rasterize=self.use_rasterize,
            legend_position=self.legend_position,
            width=self.width,
            height=self.height,
        )

        # 3. 返回包含 HoloViews 图表对象的字典
        return {"plot_object": final_plot}

    # --- (高级) 状态管理 ---
    # 如果需要保存/加载节点状态（包括选择的列等），可以实现 get_state/set_state
    # def get_state(self):
    #     state = super().get_state()
    #     state.update({
    #         'x_col': self.x_col,
    #         'y_cols': self.y_cols,
    #         'title': self.title,
    #         # ... 其他需要保存的参数 ...
    #     })
    #     return state

    # def set_state(self, state):
    #     super().set_state(state)
    #     self.x_col = state.get('x_col')
    #     self.y_cols = state.get('y_cols', [])
    #     self.title = state.get('title', "Time Series Plot")
    #     # ... 其他需要恢复的参数 ...
    #     # 恢复状态后可能需要手动更新预览
    #     self._hv_pane.object = self._update_preview()
