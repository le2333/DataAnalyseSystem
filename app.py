import panel as pn
from controller.app_controller import AppController

# 初始化应用
pn.extension()
app_controller = AppController()
app = app_controller.get_app()

# 启动服务
if __name__ == '__main__':
    pn.serve(app, 
             title='时间序列数据分析系统', 
             show=True, 
             port=5006, 
             auto_reload=True) 