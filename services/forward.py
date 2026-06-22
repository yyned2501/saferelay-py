"""消息转发服务 — 双向转发、话题模式、媒体组、编辑同步。"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

from core.bot import Bot, InlineKeyboardMarkup, Message
from core.database import Database
from core.logger import get_logger
from utils.helpers import TTLCache

logger = get_logger("services.forward")

# 媒体组缓冲配置
MEDIA_GROUP_WAIT_MS = 300       # 等待 300ms 收集同组消息
MEDIA_GROUP_MAX_WAIT_MS = 3000  # 最长等待 3000ms


class MediaGroupCollector:
    """媒体组消息收集器。"""

    def __init__(self):
        self._buffers: Dict[str, Dict[str, Any]] = {}

    async def collect(self, msg: Message, handler) -> Any:
        """收集媒体组消息，收集完毕后执行 handler。

        Args:
            msg: 当前消息
            handler: 接收消息列表的异步函数

        Returns:
            handler 的返回值或 None（还在收集中）
        """
        group_id = msg.media_group_id
        if not group_id:
            return await handler([msg])

        buf = self._buffers.get(group_id)
        is_first = buf is None

        if is_first:
            buf = {
                "messages": [],
                "handler": handler,
                "last_update": 0,
                "event": asyncio.Event(),
                "max_deadline": time.time() + MEDIA_GROUP_MAX_WAIT_MS / 1000,
            }
            self._buffers[group_id] = buf

        buf["messages"].append(msg)
        buf["last_update"] = time.time()

        if not is_first:
            buf["event"].set()
            buf["event"].clear()
            return None

        # 首条消息：等待收集
        while True:
            remaining = buf["max_deadline"] - time.time()
            if remaining <= 0:
                break
            wait = min(MEDIA_GROUP_WAIT_MS / 1000, remaining)
            await asyncio.sleep(wait)
            # 检查是否有新消息
            since_last = time.time() - buf["last_update"]
            if since_last >= MEDIA_GROUP_WAIT_MS / 1000:
                break

        self._buffers.pop(group_id, None)
        buf["messages"].sort(key=lambda m: m.id)
        return await handler(buf["messages"])


class ForwardService:
    """消息转发服务。"""

    FORWARD_MODE_DIRECT = "direct"
    FORWARD_MODE_TOPIC = "topic"

    def __init__(self, db: Database, bot: Bot, admin_ids: List[int],
                 group_id: Optional[int] = None):
        self.db = db
        self.bot = bot
        self.admin_ids = admin_ids
        self.group_id = group_id
        self.admin_uid = admin_ids[0] if admin_ids else None
        self.media_collector = MediaGroupCollector()
        # 线程创建 In-Flight 保护
        self._topic_create_in_flight: Dict[str, asyncio.Future] = {}
        # 缓存
        self._mode_cache = TTLCache(default_ttl_ms=60000)
        self._topic_env_cache = TTLCache(default_ttl_ms=300000)
        self._topic_alert_cache = TTLCache(default_ttl_ms=600000)

    # ---- 转发模式 ----

    async def get_forward_mode(self) -> str:
        """获取转发模式。"""
        cached = self._mode_cache.get("forward_mode")
        if cached:
            return cached
        mode = await self.db.get_config("forward_mode", self.FORWARD_MODE_DIRECT)
        mode = mode if mode in (self.FORWARD_MODE_DIRECT, self.FORWARD_MODE_TOPIC) else self.FORWARD_MODE_DIRECT
        self._mode_cache.set("forward_mode", mode, 60000)
        return mode

    async def set_forward_mode(self, mode: str) -> str:
        """设置转发模式。"""
        mode = mode if mode in (self.FORWARD_MODE_DIRECT, self.FORWARD_MODE_TOPIC) else self.FORWARD_MODE_DIRECT
        await self.db.set_config("forward_mode", mode)
        self._mode_cache.set("forward_mode", mode)
        return mode

    async def is_topic_forwarding_enabled(self) -> bool:
        """检查话题转发是否启用。"""
        if not self.group_id or not self.admin_uid:
            return False
        mode = await self.get_forward_mode()
        return mode == self.FORWARD_MODE_TOPIC

    async def has_topic_prerequisites(self) -> bool:
        """检查话题模式前置条件。"""
        return bool(self.group_id and self.admin_uid)

    # ---- 话题创建和管理 ----

    async def ensure_user_topic(self, user_id: int, profile: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """确保用户有话题，如果没有则创建。"""
        if not self.group_id:
            return None

        # 检查已有映射
        thread_id = await self.db.get_user_topic(user_id)
        if thread_id:
            return {"thread_id": thread_id, "newly_created": False}

        # In-Flight 去重
        key = str(user_id)
        if key in self._topic_create_in_flight:
            try:
                return await self._topic_create_in_flight[key]
            except Exception:
                pass

        future = asyncio.get_event_loop().create_future()
        self._topic_create_in_flight[key] = future

        try:
            result = await self._ensure_user_topic_internal(user_id, profile)
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            self._topic_create_in_flight.pop(key, None)

    async def _ensure_user_topic_internal(self, user_id: int, profile: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """内部：创建用户话题。"""
        # 二次检查
        thread_id = await self.db.get_user_topic(user_id)
        if thread_id:
            return {"thread_id": thread_id, "newly_created": False}

        display_name = ""
        if profile:
            display_name = f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip()
        if not display_name:
            display_name = "访客"

        title = f"{display_name}（{user_id}）"[:60]

        try:
            topic = await self.bot.create_forum_topic(self.group_id, title)
            if not topic:
                logger.error("create_topic_failed", {"user_id": user_id})
                return None
            new_thread_id = topic.id

            await self.db.set_user_topic(user_id, new_thread_id)
            await self.db.set_thread_mapping(new_thread_id, user_id)

            # 发送欢迎消息到话题
            welcome_lines = [
                "👤 新访客对话",
                f"UID：<code>{user_id}</code>",
            ]
            if profile:
                if profile.get("username"):
                    welcome_lines.append(f"用户名：@{profile['username']}")
            welcome_lines.append("\n请在此话题内回复用户消息。")

            await self.bot.send_message(
                self.group_id,
                "\n".join(welcome_lines),
                message_thread_id=new_thread_id,
                parse_mode="HTML",
            )

            logger.info("user_topic_created", {"user_id": user_id, "thread_id": new_thread_id})
            return {"thread_id": new_thread_id, "newly_created": True}

        except Exception as e:
            logger.error("create_topic_error", {"user_id": user_id, "error": str(e)})
            return None

    # ---- 消息转发 ----

    async def forward_guest_message(self, message: Message) -> None:
        """转发用户消息到管理员或话题。"""
        if not message.from_user:
            return
        user_id = message.from_user.id
        logger.info("forward_guest_start", {"user_id": user_id})

        await self.db.increment_message_count()
        await self.db.record_active_user(user_id)

        await self.media_collector.collect(message, lambda msgs: self._do_forward(msgs, user_id))

    async def _do_forward(self, messages: List[Message], user_id: int) -> None:
        """执行转发。"""
        topic_mode = await self.is_topic_forwarding_enabled()

        if topic_mode:
            profile = {"first_name": messages[0].from_user.first_name if messages[0].from_user else "",
                       "last_name": messages[0].from_user.last_name if messages[0].from_user else "",
                       "username": messages[0].from_user.username if messages[0].from_user else ""}
            topic = await self.ensure_user_topic(user_id, profile)
            if topic and topic.get("thread_id"):
                await self._forward_to_topic(messages, user_id, topic["thread_id"])
                return

        # 私聊模式（直接转发给管理员）
        await self._forward_to_admin(messages, user_id)

    async def _forward_to_admin(self, messages: List[Message], user_id: int) -> None:
        """转发消息到管理员私聊。"""
        if not self.admin_uid:
            return
        target = {"chat_id": self.admin_uid, "label": "admin_dm"}
        for msg in messages:
            await self._forward_single(msg, user_id, target)

    async def _forward_to_topic(self, messages: List[Message], user_id: int, thread_id: int) -> None:
        """转发消息到话题。"""
        if not self.group_id:
            return
        target = {"chat_id": self.group_id, "message_thread_id": thread_id, "label": "topic"}
        for msg in messages:
            await self._forward_single(msg, user_id, target)

    async def _forward_single(self, msg: Message, user_id: int, target: Dict[str, Any]) -> Optional[Message]:
        """转发单条消息。"""
        try:
            fwd = await msg.forward(
                target["chat_id"],
                message_thread_id=target.get("message_thread_id"),
            )
            if fwd:
                await self.db.store_forward_mapping(
                    fwd.id, user_id, msg.id,
                    target.get("chat_id"), target.get("message_thread_id"),
                )
            return fwd
        except Exception as e:
            logger.error("forward_single_failed", {"user_id": user_id, "error": str(e)})
            # fallback: copy
            try:
                copy = await msg.copy(
                    target["chat_id"],
                    message_thread_id=target.get("message_thread_id"),
                )
                if copy:
                    await self.db.store_forward_mapping(
                        copy.id, user_id, msg.id,
                        target.get("chat_id"), target.get("message_thread_id"),
                    )
                return copy
            except Exception as e2:
                logger.error("copy_fallback_failed", {"user_id": user_id, "error": str(e2)})
                return None

    # ---- 管理员回复 ----

    async def handle_admin_reply(self, message: Message) -> None:
        """处理管理员回复消息。"""
        reply = message.reply_to_message
        if not reply:
            return

        guest_chat_id = None

        # 话题模式：通过话题 ID 查找用户
        if message.chat and self.group_id and str(message.chat.id) == str(self.group_id) and message.message_thread_id:
            guest_chat_id = await self.db.get_user_by_thread(message.message_thread_id)

        # 私聊模式：通过转发映射查找
        if not guest_chat_id:
            mapping = await self.db.get_forward_mapping(reply.id)
            if mapping:
                guest_chat_id = mapping["source_chat"]

        if not guest_chat_id:
            await message.reply_text("⚠️ 未找到原用户映射，可能消息太旧或被清理了缓存。")
            return

        try:
            copy = await message.copy(guest_chat_id)
            if copy:
                await self.db.store_reply_mapping(message.id, guest_chat_id, copy.id)
        except Exception as e:
            logger.error("admin_reply_failed", {"error": str(e)})
            await message.reply_text("⚠️ 回复发送失败。")

    # ---- 编辑同步 ----

    async def sync_guest_edit(self, message: Message) -> None:
        """同步用户编辑消息。"""
        orig_msg_id = message.id
        user_id = message.from_user.id if message.from_user else message.chat.id

        fwd_id = await self.db.get_original_mapping(orig_msg_id)
        if not fwd_id:
            return

        # 尝试查找已有的编辑通知并更新
        notice = await self.db.get_edit_notice(user_id, orig_msg_id)
        edit_text = f"✏️ {message.text or '(无文本内容)'}"

        if notice:
            try:
                await self.bot.edit_message_text(
                    notice["notice_chat"], notice["notice_msg_id"], edit_text,
                    parse_mode="HTML",
                )
                return
            except Exception:
                pass

        # 发送新的编辑通知
        mapping = await self.db.get_forward_mapping(fwd_id)
        target_chat = mapping["target_chat"] if mapping else self.admin_uid
        target_thread = mapping.get("thread_id")

        kwargs = {"parse_mode": "HTML"}
        if target_thread:
            kwargs["message_thread_id"] = target_thread

        sent = await self.bot.send_message(target_chat, edit_text, **kwargs)
        if sent:
            await self.db.store_edit_notice(user_id, orig_msg_id, target_chat, sent.id)

    async def sync_admin_edit(self, message: Message) -> None:
        """同步管理员编辑消息。"""
        mapping = await self.db.get_reply_mapping(message.id)
        if not mapping:
            return

        try:
            await self.bot.edit_message_text(
                mapping["guest_chat"], mapping["guest_msg_id"],
                message.text or "",
            )
        except Exception as e:
            logger.error("admin_edit_sync_failed", {"error": str(e)})

    # ---- 暂存队列 ----

    async def append_pending(self, user_id: int, message_id: int) -> int:
        """添加消息到暂存队列。"""
        return await self.db.append_pending(user_id, message_id)

    async def process_pending(self, user_id: int) -> Dict[str, int]:
        """验证通过后处理暂存消息。"""
        pending = await self.db.get_pending(user_id)
        forwarded = 0
        failed = 0

        for item in pending:
            msg_id = item["message_id"]
            try:
                topic_mode = await self.is_topic_forwarding_enabled()
                if topic_mode:
                    topic = await self.ensure_user_topic(user_id)
                    if topic and topic.get("thread_id"):
                        target = {"chat_id": self.group_id, "message_thread_id": topic["thread_id"]}
                    else:
                        target = {"chat_id": self.admin_uid}
                else:
                    target = {"chat_id": self.admin_uid}

                # 使用 Pyrogram 的 forward_messages
                await self.bot.forward_messages(
                    target["chat_id"], user_id, msg_id,
                    message_thread_id=target.get("message_thread_id"),
                )
                forwarded += 1
            except Exception as e:
                logger.error("pending_forward_failed", {"user_id": user_id, "message_id": msg_id, "error": str(e)})
                failed += 1

            await self.db.delete_pending_item(user_id, msg_id)

        if failed == 0:
            await self.db.clear_pending(user_id)

        return {"forwarded": forwarded, "failed": failed}
