import panel as pn
import param
from model.data_manager import DataManager
from controller.load_controller import LoadController
from controller.data_manager_controller import DataManagerController
from controller.process_controller import ProcessController
from controller.comparison_controller import ComparisonController
# Import the new ExplorationController
from controller.exploration_controller import ExplorationController
# Views are managed by their controllers now, except maybe LoadView if it's simple
# from view.explore_1d_view import Explore1DView
# from view.explore_multidim_view import ExploreMultiDView
from view.load_view import LoadView # Keep if LoadController manages it directly

pn.extension(template='material')

class AppController(param.Parameterized):
    """应用主控制器，管理数据和视图切换。"""

    # 核心数据管理器
    data_manager = param.Parameter(DataManager(), precedence=-1)

    # 子控制器实例
    load_controller = param.Parameter(LoadController, precedence=-1)
    data_manager_controller = param.Parameter(DataManagerController, precedence=-1)
    process_controller = param.Parameter(ProcessController, precedence=-1)
    comparison_controller = param.Parameter(ComparisonController, precedence=-1)
    exploration_controller = param.Parameter(ExplorationController, precedence=-1) # Add new controller

    # 不需要单独管理 exploration views 了，由 ExplorationController 管理
    # explore_1d_view = param.Parameter(precedence=-1)
    # explore_multidim_view = param.Parameter(precedence=-1)

    # 当前主区域显示的视图名称
    current_view_name = param.String(default='data_manager')

    # 主内容区域
    main_area = param.ClassSelector(class_=pn.Column, is_instance=True)

    def __init__(self, **params):
        super().__init__(**params)
        # 实例化子控制器，传递依赖
        # Use param.update to set controller instances if using param.Parameter(ControllerClass)
        self.load_controller = LoadController(data_manager=self.data_manager)
        # Pass self.navigate_to as the callback
        self.data_manager_controller = DataManagerController(
            data_manager=self.data_manager,
            navigation_callback=self.navigate_to # Pass the method directly
        )
        self.process_controller = ProcessController(data_manager=self.data_manager)
        self.comparison_controller = ComparisonController(data_manager=self.data_manager)
        self.exploration_controller = ExplorationController(data_manager=self.data_manager) # Instantiate new

        # 初始化主区域
        self.main_area = pn.Column(self.data_manager_controller.get_view_panel(), sizing_mode='stretch_both')

        # 监听视图切换请求 (直接由 current_view_name 改变触发)
        self.param.watch(self._update_main_area_on_name_change, 'current_view_name')

    def _update_main_area_on_name_change(self, event):
        """Updates the main area when current_view_name changes directly."""
        view_name = event.new
        self._update_main_area(view_name)

    # Extracted the core logic to a separate method for reuse
    def _update_main_area(self, view_name: str):
        """Updates the main content area based on the view name."""
        self.main_area.clear()
        if view_name == 'data_manager':
            self.main_area.append(self.data_manager_controller.get_view_panel())
        elif view_name == 'load':
            self.main_area.append(self.load_controller.get_view_panel())
        elif view_name == 'explore': # Unified exploration view
            self.main_area.append(self.exploration_controller.get_view_panel())
        elif view_name == 'process':
            self.main_area.append(self.process_controller.get_view_panel())
        elif view_name == 'compare':
            self.main_area.append(self.comparison_controller.get_view_panel())
        else:
            self.main_area.append(pn.pane.Alert(f"未知视图: {view_name}", alert_type='danger'))

    def navigate_to(self, view_name: str, **kwargs):
        """Handles navigation: updates controller states and changes the current view."""
        print(f"AppController: Navigating to: {view_name} with args: {kwargs}")

        # 更新对应控制器的状态 (准备数据)
        if view_name == 'explore':
            data_id = kwargs.get('data_id')
            if data_id:
                 # Call the controller's method to set the data
                 self.exploration_controller.set_selected_data(data_id)
        elif view_name == 'process':
            selected_ids = kwargs.get('selected_ids')
            if selected_ids is not None:
                self.process_controller.set_selected_data(selected_ids)
        elif view_name == 'compare':
            selected_ids = kwargs.get('selected_ids')
            if selected_ids is not None:
                self.comparison_controller.set_selected_data(selected_ids)
        # No special preparation needed for 'load' or 'data_manager' currently

        # 切换视图 (触发 _update_main_area_on_name_change)
        if self.current_view_name != view_name:
             self.current_view_name = view_name
        else:
             # If navigating to the same view, still ensure the main area is updated correctly
             # (e.g., if navigating with different data)
             self._update_main_area(view_name)

    def get_app_layout(self) -> pn.template.MaterialTemplate:
        template = pn.template.MaterialTemplate(title="数据分析系统")

        # --- Remove Sidebar --- #
        # sidebar_content = pn.Column(
        #     pn.widgets.Button(name="数据加载", button_type='primary', width=200, align='center',
        #                       on_click=lambda event: self.navigate_to('load')),
        #     pn.widgets.Button(name="数据管理", button_type='primary', width=200, align='center',
        #                       on_click=lambda event: self.navigate_to('data_manager')),
        #     width=220
        # )
        # template.sidebar.append(sidebar_content)

        # Just append the main area
        template.main.append(self.main_area)

        return template 