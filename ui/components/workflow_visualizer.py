import panel as pn
import param
import logging
import networkx as nx
import numpy as np # Import numpy for distance calculation
import hvplot.networkx as hvnx # Keep for potential future use? Maybe remove later.
import holoviews as hv
from holoviews import opts
# Import Selection1D instead of SingleTap
from holoviews.streams import Selection1D
from bokeh.models import HoverTool

from core.workflow import Workflow
# Import ViewModel
from viewmodels import WorkflowViewModel
# 引入 BaseNode 用于处理 workflow.nodes 可能为空的情况
from core.node import BaseNode

hv.extension('bokeh')
logger = logging.getLogger(__name__)

# Removed TAP_THRESHOLD_DISTANCE_SQ as it's no longer needed

class WorkflowVisualizer(param.Parameterized):
    """
    使用 HoloViews 核心元素 (Graph, Nodes, Labels) 和 Selection1D 可视化工作流图。
    """
    # --- Input Parameters ---
    workflow = param.ClassSelector(class_=Workflow, precedence=-1)
    view_model = param.ClassSelector(class_=WorkflowViewModel, doc="关联的 WorkflowViewModel", precedence=-1)

    # --- Output Parameters / Events ---
    # REMOVED: tapped_node_id is no longer used for signaling
    # tapped_node_id = param.String(default=None, doc="最后被点击的节点ID")

    # --- Internal State ---
    _plot_pane = param.Parameter(default=pn.pane.HoloViews(None, sizing_mode='stretch_both'), precedence=-1)
    _node_positions = param.Dict(default={})
    # Use Selection1D stream
    _selection_stream = param.Parameter(None, precedence=-1) 
    _current_plot = param.Parameter(None, precedence=-1)
    _nodes_element_cache = param.Parameter(None, precedence=-1)

    def __init__(self, **params):
        # Explicitly check for view_model
        if 'view_model' not in params or params['view_model'] is None:
            raise ValueError("WorkflowVisualizer requires a valid WorkflowViewModel instance.")
        super().__init__(**params)
        logger.info(f"WorkflowVisualizer __init__: Received workflow: {self.workflow.name if self.workflow else 'None'}")
        # Initialize with Selection1D, source set later
        self._selection_stream = Selection1D(source=None)
        self._update_node_positions()
        self._create_plot()
        logger.info(f"WorkflowVisualizer __init__: Initial plot created. Pane object: {type(self._plot_pane.object)}")

    @param.depends('workflow', watch=True)
    def _handle_workflow_replacement(self, event=None):
        logger.info(f"WorkflowVisualizer: Workflow object replaced. New workflow: {self.workflow.name if self.workflow else 'None'}. Refreshing plot.")
        # self.tapped_node_id = None # No longer needed
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
            # Ensure all nodes have positions
            all_nodes = list(self.workflow.graph.nodes())
            if not pos or any(nid not in pos for nid in all_nodes):
                 logger.info("Node positions not found or incomplete, calculating spring layout.")
                 try:
                     # Use existing positions as fixed if available
                     fixed_nodes = list(pos.keys()) if pos else None
                     pos = nx.spring_layout(self.workflow.graph, pos=pos, fixed=fixed_nodes, k=0.8, iterations=50, seed=42)
                 except Exception as e:
                     logger.error(f"Error calculating graph layout: {e}", exc_info=True)
                     pos = {nid: (0,0) for nid in all_nodes} # Fallback
                     # Try random as a last resort if spring fails badly
                     try:
                         pos = nx.random_layout(self.workflow.graph, seed=42)
                     except Exception as e_rand:
                         logger.error(f"Error calculating random layout: {e_rand}", exc_info=True)
                         pos = {nid: (0.5, 0.5) for nid in all_nodes}
        self._node_positions = pos

    def _create_plot(self):
        logger.info("WorkflowVisualizer _create_plot called (using hv.Graph and Selection1D).")
        if not self.workflow or not self.workflow.graph or not self.workflow.graph.nodes:
            nodes_count = len(self.workflow.graph.nodes) if self.workflow and self.workflow.graph else 0
            logger.warning(f"Workflow is empty or has no nodes (Nodes: {nodes_count}). Clearing plot pane.")
            empty_text = hv.Text(0, 0, "工作流为空").opts(xaxis=None, yaxis=None, toolbar=None)
            # Create new pane for empty state
            new_empty_pane = pn.pane.HoloViews(empty_text, sizing_mode='stretch_both')
            # Only replace if the current object isn't already the empty text placeholder? Maybe always replace.
            self._plot_pane = new_empty_pane # Replace parameter value
            self._current_plot = None
            self._nodes_element_cache = None
            if self._selection_stream: self._selection_stream.source = None # Disconnect stream
            return

        G = self.workflow.graph
        pos = self._node_positions
        all_nodes = list(G.nodes())
        logger.info(f"_create_plot: Plotting graph with {len(all_nodes)} nodes and {len(G.edges)} edges.")

        if not pos or any(nid not in pos for nid in all_nodes):
            logger.error(f"_create_plot: Node positions are missing or incomplete ({len(pos)} positions for {len(all_nodes)} nodes). Cannot plot.")
            empty_text = hv.Text(0, 0, "错误：节点位置信息不完整").opts(xaxis=None, yaxis=None, toolbar=None)
            if self._plot_pane.object is None or (isinstance(self._plot_pane.object, hv.Text) and "节点位置信息不完整" not in self._plot_pane.object.label):
                 self._plot_pane.object = empty_text
            self._current_plot = None
            self._nodes_element_cache = None # Clear cache
            if self._selection_stream: self._selection_stream.source = None # Disconnect stream
            return

        # --- Explicitly prepare node data --- 
        node_data = {
            'index': all_nodes,
            'x': [pos[nid][0] for nid in all_nodes],
            'y': [pos[nid][1] for nid in all_nodes],
            'node_type': [],
            'params_str': []
        }
        nodes_dict = self.workflow.nodes or {}
        for nid in all_nodes:
            node = nodes_dict.get(nid)
            if node:
                node_data['node_type'].append(node.node_type)
                try:
                    params_to_show = {p: getattr(node, p) for p in node.param
                                      if node.param[p].precedence != -1 and p not in ['name', 'position', 'workflow_runner']}
                    node_data['params_str'].append(str(params_to_show) if params_to_show else "{}")
                except Exception as e:
                     logger.warning(f"Could not get params for node {nid}: {e}")
                     node_data['params_str'].append("Error")
            else: # 处理图中存在但 _nodes 字典中没有的节点 (理论上不应发生，但增加健壮性)
                logger.warning(f"Node {nid} found in graph but not in workflow.nodes dictionary.")
                node_data['node_type'].append('Unknown')
                node_data['params_str'].append('No Data')
        logger.debug(f"_create_plot: Prepared node data: {node_data}")

        try:
            # --- Create HoloViews elements --- 
            nodes_element = hv.Nodes(node_data, kdims=['x', 'y', 'index'], vdims=['node_type', 'params_str'])
            graph_element = hv.Graph((G, nodes_element))
            labels_element = hv.Labels(nodes_element, kdims=['x', 'y'], vdims='index')
            self._nodes_element_cache = nodes_element # Cache for tap handler
            logger.info("_create_plot: HoloViews elements created (Nodes, Graph, Labels).")

            # --- Link Selection1D stream --- 
            if self._selection_stream.source is not nodes_element:
                 self._selection_stream.source = nodes_element
                 # Ensure subscriber is added only once or handled correctly by HoloViews
                 try: 
                      self._selection_stream.add_subscriber(self._handle_selection)
                      logger.info("Linked Selection1D stream to nodes element and added subscriber.")
                 except Exception as e_sub:
                      # Handle cases where subscriber might already exist depending on HV version
                      logger.warning(f"Could not add subscriber (might already exist): {e_sub}")

            # --- Define HoverTool --- 
            hover = HoverTool(
                tooltips=[("ID", "@index"), ("Type", "@node_type"), ("Params", "@params_str{safe}")]
            )

            # --- Apply options --- 
            styled_nodes = nodes_element.opts(
                opts.Nodes(size=15, color='node_type', cmap='category20',
                           tools=[hover, 'tap'], # Ensure tap tool is present
                           line_color='black')
            )
            styled_graph = graph_element.opts(
                # Apply node styling via the graph element
                 opts.Nodes(size=15, color='node_type', cmap='category20', tools=[hover, 'tap'], line_color='black'),
                 opts.Graph(xaxis=None, yaxis=None, show_legend=False, padding=0.1,
                            # Apply directed only if edges exist
                            directed=(G.number_of_edges() > 0), 
                            edge_color='gray', edge_line_width=1)
            )
            styled_labels = labels_element.opts(
                 opts.Labels(text_font_size='8pt', text_color='black', 
                             text_baseline='bottom', text_align='center', yoffset=0.02) # Offset labels slightly
            )
            logger.info("_create_plot: Options applied.")
            
            # --- Overlay graph and labels --- 
            # Overlay styled elements
            final_plot = styled_graph * styled_labels
            logger.info("_create_plot: Graph and Labels overlaid.")

        except Exception as e:
            logger.error(f"_create_plot: Error during HoloViews elements creation or opts: {e}", exc_info=True)
            empty_text = hv.Text(0, 0, f"绘图错误: {e}").opts(xaxis=None, yaxis=None, toolbar=None)
            if self._plot_pane.object is None or (isinstance(self._plot_pane.object, hv.Text) and "绘图错误" not in self._plot_pane.object.label):
                 self._plot_pane.object = empty_text
            self._current_plot = None
            self._nodes_element_cache = None # Clear cache
            if self._selection_stream: self._selection_stream.source = None # Disconnect stream
            return
            
        logger.info(f"_create_plot: Updating plot pane by creating new pane object.")
        self._current_plot = final_plot
        # Create a new pane object instead of updating the existing one's object
        # Note: This might disconnect bindings if not handled carefully, but can force update.
        # Re-evaluate if this causes issues with stream re-linking etc.
        new_plot_pane = pn.pane.HoloViews(self._current_plot, sizing_mode='stretch_both')
        self._plot_pane = new_plot_pane # Directly replace the parameter's value
        # We might not need trigger if we replace the whole object
        # self._plot_pane.param.trigger('object') 
        logger.info("_create_plot: Plot pane parameter replaced with new pane object.")

    def _handle_selection(self, index=None):
        """Handles selection events using Selection1D (list of indices)."""
        logger.debug(f"_handle_selection received: index={index}")
        selected_node_id = None
        if index and isinstance(index, list) and len(index) > 0:
            selected_idx = index[0] # Use the first selected index for tap-like behavior
            if self._nodes_element_cache is not None:
                 nodes_df = self._nodes_element_cache.data
                 if not nodes_df.empty and selected_idx < len(nodes_df):
                     try:
                         selected_node_id = nodes_df.iloc[selected_idx]['index']
                         logger.info(f"_handle_selection: Node index {selected_idx} selected, mapped to ID: {selected_node_id}")
                     except IndexError:
                          logger.warning(f"_handle_selection: Selected index {selected_idx} out of bounds for node data using iloc.")
                     except KeyError:
                          logger.warning(f"_handle_selection: 'index' column not found in cached node data.")
                 else:
                      logger.warning(f"_handle_selection: Selected index {selected_idx} out of bounds or nodes_df empty.")
            else:
                logger.warning("_handle_selection: Nodes element cache is None, cannot map index.")
        else:
            # No index selected (e.g., clicked empty space or deselected)
            logger.debug("_handle_selection: No index selected. Clearing selection.")
            # selected_node_id remains None

        # Update ViewModel only if the selection state has changed
        current_vm_selection = self.view_model.selected_node_id if self.view_model else '[VM unavailable]'
        if self.view_model and current_vm_selection != selected_node_id:
            logger.info(f"---> Calling view_model.select_node('{selected_node_id}') (Previous: '{current_vm_selection}')")
            try:
                 self.view_model.select_node(selected_node_id)
            except Exception as e:
                 logger.error(f"_handle_selection: Error calling view_model.select_node: {e}", exc_info=True)
        else:
             logger.debug(f"---> NOT calling select_node. Reason: Selection unchanged or no ViewModel. Current: {current_vm_selection}, New: {selected_node_id}")

    @param.depends('_plot_pane')
    def view(self) -> pn.viewable.Viewable:
        """返回 HoloViews 图形面板。"""
        return self._plot_pane

    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 表示。"""
        return self.view 