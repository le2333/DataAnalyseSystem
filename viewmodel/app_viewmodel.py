import param
import panel as pn
from typing import Dict, Any, Optional
from model.data_manager import DataManager
from viewmodel.data_manager_viewmodel import DataManagerViewModel
import importlib


class AppViewModel(param.Parameterized):
    """主应用视图模型，管理应用整体状态和导航"""

    # 核心数据模型
    data_manager = param.ClassSelector(class_=DataManager)

    # 子视图模型
    data_manager_viewmodel = param.ClassSelector(class_=DataManagerViewModel)

    # 视图状态
    current_view_name = param.String(default="data_manager", doc="当前视图名称")

    # 主内容区域
    main_area = param.ClassSelector(class_=pn.Column, is_instance=True)

    def __init__(self, **params):
        # 创建数据管理器
        data_manager = DataManager()

        # 创建子视图模型
        data_manager_viewmodel = DataManagerViewModel(data_manager=data_manager)

        # 初始化主区域
        main_area = pn.Column(sizing_mode="stretch_both")

        # 调用父类初始化
        super().__init__(
            data_manager=data_manager,
            data_manager_viewmodel=data_manager_viewmodel,
            main_area=main_area,
            **params,
        )

        # 监听视图名称变化
        self.param.watch(self._update_main_area, "current_view_name")

        # 初始显示
        self._update_main_area(None)

    def _update_main_area(self, event):
        """根据当前视图名称更新主内容区域"""
        view_name = self.current_view_name
        self.main_area.clear()

        # 根据视图名称加载对应内容
        if view_name == "data_manager":
            try:
                from view.data_manager_view import create_data_manager_view

                self.main_area.append(
                    create_data_manager_view(self.data_manager_viewmodel)
                )
            except ImportError as e:
                self.main_area.append(
                    pn.pane.Alert(
                        f"无法加载数据管理视图：{str(e)}", alert_type="danger"
                    )
                )
        elif view_name == "load":
            self.main_area.append(
                pn.pane.Alert("加载数据视图暂未实现，正在开发中...", alert_type="info")
            )
        elif view_name == "process":
            self.main_area.append(
                pn.pane.Alert("数据处理视图暂未实现，正在开发中...", alert_type="info")
            )
        elif view_name == "visualize":
            self.main_area.append(
                pn.pane.Alert(
                    "数据可视化视图暂未实现，正在开发中...", alert_type="info"
                )
            )
        else:
            self.main_area.append(
                pn.pane.Alert(f"未知视图: {view_name}", alert_type="danger")
            )

    def navigate_to(self, view_name: str, **kwargs):
        """导航到指定视图，并传递参数"""
        print(f"导航到: {view_name}，参数: {kwargs}")

        # 更新当前视图
        self.current_view_name = view_name

    def get_app_layout(self) -> pn.template.MaterialTemplate:
        """获取应用布局"""
        template = pn.template.MaterialTemplate(title="数据分析系统 (MVVM架构)")

        # 创建导航栏
        nav_items = [
            pn.widgets.Button(
                name="数据管理",
                button_type="light",
                width=100,
                on_click=lambda event: self.navigate_to("data_manager"),
            ),
            pn.widgets.Button(
                name="加载数据",
                button_type="light",
                width=100,
                on_click=lambda event: self.navigate_to("load"),
            ),
            pn.widgets.Button(
                name="处理数据",
                button_type="light",
                width=100,
                on_click=lambda event: self.navigate_to("process"),
            ),
            pn.widgets.Button(
                name="可视化",
                button_type="light",
                width=100,
                on_click=lambda event: self.navigate_to("visualize"),
            ),
        ]

        # 使用styles属性设置背景颜色
        navbar = pn.Row(
            *nav_items, height=50, margin=5, styles={"background-color": "#f0f0f0"}
        )

        # 添加导航栏和主区域
        template.header.append(navbar)
        template.main.append(self.main_area)

        return template
