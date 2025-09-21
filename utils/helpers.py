"""辅助函数模块"""

from typing import Optional


def safe_int(value: any, default: int = 0) -> int:
    """安全转换为整数"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_str(value: any, default: str = "") -> str:
    """安全转换为字符串"""
    try:
        return str(value)
    except Exception:
        return default


def truncate_text(text: str, max_length: int = 50) -> str:
    """截断文本"""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."
