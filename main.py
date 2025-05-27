import re
from typing import List

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Image, Plain, Reply
from astrbot.core.star.filter.event_message_type import EventMessageType


@register(
    "wwuid_reply_enhance",
    "tyql688",
    "基于astrbot的wwuid的回复增强。",
    "1.0.0",
    "https://github.com/tyql688/astrbot_plugin_wwuid_reply_enhance",
)
class WwuidReplyEnhance(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.prefix: List[str] = config.PREFIX  # type: ignore

    @filter.event_message_type(EventMessageType.ALL, priority=114514)
    async def on_all_message(self, event: AstrMessageEvent):
        if not any(event.message_str.startswith(prefix) for prefix in self.prefix):
            logger.debug(
                f"wwuid_reply_enhance: {event.message_str} not start with {self.prefix}"
            )
            return

        pattern = r"上传.*?面板图$"
        match = re.search(pattern, event.message_str)
        if not match:
            logger.debug(
                msg=f"wwuid_reply_enhance: {event.message_str} not match {pattern}"
            )
            return

        # 解析引用内容
        imgs = []
        for _message in event.get_messages():
            if isinstance(_message, Reply) and _message.chain:
                for comp in _message.chain:
                    if isinstance(comp, Image):
                        event.message_obj.message.append(comp)
                        imgs.append(comp)

        if not imgs:
            return

        # 开始伪造消息
        message_obj = event.message_obj
        message_obj.message = imgs
        message_obj.message.append(Plain(text=event.message_str))

        event = AstrMessageEvent(
            message_str=event.message_str,
            message_obj=message_obj,
            platform_meta=event.platform_meta,
            session_id=event.session_id,
        )

        logger.debug(
            f"wwuid_reply_enhance fake: message_str:{event.message_str}, message_obj:{event.message_obj}"
        )

        self.context.get_platform(event.get_platform_name()).commit_event(event)

        event.stop_event()
        return
