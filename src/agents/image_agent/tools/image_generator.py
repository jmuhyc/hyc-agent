"""
文本生成图像工具

使用 LangChain @tool 装饰器，遵循标准工具文档规范
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from dashscope import ImageSynthesis


class ImageGeneratorArgs(BaseModel):
    """文本生成图像工具参数"""
    prompt: str = Field(
        description="图像生成描述，描述越详细生成效果越好"
    )
    n: int = Field(
        default=1,
        description="生成图像数量"
    )
    size: str = Field(
        default="1024*1024",
        description="图像尺寸，可选 '1024*1024'、'720*1280'、'1280*720'"
    )
    negative_prompt: str = Field(
        default=None,
        description="负面提示词，指定不想出现的内容"
    )


@tool(args_schema=ImageGeneratorArgs)
def image_generator(prompt: str, n: int = 1, size: str = "1024*1024",
                    negative_prompt: str = None) -> str:
    """根据文本描述生成图像"""
    from src.config import get_wanx_model

    kwargs = {
        "model": get_wanx_model(),
        "prompt": prompt,
        "n": n,
        "size": size,
    }

    if negative_prompt:
        kwargs["negative_prompt"] = negative_prompt

    response = ImageSynthesis.call(**kwargs)

    if response.status_code != 200:
        return f"Error: 生成失败 - {response.message}"

    urls = [r.url for r in response.output.results]
    return f"成功生成 {len(urls)} 张图像:\n" + "\n".join(urls)