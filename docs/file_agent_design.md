# File Agent - 设计文档

## 1. 概述

File Agent 是一个基于 **ReAct (Reasoning + Acting)** 架构的 AI Agent，使用 DeepSeek 模型作为推理引擎，通过 LangChain `create_agent` 实现工具调用能力。

### 1.1 核心特性

- **ReAct 架构**: 基于 LangChain `create_agent` 的标准 ReAct 实现
- **DeepSeek 集成**: 使用 DeepSeek Chat 模型，支持原生 `bind_tools`
- **LangChain 兼容**: 遵循 LangChain 工具调用标准，使用 Pydantic 定义工具参数
- **工具扩展**: 支持动态注册新工具

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                         User Input                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       FileAgent.run()                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐     │
│  │                   System Prompt                       │     │
│  │  - Tool definitions with Pydantic args_schema       │     │
│  │  - Parameter descriptions via Field(description=)    │     │
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
│                    │  - model node (LLM)   │                 │
│                    │  - tools node          │                 │
│                    └─────────┬─────────────┘                  │
│                              │                                │
│                    ┌─────────┴─────────┐                     │
│                    │   Tool Execution   │                     │
│                    │   (9 file tools)   │                     │
│                    └───────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 组件说明

| 组件 | 文件 | 职责 |
|------|------|------|
| **BaseAgent** | `src/core/agent.py` | Agent 基类，基于 LangChain `create_agent` |
| **FileAgent** | `src/agents/file_agent/file_agent.py` | 文件操作 Agent |
| **DeepSeekLLM** | `src/core/llm/deepseek.py` | LLM 封装，DeepSeek API + `bind_tools` |
| **Tool Functions** | `src/agents/file_agent/tools/*.py` | 文件操作工具集 |
| **Config** | `src/config.py` | 配置加载，环境变量 |

---

## 3. ReAct 执行流程

### 3.1 LangChain create_agent 内部流程

LangChain `create_agent` 创建一个 LangGraph StateGraph，包含以下节点：

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Input                              │
│           {"messages": [{"role": "user", "content": ...}]}  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      model Node                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ 1. LLM receives messages                             │    │
│  │ 2. LLM.call(messages) with bound tools               │    │
│  │ 3. If response contains tool_calls → continue       │    │
│  │ 4. If response is direct answer → stop               │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
              tool_calls          no tool_calls
                    │                     │
                    ▼                     ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│        tools Node         │   │        Return           │
│  ┌────────────────────┐  │   │   last AIMessage        │
│  │ 1. Execute tools   │  │   └──────────────────────────┘
│  │ 2. Return ToolMessage │
│  └────────────────────┘  │
└──────────┬───────────────┘
           │
           ▼
    ┌──────────────┐
    │ model Node   │ ← loops until no tool_calls
    └──────────────┘
```

### 3.2 消息格式

```python
messages = [
    {"role": "system", "content": "You are a file operation assistant...\n{tools}"},
    {"role": "user", "content": "Read the file hello.txt"},
    {"role": "assistant", "content": None, "tool_calls": [...]},
    {"role": "tool", "content": "Hello World", "tool_call_id": "..."},
    {"role": "assistant", "content": "The content of hello.txt is: Hello World"}
]
```

---

## 4. 循环防护机制

LangChain `create_agent` 内置循环防护：

| 机制 | 说明 |
|------|------|
| **recursion_limit** | 通过 `invoke(..., {"recursion_limit": N})` 控制最大迭代次数 |
| **tool_calls 检测** | 当 LLM 响应不包含 `tool_calls` 时停止循环 |

---

## 5. 工具系统

### 5.1 工具列表

| 工具名 | 功能 | 参数 |
|--------|------|------|
| `file_reader` | 读取文件 | `file_path`, `max_lines`, `encoding` |
| `file_writer` | 写入文件 | `file_path`, `content`, `encoding`, `append` |
| `dir_lister` | 列出目录 | `path`, `recursive`, `include_hidden` |
| `file_search` | 搜索文件 | `directory`, `pattern`, `case_sensitive` |
| `file_content_search` | 搜索内容 | `directory`, `keyword`, `file_pattern`, `case_sensitive`, `max_results` |
| `file_copy` | 复制文件 | `source`, `destination`, `overwrite` |
| `file_move` | 移动文件 | `source`, `destination`, `overwrite` |
| `file_delete` | 删除文件 | `path`, `recursive` |
| `file_info` | 文件信息 | `path` |

### 5.2 工具定义示例

```python
from langchain_core.tools import tool
from pydantic import BaseModel, Field

