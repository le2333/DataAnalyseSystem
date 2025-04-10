PREPROCESSORS = {}
ANALYZERS = {}
VISUALIZERS = {}
LOADERS = {} # 新增加载器注册表
STRUCTURERS = {} # 新增：数据结构化服务注册表

def register_service(registry: dict, name: str, function: callable, input_type: type | None, output_type: type, params_spec: dict | None = None):
    """
    通用注册函数，用于向指定的注册表添加服务。

    Args:
        registry: 目标注册表 (e.g., PREPROCESSORS, VISUALIZERS)。
        name: 服务的用户友好名称。
        function: 实现服务功能的函数或方法。
        input_type: 服务期望的输入 DataContainer 类型 (或 None，如加载器)。
        output_type: 服务返回的 DataContainer 类型。
        params_spec: (可选) 服务所需参数的规范，用于动态生成UI。
                     格式: {'param_name': {'type': 'integer'/'string'/'float'/'boolean', 'default': value, 'label': '用户标签'}}
    """
    if name in registry:
        print(f"警告: 服务名称 '{name}' 已存在于注册表中，将被覆盖。")

    registry[name] = {
        "function": function,
        "input_type": input_type,
        "output_type": output_type,
        "params": params_spec if params_spec is not None else {}
    } 