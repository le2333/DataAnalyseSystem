import panel as pn
import param
import logging
import networkx as nx
import numpy as np # 导入 numpy 用于距离计算
import hvplot.networkx as hvnx # 保留以备将来使用？也许稍后移除。
import holoviews as hv
from holoviews import opts
# 导入 Selection1D 而不是 SingleTap
from holoviews.streams import Selection1D
from bokeh.models import HoverTool

# 不再直接需要 Workflow，通过 ViewModel 获取
# from core.workflow import Workflow
# 导入 ViewModel
from viewmodels import WorkflowViewModel
# 引入 BaseNode 用于处理 workflow.nodes 可能为空的情况
from core.node import BaseNode
from .base_panel import BasePanelComponent # 导入基类

hv.extension('bokeh')
logger = logging.getLogger(__name__)

# 移除 TAP_THRESHOLD_DISTANCE_SQ 因为不再需要

class WorkflowVisualizer(BasePanelComponent):
    """
    使用 HoloViews 核心元素 (Graph, Nodes, Labels) 和 Selection1D 可视化工作流图。
    """
    # --- 输入参数 --- (view_model 从基类继承)
    # workflow = param.ClassSelector(class_=Workflow, precedence=-1) # 不再需要，通过 view_model.model 获取

    # --- 输出参数 / 事件 ---
    # 已移除: tapped_node_id 不再用于信号传递
    # tapped_node_id = param.String(default=None, doc="最后被点击的节点ID")

    # --- 内部状态 ---
    _plot_pane = param.Parameter(default=pn.pane.HoloViews(None, sizing_mode='stretch_both'), precedence=-1)
    _node_positions = param.Dict(default={})
    # 使用 Selection1D 流
    _selection_stream = param.Parameter(None, precedence=-1)
    _current_plot = param.Parameter(None, precedence=-1)

    def __init__(self, view_model: WorkflowViewModel, **params):
        params['view_model'] = view_model
        super().__init__(**params)
        logger.info(f"WorkflowVisualizer __init__: ViewModel: {self.view_model}")
        
        # --- 恢复直接监听器 --- 
        logger.info("WorkflowVisualizer: 正在恢复监听器...")
        self.view_model.param.watch(self.refresh, 'available_node_ids')
        self.view_model.param.watch(self.refresh, 'connection_list_data')
        self.view_model.param.watch(self._handle_workflow_replacement, 'model')
        logger.info("WorkflowVisualizer: 监听器已恢复。")
        # ----------------------
        
        self._update_node_positions()
        self._create_plot()
        logger.info(f"WorkflowVisualizer __init__: 初始绘图已创建。Pane 对象: {type(self._plot_pane.object)}")

    # 监听 view_model.model 而不是 self.workflow
    # @param.depends('workflow', watch=True)
    def _handle_workflow_replacement(self, event=None):
        new_model = event.new if event else self.view_model.model
        logger.info(f"WorkflowVisualizer: ViewModel 的模型已更改。新模型: {new_model.name if new_model else 'None'}。正在刷新绘图。")
        self.refresh()

    def refresh(self, event=None):
        # Restore INFO level for refresh call log
        logger.info(f"--- WorkflowVisualizer refresh 被调用 (事件: {event.name if event else 'manual'}) ---")
        workflow = self.view_model.model
        self._update_node_positions()
        self._create_plot()
        logger.info(f"WorkflowVisualizer refresh 完成。Pane 对象: {type(self._plot_pane.object)}")

    def _update_node_positions(self):
        """从 view_model.model 对象中提取或计算节点位置。"""
        pos = {}
        workflow = self.view_model.model # 从 view_model 获取工作流
        if workflow and workflow.graph:
            pos = nx.get_node_attributes(workflow.graph, 'pos')
            # 确保所有节点都有位置
            all_nodes = list(workflow.graph.nodes())
            if not pos or any(nid not in pos for nid in all_nodes):
                 logger.info("未找到或不完整的节点位置，正在计算 spring 布局。")
                 try:
                     # 如果可用，使用现有位置作为固定位置
                     fixed_nodes = list(pos.keys()) if pos else None
                     pos = nx.spring_layout(workflow.graph, pos=pos, fixed=fixed_nodes, k=0.8, iterations=50, seed=42)
                 except Exception as e:
                     logger.error(f"计算图形布局时出错: {e}", exc_info=True)
                     pos = {nid: (0,0) for nid in all_nodes} # 回退方案
                     # 如果 spring 布局严重失败，尝试使用 random 作为最后手段
                     try:
                         pos = nx.random_layout(workflow.graph, seed=42)
                     except Exception as e_rand:
                         logger.error(f"计算随机布局时出错: {e_rand}", exc_info=True)
                         pos = {nid: (0.5, 0.5) for nid in all_nodes}
        self._node_positions = pos

    def _create_plot(self):
        logger.info("调用了 WorkflowVisualizer _create_plot (使用 hv.Graph 和 Selection1D)。")
        workflow = self.view_model.model
        # Remove graph nodes log at start, rely on the empty check
        # graph_nodes_at_start = ...
        # logger.critical(...) 
        
        # --- 处理空工作流 (使用 .object 更新) --- 
        if not workflow or not workflow.graph or not workflow.graph.nodes:
            nodes_count = len(workflow.graph.nodes) if workflow and workflow.graph else 0
            logger.warning(f"工作流为空或没有节点 (节点数: {nodes_count})。正在清除绘图窗格。")
            empty_text = hv.Text(0, 0, "工作流为空").opts(xaxis=None, yaxis=None, toolbar=None)
            if isinstance(self._plot_pane, pn.pane.HoloViews):
                self._plot_pane.object = empty_text
            else:
                 logger.warning("_create_plot (empty): _plot_pane 不是 HoloViews Pane，正在替换。")
                 self._plot_pane = pn.pane.HoloViews(empty_text, sizing_mode='stretch_both')
            self._current_plot = None
            if self._selection_stream: self._selection_stream.source = None
            return

        G = workflow.graph
        pos = self._node_positions
        # Make sure positions are correctly embedded in the graph G for hv.Graph
        # (Workflow.add_node already does this, but double-check or re-apply here if needed)
        nx.set_node_attributes(G, pos, 'pos')
        # Also ensure type and label are present as node attributes in G
        # (Workflow.add_node should handle this)

        # <<< 在创建 hv.Graph 之前，解包 pos 到 x, y 节点属性 >>>
        if pos:
            for node_id, position in pos.items():
                if node_id in G:
                    G.nodes[node_id]['x'] = position[0]
                    G.nodes[node_id]['y'] = position[1]
        # -----------------------------------------------------

        logger.info(f"_create_plot: Graph nodes with attributes: {list(G.nodes(data=True))}")
        logger.info(f"_create_plot: Graph edges with attributes: {list(G.edges(data=True))}")
        
        try:
            # --- 创建 HoloViews Graph 直接从 NetworkX graph G --- 
            # 移除 kdims，让 HV 自动推断边的连接方式
            # 将 x, y 加入 vdims
            graph_element = hv.Graph(G, vdims=['type', 'label', 'x', 'y'])
            logger.info("_create_plot: hv.Graph element created directly from G.")
            
            # Source labels from the graph element's nodes, using x, y kdims
            labels_element = hv.Labels(graph_element.nodes, kdims=['x', 'y'], vdims='index')

            # --- Initialize or Re-link Selection1D Stream --- 
            if self._selection_stream is None:
                self._selection_stream = Selection1D(source=graph_element.nodes)
                self._selection_stream.add_subscriber(self._handle_selection)
                logger.info("Selection1D stream initialized and linked to graph nodes.")
            elif self._selection_stream.source is not graph_element.nodes:
                self._selection_stream.source = graph_element.nodes
                logger.info("Selection1D stream source re-linked to new graph nodes.")
                # Subscriber should persist, no need to re-add usually

            # --- Define HoverTool (使用 type 和 label 属性) --- 
            hover = HoverTool(
                tooltips=[("ID", "@index"), ("类型", "@type"), ("标签", "@label")]
            )

            # --- Apply Options (targeting graph_element) --- 
            is_directed = G.number_of_edges() > 0
            styled_graph = graph_element.opts(
                opts.Nodes(size=15, color='type', cmap='category20',
                           tools=[hover, 'tap'], line_color='black'),
                opts.Graph(xaxis=None, yaxis=None, show_legend=False, padding=0.1,
                           directed=False, # Keep directed=False for now
                           edge_color='gray', edge_line_width=1)
            )
            styled_labels = labels_element.opts(
                 opts.Labels(text_font_size='8pt', text_color='black',
                             text_baseline='bottom', text_align='center', yoffset=0.02)
            )
            logger.info("_create_plot: Options applied to graph and labels.")

            final_plot = styled_graph * styled_labels
            logger.info("_create_plot: Graph and labels overlaid.")

        except Exception as e:
             # --- 处理 HoloViews 错误 (使用 .object 更新) --- 
            logger.error(f"_create_plot: 在 HoloViews 元素创建或应用选项期间出错: {e}", exc_info=True)
            empty_text = hv.Text(0, 0, f"绘图错误: {e}").opts(xaxis=None, yaxis=None, toolbar=None)
            if isinstance(self._plot_pane, pn.pane.HoloViews):
                 self._plot_pane.object = empty_text
            else:
                 logger.warning("_create_plot (hv error): _plot_pane 不是 HoloViews Pane，正在替换。")
                 self._plot_pane = pn.pane.HoloViews(empty_text, sizing_mode='stretch_both')
            self._current_plot = None
            if self._selection_stream: self._selection_stream.source = None
            return

        # --- 更新 Panel 窗格 (使用 .object 更新) --- 
        self._current_plot = final_plot
        logger.info(f"_create_plot: 正在更新现有绘图窗格的 object 属性。")
        try:
            if isinstance(self._plot_pane, pn.pane.HoloViews):
                 self._plot_pane.object = self._current_plot
                 logger.info("_create_plot: 现有绘图窗格的 object 属性已更新。")
            else:
                 logger.warning(f"_create_plot (update): _plot_pane 不是 HoloViews Pane ... 回退到替换 Parameter。")
                 self._plot_pane = pn.pane.HoloViews(self._current_plot, sizing_mode='stretch_both')
        except Exception as e_update:
             logger.error(f"_create_plot: 更新绘图窗格 object 时出错: {e_update}", exc_info=True)
             # 可以考虑在这里设置错误信息，例如也更新为错误文本
             error_text = hv.Text(0, 0, f"更新绘图时出错: {e_update}").opts(xaxis=None, yaxis=None, toolbar=None)
             if isinstance(self._plot_pane, pn.pane.HoloViews):
                  self._plot_pane.object = error_text 
             else:
                  self._plot_pane = pn.pane.HoloViews(error_text, sizing_mode='stretch_both')

    def _handle_selection(self, index=None):
        logger.debug(f"_handle_selection 收到: index={index}")
        selected_node_id = None
        if index and isinstance(index, list) and len(index) > 0:
            selected_idx = index[0] 
            # <<< Read data from graph_element.nodes.data >>>
            if self._current_plot and hasattr(self._current_plot, 'nodes'): 
                nodes_data = self._current_plot.nodes.data # Get DataFrame/Dict from Nodes element
                # Check if it's pandas DataFrame or dictionary-like
                if hasattr(nodes_data, 'iloc'): # Pandas DataFrame
                    if not nodes_data.empty and selected_idx < len(nodes_data):
                        try:
                            selected_node_id = nodes_data.iloc[selected_idx].get('index', None) # Use .get for safety
                            if selected_node_id is None: # Try accessing index directly if column name is different
                                selected_node_id = nodes_data.index[selected_idx]
                        except (IndexError, KeyError) as e:
                             logger.warning(f"_handle_selection: Error accessing node data via iloc/index: {e}")
                    else:
                         logger.warning(f"_handle_selection: Index {selected_idx} out of range or nodes_data empty.")
                elif isinstance(nodes_data, dict): # Dictionary
                    # Assuming keys match indices somehow, or need a list conversion
                    # This part might need refinement based on actual nodes_data structure
                    try:
                        node_list = list(nodes_data.get('index', [])) # Try getting 'index' key
                        if not node_list:
                             node_list = list(nodes_data.keys()) # Fallback to dict keys?
                        if selected_idx < len(node_list):
                            selected_node_id = node_list[selected_idx]
                    except Exception as e:
                        logger.warning(f"_handle_selection: Error accessing node data from dict: {e}")
                else:
                     logger.warning(f"_handle_selection: Unexpected nodes_data type: {type(nodes_data)}")

                if selected_node_id:
                    logger.info(f"_handle_selection: 节点索引 {selected_idx} 已选择，映射到 ID: {selected_node_id}")
                    self.view_model.select_node(selected_node_id)
                else:
                    logger.warning(f"_handle_selection: 无法从索引 {selected_idx} 映射节点 ID。")

            else:
                logger.warning("_handle_selection: _current_plot 或其 nodes 属性不可用，无法映射索引。")
        else:
            logger.debug("_handle_selection: 未选择任何节点。")
            self.view_model.select_node(None)

    # panel() 方法现在由基类提供 (如果它是抽象的)
    # 如果基类的 panel() 不满足需求，可以覆盖它
    # def panel(self) -> pn.viewable.Viewable:
    #     """返回此组件的 Panel 表示。"""
    #     # 可能需要确保 _plot_pane 是最新的？
    #     # 或者直接返回 _plot_pane 参数本身，让 Panel 处理更新？
    #     return pn.panel(self._plot_pane) # 尝试直接返回参数

    # 移除 view() 方法，panel() 是标准接口
    # @param.depends('_plot_pane')
    # def view(self) -> pn.viewable.Viewable:
    #     logger.debug("WorkflowVisualizer view() called.")
    #     return self._plot_pane

    @param.depends('_plot_pane')
    def view(self) -> pn.viewable.Viewable:
        """返回包含 HoloViews 绘图的 Panel 窗格。"""
        return self._plot_pane

    # 实现抽象方法
    def panel(self) -> pn.viewable.Viewable:
        """与 view() 相同，用于一致性。"""
        return self.view() 