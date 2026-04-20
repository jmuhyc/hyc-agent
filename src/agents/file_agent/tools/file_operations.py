"""
文件操作工具：复制、移动、删除、信息获取

使用 LangChain @tool 装饰器，遵循标准工具文档规范
"""

from langchain_core.tools import tool
from pydantic import BaseModel, Field
from pathlib import Path
import shutil


class FileCopyArgs(BaseModel):
    """文件复制工具参数"""
    source: str = Field(
        description="源文件或目录的路径"
    )
    destination: str = Field(
        description="目标路径"
    )
    overwrite: bool = Field(
        default=False,
        description="是否覆盖已存在的文件"
    )


class FileMoveArgs(BaseModel):
    """文件移动工具参数"""
    source: str = Field(
        description="源文件或目录的路径"
    )
    destination: str = Field(
        description="目标路径"
    )
    overwrite: bool = Field(
        default=False,
        description="是否覆盖已存在的文件"
    )


class FileDeleteArgs(BaseModel):
    """文件删除工具参数"""
    path: str = Field(
        description="要删除的文件或目录路径"
    )
    recursive: bool = Field(
        default=False,
        description="是否递归删除目录及其内容"
    )


class FileInfoArgs(BaseModel):
    """文件信息工具参数"""
    path: str = Field(
        description="文件或目录路径"
    )


@tool(args_schema=FileCopyArgs)
def file_copy(source: str, destination: str, overwrite: bool = False) -> str:
    """复制文件或目录到新位置"""
    try:
        src_path = Path(source)
        dst_path = Path(destination)

        if not src_path.exists():
            return f"Error: 源不存在: {source}"

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if dst_path.exists() and not overwrite:
            return f"Error: 目标已存在: {destination}。使用 overwrite=True 覆盖。"

        if src_path.is_dir():
            if dst_path.exists() and overwrite:
                shutil.rmtree(dst_path)
            shutil.copytree(src_path, dst_path)
            return f"Success: 已复制目录 '{source}' 到 '{destination}'"
        else:
            if dst_path.is_dir():
                dst_path = dst_path / src_path.name
            shutil.copy2(src_path, dst_path)
            return f"Success: 已复制文件 '{source}' 到 '{dst_path}'"

    except Exception as e:
        return f"Error: 复制失败: {str(e)}"


@tool(args_schema=FileMoveArgs)
def file_move(source: str, destination: str, overwrite: bool = False) -> str:
    """移动文件或目录到新位置"""
    try:
        src_path = Path(source)
        dst_path = Path(destination)

        if not src_path.exists():
            return f"Error: 源不存在: {source}"

        dst_path.parent.mkdir(parents=True, exist_ok=True)

        if dst_path.exists():
            if overwrite:
                if dst_path.is_dir():
                    shutil.rmtree(dst_path)
                else:
                    dst_path.unlink()
            else:
                return f"Error: 目标已存在: {destination}。使用 overwrite=True 覆盖。"

        shutil.move(str(src_path), str(dst_path))
        return f"Success: 已移动 '{source}' 到 '{destination}'"

    except Exception as e:
        return f"Error: 移动失败: {str(e)}"


@tool(args_schema=FileDeleteArgs)
def file_delete(path: str, recursive: bool = False) -> str:
    """删除文件或空目录"""
    try:
        del_path = Path(path)

        if not del_path.exists():
            return f"Error: 路径不存在: {path}"

        if del_path.is_dir():
            if recursive:
                shutil.rmtree(del_path)
                return f"Success: 已删除目录及其内容: {path}"
            else:
                if any(del_path.iterdir()):
                    return f"Error: 目录非空。使用 recursive=True 递归删除。"
                del_path.rmdir()
                return f"Success: 已删除空目录: {path}"
        else:
            del_path.unlink()
            return f"Success: 已删除文件: {path}"

    except Exception as e:
        return f"Error: 删除失败: {str(e)}"


@tool(args_schema=FileInfoArgs)
def file_info(path: str) -> str:
    """获取文件或目录的详细信息"""
    try:
        info_path = Path(path)

        if not info_path.exists():
            return f"Error: 路径不存在: {path}"

        stat = info_path.stat()

        info = []
        info.append(f"路径: {info_path.resolve()}")
        info.append(f"类型: {'目录' if info_path.is_dir() else '文件'}")

        if info_path.is_file():
            info.append(f"大小: {_format_size(stat.st_size)}")

        info.append(f"修改时间: {stat.st_mtime}")

        return "\n".join(info)

    except Exception as e:
        return f"Error: 获取信息失败: {str(e)}"


def _format_size(size: int) -> str:
    """格式化文件大小为人类可读格式"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"