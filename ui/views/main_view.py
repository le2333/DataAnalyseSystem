# ui/views/main_view.py
import panel as pn
import param
import logging
import uuid
from pathlib import Path
import json

# --- 标准导入 ---
# 假设从根目录通过 main.py 运行
from core.workflow import Workflow, WorkflowRunner
from core.node import NodeRegistry
# 不再直接依赖子组件，而是依赖编辑器视图
# from ui.components.node_palette import NodePalette
# from ui.components.config_editor import ConfigEditor
# from ui.components.workflow_visualizer import WorkflowVisualizer
from ui.views.workflow_editor_view import WorkflowEditorView # 导入编辑器视图


pn.extension(notifications=True) # 启用通知以提供用户反馈

logger = logging.getLogger(__name__)

class MainView(param.Parameterized):
    """
    应用程序的主框架视图。
    管理顶层布局（如标签页、工具栏），并包含具体功能视图（如工作流编辑器）。
    """

    # --- 核心对象 ---
    # MainView 持有当前活动的工作流实例
    workflow = param.ClassSelector(class_=Workflow)
    runner = param.ClassSelector(class_=WorkflowRunner)

    # --- 视图/页面 (作为标签页) ---
    # 实例化子视图
    workflow_editor: WorkflowEditorView = None

    # --- UI 组件 / 控件 (工具栏) ---
    run_button = param.Parameter()
    save_button = param.Parameter()
    load_button = param.Parameter()
    clear_button = param.Parameter()
    delete_node_button = param.Parameter()
    file_input = param.Parameter()
    status_text = param.Parameter(default=pn.pane.Markdown("状态：就绪", align='center'))

    def __init__(self, **params):
        """
        初始化 MainView 框架。
        """
        # --- 在 super().__init__() 之前设置默认核心对象 ---
        if 'workflow' not in params:
            params['workflow'] = Workflow(name="New Workflow")
        if 'runner' not in params:
            params['runner'] = WorkflowRunner()

        # --- 初始化组件和控件 (工具栏) ---
        self.run_button = pn.widgets.Button(name="▶️ 运行工作流", button_type="success", width=120, align='center')
        self.save_button = pn.widgets.Button(name="💾 保存工作流", button_type="primary", width=120, align='center')
        self.load_button = pn.widgets.Button(name="📂 加载工作流", button_type="default", width=120, align='center')
        self.clear_button = pn.widgets.Button(name="🗑️ 清空工作流", button_type="danger", width=120, align='center')
        self.delete_node_button = pn.widgets.Button(name="❌ 删除选中节点", button_type="warning", width=150, align='center', disabled=True)
        self.file_input = pn.widgets.FileInput(accept=".json", multiple=False, visible=False)
        
        # --- 实例化子视图 ---
        # 将 MainView 持有的 workflow 实例传递给编辑器
        self.workflow_editor = WorkflowEditorView(workflow=params['workflow'])
        
        # --- 调用 super().__init__() ---
        super().__init__(**params)

        # --- 绑定工具栏交互 ---
        self.run_button.on_click(self._run_workflow)
        self.save_button.on_click(self._trigger_save_workflow)
        self.load_button.on_click(self._trigger_load_workflow)
        self.clear_button.on_click(self._clear_workflow)
        self.delete_node_button.on_click(self._delete_selected_node) # 需要访问编辑器的选中状态
        self.file_input.param.watch(self._handle_load_workflow, 'value')
        
        # --- 监听影响工具栏的更改 ---
        # 监听编辑器视图的选中节点，以启用/禁用删除按钮
        self.workflow_editor.param.watch(self._update_delete_button_state, 'selected_node_id')
        # 监听工作流替换事件，以确保编辑器视图使用新的实例
        self.param.watch(self._handle_workflow_replacement, 'workflow')
        # 初始化删除按钮状态
        self._update_delete_button_state()

    # --- 工具栏动作处理程序 ---
    
    def _update_delete_button_state(self, event=None):
         """根据编辑器视图的选中状态更新删除按钮。"""
         selected_id = self.workflow_editor.selected_node_id
         self.delete_node_button.disabled = (selected_id is None)

    def _run_workflow(self, event):
        """运行当前工作流 (由 MainView 持有)。"""
        logger.info("触发工作流运行...")
        self.status_text.object = "状态：正在运行..."
        self.run_button.loading = True
        try:
            if not self.workflow:
                raise ValueError("工作流未初始化")
            if not self.runner:
                 self.runner = WorkflowRunner() # 确保 runner 存在
            self.runner.run(self.workflow)
            logger.info(f"工作流 '{self.workflow.name}' 执行调用完成。")
            self.status_text.object = "状态：运行完成 (请查看日志)"
            if pn.state.notifications:
                pn.state.notifications.success("工作流运行流程已完成。", duration=3000)
        except Exception as e:
            logger.error(f"运行工作流失败: {e}", exc_info=True)
            self.status_text.object = f"状态：运行失败 - {e}"
            if pn.state.notifications:
                pn.state.notifications.error(f"运行工作流失败: {e}", duration=5000)
        finally:
            self.run_button.loading = False

    def _trigger_save_workflow(self, event):
        """准备保存当前工作流并触发下载。"""
        logger.info("触发保存工作流...")
        if not self.workflow:
             logger.warning("无法保存，工作流为空。")
             if pn.state.notifications:
                 pn.state.notifications.warning("工作流为空，无法保存。", duration=3000)
             return
        try:
            workflow_json = self.workflow.serialize()
            file_name = f"{self.workflow.name.replace(' ', '_').replace('/', '_')}.json"
            if hasattr(pn.state, 'download'):
                 pn.state.download(data=workflow_json, filename=file_name, mime_type="application/json")
                 logger.info(f"工作流已准备下载为 {file_name}")
                 if pn.state.notifications:
                    pn.state.notifications.info("工作流文件已开始下载。", duration=3000)
            else:
                 logger.warning("pn.state.download 不可用，无法直接触发下载。")
                 # 可以在 UI 中显示一个下载链接
                 # download_link = pn.pane.HTML(f'<a href="data:application/json;charset=utf-8,{workflow_json}" download="{file_name}">点击下载 {file_name}</a>')
                 # self.status_text.object = download_link # 或者添加到其他地方
                 if pn.state.notifications:
                     pn.state.notifications.warning("无法自动下载，请检查浏览器设置或联系管理员。", duration=4000)

        except Exception as e:
            logger.error(f"序列化或准备下载工作流失败: {e}", exc_info=True)
            if pn.state.notifications:
                pn.state.notifications.error(f"保存工作流失败: {e}", duration=4000)

    def _trigger_load_workflow(self, event):
        """点击加载按钮 - 使文件输入可见。"""
        logger.info("触发加载工作流文件选择...")
        if pn.state.notifications:
            pn.state.notifications.info("请使用文件选择器加载工作流文件 (.json)。", duration=4000)
        self.file_input.visible = True

    def _handle_load_workflow(self, event: param.parameterized.Event):
        """当 FileInput 的 value 改变时调用。"""
        if event.new:
            file_content_bytes = event.new
            filename = self.file_input.filename or "unknown.json"
            logger.info(f"接收到加载工作流文件: {filename}")
            self.status_text.object = f"状态：正在加载 {filename}..."
            try:
                json_data = file_content_bytes.decode('utf-8')
                new_workflow = Workflow.deserialize(json_data)
                # 替换 MainView 持有的 workflow 实例
                # 这会触发 _handle_workflow_replacement
                self.workflow = new_workflow
                logger.info(f"工作流 '{new_workflow.name}' 已成功加载。")
                self.status_text.object = f"状态：加载成功 - {new_workflow.name}"
                if pn.state.notifications:
                    pn.state.notifications.success(f"工作流 '{new_workflow.name}' 已加载。", duration=3000)
            except json.JSONDecodeError as e:
                 logger.error(f"加载工作流失败：无效的 JSON 文件 '{filename}'. {e}")
                 self.status_text.object = "状态：加载失败 - 无效的JSON"
                 if pn.state.notifications:
                     pn.state.notifications.error(f"加载失败：无效的JSON文件 '{filename}'。", duration=4000)
            except Exception as e:
                logger.error(f"加载工作流 '{filename}' 失败: {e}", exc_info=True)
                self.status_text.object = f"状态：加载失败 - {e}"
                if pn.state.notifications:
                    pn.state.notifications.error(f"加载工作流失败: {e}", duration=4000)
            finally:
                # 重置 FileInput
                self.file_input.value = None
                self.file_input.filename = None
                self.file_input.visible = False

    def _handle_workflow_replacement(self, event: param.parameterized.Event):
        """当 self.workflow 被新实例替换时，确保子视图也更新。"""
        logger.info(f"MainView workflow replaced. Updating editor view.")
        new_workflow = event.new
        if self.workflow_editor.workflow is not new_workflow:
             self.workflow_editor.workflow = new_workflow
        # 可能需要重置编辑器视图的选中状态
        if self.workflow_editor.selected_node_id is not None:
             self.workflow_editor.selected_node_id = None

    def _clear_workflow(self, event):
        """清空当前工作流。"""
        logger.info("触发清空工作流...")
        try:
            # 创建新实例并替换，触发 _handle_workflow_replacement
            self.workflow = Workflow(name="New Workflow")
            logger.info("工作流已清空。")
            self.status_text.object = "状态：工作流已清空"
            if pn.state.notifications:
                pn.state.notifications.info("工作流已清空。", duration=2000)
        except Exception as e:
            logger.error(f"清空工作流时出错: {e}", exc_info=True)
            if pn.state.notifications:
                pn.state.notifications.error(f"清空工作流失败: {e}", duration=4000)

    def _delete_selected_node(self, event):
        """删除编辑器视图中选中的节点。"""
        node_id = self.workflow_editor.selected_node_id # 从编辑器获取 ID
        if node_id:
            logger.info(f"请求删除节点: {node_id}")
            if not self.workflow:
                 logger.warning("无法删除节点，工作流为空。")
                 return
            try:
                # 直接在 MainView 持有的 workflow 上操作
                self.workflow.remove_node(node_id)
                logger.info(f"节点 '{node_id}' 已从工作流移除。")
                # 清除编辑器的选择状态 (它应该会触发 MainView 的 watcher 更新按钮状态)
                self.workflow_editor.selected_node_id = None
                # 触发 workflow 更新，让编辑器和其他组件知道变化
                self.param.trigger('workflow')
                if pn.state.notifications:
                    pn.state.notifications.info(f"节点 '{node_id}' 已删除。", duration=2000)
            except Exception as e:
                logger.error(f"删除节点 '{node_id}' 失败: {e}", exc_info=True)
                if pn.state.notifications:
                    pn.state.notifications.error(f"删除节点失败: {e}", duration=4000)
        else:
            logger.warning("尝试删除节点，但没有节点被选中。")
            if pn.state.notifications:
                pn.state.notifications.warning("请先在画布上选择一个要删除的节点。", duration=3000)

    # --- 布局定义 ---
    def panel(self) -> pn.viewable.Viewable:
        """返回应用程序的主 Panel 布局。"""

        toolbar = pn.Row(
            self.load_button,
            self.file_input,
            self.save_button,
            self.clear_button,
            self.run_button,
            self.delete_node_button, # 删除按钮放回工具栏
            self.status_text,
            align='center',
            sizing_mode='stretch_width',
            styles={'background': '#f0f0f0', 'padding': '10px'}
        )

        # --- 创建应用程序的整体布局 ---
        # 使用模板
        template = pn.template.VanillaTemplate(
            title="时间序列分析平台 (TSAP)",
            sidebar_width=0, # 隐藏侧边栏，因为我们的主要导航在标签页
            header_background="#0072B5", # Example header color
            header_color="white",
            busy_indicator=pn.indicators.BooleanStatus(value=False, color='success', align='center')
        )

        # 将工具栏添加到模板的页眉区域
        template.header.append(toolbar)

        # 将编辑器视图添加到主内容区域
        template.main.append(self.workflow_editor.panel())

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