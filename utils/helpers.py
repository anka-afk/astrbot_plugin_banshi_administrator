"""辅助函数模块"""

from typing import Optional
from astrbot.api import logger


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


def format_duration(seconds: int) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds}秒"
    elif seconds < 3600:
        return f"{seconds // 60}分钟"
    elif seconds < 86400:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes > 0:
            return f"{hours}小时{minutes}分钟"
        return f"{hours}小时"
    else:
        days = seconds // 86400
        hours = (seconds % 86400) // 3600
        if hours > 0:
            return f"{days}天{hours}小时"
        return f"{days}天"


def is_command_message(text: str) -> bool:
    """判断是否为指令消息"""
    if not text:
        return False
    command_prefixes = ["//", "/", "!", "！", ".", "。"]
    return any(text.startswith(prefix) for prefix in command_prefixes)
