from typing import Optional
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from .base import BaseDetector
from ...utils.constants import BAN_DURATIONS, WARNING_RECALL_DELAY
from ...utils.rules import AdminRules
import asyncio


class ChatDetector(BaseDetector):
    """聊天内容检测器"""

    def __init__(self, administrator, config):
        super().__init__(administrator, config)
        self._warning_tasks = {}

    async def _init_impl(self) -> None:
        """初始化实现"""
        pass

    async def _stop_impl(self) -> None:
        """停止实现"""
        # 停止所有警告消息撤回任务
        for task in self._warning_tasks.values():
            if not task.done():
                task.cancel()
        self._warning_tasks.clear()

    async def check(self, event: AstrMessageEvent) -> bool:
        """检查并处理聊天消息"""
        try:
            if not self.bot:
                return False

            # 检查是否启用聊天检测
            if not self.config.get("enable_chat_detection", True):
                return False

            # 检查消息是否应该被禁言
            should_ban = await self._should_ban_chat_message(event)
            if should_ban:
                group_id = event.message_obj.group_id
                user_id = event.message_obj.sender.user_id
                await self._handle_chat_ban(
                    group_id, user_id, event.message_obj.message_id
                )
                logger.info(f"检测到用户 {user_id} 发送纯聊天内容，已禁言30分钟")
                event.stop_event()
                return True

            return False

        except Exception as e:
            logger.error(f"聊天检测时发生错误: {e}", exc_info=True)
            return False

    async def _should_ban_chat_message(self, event: AstrMessageEvent) -> bool:
        """判断聊天消息是否应该被禁言"""
        try:
            # 检查是否有文本内容
            message_text = event.message_str.strip()
            if not message_text:
                return False

            # 检查最小长度
            min_length = self.config.get("chat_detection_min_length", 2)
            if len(message_text) < min_length:
                return False

            # 明显的聊天内容
            if self._is_obviously_chat(message_text):
                return True

            # 使用 LLM 进行判断
            is_forward = await self._is_forward_content(event, message_text)
            return not is_forward  # 如果不是转发文案，就是纯聊天

        except Exception as e:
            logger.error(f"判断聊天禁言时发生错误: {e}", exc_info=True)
            return False

    async def _is_forward_content(
        self, event: AstrMessageEvent, message_text: str
    ) -> bool:
        """判断消息是否为转发文案"""
        try:
            # 获取 LLM 提供商
            provider = self.administrator.context.get_using_provider(
                umo=event.unified_msg_origin
            )

            if not provider:
                logger.warning("未找到可用的 LLM 提供商，无法进行文案检测")
                return True  # 没有LLM时默认放行

            # 如果消息过短，可能是纯聊天
            if len(message_text.strip()) < 10:
                return False

            # 构建检测提示词
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(message_text)

            # 调用 LLM 进行判断
            llm_resp = await provider.text_chat(
                prompt=user_prompt,
                context=[],
                system_prompt=system_prompt,
            )

            if llm_resp and llm_resp.result_chain:
                response_text = llm_resp.result_chain.get_plain_text().strip().lower()
                is_forward = self._parse_llm_response(response_text)
                logger.debug(
                    f"文案检测结果: 消息='{message_text[:50]}...', "
                    f"判断={'转发文案' if is_forward else '纯聊天'}, "
                    f"LLM响应='{response_text}'"
                )
                return is_forward

            logger.warning("LLM 响应为空，默认判断为转发文案")
            return True

        except Exception as e:
            logger.error(f"文案检测时发生错误: {e}", exc_info=True)
            return True

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专门判断消息类型的助手。你的任务是判断用户发送的消息是否为"转发文案"。

转发文案的特征：
1. 段子、笑话、梗图配文
2. 心灵鸡汤、励志语录
3. 广告文案、营销文字
4. 表情包配文、网络流行语
5. 长篇故事、小说片段
6. 复制粘贴的文字内容
7. 明显的转发分享内容
8. 诗词、歌词等文艺作品

