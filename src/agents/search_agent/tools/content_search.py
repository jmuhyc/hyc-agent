"""
内容搜索工具

使用正则表达式在文件内容中搜索
返回结构化结果供 LLM 二次理解
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
import re
import subprocess
import shutil

from .search_result import ContentSearchResult, SearchMatch


class ContentSearchArgs(BaseModel):
    """内容搜索工具参数"""
    pattern: str = Field(
        description="正则表达式搜索模式"
    )
    path: str = Field(
        default=".",
        description="搜索路径（文件或目录）"
    )
    glob: str = Field(
        default="*",
        description="文件过滤 glob 模式（如 '*.py'）"
    )
    case_sensitive: bool = Field(
        default=False,
        description="是否区分大小写"
    )
    context_lines: int = Field(
        default=1,
        description="结果上下文的行数（默认1行）"
    )
    max_results: int = Field(
        default=50,
        description="最大返回结果数"
    )


def _search_with_ripgrep(
    pattern: str,
    path: str,
    glob: str,
    case_sensitive: bool,
    context_lines: int,
    max_results: int
) -> ContentSearchResult:
    """使用 ripgrep 进行搜索"""
    rg_path = shutil.which("rg") or shutil.which("grep")
    if not rg_path:
        return _search_with_python(pattern, path, glob, case_sensitive, context_lines, max_results)

    cmd = [
        rg_path,
        "--hidden",
        "--glob", "!.*",
        "-n",
        "-j",
    ]

    if not case_sensitive:
        cmd.append("-i")

    if glob and glob != "*":
        cmd.extend(["--glob", glob])

    if context_lines > 0:
        cmd.extend(["-C", str(context_lines)])

    cmd.extend(["-e", pattern, path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        matches: list[SearchMatch] = []
        files_set = set()

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            seen: set[tuple[str, int]] = set()

            for line in lines:
                if "--" in line or ":-" in line:
                    continue
                if ":" not in line:
                    continue

                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue

                file_path, line_num_str, content = parts
                try:
                    line_num = int(line_num_str)
                except ValueError:
                    continue

                if (file_path, line_num) in seen:
                    continue
                seen.add((file_path, line_num))
                files_set.add(file_path)

                match = SearchMatch(
                    file=file_path,
                    line_number=line_num,
                    content=content[:200] if len(content) > 200 else content,
                )
                matches.append(match)

                if len(matches) >= max_results:
                    break

        truncated = len(matches) >= max_results

        return ContentSearchResult(
            query=pattern,
            num_matches=len(matches),
            num_files=len(files_set),
            matches=matches,
            truncated=truncated
        )

    except subprocess.TimeoutExpired:
        return ContentSearchResult(
            query=pattern,
            num_matches=0,
            num_files=0,
            matches=[],
            truncated=False
        )
    except Exception as e:
        return ContentSearchResult(
            query=pattern,
            num_matches=0,
            num_files=0,
            matches=[],
            truncated=False
        )


def _search_with_python(
    pattern: str,
    path: str,
    glob: str,
    case_sensitive: bool,
    context_lines: int,
    max_results: int
) -> ContentSearchResult:
    """使用 Python re 进行搜索（ripgrep 不可用时的备选方案）"""
    try:
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)
    except re.error:
        return ContentSearchResult(
            query=pattern,
            num_matches=0,
            num_files=0,
            matches=[],
            truncated=False
        )

    search_path = Path(path)
    if search_path.is_file():
        search_path = [search_path]
    elif search_path.is_dir():
        pattern_glob = glob if glob != "*" else "*"
        search_path = list(search_path.rglob(pattern_glob))
    else:
        return ContentSearchResult(
            query=pattern,
            num_matches=0,
            num_files=0,
            matches=[],
            truncated=False
        )

    matches: list[SearchMatch] = []
    files_set = set()
    all_lines: dict[str, list[str]] = {}

    for file_path in search_path:
        if not file_path.is_file():
            continue
        if file_path.stat().st_size > 10 * 1024 * 1024:
            continue

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                all_lines[str(file_path)] = f.readlines()
        except Exception:
            continue

    for file_path_str, lines in all_lines.items():
        for i, line in enumerate(lines, 1):
            if regex.search(line):
                files_set.add(file_path_str)
                content = line.rstrip()

                ctx_before = lines[i - 2] if i > 1 and context_lines > 0 else None
                ctx_after = lines[i] if i < len(lines) and context_lines > 0 else None

                match = SearchMatch(
                    file=file_path_str,
                    line_number=i,
                    content=content[:200] if len(content) > 200 else content,
                    context_before=ctx_before.rstrip() if ctx_before else None,
                    context_after=ctx_after.rstrip() if ctx_after else None,
                )
                matches.append(match)

                if len(matches) >= max_results:
                    break

        if len(matches) >= max_results:
            break

    truncated = len(matches) >= max_results

    return ContentSearchResult(
        query=pattern,
        num_matches=len(matches),
        num_files=len(files_set),
        matches=matches,
        truncated=truncated
    )


@tool(args_schema=ContentSearchArgs)
def content_search(
    pattern: str,
    path: str = ".",
    glob: str = "*",
    case_sensitive: bool = False,
    context_lines: int = 1,
    max_results: int = 50
) -> str:
    """在文件内容中使用正则表达式搜索匹配的文本行，返回结构化结果供 LLM 理解和总结"""
    if not pattern:
        return "错误: 必须提供 pattern 参数"

    result = _search_with_ripgrep(
        pattern=pattern,
        path=path,
        glob=glob,
        case_sensitive=case_sensitive,
        context_lines=context_lines,
        max_results=max_results
    )

    if result.num_matches == 0:
        return f"未找到匹配 '{pattern}' 的结果"

    return result.model_dump_json(indent=2, exclude_none=True)
