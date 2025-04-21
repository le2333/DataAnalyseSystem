import numpy as np
from .data_container import DataContainer
from typing import Any, Optional, Dict, List

class ImageSetContainer(DataContainer):
    """存储图像集数据的容器。

    继承自 DataContainer，内部数据 (_data) 是一个字典，
    键是图像的标识符 (str)，值是 NumPy 数组表示的图像。
    """

    DATA_TYPE = "image_set"

    def __init__(self, 
                 image_dict: Dict[str, np.ndarray], 
                 name: str, 
                 source_ids: Optional[List[str]] = None, 
                 operation_info: Optional[Dict[str, Any]] = None):
        """初始化图像集数据容器。

        Args:
            image_dict: 包含图像数据的字典。键是图像标识符 (str)，值是 NumPy 数组。
            name: 用户可读的数据集名称。
            source_ids: (可选) 生成此数据的源数据 ID 列表。
            operation_info: (可选) 生成此数据的操作信息。

        Raises:
            TypeError: 如果 image_dict 不是字典，或者其值包含非 NumPy 数组。
            ValueError: 如果 image_dict 为空。
        """
        if not isinstance(image_dict, dict):
            raise TypeError("图像数据必须以字典形式提供。")
        if not image_dict: 
             raise ValueError("图像字典不能为空。")
             
        # 验证字典中的值是否都是 NumPy 数组
        for key, value in image_dict.items():
            if not isinstance(value, np.ndarray):
                raise TypeError(f"图像字典中的值必须是 NumPy 数组，但键 '{key}' 的值类型为 {type(value).__name__}。")

        # 调用基类构造函数
        super().__init__(image_dict, name, self.DATA_TYPE, source_ids, operation_info)

    @property
    def images(self) -> Dict[str, np.ndarray]:
        """以字典形式返回包含的所有图像数据。
        
        键是图像标识符 (str)，值是 NumPy 数组。
        """
        # __init__ 保证了 self._data 是字典
        assert isinstance(self._data, dict)
        return self._data

    def get_image_ids(self) -> List[str]:
        """获取此图像集中所有图像的标识符列表。"""
        # self.images 保证返回字典
        return list(self.images.keys())

    def get_image(self, image_id: str) -> Optional[np.ndarray]:
        """根据 ID 获取单个图像。

        Args:
            image_id: 要获取的图像的标识符。

        Returns:
            对应的 NumPy 数组表示的图像，如果 ID 不存在则返回 None。
        """
        # self.images.get() 处理了 ID 不存在的情况
        return self.images.get(image_id)

    def get_summary(self) -> Dict[str, Any]:
        """获取图像集的摘要信息（覆盖基类方法）。

        在基类摘要的基础上，添加图像数量和形状信息。

        Returns:
            包含图像集特有信息的摘要字典。
        """
        # 调用基类方法获取基础摘要信息
        summary = super().get_summary()
        
        image_count = 0
        image_shapes_set = set() # 使用集合存储遇到的不同形状
        first_image_shape_str = "N/A"
        all_shapes_same = True

        image_data = self.images # 直接访问属性
        if image_data:
            image_count = len(image_data)
            # 获取第一个图像的形状（如果存在）
            first_image = next(iter(image_data.values()), None)
            if first_image is not None:
                 # 安全地获取形状，转换为字符串
                 first_image_shape = getattr(first_image, 'shape', None)
                 first_image_shape_str = str(first_image_shape) if first_image_shape is not None else '未知形状'
                 image_shapes_set.add(first_image_shape) # 添加形状元组到集合
                 
                 # 优化：如果只有一个图像，形状肯定是一致的
                 if image_count > 1:
                     # 检查所有图像形状是否与第一个一致
                     for img in image_data.values():
                         current_shape = getattr(img, 'shape', None)
                         image_shapes_set.add(current_shape) # 添加到集合以统计不同形状数量
                         if all_shapes_same and current_shape != first_image_shape:
                             all_shapes_same = False
                             # 如果已经发现不一致，无需再比较后续形状是否与第一个相同
                             # 但仍然需要继续迭代以收集所有不同的形状到 set 中
            
        # 格式化形状信息用于显示
        if image_count == 0:
            shape_display = "N/A (空集)"
        elif all_shapes_same:
            shape_display = first_image_shape_str
        else:
            # 计算有效形状的数量（排除 None）
            valid_shape_count = len([s for s in image_shapes_set if s is not None])
            if valid_shape_count > 1:
                 shape_display = f"{valid_shape_count} 种不同形状"
            elif valid_shape_count == 1:
                 # 如果只有一种有效形状，即使集合里可能有 None，也显示该形状
                 valid_shape = next(s for s in image_shapes_set if s is not None)
                 shape_display = str(valid_shape)
            else: # 集合中只有 None 或空集合
                 shape_display = "未知形状"

        # 更新摘要字典
        summary.update({
            'image_count': image_count,
            'image_shape': shape_display,
            # 可以考虑添加 dtype 信息摘要，但可能比较复杂 (例如混合类型)
            # 'dtype': ... 
        })
        # 从基类摘要中移除不适用于图像集的列信息
        summary.pop('columns', None)
        summary.pop('start_time', None)
        summary.pop('end_time', None)
        summary.pop('index_type', None)
        
        return summary 