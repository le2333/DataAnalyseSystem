# core/workflow/runner.py
import logging
from typing import Dict, Any, Optional, Tuple, Union
import polars as pl
from prefect import flow, task, get_run_logger
from prefect.futures import PrefectFuture
# SequentialTaskRunner 是 Prefect 2 中未指定并发运行器时的默认设置。
# 移除导入: from prefect.task_runners import SequentialTaskRunner

from .workflow import Workflow
from core.node import BaseNode

logger = logging.getLogger(__name__)

# --- 使用最终版本的 run_node_task --- 
@task(name="node-runner-{node_id}")
def run_node_task(node: BaseNode, node_id: str, upstream_connections: Dict[str, Tuple[PrefectFuture, str]]) -> Dict[str, pl.DataFrame]:
    """
    一个 Prefect task，用于执行单个 BaseNode 的 run 方法。

    Args:
        node: 要执行的 BaseNode 实例。
        node_id: 节点的 ID (主要用于 task 名称)。
        upstream_connections: 一个字典，键是当前任务期望的输入端口名，
                              值是元组 (产生输入的上游任务的 PrefectFuture, 上游任务输出端口名)。

    Returns:
        节点执行产生的输出 DataFrame 字典。
    """
    prefect_logger = get_run_logger()
    prefect_logger.info(f"==> [任务开始] 执行节点: {node.node_type} (ID: {node_id}) 参数: {node.params}")

    inputs: Dict[str, pl.DataFrame] = {}
    try:
        # 从 Futures 中获取实际的输入数据
        for input_port, (upstream_future, source_port) in upstream_connections.items():
            # upstream_future.result() 会阻塞，直到上游任务完成并返回结果
            upstream_output_dict = upstream_future.result() # 获取上游任务的整个输出字典
            prefect_logger.debug(f"    节点 {node_id}: 正在从上游任务 '{upstream_future.name}' (端口 '{source_port}') 获取输入 '{input_port}'")

            if not isinstance(upstream_output_dict, dict):
                 msg = f"节点 {node_id}: 上游任务 {upstream_future.name} 返回的不是预期的字典，而是 {type(upstream_output_dict)}"
                 prefect_logger.error(msg)
                 raise TypeError(msg)
            
            if source_port not in upstream_output_dict:
                # 检查一下是否是 Polars DataFrame，如果是，可能上游只有一个输出且没用字典包装
                if len(upstream_output_dict) == 1 and isinstance(list(upstream_output_dict.values())[0], pl.DataFrame):
                    # 假设只有一个输出，直接使用
                    prefect_logger.warning(f"    节点 {node_id}: 上游任务 {upstream_future.name} 的输出字典中未直接找到端口 '{source_port}'，但发现单个 DataFrame 输出，将尝试使用它。建议上游节点始终返回端口名映射的字典。")
                    result_data = list(upstream_output_dict.values())[0]
                else:
                    msg = f"节点 {node_id}: 在上游任务 {upstream_future.name} 的输出字典 {list(upstream_output_dict.keys())} 中未找到期望的端口 '{source_port}'"
                    prefect_logger.error(msg)
                    raise KeyError(msg)
            else:
               result_data = upstream_output_dict[source_port]
            
            # 类型检查移到这里，确保 result_data 存在且类型正确
            expected_input_type = node.define_inputs().get(input_port)
            if not isinstance(result_data, pl.DataFrame):
                 # 简单处理 Optional[pl.DataFrame] 的情况
                 is_optional = hasattr(expected_input_type, '__origin__') and expected_input_type.__origin__ is Union and type(None) in expected_input_type.__args__
                 if result_data is None and is_optional:
                     prefect_logger.debug(f"    节点 {node_id}: 输入端口 '{input_port}' 接收到合法的 None 值。")
                     inputs[input_port] = None # 传递 None
                     continue # 跳过下面的 DataFrame 检查
                 else:    
                     msg = f"节点 {node_id}: 从上游任务 {upstream_future.name} 的端口 '{source_port}' 接收到的数据类型 ({type(result_data)}) 与期望的 Polars DataFrame (或允许的None) 不符。"
                     prefect_logger.error(msg)
                     raise TypeError(msg)
            inputs[input_port] = result_data

        prefect_logger.info(f"    节点 {node_id}: 接收到所有输入: {list(inputs.keys())}")

        # 验证输入 (可选但推荐)
        node.validate_inputs(inputs)
        prefect_logger.debug(f"    节点 {node_id}: 输入验证通过。")

        # 执行节点的核心逻辑
        outputs = node.run(inputs)
        prefect_logger.info(f"    节点 {node_id}: 执行完成，输出端口: {list(outputs.keys()) if isinstance(outputs, dict) else '非字典输出'}")

        # --- 输出处理和验证 --- 
        if not isinstance(outputs, dict):
             # 如果只有一个输出且是 DF，尝试包装成字典
             if isinstance(outputs, pl.DataFrame):
                 defined_outputs = node.define_outputs()
                 if len(defined_outputs) == 1:
                     output_port_name = list(defined_outputs.keys())[0]
                     prefect_logger.warning(f"    节点 {node_id}: run() 方法直接返回了一个 DataFrame 而不是字典。将自动包装到端口 '{output_port_name}' 中。建议 run() 方法始终返回字典。")
                     outputs = {output_port_name: outputs}
                 else:
                     msg = f"节点 {node_id}: run() 方法返回了一个 DataFrame，但节点定义了多个或零个输出端口 ({list(defined_outputs.keys())})。无法确定端口名称。"
                     prefect_logger.error(msg)
                     raise TypeError(msg)
             # 允许返回 None 或空字典吗？
             elif outputs is None:
                 prefect_logger.info(f"    节点 {node_id}: run() 方法返回 None，将其视为空输出字典。")
                 outputs = {} # 转换成空字典，避免下游出错
             else:
                 msg = f"节点 {node_id}: run() 方法返回的不是预期的字典或 DataFrame，而是 {type(outputs)}"
                 prefect_logger.error(msg)
                 raise TypeError(msg)
        
        # 验证输出字典中的类型
        expected_outputs_def = node.define_outputs()
        for output_port, df in outputs.items():
            if output_port not in expected_outputs_def:
                 prefect_logger.warning(f"    节点 {node_id}: 产生未在 define_outputs 中定义的输出端口 '{output_port}'")
            # 检查 df 是否为 DataFrame，除非预期类型允许 None
            elif not isinstance(df, pl.DataFrame):
                 expected_type = expected_outputs_def.get(output_port)
                 # 简化的 None 类型检查，实际可能需要更复杂的 typing.get_origin等
                 is_optional = hasattr(expected_type, '__origin__') and expected_type.__origin__ is Union and type(None) in expected_type.__args__
                 if df is None and is_optional:
                      pass # 允许 None
                 else:
                     prefect_logger.error(f"    节点 {node_id}: 输出端口 '{output_port}' 的类型不是 Polars DataFrame (或允许的 None)，而是 {type(df)}")
                     # 可能需要根据策略决定是否抛出异常

        prefect_logger.debug(f"    节点 {node_id}: 输出验证完成。返回: {list(outputs.keys())}")
        prefect_logger.info(f"<== [任务成功] 节点 {node_id} 执行成功。")
        return outputs

    except Exception as e:
        prefect_logger.error(f"<== [任务失败] 执行节点 {node_id} (类型: {node.node_type}) 失败: {e}", exc_info=True)
        raise # 让异常冒泡，Prefect 会处理任务失败状态


