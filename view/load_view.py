import panel as pn
import pandas as pd
import param
import io
import os # 导入 os 以使用 expanduser
from typing import List, Optional

pn.extension(sizing_mode="stretch_width")

class LoadView(param.Parameterized):
    """负责数据加载的 UI 视图 (使用 FileSelector)。"""
    # 引用 DataManager 获取列信息等?
    # 或者由 Controller 提供?
    # 暂时保持独立，列信息在加载后由 Controller 更新

    # UI 组件
    file_selector = param.ClassSelector(class_=pn.widgets.FileSelector, is_instance=True)
    time_column_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True)
    data_column_selector = param.ClassSelector(class_=pn.widgets.Select, is_instance=True)
    load_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    status_text = param.ClassSelector(class_=pn.pane.Markdown, is_instance=True)
    preview_area = param.ClassSelector(class_=pn.pane.DataFrame, is_instance=True)

    def __init__(self, **params):
        super().__init__(**params)
        self._create_ui_components()

    def _create_ui_components(self):
        # 使用 FileSelector，从项目根目录下的 'data' 文件夹开始浏览
        start_dir = 'data' 
        # 检查 data 文件夹是否存在，如果不存在，则使用当前目录
        if not os.path.isdir(start_dir):
            print(f"警告: 默认数据文件夹 '{start_dir}' 不存在，将使用当前目录 '.'")
            start_dir = '.'
            
        self.file_selector = pn.widgets.FileSelector(start_dir, file_pattern='*.csv', only_files=True, show_hidden=False)
        
        self.time_column_selector = pn.widgets.Select(name="选择时间列", options=[], disabled=True)
        self.data_column_selector = pn.widgets.Select(name="选择数据列 (可选)", options=[], disabled=True)
        self.load_button = pn.widgets.Button(name="加载选中文件", button_type="primary", disabled=True)
        self.status_text = pn.pane.Markdown("请在上方选择文件...")
        self.preview_area = pn.pane.DataFrame(None, height=200, sizing_mode='stretch_width')

        # 监听文件选择变化 (FileSelector 的 value 是选中的路径列表)
        self.file_selector.param.watch(self._on_path_select, 'value')
        self.time_column_selector.param.watch(self._on_column_select, 'value')

    def _on_path_select(self, event):
        selected_paths = event.new
        if selected_paths:
            # 尝试读取第一个选定文件的列名用于预览和选择
            first_path = selected_paths[0]
            try:
                # 只读少量数据进行预览和列名获取
                df_preview = pd.read_csv(first_path, nrows=5)
                columns = list(df_preview.columns)
                self.preview_area.object = df_preview
                self.time_column_selector.options = columns
                self.data_column_selector.options = ['[自动选择]'] + columns
                self.time_column_selector.disabled = False
                self.data_column_selector.disabled = False
                self.status_text.object = f"已选择 {len(selected_paths)} 个文件。请选择时间列和数据列。"
                self._on_column_select(None) # 触发按钮状态更新
            except Exception as e:
                self.status_text.object = f"错误：无法读取文件 '{os.path.basename(first_path)}' 的列名或预览: {e}"
                self.preview_area.object = None
                self.time_column_selector.options = []
                self.data_column_selector.options = []
                self.time_column_selector.disabled = True
                self.data_column_selector.disabled = True
                self.load_button.disabled = True
        else:
            self.preview_area.object = None
            self.status_text.object = "请在上方选择文件..."
            self.time_column_selector.options = []
            self.data_column_selector.options = []
            self.time_column_selector.disabled = True
            self.data_column_selector.disabled = True
            self.load_button.disabled = True

    def _on_column_select(self, event):
        # 只要选择了文件路径并且选择了时间列，就启用加载按钮
        if self.file_selector.value and self.time_column_selector.value:
            self.load_button.disabled = False
        else:
            self.load_button.disabled = True

    def update_status(self, message: str):
        self.status_text.object = message

    def get_panel(self) -> pn.layout.Panel:
        # FileSelector 可能比较高，调整布局
        return pn.Column(
            pn.pane.Markdown("## 加载一维时间序列 (CSV)"),
            self.file_selector, # 文件选择器放在顶部
            pn.pane.Markdown("### 文件预览 (首个文件前5行)"),
            self.preview_area,
            pn.Row(self.time_column_selector, self.data_column_selector),
            self.load_button,
            self.status_text,
            sizing_mode='stretch_width'
        ) 