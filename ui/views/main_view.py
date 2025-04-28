# ui/views/main_view.py
import panel as pn
import param
import logging
import uuid
from pathlib import Path
import json

# --- Standard Imports ---
# Assuming running via main.py from the root directory
from core.workflow import Workflow, WorkflowRunner
from core.node import NodeRegistry
from ui.components.node_palette import NodePalette
from ui.components.node_config import NodeConfigPanel
from ui.components.workflow_canvas import WorkflowCanvas


pn.extension(notifications=True) # Enable notifications for user feedback

logger = logging.getLogger(__name__)

class MainView(param.Parameterized):
    """
    主应用程序视图，整合所有 UI 组件和核心逻辑。
    """

    # --- Core Objects ---
    # 定义 Parameter，但不在此处设置复杂的默认实例
    workflow = param.Parameter(default=None, constant=False)
    runner = param.Parameter(default=None, constant=False)

    # --- UI Components / Widgets ---
    # 定义为实例属性，在 __init__ 中创建

    # --- Status Text ---
    status_text = param.Parameter(default=pn.pane.Markdown("状态：就绪", align='center'))


    def __init__(self, **params):
        # --- Set default core objects BEFORE super().__init__ ---
        # Check if workflow/runner were passed in params, otherwise use default
        if 'workflow' not in params:
            params['workflow'] = Workflow(name="New Workflow")
        if 'runner' not in params:
            params['runner'] = WorkflowRunner()
            
        # --- Initialize Components and Widgets ---
        # 这些是视图的组成部分，不是配置参数，所以设为普通实例属性
        self.node_palette = NodePalette()
        self.node_config = NodeConfigPanel()
        self.workflow_canvas = WorkflowCanvas()

        self.run_button = pn.widgets.Button(name="▶️ 运行", button_type="success", width=80, align='center')
        self.save_button = pn.widgets.Button(name="💾 保存", button_type="primary", width=80, align='center')
        self.load_button = pn.widgets.Button(name="📂 加载", button_type="default", width=80, align='center')
        self.clear_button = pn.widgets.Button(name="🗑️ 清空", button_type="danger", width=80, align='center')
        self.delete_node_button = pn.widgets.Button(name="❌ 删除选中节点", button_type="warning", width=150, align='center', disabled=True)
        self.file_input = pn.widgets.FileInput(accept=".json", multiple=False, visible=False)

        # --- Call super().__init__ AFTER defaults are set and components initialized ---
        # This assigns workflow and runner from params (either passed in or default)
        # to self.workflow and self.runner via param magic.
        super().__init__(**params)

        # --- Connect Components (using self.workflow which is now set) ---
        self.node_config.workflow = self.workflow
        self.workflow_canvas.workflow = self.workflow

        # --- Bind Interactions ---
        self.node_palette.param.watch(self._add_node_from_palette, 'selected_node_type')
        self.workflow_canvas.param.watch(self._update_config_on_selection, 'selected_node_id')
        self.run_button.on_click(self._run_workflow)
        self.save_button.on_click(self._trigger_save_workflow)
        self.load_button.on_click(self._trigger_load_workflow)
        self.clear_button.on_click(self._clear_workflow)
        self.delete_node_button.on_click(self._delete_selected_node)
        self.file_input.param.watch(self._handle_load_workflow, 'value')

        # --- Watch for workflow replacement ---
        self.param.watch(self._on_workflow_replace, 'workflow')

    # --- Interaction Handlers (remain mostly the same) ---

    def _on_workflow_replace(self, event: param.parameterized.Event):
        """当 self.workflow 参数被新实例替换时调用。"""
        logger.info(f"Workflow instance replaced. Updating child components. New workflow: {event.new.name}")
        # Make sure child components reference the *new* workflow object
        self.node_config.workflow = event.new
        self.workflow_canvas.workflow = event.new # This should trigger canvas redraw via its own watch
        # Explicitly clear selection/config related to the old workflow
        self.workflow_canvas.selected_node_id = None
        # Config panel update is triggered by selected_node_id change above
        self.delete_node_button.disabled = True


    def _add_node_from_palette(self, event: param.parameterized.Event):
        """当 NodePalette 中选择一个节点类型时调用。"""
        if event.new:
            node_type = event.new
            logger.info(f"接收到添加节点请求: {node_type}")
            try:
                node_id = f"{node_type.lower()}_{uuid.uuid4().hex[:6]}"
                position = (0.0, 0.0) # Simplify position for now
                # Directly modify the *current* workflow instance
                self.workflow.add_node(node_id=node_id, node_type=node_type, position=position)
                logger.info(f"节点 '{node_id}' ({node_type}) 已添加到工作流。")
                # Explicitly tell canvas to redraw because internal graph changed
                self.workflow_canvas.redraw(preserve_range=True)
                pn.state.notifications.success(f"已添加节点: {node_type}", duration=2000)
            except Exception as e:
                logger.error(f"添加节点 {node_type} 失败: {e}", exc_info=True)
                pn.state.notifications.error(f"添加节点失败: {e}", duration=4000)
            finally:
                self.node_palette.selected_node_type = None

    def _update_config_on_selection(self, event: param.parameterized.Event):
        """当 WorkflowCanvas 中的 selected_node_id 改变时调用。"""
        new_node_id = event.new
        logger.debug(f"画布选择节点: {new_node_id}")
        # Pass the selection to the config panel
        self.node_config.selected_node_id = new_node_id
        # Enable/disable delete button
        self.delete_node_button.disabled = (new_node_id is None)

    def _run_workflow(self, event):
        """运行当前工作流。"""
        logger.info("触发工作流运行...")
        self.status_text.object = "状态：正在运行..."
        self.run_button.loading = True
        try:
            self.runner.run(self.workflow) # Use the runner instance
            logger.info(f"工作流 '{self.workflow.name}' 执行调用完成。")
            self.status_text.object = "状态：运行完成 (请查看日志)"
            pn.state.notifications.success("工作流运行流程已完成。", duration=3000)
        except Exception as e:
            logger.error(f"运行工作流 '{self.workflow.name}' 失败: {e}", exc_info=True)
            self.status_text.object = f"状态：运行失败 - {e}"
            pn.state.notifications.error(f"运行工作流失败: {e}", duration=5000)
        finally:
            self.run_button.loading = False

    def _trigger_save_workflow(self, event):
        """准备保存工作流并触发下载。"""
        logger.info("触发保存工作流...")
        try:
            workflow_json = self.workflow.serialize()
            file_name = f"{self.workflow.name.replace(' ', '_').replace('/', '_')}.json"
            pn.state.download(data=workflow_json, filename=file_name, mime_type="application/json")
            logger.info(f"工作流已准备下载为 {file_name}")
            pn.state.notifications.info("工作流文件已开始下载。", duration=3000)
        except Exception as e:
            logger.error(f"序列化或准备下载工作流失败: {e}", exc_info=True)
            pn.state.notifications.error(f"保存工作流失败: {e}", duration=4000)

    def _trigger_load_workflow(self, event):
        """点击加载按钮 - 使文件输入可见。"""
        logger.info("触发加载工作流文件选择...")
        pn.state.notifications.info("请使用文件选择器加载工作流文件 (.json)。", duration=4000)
        # Make the file input visible so the user can interact
        self.file_input.visible = True

    def _handle_load_workflow(self, event: param.parameterized.Event):
        """当 FileInput 的 value 改变时（即文件被选择）调用。"""
        if event.new:
            file_content_bytes = event.new
            filename = self.file_input.filename or "unknown.json"
            logger.info(f"接收到加载工作流文件: {filename}")
            self.status_text.object = f"状态：正在加载 {filename}..."
            try:
                json_data = file_content_bytes.decode('utf-8')
                new_workflow = Workflow.deserialize(json_data)
                # Replace the current workflow object instance.
                # This will trigger the _on_workflow_replace watcher.
                self.workflow = new_workflow
                logger.info(f"工作流 '{new_workflow.name}' 已成功加载并替换当前工作流。")
                self.status_text.object = f"状态：加载成功 - {new_workflow.name}"
                pn.state.notifications.success(f"工作流 '{new_workflow.name}' 已加载。", duration=3000)

            except json.JSONDecodeError as e:
                 logger.error(f"加载工作流失败：无效的 JSON 文件 '{filename}'. {e}")
                 self.status_text.object = "状态：加载失败 - 无效的JSON"
                 pn.state.notifications.error(f"加载失败：无效的JSON文件 '{filename}'。", duration=4000)
            except Exception as e:
                logger.error(f"加载工作流 '{filename}' 失败: {e}", exc_info=True)
                self.status_text.object = f"状态：加载失败 - {e}"
                pn.state.notifications.error(f"加载工作流失败: {e}", duration=4000)
            finally:
                # Reset and hide the file input regardless of success/failure
                self.file_input.value = None
                self.file_input.filename = None
                self.file_input.visible = False


    def _clear_workflow(self, event):
        """清空当前工作流。"""
        logger.info("触发清空工作流...")
        try:
            # Create a new empty workflow instance and replace the old one.
            # This will trigger the _on_workflow_replace watcher.
            self.workflow = Workflow(name="New Workflow")
            logger.info("工作流已清空。")
            self.status_text.object = "状态：工作流已清空"
            pn.state.notifications.info("工作流已清空。", duration=2000)
        except Exception as e:
            logger.error(f"清空工作流时出错: {e}", exc_info=True)
            pn.state.notifications.error(f"清空工作流失败: {e}", duration=4000)

    def _delete_selected_node(self, event):
        """删除画布上选中的节点。"""
        node_id = self.workflow_canvas.selected_node_id
        if node_id:
            logger.info(f"触发删除节点: {node_id}")
            try:
                # Directly modify the *current* workflow instance
                self.workflow.remove_node(node_id)
                logger.info(f"节点 '{node_id}' 已从工作流移除。")
                # Clear selection and redraw
                self.workflow_canvas.selected_node_id = None # This triggers config clear via watcher
                # Explicitly redraw canvas after node removal
                self.workflow_canvas.redraw()
                pn.state.notifications.info(f"节点 '{node_id}' 已删除。", duration=2000)
            except Exception as e:
                logger.error(f"删除节点 '{node_id}' 失败: {e}", exc_info=True)
                pn.state.notifications.error(f"删除节点失败: {e}", duration=4000)
        else:
            logger.warning("尝试删除节点，但没有节点被选中。")
            pn.state.notifications.warning("请先在画布上选择一个要删除的节点。", duration=3000)

    # --- Layout Definition ---
    def panel(self) -> pn.viewable.Viewable:
        """返回应用程序的主 Panel 布局。"""

        toolbar = pn.Row(
            self.load_button,
            self.file_input, # Keep FileInput visible in the toolbar layout
            self.save_button,
            self.clear_button,
            self.run_button,
            pn.layout.HSpacer(),
            self.status_text,
            self.delete_node_button,
            height=60,
            styles={'background': '#f0f0f0', 'padding': '10px'}
        )

        template = pn.template.FastListTemplate(
            title="数据分析平台",
            sidebar=[
                self.node_palette.panel(),
                pn.pane.HTML("<hr>"),
                self.node_config.panel() # Config panel in the sidebar
            ],
            main=[
                toolbar,
                self.workflow_canvas.panel()
            ],
            sidebar_width=280,
            accent_base_color="#4CAF50",
            header_background="#388E3C",
        )
        return template

# --- 用于直接测试此视图 (可选) --- 
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG)
#     # 需要先发现节点
#     try:
#         NodeRegistry.discover_nodes()
#     except Exception as e:
#          logger.warning(f"Direct execution node discovery failed: {e}")
#     main_view = MainView()
#     main_view.panel().servable() 