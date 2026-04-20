# Image Agent - 设计文档

## 1. 概述

Image Agent 是一个基于 **ReAct (Reasoning + Acting)** 架构的 AI Agent，使用 DeepSeek 模型作为推理引擎，通过 LangChain `create_agent` 实现工具调用能力，调用阿里云万象（WANX）模型完成图像生成。

### 1.1 核心特性

- **ReAct 架构**: 基于 LangChain `create_agent` 的标准 ReAct 实现
- **DeepSeek 集成**: 使用 DeepSeek Chat 模型，通过 `bind_tools` 调用图像生成工具
- **万象 API**: 调用 DashScope 的 `ImageSynthesis.call()` 生成图像
- **循环防护**: `max_iterations=5`，防止重复调用生图工具

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         User Input                           │
│                   "画一只可爱的橘猫"                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       ImageAgent.run()                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │                   System Prompt                       │     │
│  │  - Tool definitions with Pydantic args_schema       │     │
│  │  - 重要规则：只调用一次，不要重复调用                  │     │
│  └─────────────────────────────────────────────────────┘     │
│                              │                                │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              LangChain create_agent                   │     │
│  │  - model.bind_tools(tools)                            │     │
│  │  - SystemMessage(content=prompt)                      │     │
│  └─────────────────────────────────────────────────────┘     │
│                              │                                │
│                    ┌─────────┴─────────┐                     │
│                    │  LangGraph StateGraph │                 │
│                    │  - model node (DeepSeek) │             │
│                    │  - tools node            │             │
│                    └─────────┬─────────────┘                  │
│                              │                                │
│                    ┌─────────┴─────────┐                     │
│                    │   Tool Execution   │                     │
│                    │   image_generator  │                     │
│                    │   (wanx-v1)        │                     │
│                    └─────────┬─────────┘                     │
│                              │                                │
│                    ┌─────────┴─────────┐                     │
│                    │  ImageSynthesis.call() │                │
│                    │  返回图像 URL        │                   │
│                    └───────────────────┘                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 组件说明

| 组件 | 文件 | 职责 |
|------|------|------|
| **BaseAgent** | `src/core/agent.py` | Agent 基类，基于 LangChain `create_agent` |
| **ImageAgent** | `src/agents/image_agent/image_agent.py` | 图像生成 Agent |
| **DeepSeekLLM** | `src/core/llm/deepseek.py` | LLM 推理引擎，支持 `bind_tools` |
| **ImageGenerator** | `src/agents/image_agent/tools/image_generator.py` | 文生图工具 |
| **SketchToImage** | `src/agents/image_agent/tools/sketch_to_image.py` | 草图转图像工具 |
| **ImageToImage** | `src/agents/image_agent/tools/image_to_image.py` | 图生图工具 |
| **Config** | `src/config.py` | 配置加载，环境变量 |

---

## 3. ReAct 执行流程

### 3.1 LangChain create_agent 内部流程

```
用户输入 → model node (DeepSeek 决定调用工具) → tools node (执行 image_generator)
         → ImageSynthesis.call(wanx-v1) → 返回图像 URL → model node (生成描述)
         → 返回最终结果
```

### 3.2 消息格式

```python
messages = [
    {"role": "system", "content": "你是一个专业的 AI 图像生成助手...\n{tools}"},
    {"role": "user", "content": "画一只可爱的橘猫"},
    {"role": "assistant", "content": None, "tool_calls": [{"name": "image_generator", ...}]},
    {"role": "tool", "content": "成功生成 1 张图像:\nhttps://...", "tool_call_id": "..."},
    {"role": "assistant", "content": "已为您生成一只可爱的橘猫图片！\n![橘猫](https://...)"}
]
```

---

## 4. 循环防护机制

| 机制 | 值 | 说明 |
|------|-----|------|
| **max_iterations** | 5 | 限制最大迭代次数 |
| **recursion_limit** | 10 | `max_iterations * 2`，LangGraph 节点遍历上限 |
| **GraphRecursionError** | 捕获 | 超过递归限制时返回友好错误 |

---

## 5. 工具系统

### 5.1 工具列表

| 工具名 | 模型 | 功能 | 必填参数 |
|--------|------|------|---------|
| `image_generator` | `wanx-v1` | 文本生成图像（文生图） | `prompt` |
| `image_to_image` | `wanx-v1` | 图生图（根据参考图和描述生成新图） | `image_url`, `prompt` |

