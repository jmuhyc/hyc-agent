"""
File Agent 入口文件

File Operation Agent 的交互式命令行界面
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_environment
from src.agents.file_agent import create_file_agent
from src.agents.file_agent.tools import (
    file_reader,
    file_writer,
    dir_lister,
    file_search,
    file_content_search,
    file_copy,
    file_move,
    file_delete,
    file_info,
)


def initialize_tools():
    """
    初始化文件操作工具集

    Returns:
        dict: 工具名称 -> callable 的字典
    """
    tools = {
        "file_reader": file_reader,
        "file_writer": file_writer,
        "dir_lister": dir_lister,
        "file_search": file_search,
        "file_content_search": file_content_search,
        "file_copy": file_copy,
        "file_move": file_move,
        "file_delete": file_delete,
        "file_info": file_info,
    }
    return tools


def main():
    """主函数"""
    load_environment()

    print("=" * 50)
    print("File Operation Agent 已启动")
    print("=" * 50)

    tools = initialize_tools()
    print(f"已加载 {len(tools)} 个工具: {list(tools.keys())}")

    agent = create_file_agent(tools=tools)
    print("Agent 创建成功")

    print("\n" + "=" * 50)
    print("File Operation Agent（输入 'exit' 退出）")
    print("=" * 50 + "\n")

    while True:
        try:
            user_input = input("User: ").strip()

            if user_input.lower() in ['exit', 'quit', 'q']:
                print("再见!")
                break

            if not user_input:
                continue

            print("\nAgent: ", end="", flush=True)
            response = agent.run(user_input)
            print(response)
            print()

        except KeyboardInterrupt:
            print("\n\n已退出")
            break
        except Exception as e:
            print(f"\n错误: {e}\n")


if __name__ == "__main__":
    main()
