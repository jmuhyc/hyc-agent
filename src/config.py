"""
hyc-agent 配置模块
"""

import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent


def load_environment():
    """加载 .env 环境变量"""
    env_file = BASE_DIR / '.env'
    if env_file.exists():
        load_dotenv(env_file)
    else:
        raise FileNotFoundError(f'.env 文件未找到: {env_file}')


def get_dashscope_api_key() -> str:
    """获取 DashScope API 密钥"""
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    if not api_key:
        raise ValueError('DASHSCOPE_API_KEY 未在 .env 文件中设置')
    return api_key


def get_dashscope_model() -> str:
    """获取 DashScope 模型名称"""
    return os.environ.get('DASHSCOPE_MODEL', 'qwen-max')


def get_wanx_model() -> str:
    """获取图像生成模型名称"""
    return os.environ.get('WANX_MODEL', 'wanx-v1')


def get_deepseek_api_key() -> str:
    """获取 DeepSeek API 密钥"""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        raise ValueError('DEEPSEEK_API_KEY 未在 .env 文件中设置')
    return api_key


def get_deepseek_model() -> str:
    """获取 DeepSeek 模型名称"""
    return os.environ.get('DEEPSEEK_MODEL', 'deepseek-chat')