### 5.2 image_generator 工具定义

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class ImageGeneratorArgs(BaseModel):
    """文本生成图像工具参数"""
    prompt: str = Field(description="图像生成描述，描述越详细生成效果越好")
    n: int = Field(default=1, description="生成图像数量")
    size: str = Field(default="1024*1024", description="图像尺寸")
    negative_prompt: str = Field(default=None, description="负面提示词")

@tool(args_schema=ImageGeneratorArgs)
def image_generator(prompt: str, n: int = 1, size: str = "1024*1024",
                    negative_prompt: str = None) -> str:
    """根据文本描述生成图像"""
    from src.config import get_wanx_model
    from dashscope import ImageSynthesis

    response = ImageSynthesis.call(
        model=get_wanx_model(),
        prompt=prompt,
        n=n,
        size=size,
        **({"negative_prompt": negative_prompt} if negative_prompt else {})
    )

    if response.status_code != 200:
        return f"Error: 生成失败 - {response.message}"

    urls = [r.url for r in response.output.results]
    return f"成功生成 {len(urls)} 张图像:\n" + "\n".join(urls)
```

### 5.3 错误处理约定

工具返回错误时，返回以 `"Error:"` 开头的字符串：

```python
if response.status_code != 200:
    return f"Error: 生成失败 - {response.message}"
```

---

## 6. LLM 接口

### 6.1 DeepSeekLLM

与 FileAgent 共用 `src/core/llm/deepseek.py`，通过 `bind_tools` 绑定图像生成工具。

---

## 7. 使用方式

### 7.1 基本使用

```python
from src.config import load_environment
from src.agents.image_agent import create_image_agent
from src.agents.image_agent.tools import image_generator

# 加载环境变量
load_environment()

# 创建 Agent
agent = create_image_agent({'image_generator': image_generator})

# 运行
result = agent.run('画一只可爱的橘猫')
print(result)
```

### 7.2 使用所有工具

```python
from src.agents.image_agent import create_image_agent
from src.agents.image_agent.tools import image_generator, sketch_to_image, image_editor

tools = {
    'image_generator': image_generator,
    'sketch_to_image': sketch_to_image,
    'image_editor': image_editor,
}

agent = create_image_agent(tools=tools)
result = agent.run('基于这张草图生成一张写实风格的风景画', sketch_image_url='...')
```

### 7.3 自定义参数

```python
agent = create_image_agent(
    tools={'image_generator': image_generator},
    model="deepseek-chat",
    max_iterations=5,
    verbose=True
)
```

---

## 8. 项目结构

```
hyc-agent/
├── src/
│   ├── config.py                  # 配置加载
│   │
│   ├── agents/
│   │   ├── file_agent/           # 文件操作 Agent
│   │   └── image_agent/          # 图像生成 Agent
│   │       ├── __init__.py
│   │       ├── image_agent.py    # Agent 实现
│   │       └── tools/            # 工具集
│   │           ├── __init__.py
│   │           ├── image_generator.py
│   │           └── image_to_image.py
│   │
│   └── core/
│       ├── agent.py              # Agent 基类
│       └── llm/
│           ├── deepseek.py       # DeepSeek 实现
│           └── dashscope.py      # DashScope 实现
│
├── tests/
├── docs/
│   ├── file_agent_design.md      # FileAgent 设计文档
│   └── image_agent_design.md     # 本文档
└── requirements.txt
```

---

## 9. 与 FileAgent 的对比

| 维度 | FileAgent | ImageAgent |
|------|----------|-----------|
| **LLM** | DeepSeek | DeepSeek |
| **工具** | 文件操作 (9个) | 图像生成 (1个) |
| **工具调用方式** | `bind_tools` + ReAct | `bind_tools` + ReAct |
| **max_iterations** | 10 | 5 |
| **API** | 本地文件系统 | DashScope 万象 API |

---

## 10. 注意事项

1. **API Key 安全**: 不要将 `.env` 文件提交到版本控制
2. **递归限制**: `max_iterations=5` 对图像生成足够，防止重复调用浪费资源
3. **模型配置**: `image_generator` 使用 `get_wanx_model()` 从配置读取，其他工具硬编码模型名
4. **输入格式**: Agent 输入必须是 `{"messages": [{"role": "user", "content": ...}]}` 格式
5. **错误处理**: 工具返回 `"Error:"` 格式的错误信息，BaseAgent.run() 会捕获并返回
