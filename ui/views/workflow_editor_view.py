import panel as pn
import param
import logging
import uuid
from typing import Dict, Any, Optional, List, Tuple

from core.workflow import Workflow
from core.node import NodeRegistry # For edge config
from ui.components.node_palette import NodePalette
from ui.components.workflow_visualizer import WorkflowVisualizer

logger = logging.getLogger(__name__)

class WorkflowEditorView(param.Parameterized):
    """
    独立的编辑器视图，用于管理工作流的可视化和配置。
    左侧节点库，中间上可视化下管理，右侧节点参数。
    """
    # --- Core Objects ---
    workflow = param.ClassSelector(class_=Workflow)

    # --- State ---
    selected_node_id = param.String(default=None, doc="当前选中的节点ID")

    # --- UI Components (Initialized in __init__) ---
    node_palette: NodePalette = None
    visualizer: WorkflowVisualizer = None
    node_selector = param.Parameter() # 用于节点管理标签页的选择器
    delete_node_button = param.Parameter() # 新增删除按钮
    # 边配置控件将在 __init__ 中创建
    # 右侧配置面板将动态填充

    # --- Layout Panes ---
    _left_pane = param.Parameter(precedence=-1)
    _center_top_pane = param.Parameter(precedence=-1)
    # _center_bottom_pane 现在是 Tabs 对象
    _management_panel_container = param.Parameter(precedence=-1)
    _right_pane = param.Parameter(default=pn.Column("选择一个节点以查看其配置", sizing_mode='stretch_width'), precedence=-1)

    # --- Edge Creation Widgets ---
    source_node_select = param.Parameter()
    source_port_select = param.Parameter()
    target_node_select = param.Parameter()
    target_port_select = param.Parameter()
    add_edge_button = param.Parameter()

    def __init__(self, workflow: Optional[Workflow] = None, **params):
        if workflow is None:
            workflow = Workflow(name="New Workflow")
        params['workflow'] = workflow
        super().__init__(**params)

        self.node_palette = NodePalette()
        self.visualizer = WorkflowVisualizer(workflow=self.workflow)
        self._create_edge_widgets()
        self.node_selector = pn.widgets.Select(name="选择节点配置", options=[], sizing_mode='stretch_width')
        self.delete_node_button = pn.widgets.Button(name="🗑️ 删除选中节点", button_type="danger", sizing_mode='stretch_width', disabled=True) # 初始禁用

        self._left_pane = pn.Column(self.node_palette.panel(), width=250, styles={'background':'#fafafa'})
        self._center_top_pane = self.visualizer.panel()
        self._management_panel_container = self._build_management_panel() # 构建初始管理面板

        # --- Bind Interactions ---
        self.node_palette.param.watch(self._add_node_from_palette, 'selected_node_type')
        self.node_selector.param.watch(self._update_selection_from_selector, 'value')
        self.param.watch(self._update_right_pane, 'selected_node_id')
        self.param.watch(self._enable_delete_button, 'selected_node_id') # 监听选中节点变化以启用/禁用删除按钮
        self.delete_node_button.on_click(self._remove_selected_node) # 绑定删除按钮事件
        # 监听 workflow 变化以更新整个管理面板
        self.param.watch(self._update_management_panel, 'workflow')

        logger.info(f"WorkflowEditorView initialized for workflow: {self.workflow.name}")

    # ===============================================
    # == Edge Configuration Methods ==
    # ===============================================
    
    def _create_edge_widgets(self):
        """创建用于"连接管理"标签页的表单小部件。"""
        self.source_node_select = pn.widgets.Select(name="源节点", options=[], width=120)
        self.source_port_select = pn.widgets.Select(name="源端口", options=[], width=120)
        self.target_node_select = pn.widgets.Select(name="目标节点", options=[], width=120)
        self.target_port_select = pn.widgets.Select(name="目标端口", options=[], width=120)
        self.add_edge_button = pn.widgets.Button(name="🔗 添加连接", button_type="primary", width=100)
        
        self.source_node_select.param.watch(self._update_source_ports, 'value')
        self.target_node_select.param.watch(self._update_target_ports, 'value')
        self.add_edge_button.on_click(self._add_edge)
        # self.param.watch(self._update_node_options, 'workflow') # node options 由 _update_node_management_tab 处理
        # self._update_node_options() # init 时由 _update_node_management_tab 调用
        
    # _update_node_options 被合并到 _update_node_management_tab

    def _update_source_ports(self, event=None):
        """当源节点选择变化时，更新源端口下拉列表。"""
        node_id = self.source_node_select.value
        ports = []
        if node_id and self.workflow:
            try:
                node_instance = self.workflow.get_node(node_id)
                node_cls = NodeRegistry.get_node_class(node_instance.node_type)
                if node_cls:
                    ports = list(node_cls.define_outputs().keys())
            except Exception as e:
                logger.error(f"获取节点 '{node_id}' 输出端口失败: {e}")
        self.source_port_select.options = ports
        
    def _update_target_ports(self, event=None):
        """当目标节点选择变化时，更新目标端口下拉列表。"""
        node_id = self.target_node_select.value
        ports = []
        if node_id and self.workflow:
            try:
                node_instance = self.workflow.get_node(node_id)
                node_cls = NodeRegistry.get_node_class(node_instance.node_type)
                if node_cls:
                    ports = list(node_cls.define_inputs().keys())
            except Exception as e:
                 logger.error(f"获取节点 '{node_id}' 输入端口失败: {e}")
        self.target_port_select.options = ports
        
    def _add_edge(self, event):
        """处理添加连接按钮点击事件。"""
        source_node = self.source_node_select.value
        source_port = self.source_port_select.value
        target_node = self.target_node_select.value
        target_port = self.target_port_select.value
        if not all([source_node, source_port, target_node, target_port]): return
        if source_node == target_node: return
        logger.info(f"请求添加边: {source_node}.{source_port} -> {target_node}.{target_port}")
        try:
            self.workflow.add_edge(source_node, source_port, target_node, target_port)
            logger.info("边已成功添加到工作流。")
            self.visualizer.refresh() # 刷新静态图
            self._update_management_panel() # 更新管理面板 (含连接列表)
            if pn.state.notifications: pn.state.notifications.success(f"连接 {source_node} -> {target_node} 已添加", duration=2000)
        except ValueError as e:
            logger.error(f"添加边失败: {e}")
            if pn.state.notifications: pn.state.notifications.error(f"添加连接失败: {e}", duration=4000)
        except Exception as e:
            logger.error(f"添加边时发生未知错误: {e}", exc_info=True)
            if pn.state.notifications: pn.state.notifications.error("添加连接时发生内部错误。", duration=4000)
                
    def _remove_edge(self, edge_data: Tuple[str, str, str, str]):
        """删除指定的边。"""
        u, v, source_port, target_port = edge_data
        logger.info(f"请求删除边: {u}.{source_port} -> {v}.{target_port}")
        try:
             self.workflow.remove_edge(u, source_port, v, target_port)
             logger.info(f"连接 {u}.{source_port} -> {v}.{target_port} 已移除。")
             self.visualizer.refresh()
             self._update_management_panel()
             if pn.state.notifications: pn.state.notifications.info(f"连接 {u} -> {v} 已删除。", duration=2000)
        except NotImplementedError:
              logger.error("Workflow.remove_edge(u, sport, v, tport) 方法未实现！")
              if pn.state.notifications: pn.state.notifications.error("删除连接的功能尚未完全实现。", duration=4000)
        except Exception as e:
             logger.error(f"移除边 {u} -> {v} 失败: {e}", exc_info=True)
             if pn.state.notifications: pn.state.notifications.error(f"移除连接失败: {e}", duration=4000)

    # ===============================================
    # == Node Management Methods ==
    # ===============================================

    def _remove_selected_node(self, event):
        """删除当前在 node_selector 中选中的节点。"""
        node_id_to_remove = self.node_selector.value
        if not node_id_to_remove:
            if pn.state.notifications: pn.state.notifications.warning("请先选择要删除的节点。", duration=3000)
            return

        logger.info(f"请求删除节点: {node_id_to_remove}")
        if not self.workflow:
            logger.error("无法删除节点，workflow 对象不存在。")
            return

        try:
            self.workflow.remove_node(node_id_to_remove)
            logger.info(f"节点 '{node_id_to_remove}' 已成功从工作流移除。")

            # 1. 清空选中状态 (会触发 _update_right_pane 清空右侧面板)
            self.selected_node_id = None
            # self.node_selector.value = None # 会在 _update_management_panel 中处理

            # 2. 刷新可视化
            self.visualizer.refresh()

            # 3. 触发管理面板更新 (会更新所有下拉菜单和连接列表)
            #    必须在 visualizer.refresh() 之后，因为它依赖 graph
            self.param.trigger('workflow')

            if pn.state.notifications: pn.state.notifications.success(f"节点 '{node_id_to_remove}' 已删除。", duration=2000)

        except KeyError:
            logger.error(f"尝试删除不存在的节点 '{node_id_to_remove}'。")
            if pn.state.notifications: pn.state.notifications.error(f"删除失败：找不到节点 '{node_id_to_remove}'。", duration=4000)
            # 即使出错也尝试更新一下面板，以防数据不一致
            self.param.trigger('workflow')
        except Exception as e:
            logger.error(f"删除节点 '{node_id_to_remove}' 时发生错误: {e}", exc_info=True)
            if pn.state.notifications: pn.state.notifications.error(f"删除节点时发生内部错误: {e}", duration=4000)
            # 即使出错也尝试更新一下面板
            self.param.trigger('workflow')

    def _enable_delete_button(self, event):
        """根据是否有节点被选中来启用或禁用删除按钮。"""
        self.delete_node_button.disabled = not bool(event.new)

    # ===============================================
    # == Center Bottom Management Panel Builder ==
    # ===============================================

    # @param.depends('workflow', watch=True) # 由 watcher 调用
    def _update_management_panel(self, event=None):
        """工作流变化时，重建整个管理面板。"""
        logger.debug("Workflow changed, rebuilding management panel.")
        self._management_panel_container = self._build_management_panel()
        self.param.trigger('_management_panel_container')

    def _build_management_panel(self) -> pn.Column:
        """构建中间下方的管理面板 (节点管理 + 连接管理)。"""
        node_ids = list(self.workflow._nodes.keys()) if self.workflow else []
        
        # --- 更新节点管理部分的选项 --- 
        try:
             current_selection = self.node_selector.value
             self.node_selector.options = node_ids
             if current_selection in node_ids:
                 self.node_selector.value = current_selection
             # else: # 如果之前选中的节点被删了，选择器会自动变为空
             #     # self.selected_node_id = None # 这个由 _remove_selected_node 处理
             #     pass
        except Exception as e:
             logger.error(f"更新节点选择器选项时出错: {e}")
             
        node_management_section = pn.Column(
            pn.pane.Markdown("#### 节点管理"),
            self.node_selector,
            self.delete_node_button, # 在这里添加删除按钮
            # 可以加其他节点管理按钮
            sizing_mode='stretch_width'
        )
        
        # --- 更新连接管理部分的选项 --- 
        try:
            current_source = self.source_node_select.value
            current_target = self.target_node_select.value
            self.source_node_select.options = node_ids
            self.target_node_select.options = node_ids
            if current_source in node_ids: self.source_node_select.value = current_source
            if current_target in node_ids: self.target_node_select.value = current_target
            self._update_source_ports()
            self._update_target_ports()
        except Exception as e:
            logger.error(f"更新边管理节点下拉菜单时出错: {e}")
            
        connection_rows = [pn.pane.Markdown("#### 连接管理")]
        edge_form = pn.Row(
            self.source_node_select, self.source_port_select, pn.pane.HTML("&nbsp;→&nbsp;"),
            self.target_node_select, self.target_port_select, self.add_edge_button,
            styles={'align-items': 'end'}
        )
        connection_rows.append(edge_form)
        connection_rows.append(pn.pane.HTML("<hr>"))
        connection_rows.append(pn.pane.Markdown("**现有连接:**"))
        if self.workflow and self.workflow.graph:
            if not self.workflow.graph.edges:
                 connection_rows.append(pn.pane.Markdown("_当前没有连接。_"))
            else:
                for u, v, data in self.workflow.graph.edges(data=True):
                    source_port = data.get('source_port', '?')
                    target_port = data.get('target_port', '?')
                    edge_data = (u, v, source_port, target_port)
                    remove_button = pn.widgets.Button(name="🗑️", button_type="danger", width=40, height=30, margin=(0,0,0,5))
                    remove_button.on_click(lambda event, ed=edge_data: self._remove_edge(ed))
                    edge_label = f"`{u}.{source_port}` → `{v}.{target_port}`"
                    connection_rows.append(pn.Row(pn.pane.Markdown(edge_label, margin=(0, 5)), remove_button))
        else:
            connection_rows.append(pn.pane.Markdown("_无工作流或工作流图。_"))
            
        connection_management_section = pn.Column(*connection_rows, sizing_mode='stretch_width')

        # 返回包含两个部分的列布局
        return pn.Column(
            node_management_section,
            pn.layout.Divider(),
            connection_management_section,
            sizing_mode='stretch_width', 
            styles={'padding': '10px'}
        )

    # ===============================================
    # == Interaction Handlers ==
    # ===============================================

    def _add_node_from_palette(self, event: param.parameterized.Event):
        """处理从节点库添加节点，并自动选择，同时设置源节点。"""
        if event.new:
            node_type = event.new
            logger.info(f"接收到添加节点请求: {node_type}")
            if not self.workflow: return
            
            # --- 记住添加前的目标节点 --- 
            previous_target_node = self.target_node_select.value
            logger.debug(f"Previous target node before adding: {previous_target_node}")
            
            try:
                node_id = f"{node_type.lower()}_{uuid.uuid4().hex[:6]}"
                pos = self._get_next_node_position()
                self.workflow.add_node(node_id=node_id, node_type=node_type, position=pos)
                logger.info(f"节点 '{node_id}' ({node_type}) 已添加到工作流。")
                self.visualizer.refresh()
                self.param.trigger('workflow') # 触发管理面板更新
                
                # --- 自动选择新节点 (目标和配置) --- 
                try:
                    # 等待 workflow watcher 更新完选项后再设置值可能更稳妥，
                    # 但 Panel 通常能处理好，先尝试直接设置
                    self.target_node_select.value = node_id # 设置新节点为目标
                    self.node_selector.value = node_id # 设置新节点为选中配置
                    logger.info(f"已自动选择新节点 '{node_id}' 为目标和配置对象。")
                    
                    # --- 自动设置源节点 --- 
                    if previous_target_node and previous_target_node in self.source_node_select.options:
                        self.source_node_select.value = previous_target_node
                        logger.info(f"已自动设置源节点为之前的目标节点 '{previous_target_node}'。")
                    else:
                         logger.info(f"无法自动设置源节点 (之前的目标 '{previous_target_node}' 不存在或无效)。")
                             
                except Exception as e:
                     logger.warning(f"自动选择新/源节点 '{node_id}'/'{previous_target_node}' 失败: {e}")
                     
                if pn.state.notifications: pn.state.notifications.success(f"已添加节点: {node_type}", duration=2000)
            except Exception as e:
                 logger.error(f"添加节点 {node_type} 失败: {e}", exc_info=True)
                 if pn.state.notifications: pn.state.notifications.error(f"添加节点失败: {e}", duration=4000)
            finally:
                self.node_palette.selected_node_type = None
                
    def _get_next_node_position(self, offset_x=50, offset_y=50):
        """计算新节点的简单位置，避免重叠。"""
        max_x, max_y = 0, 0
        positions = self.visualizer._node_positions if hasattr(self.visualizer, '_node_positions') else {}
        if positions:
            try:
                 max_x = max(p[0] for p in positions.values() if p) 
                 max_y = max(p[1] for p in positions.values() if p)
                 return (max_x + offset_x, max_y + offset_y)
            except ValueError:
                 pass
        return (50.0, 50.0) # Default position
        
    def _update_selection_from_selector(self, event: param.parameterized.Event):
        """当节点管理选择器值变化时，更新 selected_node_id。"""
        logger.info(f"[_update_selection_from_selector] Node selector value changed: {event.new}")
        self.selected_node_id = event.new

    def _update_right_pane(self, event: param.parameterized.Event):
        """当选中的节点 ID 变化时，更新右侧的参数配置面板。"""
        node_id = event.new
        logger.info(f"[_update_right_pane] Triggered for selected_node_id: {node_id}")
        if node_id and self.workflow:
            try:
                node = self.workflow.get_node(node_id)
                if hasattr(node, 'get_config_panel'):
                    logger.info(f"[_update_right_pane] Getting config panel for node '{node_id}'...")
                    config_panel = node.get_config_panel()
                    logger.info(f"[_update_right_pane] Got config panel of type: {type(config_panel)}")
                    self._right_pane = pn.Column(config_panel, sizing_mode='stretch_width')
                    logger.info(f"[_update_right_pane] Right pane updated for node '{node_id}'.")
                else:
                     logger.warning(f"[_update_right_pane] Node '{node_id}' 没有实现 get_config_panel。")
                     self._right_pane = pn.Column(f"节点 '{node_id}' 没有提供配置界面。", sizing_mode='stretch_width')
            except KeyError:
                logger.warning(f"[_update_right_pane] 更新右侧面板时未找到节点 '{node_id}'。")
                self._right_pane = pn.Column("错误：找不到选中的节点", sizing_mode='stretch_width')
            except Exception as e:
                 logger.error(f"[_update_right_pane] 获取节点 '{node_id}' 配置面板时出错: {e}", exc_info=True)
                 self._right_pane = pn.Column(f"加载节点 '{node_id}' 配置时出错。", sizing_mode='stretch_width')
        else:
            logger.info("[_update_right_pane] No node selected, setting default message.")
            self._right_pane = pn.Column("选择一个节点以查看其配置", sizing_mode='stretch_width', styles={'padding': '10px'})
        self.param.trigger('_right_pane')

    def _handle_workflow_change(self, event: param.parameterized.Event):
        """处理 workflow 对象被替换的情况 (例如加载)。"""
        logger.info("Workflow object instance changed in WorkflowEditorView.")
        if self.visualizer.workflow is not self.workflow:
             self.visualizer.workflow = self.workflow
        # workflow watcher 会调用 _update_management_panel
        self.selected_node_id = None

    # ===============================================
    # == Layout Definition ==
    # ===============================================
    
    @param.depends('_management_panel_container') # 依赖新的容器参数
    def management_panel(self):
        """返回中间下方的管理面板。"""
        return self._management_panel_container

    @param.depends('_right_pane')
    def right_panel(self):
        """返回右侧的节点配置面板。"""
        return self._right_pane

    def panel(self) -> pn.viewable.Viewable:
        """返回编辑器的主 Panel 布局，调整高度比例。"""
        # 使用两个 Column 实现大致 50/50 分割
        # 父容器 Row 需要有确定的高度，或者使用 sizing_mode='stretch_both'
        center_pane = pn.Column(
            pn.Column(self._center_top_pane, sizing_mode='stretch_both'), # 上方可视化
            pn.Column(self.management_panel, sizing_mode='stretch_both'), # 下方管理面板
            sizing_mode='stretch_width' # 让中间列宽度自动
        )

        main_layout = pn.Row(
            self._left_pane,    # Node Palette (固定宽度)
            center_pane,        # Visualizer + Management Panel (自动宽度)
            self.right_panel,   # Node Config (动态宽度，或固定)
            sizing_mode='stretch_both' # 让整体布局充满页面
        )
        
        return main_layout

# 注意：此视图不再包含运行/保存/加载按钮，这些通常属于更高层的应用视图 (如之前的 MainView)
# 或者可以作为参数传入一个控制面板 