import panel as pn
import param
import logging

from .base_panel import BasePanelComponent
from viewmodels.workflow_viewmodel import WorkflowViewModel # 需要类型提示

logger = logging.getLogger(__name__)

class NodeConfigPanel(BasePanelComponent):
    """
    负责显示当前选中节点配置面板的自治组件。
    """
    # 内部状态，持有实际要显示的 Panel 内容
    _content = param.Parameter(default=pn.Column("选择一个节点以查看其配置", sizing_mode='stretch_width', styles={'padding': '10px'}))

    def __init__(self, view_model: WorkflowViewModel, **params):
        # 在 super().__init__ 之前设置 _content，因为它在 panel() 中使用
        # default 值会被 __init__ 中的逻辑覆盖
        params['view_model'] = view_model # 确保 view_model 在 params 中
        super().__init__(**params)

        # 首次初始化时更新内容
        self._update_content()

        # 监听 selected_node_id 的变化
        self.view_model.param.watch(self._selected_node_changed_callback, 'selected_node_id')
        # 当模型本身被替换时 (加载新工作流), 也需要重新获取节点 (如果之前有选中)
        self.view_model.param.watch(self._selected_node_changed_callback, 'model')

    def _selected_node_changed_callback(self, event=None):
        """当 view_model.selected_node_id 或 view_model.model 改变时调用。"""
        logger.debug(f"NodeConfigPanel: 检测到变化 (事件: {event.name if event else 'init'})，正在更新配置面板内容...")
        self._update_content()

    def _update_content(self):
        """根据当前 view_model.selected_node_id 获取并更新配置面板内容。"""
        node_id = self.view_model.selected_node_id
        new_panel_content = None
        if node_id and self.view_model.model:
            try:
                node = self.view_model.model.get_node(node_id)
                if hasattr(node, 'get_config_panel'):
                    logger.info(f"NodeConfigPanel: 正在获取节点 '{node_id}' 的配置面板...")
                    # 调用节点自身的配置面板生成方法
                    config_panel = node.get_config_panel() # BaseNode 确保返回 Panel 对象
                    logger.info(f"NodeConfigPanel: 获取到类型为 {type(config_panel)} 的配置面板")
                    new_panel_content = config_panel
                else:
                    # BaseNode 应该总是有 get_config_panel
                    logger.error(f"NodeConfigPanel: 节点 '{node_id}' 缺少 get_config_panel 方法！")
                    new_panel_content = pn.pane.Alert(f"节点 '{node_id}' 缺少配置面板方法！", alert_type='danger')
            except KeyError:
                logger.warning(f"NodeConfigPanel: 更新配置面板时未找到节点 '{node_id}'。")
                new_panel_content = pn.pane.Alert(f"错误：找不到选中的节点 '{node_id}'", alert_type='warning')
            except Exception as e:
                logger.error(f"NodeConfigPanel: 获取/构建节点 '{node_id}' 的配置面板时出错: {e}", exc_info=True)
                new_panel_content = pn.pane.Alert(f"加载节点 '{node_id}' 配置时出错: {e}", alert_type='danger')
        else:
            logger.info("NodeConfigPanel: 未选择节点，设置默认消息。")
            new_panel_content = pn.Column("选择一个节点以查看其配置", sizing_mode='stretch_width', styles={'padding': '10px'})

        # 更新内部持有的 Panel 对象
        # 使用 self.param.update 来修改 Parameter 的值
        # 不能直接 self._content = new_panel_content 因为它是 Parameter
        self.param.update(_content=new_panel_content)
        logger.debug("NodeConfigPanel: 内容已更新。")

    def panel(self) -> pn.viewable.Viewable:
        """返回包含当前节点配置内容的 Panel 对象。"""
        # 返回 _content 参数本身，Panel 会自动处理更新
        # 或者返回一个动态函数包裹的 pn.panel(self._content)，效果类似
        return pn.panel(self._content) 