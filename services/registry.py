from typing import List, Dict, Any, Callable, Type, Union, Optional, TypeAlias

# --- 服务注册表定义 ---
# 使用类型别名提高可读性
ServiceInfo: TypeAlias = Dict[str, Any]
ServiceRegistry: TypeAlias = Dict[str, ServiceInfo]

# 各类服务的注册表
PREPROCESSORS: ServiceRegistry = {}
ANALYZERS: ServiceRegistry = {}
VISUALIZERS: ServiceRegistry = {}
LOADERS: ServiceRegistry = {} # 文件加载服务
STRUCTURERS: ServiceRegistry = {} # 数据结构化服务

# --- 服务注册函数 ---

def register_service(
    registry: ServiceRegistry,
    name: str,
    function: Callable[..., Any], # 更通用的 Callable 类型提示
    input_type: Optional[Union[Type, List[Type]]] = None,
    output_type: Optional[Union[Type, List[Type]]] = None,
    params_spec: Optional[Dict[str, Dict[str, Any]]] = None,
    accepts_list: bool = False,
    input_param_name: Optional[str] = None
) -> None:
    """通用服务注册函数。

    将服务及其元数据添加到指定的注册表字典中。
    如果服务名称已存在，将覆盖现有条目并打印警告。

    Args:
        registry (ServiceRegistry): 目标注册表字典 (例如 PREPROCESSORS)。
        name (str): 服务的用户友好名称，将在 UI 中显示。
        function (Callable): 实现服务功能的函数或方法。
        input_type (Optional[Union[Type, List[Type]]]): 
            服务期望的主要输入数据类型。可以是单个类型 (如 pd.DataFrame, 
            TimeSeriesContainer)，类型列表 (用于多输入服务)，或 None 
            (如果服务不直接处理特定类型数据或处理方式复杂)。
            用于类型检查和 UI 适配。
        output_type (Optional[Union[Type, List[Type]]]): 
            服务返回的主要结果类型。可以是单个类型、类型列表或 None。
            用于类型检查和结果处理。
        params_spec (Optional[Dict[str, Dict[str, Any]]]): 
            服务所需参数的规范字典，用于动态生成 UI。
            格式: {
                '参数名': {
                    'type': '类型字符串', 
                    'label': 'UI标签', 
                    'default': 默认值, 
                    'options': [选项列表] (可选, 仅用于 select/multiselect), 
                    'min': 最小值 (可选, 用于 numeric), 
                    'max': 最大值 (可选, 用于 numeric), 
                    'step': 步长 (可选, 用于 numeric)
                }
            }
            支持的类型字符串: 'integer', 'float', 'string', 'boolean', 
            'select', 'multiselect', 'file' (未来可能支持)。
        accepts_list (bool): 指示服务函数是否期望接收对象列表作为其主要输入参数
                             (由 input_param_name 指定)，而不是单个对象。
                             默认为 False。
        input_param_name (Optional[str]): 服务函数接收主要输入数据 (单个对象或列表) 
                                      的关键字参数名称。
                                      如果为 None，调用者 (如控制器) 可能需要根据
                                      accepts_list 标志或函数签名推断或使用默认值。
    """
    if name in registry:
        print(f"警告: 服务名称 '{name}' 已存在于注册表 {registry.__name__ if hasattr(registry, '__name__') else type(registry)} 中，将被新服务覆盖。")

    registry[name] = {
        "function": function,
        "input_type": input_type,
        "output_type": output_type,
        "params": params_spec if params_spec is not None else {},
        "accepts_list": accepts_list,
        "input_param_name": input_param_name
    } 