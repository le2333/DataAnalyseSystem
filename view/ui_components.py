import panel as pn
import param
import pandas as pd

class LoadInterface(param.Parameterized):
    """封装数据加载相关的UI组件和布局"""
    
    # UI 组件
    file_selector = pn.widgets.FileSelector(
        'data/', 
        name='选择数据文件', 
        only_files=True, 
        file_pattern='*.csv'
    )
    # 注意：time_column 的 options 需要在 DataController 中根据加载的文件动态更新
    time_column = pn.widgets.Select(name='时间列', options=[]) 
    load_button = pn.widgets.Button(name='加载数据', button_type='primary')
    loaded_data_info_display = pn.pane.Markdown("", sizing_mode='stretch_width')

    def get_panel(self):
        """返回此UI单元的Panel布局"""
        return pn.Column(
            pn.Row('## 数据加载', sizing_mode='stretch_width'),
            # 文件选择行
            pn.Row(
                "从data目录选择CSV文件：", 
                self.file_selector,
                sizing_mode='stretch_width'
            ),
            # 时间列选择行 (加载按钮暂放这里，后续可调整)
            pn.Row(
                "时间列：", 
                self.time_column, 
                self.load_button,
                sizing_mode='stretch_width'
            ),
            pn.layout.Divider(),
            pn.Row(self.loaded_data_info_display, sizing_mode='stretch_width'),
            # 性能信息暂时移到可视化部分或单独处理
            # pn.Row(self.perf_info, sizing_mode='stretch_width'), 
            sizing_mode='stretch_width'
        )

class VisMainOptions(param.Parameterized):
    """封装可视化主要选项（数据源、列、触发按钮）"""
    
    # UI 组件
    source_selector = pn.widgets.MultiSelect(name='选择数据源', options=[], sizing_mode='stretch_width')
    column_selector = pn.widgets.MultiSelect(name='选择要显示的列', options=[], sizing_mode='stretch_width')
    visualization_button = pn.widgets.Button(name='可视化', button_type='success')

    def get_panel(self):
        """返回此UI单元的Panel布局"""
        # 先简单组合，后续可在 get_visualization_interface 中放入Card
        return pn.Column(
            "选择数据源和列：",
            self.source_selector,
            self.column_selector,
            self.visualization_button,
            sizing_mode='stretch_width'
        )
        
    def update_source_options(self, options):
        """更新数据源选择器的选项"""
        self.source_selector.options = options
        # 考虑是否需要重置 value
        # self.source_selector.value = [] 

    def update_column_options(self, options):
        """更新列选择器的选项"""
        # 保留已选中的有效列
        current_selection = self.column_selector.value
        self.column_selector.options = options
        self.column_selector.value = [col for col in current_selection if col in options] 

class VisRenderingOptions(param.Parameterized):
    """封装可视化渲染相关的选项"""
    
    rendering_method = pn.widgets.RadioButtonGroup(
        name='渲染方式', 
        options=['自动', 'WebGL', 'Datashader栅格化'],
        value='自动'
    )

    def get_panel(self):
        """返回此UI单元的Panel布局"""
        return pn.Column(
            "渲染设置：",
            self.rendering_method,
            sizing_mode='stretch_width'
        )
        
    def get_config(self):
        """返回渲染配置字典"""
        use_datashader = None
        if self.rendering_method.value == 'Datashader栅格化':
            use_datashader = True
        elif self.rendering_method.value == 'WebGL':
             use_datashader = False
             
        return {
            'use_datashader': use_datashader, # 传递给视图的选项
        }

class TimeAlignmentOptions(param.Parameterized):
    """封装时间对齐相关的选项"""
    
    align_checkbox = pn.widgets.Checkbox(
        name='启用时间对齐', 
        value=False
    )
    align_method = pn.widgets.Select(
        name='对齐方法',
        options=['nearest', 'ffill', 'bfill', 'linear'],
        value='nearest',
        disabled=True # 默认禁用
    )
    align_freq = pn.widgets.Select(
        name='对齐频率',
        options=['原始', '1s', '100ms', '1min', '5min', '10min', '1h'],
        value='原始',
        disabled=True # 默认禁用
    )

    @param.depends('align_checkbox.value', watch=True)
    def _toggle_alignment_options(self):
        """根据复选框状态启用/禁用对齐选项"""
        is_enabled = self.align_checkbox.value
        self.align_method.disabled = not is_enabled
        self.align_freq.disabled = not is_enabled

    def get_panel(self):
        """返回此UI单元的Panel布局"""
        return pn.Column(
            "时间对齐设置：",
            pn.Row(self.align_checkbox),
            pn.Row("对齐方法：", self.align_method),
            pn.Row("对齐频率：", self.align_freq),
            sizing_mode='stretch_width'
        )
        
    def get_config(self):
        """返回时间对齐配置字典"""
        if not self.align_checkbox.value:
            return {'enabled': False}
            
        return {
            'enabled': True,
            'method': self.align_method.value,
            'freq': None if self.align_freq.value == '原始' else self.align_freq.value
        }

class SourceTimeMappingDisplay(param.Parameterized):
    """封装数据显示源时间列映射的Tabulator"""
    
    source_time_mapping = pn.widgets.Tabulator(
            value=pd.DataFrame({'数据源': [], '时间列': []}),
            # name='数据源时间列映射', # 名字放在外部Column里
            widths={'数据源': 150, '时间列': 150},
            disabled=True,
            sizing_mode='stretch_width' 
    )
    
    def update_mapping(self, data_frame):
        """更新Tabulator的数据"""
        self.source_time_mapping.value = data_frame
        
    def get_panel(self):
        """返回此UI单元的Panel布局"""
        return pn.Column(
             "数据源时间列映射：",
             self.source_time_mapping,
             sizing_mode='stretch_width'
        ) 