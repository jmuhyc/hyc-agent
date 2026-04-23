"""
Search Agent CLI 入口

运行方式: python src/agents/search_agent/run_search_agent.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.agents.search_agent.search_agent import create_search_agent
from src.agents.search_agent.tools import content_search, glob_search, fuzzy_search


def main():
    """主函数"""
    print("=" * 60)
    print("Search Agent - 搜索式 Agent")
    print("=" * 60)
    print()

    # 创建搜索工具
    tools = [content_search, glob_search, fuzzy_search]

    # 创建 Agent
    try:
        agent = create_search_agent(tools=tools, use_deepseek=True, verbose=False)
        print("Agent 创建成功!")
        print()
        print("可用工具:")
        print("  1. content_search - 正则表达式内容搜索")
        print("  2. glob_search - glob 模式文件搜索")
        print("  3. fuzzy_search - 模糊文件搜索")
        print()
        print("输入 'quit' 或 'exit' 退出")
        print("-" * 60)
    except ValueError as e:
        print(f"配置错误: {e}")
        print("请确保在 .env 文件中设置了 DEEPSEEK_API_KEY")
        sys.exit(1)
    except Exception as e:
        print(f"Agent 创建失败: {e}")
        sys.exit(1)

    # 交互式循环
    while True:
        try:
            user_input = input("\n你: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["quit", "exit", "q"]:
                print("再见!")
                break

            print("\n思考中...")
            result = agent.run(user_input)
            print(f"\nAgent: {result}")

        except KeyboardInterrupt:
            print("\n\n再见!")
            break
        except EOFError:
            break


if __name__ == "__main__":
    main()
