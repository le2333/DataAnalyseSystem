import panel as pn

# 使用新的MVVM架构
from viewmodel.app_viewmodel import AppViewModel

# 导入服务模块以触发类自动注册
# 加载器和结构化器


# 创建应用视图模型
app_viewmodel = AppViewModel()

# 获取应用布局并使其可服务
app_layout = app_viewmodel.get_app_layout()
app_layout.servable(title="数据分析系统 (MVVM架构)")

# 启动服务
if __name__ == "__main__":
    pn.serve(
        app_layout, title="时间序列数据分析系统", show=True, port=5006, auto_reload=True
    )
