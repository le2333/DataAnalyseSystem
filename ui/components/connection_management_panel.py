import panel as pn
import param
import logging
from typing import List, Tuple, Any, Optional, Dict, Type

from core.node import NodeRegistry # 仍然需要 Registry 获取端口
from viewmodels import WorkflowViewModel # 导入 ViewModel
from .base_panel import BasePanelComponent # 导入基类

logger = logging.getLogger(__name__)

class ConnectionManagementPanel(BasePanelComponent):
    """
    封装连接管理功能的 Panel 组件。
    设计原则：监听 ViewModel 的状态变化更新 UI，用户交互触发 ViewModel 更新。
    目标节点选择由 ViewModel 的 selected_node_id 驱动。
    源节点选择根据目标节点的变化自动设置为上一个目标节点。
    """
    # --- 输入参数 --- (view_model 从基类继承)
    # view_model = param.ClassSelector(class_=WorkflowViewModel, doc="关联的 WorkflowViewModel")

    # --- 输出参数 / 事件 ---
    # request_add_edge_data = param.Parameter(default=None, doc="请求添加边 (source_id, source_port, target_id, target_port)")
    # request_remove_edge_data = param.Parameter(default=None, doc="请求删除边 (source_id, source_port, target_id, target_port)")

    # --- UI 控件 ---
    source_node_select = param.Parameter()
    source_port_select = param.Parameter()
    target_node_select = param.Parameter()
    target_port_select = param.Parameter()
    add_edge_button = param.Parameter()
    _connection_list_container = param.Parameter(default=pn.Column(sizing_mode='stretch_width'))

    # --- 状态参数 (编辑器视图的输入/输出) ---
    # 新增：存储上一个目标节点
    previous_target_node_id = param.String(default=None, allow_None=True, doc="上一个选中的目标节点 ID", precedence=-1)

    # 用于管理更新和先前选择的内部状态
    _last_vm_selected_id = param.String(default=None, precedence=-1) # 跟踪从 ViewModel 收到的最后一个 ID
    _updating_target_internally = param.Boolean(default=False, precedence=-1) # 防止递归的标志

    def __init__(self, view_model: WorkflowViewModel, **params):
        # 将 view_model 传递给基类
        params['view_model'] = view_model
        super().__init__(**params) # 调用基类 __init__
        # --- 初始化 ViewModel 依赖的状态 --- 
        node_options = self.view_model.available_node_ids if self.view_model else []
        initial_vm_selection = self.view_model.selected_node_id if self.view_model else None
        self._last_vm_selected_id = initial_vm_selection # 初始化跟踪器

        # --- 初始化控件 ---
        self.source_node_select = pn.widgets.Select(name="源节点", options=node_options, width=120)
        self.source_port_select = pn.widgets.Select(name="源端口", options=[], width=120, disabled=True)
        self.target_node_select = pn.widgets.Select(
            name="目标节点", 
            options=node_options, 
            value=initial_vm_selection, # 使用 ViewModel 状态进行初始化
            width=120
        )
        self.target_port_select = pn.widgets.Select(name="目标端口", options=[], width=120, disabled=True)
        self.add_edge_button = pn.widgets.Button(name="🔗 添加连接", button_type="primary", width=100, disabled=True)
        
        # --- 绑定 ---
        # ViewModel 更新 -> UI 更新
        self.view_model.param.watch(self._update_node_selectors, 'available_node_ids')
        self.view_model.param.watch(self._update_connection_list_display, 'connection_list_data')
        self.view_model.param.watch(self._handle_vm_selection_change, 'selected_node_id') # 新增：监听 ViewModel 的选择
        
        # 内部 UI 交互
        self.source_node_select.param.watch(self._update_source_ports, 'value')
        self.target_node_select.param.watch(self._handle_manual_target_select, 'value') # 用户选择目标节点
        self.source_port_select.param.watch(self._update_add_button_state, 'value')
        self.target_port_select.param.watch(self._update_add_button_state, 'value')
        self.add_edge_button.on_click(self._request_add_edge)

        # --- 初始状态设置 ---
        self._update_connection_list_display()
        # 根据 ViewModel 状态（如果存在）设置初始源/目标
        self._handle_target_node_change(initial_vm_selection, update_selector=False, is_initial_call=True)
        self._update_add_button_state()

    # =====================================================
    # == 目标节点更改事件处理程序 (联动) ==
    # =====================================================

    def _handle_vm_selection_change(self, event: param.parameterized.Event):
        """处理来自 ViewModel 的 selected_node_id 更改。"""
        new_target_id = event.new
        logger.debug(f"ConnectionPanel: 收到 ViewModel selected_node_id 更改: {new_target_id}")
        # 触发内部更新逻辑
        self._handle_target_node_change(new_target_id, update_selector=True)
        # 更新跟踪器
        self._last_vm_selected_id = new_target_id

    def _handle_manual_target_select(self, event: param.parameterized.Event):
        """处理 target_node_select 控件中的手动选择。"""
        if self._updating_target_internally:
            logger.debug("由于内部更新标志，手动目标选择处理程序被跳过。")
            return
        
        new_target_widget_value = event.new
        logger.debug(f"ConnectionPanel: 手动目标节点选择: {new_target_widget_value} (ViewModel 有 {self.view_model.selected_node_id})")
        
        # 仅当手动选择与 ViewModel 状态不同时通知 ViewModel
        if new_target_widget_value != self.view_model.selected_node_id:
            logger.info(f"ConnectionPanel: 将手动目标选择 '{new_target_widget_value}' 转发给 ViewModel。")
            # 直接调用 ViewModel 命令
            self.view_model.select_node(new_target_widget_value) 
            # ViewModel 的更改将触发 _handle_vm_selection_change，后者会调用 _handle_target_node_change
        else:
            # 如果用户重新选择了已处于 ViewModel 状态的相同节点，
            # 仍然确保更新此选择的端口
            logger.debug("手动选择与 ViewModel 状态匹配。确保更新端口。")
            self._update_target_ports()
            self._update_add_button_state()

    def _handle_target_node_change(self, new_target_id: Optional[str], update_selector: bool = True, is_initial_call: bool = False):
        """核心逻辑：更新上一个节点，设置源节点，更新选择器/端口。"""
        logger.debug(f"处理目标节点更改。新 ID: {new_target_id}，更新选择器: {update_selector}，初始调用: {is_initial_call}")

        # 1. 记录上一个目标 ID
        # 使用 _last_vm_selected_id 跟踪 *上一个* ViewModel 状态
        if not is_initial_call and new_target_id != self._last_vm_selected_id:
            old_target_for_previous = self._last_vm_selected_id
            logger.info(f"将 previous_target_node_id 设置为: {old_target_for_previous} (在 {new_target_id} 之前的 ViewModel 选择)")
            self.previous_target_node_id = old_target_for_previous
            # 为 *下一个* 更改更新跟踪器
            # 这现在在 _handle_vm_selection_change 中发生

        # 2. 更新目标选择器控件（如果需要且允许）
        if update_selector and self.target_node_select.value != new_target_id:
            available_nodes = self.view_model.available_node_ids if self.view_model else []
            if new_target_id in available_nodes or new_target_id is None:
                logger.debug(f"将目标选择器控件更新为: {new_target_id}")
                self._updating_target_internally = True
                try:
                    self.target_node_select.value = new_target_id
                finally:
                    self._updating_target_internally = False
            else:
                logger.warning(f"目标节点 ID '{new_target_id}' 不在可用选项中，无法更新选择器。")

        # 3. 根据（现在更新的）previous_target_node_id 更新源节点选择器
        self._update_source_based_on_previous(new_target_id)

        # 4. 更新端口选择器
        self._update_source_ports() # 源节点可能已更改
        self._update_target_ports() # 目标节点肯定已更改或需要刷新
        
        # 5. 更新添加按钮状态
        self._update_add_button_state()
        
    def _update_source_based_on_previous(self, current_target_id: Optional[str]):
        """根据 previous_target_node_id 设置源节点选择器。"""
        potential_source_id = self.previous_target_node_id
        available_nodes = self.view_model.available_node_ids if self.view_model else []
        
        if potential_source_id and potential_source_id in available_nodes:
            if potential_source_id != current_target_id:
                if self.source_node_select.value != potential_source_id:
                    logger.info(f"将源选择器控件设置为上一个目标: {potential_source_id}")
                    self.source_node_select.value = potential_source_id # 触发源端口更新
            else:
                logger.debug("不设置源节点，因为它与当前目标节点相同。")
        else: # 没有有效的上一个目标
            logger.debug("没有有效的上一个目标可以设置为源节点。")
            # 确保源节点与目标节点不同
            if self.source_node_select.value == current_target_id:
                 self.source_node_select.value = None

    # ===========================================
    # == UI 更新方法 (由 VM/自身驱动) ==
    # ===========================================

    def _update_node_selectors(self, event: Optional[param.parameterized.Event] = None):
        """根据 ViewModel 的 available_node_ids 更新节点选择器选项。"""
        new_options = event.new if event else (self.view_model.available_node_ids if self.view_model else [])
        logger.debug(f"ConnectionPanel: 使用选项更新节点选择器: {new_options}")
        
        current_source = self.source_node_select.value

        source_changed = False
        target_changed = False

        if self.source_node_select.options != new_options:
            self.source_node_select.options = new_options
            source_changed = True
            if current_source not in new_options and current_source is not None:
                self.source_node_select.value = None # 清除选择
            # else: 保留现有的有效选择
            
        if self.target_node_select.options != new_options:
            old_updating_flag = self._updating_target_internally
            self._updating_target_internally = True
            try:
                self.target_node_select.options = new_options
                target_changed = True
                # 确保选项更改后目标选择器反映 ViewModel 状态
                current_vm_selection = self.view_model.selected_node_id
                if current_vm_selection in new_options:
                    if self.target_node_select.value != current_vm_selection:
                        self.target_node_select.value = current_vm_selection
                elif self.target_node_select.value is not None: # ViewModel 选择无效，清除控件
                     self.target_node_select.value = None
            finally:
                 self._updating_target_internally = old_updating_flag
             
        # 仅当相应的选择器值可能已更改时才更新端口
        if source_changed: self._update_source_ports()
        if target_changed: self._update_target_ports()
             
        self._update_add_button_state()


    def _update_connection_list_display(self, event: Optional[param.parameterized.Event] = None):
        """当 ViewModel 的 connection_list_data 变化时，重新构建连接列表 UI。"""
        connection_data = self.view_model.connection_list_data if self.view_model else []
        logger.debug(f"ConnectionManagementPanel: 使用数据重建连接列表显示: {connection_data}")
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
                    logger.warning(f"ConnectionManagementPanel: 发现无效的边数据格式: {edge_data}")
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
             changed = True # 选项已更改
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
        """根据节点 ID 和方向（源或目标）获取端口列表。"""
        if not node_id:
            return []
        try:
            # 使用 view_model.get_node_info 获取节点信息
            node_info = self.view_model.get_node_info(node_id)
            if not node_info:
                return [] # 如果找不到节点信息，返回空列表

            if is_source:
                # 从 node_info 获取输出端口定义 (Dict[str, Type])
                port_definitions: Dict[str, Type] = node_info.get('outputs', {})
                    else:
                # 从 node_info 获取输入端口定义 (Dict[str, Type])
                port_definitions: Dict[str, Type] = node_info.get('inputs', {})

            # 正确处理 Dict[str, Type]，将其转换为 List[Tuple[str, str]]
            # 将 Type 对象转换为其名称字符串
            ports = [(f"{name} ({typ.__name__})", name) for name, typ in port_definitions.items()]
            return ports # 返回计算得到的 ports

            except Exception as e:
            # 保持原始的错误日志记录
            logger.error(f"获取节点 {node_id} 的端口时出错: {e}", exc_info=True) # 添加 exc_info=True 获取更详细的回溯
            return [] # 出错时返回空列表
        
    def _update_add_button_state(self, event=None):
        """根据端口选择启用/禁用"添加连接"按钮。"""
        source_selected = bool(self.source_node_select.value and self.source_port_select.value)
        target_selected = bool(self.target_node_select.value and self.target_port_select.value)
        is_same_node = self.source_node_select.value == self.target_node_select.value
        
        self.add_edge_button.disabled = not (source_selected and target_selected and not is_same_node)
        if is_same_node and source_selected and target_selected:
             logger.debug("禁用添加按钮：源节点和目标节点不能相同。")
        elif not (source_selected and target_selected):
             logger.debug(f"禁用添加按钮：源选择: {source_selected}, 目标选择: {target_selected}")
        else:
             logger.debug("启用添加按钮")

    def _request_add_edge(self, event):
        """处理"添加连接"按钮点击事件，发出添加边的请求。"""
        source_id = self.source_node_select.value
        raw_source_port = self.source_port_select.value
        target_id = self.target_node_select.value
        raw_target_port = self.target_port_select.value

        # --- Safeguard for potential tuple value from Select --- 
        source_port = raw_source_port[1] if isinstance(raw_source_port, tuple) and len(raw_source_port) == 2 else raw_source_port
        target_port = raw_target_port[1] if isinstance(raw_target_port, tuple) and len(raw_target_port) == 2 else raw_target_port
        # -----------------------------------------------------

        # 添加调试日志 (保留之前的日志)
        logger.debug(f"ConnectionPanel: Raw source port select value: {raw_source_port!r}, type: {type(raw_source_port)}")
        logger.debug(f"ConnectionPanel: Raw target port select value: {raw_target_port!r}, type: {type(raw_target_port)}")
        logger.debug(f"ConnectionPanel: Processed source_port: {source_port!r}")
        logger.debug(f"ConnectionPanel: Processed target_port: {target_port!r}")

        if not all([source_id, source_port, target_id, target_port]):
            logger.warning("请求添加边，但并非所有字段都已填写。")
            if pn.state.notifications: pn.state.notifications.warning("请选择源和目标节点及端口。", duration=3000)
            return
            
        if source_id == target_id:
            logger.warning("无法添加连接：源节点和目标节点不能相同。")
            if pn.state.notifications: pn.state.notifications.error("源节点和目标节点不能相同。", duration=3000)
            return

        # edge_data 不再需要，直接传递参数
        # edge_data = (source_id, source_port, target_id, target_port)
        logger.info(f"ConnectionManagementPanel: 请求添加边: {source_id}.{source_port} -> {target_id}.{target_port}")
        
        # 直接调用 ViewModel 的方法，传递解包后的参数
        try:
            self.view_model.add_edge(source_id, source_port, target_id, target_port)
            # 清除端口选择以防意外重复添加？或者留给用户？
            # self.source_port_select.value = None
            # self.target_port_select.value = None
        except Exception as e:
            logger.error(f"调用 view_model.add_edge 时出错: {e}", exc_info=True)
            if pn.state.notifications: pn.state.notifications.error(f"添加连接失败: {e}")


    def _request_remove_edge(self, edge_data: Tuple[str, str, str, str]):
        """处理删除特定连接的请求。"""
        # edge_data is (u, source_port, v, target_port) from the lambda
        u, source_port, v, target_port = edge_data
        logger.info(f"ConnectionManagementPanel: 请求删除边: {u}.{source_port} -> {v}.{target_port}")
        # 直接调用 ViewModel 的方法，确保参数顺序正确
        try:
            # ViewModel.delete_edge 期望 (source_id, target_id, source_port, target_port)
            # Model.remove_edge 期望 (source_id, source_port, target_id, target_port)
            # 因此，传递给 ViewModel 的应该是 (u, v, source_port, target_port) ? 不对，ViewModel 应该遵循 Model
            # ViewModel delete_edge(source_id, target_id, source_port, target_port)
            # Model remove_edge(source_node_id, source_port, target_node_id, target_port)
            # 确认 ViewModel 的 delete_edge 定义... 它直接调用 model.remove_edge
            # 所以 ViewModel delete_edge 实际需要 (src_id, src_port, tgt_id, tgt_port)
            self.view_model.delete_edge(u, source_port, v, target_port)
        except Exception as e:
            logger.error(f"调用 view_model.delete_edge 时出错: {e}", exc_info=True)
            if pn.state.notifications: pn.state.notifications.error(f"删除连接失败: {e}")


    def _build_panel(self) -> pn.Column:
        """构建此组件的 Panel 布局。"""
        # 构建面板内容
        connection_configurator = pn.Row(
            pn.Column(self.source_node_select, self.source_port_select),
            pn.Column(self.target_node_select, self.target_port_select),
            pn.Column(pn.layout.Spacer(height=20), self.add_edge_button), # 添加间隔使按钮对齐
            sizing_mode='stretch_width'
        )
        
        return pn.Column(
            pn.pane.Markdown("#### 连接管理"),
            connection_configurator,
            pn.pane.Markdown("##### 当前连接"),
            self._connection_list_container, # 显示连接列表的容器
            sizing_mode='stretch_width'
        )

    # 实现抽象方法
    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 布局。"""
        # 直接调用 _build_panel 来获取内容
        return self._build_panel() 