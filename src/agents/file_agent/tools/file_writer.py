"""
文件写入工具

使用 LangChain @tool 装饰器，遵循标准工具文档规范
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path


class FileWriterArgs(BaseModel):
    """文件写入工具参数"""
    file_path: str = Field(
        description="文件路径（绝对路径或相对于当前目录）"
    )
    content: str = Field(
        description="要写入的文本内容"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码（默认 utf-8）"
    )
    append: bool = Field(
        default=False,
        description="若为 True，则追加到现有文件；否则覆盖"
    )


@tool(args_schema=FileWriterArgs)
def file_writer(file_path: str, content: str, encoding: str = "utf-8", append: bool = False) -> str:
    """将文本内容写入文件"""
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        mode = 'a' if append else 'w'

        with open(path, mode, encoding=encoding) as f:
            f.write(content)

        action = "已追加到" if append else "已写入"
        return f"Success: {action} 文件: {file_path}"

    except Exception as e:
        return f"Error: 写入文件失败: {str(e)}"