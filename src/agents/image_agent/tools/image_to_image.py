"""
图生图工具（Image-to-Image）

使用 LangChain @tool 装饰器，遵循标准工具文档规范
基于通义万相的图像生成能力，根据参考图和描述生成新图
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from dashscope import ImageSynthesis


class ImageToImageArgs(BaseModel):
    """图生图工具参数"""
    image_url: str = Field(
        description="参考图片的 URL（需公网可访问）"
    )
    prompt: str = Field(
        description="图像描述，说明想要生成什么样的图像"
    )
    n: int = Field(
        default=1,
        description="生成图像数量"
    )
    size: str = Field(
        default="1024*1024",
        description="图像尺寸，可选 '1024*1024'、'720*1280'、'1280*720'"
    )


@tool(args_schema=ImageToImageArgs)
def image_to_image(image_url: str, prompt: str, n: int = 1, size: str = "1024*1024") -> str:
    """
    根据参考图片和文字描述生成新图像

    可以对参考图进行修改、扩展、风格变化等操作。
    例如：换个背景、加个物体、改变风格、扩展画面等。
    """
    response = ImageSynthesis.call(
        model="wanx-v1",
        prompt=prompt,
        image_url=image_url,
        n=n,
        size=size
    )

    if response.status_code != 200:
        return f"Error: 生成失败 - {response.message}"

    urls = [r.url for r in response.output.results]
    return f"成功生成 {len(urls)} 张图像:\n" + "\n".join(urls)