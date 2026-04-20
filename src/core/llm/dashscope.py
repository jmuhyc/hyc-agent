"""
DashScope LLM 实现

使用阿里云 DashScope API 调用 Qwen 模型
遵循 LangChain BaseChatModel 接口
支持从文本响应中解析工具调用
"""

import json
import re
from typing import Optional, List, Dict, Any, Sequence
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from pydantic import Field
from dashscope import Generation


class DashScopeLLM(BaseChatModel):
    """DashScope Qwen 模型 LLM 实现，遵循 LangChain BaseChatModel 接口

    支持工具调用：会从 LLM 响应中解析 JSON 格式的工具调用，
    并转换为 LangChain 标准的 tool_calls 格式
    """

    model: str = Field(default="qwen-max", description="模型名称")
    api_key: Optional[str] = Field(default=None, description="API密钥")
    temperature: float = Field(default=0.7, description="温度参数")
    top_p: float = Field(default=0.9, description="top_p 参数")
    max_tokens: int = Field(default=2048, description="最大 token 数")

    # 类变量：存储当前绑定的工具
    _bound_tools: Optional[List[BaseTool]] = None

    def _llm_type(self) -> str:
        """返回 LLM 类型标识"""
        return "dashscope"

    def _model_kwargs(self) -> Dict[str, Any]:
        """返回模型参数"""
        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        """将 LangChain 消息转换为 DashScope 格式"""
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

    def _parse_tool_call(self, response: str, tools: List[BaseTool]) -> Optional[Dict[str, Any]]:
        """从 LLM 响应中解析工具调用

        Args:
            response: LLM 响应文本
            tools: 可用的工具列表

        Returns:
            解析出的工具调用信息，包含 name, args, id
        """
        try:
            # 尝试直接解析 JSON
            try:
                parsed = json.loads(response)
                if isinstance(parsed, dict) and "tool" in parsed:
                    tool_name = parsed.get("tool")
                    params = parsed.get("params", {})
                    return {
                        "name": tool_name,
                        "args": params,
                        "id": f"call_{tool_name}_{hash(str(params))}"
                    }
            except json.JSONDecodeError:
                pass

            # 处理转义的双花括号
            def unescape_braces(s):
                result = []
                i = 0
                while i < len(s):
                    if i < len(s) - 1 and s[i] == '{' and s[i+1] == '{':
                        result.append('{')
                        i += 2
                    elif i < len(s) - 1 and s[i] == '}' and s[i+1] == '}':
                        result.append('}')
                        i += 2
                    else:
                        result.append(s[i])
                        i += 1
                return ''.join(result)

            unescaped = unescape_braces(response)
            if unescaped != response:
                try:
                    parsed = json.loads(unescaped)
                    if isinstance(parsed, dict) and "tool" in parsed:
                        tool_name = parsed.get("tool")
                        params = parsed.get("params", {})
                        return {
                            "name": tool_name,
                            "args": params,
                            "id": f"call_{tool_name}_{hash(str(params))}"
                        }
                except json.JSONDecodeError:
                    pass

            # 使用括号匹配查找包含 "tool" 的 JSON 对象
            for search_str in ['"tool"', "'tool'"]:
                tool_pos = response.find(search_str)
                if tool_pos == -1:
                    continue

                start = response.rfind('{', 0, tool_pos)
                if start == -1:
                    continue

                depth = 0
                end = None
                for i in range(start, len(response)):
                    c = response[i]
                    if c == '{':
                        depth += 1
                    elif c == '}':
                        depth -= 1
                        if depth == 0:
                            end = i + 1
                            break

                if end is not None:
                    try:
                        json_str = response[start:end]
                        parsed = json.loads(json_str)
                        if isinstance(parsed, dict) and "tool" in parsed:
                            tool_name = parsed.get("tool")
                            params = parsed.get("params", {})
                            # 验证工具是否存在
                            tool_names = {t.name for t in tools}
                            if tool_name in tool_names:
                                return {
                                    "name": tool_name,
                                    "args": params,
                                    "id": f"call_{tool_name}_{hash(str(params))}"
                                }
                    except json.JSONDecodeError:
                        continue

        except Exception:
            pass

        return None

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any
    ) -> ChatResult:
        """生成聊天回复，LangChain 标准接口"""
        # 转换消息格式
        dashscope_messages = self._convert_messages(messages)

        # 确定 API key
        api_key = self.api_key
        if not api_key:
            import os
            api_key = os.environ.get("DASHSCOPE_API_KEY")

        # 调用 DashScope API
        response = Generation.call(
            model=self.model,
            messages=dashscope_messages,
            api_key=api_key,
            result_format='message',
            **self._model_kwargs(),
            **kwargs
        )

        if response.status_code != 200:
            raise ValueError(f"API 调用失败: {response.code} - {response.message}")

        content = response.output['choices'][0]['message']['content']

        # 检查是否有绑定的工具
        tools = self._bound_tools or []

        # 尝试解析工具调用
        tool_call = self._parse_tool_call(content, tools)

        if tool_call:
            # 返回带有工具调用的响应
            return ChatResult(generations=[ChatGeneration(
                message=AIMessage(
                    content=content,
                    tool_calls=[tool_call]
                )
            )])

        # 返回普通响应
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    def bind_tools(self, tools: List[Any], **kwargs: Any) -> Runnable:
        """绑定工具，用于 LangChain Agent"""
        # 存储绑定的工具
        self._bound_tools = [t for t in tools if isinstance(t, BaseTool)]
        return self


def create_dashscope_llm(
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> DashScopeLLM:
    """创建 DashScope LLM 的工厂函数"""
    from src.config import get_dashscope_model, get_dashscope_api_key

    return DashScopeLLM(
        model=model or get_dashscope_model(),
        api_key=api_key or get_dashscope_api_key(),
        **kwargs
    )