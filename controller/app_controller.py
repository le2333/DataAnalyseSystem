import panel as pn
import param
from model.data_manager import DataManager
from controller.load_controller import LoadController
from controller.data_manager_controller import DataManagerController
from controller.process_controller import ProcessController
# 导入统一的可视化控制器
from controller.unified_visualization_controller import UnifiedVisualizationController
# 视图由各自的控制器管理
# from view.load_view import LoadView # LoadController 直接管理 LoadView

pn.extension(template='material')

class AppController(param.Parameterized):
    """应用主控制器，管理数据和视图切换。"""

    # 核心数据管理器
    data_manager = param.Parameter(DataManager(), precedence=-1)

    # 子控制器实例 (使用类作为类型提示，在 __init__ 中实例化)
    load_controller = param.Parameter(LoadController, precedence=-1)
    data_manager_controller = param.Parameter(DataManagerController, precedence=-1)
    process_controller = param.Parameter(ProcessController, precedence=-1)
    unified_visualization_controller = param.Parameter(UnifiedVisualizationController, precedence=-1)

    # 当前主区域显示的视图名称
    current_view_name = param.String(default='data_manager')

    # 主内容区域
    main_area = param.ClassSelector(class_=pn.Column, is_instance=True)

    def __init__(self, **params):
        super().__init__(**params)
        # 实例化子控制器，传递依赖
        self.load_controller = LoadController(data_manager=self.data_manager)
        # 将 self.navigate_to 作为回调传递给 DataManagerController
        self.data_manager_controller = DataManagerController(
            data_manager=self.data_manager,
            navigation_callback=self.navigate_to # 直接传递方法
        )
        self.process_controller = ProcessController(data_manager=self.data_manager)
        # 实例化统一的控制器
        self.unified_visualization_controller = UnifiedVisualizationController(data_manager=self.data_manager)

        # 初始化主区域，默认显示数据管理器视图
        self.main_area = pn.Column(self.data_manager_controller.get_view_panel(), sizing_mode='stretch_both')

        # 监听视图切换请求 (当 current_view_name 改变时触发)
        self.param.watch(self._update_main_area_on_name_change, 'current_view_name')

    def _update_main_area_on_name_change(self, event):
        """当 current_view_name 直接改变时更新主区域。"""
        view_name = event.new
        self._update_main_area(view_name)

    # 将核心更新逻辑提取到单独的方法中以便复用
    def _update_main_area(self, view_name: str):
        """根据视图名称更新主内容区域。"""
        self.main_area.clear()
        if view_name == 'data_manager':
            self.main_area.append(self.data_manager_controller.get_view_panel())
        elif view_name == 'load':
            self.main_area.append(self.load_controller.get_view_panel())
        elif view_name == 'process':
            self.main_area.append(self.process_controller.get_view_panel())
        elif view_name == 'visualize': # 统一的可视化视图路由
            self.main_area.append(self.unified_visualization_controller.get_view_panel())
        else:
            self.main_area.append(pn.pane.Alert(f"未知视图: {view_name}", alert_type='danger'))

    def navigate_to(self, view_name: str, **kwargs):
        """处理导航：更新控制器状态并更改当前视图。"""
        print(f"AppController: 正在导航到: {view_name}，参数: {kwargs}")

        # 更新对应控制器的状态 (准备数据)
        if view_name == 'process':
            selected_ids = kwargs.get('selected_ids')
            if selected_ids is not None:
                self.process_controller.set_selected_data(selected_ids)
        elif view_name == 'visualize': # 处理到统一视图的导航
            selected_ids = kwargs.get('selected_ids') # 期望是列表或单个字符串
            if selected_ids is not None:
                 self.unified_visualization_controller.set_selected_data(selected_ids)

        # 切换视图 (触发 _update_main_area_on_name_change)
        if self.current_view_name != view_name:
             self.current_view_name = view_name
        else:
             # 如果导航到相同视图，仍然确保主区域正确更新
             # (例如，使用不同的数据导航)
             self._update_main_area(view_name)

    def get_app_layout(self) -> pn.template.MaterialTemplate:
        template = pn.template.MaterialTemplate(title="数据分析系统 (统一视图)")

        # 直接添加主区域
        template.main.append(self.main_area)

        return template 