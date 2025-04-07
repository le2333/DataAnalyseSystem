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
        return pn.Column(
            # 标题行
            pn.pane.Markdown('## 数据可视化', sizing_mode='stretch_width'),
            
            # 控制面板 - 独立的卡片
            pn.Card(
                pn.Column(
                    pn.Row(
                        pn.Column(
                            "选择要可视化的列：", 
                            self.column_selector,
                            width=300
                        ),
                        pn.Spacer(width=20),
                        pn.Spacer(width=20),
                        pn.Column(
                            " ",  # 占位符确保按钮垂直居中
                            self.visualization_button,
                            width=150
                        ),
                        sizing_mode='stretch_width'
                    ),
                    pn.Row(self.loaded_data_info, sizing_mode='stretch_width'),
                ),
                title="控制面板",
                collapsed=False,
                sizing_mode='stretch_width'
            ),
            
            # 性能信息
            pn.Row(self.perf_info, sizing_mode='stretch_width', height=30),
            
            # 数据可视化区域 - 单独的卡片
            pn.Card(
                self.visualization_view, 
                sizing_mode='stretch_width',
                min_height=550,  # 确保可视化有足够的空间
                margin=(10, 0)
            ),
            
            sizing_mode='stretch_width',
            height=800  # 为整个界面设置足够的高度
        ) 