import panel as pn
import param
import logging
import networkx as nx
import hvplot.networkx as hvnx
import holoviews as hv
from holoviews import opts
from bokeh.models import HoverTool

from core.workflow import Workflow

hv.extension('bokeh')
logger = logging.getLogger(__name__)

class WorkflowVisualizer(param.Parameterized):
    """
    使用 hvPlot 和 NetworkX 静态可视化工作流图。
    (移除了节点点击交互)
    """
    workflow = param.ClassSelector(class_=Workflow, precedence=-1)
    # selected_node_id = param.String(default=None, doc="当前选中的节点ID") # 移除输出参数

    # 内部状态
    _plot_pane = param.Parameter(default=pn.pane.HoloViews(None, sizing_mode='stretch_both'), precedence=-1)
    _node_positions = param.Dict(default={})
    # _tap_stream = param.Parameter(precedence=-1) # 移除 tap stream

    def __init__(self, **params):
        super().__init__(**params)
        self._update_node_positions()
        self._create_plot()

    @param.depends('workflow', watch=True)
    def _handle_workflow_replacement(self, event=None):
        logger.debug("WorkflowVisualizer detected workflow object replacement.")
        self.refresh()

    def refresh(self):
        logger.debug("WorkflowVisualizer refresh called.")
        self._update_node_positions()
        self._create_plot()

    def _update_node_positions(self):
        """从 workflow 对象中提取或计算节点位置。"""
        pos = {}
        if self.workflow and self.workflow.graph:
            # 尝试从节点属性获取位置，如果不存在，则使用 networkx 布局算法
            pos = nx.get_node_attributes(self.workflow.graph, 'pos')
            if not pos or len(pos) != len(self.workflow.graph.nodes):
                 logger.info("Node positions not found or incomplete in graph attributes, calculating spring layout.")
                 try:
                     # 使用 spring_layout 作为备选，可能需要调整参数
                     pos = nx.spring_layout(self.workflow.graph, k=0.8, iterations=50)
                     # 可以考虑将计算出的位置存回 workflow graph (如果 workflow 设计允许)
                     # nx.set_node_attributes(self.workflow.graph, pos, 'pos')
                 except Exception as e:
                     logger.error(f"Error calculating graph layout: {e}", exc_info=True)
                     # 使用随机布局作为最终备选
                     pos = nx.random_layout(self.workflow.graph)

        self._node_positions = pos
        # print(f"Updated node positions: {self._node_positions}")

    def _create_plot(self):
        """创建或更新 HoloViews 图形 (无交互)。"""
        if not self.workflow or not self.workflow.graph or not self.workflow.graph.nodes:
            logger.debug("Workflow is empty, clearing plot pane.")
            # 创建一个空视图或提示信息
            empty_text = hv.Text(0, 0, "工作流为空").opts(xaxis=None, yaxis=None, toolbar=None)
            new_pane = pn.pane.HoloViews(empty_text, sizing_mode='stretch_both')
            if self._plot_pane.object != new_pane.object: # 避免不必要的更新
                 self._plot_pane.object = new_pane.object
            # if self.selected_node_id is not None: # 不再需要
            #      self.selected_node_id = None
            return

        G = self.workflow.graph
        pos = self._node_positions

        if not pos:
            self._update_node_positions()
            pos = self._node_positions
            if not pos:
                 logger.warning("Could not obtain node positions for plotting.")
                 pos = None 
                 
        # 定义节点悬停提示信息
        node_hover = HoverTool(
             tooltips=[
                 ("ID", "@index"), # @index 会自动获取节点的 ID
                 ("Type", "@node_type"), # 需要将 node_type 添加到节点属性中
                 ("Params", "@params_str"), # 需要将参数摘要添加到节点属性中
             ]
         )
        
        # 获取节点类型和参数信息
        node_types = {nid: node.node_type for nid, node in self.workflow._nodes.items()}
        # 使用 node.param.values() 获取参数字典
        node_params_str = {nid: str(node.param.values()) for nid, node in self.workflow._nodes.items()}
        
        # 将信息添加到图的节点属性中，供悬停工具使用
        nx.set_node_attributes(G, node_types, 'node_type')
        nx.set_node_attributes(G, node_params_str, 'params_str')

        # 使用 hvplot.networkx 绘制图形
        # directed=True 确保箭头
        # nodes_opts 和 edge_opts 用于样式控制
        graph_plot = hvnx.draw(
            G,
            pos=pos,
            node_size=150, # 节点大小
            node_color='skyblue',
            # node_label='index', # 可以在节点旁边显示ID，但可能重叠
            arrowhead_length=0.05, # 箭头大小
            edge_color='gray',
            edge_width=1,
            # width=600, height=400, # 使用 sizing_mode 控制大小
            padding=0.1
        )

        # 设置 HoloViews 选项 (移除 tap 工具)
        graph_plot = graph_plot.opts(
            opts.Nodes(tools=[node_hover]), # 只保留悬停工具
            # opts.Edges(
            #      # color='edge_color',
            #      # line_width='edge_width'
            # ),
            opts.Graph(
                xaxis=None, yaxis=None, # 隐藏坐标轴
                show_legend=False,
                padding=0.1,
                # aspect='equal' # 保持比例
            )
        )

        logger.debug("HoloViews static plot created/updated.")
        # 直接更新 pane 的 object
        if self._plot_pane.object != graph_plot:
             self._plot_pane.object = graph_plot
        # self.param.trigger('_plot_pane') # 更新 object 会自动触发

    @param.depends('_plot_pane')
    def view(self) -> pn.viewable.Viewable:
        """返回 HoloViews 图形面板。"""
        return self._plot_pane

    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 表示。"""
        # 确保在返回前至少创建/更新一次视图
        # self._update_plot_data() # 这可能会导致不必要的重复计算，依赖初始化和watch
        return self.view 