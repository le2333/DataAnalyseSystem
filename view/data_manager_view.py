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
    # 使用 Panel 的 ButtonGroup 或独立的 Buttons
    explore_1d_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    explore_multidim_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    process_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    compare_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)
    remove_button = param.ClassSelector(class_=pn.widgets.Button, is_instance=True)

    # 内部状态
    selected_data_ids = param.List(default=[])

    # 事件，用于通知 Controller/AppController
    # 参数可以是选择的 ID 列表
    explore_1d_request = param.Event(default=False)
    explore_multidim_request = param.Event(default=False)
    process_request = param.Event(default=False)
    compare_request = param.Event(default=False)
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

        # 操作按钮
        self.explore_1d_button = pn.widgets.Button(name="探索 (1D)", button_type="primary", disabled=True)
        self.explore_multidim_button = pn.widgets.Button(name="探索 (MultiD)", button_type="primary", disabled=True)
        self.process_button = pn.widgets.Button(name="数据处理...", button_type="success", disabled=True)
        self.compare_button = pn.widgets.Button(name="可视化比较...", button_type="warning", disabled=True)
        self.remove_button = pn.widgets.Button(name="删除选中", button_type="danger", disabled=True)

        # 绑定按钮点击事件到内部触发方法
        self.explore_1d_button.on_click(self._trigger_explore_1d)
        self.explore_multidim_button.on_click(self._trigger_explore_multidim)
        self.process_button.on_click(self._trigger_process)
        self.compare_button.on_click(self._trigger_compare)
        self.remove_button.on_click(self._trigger_remove)

    @param.depends('data_manager._data_updated', watch=True)
    def _update_data_table(self):
        """更新数据表内容。"""
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
            selected_df = self.data_table.value.iloc[selected_indices]
            self.selected_data_ids = selected_df['id'].tolist()
        self._update_button_states()

    def _update_button_states(self):
        """根据选择的数据更新按钮的可用状态。"""
        num_selected = len(self.selected_data_ids)
        selected_types = set()
        if num_selected > 0:
            selected_types = {self.data_manager.get_data(sid).data_type for sid in self.selected_data_ids if self.data_manager.get_data(sid)}

        is_single_selection = num_selected == 1
        is_multi_selection = num_selected > 0

        # 探索 (1D) 按钮: 仅当选中一个 TimeSeriesData 时可用
        self.explore_1d_button.disabled = not (is_single_selection and TimeSeriesData.DATA_TYPE in selected_types)

        # 探索 (MultiD) 按钮: 仅当选中一个 MultiDimData 时可用
        self.explore_multidim_button.disabled = not (is_single_selection and MultiDimData.DATA_TYPE in selected_types)

        # 数据处理按钮: 选中至少一个时可用
        self.process_button.disabled = not is_multi_selection

        # 可视化比较按钮: 选中多个同类型数据时可用 (简单逻辑，可改进)
        is_comparable = num_selected > 1 and len(selected_types) == 1
        self.compare_button.disabled = not is_comparable

        # 删除按钮: 选中至少一个时可用
        self.remove_button.disabled = not is_multi_selection

    # --- 事件触发方法 --- #
    def _trigger_explore_1d(self, event):
        if self.selected_data_ids:
            # 触发事件，传递单个 ID
            self.param.trigger('explore_1d_request')

    def _trigger_explore_multidim(self, event):
        if self.selected_data_ids:
            self.param.trigger('explore_multidim_request')

    def _trigger_process(self, event):
        if self.selected_data_ids:
            self.param.trigger('process_request')

    def _trigger_compare(self, event):
        if self.selected_data_ids:
            self.param.trigger('compare_request')

    def _trigger_remove(self, event):
        if self.selected_data_ids:
            self.param.trigger('remove_request')

    def get_panel(self) -> pn.layout.Panel:
        """返回数据管理视图的布局。"""
        button_bar = pn.Row(
            self.explore_1d_button,
            self.explore_multidim_button,
            self.process_button,
            self.compare_button,
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