from astrbot.api.star import Star, Context, register
from astrbot.api import AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api import logger
from .core.curfew_manager import CurfewManager
from .core.duplicate_detector import DuplicateDetector
from .utils.rules import AdminRules


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
        self.curfew_manager = CurfewManager(self, config)
        self.duplicate_detector = DuplicateDetector(self, config)

    @filter.on_platform_loaded()
    async def on_platform_loaded(self):
        """平台加载完成后的初始化"""
        try:
            # 获取平台实例的初始化"""
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

            # 初始化各个功能模块
            await self._initialize_features()

        except Exception as e:
            logger.error(f"插件初始化失败: {e}", exc_info=True)

    async def _initialize_features(self):
        """初始化功能模块"""
        try:
            # 初始化重复检测器
            await self.duplicate_detector.init()
            logger.info("重复消息检测器初始化成功")

            # 启动宵禁功能
            await self.curfew_manager.start_all_curfews()
            logger.info("宵禁功能启动成功")

        except Exception as e:
            logger.error(f"功能模块初始化失败: {e}", exc_info=True)

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def handle_group_message(self, event: AstrMessageEvent):
        """处理群消息"""
        try:
            # 检查是否为系统事件
            if self._is_system_event(event):
                return

            # 重复消息检测
            is_duplicate = await self.duplicate_detector.check_and_handle(event)
            if is_duplicate:
                logger.info(f"检测到用户 {event.message_obj.sender.user_id} 的重复消息")

        except Exception as e:
            logger.error(f"处理群消息时发生错误: {e}", exc_info=True)
        # 屏蔽列表中的群消息
        group_id = event.message_obj.group_id
        curfew_list = self.config.get("curfew_list", [])
        if str(group_id) in curfew_list:
            logger.info(f"群 {group_id} 在列表中，跳过 llm 处理")
            event.stop_event()

    def _is_system_event(self, event: AstrMessageEvent) -> bool:
        """检查是否为系统事件"""
        try:
            # 首先检查原始消息类型
            raw_message = getattr(event.message_obj, "raw_message", None)
            if raw_message and isinstance(raw_message, dict):
                post_type = raw_message.get("post_type")
                # 只处理 message 类型的事件，其他都是系统事件
                if post_type != "message":
                    logger.debug(f"跳过系统事件: post_type={post_type}")
                    return True

            # 检查消息链长度
            message_chain = event.message_obj.message
            if not message_chain or len(message_chain) == 0:
                logger.debug("跳过空消息链事件")
                return True

            return False

        except Exception as e:
            logger.error(f"检查系统事件时发生错误: {e}")
            # 出错时保守处理，认为是系统事件
            return True

    async def terminate(self):
        """插件卸载时的清理工作"""
        try:
            # 停止重复检测器
            await self.duplicate_detector.stop()
            logger.info("重复消息检测器已停止")

            # 停止宵禁任务
            await self.curfew_manager.stop_all_curfews()
            logger.info("宵禁任务已停止")

        except Exception as e:
            logger.error(f"清理资源时发生错误: {e}", exc_info=True)
