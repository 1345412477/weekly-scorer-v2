"""文件操作工具函数"""
import os


def get_upload_dir() -> str:
    """返回 uploads 目录的绝对路径"""
    base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    upload_dir = os.path.join(base, "uploads")
    os.makedirs(upload_dir, exist_ok=True)
    return upload_dir


def is_safe_upload_path(file_path: str) -> bool:
    """检查文件路径是否在 uploads 目录下（防路径穿越）"""
    if not file_path:
        return False
    resolved_path = os.path.abspath(file_path)
    upload_dir = get_upload_dir()
    return resolved_path.startswith(upload_dir + os.sep) and os.path.isfile(resolved_path)