@flow(name="workflow-runner") # 移除 task_runner 参数以进行默认顺序执行
def run_workflow_flow(workflow: Workflow):
    """
    一个 Prefect flow，用于执行整个 Workflow。

    Args:
        workflow: 要执行的 Workflow 实例。
    """
    prefect_logger = get_run_logger()
    prefect_logger.info(f"---- [流程开始] 开始执行工作流: {workflow.name} ----")

    if not workflow.validate():
        msg = f"工作流 '{workflow.name}' 验证失败，执行中止。"
        prefect_logger.error(msg)
        raise ValueError(msg)

    # 存储每个节点任务的 Future，键是 node_id，值是该节点任务的 Future
    node_futures: Dict[str, PrefectFuture] = {} 

    # 按照拓扑顺序迭代节点，确保依赖关系正确
    try:
        sorted_nodes = workflow.get_topological_order()
        prefect_logger.info(f"节点执行顺序 (拓扑排序): {sorted_nodes}")
    except ValueError as e:
        msg = f"无法获取工作流 '{workflow.name}' 的拓扑排序: {e}"
        prefect_logger.error(msg)
        raise ValueError(msg)

    # --- 动态构建并提交任务 --- 
    all_tasks_submitted = True
    for node_id in sorted_nodes:
        node_instance = workflow.get_node(node_id)
        prefect_logger.info(f"  -> 准备节点: {node_id} (类型: {node_instance.node_type})")

        # 构建 upstream_connections
        upstream_connections: Dict[str, Tuple[PrefectFuture, str]] = {}
        possible_to_run = True
        predecessors = workflow.get_node_predecessors(node_id)
        for pred_id, source_port, target_port in predecessors:
             if pred_id not in node_futures: # node_futures 现在存 {node_id: task_future}
                 msg = f"逻辑错误：前驱节点 {pred_id} 的 Future 在处理节点 {node_id} 时不可用。检查拓扑排序或流程逻辑。"
                 prefect_logger.error(msg)
                 possible_to_run = False
                 break # 无法继续处理此节点
             upstream_task_future = node_futures[pred_id]
             upstream_connections[target_port] = (upstream_task_future, source_port)
             prefect_logger.debug(f"     节点 {node_id}: 添加依赖 {target_port} <- {pred_id}.{source_port}")
        
        if not possible_to_run:
             all_tasks_submitted = False
             prefect_logger.error(f"  -> 节点 {node_id} 因前驱节点 Future 缺失而无法提交。")
             continue # 跳过此节点

        # 提交任务，传递连接信息
        try:
            current_task_future = run_node_task.submit(
                 node=node_instance,
                 node_id=node_id,
                 upstream_connections=upstream_connections, # 传递修改后的参数
                 task_run_name=f"run-{node_id.replace('_','-')}" # 自定义 task run 名称
            )
            # 存储当前任务的 Future
            node_futures[node_id] = current_task_future
            prefect_logger.info(f"  -> 成功提交任务: {current_task_future.name} for node {node_id}")
        except Exception as e:
            prefect_logger.error(f"  -> 提交节点 {node_id} 任务时出错: {e}", exc_info=True)
            all_tasks_submitted = False
            # 是否需要停止整个流程？取决于策略
            break # 暂时停止

    if not all_tasks_submitted:
         msg = f"工作流 '{workflow.name}' 部分任务未能成功提交，流程可能未完整执行。"
         prefect_logger.error(msg)
         # 可以选择在这里 raise error
    else:
         prefect_logger.info(f"---- 所有节点任务已提交 for workflow {workflow.name} ----")
    
    # Flow 会自动等待所有被 submit 的 task 完成（或失败）
    # 你可以在这里添加代码来处理最终结果，如果需要的话
    # final_node_ids = [n for n in sorted_nodes if workflow.graph.out_degree(n) == 0]
    # final_results = {}
    # for final_id in final_node_ids:
    #     if final_id in node_futures:
    #         try:
    #             final_results[final_id] = node_futures[final_id].result()
    #             prefect_logger.info(f"获取到最终节点 {final_id} 的结果: {list(final_results[final_id].keys())}")
    #         except Exception as e:
    #             prefect_logger.error(f"获取最终节点 {final_id} 结果时出错: {e}")
    # return final_results # 返回最终结果字典


