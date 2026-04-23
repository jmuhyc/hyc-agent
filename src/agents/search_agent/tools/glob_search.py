"""
文件搜索工具

使用 glob 模式匹配搜索文件
返回结构化结果供 LLM 二次理解
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
import fnmatch
import os

from .search_result import FileSearchResult, FileMatch


class GlobSearchArgs(BaseModel):
    """文件搜索工具参数"""
    pattern: str = Field(
        description="glob 模式（如 '*.py', 'test_*.js', '**/*.json'）"
    )
    path: str = Field(
        default=".",
        description="搜索路径"
    )
    case_sensitive: bool = Field(
        default=False,
        description="是否区分大小写"
    )
    max_results: int = Field(
        default=100,
        description="最大返回结果数"
    )


@tool(args_schema=GlobSearchArgs)
def glob_search(
    pattern: str,
    path: str = ".",
    case_sensitive: bool = False,
    max_results: int = 100
) -> str:
    """根据 glob 模式搜索文件，支持 ** 递归匹配，返回结构化结果"""
    if not pattern:
        return "错误: 必须提供 pattern 参数"

    search_path = Path(path)
    if not search_path.exists():
        return f"错误: 路径不存在: {path}"

    search_pattern = pattern if case_sensitive else pattern.lower()

    matches: list[FileMatch] = []
    try:
        if "**" in pattern:
            items = list(search_path.rglob(pattern if case_sensitive else pattern.lower()))
        else:
            items = list(search_path.glob(pattern))

        for item in items:
            name = item.name
            if not case_sensitive:
                name = name.lower()

            if fnmatch.fnmatch(name, search_pattern):
                rel_path = item.relative_to(search_path) if item.is_relative_to(search_path) else item
                file_match = FileMatch(
                    path=str(rel_path),
                    is_dir=item.is_dir(),
                    size=item.stat().st_size if item.is_file() else None
                )
                matches.append(file_match)

    except Exception as e:
        return f"搜索出错: {str(e)}"

    if not matches:
        return f"在 '{path}' 中未找到匹配 '{pattern}' 的文件"

    truncated = len(matches) > max_results
    limited_matches = matches[:max_results]

    result = FileSearchResult(
        pattern=pattern,
        num_results=len(matches),
        matches=limited_matches,
        truncated=truncated
    )

    return result.model_dump_json(indent=2, exclude_none=True)
