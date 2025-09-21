"""群管理规则配置模块"""

from typing import Tuple
from .constants import BAN_DURATIONS, MESSAGE_TYPE_NAMES, DEFAULT_BAN_DURATION


class AdminRules:
    """管理规则配置类"""

    @staticmethod
    def get_ban_duration(message_type: str) -> int:
        """根据消息类型获取禁言时长（秒）"""
        return BAN_DURATIONS.get(message_type, DEFAULT_BAN_DURATION)

    @staticmethod
    def get_warning_message(message_type: str) -> str:
        """获取警告消息"""
        type_name = MESSAGE_TYPE_NAMES.get(message_type, "内容")
        duration_minutes = AdminRules.get_ban_duration(message_type) // 60
        return f"⚠️ 检测到重复发送24小时内的{type_name}，已禁言{duration_minutes}分钟。此消息将在1分钟后撤回。"

    @staticmethod
    def normalize_time_string(time_str: str) -> str:
        """标准化时间字符串"""
        # 处理特殊格式
        if time_str == "24:00":
            return "00:00"

        # 处理点分格式
        if "." in time_str:
            time_str = time_str.replace(".", ":")

        # 验证并标准化格式
        parts = time_str.split(":")
        if len(parts) >= 2:
            try:
                hour = int(parts[0]) % 24
                minute = int(parts[1]) % 60
                return f"{hour:02d}:{minute:02d}"
            except ValueError:
                pass

        raise ValueError(f"无效的时间格式: {time_str}")

    @staticmethod
    def validate_curfew_config(curfew_time: str, curfew_last: int) -> Tuple[bool, str]:
        """验证宵禁配置"""
        try:
            # 验证时间格式
            normalized_time = AdminRules.normalize_time_string(curfew_time)

            # 验证持续时间
            if not isinstance(curfew_last, (int, float)):
                return False, "宵禁持续时间必须是数字"

            curfew_last = int(curfew_last)
            if curfew_last <= 0 or curfew_last > 24:
                return False, "宵禁持续时间必须在1-24小时之间"

            return True, f"配置有效：{normalized_time} 开始，持续 {curfew_last} 小时"

        except ValueError as e:
            return False, str(e)
        except Exception as e:
            return False, f"配置验证失败: {str(e)}"

    @staticmethod
    def is_command_message(text: str) -> bool:
        """判断是否为指令消息"""
        if not text:
            return False
        command_prefixes = ["//", "/", "!", "！", ".", "。"]
        return any(text.startswith(prefix) for prefix in command_prefixes)

    @staticmethod
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
