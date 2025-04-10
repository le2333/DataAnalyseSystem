import panel as pn
import pandas as pd
import param
from typing import List, Dict
# 假设 DataManager 会被 Controller 注入

pn.extension(sizing_mode="stretch_width")

class DataManagerView(param.Parameterized):
    """负责展示 DataManager 内容和提供基本交互 (重命名/删除) 的视图。"""
    data_manager = param.Parameter(precedence=-1) # 依赖注入 DataManager
    selected_data_id = param.String(default="", label="选中的数据ID") # 跟踪选中的行

    # UI 组件
    data_table = param.ClassSelector(class_=pn.widgets.DataFrame, is_instance=True)
    rename_input = param.ClassSelector(class_=pn.widgets.TextInput, is_instance=True)
    rename_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    delete_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    details_area = param.ClassSelector(class_=pn.pane.Markdown, is_instance=True)

    def __init__(self, data_manager, **params):
        super().__init__(data_manager=data_manager, **params)
        self._create_ui_components()
        self._update_table()

    def _create_ui_components(self):
        self.data_table = pn.widgets.DataFrame(value=pd.DataFrame(),
                                                titles={'id': 'ID', 'name': '名称', 'type': '类型', 'created_at': '创建时间', 'shape': '形状/长度', 'source_count': '来源数', 'operation': '生成操作'},
                                                row_height=30, sizing_mode='stretch_width', max_height=400,
                                                disabled=True, # 禁止直接编辑表格
                                                auto_edit=False,
                                                show_index=False)
        self.rename_input = pn.widgets.TextInput(name="新名称", placeholder="输入新名称...")
        self.rename_button = pn.widgets.Button(name="重命名", button_type="warning", disabled=True)
        self.delete_button = pn.widgets.Button(name="删除选中项", button_type="danger", disabled=True)
        self.details_area = pn.pane.Markdown("请先选择一个数据项查看详情", sizing_mode='stretch_width')

        # 绑定表格选择事件
        self.data_table.param.watch(self._on_selection_change, 'selection')

    @param.depends('data_manager._data_updated', watch=True)
    def _update_table(self):
        summaries = self.data_manager.list_data_summaries()
        df = pd.DataFrame(summaries)
        # 调整列顺序和显示
        cols_to_show = ['id', 'name', 'type', 'shape', 'source_count', 'operation', 'created_at']
        available_cols = [col for col in cols_to_show if col in df.columns]
        self.data_table.value = df[available_cols] if not df.empty else pd.DataFrame(columns=available_cols)
        self.data_table.selection = [] # 清除选择
        self._update_buttons_state()
        self._update_details_area()

    def _on_selection_change(self, event):
        if event.new:
            selected_index = event.new[0] # 只处理单选
            if selected_index < len(self.data_table.value):
                self.selected_data_id = self.data_table.value.iloc[selected_index]['id']
            else:
                 self.selected_data_id = ""
        else:
            self.selected_data_id = ""
        self._update_buttons_state()
        self._update_details_area()

    def _update_buttons_state(self):
        enabled = bool(self.selected_data_id)
        self.rename_button.disabled = not enabled
        self.delete_button.disabled = not enabled
        self.rename_input.value = "" # 清空输入框

    def _update_details_area(self):
        if self.selected_data_id:
            data_obj = self.data_manager.get_data(self.selected_data_id)
            if data_obj:
                metadata = data_obj.get_summary() # 获取摘要即可
                details_md = "### 数据详情\n"
                for key, value in metadata.items():
                    details_md += f"- **{key.replace('_', ' ').title()}:** {value}\n"
                # 可以考虑显示更详细的元数据 data_object.metadata
                self.details_area.object = details_md
            else:
                 self.details_area.object = "错误：无法找到所选数据项的详细信息。"
        else:
            self.details_area.object = "请先选择一个数据项查看详情"

    def get_panel(self) -> pn.layout.Panel:
        """返回数据管理页面的布局。"""
        actions_row = pn.Row(
            self.rename_input,
            self.rename_button,
            self.delete_button,
            sizing_mode='stretch_width'
        )
        layout = pn.Column(
            pn.pane.Markdown("## 数据管理"),
            self.data_table,
            actions_row,
            pn.pane.Markdown("### 详情"),
            self.details_area,
            sizing_mode='stretch_width'
        )
        return layout 