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
# project_root = Path(__file__).parent
# if str(project_root) not in sys.path:
#     sys.path.insert(0, str(project_root))
#     logger.info(f"Added project root to sys.path: {project_root}")

# --- Import Core Components ---
try:
    from core.node import NodeRegistry
    from ui.views.main_view import MainView
except ImportError as e:
    logger.error(f"无法导入核心组件。请确保你在项目根目录下运行，并且所有 __init__.py 文件都存在。错误: {e}", exc_info=True)
    sys.exit(1) # 退出程序

# --- Discover Nodes (at module level, before MainView instantiation) ---
logger.info("应用程序启动 - 开始发现节点...")
nodes_dir = "nodes" # 相对于项目根目录
try:
    loaded_module_count = NodeRegistry.discover_nodes(nodes_dir)
    logger.info(f"节点发现完成。尝试加载 {loaded_module_count} 个模块。")
    available_nodes_meta = NodeRegistry.list_available_nodes()
    if not available_nodes_meta:
         logger.warning(f"在 '{nodes_dir}' 目录下没有发现或成功注册任何节点。请检查节点实现和注册。")
    else:
         logger.info(f"当前已注册的节点类型: {list(available_nodes_meta.keys())}")
except Exception as e:
    logger.error(f"节点发现过程中发生错误: {e}", exc_info=True)
    # 可以选择继续运行，但 NodePalette 会是空的

# --- Create Main View (at module level) ---
logger.info("创建主视图...")
try:
    main_view = MainView()
    logger.info("主视图创建成功。")
except Exception as e:
    logger.error(f"创建 MainView 时出错: {e}", exc_info=True)
    sys.exit(1)

# --- Make it Servable (at module level) ---
logger.info("准备启动 Panel 服务...")
try:
    main_view.panel().servable(title="数据分析平台")
    logger.info("应用已配置为可服务。请使用 'panel serve main.py --show' 来运行和查看。")
except Exception as e:
     logger.error(f"配置 Panel 服务时出错: {e}", exc_info=True)

# The if __name__ == "__main__": block is removed as panel serve 
# does not execute it directly. The servable() call at the module level
# is what Panel looks for. 