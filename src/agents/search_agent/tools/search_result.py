"""
搜索结果数据结构

提供结构化的搜索结果，供 LLM 进行二次理解和加工
"""

from pydantic import BaseModel, Field
from typing import Optional


class SearchMatch(BaseModel):
    """单条搜索匹配"""
    file: str = Field(description="文件路径")
    line_number: int = Field(description="行号")
    content: str = Field(description="匹配行的内容")
    context_before: Optional[str] = Field(default=None, description="前一行上下文")
    context_after: Optional[str] = Field(default=None, description="后一行上下文")


class ContentSearchResult(BaseModel):
    """内容搜索结果"""
    query: str = Field(description="搜索查询")
    num_matches: int = Field(description="匹配总数")
    num_files: int = Field(description="涉及文件数")
    matches: list[SearchMatch] = Field(description="匹配列表")
    truncated: bool = Field(default=False, description="是否被截断")


class FileMatch(BaseModel):
    """文件名匹配"""
    path: str = Field(description="文件路径")
    is_dir: bool = Field(default=False, description="是否为目录")
    size: Optional[int] = Field(default=None, description="文件大小（字节）")


class FileSearchResult(BaseModel):
    """文件搜索结果"""
    pattern: str = Field(description="搜索模式")
    num_results: int = Field(description="结果总数")
    matches: list[FileMatch] = Field(description="匹配列表")
    truncated: bool = Field(default=False, description="是否被截断")


class FuzzyMatch(BaseModel):
    """模糊匹配结果"""
    path: str = Field(description="文件路径")
    score: float = Field(description="匹配得分（越低越好，0为完美匹配）")
    matched_indices: list[int] = Field(default_factory=list, description="匹配的字符位置")


class FuzzySearchResult(BaseModel):
    """模糊搜索结果"""
    query: str = Field(description="搜索查询")
    num_results: int = Field(description="结果总数")
    matches: list[FuzzyMatch] = Field(description="匹配列表")
