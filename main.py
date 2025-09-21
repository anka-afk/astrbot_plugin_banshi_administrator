from astrbot.api.star import Star, Context, register
from astrbot.api import AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from .core.manager import DetectorManager
from .handlers.message import MessageHandler


@register(
    "banshi_administrator",
    "anka",
    "搬史群管理插件",
    "1.0.0",
    "https://github.com/anka/astrbot_plugin_banshi_administrator",
)
class Administrator(Star):
    """搬史群管理插件主类"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.platform = None
        self.detector_manager = DetectorManager(self, config)
        self.message_handler = MessageHandler(self.detector_manager)

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成后的初始化"""
        try:
            # 获取平台实例
            platform_name = self.config.get("platform_name", "napcat")
            try:
                self.platform = self.context.get_platform_inst(platform_name)
                logger.info(f"成功加载平台: {platform_name}")
            except Exception as e:
                logger.warning(f"未能加载平台 {platform_name}: {e}")
                return

            if not self.platform:
                logger.warning("平台未成功加载，插件功能将受限")
                return

            # 初始化检测器管理器
            await self.detector_manager.init_all()
            logger.info("搬史群管理插件初始化完成")

        except Exception as e:
            logger.error(f"插件初始化失败: {e}", exc_info=True)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE, priority=10000000)
    async def handle_group_message(self, event: AstrMessageEvent):
        """处理群消息"""
        await self.message_handler.handle_group_message(event)

    async def terminate(self):
        """插件卸载时的清理工作"""
        try:
            await self.detector_manager.stop_all()
            logger.info("搬史群管理插件已停止")
        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}", exc_info=True)
