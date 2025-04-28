# ui/components/workflow_canvas.py
import panel as pn
import param
import logging
import networkx as nx
from bokeh.plotting import figure, from_networkx
from bokeh.models import (
    Plot, ColumnDataSource, StaticLayoutProvider, Circle, MultiLine, TapTool,
    HoverTool, BoxSelectTool, NodesAndLinkedEdges, EdgesAndLinkedNodes,
    GraphRenderer, PointDrawTool, LabelSet
)
from bokeh.palettes import Spectral8 # Or any other palette
from bokeh.events import Tap, DoubleTap, SelectionGeometry

# 确保可以访问核心模块
try:
    from core.workflow import Workflow
except ImportError:
    # 处理直接运行或测试时的导入问题 (如果需要)
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from core.workflow import Workflow

# Ensure Bokeh extension is loaded for Panel
pn.extension('bokeh')

logger = logging.getLogger(__name__)

class WorkflowCanvas(param.Parameterized):
    """
    使用 Bokeh 可视化和交互式编辑工作流图。
    """
    workflow = param.ClassSelector(class_=Workflow, doc="要显示和编辑的工作流")
    selected_node_id = param.String(default=None, doc="在画布上选中的节点ID")
    # Signals for interaction results (handled by parent view)
    request_node_context_menu = param.Parameter(default=None, doc="请求显示节点上下文菜单 (携带节点ID和事件)")
    request_edge_creation = param.Parameter(default=None, doc="请求创建边 (携带源/目标ID)")
    request_canvas_context_menu = param.Parameter(default=None, doc="请求显示画布上下文菜单 (携带事件)")
    request_view_update = param.Event(doc="通知父组件视图需要更新") # 用于触发外部更新

    # Bokeh plot object
    _bokeh_plot = param.Parameter(precedence=-1)
    _graph_renderer = param.Parameter(precedence=-1)
    _node_source = param.Parameter(default=ColumnDataSource({'index': [], 'x': [], 'y': [], 'label': [], 'color': [], 'radius': [], 'type': [], 'params_str': []}), precedence=-1)
    _edge_source = param.Parameter(default=ColumnDataSource({'start': [], 'end': []}), precedence=-1)

    # Internal state for edge drawing, etc. (simplified)
    _edge_start_node = param.String(default=None)

    def __init__(self, **params):
        # Call super init first to handle passed parameters like workflow
        super().__init__(**params)
        self._figure = self._create_figure()
        self._bokeh_plot = pn.pane.Bokeh(self._figure, sizing_mode='stretch_both', min_height=500)
        self._update_graph_renderer() # Initial draw based on initial workflow

    def _create_figure(self) -> figure:
        """创建 Bokeh 图形对象和基础工具。"""
        fig = figure(
            title="工作流画布",
            x_range=(-2, 2), y_range=(-2, 2), # Initial range, will adapt
            tools="pan,wheel_zoom,reset,save", # Basic navigation
            active_scroll='wheel_zoom',
            sizing_mode='stretch_both'
        )
        fig.axis.visible = False
        fig.grid.visible = False

        # --- Interaction Tools ---
        # Node Selection (TapTool)
        tap_tool = TapTool(renderers=[]) # We'll set renderers later
        fig.add_tools(tap_tool)

        # Node Dragging (PointDrawTool - requires careful handling)
        # PointDrawTool modifies the source directly. We listen via on_patch.
        # It's crucial that the source columns match what PointDrawTool expects (x, y)
        # And that the renderer is correctly configured.
        draw_tool = PointDrawTool(renderers=[], add=False) # add=False means only dragging
        fig.add_tools(draw_tool)

        # Double Tap for adding nodes (on empty space) - Example Handler
        # fig.on_event(DoubleTap, self._handle_double_tap) # Disabled for now

        # Hover Tool (Optional)
        node_hover = HoverTool(
            tooltips=[("类型", "@type"), ("ID", "@index"), ("参数", "@params_str")],
            renderers=[] # Set later
        )
        fig.add_tools(node_hover)

        return fig

    @param.depends('workflow', watch=True)
    def _workflow_changed(self):
        """当外部工作流对象本身发生变化时调用 (e.g., loading a new one)。"""
        logger.debug(f"Workflow object changed to: {self.workflow.name if self.workflow else 'None'}. Redrawing canvas.")
        self._edge_start_node = None # Reset edge drawing state
        # Don't reset selected_node_id here, let the parent view decide if needed
        self._update_graph_renderer()

    def _update_graph_renderer(self, preserve_range: bool = False):
        """根据当前 workflow.graph 更新 Bokeh GraphRenderer。"""
        if not self.workflow:
            logger.debug("_update_graph_renderer skipped: No workflow.")
            if self._graph_renderer:
                 # Attempt to remove cleanly if it exists
                 if self._graph_renderer in self._figure.renderers:
                     self._figure.renderers.remove(self._graph_renderer)
                 self._graph_renderer = None
            # Clear data sources
            self._node_source.data = self._get_empty_node_data()
            self._edge_source.data = {'start': [], 'end': []}
            self.request_view_update = True # Trigger panel update
            return

        G = self.workflow.graph
        logger.debug(f"Updating graph renderer for workflow '{self.workflow.name}' with {len(G.nodes)} nodes and {len(G.edges)} edges.")

        # --- Prepare Data Sources --- 
        node_indices = list(G.nodes())

        if not node_indices:
            logger.debug("_update_graph_renderer: Graph has no nodes.")
            if self._graph_renderer and self._graph_renderer in self._figure.renderers:
                 self._figure.renderers.remove(self._graph_renderer)
                 self._graph_renderer = None
            self._node_source.data = self._get_empty_node_data()
            self._edge_source.data = {'start': [], 'end': []}
            self.request_view_update = True
            return

        # Get positions, default to (0,0) if missing - IMPORTANT for layout provider
        pos = {nid: G.nodes[nid].get('pos', (0.0, 0.0)) for nid in node_indices}
        graph_layout = StaticLayoutProvider(graph_layout=pos)

        # Update node data source
        node_data = {
            'index': node_indices,
            'x': [p[0] for p in pos.values()],
            'y': [p[1] for p in pos.values()],
            'label': [G.nodes[i].get('label', i) for i in node_indices],
            'type': [G.nodes[i].get('type', 'Unknown') for i in node_indices],
            'params_str': [str(self.workflow.get_node_params(i)) if i in self.workflow._nodes else '{}' for i in node_indices], # Safer access
            'color': [Spectral8[i % len(Spectral8)] for i in range(len(node_indices))], # Simple coloring
            'radius': [7.5] * len(node_indices) # Default radius
        }
        self._node_source.data = node_data

        # Update edge data source
        edge_starts = [u for u, v in G.edges()]
        edge_ends = [v for u, v in G.edges()]
        self._edge_source.data = {'start': edge_starts, 'end': edge_ends}

        # --- Create or Update GraphRenderer --- 
        # Check if renderer needs creation or is already present
        renderer_exists = self._graph_renderer and self._graph_renderer in self._figure.renderers
        if not renderer_exists:
            logger.debug("Creating new GraphRenderer.")
            # Create new renderer
            self._graph_renderer = GraphRenderer()

            # *** Set layout provider before adding renderer to figure ***
            self._graph_renderer.layout_provider = graph_layout

            # Configure node rendering glyphs
            self._graph_renderer.node_renderer.glyph = Circle(radius='radius', fill_color='color', line_color="black", line_width=1)
            self._graph_renderer.node_renderer.selection_glyph = Circle(radius='radius', fill_color='color', line_color="red", line_width=3)
            self._graph_renderer.node_renderer.hover_glyph = Circle(radius='radius', fill_color='color', line_color="blue", line_width=2)
            # Set node data source
            self._graph_renderer.node_renderer.data_source.data = dict(self._node_source.data)

            # Configure edge rendering glyphs
            self._graph_renderer.edge_renderer.glyph = MultiLine(line_color="#CCCCCC", line_alpha=0.8, line_width=2)
            self._graph_renderer.edge_renderer.selection_glyph = MultiLine(line_color=Spectral8[0], line_width=3)
            self._graph_renderer.edge_renderer.hover_glyph = MultiLine(line_color=Spectral8[1], line_width=3)
            # Set edge data source
            self._graph_renderer.edge_renderer.data_source.data = dict(self._edge_source.data)

            # Set selection/inspection policies
            self._graph_renderer.selection_policy = NodesAndLinkedEdges()
            self._graph_renderer.inspection_policy = EdgesAndLinkedNodes()

            # *** Add the new renderer to the figure after configuration ***
            self._figure.renderers.append(self._graph_renderer)

            # --- Connect Tools to the NEW Renderer --- 
            for tool in self._figure.tools:
                 if isinstance(tool, (TapTool, HoverTool, PointDrawTool)):
                     tool.renderers = [self._graph_renderer.node_renderer]

            # --- Register Event Handlers (only once after renderer creation) --- 
            if not hasattr(self, '_handlers_registered'): # Prevent duplicate registrations
                self._figure.on_event(Tap, self._handle_tap)
                self._node_source.on_patch(self._handle_node_drag_patch)
                self._handlers_registered = True
                logger.debug("Event handlers registered for Tap and Node Patch.")
        else:
             logger.debug("Updating existing GraphRenderer.")
             # *** Update existing renderer's layout and data sources ***
             self._graph_renderer.layout_provider = graph_layout
             self._graph_renderer.node_renderer.data_source.data = dict(self._node_source.data)
             self._graph_renderer.edge_renderer.data_source.data = dict(self._edge_source.data)

        # --- Adjust plot range if needed --- 
        if not preserve_range and node_indices:
            x_coords = node_data['x']
            y_coords = node_data['y']
            if x_coords and y_coords: # Check if not empty
                 margin = 0.5
                 x_min, x_max = min(x_coords), max(x_coords)
                 y_min, y_max = min(y_coords), max(y_coords)
                 # Add check for single node case where min == max
                 x_range_width = (x_max - x_min) if x_max > x_min else 1.0
                 y_range_width = (y_max - y_min) if y_max > y_min else 1.0
                 self._figure.x_range.start = x_min - margin * x_range_width
                 self._figure.x_range.end = x_max + margin * x_range_width
                 self._figure.y_range.start = y_min - margin * y_range_width
                 self._figure.y_range.end = y_max + margin * y_range_width
                 logger.debug(f"Adjusted plot range: X=[{self._figure.x_range.start:.2f}, {self._figure.x_range.end:.2f}], Y=[{self._figure.y_range.start:.2f}, {self._figure.y_range.end:.2f}]")

        logger.debug("Graph renderer update complete.")
        # Triggering the update of the Bokeh pane itself
        self.request_view_update = True
        # self._bokeh_plot.object = None # Force refresh trick (can be unstable)
        # self._bokeh_plot.object = self._figure

    def _get_empty_node_data(self):
        """Returns an empty dictionary structure for the node source."""
        return {'index': [], 'x': [], 'y': [], 'label': [], 'color': [], 'radius': [], 'type': [], 'params_str': []}

    def _handle_tap(self, event: Tap):
        """处理画布上的单击事件。"""
        if not self._graph_renderer: return # 防御性检查
        selected_indices = self._graph_renderer.node_renderer.data_source.selected.indices
        if selected_indices:
            tapped_node_index = selected_indices[-1] # 最后选定的
            if tapped_node_index < len(self._node_source.data['index']):
                 node_id = self._node_source.data['index'][tapped_node_index]
                 logger.info(f"节点被点击: {node_id}")
                 self.selected_node_id = node_id
                 self._edge_start_node = None
            else:
                 logger.warning(f"点击选择的索引 {tapped_node_index} 超出节点数据范围。")
                 self.selected_node_id = None
                 self._edge_start_node = None
        else:
             logger.debug("点击了空白画布区域。")
             if self.selected_node_id is not None:
                  self.selected_node_id = None # 如果点击空白区域则取消选择
             self._edge_start_node = None # 取消边绘制


    def _handle_node_drag_patch(self, attr, old, new):
        """处理 PointDrawTool 或直接修改 node_source 导致的节点位置变化。"""
        logger.debug(f"节点源被修补: {attr} {new}")
        updated_nodes_in_workflow = False
        if attr in ('x', 'y'):
            for index, new_coord in new:
                 if isinstance(index, int) and index < len(self._node_source.data['index']):
                     node_id = self._node_source.data['index'][index]
                     try:
                         current_pos = self.workflow.get_node_position(node_id) or (0.0, 0.0)
                         new_x = new_coord if attr == 'x' else current_pos[0]
                         new_y = new_coord if attr == 'y' else current_pos[1]
                         new_pos_tuple = (new_x, new_y)
                         if abs(new_pos_tuple[0] - current_pos[0]) > 1e-6 or abs(new_pos_tuple[1] - current_pos[1]) > 1e-6:
                             logger.info(f"节点 '{node_id}' (通过补丁 {attr}) 拖拽到 {new_pos_tuple}")
                             self.workflow.update_node_position(node_id, new_pos_tuple)
                             updated_nodes_in_workflow = True
                         else:
                             logger.debug(f"节点 '{node_id}' 的拖拽补丁被忽略，位置几乎未变。")
                     except KeyError:
                         logger.warning(f"更新时在工作流图中未找到被拖拽的节点 '{node_id}'。")
                     except Exception as e:
                          logger.error(f"从补丁更新节点 '{node_id}' 的位置时出错: {e}")
                 else:
                      logger.warning(f"节点拖拽补丁的索引无效: {index}")

    # --- Methods for external control --- 
    def update_node_style(self, node_id: str, **style_props):
         """尝试更新单个节点的样式 (颜色, 半径等)。"""
         if not self._node_source or 'index' not in self._node_source.data:
              logger.warning("Cannot update style, node source is not ready.")
              return
         try:
            node_list = self._node_source.data['index']
            if node_id in node_list:
                idx = node_list.index(node_id)
                patch_data = {key: [(idx, value)] for key, value in style_props.items() if key in self._node_source.data}
                if patch_data:
                    self._node_source.patch(patch_data)
                    logger.debug(f"Patched style for node '{node_id}': {style_props}")
                else:
                    logger.warning(f"No valid style keys provided for patching node '{node_id}': {style_props.keys()}")
            else:
                logger.warning(f"Cannot update style, node '{node_id}' not found in current view source index.")
         except Exception as e:
             logger.error(f"Error patching style for node '{node_id}': {e}")


    def redraw(self, preserve_range: bool = True):
         """强制重新绘制图形，通常在工作流结构改变后调用。"""
         logger.info(f"Redrawing workflow canvas... Preserve range: {preserve_range}")
         # Simply call the update method
         self._update_graph_renderer(preserve_range=preserve_range)

    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 表示 (Bokeh 图)。"""
        return self._bokeh_plot 