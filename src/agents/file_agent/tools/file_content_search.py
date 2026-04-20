"""
文件内容搜索工具

使用 LangChain @tool 装饰器，遵循标准工具文档规范
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
import fnmatch


class FileContentSearchArgs(BaseModel):
    """文件内容搜索工具参数"""
    directory: str = Field(
        default=".",
        description="要搜索的目录路径（默认当前目录）"
    )
    keyword: str = Field(
        description="要在文件内容中搜索的关键词"
    )
    file_pattern: str = Field(
        default="*",
        description="仅搜索匹配此 glob 模式的文件（如 '*.py'、'*.txt'）"
    )
    case_sensitive: bool = Field(
        default=False,
        description="是否区分大小写搜索"
    )
    max_results: int = Field(
        default=50,
        description="最大返回匹配数"
    )


@tool(args_schema=FileContentSearchArgs)
def file_content_search(
    directory: str = ".",
    keyword: str = "",
    file_pattern: str = "*",
    case_sensitive: bool = False,
    max_results: int = 50
) -> str:
    """在目录中的文件内容里搜索关键词"""
    try:
        if not keyword:
            return "Error: 必须提供 keyword 参数"

        dir_path = Path(directory)

        if not dir_path.exists():
            return f"Error: 目录不存在: {directory}"

        if not dir_path.is_dir():
            return f"Error: 不是目录: {directory}"

        search_keyword = keyword if case_sensitive else keyword.lower()
        search_pattern = file_pattern if case_sensitive else file_pattern.lower()

        results = []
        search_count = 0

        for file_path in dir_path.rglob('*'):
            if not file_path.is_file():
                continue

            if not fnmatch.fnmatch(file_path.name.lower(), search_pattern):
                continue

            if file_path.stat().st_size > 1024 * 1024:
                continue

            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        content = line if case_sensitive else line.lower()

                        if search_keyword in content:
                            context = line.rstrip()
                            if len(context) > 100:
                                context = context[:100] + "..."

                            results.append({
                                'file': str(file_path.relative_to(dir_path)),
                                'line': line_num,
                                'context': context
                            })
                            search_count += 1

                            if search_count >= max_results:
                                break

            except Exception:
                continue

            if search_count >= max_results:
                break

        if not results:
            return f"在匹配 '{file_pattern}' 的文件中未找到 '{keyword}'"

        output = f"找到 {len(results)} 个匹配:\n\n"
        for r in results:
            output += f"{r['file']}:{r['line']}: {r['context']}\n"

        return output

    except Exception as e:
        return f"Error: 搜索内容失败: {str(e)}"