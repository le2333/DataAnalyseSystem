import panel as pn
import param
import logging
from typing import List, Optional

from viewmodels import WorkflowViewModel # 导入 ViewModel
from .base_panel import BasePanelComponent # 导入基类

logger = logging.getLogger(__name__)

class NodeManagementPanel(BasePanelComponent):
    """
    封装节点管理功能的 Panel 组件。
    显示节点列表，允许选择和请求删除。
    设计原则：本组件响应 ViewModel 的状态变化更新 UI，
    并将用户操作 (如选择、删除请求) 转发给 ViewModel (通过 EditorView 或直接)。
    现在监听 ViewModel 的 selected_node_id。
    """
    # --- 输入参数 --- (从基类继承 view_model)
    # view_model = param.ClassSelector(class_=WorkflowViewModel, doc="关联的 WorkflowViewModel")

    # --- 输出参数 / 事件 --- (不变)
    # REMOVED: selected_node_id is now managed by ViewModel
    # selected_node_id = param.String(default=None, doc="当前选中的节点ID")
    # 请求删除节点 (携带节点ID)
    # request_delete_node_id = param.String(default=None, doc="请求删除指定ID的节点")

    # --- UI 控件 --- (不变)
    _node_selector = param.Parameter() # 使用 Select Widget
    _delete_node_button = param.Parameter()
    # _panel_content 不再需要，panel() 方法直接构建

    # Internal flag to prevent loops when updating selector from ViewModel
    _updating_selector_internally = param.Boolean(default=False, precedence=-1)

    def __init__(self, view_model: WorkflowViewModel, **params):
        # 将 view_model 传递给基类
        params['view_model'] = view_model
        super().__init__(**params) # 调用基类 __init__
        # --- 初始化 ViewModel 依赖的状态 --- 
        node_options = self.view_model.available_node_ids if self.view_model else []
        initial_selection = self.view_model.selected_node_id if self.view_model else None
        
        # --- 初始化控件 ---
        self._node_selector = pn.widgets.Select(
            name="选择节点", 
            options=node_options, 
            value=initial_selection, # Set initial value from VM
            sizing_mode='stretch_width'
        )
        self._delete_node_button = pn.widgets.Button(
            name="🗑️ 删除选中节点", 
            button_type="danger", 
            sizing_mode='stretch_width', 
            disabled=(initial_selection is None) # Disable if nothing selected initially
        )

        # --- 绑定 --- (不变)
        # ViewModel available nodes change -> Update selector options
        self.view_model.param.watch(self._update_selector_options, 'available_node_ids')
        # ViewModel selected node changes -> Update selector value (UI)
        self.view_model.param.watch(self._update_selector_value, 'selected_node_id')
        # User selects in UI -> Notify ViewModel (forward selection)
        self._node_selector.param.watch(self._forward_selection_change, 'value')
        # Delete button clicked -> Set request parameter
        self._delete_node_button.on_click(self._request_delete_node)
        # ViewModel selected node changes -> Update delete button state
        self.view_model.param.watch(self._update_delete_button_state, 'selected_node_id')

    def _update_selector_options(self, event: param.parameterized.Event):
        """当 ViewModel 的 available_node_ids 变化时，更新选择器的选项。"""
        new_options = event.new
        logger.debug(f"NodeManagementPanel: Received new node options: {new_options}")
        if self._node_selector.options != new_options:
            logger.debug("NodeManagementPanel: Updating selector options.")
            current_vm_selection = self.view_model.selected_node_id
            # Temporarily disable internal update flag check for option change
            # as value might need reset if current selection removed
            old_updating_flag = self._updating_selector_internally
            self._updating_selector_internally = True 
            try:
                self._node_selector.options = new_options
                # Ensure selector value matches ViewModel state after options update
                if current_vm_selection in new_options:
                    if self._node_selector.value != current_vm_selection:
                         self._node_selector.value = current_vm_selection
                elif self._node_selector.value is not None:
                     self._node_selector.value = None # Clear selector if VM selection invalid
            finally:
                 self._updating_selector_internally = old_updating_flag

    def _update_selector_value(self, event: param.parameterized.Event):
        """当 ViewModel 的 selected_node_id 变化时，更新选择器的值。"""
        new_selection = event.new
        logger.info(f"NodeManagementPanel._update_selector_value: Received new selection from VM: '{new_selection}'") # Log entry
        logger.debug(f"    Current selector value: '{self._node_selector.value}'")
        logger.debug(f"    Selector options: {self._node_selector.options}")
        # Update selector only if its value differs from the new VM state
        if self._node_selector.value != new_selection:
            logger.info("    -> Selector value differs. Attempting update.")
            # Prevent the change handler from re-notifying the ViewModel
            logger.debug("       Setting _updating_selector_internally = True")
            self._updating_selector_internally = True 
            try:
                # Check if the new selection is valid in current options
                if new_selection in self._node_selector.options or new_selection is None:
                    logger.info(f"       Setting selector value to: '{new_selection}'")
                    self._node_selector.value = new_selection
                else:
                     logger.warning(f"       ViewModel selected ID '{new_selection}' not in selector options. Cannot update UI.")
            finally:
                logger.debug("       Setting _updating_selector_internally = False")
                self._updating_selector_internally = False
        else:
            logger.info("    -> Selector value matches VM state. No UI update needed.")

    def _forward_selection_change(self, event):
        """当用户在选择器中选择时，通知 ViewModel。"""
        # Prevent loop if the change was triggered internally by _update_selector_value
        if self._updating_selector_internally:
            logger.debug("NodeManagementPanel: Selector value change ignored (internal update).")
            return
        
        new_selection = event.new
        logger.debug(f"NodeManagementPanel: User selected '{new_selection}' in UI. Forwarding to ViewModel.")
        # Directly call ViewModel's method (or rely on EditorView to forward)
        # For consistency with EditorView handling other forwards, we assume EditorView listens
        # to this panel's selected_node_id (which we now remove).
        # ---> NEW APPROACH: Rely on EditorView listener for now <--- 
        # ---> Let EditorView call self.view_model.select_node(new_selection) <--- 
        # ---> Reintroduce selected_node_id output param? No, let's assume direct call or EditorView handles <--- 
        # Let's stick to the plan: EditorView ALREADY listens to this panel's selection changes.
        # BUT we removed selected_node_id output. The listener in EditorView was:
        # self.node_management_panel.param.watch(self._forward_node_selection, 'selected_node_id')
        # This won't work anymore.
        
        # === REVISED PLAN ===
        # This panel SHOULD directly notify the ViewModel.
        # Remove the need for EditorView to forward this specific event.
        if self.view_model.selected_node_id != new_selection:
             self.view_model.select_node(new_selection)

    def _update_delete_button_state(self, event=None):
        """根据 ViewModel 的 selected_node_id 启用/禁用删除按钮。"""
        is_selected = bool(self.view_model.selected_node_id)
        logger.debug(f"NodeManagementPanel: Updating delete button enabled state to: {is_selected}")
        self._delete_node_button.disabled = not is_selected

    def _request_delete_node(self, event):
        """处理删除按钮点击事件，发出删除请求。"""
        node_id_to_remove = self.view_model.selected_node_id # Get ID from ViewModel
        if not node_id_to_remove:
            logger.warning("NodeManagementPanel: Delete requested but no node selected in ViewModel.")
            if pn.state.notifications: pn.state.notifications.warning("请先选择要删除的节点。", duration=3000)
            return

        logger.info(f"NodeManagementPanel: Requesting deletion of node: {node_id_to_remove}")
        # Set the output parameter for EditorView to pick up
        # self.request_delete_node_id = node_id_to_remove
        # Call ViewModel directly
        try:
            self.view_model.delete_node(node_id_to_remove)
        except Exception as e:
             logger.error(f"NodeManagementPanel: Error calling view_model.delete_node: {e}", exc_info=True)
             if pn.state.notifications: pn.state.notifications.error(f"删除节点 '{node_id_to_remove}' 失败: {e}")
        # Reset the request immediately (or let EditorView do it? Let EditorView do it for consistency)

    # 实现抽象方法
    def panel(self) -> pn.viewable.Viewable:
        """返回此组件的 Panel 布局。"""
        # Build the panel dynamically or return pre-built content
        return pn.Column(
            pn.pane.Markdown("#### 节点管理"),
            self._node_selector,
            self._delete_node_button,
            sizing_mode='stretch_width'
        ) 