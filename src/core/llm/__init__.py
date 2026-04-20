"""
LLM 模块 - 语言模型接口
"""

from src.core.llm.base import BaseLLM
from src.core.llm.dashscope import DashScopeLLM

__all__ = ['BaseLLM', 'DashScopeLLM']
