"""
文件搜索工具

使用 LangChain @tool 装饰器，遵循标准工具文档规范
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
import fnmatch


class FileSearchArgs(BaseModel):
    """文件搜索工具参数"""
    directory: str = Field(
        default=".",
        description="要搜索的目录路径（默认当前目录）"
    )
    pattern: str = Field(
        default="*",
        description="匹配文件名的 glob 模式（如 '*.py'、'test_*'、'*.json'）"
    )
    case_sensitive: bool = Field(
        default=False,
        description="是否区分大小写搜索"
    )


@tool(args_schema=FileSearchArgs)
def file_search(directory: str = ".", pattern: str = "*", case_sensitive: bool = False) -> str:
    """根据文件名模式在目录中搜索文件和文件夹"""
    try:
        dir_path = Path(directory)

        if not dir_path.exists():
            return f"Error: 目录不存在: {directory}"

        if not dir_path.is_dir():
            return f"Error: 不是目录: {directory}"

        search_pattern = pattern if case_sensitive else pattern.lower()

        results = []

        for item in dir_path.rglob('*'):
            name = item.name
            search_name = name if case_sensitive else name.lower()

            if fnmatch.fnmatch(search_name, search_pattern):
                relative_path = item.relative_to(dir_path)
                if item.is_dir():
                    results.append(f"{relative_path}/")
                else:
                    results.append(str(relative_path))

        if not results:
            return f"在 '{directory}' 中未找到匹配 '{pattern}' 的文件"

        return f"找到 {len(results)} 个匹配:\n" + "\n".join(sorted(results))

    except Exception as e:
        return f"Error: 搜索文件失败: {str(e)}"