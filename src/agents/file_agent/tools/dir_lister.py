"""
目录列表工具

使用 LangChain @tool 装饰器，遵循标准工具文档规范
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
import os


class DirListerArgs(BaseModel):
    """目录列表工具参数"""
    path: str = Field(
        default=".",
        description="要列出的目录路径（默认当前目录）"
    )
    recursive: bool = Field(
        default=False,
        description="若为 True，递归列出所有子目录内容"
    )
    include_hidden: bool = Field(
        default=False,
        description="若为 True，包含以点开头的隐藏文件"
    )


@tool(args_schema=DirListerArgs)
def dir_lister(path: str = ".", recursive: bool = False, include_hidden: bool = False) -> str:
    """列出目录中的文件和子目录"""
    try:
        dir_path = Path(path)

        if not dir_path.exists():
            return f"Error: 目录不存在: {path}"

        if not dir_path.is_dir():
            return f"Error: 不是目录: {path}"

        result_parts = []
        base_path = dir_path.resolve()

        if recursive:
            for root, dirs, files in os.walk(base_path):
                root_path = Path(root)
                level = root_path.relative_to(base_path).count(os.sep)

                if level == 0:
                    result_parts.append(f"\n{root_path}:")
                else:
                    indent = "  " * level
                    result_parts.append(f"{indent}{root_path.name}/:")

                if not include_hidden:
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    files = [f for f in files if not f.startswith('.')]

                for f in sorted(files):
                    result_parts.append(f"{'  ' * (level + 1)}{f}")
        else:
            items = list(dir_path.iterdir())

            if not include_hidden:
                items = [item for item in items if not item.name.startswith('.')]

            for item in sorted(items, key=lambda x: (not x.is_dir(), x.name)):
                if item.is_dir():
                    result_parts.append(f"{item.name}/")
                else:
                    size = item.stat().st_size
                    size_str = _format_size(size)
                    result_parts.append(f"{item.name} ({size_str})")

        if not result_parts:
            return "目录为空"

        return "\n".join(result_parts)

    except Exception as e:
        return f"Error: 列出目录失败: {str(e)}"


def _format_size(size: int) -> str:
    """格式化文件大小为人类可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"