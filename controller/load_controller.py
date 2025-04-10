import param
import panel as pn
import pandas as pd # 导入 pandas 用于文件读取
from model.data_manager import DataManager
from view.load_view import LoadView
from services.registry import STRUCTURERS # 导入数据结构化注册表
import os

class LoadController(param.Parameterized):
    """处理 LoadView 交互，读取文件，调用结构化服务并将数据添加到 DataManager。"""

    data_manager = param.Parameter(precedence=-1)
    view = param.Parameter(precedence=-1)

    # 加载状态
    is_loading = param.Boolean(default=False, precedence=-1)

    def __init__(self, data_manager: DataManager, **params):
        view_instance = LoadView()
        super().__init__(data_manager=data_manager, view=view_instance, **params)
        self._bind_events()

    def _bind_events(self):
        self.view.load_button.on_click(self._handle_load)

    def _handle_load(self, event):
        if self.is_loading:
            return
        
        # 从 FileSelector 获取文件路径列表
        selected_file_paths = self.view.file_selector.value
        time_col = self.view.time_column_selector.value
        data_col_option = self.view.data_column_selector.value
        data_col = None if data_col_option == '[自动选择]' else data_col_option

        if not selected_file_paths:
            self.view.update_status("错误：未选择任何文件。")
            return
        if not time_col:
            self.view.update_status("错误：必须选择时间列。")
            return

        self.is_loading = True
        self.view.load_button.loading = True
        self.view.update_status("正在加载和处理数据...")

        # --- 获取结构化服务 --- #
        structurer_name = "Structure DataFrame to Time Series"
        structurer_info = STRUCTURERS.get(structurer_name)
        if not structurer_info:
            self.view.update_status(f"错误：找不到数据结构化服务 '{structurer_name}'")
            self.is_loading = False
            self.view.load_button.loading = False
            return
        
        structurer_func = structurer_info['function']
        success_count = 0
        error_count = 0
        error_messages = []

        # --- 同步处理每个文件 --- #
        for i, file_path in enumerate(selected_file_paths):
            # 获取文件名用于消息
            filename = os.path.basename(file_path)
            base_name_for_naming = os.path.splitext(filename)[0]
            df_read = None # 初始化 df_read
            
            try:
                # --- 1. 文件读取阶段 (同步) --- #
                df_read = pd.read_csv(
                    file_path,
                    parse_dates=[time_col]
                )

                # --- 2. 数据结构化阶段 (同步) --- #
                new_data_container = structurer_func(
                    input_df=df_read,
                    time_column_name=time_col,
                    data_column_name=data_col,
                    base_name_for_naming=base_name_for_naming,
                    name_prefix="Loaded"
                )
                
                # --- 3. 添加到 DataManager --- #
                if new_data_container:
                    self.data_manager.add_data(new_data_container)
                    success_count += 1
                else:
                     error_count += 1
                     error_messages.append(f"{filename}: 数据结构化服务返回空结果。")

            except FileNotFoundError as e:
                 error_count += 1
                 error_messages.append(f"{filename}: 文件读取失败 - {e}")
            except ValueError as e: # 捕获 read_csv 或结构化服务中的 ValueError
                 error_count += 1
                 error_messages.append(f"{filename}: 处理失败 - {e}")
            except Exception as e: # 捕获其他意外错误
                 error_count += 1
                 error_messages.append(f"{filename}: 发生意外错误 - {e}")
            finally:
                # 更新进度（如果需要）
                progress = (i + 1) / len(selected_file_paths) * 100
                self.view.update_status(f"处理进度: {progress:.1f}% ({i+1}/{len(selected_file_paths)}) ...")

        # --- 更新最终状态 --- #
        final_status = f"处理完成：成功 {success_count} 个，失败 {error_count} 个。"
        if error_messages:
            final_status += "\n错误详情:\n" + "\n".join(f"- {msg}" for msg in error_messages)
        
        self.view.update_status(final_status)
        self.is_loading = False
        self.view.load_button.loading = False
        # Consider clearing selection after load
        # self.view.file_selector.value = []

    def get_view_panel(self) -> pn.layout.Panel:
        """返回此控制器管理的视图 Panel。"""
        return self.view.get_panel() 