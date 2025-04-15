import param
import panel as pn
from model.data_manager import DataManager
from view.data_manager_view import DataManagerView

class DataManagerController(param.Parameterized):
    """处理 DataManagerView 交互的控制器。"""

    # 依赖注入
    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)
    app_controller = param.Parameter(precedence=-1)

    def __init__(self, data_manager: DataManager, **params):
        view_instance = DataManagerView(data_manager=data_manager)
        super().__init__(data_manager=data_manager, view=view_instance, **params)
        if self.app_controller is None and 'app_controller' in params:
            self.app_controller = params['app_controller']
        elif self.app_controller is None:
            print("警告: DataManagerController 未接收到 AppController 实例!")
        self._bind_events()

    def _bind_events(self):
        """监听视图触发的操作事件。"""
        # 移除旧的 on_click 绑定
        # self.view.rename_button.on_click(self._handle_rename)
        # self.view.delete_button.on_click(self._handle_delete)

        # 添加对新事件的监听 (使用 param.watch)
        self.view.param.watch(self._navigate_explore_1d, 'explore_1d_request')
        self.view.param.watch(self._navigate_explore_multidim, 'explore_multidim_request')
        self.view.param.watch(self._navigate_process, 'process_request')
        self.view.param.watch(self._navigate_compare, 'compare_request')
        # 将删除逻辑绑定到 remove_request 事件
        self.view.param.watch(self._handle_remove, 'remove_request')

    # _handle_rename 不再需要，因为视图中没有重命名按钮了
    # def _handle_rename(self, event): ...

    # 重命名 _handle_delete 为 _handle_remove 以匹配事件
    def _handle_remove(self, event):
        """处理删除请求 (由 remove_request 事件触发)。"""
        # event.new 在事件触发时为 True
        if not event.new or not self.view.selected_data_ids:
            # 可以选择不显示通知，因为按钮应该被禁用
            # pn.state.notifications.warning("没有选择要删除的数据项。")
            return

        removed_count = 0
        errors = []
        # 复制列表，因为 data_manager.remove_data 会触发视图更新，可能改变 selection
        ids_to_remove = list(self.view.selected_data_ids)

        # 确认逻辑 (可选)
        # names_to_remove = [self.data_manager.get_data(id).name for id in ids_to_remove if self.data_manager.get_data(id)]
        # confirmation = await pn.state.modal.confirm("确认删除?", f"确定要删除 {len(names_to_remove)} 个数据项吗?\n - " + "\n - ".join(names_to_remove))
        # if not confirmation:
        #     return

        for data_id in ids_to_remove:
            data_obj = self.data_manager.get_data(data_id)
            name = data_obj.name if data_obj else f"ID {data_id[:8]}..."
            if self.data_manager.remove_data(data_id):
                removed_count += 1
            else:
                errors.append(name)

        if removed_count > 0:
             pn.state.notifications.success(f"成功删除了 {removed_count} 个数据项。")
        if errors:
             pn.state.notifications.error(f"无法删除以下数据项: {', '.join(errors)}。")
        # 表格会因 _data_updated 自动更新，按钮状态也会更新

    # --- 导航方法 --- #
    def _navigate_explore_1d(self, event):
        """通知 AppController 导航到 Explore1D 视图。"""
        if event.new and self.view.selected_data_ids:
            data_id = self.view.selected_data_ids[0]
            # 确保 app_controller 存在
            if self.app_controller:
                print(f"探索按钮点击，数据ID: {data_id}") # Debug
                # 调用 AppController 的导航方法，传递视图名称和数据ID
                # 将 'explore_1d' 改为 'explore'
                self.app_controller.navigate_to('explore', data_id=data_id)
            else:
                 print("错误：AppController 未设置，无法导航。")

    def _navigate_explore_multidim(self, event):
        """通知 AppController 导航到 ExploreMultiD 视图。"""
        if event.new and self.view.selected_data_ids:
            data_id = self.view.selected_data_ids[0]
            if self.app_controller:
                 self.app_controller.navigate_to('explore_multidim', data_id=data_id)
            else:
                 print("错误：AppController 未设置，无法导航。")

    def _navigate_process(self, event):
        """通知 AppController 导航到 Process 视图。"""
        if event.new and self.view.selected_data_ids:
            selected_ids = list(self.view.selected_data_ids)
            if self.app_controller:
                self.app_controller.navigate_to('process', selected_ids=selected_ids)
            else:
                 print("错误：AppController 未设置，无法导航。")

    def _navigate_compare(self, event):
        """通知 AppController 导航到 Comparison 视图。"""
        if event.new and self.view.selected_data_ids:
            selected_ids = list(self.view.selected_data_ids)
            if self.app_controller:
                 self.app_controller.navigate_to('compare', selected_ids=selected_ids)
            else:
                 print("错误：AppController 未设置，无法导航。")

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 