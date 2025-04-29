import panel as pn
import param
import logging
from typing import List, Tuple, Any, Optional

from core.node import NodeRegistry # 仍然需要 Registry 获取端口
from viewmodels import WorkflowViewModel # 导入 ViewModel

logger = logging.getLogger(__name__)

class ConnectionManagementPanel(param.Parameterized):
    """
    封装连接管理功能的 Panel 组件。
    设计原则：监听 ViewModel 的状态变化更新 UI，用户交互触发 ViewModel 更新。
    目标节点选择由 ViewModel 的 selected_node_id 驱动。
    源节点选择根据目标节点的变化自动设置为上一个目标节点。
    """
    # --- Input Parameters ---
    view_model = param.ClassSelector(class_=WorkflowViewModel, doc="关联的 WorkflowViewModel")

    # --- Output Parameters / Events ---
    request_add_edge_data = param.Parameter(default=None, doc="请求添加边 (source_id, source_port, target_id, target_port)")
    request_remove_edge_data = param.Parameter(default=None, doc="请求删除边 (source_id, source_port, target_id, target_port)")

    # --- UI Widgets ---
    source_node_select = param.Parameter()
    source_port_select = param.Parameter()
    target_node_select = param.Parameter()
    target_port_select = param.Parameter()
    add_edge_button = param.Parameter()
    _connection_list_container = param.Parameter(default=pn.Column(sizing_mode='stretch_width'))

    # --- State Parameters (Inputs/Outputs for Editor View) ---
    # 新增：存储上一个目标节点
    previous_target_node_id = param.String(default=None, allow_None=True, doc="上一个选中的目标节点 ID", precedence=-1)

    # Internal state for managing updates and previous selections
    _last_vm_selected_id = param.String(default=None, precedence=-1) # Track last ID received from VM
    _updating_target_internally = param.Boolean(default=False, precedence=-1) # Flag to prevent recursion

    def __init__(self, **params):
        super().__init__(**params)
        node_options = self.view_model.available_node_ids if self.view_model else []
        initial_vm_selection = self.view_model.selected_node_id if self.view_model else None
        self._last_vm_selected_id = initial_vm_selection # Initialize tracker

        # --- Initialize Widgets ---
        self.source_node_select = pn.widgets.Select(name="源节点", options=node_options, width=120)
        self.source_port_select = pn.widgets.Select(name="源端口", options=[], width=120, disabled=True)
        self.target_node_select = pn.widgets.Select(
            name="目标节点", 
            options=node_options, 
            value=initial_vm_selection, # Initialize with VM state
            width=120
        )
        self.target_port_select = pn.widgets.Select(name="目标端口", options=[], width=120, disabled=True)
        self.add_edge_button = pn.widgets.Button(name="🔗 添加连接", button_type="primary", width=100, disabled=True)
        
        # --- Bindings ---
        # ViewModel Updates -> UI Updates
        self.view_model.param.watch(self._update_node_selectors, 'available_node_ids')
        self.view_model.param.watch(self._update_connection_list_display, 'connection_list_data')
        self.view_model.param.watch(self._handle_vm_selection_change, 'selected_node_id') # NEW: Listen to VM selection
        
        # Internal UI Interactions
        self.source_node_select.param.watch(self._update_source_ports, 'value')
        self.target_node_select.param.watch(self._handle_manual_target_select, 'value') # User selects Target Node
        self.source_port_select.param.watch(self._update_add_button_state, 'value')
        self.target_port_select.param.watch(self._update_add_button_state, 'value')
        self.add_edge_button.on_click(self._request_add_edge)

        # --- Initial State Setup ---
        self._update_connection_list_display()
        # Set initial source/target based on VM state (if any)
        self._handle_target_node_change(initial_vm_selection, update_selector=False, is_initial_call=True)
        self._update_add_button_state()

    # =====================================================
    # == Event Handlers for Target Node Change (Linkage) ==
    # =====================================================

    def _handle_vm_selection_change(self, event: param.parameterized.Event):
        """Handles selected_node_id changes from the ViewModel."""
        new_target_id = event.new
        logger.debug(f"ConnectionPanel: Received ViewModel selected_node_id change: {new_target_id}")
        # Trigger the internal update logic
        self._handle_target_node_change(new_target_id, update_selector=True)
        # Update tracker
        self._last_vm_selected_id = new_target_id

    def _handle_manual_target_select(self, event: param.parameterized.Event):
        """Handles manual selection in the target_node_select widget."""
        if self._updating_target_internally:
            logger.debug("Manual target select handler skipped due to internal update flag.")
            return
        
        new_target_widget_value = event.new
        logger.debug(f"ConnectionPanel: Manual target node selection: {new_target_widget_value} (ViewModel has {self.view_model.selected_node_id})")
        
        # Only notify ViewModel if the manual selection differs from the VM state
        if new_target_widget_value != self.view_model.selected_node_id:
            logger.info(f"ConnectionPanel: Forwarding manual target selection '{new_target_widget_value}' to ViewModel.")
            # Directly call ViewModel command
            self.view_model.select_node(new_target_widget_value) 
            # ViewModel change will trigger _handle_vm_selection_change, which calls _handle_target_node_change
        else:
            # If user re-selected the same node already in VM state, 
            # still ensure ports are updated for this selection
            logger.debug("Manual selection matches ViewModel state. Ensuring ports are updated.")
            self._update_target_ports()
            self._update_add_button_state()

    def _handle_target_node_change(self, new_target_id: Optional[str], update_selector: bool = True, is_initial_call: bool = False):
        """Core logic: Updates previous node, sets source, updates selectors/ports."""
        logger.debug(f"Handling target node change. New ID: {new_target_id}, Update Selector: {update_selector}, Initial: {is_initial_call}")

        # 1. Record previous target ID
        # Use _last_vm_selected_id to track the *previous* VM state
        if not is_initial_call and new_target_id != self._last_vm_selected_id:
            old_target_for_previous = self._last_vm_selected_id
            logger.info(f"Setting previous_target_node_id to: {old_target_for_previous} (was VM selection before {new_target_id})")
            self.previous_target_node_id = old_target_for_previous
            # Update the tracker for the *next* change
            # This happens in _handle_vm_selection_change now

        # 2. Update Target Selector Widget (if needed and allowed)
        if update_selector and self.target_node_select.value != new_target_id:
            available_nodes = self.view_model.available_node_ids if self.view_model else []
            if new_target_id in available_nodes or new_target_id is None:
                logger.debug(f"Updating target selector widget to: {new_target_id}")
                self._updating_target_internally = True
                try:
                    self.target_node_select.value = new_target_id
                finally:
                    self._updating_target_internally = False
            else:
                logger.warning(f"Target node ID '{new_target_id}' not in available options, cannot update selector.")

        # 3. Update Source Node Selector based on the (now updated) previous_target_node_id
        self._update_source_based_on_previous(new_target_id)

        # 4. Update Port Selectors
        self._update_source_ports() # Source might have changed
        self._update_target_ports() # Target definitely changed or needs refresh
        
        # 5. Update Add Button State
        self._update_add_button_state()
        
    def _update_source_based_on_previous(self, current_target_id: Optional[str]):
        """Sets the source node selector based on previous_target_node_id."""
        potential_source_id = self.previous_target_node_id
        available_nodes = self.view_model.available_node_ids if self.view_model else []
        
        if potential_source_id and potential_source_id in available_nodes:
            if potential_source_id != current_target_id:
                if self.source_node_select.value != potential_source_id:
                    logger.info(f"Setting source selector widget to previous target: {potential_source_id}")
                    self.source_node_select.value = potential_source_id # Triggers source port update
            else:
                logger.debug("Not setting source node as it's the same as the current target.")
                # If previous was same as current, maybe clear source?
                # if self.source_node_select.value == potential_source_id:
                #     self.source_node_select.value = None
        else: # No valid previous target
            logger.debug("No valid previous target to set as source.")
            # Ensure source is not same as target
            if self.source_node_select.value == current_target_id:
                 self.source_node_select.value = None

    # ===========================================
    # == UI Update Methods (Driven by VM/Self) ==
    # ===========================================

    def _update_node_selectors(self, event: Optional[param.parameterized.Event] = None):
        """Updates node selector options based on ViewModel available_node_ids."""
        new_options = event.new if event else (self.view_model.available_node_ids if self.view_model else [])
        logger.debug(f"ConnectionPanel: Updating node selectors with options: {new_options}")
        
        current_source = self.source_node_select.value
        current_target_widget = self.target_node_select.value 

        source_changed = False
        target_changed = False

        if self.source_node_select.options != new_options:
            self.source_node_select.options = new_options
            source_changed = True
            if current_source not in new_options and current_source is not None:
                self.source_node_select.value = None # Clears selection
            # else: Keep existing valid selection
            
        if self.target_node_select.options != new_options:
            old_updating_flag = self._updating_target_internally
            self._updating_target_internally = True
            try:
                self.target_node_select.options = new_options
                target_changed = True
                # Ensure target selector reflects VM state after options change
                current_vm_selection = self.view_model.selected_node_id
                if current_vm_selection in new_options:
                    if self.target_node_select.value != current_vm_selection:
                        self.target_node_select.value = current_vm_selection
                elif self.target_node_select.value is not None: # VM selection is not valid, clear widget
                     self.target_node_select.value = None
            finally:
                 self._updating_target_internally = old_updating_flag
             
        # Update ports only if the corresponding selector might have changed value
        if source_changed: self._update_source_ports()
        if target_changed: self._update_target_ports()
             
        self._update_add_button_state()


    def _update_connection_list_display(self, event: Optional[param.parameterized.Event] = None):
        """当 ViewModel 的 connection_list_data 变化时，重新构建连接列表 UI。"""
        connection_data = self.view_model.connection_list_data if self.view_model else []
        logger.debug(f"ConnectionManagementPanel: Rebuilding connection list display with data: {connection_data}")
        connection_rows = []
        if not connection_data:
            connection_rows.append(pn.pane.Markdown("_当前没有连接。_"))
        else:
            for edge_data in connection_data:
                if len(edge_data) == 4:
                    u, v, source_port, target_port = edge_data
                    remove_button = pn.widgets.Button(name="🗑️", button_type="danger", width=40, height=30, margin=(0,0,0,5))
                    remove_button.on_click(lambda event, ed=(u, source_port, v, target_port): self._request_remove_edge(ed))
                    edge_label = f"`{u}.{source_port}` → `{v}.{target_port}`"
                    connection_rows.append(pn.Row(pn.pane.Markdown(edge_label, margin=(0, 5)), remove_button))
                else:
                    logger.warning(f"ConnectionManagementPanel: Invalid edge data format found: {edge_data}")
        self._connection_list_container.objects = connection_rows

    def _update_source_ports(self, event=None):
        """更新源端口下拉列表。"""
        node_id = self.source_node_select.value
        ports = self._get_ports(node_id, is_source=True)
        current_val = self.source_port_select.value
        changed = False
        if self.source_port_select.options != ports:
             self.source_port_select.options = ports
             if current_val not in [p[1] for p in ports]:
                 self.source_port_select.value = None
                 changed = True
             self.source_port_select.disabled = not bool(ports)
             changed = True # Options changed
        elif not node_id and not self.source_port_select.disabled:
            self.source_port_select.disabled = True
            changed = True
        elif node_id and self.source_port_select.disabled:
             self.source_port_select.disabled = not bool(ports)
             changed = True
            
        if changed: self._update_add_button_state()

    def _update_target_ports(self, event=None):
        """更新目标端口下拉列表。"""
        node_id = self.target_node_select.value 
        ports = self._get_ports(node_id, is_source=False)
        current_val = self.target_port_select.value
        changed = False
        if self.target_port_select.options != ports:
             self.target_port_select.options = ports
             if current_val not in [p[1] for p in ports]:
                 self.target_port_select.value = None
                 changed = True
             self.target_port_select.disabled = not bool(ports)
             changed = True
        elif not node_id and not self.target_port_select.disabled:
             self.target_port_select.disabled = True
             changed = True
        elif node_id and self.target_port_select.disabled:
             self.target_port_select.disabled = not bool(ports)
             changed = True

        if changed: self._update_add_button_state()

    def _get_ports(self, node_id: Optional[str], is_source: bool) -> List[Tuple[str, str]]:
        """Helper to get input or output ports for a given node ID."""
        port_options = []
        if node_id and self.view_model and self.view_model.model and node_id in self.view_model.model.nodes:
            node_instance = None # Initialize for logging in except block
            try:
                node_instance = self.view_model.model.get_node(node_id)
                ports_dict = node_instance.define_outputs() if is_source else node_instance.define_inputs()

                for name, spec in ports_dict.items():
                    data_type_str = 'unknown' # Default
                    # Check if spec has data_type attribute (like PortSpec)
                    if hasattr(spec, 'data_type'):
                        data_type_val = getattr(spec, 'data_type', 'unknown')
                        # If the attribute itself is a type, get its name
                        if isinstance(data_type_val, type):
                            data_type_str = data_type_val.__name__
                        else: # Otherwise, convert the attribute value to string
                            data_type_str = str(data_type_val)
                    # Check if spec *is* a type object (like DataFrame)
                    elif isinstance(spec, type):
                        data_type_str = spec.__name__
                    # Fallback if spec is neither a type nor has data_type
                    else:
                        data_type_str = str(spec)

                    port_options.append((f"{name} ({data_type_str})", name))

            except Exception as e:
                # Use node_instance if available, otherwise just node_id
                node_type = getattr(node_instance, 'node_type', 'unknown') if node_instance else 'unknown'
                logger.warning(
                    f"Failed to get {'output' if is_source else 'input'} ports for node {node_id} (type {node_type}): {e}",
                    exc_info=True
                )
        return port_options
        
    def _update_add_button_state(self, event=None):
        """更新添加按钮的启用状态。"""
        can_add = bool(
            self.source_node_select.value and
            self.source_port_select.value and
            self.target_node_select.value and
            self.target_port_select.value and
            self.source_node_select.value != self.target_node_select.value # Prevent self-loops via UI
        )
        self.add_edge_button.disabled = not can_add

    # =====================================================
    # == Action Request Methods (Triggering ViewModel) ==
    # =====================================================

    def _request_add_edge(self, event):
        """处理添加连接按钮点击事件，发出添加请求。"""
        source_node = self.source_node_select.value
        source_port = self.source_port_select.value
        target_node = self.target_node_select.value
        target_port = self.target_port_select.value

        # Validation already handled by button state, but double-check
        if not all([source_node, source_port, target_node, target_port]):
            logger.warning("Add edge requested but not all fields are selected.")
            if pn.state.notifications: pn.state.notifications.error("内部错误：添加按钮状态不一致。", duration=3000)
            return
        if source_node == target_node:
            logger.warning("Add edge requested for self-loop.")
            if pn.state.notifications: pn.state.notifications.warning("不允许创建自环连接。", duration=3000)
            return

        logger.info(f"ConnectionManagementPanel: Requesting to add edge: {source_node}.{source_port} -> {target_node}.{target_port}")
        # Set the output parameter to signal the request
        self.request_add_edge_data = (source_node, source_port, target_node, target_port)
        # Optionally reset fields after request? Or let ViewModel handle it?
        # self.source_port_select.value = None
        # self.target_port_select.value = None

    def _request_remove_edge(self, edge_data: Tuple[str, str, str, str]):
        """处理删除连接按钮点击事件，发出删除请求。"""
        if not isinstance(edge_data, tuple) or len(edge_data) != 4:
             logger.error(f"Invalid edge data received for removal: {edge_data}")
             return
        u, source_port, v, target_port = edge_data # Correct order? ViewModel uses (u,v,src_port,tgt_port)? Check VM.
        # Assuming VM uses (src_id, src_port, tgt_id, tgt_port)
        logger.info(f"ConnectionManagementPanel: Requesting to remove edge: {u}.{source_port} -> {v}.{target_port}")
        # Set the output parameter
        self.request_remove_edge_data = edge_data # Pass the exact data received

    # ==================
    # == Panel Layout ==
    # ==================

    def _build_panel(self) -> pn.Column:
        """构建面板 UI。"""
        edge_form = pn.Row(
            self.source_node_select, self.source_port_select, pn.pane.HTML("&nbsp;→&nbsp;", styles={'line-height':'2'}),
            self.target_node_select, self.target_port_select, self.add_edge_button,
            styles={'align-items': 'end'} # Align items vertically at the bottom
        )
        return pn.Column(
            pn.pane.Markdown("#### 连接管理"),
            edge_form,
            pn.layout.Divider(),
            pn.pane.Markdown("**现有连接:**"),
            self._connection_list_container, # Container for dynamic rows
            sizing_mode='stretch_width'
        )

    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 布局。"""
        # Rebuild panel content if needed (or rely on param.depends if _panel_content were used)
        # For simplicity now, just return the built content from init
        # If dynamic layout changes were needed, we'd use @param.depends on relevant params
        return self._build_panel() # Return the layout built in init 