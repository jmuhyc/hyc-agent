"""
文件读取工具

使用 LangChain @tool 装饰器，遵循标准工具文档规范
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path


class FileReaderArgs(BaseModel):
    """文件读取工具参数"""
    file_path: str = Field(
        description="文件路径（绝对路径或相对于当前目录）"
    )
    max_lines: int = Field(
        default=100,
        description="最大读取行数（默认 100，设为 0 则读取全部）"
    )
    encoding: str = Field(
        default="utf-8",
        description="文件编码（默认 utf-8）"
    )


@tool(args_schema=FileReaderArgs)
def file_reader(file_path: str, max_lines: int = 100, encoding: str = "utf-8") -> str:
    """读取文件内容并返回文件文本"""
    try:
        path = Path(file_path)

        if not path.exists():
            return f"Error: 文件不存在: {file_path}"

        if not path.is_file():
            return f"Error: 不是文件: {file_path}"

        if path.stat().st_size > 5 * 1024 * 1024:
            return f"Error: 文件太大（最大 5MB）: {file_path}"

        with open(path, 'r', encoding=encoding, errors='replace') as f:
            if max_lines > 0:
                lines = [f.readline() for _ in range(max_lines)]
                content = ''.join(lines)
                remaining = f.read()
                if remaining:
                    content += f"\n...（已截断，仅显示前 {max_lines} 行）"
            else:
                content = f.read()

        return content

    except Exception as e:
        return f"Error: 读取文件失败: {str(e)}"