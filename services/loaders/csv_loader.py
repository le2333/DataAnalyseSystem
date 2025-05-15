import pandas as pd
from typing import Dict, Any
from services.base import DataLoader


class CSVLoader(DataLoader):
    """CSV文件加载器"""

    name = "CSV加载器"
    description = "加载CSV格式的数据文件"

    @classmethod
    def get_param_specs(cls) -> Dict[str, Dict[str, Any]]:
        """返回参数规范"""
        return {
            "encoding": {
                "type": "string",
                "label": "编码方式",
                "default": "utf-8",
                "options": ["utf-8", "gbk", "latin1"],
            },
            "delimiter": {
                "type": "string",
                "label": "分隔符",
                "default": ",",
                "options": [",", ";", "\t", "|"],
            },
            "header": {"type": "integer", "label": "表头行号", "default": 0},
        }

    @classmethod
    def load(cls, file_path: str, **params) -> pd.DataFrame:
        """加载CSV文件"""
        encoding = params.get("encoding", "utf-8")
        delimiter = params.get("delimiter", ",")
        header = params.get("header", 0)

        try:
            return pd.read_csv(
                file_path, encoding=encoding, delimiter=delimiter, header=header
            )
        except Exception as e:
            raise ValueError(f"CSV加载失败: {str(e)}")
