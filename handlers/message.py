from typing import TYPE_CHECKING
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent

if TYPE_CHECKING:
    from ..core.manager import DetectorManager


class MessageHandler:
    """消息处理器"""

    def __init__(self, detector_manager: "DetectorManager"):
        self.detector_manager = detector_manager

    async def handle_group_message(self, event: AstrMessageEvent) -> None:
        """处理群消息"""
        try:
            # 检查是否为系统事件
            if self._is_system_event(event):
                return

            # 优先执行重复消息检测
            is_duplicate = await self.detector_manager.check_duplicate_message(event)
            if is_duplicate:
                logger.info(f"群 {event.message_obj.group_id} 检测到重复消息，已处理")
                event.stop_event()  # 停止后续处理
                return

            is_blocked = await self.detector_manager.check_other_detectors(event)
            if is_blocked:
                logger.info(f"群 {event.message_obj.group_id} 消息被其他检测器拦截")

            # 判断是否跳过LLM处理
            group_id = event.message_obj.group_id
            if self.detector_manager.should_skip_llm(group_id):
                logger.info(f"群 {group_id} 在监控列表中，跳过LLM处理")
                event.stop_event()

        except Exception as e:
            logger.error(f"处理群消息时发生错误: {e}", exc_info=True)

    def _is_system_event(self, event: AstrMessageEvent) -> bool:
        """检查是否为系统事件"""
        try:
            # 检查原始消息类型
            raw_message = getattr(event.message_obj, "raw_message", None)
            if raw_message and isinstance(raw_message, dict):
                post_type = raw_message.get("post_type")
                if post_type != "message":
                    logger.debug(f"跳过系统事件: post_type={post_type}")
                    return True

            # 检查消息链
            message_chain = event.message_obj.message
            if not message_chain or len(message_chain) == 0:
                logger.debug("跳过空消息链事件")
                return True

            return False

        except Exception as e:
            logger.error(f"检查系统事件时发生错误: {e}")
            return True
