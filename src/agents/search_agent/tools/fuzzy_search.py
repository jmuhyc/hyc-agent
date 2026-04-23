"""
模糊文件搜索工具

实现 nucleo/fzf 风格的模糊匹配算法
O(1) 位图过滤 + Top-k 贪心匹配
返回结构化结果供 LLM 二次理解
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
from dataclasses import dataclass
import fnmatch

from .search_result import FuzzySearchResult, FuzzyMatch


@dataclass
class SearchResult:
    """内部搜索结果"""
    path: str
    score: float
    matched_indices: list[int]


class FuzzySearchArgs(BaseModel):
    """模糊搜索工具参数"""
    query: str = Field(
        description="模糊搜索查询字符串"
    )
    path: str = Field(
        default=".",
        description="搜索路径"
    )
    file_pattern: str = Field(
        default="*",
        description="文件过滤 glob 模式"
    )
    limit: int = Field(
        default=20,
        description="返回的最大结果数"
    )


class FileIndex:
    """
    模糊文件索引

    使用 nucleo 风格的算法:
    - O(1) 位图过滤快速排除不匹配的路径
    - 贪心最早匹配 (Greedy-earliest)
    - Top-k 优化
    """

    SCORE_MATCH = 16
    BONUS_BOUNDARY = 8
    BONUS_CAMEL = 6
    BONUS_CONSECUTIVE = 4
    BONUS_FIRST_CHAR = 8
    PENALTY_GAP_START = 3
    PENALTY_GAP_EXTENSION = 1

    def __init__(self):
        self.paths: list[str] = []
        self.lower_paths: list[str] = []
        self.char_bits: list[int] = []

    def load_from_directory(self, directory: str, pattern: str = "*"):
        """从目录加载文件列表"""
        dir_path = Path(directory)
        if not dir_path.exists():
            raise ValueError(f"目录不存在: {directory}")

        self.paths = []
        self.lower_paths = []
        self.char_bits = []

        for item in dir_path.rglob("*"):
            if not item.is_file():
                continue
            if not fnmatch.fnmatch(item.name, pattern):
                continue

            rel_path = item.relative_to(dir_path) if item.is_relative_to(dir_path) else item
            path_str = str(rel_path)

            self.paths.append(path_str)
            self.lower_paths.append(path_str.lower())
            self.char_bits.append(self._compute_char_bits(path_str.lower()))

    def _compute_char_bits(self, path: str) -> int:
        """计算路径的字符位图 (a-z)"""
        bits = 0
        for char in path:
            if 'a' <= char <= 'z':
                bits |= 1 << (ord(char) - ord('a'))
            elif '0' <= char <= '9':
                pass
        return bits

    def _build_needle_bitmap(self, query: str) -> int:
        """构建查询的位图"""
        bits = 0
        for char in query.lower():
            if 'a' <= char <= 'z':
                bits |= 1 << (ord(char) - ord('a'))
        return bits

    def _find_earliest_match(self, lower_path: str, query: str) -> tuple[int, list[int]]:
        """找到查询字符在路径中最早出现的位置"""
        matched = []
        query_idx = 0

        for i, char in enumerate(lower_path):
            if query_idx >= len(query):
                break
            if char == query[query_idx]:
                matched.append(i)
                query_idx += 1

        if query_idx < len(query):
            return -1, []
        return matched[0] if matched else -1, matched

    def _is_boundary(self, path: str, pos: int) -> bool:
        """判断位置是否为单词边界"""
        if pos == 0:
            return True
        char = path[pos]
        prev_char = path[pos - 1]
        return char.isupper() or char in '_-./\\' or prev_char in '_-./\\'

    def _is_camel(self, path: str, pos: int) -> bool:
        """判断是否为 CamelCase 边界"""
        if pos == 0:
            return False
        char = path[pos]
        prev_char = path[pos - 1]
        return char.isupper() and prev_char.islower()

    def _score_match(self, path: str, pos: int, consecutive: bool) -> int:
        """计算单个匹配的得分"""
        score = self.SCORE_MATCH

        if self._is_boundary(path, pos):
            score += self.BONUS_BOUNDARY
        if self._is_camel(path, pos):
            score += self.BONUS_CAMEL
        if consecutive:
            score += self.BONUS_CONSECUTIVE
        if pos == 0:
            score += self.BONUS_FIRST_CHAR

        return score

    def _compute_score(self, path: str, query: str, matched: list[int]) -> float:
        """计算路径的总得分（越低越好）"""
        if not matched:
            return float('inf')

        score = 0
        prev_pos = -1

        for pos in matched:
            consecutive = prev_pos >= 0 and pos == prev_pos + 1
            score += self._score_match(path, pos, consecutive)

            if prev_pos >= 0 and pos > prev_pos + 1:
                gap = pos - prev_pos - 1
                score += self.PENALTY_GAP_START + gap * self.PENALTY_GAP_EXTENSION

            prev_pos = pos

        max_score = len(query) * (self.SCORE_MATCH + self.BONUS_BOUNDARY + self.BONUS_CONSECUTIVE)
        return score / max_score if max_score > 0 else float('inf')

    def search(self, query: str, limit: int = 20) -> list[SearchResult]:
        """执行模糊搜索"""
        if not query:
            return [SearchResult(path=p, score=0.0, matched_indices=[]) for p in self.paths[:limit]]

        needle_bitmap = self._build_needle_bitmap(query)
        query_lower = query.lower()

        top_k: list[tuple[str, float]] = []

        for path, lower_path, char_bit in zip(self.paths, self.lower_paths, self.char_bits):
            if (char_bit & needle_bitmap) != needle_bitmap:
                continue

            _, matched = self._find_earliest_match(lower_path, query_lower)
            if not matched:
                continue

            score = self._compute_score(lower_path, query_lower, matched)

            if len(top_k) < limit:
                top_k.append((path, score))
                top_k.sort(key=lambda x: x[1])
            elif score < top_k[-1][1]:
                top_k[-1] = (path, score)
                top_k.sort(key=lambda x: x[1])

        return [SearchResult(path=p, score=s, matched_indices=[]) for p, s in top_k]


_index: FileIndex | None = None


def _get_index() -> FileIndex:
    """获取或创建全局索引"""
    global _index
    if _index is None:
        _index = FileIndex()
    return _index


@tool(args_schema=FuzzySearchArgs)
def fuzzy_search(
    query: str,
    path: str = ".",
    file_pattern: str = "*",
    limit: int = 20
) -> str:
    """执行模糊文件搜索，使用类 fzf/nucleo 算法，返回结构化结果"""
    if not query:
        return "错误: 必须提供 query 参数"

    try:
        index = _get_index()
        index.load_from_directory(path, file_pattern)

        results = index.search(query, limit)

        if not results:
            return f"未找到匹配 '{query}' 的文件"

        fuzzy_matches = [
            FuzzyMatch(
                path=r.path,
                score=r.score,
                matched_indices=r.matched_indices
            )
            for r in results
        ]

        result = FuzzySearchResult(
            query=query,
            num_results=len(fuzzy_matches),
            matches=fuzzy_matches
        )

        return result.model_dump_json(indent=2, exclude_none=True)
    except ValueError as e:
        return f"错误: {e}"
    except Exception as e:
        return f"搜索出错: {str(e)}"
