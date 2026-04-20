"""
Agent 基类

基于 LangChain create_agent 的 ReAct Agent
支持 DeepSeek 等原生支持工具调用的模型
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Sequence, Optional

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool
from langchain_core.messages import SystemMessage
from langchain.agents import create_agent
from langgraph.errors import GraphRecursionError


class BaseAgent(ABC):
    """
    基于 LangChain create_agent 的 ReAct Agent

    支持使用 bind_tools 的模型（如 DeepSeek）
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool],
        system_prompt: str,
        max_iterations: int = 10,
        verbose: bool = False
    ):
        """
        初始化 Agent

        Args:
            llm: LangChain 兼容的 LLM 实例（需支持 bind_tools）
            tools: LangChain BaseTool 列表
            system_prompt: 系统提示词模板
            max_iterations: 最大迭代次数
            verbose: 是否输出详细日志
        """
        self.llm = llm
        self.tools = list(tools)
        self.system_prompt = system_prompt
        self.max_iterations = max_iterations
        self.verbose = verbose

        # 构建系统提示词
        self.prompt = self.build_system_prompt()

        # 创建 LangChain Agent
        self._agent = create_agent(
            model=llm,
            tools=self.tools,
            system_prompt=SystemMessage(content=self.prompt),
        )

    @abstractmethod
    def build_system_prompt(self) -> str:
        """构建包含工具定义的系统提示词"""
        pass

    def run(self, user_input: str) -> str:
        """
        运行 Agent 处理用户输入

        Args:
            user_input: 用户输入

        Returns:
            str: Agent 执行结果
        """
        try:
            result = self._agent.invoke(
                {"messages": [{"role": "user", "content": user_input}]},
                {"recursion_limit": self.max_iterations * 2}
            )
        except GraphRecursionError:
            return "错误：执行超过最大迭代次数，请简化请求或联系管理员。"
        except Exception as e:
            return f"错误：{str(e)}"

        # 提取输出
        if isinstance(result, dict):
            if "output" in result:
                return result["output"]
            if "messages" in result:
                messages = result["messages"]
                for msg in reversed(messages):
                    if hasattr(msg, "content") and msg.content:
                        return msg.content
                return str(messages[-1]) if messages else "无返回结果"
            return str(result)
        return str(result)