"""
DeepSeek LLM 实现

使用 DeepSeek API 调用 DeepSeek 模型
遵循 LangChain BaseChatModel 接口，支持工具调用
"""

from typing import Optional, List, Dict, Any
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.runnables import Runnable
from pydantic import Field
from langchain_deepseek import ChatDeepSeek


class DeepSeekLLM(BaseChatModel):
    """DeepSeek 模型 LLM 实现，遵循 LangChain BaseChatModel 接口

    支持工具调用（bind_tools），可与 LangChain ReAct Agent 配合使用
    """

    model: str = Field(default="deepseek-chat", description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    temperature: float = Field(default=0.7, description="温度参数")
    max_tokens: int = Field(default=2048, description="最大 token 数")

    def _llm_type(self) -> str:
        """返回 LLM 类型标识"""
        return "deepseek"

    def _model_kwargs(self) -> Dict[str, Any]:
        """返回模型参数"""
        return {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """将 LangChain 消息转换为 DeepSeek 格式"""
        result = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                role = "user"
            elif isinstance(msg, AIMessage):
                role = "assistant"
            elif isinstance(msg, SystemMessage):
                role = "system"
            else:
                role = "user"
            result.append({"role": role, "content": msg.content})
        return result

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """生成聊天回复，LangChain 标准接口"""
        # 转换消息格式
        deepseek_messages = self._convert_messages(messages)

        # 确定 API key
        api_key = self.api_key
        if not api_key:
            import os
            api_key = os.environ.get("DEEPSEEK_API_KEY")

        # 创建 DeepSeek 客户端
        client = ChatDeepSeek(
            model=self.model,
            api_key=api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # 调用 DeepSeek API
        response = client.invoke(messages)

        # 返回 ChatResult
        if hasattr(response, 'content'):
            return ChatResult(generations=[ChatGeneration(message=response)])
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=str(response)))])

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> Runnable:
        """绑定工具，用于 LangChain Agent"""
        # 使用 DeepSeek 原生的 bind_tools
        api_key = self.api_key
        if not api_key:
            import os
            api_key = os.environ.get("DEEPSEEK_API_KEY")

        client = ChatDeepSeek(
            model=self.model,
            api_key=api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return client.bind_tools(tools, **kwargs)


def create_deepseek_llm(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> DeepSeekLLM:
    """创建 DeepSeek LLM 的工厂函数"""
    from src.config import get_deepseek_model, get_deepseek_api_key

    return DeepSeekLLM(
        model=model or get_deepseek_model(),
        api_key=api_key or get_deepseek_api_key(),
        **kwargs
    )