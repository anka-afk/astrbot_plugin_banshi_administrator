import asyncio
from typing import Optional, TYPE_CHECKING
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from ..models.message_record import MessageRecord
from ..utils.rules import AdminRules

if TYPE_CHECKING:
    from ..main import Administrator


class DuplicateDetector:
    """重复消息检测器"""

    def __init__(self, administrator: "Administrator", config: dict):
        self.administrator = administrator
        self.config = config
        self.message_record = MessageRecord()
        self._cleanup_task = None
        self._reminder_tasks = {}

    @property
    def bot(self):
        """获取bot实例"""
        platform = self.administrator.platform
        if platform and hasattr(platform, "bot"):
            return platform.bot
        return None

    async def init(self):
        """初始化检测器"""
        await self.message_record.init_db()
        self._cleanup_task = asyncio.create_task(self._cleanup_scheduler())

    async def stop(self):
        """停止检测器"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        for task in self._reminder_tasks.values():
            if not task.done():
                task.cancel()
        self._reminder_tasks.clear()

    async def check_and_handle(self, event: AstrMessageEvent) -> bool:
        """检查并处理重复消息"""
        try:
            if not self.bot:
                return False

            group_id = event.message_obj.group_id
            user_id = event.message_obj.sender.user_id

            if not group_id or not user_id:
                return False

            # 检查是否在监控列表中
            curfew_list = self.config.get("curfew_list", [])
            if str(group_id) not in curfew_list:
                return False

            # 过滤系统事件和空消息
            if self._is_system_event(event):
                return False

            # 提取消息内容
            content_info = self._extract_message_content(event.message_obj.message)
            if not content_info:
                # 未知消息类型，禁言3小时
                await self._handle_ban_and_warning(
                    group_id,
                    user_id,
                    event.message_obj.message,
                    10800,
                    "检测到不支持的消息类型，已禁言3小时",
                )
                await self._recall_user_message(event.message_obj.message_id)
                return True

            content_hash, message_type, preview = content_info

            # 处理转发消息
            if content_hash.startswith("forward_async:"):
                forward_id = content_hash.split(":", 1)[1]
                forward_content = await self._get_forward_message_content(forward_id)

                if forward_content == "ADVERTISEMENT_DETECTED":
                    await self._recall_user_message(event.message_obj.message_id)
                    await self._handle_ban_and_warning(
                        group_id,
                        user_id,
                        None,
                        86400,
                        "检测到转发消息中包含群聊推荐广告，已禁言24小时",
                    )
                    return True
                elif forward_content:
                    content_hash = f"forward_content:{hash(forward_content)}"
                else:
                    content_hash = "forward:message"

            # 检查是否为重复消息
            duplicate_info = await self.message_record.check_duplicate_message(
                group_id, user_id, content_hash
            )

            if duplicate_info:
                await self._recall_user_message(event.message_obj.message_id)
                await self._handle_duplicate_message(group_id, user_id, message_type)
                return True
            else:
                await self.message_record.add_message_record(
                    group_id, user_id, content_hash, message_type, preview
                )
                return False

        except Exception as e:
            logger.error(f"检查重复消息时发生错误: {e}", exc_info=True)
            return False

    def _is_system_event(self, event: AstrMessageEvent) -> bool:
        """检查是否为系统事件"""
        try:
            raw_message = getattr(event.message_obj, "raw_message", None)
            if raw_message and isinstance(raw_message, dict):
                if raw_message.get("post_type") != "message":
                    return True

            message_chain = event.message_obj.message
            if not message_chain or len(message_chain) == 0:
                return True

            # 检查是否有实际内容
            for segment in message_chain:
                if hasattr(segment, "text") and getattr(segment, "text", "").strip():
                    return False
                component_type = self._get_component_type(segment)
                if component_type in ["image", "video", "record", "forward", "face"]:
                    return False

            return True

        except Exception as e:
            logger.error(f"检查系统事件时发生错误: {e}")
            return True

    def _extract_message_content(self, message_chain: list) -> Optional[tuple]:
        """提取消息内容用于检测"""
        if not message_chain:
            return None

        supported_types = {"plain", "text", "image", "video", "forward"}
        text_contents = []
        media_contents = []
        forward_content = None

        for segment in message_chain:
            component_type = self._get_component_type(segment)

            if component_type not in supported_types and component_type != "unknown":
                return None

            if component_type in ["plain", "text"]:
                text = self._get_text_content(segment)
                if text and text.strip():
                    text_contents.append(text.strip())
            elif component_type in ["image", "video"]:
                media_info = self._extract_media_content(segment, component_type)
                if media_info:
                    media_contents.append(media_info[0])
            elif component_type == "forward":
                forward_info = self._extract_forward_content(segment)
                if forward_info:
                    forward_content = forward_info
                    break  # 转发消息优先处理，直接返回

        # 如果有转发消息，直接返回转发消息信息
        if forward_content:
            return forward_content

        # 构建混合内容的哈希值和预览
        content_parts = []
        preview_parts = []
        message_type = "mixed"

        # 添加文字内容
        if text_contents:
            full_text = " ".join(text_contents)
            content_parts.append(f"text:{full_text}")
            preview_parts.append(f"文本:{full_text[:30]}")
            if not media_contents:  # 纯文字消息
                message_type = "text"

        # 添加媒体内容
        if media_contents:
            content_parts.extend(media_contents)
            # 统计各种媒体类型
            media_types = []
            for media in media_contents:
                media_type = media.split(":", 1)[0]
                if media_type not in media_types:
                    media_types.append(media_type)

            type_names = {
                "image": "图片",
                "video": "视频",
                "record": "语音",
            }
            media_display = "+".join([type_names.get(t, t) for t in media_types])
            preview_parts.append(media_display)

            if not text_contents:  # 纯媒体消息
                message_type = media_types[0] if len(media_types) == 1 else "mixed"

        if content_parts:
            # 使用所有内容部分生成哈希值
            content_hash = "|".join(sorted(content_parts))  # 排序确保一致性
            preview = "+".join(preview_parts)
            return content_hash, message_type, preview

        return None

    def _get_component_type(self, segment) -> str:
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

    def _get_text_content(self, segment) -> str:
        """获取文本组件的内容"""
        try:
            return getattr(segment, "text", "") if hasattr(segment, "text") else ""
        except Exception:
            return ""

    def _extract_media_content(self, segment, component_type: str) -> Optional[tuple]:
        """提取媒体组件信息"""
        try:
            for attr in ["file", "url", "path", "id"]:
                if hasattr(segment, attr):
                    value = getattr(segment, attr)
                    if value:
                        content_hash = f"{component_type}:{value}"
                        type_names = {
                            "image": "图片",
                            "video": "视频",
                            "record": "语音",
                        }
                        type_display = type_names.get(component_type, component_type)
                        preview = f"{type_display}:{str(value)[:50]}..."
                        return content_hash, component_type, preview
        except Exception:
            pass
        return None

    def _extract_forward_content(self, segment) -> Optional[tuple]:
        """提取转发消息信息"""
        try:
            if hasattr(segment, "id"):
                forward_id = getattr(segment, "id", "")
                if forward_id:
                    return (
                        f"forward_async:{forward_id}",
                        "forward",
                        f"转发消息:{forward_id[:20]}...",
                    )
        except Exception:
            pass
        return None

    async def _get_forward_message_content(self, forward_id: str) -> Optional[str]:
        """获取转发消息的实际内容"""
        try:
            if not self.bot:
                return None

            result = await self.bot.api.call_action(
                "get_forward_msg", message_id=forward_id
            )
            if not result:
                return None

            # 获取消息列表
            messages = None
            if "data" in result and isinstance(result["data"], dict):
                messages = result["data"].get("messages", [])
            elif "messages" in result:
                messages = result.get("messages", [])

            if not messages:
                return None

            # 检测广告内容
            if await self._check_for_advertisements(messages):
                return "ADVERTISEMENT_DETECTED"

            # 提取消息内容
            content_parts = []
            for msg in messages:
                if "raw_message" in msg and msg["raw_message"]:
                    content_parts.append(msg["raw_message"])
                elif "message" in msg and isinstance(msg["message"], list):
                    for msg_part in msg["message"]:
                        if msg_part.get("type") == "text" and "data" in msg_part:
                            text_data = msg_part["data"].get("text", "")
                            if text_data:
                                content_parts.append(text_data)
                        elif (
                            msg_part.get("type") in ["image", "json"]
                            and "data" in msg_part
                        ):
                            data_content = str(msg_part["data"])[:50]
                            content_parts.append(
                                f"[{msg_part.get('type')}:{data_content}]"
                            )

            return "|".join(content_parts) if content_parts else None

        except Exception as e:
            logger.error(f"获取转发消息内容失败: {e}")
            return None

    async def _check_for_advertisements(self, messages: list) -> bool:
        """检测转发消息中的广告内容"""
        try:
            ad_keywords = [
                "推荐群聊",
                "群聊推荐",
                "进群",
                "加群",
                "群号",
                "QQ群",
                "微信群",
                "telegram",
                "tg群",
                "扫码进群",
                "点击进群",
                "群二维码",
            ]

            group_card_indicators = [
                "com.tencent.troopsharecard",
                "推荐群聊",
                "contact",
                "jumpUrl",
                "qm.qq.com",
                "group_code",
            ]

            for msg in messages:
                # 检查raw_message
                if "raw_message" in msg and msg["raw_message"]:
                    raw_msg = msg["raw_message"].lower()
                    if any(keyword in raw_msg for keyword in ad_keywords):
                        return True

                # 检查message链
                if "message" in msg and isinstance(msg["message"], list):
                    for msg_part in msg["message"]:
                        if msg_part.get("type") == "text" and "data" in msg_part:
                            text_data = msg_part["data"].get("text", "").lower()
                            if any(keyword in text_data for keyword in ad_keywords):
                                return True
                        elif msg_part.get("type") == "json" and "data" in msg_part:
                            json_data = msg_part["data"].get("data", "").lower()
                            if any(
                                indicator.lower() in json_data
                                for indicator in group_card_indicators
                            ):
                                return True

            return False

        except Exception as e:
            logger.error(f"检测广告内容时发生错误: {e}")
            return False

    async def _recall_user_message(self, message_id: str):
        """撤回用户消息"""
        try:
            if message_id:
                await self.bot.api.call_action("delete_msg", message_id=message_id)
        except Exception as e:
            logger.error(f"撤回用户消息失败: {e}")

    async def _handle_ban_and_warning(
        self,
        group_id: int,
        user_id: int,
        message_chain: list,
        ban_duration: int,
        warning_msg: str,
    ):
        """通用的禁言和警告处理"""
        try:
            # 执行禁言
            await self.bot.api.call_action(
                "set_group_ban",
                group_id=group_id,
                user_id=user_id,
                duration=ban_duration,
            )

            # 发送警告消息
            send_result = await self.bot.api.call_action(
                "send_group_msg", group_id=group_id, message=warning_msg
            )

            # 安排撤回警告消息
            if isinstance(send_result, dict) and send_result.get("message_id"):
                message_id = send_result["message_id"]
                task_key = f"{group_id}_{message_id}"
                self._reminder_tasks[task_key] = asyncio.create_task(
                    self._recall_reminder(message_id, task_key)
                )

        except Exception as e:
            logger.error(f"执行禁言和警告时发生错误: {e}")

    async def _handle_duplicate_message(
        self, group_id: int, user_id: int, message_type: str
    ):
        """处理重复消息"""
        try:
            ban_duration = AdminRules.get_ban_duration(message_type)
            warning_msg = AdminRules.get_warning_message(message_type)
            await self._handle_ban_and_warning(
                group_id, user_id, None, ban_duration, warning_msg
            )
        except Exception as e:
            logger.error(f"处理重复消息时发生错误: {e}")

    async def _recall_reminder(self, message_id: int, task_key: str):
        """撤回提醒消息"""
        try:
            await asyncio.sleep(60)
            await self.bot.api.call_action("delete_msg", message_id=message_id)
        except Exception as e:
            logger.error(f"撤回消息失败: {e}")
        finally:
            self._reminder_tasks.pop(task_key, None)

    async def _cleanup_scheduler(self):
        """定期清理过期记录"""
        while True:
            try:
                await asyncio.sleep(3600)
                await self.message_record.cleanup_old_records()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理过期记录时发生错误: {e}")
