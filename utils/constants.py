"""常量定义"""

# 默认配置
DEFAULT_CONFIG = {
    "platform_name": "napcat",
    "curfew_list": [],
    "curfew_time": "24:00",
    "curfew_last": 8,
    "enable_chat_detection": True,
    "chat_detection_min_length": 1,
    "chat_group_hint": "请前往聊天群聊天",
    "enable_poke_detection": True,
    "poke_warning_message": "⚠️ 检测到戳一戳消息，已禁言3小时。请不要使用戳一戳功能。此消息将在1分钟后撤回。",
}

# 禁言时长（秒）
BAN_DURATIONS = {
    "text": 600,  # 文本重复：10分钟
    "image": 600,  # 图片重复：10分钟
    "video": 900,  # 视频重复：15分钟
    "forward": 300,  # 聊天记录重复：5分钟
    "audio": 600,  # 语音重复：10分钟
    "file": 600,  # 文件重复：10分钟
    "chat": 1800,  # 聊天内容：30分钟
    "poke": 10800,  # 戳一戳：3小时
    "unknown": 10800,  # 未知类型：3小时
    "advertisement": 86400,  # 广告：24小时
}

# 消息类型名称映射
MESSAGE_TYPE_NAMES = {
    "text": "文本",
    "image": "图片",
    "video": "视频",
    "forward": "聊天记录",
    "audio": "语音",
    "file": "文件",
    "chat": "聊天内容",
    "poke": "戳一戳",
    "unknown": "不支持的消息类型",
    "advertisement": "广告",
}

# 警告消息撤回延迟（秒）
WARNING_RECALL_DELAY = 60

# 数据库清理间隔（秒）
DB_CLEANUP_INTERVAL = 3600

# 重复消息检测时间窗口（小时）
DUPLICATE_CHECK_WINDOW = 24

# 数据库记录保留时间（小时）
DB_RECORD_RETENTION = 25
