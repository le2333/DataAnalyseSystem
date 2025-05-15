import param
from typing import List, Dict, Any, Optional
from model.data_manager import DataManager
from services.base import DataPreprocessor


class ProcessViewModel(param.Parameterized):
    """数据处理视图模型，处理数据预处理和变换"""

    # 持有数据管理器模型
    data_manager = param.ClassSelector(class_=DataManager)

    # UI状态和数据
    selected_data_ids = param.List(default=[], doc="选中的数据ID列表")
    status_message = param.String(default="", doc="状态信息")
    status_type = param.String(
        default="info", doc="状态类型：info, success, warning, danger"
    )
    status_visible = param.Boolean(default=False, doc="状态是否可见")

    # 服务选择
    selected_service_name = param.String(default="", doc="选中的预处理服务名称")

    # 处理按钮状态
    can_process = param.Boolean(default=False, doc="是否可以执行处理")

    def __init__(self, data_manager: DataManager, **params):
        super().__init__(data_manager=data_manager, **params)

        # 监听相关参数变化以更新按钮状态
        self.param.watch(
            self._update_process_button_state,
            ["selected_data_ids", "selected_service_name"],
        )

    def _update_process_button_state(self, *events):
        """更新处理按钮状态"""
        self.can_process = bool(self.selected_service_name and self.selected_data_ids)

    def get_preprocessor_services(self) -> Dict[str, Any]:
        """获取所有可用的预处理服务"""
        return {name: cls for name, cls in DataPreprocessor.get_all_services().items()}

    def select_data(self, data_ids: List[str]):
        """选择数据项"""
        self.selected_data_ids = data_ids

    def get_selected_data_info(self) -> str:
        """获取选中数据的信息描述"""
        if not self.selected_data_ids:
            return "**当前未选择数据**"

        info_str = f"**选定数据 ({len(self.selected_data_ids)} 项):**\n"
        names = []
        types = set()
        for data_id in self.selected_data_ids:
            dc = self.data_manager.get_data(data_id)
            if dc:
                names.append(f"- {dc.name} ({dc.data_type})")
                types.add(dc.data_type)
            else:
                names.append(f"- ID: {data_id} (未找到)")
        info_str += "\n".join(names)
        return info_str

    def get_service_params(self, service_name: str) -> Dict[str, Dict[str, Any]]:
        """获取指定预处理服务的参数规范"""
        services = self.get_preprocessor_services()
        if service_name in services:
            return services[service_name].get_param_specs()
        return {}

    def process_data(self, service_params: Dict[str, Any]) -> List[str]:
        """执行数据处理，返回处理结果的数据ID列表"""
        if not self.can_process:
            self.set_status("无法执行处理，请检查配置", "warning")
            return []

        added_ids = []

        try:
            # 获取选定的服务
            preprocessor_class = DataPreprocessor.get_all_services().get(
                self.selected_service_name
            )

            if not preprocessor_class:
                raise ValueError("未找到选定的预处理服务")

            # 获取选中的数据容器
            input_data = []
            for data_id in self.selected_data_ids:
                data = self.data_manager.get_data(data_id)
                if data:
                    input_data.append(data)

            if not input_data:
                raise ValueError("未找到选中的数据")

            # 执行预处理
            result_data = preprocessor_class.preprocess(input_data, **service_params)

            # 结果可能是单个数据容器或容器列表
            if isinstance(result_data, list):
                for data in result_data:
                    data_id = self.data_manager.add_data(data)
                    added_ids.append(data_id)
            else:
                data_id = self.data_manager.add_data(result_data)
                added_ids.append(data_id)

            # 更新状态
            self.set_status(f"处理成功，生成了 {len(added_ids)} 个结果", "success")

            return added_ids

        except Exception as e:
            self.set_status(f"处理失败: {str(e)}", "danger")
            return []

    def set_status(self, message: str, status_type: str = "info"):
        """设置状态信息"""
        self.status_message = message
        self.status_type = status_type
        self.status_visible = bool(message)
