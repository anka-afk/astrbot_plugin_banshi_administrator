import asyncio
from typing import Dict, TYPE_CHECKING
from astrbot.api import logger
from ..models.curfew_info import CurfewInfo
from ..utils.rules import AdminRules

if TYPE_CHECKING:
    from ..main import Administrator


class CurfewTask:
    """宵禁任务类"""

    def __init__(self, manager: "CurfewManager", curfew_info: CurfewInfo):
        self.manager = manager
        self.curfew_info = curfew_info
        self.group_id = curfew_info.group_id
        self.task: asyncio.Task = None
        self.is_banned = False
        self._active = False

    @property
    def bot(self):
        """获取bot实例"""
        platform = self.manager.administrator.platform
        if platform and hasattr(platform, "bot"):
            return platform.bot
        return None

    def is_running(self) -> bool:
        """检查任务是否正在运行"""
        return self.task is not None and not self.task.done()

    async def start(self):
        """启动宵禁任务"""
        if self._active:
            logger.warning(f"群 {self.group_id} 的宵禁任务已在运行")
            return

        self._active = True
        self.task = asyncio.create_task(self._run())
        logger.info(f"群 {self.group_id} 的宵禁任务已启动")

    async def stop(self):
        """停止宵禁任务"""
        self._active = False

        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        # 如果处于禁言状态，解除禁言
        if self.is_banned and self.bot:
            try:
                payloads = {"group_id": self.group_id, "enable": False}
                await self.bot.api.call_action("set_group_whole_ban", **payloads)
                self.is_banned = False
            except Exception as e:
                logger.error(f"解除群 {self.group_id} 禁言失败: {e}")

        logger.info(f"群 {self.group_id} 的宵禁任务已停止")

    async def _run(self):
        """宵禁任务主循环"""
        while self._active:
            try:
                # 等待bot可用
                if not self.bot:
                    await asyncio.sleep(60)
                    continue

                # 检查是否在宵禁时间内
                is_curfew_time = self.curfew_info.is_curfew_time()

                if is_curfew_time and not self.is_banned:
                    await self._enable_curfew()
                elif not is_curfew_time and self.is_banned:
                    await self._disable_curfew()

                # 计算下次检查时间
                sleep_seconds = self.curfew_info.get_next_check_seconds()
                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"群 {self.group_id} 宵禁任务异常: {e}", exc_info=True)
                await asyncio.sleep(60)  # 出错后等待1分钟重试

    async def _enable_curfew(self):
        """启用宵禁"""
        try:
            # 发送宵禁开始消息（不自动撤回）
            send_payloads = {
                "group_id": self.group_id,
                "message": f"【{self.curfew_info.start_time_str}】本群宵禁开始！",
            }
            await self.bot.api.call_action("send_group_msg", **send_payloads)

            # 开启全体禁言
            ban_payloads = {"group_id": self.group_id, "enable": True}
            await self.bot.api.call_action("set_group_whole_ban", **ban_payloads)
            self.is_banned = True
            logger.info(f"群 {self.group_id} 已开启全体禁言")
        except Exception as e:
            logger.error(f"群 {self.group_id} 宵禁开启失败: {e}")

    async def _disable_curfew(self):
        """禁用宵禁"""
        try:
            # 发送宵禁结束消息（不自动撤回）
            send_payloads = {
                "group_id": self.group_id,
                "message": f"【{self.curfew_info.end_time_str}】本群宵禁结束！",
            }
            await self.bot.api.call_action("send_group_msg", **send_payloads)

            # 解除全体禁言
            ban_payloads = {"group_id": self.group_id, "enable": False}
            await self.bot.api.call_action("set_group_whole_ban", **ban_payloads)
            self.is_banned = False
            logger.info(f"群 {self.group_id} 已解除全体禁言")
        except Exception as e:
            logger.error(f"群 {self.group_id} 宵禁解除失败: {e}")


class CurfewManager:
    """宵禁管理器"""

    def __init__(self, administrator: "Administrator", config: dict):
        self.administrator = administrator
        self.config = config
        self.curfew_tasks: Dict[int, CurfewTask] = {}

    async def start_all_curfews(self):
        """启动所有宵禁任务"""
        curfew_list = self.config.get("curfew_list", [])
        curfew_time = self.config.get("curfew_time", "24:00")
        curfew_last = self.config.get("curfew_last", 8)

        # 验证配置
        is_valid, msg = AdminRules.validate_curfew_config(curfew_time, curfew_last)
        if not is_valid:
            logger.error(f"宵禁配置无效: {msg}")
            return

        if not curfew_list:
            logger.info("宵禁名单为空，不启动任何宵禁任务")
            return

        for group_id in curfew_list:
            try:
                group_id = int(group_id)
                curfew_info = CurfewInfo(
                    group_id=group_id,
                    start_time_str=curfew_time,
                    duration_hours=curfew_last,
                )

                task = CurfewTask(self, curfew_info)
                self.curfew_tasks[group_id] = task
                await task.start()

            except Exception as e:
                logger.error(f"启动群 {group_id} 宵禁任务失败: {e}", exc_info=True)

    async def stop_all_curfews(self):
        """停止所有宵禁任务"""
        for group_id, task in self.curfew_tasks.items():
            try:
                await task.stop()
            except Exception as e:
                logger.error(f"停止群 {group_id} 宵禁任务失败: {e}")

        self.curfew_tasks.clear()

    def get_curfew_task(self, group_id: int) -> CurfewTask:
        """获取指定群的宵禁任务"""
        return self.curfew_tasks.get(group_id)
