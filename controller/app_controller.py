import panel as pn
from model.data_manager import DataManager
from controller.load_controller import LoadController
from controller.data_manager_controller import DataManagerController
from controller.visualization_controller import VisualizationController
# 导入服务，确保它们被加载和注册
import services.visualizers
import services.data_structuring # 导入新的数据结构化服务
import services.preprocessors # 导入新的预处理器模块
# 如果有预处理器的话

class AppController:
    """应用程序主控制器，负责组装和管理各个子控制器和视图。"""

    def __init__(self):
        pn.extension(notifications=True) # 启用通知
        self.data_manager = DataManager() # 全局唯一的数据管理器

        # --- 初始化各个 MVC 组件 --- #
        self.load_controller = LoadController(data_manager=self.data_manager)
        self.data_manager_controller = DataManagerController(data_manager=self.data_manager)
        self.visualization_controller = VisualizationController(data_manager=self.data_manager)
        # 在这里可以添加多维数据处理、分析、可视化的 Controller
        # self.analysis_controller = AnalysisController(data_manager=self.data_manager)

        # --- 构建主应用布局 --- #
        self.app_layout = self._build_layout()

    def _build_layout(self) -> pn.layout.Tabs:
        """使用 Tabs 布局组合不同的功能页面。"""
        tabs = pn.Tabs(
            ("数据加载", self.load_controller.get_view_panel()),
            ("数据可视化", self.visualization_controller.get_view_panel()),
            ("数据管理", self.data_manager_controller.get_view_panel()),
            # ("多维分析", self.multi_dim_controller.get_view_panel()),
            # ("分析结果", self.analysis_controller.get_view_panel()),
            dynamic=True, # 提高性能，只渲染活动标签页
            tabs_location='left' # 将标签放在左侧
        )
        return tabs

    def get_app_layout(self) -> pn.layout.Panel:
        """返回完整的应用布局。"""
        return self.app_layout 