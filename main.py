import logging
import sys
from pathlib import Path
import panel as pn

# --- Logging Configuration ---
# 配置日志记录器，以便看到来自核心和 UI 模块的调试信息
logging.basicConfig(
    level=logging.INFO, # 可以改为 logging.DEBUG 获取更详细信息
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
    from ui.views.main_view import MainView # 导入重构后的 MainView
    # from ui.views.workflow_editor_view import WorkflowEditorView # 不再直接导入编辑器
    from core.workflow import Workflow # 可能需要用于创建初始工作流
except ImportError as e:
    logger.error(f"无法导入核心组件。请确保你在项目根目录下运行，并且所有 __init__.py 文件都存在。错误: {e}", exc_info=True)
    sys.exit(1) # Exit if core components cannot be imported

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

# --- Create Main View (at module level) ---
logger.info("创建主视图...")
try:
    # 创建工作流编辑器视图实例
    # 可以传入一个预先创建的 Workflow 对象，或者让视图创建默认的
    # initial_workflow = Workflow(name="Initial Workflow")
    # editor_view = WorkflowEditorView(workflow=initial_workflow)
    main_view = MainView() 
    logger.info("主视图创建成功。")
except Exception as e:
    logger.error(f"创建 MainView 时出错: {e}", exc_info=True)
    sys.exit(1)

# --- Dynamic Node Refresh on Session Load --- 
def refresh_nodes_on_load():
    """当新会话加载时，重新扫描节点并刷新节点面板。"""
    logger.info("会话加载/重载：检查节点更新...")
    try:
        # 重新执行节点发现
        reloaded_module_count = NodeRegistry.discover_nodes(nodes_dir)
        logger.info(f"节点重新发现完成。尝试加载 {reloaded_module_count} 个模块。")
        new_available_nodes = NodeRegistry.list_available_nodes()
        logger.info(f"当前可用节点: {list(new_available_nodes.keys())}")
        
        # 访问 main_view 实例中的 node_palette 并刷新它
        # 确保 main_view 已经在这个函数的作用域内定义
        if hasattr(main_view, 'workflow_editor') and \
           hasattr(main_view.workflow_editor, 'node_palette') and \
           main_view.workflow_editor.node_palette:
            main_view.workflow_editor.node_palette.refresh()
            logger.info("节点面板已刷新。")
        else:
            logger.warning("无法在 main_view 中找到 node_palette 来刷新。")
            
    except Exception as e:
        logger.error(f"会话加载时动态刷新节点失败: {e}", exc_info=True)

# 注册回调函数，使其在每个会话加载时运行
pn.state.onload(refresh_nodes_on_load)
logger.info("已注册 refresh_nodes_on_load 回调，用于在会话加载时刷新节点。")

# --- Make it Servable (at module level) ---
logger.info("准备启动 Panel 服务...")
try:
    # 使用 Panel 模板或直接服务视图
    # template = pn.template.FastListTemplate(
    #     title="时间序列分析平台 - 工作流编辑器",
    #     main=[editor_view.panel()],
    #     sidebar=[editor_view.node_palette.panel()] # 如果 Palette 不在 editor_view 内部管理
    # )
    # template.servable()
    
    # 直接服务编辑器视图的 panel
    main_view.panel().servable(title="数据分析平台")
    logger.info("应用已配置为可服务。请使用 'panel serve main.py --show' 来运行和查看。")
except Exception as e:
     logger.error(f"配置 Panel 服务时出错: {e}", exc_info=True)

# The if __name__ == "__main__": block is removed as panel serve 
# does not execute it directly. The servable() call at the module level
# is what Panel looks for. 