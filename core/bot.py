"""Bot 模块 — 封装 Pyrogram/Kurigram Client。

对外暴露 Bot 类以及 Message、CallbackQuery、filters 等类型，
防止 handlers/services 直接 import pyrogram。
"""

from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

# 从 pyrogram 重导出常用类型
from pyrogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Chat,
    User,
    ForumTopic,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    ForceReply,
)
from pyrogram.enums import ChatAction, ParseMode
from pyrogram import filters as _pyro_filters
from pyrogram import Client as _PyroClient
from pyrogram.handlers import MessageHandler, CallbackQueryHandler

from core.logger import get_logger

logger = get_logger("core.bot")


class Bot:
    """Bot 封装，包装 Pyrogram/Kurigram Client。"""

    def __init__(self, bot_token: str, api_id: int = 0, api_hash: str = ""):
        """初始化 Bot。

        Args:
            bot_token: Telegram Bot Token
            api_id: 可选，MTProto API ID（未提供时 Pyrogram 使用默认值）
            api_hash: 可选，MTProto API Hash
        """
        self._token = bot_token
        self._client = _PyroClient(
            name="saferelay",
            bot_token=bot_token,
            api_id=api_id or 6,
            api_hash=api_hash or "",
            in_memory=True,
        )

    # ---- 事件注册 ----

    def on_message(self, filter=None, group: int = 0) -> Callable:
        """装饰器：注册消息处理器。"""
        def decorator(func: Callable) -> Callable:
            self._client.add_handler(
                MessageHandler(func, filter),
                group,
            )
            return func
        return decorator

    def on_callback_query(self, filter=None, group: int = 0) -> Callable:
        """装饰器：注册回调查询处理器。"""
        def decorator(func: Callable) -> Callable:
            self._client.add_handler(
                CallbackQueryHandler(func, filter),
                group,
            )
            return func
        return decorator

    # ---- 消息方法 ----

    async def send_message(
        self, chat_id: Union[int, str], text: str, **kwargs
    ) -> Optional[Message]:
        """发送消息。"""
        return await self._client.send_message(chat_id, text, **kwargs)

    async def forward_messages(
        self, chat_id: Union[int, str], from_chat_id: Union[int, str],
        message_ids: Union[int, List[int]], **kwargs
    ) -> Optional[List[Message]]:
        """转发消息。"""
        if isinstance(message_ids, int):
            message_ids = [message_ids]
        result = await self._client.forward_messages(
            chat_id, from_chat_id, message_ids, **kwargs
        )
        if isinstance(result, list):
            return result
        return [result]

    async def copy_message(
        self, chat_id: Union[int, str], from_chat_id: Union[int, str],
        message_id: int, **kwargs
    ) -> Optional[Message]:
        """复制消息。"""
        return await self._client.copy_message(chat_id, from_chat_id, message_id, **kwargs)

    async def edit_message_text(
        self, chat_id: Union[int, str], message_id: int, text: str, **kwargs
    ) -> Optional[Message]:
        """编辑消息文本。"""
        return await self._client.edit_message_text(chat_id, message_id, text, **kwargs)

    async def delete_messages(
        self, chat_id: Union[int, str], message_ids: Union[int, List[int]]
    ) -> bool:
        """删除消息。"""
        if isinstance(message_ids, int):
            message_ids = [message_ids]
        return await self._client.delete_messages(chat_id, message_ids)

    async def answer_callback_query(
        self, callback_query_id: str, text: str = None, **kwargs
    ) -> bool:
        """回答回调查询。"""
        return await self._client.answer_callback_query(
            callback_query_id, text=text, **kwargs
        )

    # ---- 信息查询 ----

    async def get_chat(self, chat_id: Union[int, str]) -> Optional[Chat]:
        """获取聊天信息。"""
        return await self._client.get_chat(chat_id)

    async def get_users(self, user_ids: Union[int, str, List[Union[int, str]]]) -> Union[User, List[User]]:
        """获取用户信息。"""
        return await self._client.get_users(user_ids)

    async def get_me(self) -> Optional[User]:
        """获取机器人自身信息。"""
        return await self._client.get_me()

    # ---- 话题管理 ----

    async def create_forum_topic(
        self, chat_id: Union[int, str], title: str
    ) -> Optional[ForumTopic]:
        """创建论坛话题。"""
        return await self._client.create_forum_topic(chat_id, title)

    async def close_forum_topic(
        self, chat_id: Union[int, str], topic_id: int
    ) -> bool:
        """关闭论坛话题。"""
        return await self._client.close_forum_topic(chat_id, topic_id)

    async def reopen_forum_topic(
        self, chat_id: Union[int, str], topic_id: int
    ) -> bool:
        """重新打开论坛话题。"""
        return await self._client.reopen_forum_topic(chat_id, topic_id)

    async def edit_forum_topic(
        self, chat_id: Union[int, str], topic_id: int, title: str
    ) -> bool:
        """编辑论坛话题标题。"""
        return await self._client.edit_forum_topic(chat_id, topic_id, title)

    async def get_forum_topic(
        self, chat_id: Union[int, str], topic_id: int
    ) -> Optional[ForumTopic]:
        """获取论坛话题信息。"""
        return await self._client.get_forum_topic(chat_id, topic_id)

    async def send_chat_action(
        self, chat_id: Union[int, str], action: str
    ) -> bool:
        """发送聊天动作。"""
        return await self._client.send_chat_action(chat_id, action)

    # ---- 启动 ----

    async def start(self) -> None:
        """启动 bot（异步，用于嵌入已有事件循环）。"""
        logger.info("bot_starting", {"token_preview": self._token[:8] + "..."})
        await self._client.start()

    async def stop(self) -> None:
        """停止 bot。"""
        logger.info("bot_stopping")
        await self._client.stop()

    def run(self) -> None:
        """启动 bot（阻塞，独立运行入口）。"""
        logger.info("bot_starting", {"token_preview": self._token[:8] + "..."})
        self._client.run()

    @property
    def client(self) -> _PyroClient:
        """获取原始 Pyrogram Client（仅 core 内部使用）。"""
        return self._client


# 导出 filters 供 handlers/services 使用
filters = _pyro_filters
