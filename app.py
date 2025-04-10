import panel as pn
from controller.app_controller import AppController

# 创建 AppController 实例
app_controller = AppController()

# 获取应用布局并使其可服务
app_layout = app_controller.get_app_layout()
app_layout.servable(title="数据分析系统")

# 启动服务
if __name__ == '__main__':
    pn.serve(app_layout, 
             title='时间序列数据分析系统', 
             show=True, 
             port=5006, 
             auto_reload=True) 