"""群管理规则配置模块"""

from typing import Tuple

# 默认禁言时长（秒）
DEFAULT_BAN_DURATION = 600  # 10分钟

# 重复消息检测时间窗口（小时）
DUPLICATE_CHECK_WINDOW = 24

# 消息类型映射
MESSAGE_TYPE_NAMES = {
    "text": "文本",
    "image": "图片",
    "video": "视频",
    "forward": "聊天记录",
    "audio": "语音",
    "file": "文件",
}


class AdminRules:
    """管理规则配置类"""

    @staticmethod
    def get_ban_duration(message_type: str) -> int:
        """根据消息类型获取禁言时长（秒）"""
        durations = {
            "text": 600,  # 文本重复：10分钟
            "image": 600,  # 图片重复：10分钟
            "video": 900,  # 视频重复：15分钟
            "forward": 300,  # 聊天记录重复：5分钟
            "audio": 600,  # 语音重复：10分钟
            "file": 600,  # 文件重复：10分钟
        }
        return durations.get(message_type, DEFAULT_BAN_DURATION)

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