class FileWriterArgs(BaseModel):
    """文件写入工具参数"""
    file_path: str = Field(description="文件路径（绝对路径或相对于当前目录）")
    content: str = Field(description="要写入的文本内容")
    encoding: str = Field(default="utf-8", description="文件编码（默认 utf-8）")
    append: bool = Field(default=False, description="若为 True，则追加到现有文件；否则覆盖")

@tool(args_schema=FileWriterArgs)
def file_writer(file_path: str, content: str, encoding: str = "utf-8", append: bool = False) -> str:
    """将文本内容写入文件"""
    # Implementation...
```

### 5.3 错误处理约定

工具返回错误时，必须返回以 `"Error:"` 开头的字符串：

```python
if not path.exists():
    return f"Error: File not found: {file_path}"
```

---

## 6. LLM 接口

### 6.1 DeepSeekLLM

```python
class DeepSeekLLM(BaseChatModel):
    """DeepSeek 模型 LLM 实现，遵循 LangChain BaseChatModel 接口"""

    model: str = Field(default="deepseek-chat")
    api_key: Optional[str] = Field(default=None)
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=2048)

    def bind_tools(self, tools: List[Any], **kwargs) -> Runnable:
        """绑定工具，用于 LangChain Agent"""
        client = ChatDeepSeek(model=self.model, api_key=self.api_key, ...)
        return client.bind_tools(tools, **kwargs)
```

---

## 7. 使用方式

### 7.1 基本使用

```python
from src.config import load_environment
from src.agents.file_agent import create_file_agent
from src.agents.file_agent.tools import file_reader, file_writer, dir_lister

# 加载环境变量
load_environment()

# 创建 Agent
tools = {'file_reader': file_reader, 'file_writer': file_writer}
agent = create_file_agent(tools=tools)

# 运行
result = agent.run("Read the file hello.txt")
print(result)
```

### 7.2 自定义参数

```python
agent = create_file_agent(
    tools=tools,
    model="deepseek-chat",
    max_iterations=15,
    verbose=True
)
```

---

## 8. 项目结构

```
hyc-agent/
├── src/
│   ├── config.py              # 配置加载
│   │
│   ├── agents/                # Agent 集合
│   │   ├── __init__.py
│   │   └── file_agent/        # 文件操作 Agent
│   │       ├── __init__.py
│   │       ├── file_agent.py  # Agent 实现
│   │       └── tools/         # Agent 专属工具
│   │           ├── __init__.py
│   │           ├── file_reader.py
│   │           ├── file_writer.py
│   │           ├── dir_lister.py
│   │           ├── file_search.py
│   │           ├── file_content_search.py
│   │           └── file_operations.py
│   │
│   └── core/                  # 共享核心模块
│       ├── __init__.py
│       ├── agent.py           # Agent 基类 (LangChain create_agent)
│       └── llm/
│           ├── __init__.py
│           ├── base.py        # LLM 基类
│           ├── deepseek.py    # DeepSeek 实现
│           └── dashscope.py   # DashScope 实现 (Qwen)
│
├── tests/
│   └── test_agent_integration.py    # Agent 集成测试
├── docs/
│   └── file_agent_design.md # 本文档
├── requirements.txt
└── README.md
```

---

## 9. 未来扩展

### 9.1 可扩展方向

1. **ImageAgent**: 添加图像生成 Agent，使用万象模型
2. **更多工具**: 添加网络搜索、代码执行、数据库操作等
3. **多模态**: 支持图片、音频处理
4. **记忆系统**: 添加长期记忆和上下文管理
5. **多 Agent 协作**: 多个 Agent 分工合作
6. **Web UI**: 添加 Gradio 或 FastAPI 界面

### 9.2 添加新 Agent

```python
from src.core.agent import BaseAgent
from src.core.llm.deepseek import DeepSeekLLM

class NewAgent(BaseAgent):
    def build_system_prompt(self) -> str:
        return self.system_prompt.replace("{tools}", self._get_tool_schemas())

def create_new_agent(tools, **kwargs):
    llm = DeepSeekLLM()
    return NewAgent(llm=llm, tools=tools, **kwargs)
```

---

## 10. 注意事项

1. **API Key 安全**: 不要将 `.env` 文件提交到版本控制
2. **递归限制**: `max_iterations` 控制最大循环次数，默认 10
3. **错误处理**: 所有工具应返回 `"Error:"` 格式的错误信息
4. **参数描述**: 使用 Pydantic `Field(description=...)` 描述参数，供 LLM 理解
5. **输入格式**: Agent 输入必须是 `{"messages": [{"role": "user", "content": ...}]}` 格式
