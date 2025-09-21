from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
from astrbot.api import logger

if TYPE_CHECKING:
    from astrbot.api.event import AstrMessageEvent
    from ..main import Administrator


class BaseComponent(ABC):
    """所有组件的基类"""

    def __init__(self, administrator: "Administrator", config: dict):
        self.administrator = administrator
        self.config = config
        self._initialized = False

    @property
    def bot(self):
        """获取bot实例"""
        platform = self.administrator.platform
        if platform and hasattr(platform, "bot"):
            return platform.bot
        return None

    async def init(self) -> None:
        """初始化组件"""
        if self._initialized:
            return
        await self._init_impl()
        self._initialized = True
        logger.info(f"{self.__class__.__name__} 初始化成功")

    async def stop(self) -> None:
        """停止组件"""
        if not self._initialized:
            return
        await self._stop_impl()
        self._initialized = False
        logger.info(f"{self.__class__.__name__} 已停止")

    @abstractmethod
    async def _init_impl(self) -> None:
        """子类实现的初始化逻辑"""
        pass

    @abstractmethod
    async def _stop_impl(self) -> None:
        """子类实现的停止逻辑"""
        pass
