import panel as pn
import pandas as pd
import param
from typing import List, Dict, Any
from model.data_manager import DataManager
from model.timeseries_data import TimeSeriesData # For type checking
from model.multidim_data import MultiDimData # For type checking

pn.extension('tabulator', sizing_mode="stretch_width")

class DataManagerView(param.Parameterized):
    """显示和管理 DataManager 中的数据，并触发操作。"""
    data_manager = param.Parameter(precedence=-1)

    # UI 组件
    data_table = param.ClassSelector(class_=pn.widgets.Tabulator, is_instance=True)
    # Add Load button
    load_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    process_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    visualize_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    remove_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)

    # 内部状态
    selected_data_ids = param.List(default=[])

    # --- Events triggered by this view --- #
    load_request = param.Event(default=False) # Added event for loading
    process_request = param.Event(default=False)
    visualize_request = param.Event(default=False)
    remove_request = param.Event(default=False)

    def __init__(self, data_manager: DataManager, **params):
        super().__init__(data_manager=data_manager, **params)
        self._create_ui_components()
        self._update_data_table()
        self._setup_watchers()

    def _create_ui_components(self):
        # 配置 Tabulator
        self.data_table = pn.widgets.Tabulator(
            pd.DataFrame(), # 使用空的 DataFrame
            layout='fit_columns',
            pagination='local', page_size=10,
            selectable='checkbox', # 允许多选
            show_index=False,
            sizing_mode='stretch_width',
            height=400 # 固定高度
            # 可以根据需要添加 headers, formatters 等
        )

        # --- 操作按钮 --- #
        # Add Load Button definition
        self.load_button = pn.widgets.Button(name="数据加载...", button_type="primary", css_classes=['pn-button-primary']) # Always enabled
        self.process_button = pn.widgets.Button(name="数据处理...", button_type="success", disabled=True)
        self.visualize_button = pn.widgets.Button(name="可视化...", button_type="warning", disabled=True)
        self.remove_button = pn.widgets.Button(name="删除选中", button_type="danger", disabled=True)

        # --- 绑定按钮点击事件到内部触发方法 --- #
        self.load_button.on_click(self._trigger_load)
        self.process_button.on_click(self._trigger_process)
        self.visualize_button.on_click(self._trigger_visualize)
        self.remove_button.on_click(self._trigger_remove)

    @param.depends('data_manager._data_updated', watch=True)
    def _update_data_table(self):
        """更新数据表内容。"""
        # Call the unified method, default sort is by name
        summaries = self.data_manager.get_summary_list()
        # 过滤掉不适合显示的内部列，例如 _data
        filtered_summaries = []
        for s in summaries:
             fs = {k: v for k, v in s.items() if not k.startswith('_')}
             # 确保核心列存在
             for key in ['id', 'name', 'type']:
                 if key not in fs:
                     fs[key] = s.get(key, 'N/A')
             filtered_summaries.append(fs)
        self.data_table.value = pd.DataFrame(filtered_summaries)
        # 更新后清空选择并禁用按钮
        self.data_table.selection = []
        self._update_button_states()

    def _setup_watchers(self):
        """监听表格选择变化。"""
        self.data_table.param.watch(self._on_selection_change, 'selection')

    def _on_selection_change(self, event):
        """根据表格选择更新内部状态和按钮可用性。"""
        selected_indices = event.new
        if not selected_indices:
            self.selected_data_ids = []
        else:
            # 从 DataFrame 中获取选定行的 'id' 列
            # Need to handle potential KeyError if 'id' column is missing in rare cases
            try:
                selected_df = self.data_table.value.iloc[selected_indices]
                if 'id' in selected_df.columns:
                    self.selected_data_ids = selected_df['id'].tolist()
                else:
                    print("Warning: 'id' column not found in data table value.")
                    self.selected_data_ids = []
            except IndexError:
                 print("Warning: IndexError during selection change.")
                 self.selected_data_ids = []
        self._update_button_states()

    def _update_button_states(self):
        """根据选择的数据更新按钮的可用状态。"""
        num_selected = len(self.selected_data_ids)
        is_selection = num_selected > 0

        # Visualize button: Enabled if at least one item is selected
        self.visualize_button.disabled = not is_selection

        # Data Processing button: Enabled if at least one item is selected
        self.process_button.disabled = not is_selection

        # Remove button: Enabled if at least one item is selected
        self.remove_button.disabled = not is_selection
        # Load button is always enabled
        # self.load_button.disabled = False 

    # --- 事件触发方法 --- #
    def _trigger_load(self, event):
        """Triggers the load_request event."""
        self.load_request = True

    def _trigger_process(self, event):
        if self.selected_data_ids:
             # Trigger event with True, controller will get IDs from view state
            self.process_request = True

    def _trigger_visualize(self, event):
        if self.selected_data_ids:
            self.visualize_request = True

    def _trigger_remove(self, event):
        if self.selected_data_ids:
             # This one was already correct
            self.remove_request = True

    def get_panel(self) -> pn.layout.Panel:
        """返回数据管理视图的布局。"""
        # Add Load button to the button bar
        button_bar = pn.Row(
            self.load_button, # Add load button here
            self.visualize_button,
            self.process_button,
            self.remove_button,
            sizing_mode='stretch_width'
        )
        return pn.Column(
            pn.pane.Markdown("## 数据管理中心"),
            self.data_table,
            pn.pane.Markdown("### 操作"),
            button_bar,
            sizing_mode="stretch_width"
        ) 