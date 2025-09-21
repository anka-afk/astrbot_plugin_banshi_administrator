"""常量定义"""

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

# 默认禁言时长（秒）
DEFAULT_BAN_DURATION = 600  # 10分钟
