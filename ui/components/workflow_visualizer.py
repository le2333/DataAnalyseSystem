import panel as pn
import param
import logging
import networkx as nx
import hvplot.networkx as hvnx
import holoviews as hv
from holoviews import opts
from holoviews.streams import Tap # 导入 Tap 流
from bokeh.models import HoverTool

from core.workflow import Workflow

hv.extension('bokeh')
logger = logging.getLogger(__name__)

class WorkflowVisualizer(param.Parameterized):
    """
    使用 hvPlot 和 NetworkX 可视化工作流图，并支持节点点击。
    """
    workflow = param.ClassSelector(class_=Workflow, precedence=-1)
    # 输出参数：暴露被点击的节点 ID
    tapped_node_id = param.String(default=None, doc="最后被点击的节点ID")

    # 内部状态
    _plot_pane = param.Parameter(default=pn.pane.HoloViews(None, sizing_mode='stretch_both'), precedence=-1)
    _node_positions = param.Dict(default={})
    _tap_stream = param.Parameter(None, precedence=-1) # 用于 Tap 流
    _current_plot = param.Parameter(None, precedence=-1) # 存储当前 plot 对象以连接流

    def __init__(self, **params):
        super().__init__(**params)
        logger.info(f"WorkflowVisualizer __init__: Received workflow: {self.workflow.name if self.workflow else 'None'}")
        self._tap_stream = Tap(transient=True)
        self._update_node_positions()
        self._create_plot() # Initial plot creation
        logger.info(f"WorkflowVisualizer __init__: Initial plot created. Pane object: {type(self._plot_pane.object)}")

    @param.depends('workflow', watch=True)
    def _handle_workflow_replacement(self, event=None):
        logger.info(f"WorkflowVisualizer: Workflow object replaced. New workflow: {self.workflow.name if self.workflow else 'None'}. Refreshing plot.")
        self.tapped_node_id = None
        self.refresh()

    def refresh(self):
        logger.info("WorkflowVisualizer refresh called.")
        self._update_node_positions()
        self._create_plot()
        logger.info(f"WorkflowVisualizer refresh finished. Pane object: {type(self._plot_pane.object)}")

    def _update_node_positions(self):
        """从 workflow 对象中提取或计算节点位置。"""
        pos = {}
        if self.workflow and self.workflow.graph:
            pos = nx.get_node_attributes(self.workflow.graph, 'pos')
            if not pos or len(pos) != len(self.workflow.graph.nodes):
                 logger.info("Node positions not found or incomplete, calculating spring layout.")
                 try:
                     pos = nx.spring_layout(self.workflow.graph, k=0.8, iterations=50, seed=42)
                 except Exception as e:
                     logger.error(f"Error calculating graph layout: {e}", exc_info=True)
                     pos = nx.random_layout(self.workflow.graph, seed=42)
        self._node_positions = pos

    def _create_plot(self):
        logger.info("WorkflowVisualizer _create_plot called.")
        if not self.workflow or not self.workflow.graph or not self.workflow.graph.nodes:
            nodes_count = len(self.workflow.graph.nodes) if self.workflow and self.workflow.graph else 0
            logger.warning(f"Workflow is empty or has no nodes (Nodes: {nodes_count}). Clearing plot pane.")
            empty_text = hv.Text(0, 0, "工作流为空").opts(xaxis=None, yaxis=None, toolbar=None)
            if not isinstance(self._plot_pane.object, hv.Text) or self._plot_pane.object.text != "工作流为空":
                 self._plot_pane.object = empty_text
            self._current_plot = None
            return

        G = self.workflow.graph
        pos = self._node_positions
        logger.info(f"_create_plot: Plotting graph with {len(G.nodes)} nodes and {len(G.edges)} edges.")

        if not pos or len(pos) != len(G.nodes):
            logger.error(f"_create_plot: Node positions are missing or incomplete ({len(pos)} positions for {len(G.nodes)} nodes). Cannot plot.")
            empty_text = hv.Text(0, 0, "错误：节点位置信息不完整").opts(xaxis=None, yaxis=None, toolbar=None)
            if not isinstance(self._plot_pane.object, hv.Text) or "节点位置信息不完整" not in self._plot_pane.object.text:
                 self._plot_pane.object = empty_text
            self._current_plot = None
            return
            
        # --- Explicitly prepare node data for hv.Nodes --- 
        node_ids = list(G.nodes())
        node_data = {
            'index': node_ids,
            'x': [pos[nid][0] for nid in node_ids],
            'y': [pos[nid][1] for nid in node_ids],
            'node_type': [],
            'params_str': []
        }

        if self.workflow.nodes:
            node_types_dict = {nid: node.node_type for nid, node in self.workflow.nodes.items()}
            node_params_dict = {}
            for nid, node in self.workflow.nodes.items():
                 try:
                     node_params_dict[nid] = str(node.param.values())
                 except Exception as e:
                      logger.warning(f"Could not get params for node {nid}: {e}")
                      node_params_dict[nid] = "Error"
            
            # Map attributes to the ordered node_ids list
            node_data['node_type'] = [node_types_dict.get(nid, 'Unknown') for nid in node_ids]
            node_data['params_str'] = [node_params_dict.get(nid, 'Error') for nid in node_ids]
        else:
            logger.error("_create_plot: workflow.nodes dictionary is empty! Cannot get node details for hover.")
            node_data['node_type'] = ['Error'] * len(node_ids)
            node_data['params_str'] = ['Error'] * len(node_ids)

        logger.debug(f"_create_plot: Prepared node data: {node_data}")

        try:
            # --- Create hv.Nodes explicitly --- 
            nodes_element = hv.Nodes(node_data, kdims=['x', 'y', 'index'], vdims=['node_type', 'params_str'])
            logger.info("_create_plot: hv.Nodes element created successfully.")
            
            # --- Create hv.Graph using the NetworkX graph and the hv.Nodes element --- 
            # Pass edge information implicitly from G, node info from nodes_element
            graph_element = hv.Graph((G, nodes_element))
            logger.info("_create_plot: hv.Graph element created successfully using (G, nodes_element).")
            
            # --- Add subscriber and apply options --- 
            self._tap_stream.add_subscriber(self._handle_tap)
            logger.info("Added _handle_tap as subscriber to tap stream.")

            node_hover = HoverTool(
                tooltips=[("ID", "@index"), ("Type", "@node_type"), ("Params", "@params_str")]
            )
            
            # Apply options using .opts()
            # Combine Graph, Nodes, and Edge styling in one call
            graph_plot = graph_element.opts(
                # Options specific to Nodes element
                opts.Nodes(size=10, fill_color='skyblue', line_color='black', 
                           tools=[node_hover, 'tap'], active_tools=['tap']), 
                # Options specific to Graph element (including edge styling)
                opts.Graph(xaxis=None, yaxis=None, show_legend=False, padding=0.1, 
                           edge_color='gray', edge_line_width=1) # Apply edge styles here
            )
            logger.info("_create_plot: HoloViews options applied to hv.Graph.")

        except Exception as e:
            logger.error(f"_create_plot: Error during hv.Nodes/hv.Graph creation or opts: {e}", exc_info=True)
            empty_text = hv.Text(0, 0, f"绘图错误: {e}").opts(xaxis=None, yaxis=None, toolbar=None)
            if not isinstance(self._plot_pane.object, hv.Text) or "绘图错误" not in self._plot_pane.object.text:
                 self._plot_pane.object = empty_text
            self._current_plot = None
            return
            
        logger.info(f"_create_plot: Updating plot pane. Current object type: {type(self._plot_pane.object)}, New object type: {type(graph_plot)}")
        self._current_plot = graph_plot
        self._plot_pane.object = self._current_plot
        logger.info("_create_plot: Plot pane object updated.")

    def _handle_tap(self, x, y):
        # Keep simplified callback
        logger.critical(f"***** _handle_tap CALLED! x={x}, y={y} *****") 

    @param.depends('_plot_pane')
    def view(self) -> pn.viewable.Viewable:
        """返回 HoloViews 图形面板。"""
        return self._plot_pane

    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 表示。"""
        return self.view 