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
        self.data_manager_controller = DataManagerController(data_manager=self.data_manager, app_controller=self)
        self.process_controller = ProcessController(data_manager=self.data_manager)
        self.comparison_controller = ComparisonController(data_manager=self.data_manager)
        self.exploration_controller = ExplorationController(data_manager=self.data_manager) # Instantiate new

        # 初始化主区域
        self.main_area = pn.Column(self.data_manager_controller.get_view_panel(), sizing_mode='stretch_both')

        self.param.watch(self._update_main_area, 'current_view_name')

    def _update_main_area(self, event):
        view_name = event.new
        self.main_area.clear()
        if view_name == 'data_manager':
            self.main_area.append(self.data_manager_controller.get_view_panel())
        elif view_name == 'load':
            # Assuming LoadController provides its view panel
            self.main_area.append(self.load_controller.get_view_panel())
        elif view_name == 'explore': # Unified exploration view
            self.main_area.append(self.exploration_controller.get_view_panel())
        # Remove explore_1d and explore_multidim cases
        # elif view_name == 'explore_1d': ...
        # elif view_name == 'explore_multidim': ...
        elif view_name == 'process':
            self.main_area.append(self.process_controller.get_view_panel())
        elif view_name == 'compare':
            self.main_area.append(self.comparison_controller.get_view_panel())
        else:
            self.main_area.append(pn.pane.Alert(f"未知视图: {view_name}", alert_type='danger'))

    def navigate_to(self, view_name: str, **kwargs):
        print(f"Navigating to: {view_name} with args: {kwargs}")

        # 根据目标视图更新对应控制器的状态
        if view_name == 'explore': # Unified explore
            data_id = kwargs.get('data_id') # Expecting single ID
            if data_id:
                 # Call the controller's method to set the data
                 self.exploration_controller.set_selected_data(data_id)
        # Remove explore_1d and explore_multidim cases
        # elif view_name == 'explore_1d': ...
        # elif view_name == 'explore_multidim': ...
        elif view_name == 'process':
            selected_ids = kwargs.get('selected_ids')
            if selected_ids is not None:
                self.process_controller.set_selected_data(selected_ids)
        elif view_name == 'compare':
            selected_ids = kwargs.get('selected_ids')
            if selected_ids is not None:
                self.comparison_controller.set_selected_data(selected_ids)

        # 切换视图
        self.current_view_name = view_name

    def get_app_layout(self) -> pn.template.MaterialTemplate:
        template = pn.template.MaterialTemplate(title="数据分析系统")

        # Update sidebar to reflect new structure if needed
        # DataManagerView now handles triggering navigation
        sidebar_content = pn.Column(
            pn.widgets.Button(name="数据加载", button_type='primary', width=200, align='center'),
            pn.widgets.Button(name="数据管理", button_type='primary', width=200, align='center'),
            width=220
        )
        sidebar_content[0].on_click(lambda event: self.navigate_to('load'))
        sidebar_content[1].on_click(lambda event: self.navigate_to('data_manager'))

        template.sidebar.append(sidebar_content)
        template.main.append(self.main_area)

        return template 