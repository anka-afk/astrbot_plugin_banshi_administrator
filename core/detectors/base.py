from abc import abstractmethod
from typing import Optional
from astrbot.api.event import AstrMessageEvent
from astrbot.api import logger
from ..base import BaseComponent


class BaseDetector(BaseComponent):
    """所有检测器的基类"""

    @abstractmethod
    async def check(self, event: AstrMessageEvent) -> bool:
        """
        检查消息

        Returns:
            bool: True 表示检测到问题并已处理，False 表示正常
        """
        pass

    def get_component_type(self, segment) -> str:
        """获取消息组件类型"""
        try:
            if hasattr(segment, "type"):
                component_type = getattr(segment, "type")
                if hasattr(component_type, "value"):
                    return str(component_type.value).lower()
                else:
                    return str(component_type).lower()
            return segment.__class__.__name__.lower()
        except Exception:
            return "unknown"

    async def recall_message(self, message_id: str) -> bool:
        """撤回消息"""
        try:
            if message_id and self.bot:
                await self.bot.api.call_action("delete_msg", message_id=message_id)
                return True
        except Exception as e:
            logger.error(f"撤回消息失败: {e}")
        return False
