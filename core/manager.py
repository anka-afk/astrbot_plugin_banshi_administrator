from typing import Dict, Optional, TYPE_CHECKING
from astrbot.api import logger
from .detectors.curfew import CurfewManager
from .detectors.duplicate import DuplicateDetector
from .detectors.chat import ChatDetector
from .detectors.poke import PokeDetector

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..main import Administrator


class DetectorManager:
    """检测器统一管理器"""

    def __init__(self, administrator: "Administrator", config: dict):
        self.administrator = administrator
        self.config = config

        # 初始化各个检测器
        self.curfew_manager = CurfewManager(administrator, config)
        self.duplicate_detector = DuplicateDetector(administrator, config)
        self.chat_detector = ChatDetector(administrator, config)
        self.poke_detector = PokeDetector(administrator, config)

        # 检测器执行顺序
        self.detectors = [
            ("poke", self.poke_detector),
            ("duplicate", self.duplicate_detector),
            ("chat", self.chat_detector),
        ]

    async def init_all(self) -> None:
        """初始化所有检测器"""
        try:
            # 初始化各个检测器
            await self.duplicate_detector.init()
            await self.curfew_manager.init()

            # 启动宵禁功能
            await self.curfew_manager.start_all_curfews()

            logger.info("所有检测器初始化完成")
        except Exception as e:
            logger.error(f"检测器初始化失败: {e}", exc_info=True)
            raise

    async def stop_all(self) -> None:
        """停止所有检测器"""
        try:
            await self.duplicate_detector.stop()
            await self.curfew_manager.stop()
            await self.poke_detector.stop()
            logger.info("所有检测器已停止")
        except Exception as e:
            logger.error(f"停止检测器时发生错误: {e}", exc_info=True)

    async def check_message(self, event: "AstrMessageEvent") -> bool:
        """
        检查消息

        Returns:
            bool: True 表示消息被拦截，False 表示正常
        """
        try:
            group_id = event.message_obj.group_id
            curfew_list = self.config.get("curfew_list", [])

            # 只处理监控列表中的群
            if str(group_id) not in curfew_list:
                return False

            # 按顺序执行检测器
            for name, detector in self.detectors:
                if await self._should_run_detector(name):
                    is_detected = await detector.check(event)
                    if is_detected:
                        logger.info(f"{name} 检测器拦截了消息")
                        return True

            return False

        except Exception as e:
            logger.error(f"检查消息时发生错误: {e}", exc_info=True)
            return False

    async def _should_run_detector(self, detector_name: str) -> bool:
        """判断是否应该运行检测器"""
        if detector_name == "poke":
            return self.config.get("enable_poke_detection", True)
        elif detector_name == "chat":
            return self.config.get("enable_chat_detection", True)
        return True

    def should_skip_llm(self, group_id: int) -> bool:
        """判断是否应该跳过LLM处理"""
        curfew_list = self.config.get("curfew_list", [])
        return str(group_id) in curfew_list
