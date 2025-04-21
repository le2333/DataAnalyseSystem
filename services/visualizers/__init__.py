"""可视化服务包。

此包包含各种用于生成数据可视化的服务模块。
导入此包时，会自动加载并注册所有定义的可视化服务。
"""

# 导入所有可视化服务模块以确保服务被注册
from . import timeseries_basic
from . import timeseries_interactive

# 可以在这里添加更多可视化服务的模块导入
# from . import image_visualizer # 例如，如果未来添加

# 定义 __all__ 可以控制 'from services.visualizers import *' 的行为
# 如果不定义，默认导入所有非下划线开头的名称（包括导入的模块名）
# __all__ = ['timeseries_basic', 'timeseries_interactive']

# 可选：在这里导入子模块中的关键服务或类，以便更容易访问
# from .timeseries_basic import plot_timeseries_linked_view
# from .timeseries_interactive import plot_timeseries_complex_layout_refactored

# This file makes the visualizers directory a Python package.
# It can be left empty or used to import submodules. 