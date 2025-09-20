from datetime import datetime, time, timedelta, timezone
from ..utils.rules import AdminRules

# 北京时区 (UTC+8)
BEIJING_TIMEZONE = timezone(timedelta(hours=8))


class CurfewInfo:
    """宵禁信息模型"""

    def __init__(self, group_id: int, start_time_str: str, duration_hours: int):
        self.group_id = group_id
        self.duration_hours = duration_hours

        # 标准化时间字符串
        normalized_time = AdminRules.normalize_time_string(start_time_str)

        # 解析开始时间
        self.start_time = datetime.strptime(normalized_time, "%H:%M").time()

        # 计算结束时间
        start_hour = self.start_time.hour
        start_minute = self.start_time.minute
        end_hour = (start_hour + duration_hours) % 24
        self.end_time = time(end_hour, start_minute)

    @property
    def start_time_str(self) -> str:
        """返回开始时间字符串"""
        if self.start_time.hour == 0 and self.start_time.minute == 0:
            return "24:00"
        return self.start_time.strftime("%H:%M")

    @property
    def end_time_str(self) -> str:
        """返回结束时间字符串"""
        return self.end_time.strftime("%H:%M")

    @property
    def is_cross_day(self) -> bool:
        """判断是否跨天"""
        return self.start_time >= self.end_time

    def is_curfew_time(self) -> bool:
        """检查当前是否在宵禁时间内"""
        now = datetime.now(BEIJING_TIMEZONE)
        current_time = now.time()

        if self.is_cross_day:
            # 跨天的情况：开始时间之后或结束时间之前
            return current_time >= self.start_time or current_time < self.end_time
        else:
            # 不跨天的情况：在开始和结束时间之间
            return self.start_time <= current_time < self.end_time

    def get_next_check_seconds(self) -> float:
        """获取到下次检查的秒数"""
        now = datetime.now(BEIJING_TIMEZONE)
        current_date = now.date()

        # 构造今天的开始和结束时间
        if self.is_cross_day:
            if now.time() < self.end_time:
                # 当前在凌晨，宵禁从昨天开始
                start_dt = datetime.combine(
                    current_date - timedelta(days=1), self.start_time
                ).replace(tzinfo=BEIJING_TIMEZONE)
                end_dt = datetime.combine(current_date, self.end_time).replace(
                    tzinfo=BEIJING_TIMEZONE
                )
            else:
                # 当前在晚上，宵禁到明天结束
                start_dt = datetime.combine(current_date, self.start_time).replace(
                    tzinfo=BEIJING_TIMEZONE
                )
                end_dt = datetime.combine(
                    current_date + timedelta(days=1), self.end_time
                ).replace(tzinfo=BEIJING_TIMEZONE)
        else:
            # 不跨天
            start_dt = datetime.combine(current_date, self.start_time).replace(
                tzinfo=BEIJING_TIMEZONE
            )
            end_dt = datetime.combine(current_date, self.end_time).replace(
                tzinfo=BEIJING_TIMEZONE
            )

        # 计算下次检查时间
        if self.is_curfew_time():
            # 在宵禁时间内，检查到结束时间
            next_check = (end_dt - now).total_seconds()
        else:
            # 不在宵禁时间内，检查到开始时间
            if now < start_dt:
                next_check = (start_dt - now).total_seconds()
            else:
                # 今天的宵禁已过，计算明天的
                next_start = start_dt + timedelta(days=1)
                next_check = (next_start - now).total_seconds()

        # 确保至少等待1秒，最多等待1小时
        return max(1, min(next_check, 3600))
