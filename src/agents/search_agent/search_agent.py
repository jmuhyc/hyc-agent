"""
Search Agent 实现

基于 LangChain create_agent 的 ReAct 架构搜索 Agent
"""

from typing import List, Optional, Dict, Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.agent import BaseAgent
from src.core.llm.deepseek import DeepSeekLLM


DEFAULT_SYSTEM_PROMPT = """你是一个专业的 AI 搜索助手，善于理解用户的搜索意图并找到相关信息。

你有以下搜索工具可用：

{tools}

重要规则：
1. 理解用户的搜索需求，选择合适的搜索工具。
2. 搜索工具返回 JSON 格式的结构化结果。
3. 你需要解读这些结构化结果，理解其语义和上下文。
4. 向用户返回易于理解的总结，而非原始 JSON 数据。
5. 总结应包含：
   - 搜索到什么内容/文件
   - 相关性分析（为什么这些结果匹配用户需求）
   - 关键发现的概括性描述
6. 如果结果过多或无关，帮助用户细化搜索。

Question: {input}
Thought: {agent_scratchpad}"""


class SearchAgent(BaseAgent):
    """
    Search Agent - 搜索 Agent

    基于 LangChain create_agent，使用 ReAct 架构
    支持内容搜索、文件搜索、模糊搜索
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool] | Dict[str, Any],
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_iterations: int = 10,
        verbose: bool = True
    ):
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
        """构建包含搜索工具定义的系统提示词"""
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


def create_search_agent(
    tools: Sequence[BaseTool] | Dict[str, Any],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    use_deepseek: bool = True,
    **kwargs
) -> SearchAgent:
    """
    创建 Search Agent 的工厂函数

    Args:
        tools: LangChain BaseTool 列表或字典
        model: 模型名称（默认使用 config 中的配置）
        api_key: API 密钥
        use_deepseek: 是否使用 DeepSeek（True）或 DashScope（False）
        **kwargs: 其他参数

    Returns:
        SearchAgent: 配置好的 Agent 实例
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

    return SearchAgent(llm=llm, tools=tools, **kwargs)
