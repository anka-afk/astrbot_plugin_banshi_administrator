import asyncio
from typing import Dict
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from .base import BaseDetector
from ...utils.constants import BAN_DURATIONS, WARNING_RECALL_DELAY


class PokeDetector(BaseDetector):
    """戳一戳消息检测器"""

    def __init__(self, administrator, config):
        super().__init__(administrator, config)
        self._warning_tasks: Dict[str, asyncio.Task] = {}

    async def _init_impl(self) -> None:
        """初始化实现"""
        pass

    async def _stop_impl(self) -> None:
        """停止实现"""
        # 取消所有警告任务
        for task in self._warning_tasks.values():
            if not task.done():
                task.cancel()
        self._warning_tasks.clear()

    async def check(self, event: AstrMessageEvent) -> bool:
        """检查并处理戳一戳消息"""
        try:
            if not self.bot:
                return False

            group_id = event.message_obj.group_id
            user_id = event.message_obj.sender.user_id

            if not group_id or not user_id:
                return False

            # 检查消息链中是否包含戳一戳
            if not self._contains_poke_message(event.message_obj.message):
                return False

            # 处理戳一戳
            await self._handle_poke_ban(group_id, user_id, event.message_obj.message_id)
            logger.info(f"检测到用户 {user_id} 发送戳一戳消息，已禁言3小时")
            return True

        except Exception as e:
            logger.error(f"检查戳一戳消息时发生错误: {e}", exc_info=True)
            return False

    def _contains_poke_message(self, message_chain: list) -> bool:
        """检查消息链中是否包含戳一戳消息"""
        for segment in message_chain:
            component_type = self.get_component_type(segment)
            if component_type == "poke":
                return True

            # 检查类型字符串
            if hasattr(segment, "type"):
                type_str = str(getattr(segment, "type", ""))
                if "poke" in type_str.lower():
                    return True

        return False

    async def _handle_poke_ban(self, group_id: int, user_id: int, message_id: str):
        """处理戳一戳禁言"""
        try:
            # 撤回消息
            await self.recall_message(message_id)

            # 禁言
            ban_duration = BAN_DURATIONS.get("poke", 10800)
            await self.bot.api.call_action(
                "set_group_ban",
                group_id=group_id,
                user_id=user_id,
                duration=ban_duration,
            )

            # 发送警告
            warning_msg = self.config.get(
                "poke_warning_message",
                "⚠️ 检测到戳一戳消息，已禁言3小时。请不要使用戳一戳功能。此消息将在1分钟后撤回。",
            )

            send_result = await self.bot.api.call_action(
                "send_group_msg", group_id=group_id, message=warning_msg
            )

            # 安排撤回
            if isinstance(send_result, dict) and send_result.get("message_id"):
                warning_message_id = send_result["message_id"]
                task_key = f"poke_{group_id}_{warning_message_id}"
                self._warning_tasks[task_key] = asyncio.create_task(
                    self._recall_warning_message(warning_message_id, task_key)
                )

        except Exception as e:
            logger.error(f"处理戳一戳禁言时发生错误: {e}")

    async def _recall_warning_message(self, message_id: int, task_key: str):
        """撤回警告消息"""
        try:
            await asyncio.sleep(WARNING_RECALL_DELAY)
            await self.recall_message(str(message_id))
            logger.debug(f"已撤回戳一戳警告消息: {message_id}")
        except Exception as e:
            logger.error(f"撤回戳一戳警告消息失败: {e}")
        finally:
            self._warning_tasks.pop(task_key, None)
