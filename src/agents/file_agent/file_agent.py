"""
File Agent 实现

使用 LangChain create_agent 的 ReAct 架构文件操作 Agent
"""

from typing import List, Optional, Dict, Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.agent import BaseAgent
from src.core.llm.deepseek import DeepSeekLLM


DEFAULT_SYSTEM_PROMPT = """你是一个专业的 AI 文件操作助手。

你有以下工具可用：

{tools}

重要规则：
1. 仔细理解用户的文件操作需求。
2. 使用合适的工具完成任务。
3. 如果任务完成，返回结果。
4. 如果工具失败，尝试其他方法。

Question: {input}
Thought: {agent_scratchpad}"""


class FileAgent(BaseAgent):
    """
    File Agent - 文件操作 Agent

    使用 LangChain create_agent
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool] | Dict[str, Any],
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_iterations: int = 10,
        verbose: bool = True
    ):
        # 兼容字典格式的工具
        if isinstance(tools, dict):
            tools_list = list(tools.values())
        elif isinstance(tools, list):
            tools_list = tools
        else:
            tools_list = list(tools)

        super().__init__(
            llm=llm,
            tools=tools_list,
            system_prompt=system_prompt,
            max_iterations=max_iterations,
            verbose=verbose
        )

    def build_system_prompt(self) -> str:
        """构建包含文件工具定义的系统提示词"""
        tool_schemas = []
        for tool in self.tools:
            if hasattr(tool, 'name'):
                name = tool.name
                desc = getattr(tool, 'description', None) or "无描述"
                args_schema = getattr(tool, 'args_schema', None)
                if args_schema:
                    try:
                        schema = args_schema.model_json_schema()
                        params = []
                        for param_name, param_info in schema.get('properties', {}).items():
                            param_desc = param_info.get('description', '无描述')
                            required = param_name in schema.get('required', [])
                            req_mark = "(必填)" if required else "(可选)"
                            params.append(f"    - {param_name}: {param_desc} {req_mark}")
                        params_str = "\n".join(params) if params else "    无"
                        tool_schemas.append(f"- {name}:\n  {desc}\n  参数:\n{params_str}")
                    except Exception:
                        tool_schemas.append(f"- {name}: {desc}")
                else:
                    tool_schemas.append(f"- {name}: {desc}")

        tools_str = "\n\n".join(tool_schemas) if tool_schemas else "无可用工具"
        return self.system_prompt.replace("{tools}", tools_str)


def create_file_agent(
    tools: Sequence[BaseTool] | Dict[str, Any],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    use_deepseek: bool = True,
    **kwargs
) -> FileAgent:
    """
    创建 File Agent 的工厂函数

    Args:
        tools: LangChain BaseTool 列表或字典
        model: 模型名称（默认使用 config 中的配置）
        api_key: API 密钥
        use_deepseek: 是否使用 DeepSeek（True）或 DashScope（False）
        **kwargs: 其他参数

    Returns:
        FileAgent: 配置好的 Agent 实例
    """
    if use_deepseek:
        from src.config import get_deepseek_model, get_deepseek_api_key
        llm = DeepSeekLLM(
            model=model or get_deepseek_model(),
            api_key=api_key or get_deepseek_api_key()
        )
    else:
        from src.core.llm.dashscope import DashScopeLLM
        from src.config import get_dashscope_model, get_dashscope_api_key
        llm = DashScopeLLM(
            model=model or get_dashscope_model(),
            api_key=api_key or get_dashscope_api_key()
        )

    return FileAgent(llm=llm, tools=tools, **kwargs)