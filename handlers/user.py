"""用户消息处理 — 访客私聊消息、/start、验证触发。"""

from typing import Any

from core.bot import ParseMode, Bot, Message, filters
from core.database import Database
from core.logger import get_logger
from services.forward import ForwardService
from services.security import SecurityService
from services.stats import StatsService
from services.verify import VerifyService

logger = get_logger("handlers.user")

# 配置键
CONFIG_WELCOME_MSG = "welcome_msg"
CONFIG_AUTO_REPLY_MSG = "auto_reply_msg"
CONFIG_UNION_BAN = "union_ban"


def register(
    bot: Bot,
    db: Database,
    forward_svc: ForwardService,
    verify_svc: VerifyService,
    security_svc: SecurityService,
    stats_svc: StatsService,
) -> None:
    """注册用户消息处理器。"""

    @bot.on_message(filters.private & ~filters.command(["start", "help", "menu"]))
    async def on_guest_message(client: Any, message: Message) -> None:
        """处理用户私聊消息（非命令）。"""
        user_id = message.from_user.id if message.from_user else message.chat.id

        # ⛔ 管理员消息跳过（管理员走 admin handler）
        if user_id in forward_svc.admin_ids:
            return

        # 白名单用户直接转发
        if await security_svc.is_whitelisted(user_id):
            await forward_svc.forward_guest_message(message)
            return

        # 检查封禁
        if await security_svc.is_banned(user_id):
            await message.reply_text("🚫 您已被管理员拉黑，无法发送消息。")
            return

        # 检查联合封禁
        union_enabled = await db.get_config(CONFIG_UNION_BAN, "0")
        if union_enabled in ("1", "true"):
            is_union_banned = await security_svc.check_union_ban(user_id)
            if is_union_banned:
                await message.reply_text(
                    "🚫 <b>您已被联合封禁。</b>\n\n您的账号因违反服务条款被全局封禁。如有疑问，请联系管理员。",
                    parse_mode=ParseMode.HTML,
                )
                return

        # 检查欺诈
        is_fraud = await security_svc.check_fraud(user_id)
        if is_fraud:
            if forward_svc.admin_uid:
                await bot.send_message(
                    forward_svc.admin_uid,
                    f"🚨 <b>检测到欺诈用户</b>\n\nUID: <code>{user_id}</code>\n该用户出现在欺诈数据库中，已自动拦截。",
                    parse_mode=ParseMode.HTML,
                )
            await message.reply_text(
                "🚫 <b>服务不可用</b>\n\n您的账号存在异常，无法使用本服务。",
                parse_mode=ParseMode.HTML,
            )
            return

        # 已验证用户
        if await db.is_verified(user_id):
            # 垃圾过滤
            spam_check = await security_svc.check_spam(message)
            if spam_check["is_spam"]:
                if forward_svc.admin_uid:
                    await bot.send_message(
                        forward_svc.admin_uid,
                        f"🗑 <b>垃圾消息拦截</b>\n\nUID: <code>{user_id}</code>\n原因: {spam_check['reason']}\n\n<i>消息已拦截，未转发给管理员</i>",
                        parse_mode=ParseMode.HTML,
                    )
                await message.reply_text("🚫 您的消息因违反规则被拦截。如有疑问请联系管理员。")
                return

            # 速率限制
            allowed = await db.check_rate_limit(f"msg:{user_id}", 5000, 5)
            if not allowed:
                await message.reply_text("⚠️ 发送过于频繁，请稍后再试。")
                return

            # 自动回复（每小时一次）
            auto_reply = await db.get_config(CONFIG_AUTO_REPLY_MSG, "")
            if auto_reply:
                autoreply_key = f"autoreply_sent:{user_id}"
                autoreply_sent = await db.get_config(autoreply_key, "")
                if not autoreply_sent:
                    await message.reply_text(auto_reply)
                    await db.set_config(autoreply_key, "1")

            await forward_svc.forward_guest_message(message)
            return

        # 未验证：暂存消息并提示验证
        queue_len = await forward_svc.append_pending(user_id, message.id)
        if queue_len >= 10:
            await message.reply_text("📝 消息已暂存，完成验证后会自动发送（最多暂存10条）")

        # 触发验证
        limit_ok = await verify_svc.check_trigger_limit(user_id)
        if limit_ok:
            challenge_id, question = verify_svc.create_challenge(user_id)
            welcome = await db.get_config(CONFIG_WELCOME_MSG, "")
            text = (
                f"{welcome}\n\n🛡 请回答以下问题以继续对话：\n\n<b>{question['q']}</b>"
                if welcome
                else f"🛡 为了防止垃圾消息，请回答以下问题：\n\n<b>{question['q']}</b>"
            )
            await bot.send_message(
                user_id,
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=verify_svc.generate_keyboard(question),
            )
        else:
            await message.reply_text("⏳ 验证尝试过于频繁，请5分钟后再试。")

    @bot.on_message(filters.private & filters.command("start"))
    async def on_start(client: Any, message: Message) -> None:
        """处理 /start 命令。"""
        user_id = message.from_user.id if message.from_user else message.chat.id

        # 白名单用户
        if await security_svc.is_whitelisted(user_id):
            await message.reply_text("👋 欢迎使用 SafeRelay！\n\n您已在白名单中，可以直接发送消息给管理员。")
            return

        # 已验证用户
        if await db.is_verified(user_id):
            auto_reply = await db.get_config(CONFIG_AUTO_REPLY_MSG, "")
            text = auto_reply or "👋 欢迎使用 SafeRelay！\n\n您已通过验证，可以直接发送消息给管理员。"
            await message.reply_text(text)
            return

        # 未验证：发送验证
        limit_ok = await verify_svc.check_trigger_limit(user_id)
        if limit_ok:
            challenge_id, question = verify_svc.create_challenge(user_id)
            welcome = await db.get_config(CONFIG_WELCOME_MSG, "")
            text = (
                f"{welcome}\n\n🛡 请回答以下问题以继续对话：\n\n<b>{question['q']}</b>"
                if welcome
                else f"🛡 为了防止垃圾消息，请回答以下问题：\n\n<b>{question['q']}</b>"
            )
            await bot.send_message(
                user_id,
                text,
                parse_mode=ParseMode.HTML,
                reply_markup=verify_svc.generate_keyboard(question),
            )
        else:
            await message.reply_text("⏳ 验证尝试过于频繁，请5分钟后再试。")

    @bot.on_message(filters.private & filters.command("help"))
    async def on_help(client: Any, message: Message) -> None:
        """处理 /help 命令。"""
        await message.reply_text(
            "🤖 <b>SafeRelay 使用说明</b>\n\n"
            "• 发送消息给机器人，消息将转发给管理员\n"
            "• 如未验证，会先进行简单问答验证\n"
            "• 管理员回复的消息会转发给您\n\n"
            "<i>如有问题请联系管理员。</i>",
            parse_mode=ParseMode.HTML,
        )

    @bot.on_edited_message(filters.private)
    async def on_guest_edit(client: Any, message: Message) -> None:
        """同步用户编辑消息到管理员。"""
        user_id = message.from_user.id if message.from_user else message.chat.id
        if user_id in forward_svc.admin_ids:
            return
        await forward_svc.sync_guest_edit(message)

    logger.info("user_handlers_registered")
