# hyc-agent

AI File Operation Agent based on LangChain + Qwen (DashScope API)

## Features

A file operation AI Agent that can help you with:
- **Read/Write files** - Read content from files or create new files
- **List directories** - View contents of folders
- **Search files** - Find files by name pattern
- **Search content** - Find text inside files
- **File operations** - Copy, move, delete files and directories
- **File info** - Get detailed information about files/directories

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment:
Edit `.env` file and set your `DASHSCOPE_API_KEY`

3. Run the Agent:
```bash
python src/run.py
```

## Available Tools

| Tool | Description |
|------|-------------|
| `file_reader` | Read content from a file |
| `file_writer` | Write content to a file |
| `dir_lister` | List contents of a directory |
| `file_search` | Search for files by name pattern |
| `file_content_search` | Search for text inside files |
| `file_copy` | Copy a file or directory |
| `file_move` | Move a file or directory |
| `file_delete` | Delete a file or directory |
| `file_info` | Get information about a file/directory |

## Usage Examples

```
User: List the current directory
Agent: (lists files and folders)

User: Read README.md
Agent: (shows file content)

User: Find all Python files
Agent: (shows matching files)

User: Search for "def main" in Python files
Agent: (shows search results with line numbers)

User: Create a file called hello.txt with "Hello World"
Agent: (creates the file)
```