class WorkflowRunner:
    """封装工作流执行逻辑。"""

    def __init__(self):
        # 可以添加配置，例如选择不同的 TaskRunner 等
        pass

    def run(self, workflow: Workflow) -> Optional[Dict[str, Any]]: # 返回值类型可能需要调整
        """
        同步执行工作流。

        Args:
            workflow: 要执行的 Workflow 实例。

        Returns:
            # Prefect 2.x flow 调用不直接返回 State 对象，除非使用 .run() 方法
            # 我们可以让 flow 返回最终结果，或者这里只记录日志
            目前 run_workflow_flow 没有显式返回，所以这里返回 None。
            如果 flow 返回结果，这里需要调整。
        """
        logger.info(f"准备使用 Prefect 运行工作流: {workflow.name}")
        # 直接调用 flow 函数会同步执行它
        try:
            # run_workflow_flow 是 @flow 装饰的函数，直接调用会执行
            run_workflow_flow(workflow) # type: ignore # 它没有显式返回 State
            logger.info(f"工作流 '{workflow.name}' 同步执行流程已完成 (请检查 Prefect 日志了解任务状态)。")
            # 如果 flow 有返回值，可以在这里接收并返回
            return None # 暂时返回 None
        except Exception as e:
            logger.error(f"执行工作流 '{workflow.name}' 时发生顶层错误: {e}", exc_info=True)
            # 根据需要决定是否重新抛出异常
            raise

    # 异步运行暂时移除，因为 Prefect 2 的 run() 和直接调用行为有所不同
    # 如果需要异步，需要使用 Prefect Client 或其他部署方式
    # async def run_async(self, workflow: Workflow) -> Any:
    #     ... 