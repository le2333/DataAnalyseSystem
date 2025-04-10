import param
import panel as pn
from model.data_manager import DataManager
from view.data_manager_view import DataManagerView

class DataManagerController(param.Parameterized):
    """处理 DataManagerView 交互的控制器。"""

    # 依赖注入
    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)

    def __init__(self, data_manager: DataManager, **params):
        view_instance = DataManagerView(data_manager=data_manager)
        super().__init__(data_manager=data_manager, view=view_instance, **params)
        self._bind_events()

    def _bind_events(self):
        self.view.rename_button.on_click(self._handle_rename)
        self.view.delete_button.on_click(self._handle_delete)

    def _handle_rename(self, event):
        data_id = self.view.selected_data_id
        new_name = self.view.rename_input.value.strip()
        if not data_id:
            pn.state.notifications.warning("请先选择要重命名的数据项。")
            return
        if not new_name:
            pn.state.notifications.warning("请输入新的名称。")
            return
        
        success = self.data_manager.update_name(data_id, new_name)
        if success:
            pn.state.notifications.success(f"数据项 '{data_id[:8]}...' 已重命名为 '{new_name}'")
            # 表格会在 DataManager 更新时自动刷新
        else:
            pn.state.notifications.error(f"重命名失败。可能是名称 '{new_name}' 已被使用或数据项不存在。")

    def _handle_delete(self, event):
        data_id = self.view.selected_data_id
        if not data_id:
            pn.state.notifications.warning("请先选择要删除的数据项。")
            return

        # 获取名称用于确认信息
        data_obj = self.data_manager.get_data(data_id)
        if not data_obj:
             pn.state.notifications.error("无法找到要删除的数据项。")
             return
        data_name = data_obj.name
        
        # 这里可以添加确认对话框
        # Example: confirmation = await pn.state.modal.confirm("确认删除?", f"确定要删除数据项 \'{data_name}\' 吗?")
        # if not confirmation:
        #     return
            
        success = self.data_manager.remove_data(data_id)
        if success:
            pn.state.notifications.success(f"数据项 '{data_name}' ({data_id[:8]}...) 已删除。")
            # 表格会自动刷新
        else:
            pn.state.notifications.error(f"删除数据项 '{data_name}' 失败。")
        # else:
        #     pn.state.notifications.info(f"请确认删除 '{data_name}'", duration=5000)
        #     # 这里可以添加一个按钮或链接来触发带确认参数的删除

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 