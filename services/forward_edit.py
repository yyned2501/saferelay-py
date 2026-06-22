"""编辑同步逻辑 — 用户和管理员消息编辑同步。

仅在 services/forward.py 中被 ForwardService 使用。
"""
from typing import Any, Dict, Optional

from core.bot import Bot
from core.database import Database
from core.logger import get_logger

logger = get_logger("services.forward_edit")


class EditSyncManager:
    """编辑同步管理器。"""

    def __init__(self, db: Database, bot: Bot, admin_uid: Optional[int] = None):
        self.db = db
        self.bot = bot
        self.admin_uid = admin_uid

    async def sync_guest_edit(self, message: Any) -> None:
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

        kwargs: Dict[str, Any] = {"parse_mode": "HTML"}
        if target_thread:
            kwargs["message_thread_id"] = target_thread

        sent = await self.bot.send_message(target_chat, edit_text, **kwargs)
        if sent:
            await self.db.store_edit_notice(user_id, orig_msg_id, target_chat, sent.id)

    async def sync_admin_edit(self, message: Any) -> None:
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
