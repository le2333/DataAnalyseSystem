from typing import Any, Dict, Optional
from prefect import task, Flow, get_run_logger
import inspect

class BaseNode:
    """时序分析处理节点基类
    
    每个节点都可以有参数、输入和输出，并可以直接转换为Prefect任务
    """
    
    def __init__(self, **params):
        """
        初始化节点并存储参数
        
        Args:
            **params: 节点参数字典
        """
        self.params = params
        self.name = params.get("name", self.__class__.__name__)
    
    def process(self, *args, **kwargs) -> Any:
        """
        节点核心处理逻辑，子类必须实现此方法
        
        Returns:
            处理结果
        """
        raise NotImplementedError("子类必须实现process方法")
    
    def as_task(self, **task_kwargs):
        """
        将节点转换为Prefect任务
        
        Args:
            **task_kwargs: 传递给Prefect task装饰器的额外参数
            
        Returns:
            已装饰的task函数
        """
        @task(name=self.name, **task_kwargs)
        def _task_wrapper(*args, **kwargs):
            logger = get_run_logger()
            logger.info(f"开始执行节点: {self.name}")
            
            # 合并初始化参数和运行时参数
            run_params = self.params.copy()
            run_params.update(kwargs)

            # 获取实际 process 方法的参数签名
            process_signature = inspect.signature(self.process)
            valid_process_args = {k: v for k, v in run_params.items() if k in process_signature.parameters}
            
            try:
                # 只传递 process 方法实际接受的参数
                result = self.process(*args, **valid_process_args)
                logger.info(f"节点 {self.name} 执行完成")
                return result
            except Exception as e:
                logger.error(f"节点 {self.name} 执行失败: {str(e)}")
                raise
        
        return _task_wrapper
    
    def get_parameters(self) -> Dict[str, Dict[str, Any]]:
        """
        获取节点参数信息，用于UI显示和配置
        
        Returns:
            参数定义字典
        """
        # 获取process方法的参数签名
        signature = inspect.signature(self.process)
        parameters = {}
        
        for name, param in signature.parameters.items():
            if name != 'self' and name != 'args':
                # 检查参数是否有默认值和类型注解
                has_default = param.default is not inspect.Parameter.empty
                param_type = param.annotation if param.annotation is not inspect.Parameter.empty else None
                
                parameters[name] = {
                    "type": str(param_type.__name__) if param_type else "any",
                    "default": param.default if has_default else None,
                    "required": not has_default,
                    "current_value": self.params.get(name, param.default if has_default else None)
                }
        
        return parameters