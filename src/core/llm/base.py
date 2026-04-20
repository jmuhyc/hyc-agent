"""
LLM 基类接口

注意：已迁移到 LangChain 接口，推荐直接使用 BaseChatModel
"""

from abc import ABC, abstractmethod
from typing import List, Dict


class BaseLLM(ABC):
    """LLM 实现基类（已弃用，推荐使用 LangChain BaseChatModel）"""

    @abstractmethod
    def invoke(self, messages: List[Dict[str, str]]) -> str:
        """
        调用 LLM

        Args:
            messages: 消息列表，每条消息包含 'role' 和 'content'

        Returns:
            str: LLM 返回的文本
        """
        pass

    def __call__(self, messages: List[Dict[str, str]]) -> str:
        """简易调用接口"""
        return self.invoke(messages)