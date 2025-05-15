import param
import uuid
import pandas as pd
from typing import Dict, List, Optional, Type, Union, Tuple, cast, TypeAlias, Any
from .data_container import DataContainer

# 导入新的具体容器类型
from .timeseries_container import TimeSeriesContainer
from .image_set_container import ImageSetContainer
import datetime  # 导入 datetime 以便在 get_summary_list 中使用

# 定义支持的数据容器类型联合
SupportedData: TypeAlias = Union[TimeSeriesContainer, ImageSetContainer]
# 如果未来增加 AnalysisResult 等，在这里添加
# SupportedData = Union[TimeSeriesContainer, ImageSetContainer, AnalysisResult]


class DataManager(param.Parameterized):
    """管理应用中所有的数据容器对象。

    通过 param.Parameterized 与 Panel 的响应式系统集成，
    使用 _data_store (param.Dict) 存储数据，并提供添加、获取、删除、
    更新名称、生成摘要列表等方法。
    通过 _data_updated (param.Event) 通知数据变更。
    """

    # 内部存储，键为 ID (str)，值为支持的数据容器实例
    _data_store: Dict[str, SupportedData] = param.Dict(default={}, precedence=-1)

    # 数据更新事件，供视图监听刷新
    _data_updated = param.Event(default=False, precedence=-1)

    def add_data(self, data_container: DataContainer) -> str:
        """向管理器添加新的数据容器，并自动处理名称冲突。

        Args:
            data_container: 要添加的数据容器实例 (必须是 SupportedData 类型)。

        Returns:
            添加成功后数据容器的唯一 ID。

        Raises:
            TypeError: 如果 data_container 不是支持的数据容器类型。
            ValueError: 如果 data_container 的名称无效 (由 DataContainer 的 setter 引发)。
        """
        if not isinstance(data_container, SupportedData):
            raise TypeError(
                f"只能添加支持的数据类型 ({SupportedData})，而不是 {type(data_container).__name__}。"
            )

        dc_to_add = cast(SupportedData, data_container)

        # 处理名称冲突：如果名称已存在，则添加后缀 _1, _2, ...
        new_name = dc_to_add.name
        current_names = {dc.name for dc in self._data_store.values()}
        count = 1
        original_name = new_name
        while new_name in current_names:
            new_name = f"{original_name}_{count}"
            count += 1

        # 如果名称被修改，则更新容器实例的名称
        if new_name != original_name:
            try:
                dc_to_add.name = new_name
            except ValueError as e:
                # DataContainer 的 name.setter 会进行验证
                print(
                    f"警告: 尝试自动重命名数据容器 '{original_name}' 为 '{new_name}' 时失败: {e}"
                )
                # 尽管重命名失败，但可能仍然可以添加（如果原始名称有效且未冲突），或者根据需要抛出异常
                # 这里选择继续添加，但打印警告
                pass

        # 使用 param.Dict 的方式更新以触发 Panel 依赖更新
        # 直接修改 self._data_store[dc_to_add.id] = dc_to_add 不会触发 param 更新
        new_store = self._data_store.copy()
        new_store[dc_to_add.id] = dc_to_add
        self._data_store = new_store

        self._trigger_update()  # 触发数据更新事件
        return dc_to_add.id

    def get_data(self, data_id: str) -> Optional[SupportedData]:
        """根据 ID 获取数据容器。

        Args:
            data_id: 要获取的数据的 ID。

        Returns:
            找到的数据容器实例 (具体子类型)，如果 ID 不存在则返回 None。
        """
        return self._data_store.get(data_id)

    def remove_data(self, data_id: str) -> bool:
        """根据 ID 删除数据容器。

        Args:
            data_id: 要删除的数据的 ID。

        Returns:
            如果成功删除返回 True，如果 ID 不存在返回 False。
        """
        if data_id in self._data_store:
            new_store = self._data_store.copy()
            del new_store[data_id]
            self._data_store = new_store
            self._trigger_update()
            return True
        return False

    def get_all_data(self) -> List[SupportedData]:
        """获取当前管理器中所有数据容器的列表。

        Returns:
            包含所有数据容器对象 (具体子类型) 的列表。
        """
        return list(self._data_store.values())

    def get_data_options(
        self, filter_type: Optional[Type[DataContainer]] = None
    ) -> List[Tuple[str, str]]:
        """获取用于 UI 选择器（如下拉列表）的数据选项列表。

        Args:
            filter_type: (可选) 只包含指定类型的数据容器的基类或具体类
                         (例如 DataContainer, TimeSeriesContainer)。
                         如果为 None，则包含所有类型。

        Returns:
            一个元组列表，每个元组是 (显示名称, 数据 ID)，按名称排序。
            显示名称格式为 "名称 (类型)"。
        """
        options = []
        try:
            # 按名称排序，忽略大小写
            sorted_items = sorted(
                self._data_store.values(), key=lambda dc: dc.name.lower()
            )
        except AttributeError:
            # 处理可能的 name 属性缺失（理论上不应发生）
            print(
                "警告: 获取数据选项时，部分数据项缺少 'name' 属性，将使用未排序列表。"
            )
            sorted_items = list(self._data_store.values())

        for dc in sorted_items:
            # 进行类型过滤
            if filter_type is None or isinstance(dc, filter_type):
                display_name = f"{dc.name} ({dc.data_type})"
                options.append((display_name, dc.id))
        return options

    def get_summary_list(
        self, filter_type: Optional[Type[DataContainer]] = None, sort_key: str = "name"
    ) -> List[Dict[str, Any]]:
        """获取所有（或过滤后的）数据容器的摘要信息列表，通常用于 UI 表格显示。

        Args:
            filter_type: (可选) 要包含的数据类型 (基类或具体类，例如 TimeSeriesContainer)。
            sort_key: (可选) 用于排序摘要字典列表的键 ('name' 或 'created_at')。
                      默认为 'name' (不区分大小写)，'created_at' 会按时间反向排序（最新的在前）。

        Returns:
            一个包含每个数据对象摘要字典的列表。
        """
        summaries = []
        for dc_id, dc in self._data_store.items():
            if filter_type is None or isinstance(dc, filter_type):
                try:
                    # 调用 DataContainer 或其子类的 get_summary 方法
                    summary = dc.get_summary()
                    summaries.append(summary)
                except Exception as e:
                    # 如果获取摘要失败，记录错误并添加基础信息
                    print(
                        f"警告: 获取数据 '{getattr(dc, 'name', '(无名)')}' ({dc_id}) 的摘要时出错: {e}"
                    )
                    summaries.append(
                        {
                            "id": dc_id,
                            "name": getattr(dc, "name", "(无名)"),
                            "type": getattr(dc, "data_type", "(未知类型)"),
                            "created_at": getattr(
                                dc, "created_at", datetime.datetime.min
                            ).strftime("%Y-%m-%d %H:%M:%S"),
                            "status": f"获取摘要错误: {e}",
                        }
                    )

        # 确定排序方向和排序键的处理方式
        reverse_sort = sort_key == "created_at"
        sort_lambda = (
            lambda x: str(x.get(sort_key, "")).lower()
            if sort_key == "name"
            else x.get(sort_key, None)
        )

        try:
            summaries.sort(key=sort_lambda, reverse=reverse_sort)
        except TypeError as e:
            # 处理可能的排序键类型混合问题
            print(f"警告: 按键 '{sort_key}' 排序摘要列表时出错 (可能是类型混合): {e}")
            try:
                # 回退到按名称排序
                summaries.sort(key=lambda x: str(x.get("name", "")).lower())
            except Exception as fallback_e:
                print(f"警告: 回退按名称排序摘要列表也失败: {fallback_e}")
                # 如果连按名称排序都失败，则返回未排序列表

        return summaries

    def update_name(self, data_id: str, new_name: str) -> bool:
        """根据 ID 更新数据对象的名称，并检查名称冲突。

        Args:
            data_id: 要更新的数据的 ID。
            new_name: 新的名称。

        Returns:
            如果更新成功返回 True。
            如果 ID 不存在、新名称无效或新名称与其他现有数据冲突，则返回 False 并打印警告。
        """
        data_object = self.get_data(data_id)
        clean_new_name = new_name.strip()

        if not data_object:
            print(f"警告: 尝试更新不存在的数据 ID: {data_id}。")
            return False
        if not clean_new_name:
            print(f"警告: 数据 ID {data_id} 的新名称不能为空。")
            return False
        # 如果新名称与旧名称相同，视为成功，无需操作
        if clean_new_name == data_object.name:
            return True

        # 检查新名称是否与 *其他* 数据项冲突
        current_names = {
            dc.name for id, dc in self._data_store.items() if id != data_id
        }
        if clean_new_name in current_names:
            print(
                f"警告: 名称 '{clean_new_name}' 已被其他数据项使用，无法重命名 ID {data_id}。"
            )
            return False

        try:
            # 尝试更新 DataContainer 对象的名称 (会触发其内部验证)
            data_object.name = clean_new_name
            self._trigger_update()  # 触发更新以通知 UI
            return True
        except ValueError as e:
            # 捕获 DataContainer setter 可能抛出的 ValueError
            print(f"警告: 尝试为 ID {data_id} 设置名称 '{clean_new_name}' 时出错: {e}")
            return False

    def _trigger_update(self):
        """触发 _data_updated 事件，通知监听者数据已更改。"""
        self.param.trigger("_data_updated")
