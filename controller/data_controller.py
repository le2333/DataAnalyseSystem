import panel as pn
import os
import param
import time
import psutil
from model.data_model import DataModel
from view.data_view import DataView

class DataController(param.Parameterized):
    """数据控制器：连接数据模型和视图，处理用户交互"""
    
    # 反应式参数
    loaded_data_info = param.String(default="")
    perf_info = param.String(default="")
    
    def __init__(self, **params):
        super(DataController, self).__init__(**params)
        # 初始化模型和视图
        self.model = DataModel()
        self.view = DataView()
        
        # 初始化组件
        self._init_components()
        
        # 绑定事件
        self._bind_events()
        
        # 初始化状态
        self.loaded_data = None
        self.visualization_view = pn.Row("请先加载数据并选择要可视化的列")
        self.perf_stats = {'load_time': 0, 'render_time': 0, 'memory_usage': 0}
    
    
    def _init_components(self):
        """初始化UI组件"""
        # 数据加载组件
        self.file_selector = pn.widgets.FileSelector('data/', name='选择数据文件', 
                                                   only_files=True, file_pattern='*.csv')
        self.load_button = pn.widgets.Button(name='加载数据', button_type='primary')
        self.time_column = pn.widgets.Select(name='时间列', options=[])
        
        # 可视化组件
        self.column_selector = pn.widgets.MultiSelect(name='选择要显示的列', options=[])
        self.visualization_button = pn.widgets.Button(name='可视化', button_type='success')

        # 数据处理选项
        self.rendering_method = pn.widgets.RadioButtonGroup(
            name='渲染方式', 
            options=['自动', 'WebGL', 'LTTB降采样', 'Datashader栅格化'],
            value='自动'
        )

        # 多尺度分析选项
        self.multiscale_checkbox = pn.widgets.Checkbox(
            name='启用多尺度分析',
            value=False
        )

        # 数据采样率
        self.sample_rate = pn.widgets.FloatSlider(
            name='数据采样率', 
            start=0.01, 
            end=1.0, 
            value=1.0, 
            step=0.01
        )

        # 性能监控开关
        self.perf_monitor = pn.widgets.Checkbox(
            name='显示性能监控', 
            value=True
        )
    
    def _bind_events(self):
        """绑定UI事件"""
        self.load_button.on_click(self._load_data)
        self.visualization_button.on_click(self._visualize_data)
    
    def _load_data(self, event):
        """加载数据回调函数"""
        # 检查是否有选中的文件
        if not self.file_selector.value:
            self.loaded_data_info = "请选择一个CSV文件"
            return
            
        # 获取选中的文件
        file_path = self.file_selector.value[0]
        
        if file_path and os.path.exists(file_path):
            start_time = time.time()
            try:
                # 通过模型加载数据
                self.loaded_data = self.model.load_csv(file_path)
                
                # 更新列选择器
                self.column_selector.options = list(self.loaded_data.columns)
                self.time_column.options = list(self.loaded_data.columns)
                
                # 记录加载时间
                self.perf_stats['load_time'] = time.time() - start_time
                
                # 计算文件大小
                file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                
                # 更新加载信息
                self.loaded_data_info = (
                    f'数据加载成功: {len(self.loaded_data)}行 x {len(self.loaded_data.columns)}列 | '
                    f'文件大小: {file_size_mb:.1f} MB | '
                    f'加载耗时: {self.perf_stats["load_time"]:.2f}秒'
                )
                
            except Exception as e:
                self.loaded_data_info = f'数据加载失败: {str(e)}'
    
    def _visualize_data(self, event):
        """可视化数据回调函数"""
        if self.loaded_data is None or not self.column_selector.value:
            return
        
        try:
            # 确保设置时间索引
            if self.time_column.value:
                df = self.model.get_data().set_index(self.time_column.value)
            else:
                df = self.model.get_data()
            
            self.visualization_view = self.view.create_plot(
                df,
                self.column_selector.value
            )
        except Exception as e:
            self.visualization_view = pn.Row(f'可视化失败: {str(e)}')
    
    def get_load_interface(self):
        """返回数据加载界面"""
        return pn.Column(
            pn.Row('## 数据加载', sizing_mode='stretch_width'),
            # 文件选择行
            pn.Row(
                "从data目录选择CSV文件：", 
                self.file_selector,
                sizing_mode='stretch_width'
            ),
            # 时间列选择行
            pn.Row(
                "时间列：", 
                self.time_column, 
                self.load_button,
                sizing_mode='stretch_width'
            ),
            pn.layout.Divider(),
            pn.Row(self.loaded_data_info, sizing_mode='stretch_width'),
            pn.Row(self.perf_info, sizing_mode='stretch_width'),
            sizing_mode='stretch_width'
        )

    def get_visualization_interface(self):
        """返回数据可视化界面"""
        # 基本选项面板
        options_panel = pn.Column(
            pn.Row('## 数据可视化选项', sizing_mode='stretch_width'),
            pn.Row(
                pn.Column(
                    "选择要显示的列：",
                    self.column_selector,
                    sizing_mode='stretch_width'
                ),
                pn.Column(
                    "渲染设置：",
                    self.rendering_method,
                    pn.Row("采样率：", self.sample_rate),
                    self.multiscale_checkbox,
                    self.perf_monitor,
                    sizing_mode='stretch_width'
                ),
                sizing_mode='stretch_width'
            ),
            pn.Row(
                self.visualization_button,
                sizing_mode='stretch_width'
            ),
            pn.layout.Divider(),
            pn.Row(self.perf_info, sizing_mode='stretch_width'),
            sizing_mode='stretch_width'
        )
        
        # 将选项面板包装在可折叠Card中
        options_card = pn.Card(
            options_panel,
            title="可视化选项",
            collapsed=True,
            sizing_mode='stretch_width',
            margin=(0, 0, 2, 0)  # 添加底部margin，增加与下方卡片的距离
        )
        
        # 将可视化视图包装在Card中
        viz_card = pn.Card(
            self.visualization_view,
            title="可视化结果",
            sizing_mode='stretch_width',  # 只在宽度上伸展，高度自适应
            min_height=600,  # 设置最小高度，确保有足够空间显示图表
            margin=(0, 0, 0, 0)  # 无margin
        )
        
        # 垂直布局，让图表占据更多空间
        return pn.Column(
            options_card,
            pn.Spacer(height=5),  # 添加一个小间隔
            viz_card,
            sizing_mode='stretch_width'  # 只在宽度上伸展，高度自适应内容
        )