import re
from typing import List

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Image, Plain
from astrbot.core.star.filter.event_message_type import EventMessageType

from .utils import extract_quoted_payload


@register(
    "wwuid_reply_enhance",
    "tyql688",
    "基于astrbot的wwuid的回复增强。",
    "1.1",
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

        pattern = r"上传.*?((面板|面包|🍞|背景)图)$"
        match = re.search(pattern, event.message_str)
        if not match:
            logger.debug(
                msg=f"wwuid_reply_enhance: {event.message_str} not match {pattern}"
            )
            return

        # 使用工具类解析引用内容 (支持普通图片和合并转发内的图片)
        image_urls = await extract_quoted_payload(event)

        if not image_urls:
            return

        # 将 URL 转换为 Image 组件
        imgs = []
        for url in image_urls:
            img = Image.fromURL(url)
            # 确保 url 字段存在，方便下游插件读取
            if not img.url:
                img.url = url
            imgs.append(img)

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
