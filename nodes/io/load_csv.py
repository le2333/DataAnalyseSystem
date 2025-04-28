import polars as pl
import logging
from typing import Dict, Type, Any
import panel as pn
import param

# 确保可以正确导入 BaseNode 和 NodeRegistry
# 如果 nodes/io/ 在项目根目录下，相对导入可能工作
# from ...core.node import BaseNode, NodeRegistry
# 或者使用绝对路径 (假设 main.py 在根目录且已将根目录添加到 sys.path)
from core.node.base_node import BaseNode
from core.node.registry import NodeRegistry


logger = logging.getLogger(__name__)

@NodeRegistry.register_node
class LoadCsvNode(BaseNode):
    """
    从 CSV 文件加载数据到 Polars DataFrame。
    """
    # --- 定义参数 (使用 param 库) ---
    file_path: str = param.String(default="", doc="要加载的 CSV 文件的完整路径 (服务器路径)。", label="CSV 文件路径")
    separator: str = param.String(default=",", doc="CSV 文件中的列分隔符。", label="分隔符")
    has_header: bool = param.Boolean(default=True, doc="文件第一行是否包含列名。", label="包含表头")
    encoding: str = param.Selector(objects=["utf-8", "gbk", "latin-1", "iso-8859-1"], default="utf-8", doc="CSV 文件的文本编码格式。", label="文件编码")
    n_rows: int = param.Integer(default=None, bounds=(1, None), allow_None=True, doc="最终执行时要读取的最大行数，留空则读取所有行。", label="读取行数 (可选)")

    # --- 预览相关参数 ---
    load_preview_action = param.Action(lambda self: self._load_preview(), label="加载预览 (前3行)", precedence=0.6) # 调整顺序，放在路径后
    preview_data = param.DataFrame(default=None, precedence=-1, doc="文件前3行预览")

    # --- 节点元数据方法 --- 

    @classmethod
    def define_inputs(cls) -> Dict[str, Type]:
        """此节点没有输入。"""
        return {}

    @classmethod
    def define_outputs(cls) -> Dict[str, Type]:
        """定义输出为一个名为 'output_df' 的 DataFrame。"""
        return {"output_df": pl.DataFrame}
        
    # --- 核心运行逻辑 --- 
    def run(self, inputs: Dict[str, pl.DataFrame]) -> Dict[str, pl.DataFrame]:
        """执行读取 CSV 文件的操作。"""
        # --- 在运行前检查必需参数 --- 
        if not self.file_path or not isinstance(self.file_path, str) or not self.file_path.strip():
             raise ValueError(f"节点 '{self.node_type}' (ID: {self.node_id}) 缺少必需的 'file_path' 参数，无法运行。")
        fpath = self.file_path.strip()

        logger.info(f"节点 '{self.node_id}' ({self.node_type}): 尝试从 '{fpath}' 加载 CSV。")
        logger.debug(f"参数: separator='{self.separator}', has_header={self.has_header}, encoding='{self.encoding}', n_rows={self.n_rows}")

        try:
            df = pl.read_csv(
                source=fpath, # 使用清理过的路径
                separator=self.separator,
                has_header=self.has_header,
                encoding=self.encoding,
                n_rows=self.n_rows # 使用节点参数 n_rows
            )
            logger.info(f"成功从 '{fpath}' 加载了 {df.shape[0]} 行 x {df.shape[1]} 列的数据。")
            return {"output_df": df}
        except FileNotFoundError:
            logger.error(f"节点 '{self.node_id}': 文件未找到 - {fpath}")
            raise FileNotFoundError(f"CSV 文件未找到: {fpath}") 
        except pl.exceptions.ComputeError as e:
             logger.error(f"节点 '{self.node_id}': 读取 CSV 文件 '{fpath}' 时出错: {e}")
             raise ValueError(f"读取 CSV '{fpath}' 时出错: {e}") from e
        except Exception as e:
            logger.error(f"节点 '{self.node_id}': 加载 CSV '{fpath}' 时发生未知错误: {e}", exc_info=True)
            raise RuntimeError(f"加载 CSV '{fpath}' 时发生未知错误: {e}") from e
            
    # --- 预览功能实现 --- 
    def _load_preview(self):
        """加载文件前3行以供预览。"""
        fpath = self.file_path
        if not fpath or not isinstance(fpath, str) or not fpath.strip():
            if pn.state.notifications: pn.state.notifications.warning("请输入有效的文件路径。", duration=3000)
            self.preview_data = None
            return
        fpath = fpath.strip() # 清理路径

        try:
            logger.info(f"节点 '{self.node_id}': 尝试加载预览: {fpath}")
            # 使用 polars 读取前3行
            df_preview = pl.read_csv(
                source=fpath,
                separator=self.separator,
                has_header=self.has_header,
                encoding=self.encoding,
                n_rows=3,
                ignore_errors=True # 预览时尽量容错
            )
            self.preview_data = df_preview # 直接赋值 Polars DataFrame
            logger.info(f"预览加载成功 for {fpath}. Shape: {df_preview.shape}")
            if pn.state.notifications: pn.state.notifications.success("预览加载成功。", duration=2000)
        except FileNotFoundError:
            self.preview_data = None
            logger.error(f"预览错误: 文件未找到 {fpath}")
            if pn.state.notifications: pn.state.notifications.error(f"文件未找到: {fpath}", duration=4000)
        except pl.exceptions.NoDataError:
             self.preview_data = None # 或 pl.DataFrame() 如果想显示空表
             logger.warning(f"预览警告: 文件可能为空或只有表头: {fpath}")
             if pn.state.notifications: pn.state.notifications.warning(f"文件为空或只有表头?", duration=3000)
        except Exception as e:
            self.preview_data = None
            logger.error(f"预览错误: 读取 CSV 预览失败 {fpath}: {e}", exc_info=True)
            if pn.state.notifications: pn.state.notifications.error(f"读取预览失败: {type(e).__name__}", duration=4000)

    @param.depends('preview_data', watch=False) # watch=False 因为我们只在 get_config_panel 调用它
    def _get_preview_panel(self) -> pn.viewable.Viewable:
        """根据 preview_data 的状态返回相应的 Panel 组件。"""
        if self.preview_data is None:
            # 初始状态或加载失败时不显示任何内容
            return pn.pane.Markdown("", height=0, width=0, margin=0, sizing_mode='fixed') # 完全隐藏
        elif self.preview_data.height == 0:
             # 文件存在但为空或只有表头
             return pn.Column(
                 pn.pane.Markdown("#### 文件预览 (前3行)"),
                 pn.pane.Markdown("_预览为空或只有表头。_")
             )
        else:
            # 成功加载预览
            return pn.Column(
                pn.pane.Markdown("#### 文件预览 (前3行)"),
                pn.pane.DataFrame(self.preview_data, max_rows=3, sizing_mode='stretch_width', index=False)
            )

    # --- UI 配置面板 --- 
    def get_config_panel(self) -> pn.viewable.Viewable:
        """
        返回此节点的自定义配置面板，包含预览功能。
        """
        # 手动创建控件以获得更好的布局控制
        file_path_input = pn.widgets.TextInput.from_param(self.param.file_path, placeholder="输入服务器上的文件路径...")
        preview_button = pn.widgets.Button.from_param(self.param.load_preview_action)
        separator_input = pn.widgets.TextInput.from_param(self.param.separator)
        header_check = pn.widgets.Checkbox.from_param(self.param.has_header)
        encoding_select = pn.widgets.Select.from_param(self.param.encoding)
        n_rows_input = pn.widgets.IntInput.from_param(self.param.n_rows, placeholder="所有行") # 使用 IntInput 可能更清晰

        # 获取当前预览状态的面板
        preview_display_panel = self._get_preview_panel

        # 布局
        config_layout = pn.Column(
            pn.pane.Markdown("**CSV 加载选项**"),
            file_path_input,
            preview_button, # 按钮紧随路径输入框
            pn.Row(separator_input, header_check, styles={'align-items':'end'}), # 分隔符和表头一行
            encoding_select,
            n_rows_input,
            preview_display_panel, # 动态预览区域
            sizing_mode='stretch_width'
        )
        return config_layout 