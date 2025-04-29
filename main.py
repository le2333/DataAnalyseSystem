import logging
import sys
from pathlib import Path
import panel as pn

# --- Logging Configuration ---
# 配置日志记录器，以便看到来自核心和 UI 模块的调试信息
logging.basicConfig(
    level=logging.DEBUG, # 使用 DEBUG 级别方便调试
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Add Project Root to Path (if needed) ---
# 通常，如果从项目根目录运行此脚本，则不需要
# 但如果从其他地方导入或运行，可能需要确保 core 和 nodes 可导入
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

# --- Import Core Components ---
try:
    from core.node import NodeRegistry
    from core.workflow import Workflow
    # 导入 ViewModel 和 View
    from viewmodels import WorkflowViewModel
    # 注意：如果 MainView 内部会创建 WorkflowEditorView，我们需要调整 MainView
    # 或者直接在这里创建 WorkflowEditorView 并传递给 MainView（如果 MainView 设计允许）
    # 假设我们暂时直接运行 WorkflowEditorView
    from ui.views.workflow_editor_view import WorkflowEditorView
    # from ui.views.main_view import MainView # 暂时不使用 MainView，直接测试 Editor
except ImportError as e:
    logger.error(f"无法导入核心组件或视图/视图模型。请确保路径和 __init__.py 文件正确。错误: {e}", exc_info=True)
    sys.exit(1)

# --- Discover Nodes (Initial discovery at startup) ---
logger.info("应用程序启动 - 初始节点发现...")
nodes_dir = "nodes" # 相对于项目根目录
try:
    loaded_module_count = NodeRegistry.discover_nodes(nodes_dir)
    logger.info(f"初始节点发现完成。尝试加载 {loaded_module_count} 个模块。")
    available_nodes_meta = NodeRegistry.list_available_nodes()
    if not available_nodes_meta:
         logger.warning(f"初始发现：在 '{nodes_dir}' 目录下没有发现或成功注册任何节点。")
    else:
         logger.info(f"初始注册节点类型: {list(available_nodes_meta.keys())}")
except Exception as e:
    logger.error(f"初始节点发现过程中发生错误: {e}", exc_info=True)

# --- Create MVVM Instances ---
logger.info("创建 ViewModel 和 View 实例...")
try:
    # 1. 创建 Model (可选，如果 ViewModel 可以创建默认的)
    initial_workflow = Workflow(name="我的工作流")
    # 2. 创建 ViewModel，传入 Model
    workflow_view_model = WorkflowViewModel(workflow=initial_workflow)
    # 3. 创建 View，传入 ViewModel
    editor_view = WorkflowEditorView(view_model=workflow_view_model)
    logger.info("ViewModel 和 View 创建成功。")
except Exception as e:
    logger.error(f"创建 MVVM 实例时出错: {e}", exc_info=True)
    sys.exit(1)

# --- Dynamic Node Refresh on Session Load --- 
def refresh_nodes_on_load():
    """当新会话加载时，重新扫描节点并刷新节点面板。"""
    logger.info("会话加载/重载：检查节点更新...")
    try:
        reloaded_module_count = NodeRegistry.discover_nodes(nodes_dir)
        logger.info(f"节点重新发现完成。尝试加载 {reloaded_module_count} 个模块。")
        new_available_nodes = NodeRegistry.list_available_nodes()
        logger.info(f"当前可用节点: {list(new_available_nodes.keys())}")
        
        # 直接刷新 editor_view 中的 node_palette
        if hasattr(editor_view, 'node_palette') and editor_view.node_palette:
            editor_view.node_palette.refresh()
            logger.info("节点面板已刷新。")
        else:
            logger.warning("无法在 editor_view 中找到 node_palette 来刷新。")
            
    except Exception as e:
        logger.error(f"会话加载时动态刷新节点失败: {e}", exc_info=True)

# 注册回调函数，使其在每个会话加载时运行
pn.state.onload(refresh_nodes_on_load)
logger.info("已注册 refresh_nodes_on_load 回调，用于在会话加载时刷新节点。")

# --- Make it Servable (at module level) ---
logger.info("准备启动 Panel 服务...")
try:
    # 直接服务 WorkflowEditorView 的 panel
    editor_view.panel().servable(title="工作流编辑器 (MVVM)")
    logger.info("应用已配置为可服务。请使用 'panel serve main.py --show' 来运行和查看。")
except Exception as e:
     logger.error(f"配置 Panel 服务时出错: {e}", exc_info=True)

# The if __name__ == "__main__": block is removed as panel serve 
# does not execute it directly. The servable() call at the module level
# is what Panel looks for. 