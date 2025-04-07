import panel as pn
import param
from controller.data_controller import DataController

class AppController(param.Parameterized):
    """应用控制器：负责整体导航和页面管理"""
    
    current_page = param.String(default="数据加载")
    
    def __init__(self, **params):
        super(AppController, self).__init__(**params)
        # 初始化数据控制器
        self.data_controller = DataController()
        
        # 创建UI组件
        self._create_components()
        
        # 绑定事件
        self._bind_events()
        
        # 创建主布局
        self._create_layout()
    
    def _create_components(self):
        """创建UI组件"""
        # 导航按钮
        self.load_btn = pn.widgets.Button(
            name="数据加载", 
            button_type="primary", 
            width=120
        )
        self.vis_btn = pn.widgets.Button(
            name="数据可视化", 
            button_type="default", 
            width=120
        )
    
    def _bind_events(self):
        """绑定UI事件"""
        self.load_btn.on_click(self._switch_to_load_page)
        self.vis_btn.on_click(self._switch_to_visualization_page)
    
    def _create_layout(self):
        """创建应用布局"""
        # 创建导航栏
        self.nav_bar = pn.Row(
            pn.pane.Markdown("# 时间序列数据分析系统", margin=(10, 5, 10, 15)),
            pn.Spacer(width=20),
            self.load_btn,
            pn.Spacer(width=10),
            self.vis_btn,
            css_classes=['nav-bar'],
            height=60,
            margin=(0, 0, 10, 0),
            styles={'background': '#f8f9fa'},
            sizing_mode='stretch_width'
        )
        
        # 创建页面容器
        self.page_container = pn.Column(
            self.data_controller.get_load_interface(),
            sizing_mode='stretch_width'
        )
        
        # 创建主布局
        self.main_layout = pn.Column(
            self.nav_bar,
            pn.layout.Divider(),
            self.page_container,
            sizing_mode='stretch_width'
        )
    
    def _switch_to_load_page(self, event):
        """切换到数据加载页面"""
        # 更新导航栏按钮状态
        self.load_btn.button_type = "primary"
        self.vis_btn.button_type = "default"
        
        # 更新页面容器
        self.page_container.clear()
        self.page_container.append(self.data_controller.get_load_interface())
        
        # 更新当前页面标识
        self.current_page = "数据加载"
    
    def _switch_to_visualization_page(self, event):
        """切换到数据可视化页面"""
        # 更新导航栏按钮状态
        self.load_btn.button_type = "default"
        self.vis_btn.button_type = "primary"
        
        # 更新页面容器
        self.page_container.clear()
        self.page_container.append(self.data_controller.get_visualization_interface())
        
        # 更新当前页面标识
        self.current_page = "数据可视化"
    
    def get_app(self):
        """返回应用主界面"""
        return self.main_layout 