纯聊天的特征：
1. 日常对话、问候
2. 询问具体问题
3. 回应他人消息
4. 表达个人感受或想法
5. 讨论当前话题
6. 个人化的交流内容

请只回答"转发文案"或"纯聊天"，不要有其他解释。"""

    def _build_user_prompt(self, message_text: str) -> str:
        """构建用户提示词"""
        return f"""请判断以下消息是"转发文案"还是"纯聊天"：

消息内容："{message_text}"

这是转发文案还是纯聊天？请回答"转发文案"或"纯聊天"。"""

    def _parse_llm_response(self, response_text: str) -> bool:
        """解析 LLM 响应结果"""
        response_text = response_text.strip().lower()

        forward_indicators = [
            "转发文案",
            "转发",
            "文案",
            "段子",
            "笑话",
            "流行语",
            "forward",
            "copy",
            "paste",
            "meme",
            "joke",
        ]

        chat_indicators = [
            "纯聊天",
            "聊天",
            "对话",
            "交流",
            "个人",
            "日常",
            "chat",
            "conversation",
            "personal",
            "daily",
        ]

        # 优先检查明确的转发文案答案
        for indicator in forward_indicators:
            if indicator in response_text:
                return True

        # 检查明确的聊天答案
        for indicator in chat_indicators:
            if indicator in response_text:
                return False

        # 无法判断，默认为转发文案
        logger.warning(f"无法解析 LLM 响应: '{response_text}'，默认为转发文案")
        return True

    def _is_obviously_chat(self, message_text: str) -> bool:
        """快速判断明显是聊天的内容"""
        # 机器人指令
        if AdminRules.is_command_message(message_text):
            return True

        # 纯数字或纯符号
        if message_text.isdigit() or all(not c.isalnum() for c in message_text):
            return True

        # 重复字符
        if len(set(message_text)) == 1 and len(message_text) > 5:
            return True

        # 测试内容
        test_patterns = ["test", "测试", "123", "abc", "。", "？", "！"]
        if message_text.lower().strip() in test_patterns:
            return True

        return False

    async def _handle_chat_ban(self, group_id: int, user_id: int, message_id: str):
        """处理聊天禁言"""
        try:
            # 撤回用户消息
            await self.recall_message(message_id)

            # 禁言30分钟
            ban_duration = BAN_DURATIONS.get("chat", 1800)
            await self.bot.api.call_action(
                "set_group_ban",
                group_id=group_id,
                user_id=user_id,
                duration=ban_duration,
            )

            # 获取聊天群配置
            chat_group_hint = self.config.get(
                "chat_group_hint", "请前往专门的聊天群进行日常交流"
            )
            warning_msg = f"⚠️ 检测到聊天内容，已禁言30分钟。{chat_group_hint}。此消息将在1分钟后撤回。"

            # 发送警告消息
            send_result = await self.bot.api.call_action(
                "send_group_msg", group_id=group_id, message=warning_msg
            )

            # 安排撤回警告消息
            if isinstance(send_result, dict) and send_result.get("message_id"):
                warning_message_id = send_result["message_id"]
                task_key = f"chat_{group_id}_{warning_message_id}"
                self._warning_tasks[task_key] = asyncio.create_task(
                    self._recall_warning_message(warning_message_id, task_key)
                )

        except Exception as e:
            logger.error(f"处理聊天禁言时发生错误: {e}")

    async def _recall_warning_message(self, message_id: int, task_key: str):
        """撤回警告消息"""
        try:
            await asyncio.sleep(WARNING_RECALL_DELAY)
            await self.recall_message(str(message_id))
            logger.debug(f"已撤回警告消息: {message_id}")
        except Exception as e:
            logger.error(f"撤回警告消息失败: {e}")
        finally:
            self._warning_tasks.pop(task_key, None)
