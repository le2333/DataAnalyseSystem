import param
import pandas as pd
from typing import List, Dict, Any, Optional, Type
from model.data_manager import DataManager
from services.base import DataLoader, DataStructurer


class LoadViewModel(param.Parameterized):
    """数据加载视图模型，处理文件加载和数据结构化"""

    # 持有数据管理器模型
    data_manager = param.ClassSelector(class_=DataManager)

    # UI状态和数据
    status_message = param.String(default="请选择文件并配置加载参数", doc="状态信息")
    status_type = param.String(
        default="info", doc="状态类型：info, success, warning, danger"
    )
    preview_data = param.DataFrame(default=None, doc="预览数据")
    selected_files = param.List(default=[], doc="选中的文件列表")
    available_columns = param.List(default=[], doc="可用的列名列表")
    selected_time_column = param.String(default="", doc="选中的时间列")
    selected_data_column = param.String(default="", doc="选中的数据列(可选)")

    # 服务选择
    selected_loader_name = param.String(default="", doc="选中的加载器名称")
    selected_structurer_name = param.String(default="", doc="选中的结构化器名称")

    # 加载按钮状态
    can_load = param.Boolean(default=False, doc="是否可以执行加载")

    def __init__(self, data_manager: DataManager, **params):
        super().__init__(data_manager=data_manager, **params)

        # 监听相关参数变化以更新按钮状态
        self.param.watch(
            self._update_load_button_state,
            [
                "selected_files",
                "selected_loader_name",
                "selected_structurer_name",
                "selected_time_column",
            ],
        )

    def _update_load_button_state(self, *events):
        """更新加载按钮状态"""
        base_conditions = bool(
            self.selected_files
            and self.selected_loader_name
            and self.selected_structurer_name
        )

        time_column_required = self.available_columns and not self.selected_time_column

        self.can_load = base_conditions and not time_column_required

    def get_loader_services(self) -> Dict[str, Type[DataLoader]]:
        """获取所有可用的加载器服务"""
        return {name: cls for name, cls in DataLoader.get_all_services().items()}

    def get_structurer_services(self) -> Dict[str, Type[DataStructurer]]:
        """获取所有可用的结构化器服务"""
        return {name: cls for name, cls in DataStructurer.get_all_services().items()}

    def select_files(self, file_paths: List[str]):
        """选择文件"""
        self.selected_files = file_paths

        # 如果选择了文件，尝试预览第一个文件
        if file_paths and file_paths[0].lower().endswith(".csv"):
            try:
                # 显示预览并更新可用列
                df_preview = pd.read_csv(file_paths[0], nrows=5)
                self.preview_data = df_preview
                self.available_columns = list(df_preview.columns)

                # 更新状态信息
                self.status_message = (
                    f"已选择 {len(file_paths)} 个文件。请配置加载参数。"
                )
                self.status_type = "info"
            except Exception as e:
                self.preview_data = None
                self.available_columns = []
                self.status_message = f"预览文件失败: {str(e)}"
                self.status_type = "warning"
        else:
            self.preview_data = None
            self.available_columns = []
            if file_paths:
                self.status_message = (
                    f"已选择 {len(file_paths)} 个文件。非CSV文件无法预览。"
                )
                self.status_type = "info"
            else:
                self.status_message = "请选择文件。"
                self.status_type = "info"

    def get_loader_params(self, loader_name: str) -> Dict[str, Dict[str, Any]]:
        """获取指定加载器的参数规范"""
        loaders = self.get_loader_services()
        if loader_name in loaders:
            return loaders[loader_name].get_param_specs()
        return {}

    def get_structurer_params(self, structurer_name: str) -> Dict[str, Dict[str, Any]]:
        """获取指定结构化器的参数规范"""
        structurers = self.get_structurer_services()
        if structurer_name in structurers:
            return structurers[structurer_name].get_param_specs()
        return {}

    def load_and_structure_data(
        self, loader_params: Dict[str, Any], structurer_params: Dict[str, Any]
    ) -> List[str]:
        """加载并结构化数据，返回添加的数据ID列表"""
        if not self.can_load:
            self.status_message = "无法加载，请检查配置。"
            self.status_type = "warning"
            return []

        added_ids = []

        try:
            # 获取选定的服务
            loader_class = DataLoader.get_all_services().get(self.selected_loader_name)
            structurer_class = DataStructurer.get_all_services().get(
                self.selected_structurer_name
            )

            if not loader_class or not structurer_class:
                raise ValueError("未找到选定的加载器或结构化器")

            # 处理每个选定的文件
            for file_path in self.selected_files:
                # 1. 加载文件
                try:
                    df = loader_class.load(file_path, **loader_params)
                    self.status_message = f"已加载文件 {file_path}"
                    self.status_type = "info"
                except Exception as e:
                    self.status_message = f"加载文件 {file_path} 失败: {str(e)}"
                    self.status_type = "danger"
                    continue

                # 2. 结构化数据
                try:
                    # 添加文件名作为基础名称参数
                    import os

                    base_name = os.path.splitext(os.path.basename(file_path))[0]
                    structurer_params["base_name_for_naming"] = base_name

                    # 使用时间列和数据列设置
                    if self.selected_time_column:
                        structurer_params["time_column_name"] = (
                            self.selected_time_column
                        )
                    if (
                        self.selected_data_column
                        and self.selected_data_column != "[自动选择]"
                    ):
                        structurer_params["data_column_name"] = (
                            self.selected_data_column
                        )

                    # 结构化
                    data_container = structurer_class.structure(df, **structurer_params)

                    # 添加到数据管理器
                    data_id = self.data_manager.add_data(data_container)
                    added_ids.append(data_id)

                    self.status_message = f"已加载并结构化文件 {file_path}"
                    self.status_type = "success"
                except Exception as e:
                    self.status_message = f"结构化文件 {file_path} 失败: {str(e)}"
                    self.status_type = "danger"
                    continue

            # 最终状态更新
            if added_ids:
                count = len(added_ids)
                self.status_message = f"成功加载并结构化了 {count} 个文件"
                self.status_type = "success"
            else:
                self.status_message = "没有成功加载任何文件"
                self.status_type = "warning"

            return added_ids

        except Exception as e:
            self.status_message = f"加载过程出错: {str(e)}"
            self.status_type = "danger"
            return []
