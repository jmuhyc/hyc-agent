"""
Image Agent 实现

使用 LangChain create_agent 的 ReAct 架构图像生成 Agent
"""

from typing import List, Optional, Dict, Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from src.core.agent import BaseAgent
from src.core.llm.deepseek import DeepSeekLLM


DEFAULT_SYSTEM_PROMPT = """你是一个专业的 AI 图像生成助手。

你有以下工具可用：

{tools}

重要规则：
1. 仔细理解用户的图像需求，包括：主题、风格、颜色、氛围等。
2. 使用工具完成任务后，直接将结果返回给用户，不要重复调用相同工具。
3. 每次用户请求只需调用一次工具；如果工具返回错误，最多重试一次。
4. 返回结果时，展示图像 URL 并简要描述生成内容。
5. 如果用户需求不明确，先询问关键细节再调用工具。"""


class ImageAgent(BaseAgent):
    """
    Image Agent - 图像生成 Agent

    使用 LangChain create_agent
    """

    def __init__(
        self,
        llm: BaseChatModel,
        tools: Sequence[BaseTool] | Dict[str, Any],
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        max_iterations: int = 5,
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
        """构建包含图像工具定义的系统提示词"""
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


def create_image_agent(
    tools: Sequence[BaseTool] | Dict[str, Any],
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    use_deepseek: bool = True,
    **kwargs
) -> ImageAgent:
    """创建 ImageAgent 的工厂函数"""
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

    return ImageAgent(llm=llm, tools=tools, **kwargs)