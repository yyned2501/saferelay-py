"""回调查询处理 — 验证答案、管理菜单导航。"""

from typing import Any

from core.bot import Bot, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, filters
from core.database import Database
from core.logger import get_logger
from services.forward import ForwardService
from services.security import SecurityService
from services.stats import StatsService
from services.verify import VerifyService

logger = get_logger("handlers.callback")

CONFIG_WELCOME_MSG = "welcome_msg"
CONFIG_UNION_BAN = "union_ban"


def register(
    bot: Bot,
    db: Database,
    forward_svc: ForwardService,
    verify_svc: VerifyService,
    security_svc: SecurityService,
    stats_svc: StatsService,
) -> None:
    """注册回调查询处理器。"""

    ### ---- 验证答案回调 ---- ###

    @bot.on_callback_query(filters.regex(r"^quiz_answer:"))
    async def on_quiz_answer(client: Any, callback: CallbackQuery) -> None:
        """处理验证答案提交。"""
        user_id = callback.from_user.id
        data = callback.data

        # 解析答案索引
        try:
            answer_index = int(data.split(":")[1])
        except (IndexError, ValueError):
            await callback.answer("❌ 无效的选项", show_alert=True)
            return

        # 验证锁
        locked = await db.acquire_verify_lock(user_id, 60)
        if not locked:
            await callback.answer("⏳ 验证进行中，请稍后再试", show_alert=True)
            return

        try:
            result = verify_svc.verify_answer(user_id, answer_index)

            if result["success"]:
                # 验证成功
                display_name = callback.from_user.first_name or callback.from_user.username or "Unknown"
                await db.mark_verified(user_id, display_name)

                # 处理暂存消息
                pending_result = await forward_svc.process_pending(user_id)

                # 更新验证消息
                success_text = "✅ 验证成功！您现在可以发送消息给管理员了。"
                if pending_result["forwarded"] > 0:
                    success_text = f"✅ 验证成功！\n\n📩 刚才的 {pending_result['forwarded']} 条消息已送达管理员。"

                try:
                    await bot.edit_message_text(
                        callback.message.chat.id,
                        callback.message.id,
                        success_text,
                        reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
                    )
                except Exception as e:
                    logger.error("edit_verify_message_failed", {"error": str(e)})

                # 发送欢迎消息
                if pending_result["forwarded"] == 0:
                    welcome = await db.get_config(CONFIG_WELCOME_MSG, "")
                    if welcome:
                        await bot.send_message(user_id, welcome)

                await stats_svc.record_active_user(user_id)
                await callback.answer("✅ 验证成功！")

                # 通知管理员
                if forward_svc.admin_uid:
                    username = callback.from_user.username
                    name = f"{callback.from_user.first_name or ''} {callback.from_user.last_name or ''}".strip()
                    username_line = f"\n📎 @{username}" if username else ""
                    await bot.send_message(
                        forward_svc.admin_uid,
                        f"✅ <b>新用户验证通过</b>\n\n🆔 <code>{user_id}</code> ({name}){username_line}",
                        parse_mode="HTML",
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[[
                                InlineKeyboardButton("👤 打开用户资料", url=f"tg://user?id={user_id}")
                            ]]
                        ),
                    )
            else:
                if result["reason"] in ("expired", "max_attempts"):
                    try:
                        await bot.edit_message_text(
                            callback.message.chat.id,
                            callback.message.id,
                            result["message"],
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[]),
                        )
                    except Exception:
                        pass
                    await callback.answer(result["message"], show_alert=True)
                else:
                    await callback.answer(result["message"], show_alert=True)
        finally:
            await db.release_verify_lock(user_id)

    ### ---- 管理菜单回调 ---- ###

    @bot.on_callback_query(filters.regex(r"^(submenu_|toggle_|back_to_|refresh_|users_|user_|forward_mode|reset_spam)"))
    async def on_admin_callback(client: Any, callback: CallbackQuery) -> None:
        """处理管理菜单导航。"""
        user_id = callback.from_user.id
        if not security_svc.is_admin(user_id):
            await callback.answer("无权限", show_alert=True)
            return

        data = callback.data
        chat_id = callback.message.chat.id
        msg_id = callback.message.id

        if data == "submenu_spam":
            enabled = await security_svc.is_spam_enabled()
            text = (
                f"🗑 <b>垃圾消息过滤设置</b>\n\n"
                f"当前状态: <b>{'🟢 已开启' if enabled else '🔴 已关闭'}</b>\n\n"
                f"💡 直接发送关键词即可添加拦截规则\n"
                f"发送 <code>del:关键词</code> 删除拦截词"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    f"{'🔴 关闭过滤' if enabled else '🟢 开启过滤'}",
                    callback_data="toggle_spam_filter",
                )],
                [InlineKeyboardButton("🔄 重置为默认规则", callback_data="reset_spam_rules")],
                [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
            ])
            await bot.edit_message_text(chat_id, msg_id, text, parse_mode="HTML", reply_markup=keyboard)

        elif data == "toggle_spam_filter":
            enabled = await security_svc.is_spam_enabled()
            await security_svc.set_spam_enabled(not enabled)
            await callback.answer(f"{'已开启' if not enabled else '已关闭'}垃圾过滤")
            # 刷新菜单
            callback.data = "submenu_spam"
            return await on_admin_callback(client, callback)

        elif data == "reset_spam_rules":
            await security_svc.reset_spam_rules()
            await callback.answer("已重置为默认规则")
            callback.data = "submenu_spam"
            return await on_admin_callback(client, callback)

        elif data == "submenu_union":
            union_enabled = await db.get_config(CONFIG_UNION_BAN, "0")
            is_enabled = union_enabled in ("1", "true")
            text = (
                f"🌐 <b>联合封禁设置</b>\n\n"
                f"当前状态: {'🟢 已开启' if is_enabled else '🔴 已关闭'}\n\n"
                f"联合封禁可以自动拦截已被其他服务标记为恶意的用户。"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    f"{'🔴 关闭联合封禁' if is_enabled else '🟢 开启联合封禁'}",
                    callback_data="toggle_union",
                )],
                [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
            ])
            await bot.edit_message_text(chat_id, msg_id, text, parse_mode="HTML", reply_markup=keyboard)

        elif data == "toggle_union":
            current = await db.get_config(CONFIG_UNION_BAN, "0")
            new_val = "0" if current in ("1", "true") else "1"
            await db.set_config(CONFIG_UNION_BAN, new_val)
            await callback.answer(f"{'已关闭' if new_val == '0' else '已开启'}联合封禁")
            callback.data = "submenu_union"
            return await on_admin_callback(client, callback)

        elif data == "submenu_welcome":
            current = await db.get_config(CONFIG_WELCOME_MSG, "(未设置)")
            text = f"👋 <b>欢迎消息设置</b>\n\n📄 <b>当前内容:</b>\n<pre>{current}</pre>\n\n💡 使用 /welcome 消息内容 设置新消息"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
            ])
            await bot.edit_message_text(chat_id, msg_id, text, parse_mode="HTML", reply_markup=keyboard)

        elif data == "submenu_autoreply":
            current = await db.get_config("auto_reply_msg", "(已关闭)")
            text = f"🤖 <b>自动回复设置</b>\n\n📄 <b>当前内容:</b>\n<pre>{current}</pre>\n\n💡 使用 /autoreply 消息内容 设置自动回复"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
            ])
            await bot.edit_message_text(chat_id, msg_id, text, parse_mode="HTML", reply_markup=keyboard)

        elif data == "submenu_forward":
            mode = await forward_svc.get_forward_mode()
            text = (
                f"💬 <b>消息转发模式</b>\n\n"
                f"当前模式：<b>{'话题模式（论坛群组）' if mode == forward_svc.FORWARD_MODE_TOPIC else '私聊模式（管理员私聊）'}</b>\n\n"
                f"• 私聊模式：所有消息只发到管理员私聊\n"
                f"• 话题模式：每个访客自动创建话题，消息转发到论坛群组"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    f"{'✅ ' if mode == forward_svc.FORWARD_MODE_DIRECT else ''}📥 私聊转发",
                    callback_data=f"forward_mode:{forward_svc.FORWARD_MODE_DIRECT}",
                )],
                [InlineKeyboardButton(
                    f"{'✅ ' if mode == forward_svc.FORWARD_MODE_TOPIC else ''}💬 话题转发",
                    callback_data=f"forward_mode:{forward_svc.FORWARD_MODE_TOPIC}",
                )],
                [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
            ])
            await bot.edit_message_text(chat_id, msg_id, text, parse_mode="HTML", reply_markup=keyboard)

        elif data.startswith("forward_mode:"):
            mode = data.split(":", 1)[1]
            if mode == forward_svc.FORWARD_MODE_TOPIC and not forward_svc.group_id:
                await callback.answer("⚠️ 请先配置 GROUP_ID 环境变量", show_alert=True)
                return
            await forward_svc.set_forward_mode(mode)
            await callback.answer(f"已切换到{'话题' if mode == forward_svc.FORWARD_MODE_TOPIC else '私聊'}模式")
            callback.data = "submenu_forward"
            return await on_admin_callback(client, callback)

        elif data == "submenu_users":
            users = await db.get_verified_users()
            total = len(users)
            text = f"👥 <b>用户管理</b>\n\n📊 已验证用户: {total}\n\n💡 使用 /ban、/trust 等命令管理用户"
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("🔄 刷新", callback_data="refresh_users")],
                [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
            ])
            await bot.edit_message_text(chat_id, msg_id, text, parse_mode="HTML", reply_markup=keyboard)

        elif data == "submenu_stats":
            stats = await stats_svc.get_stats()
            text = (
                f"📊 <b>统计信息</b>\n\n"
                f"📅 <b>今日数据</b>\n"
                f"• 消息数: {stats['today_messages']}\n"
                f"• 活跃用户: {stats['today_active_users']}\n\n"
                f"📈 <b>累计数据</b>\n"
                f"• 总消息数: {stats['total_messages']}\n"
                f"• 已验证用户: {await stats_svc.get_verified_count()}"
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton("🔄 刷新", callback_data="refresh_stats")],
                [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
            ])
            await bot.edit_message_text(chat_id, msg_id, text, parse_mode="HTML", reply_markup=keyboard)

        elif data == "refresh_stats":
            await callback.answer("已刷新")
            callback.data = "submenu_stats"
            return await on_admin_callback(client, callback)

        elif data == "refresh_users":
            await callback.answer("已刷新")
            callback.data = "submenu_users"
            return await on_admin_callback(client, callback)

        elif data == "back_to_main":
            welcome_msg = await db.get_config(CONFIG_WELCOME_MSG, "")
            auto_reply = await db.get_config("auto_reply_msg", "")
            union_ban = await db.get_config(CONFIG_UNION_BAN, "0")
            fwd_mode = await forward_svc.get_forward_mode()
            spam_enabled = await security_svc.is_spam_enabled()

            fwd_status = "💬 话题" if fwd_mode == forward_svc.FORWARD_MODE_TOPIC else "📥 私聊"

            text = (
                f"🛠 <b>SafeRelay 管理面板</b>\n\n"
                f"📊 <b>当前配置:</b>\n"
                f"🔸 📝 验证模式：本地题库\n"
                f"🔸 {'🟢' if spam_enabled else '🔴'} 垃圾过滤：{'已开启' if spam_enabled else '已关闭'}\n"
                f"🔸 {'🟢' if union_ban in ('1', 'true') else '🔴'} 联合封禁：{'已开启' if union_ban in ('1', 'true') else '已关闭'}\n"
                f"🔸 {'🟢' if welcome_msg else '⚪️'} 欢迎消息：{'已设置' if welcome_msg else '未设置'}\n"
                f"🔸 {'🟢' if auto_reply else '⚪️'} 自动回复：{'已设置' if auto_reply else '未设置'}\n"
                f"🔸 {fwd_status} 转发模式：{fwd_status}\n\n"
                f"👇 点击下方按钮进入设置"
            )
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton("🗑 垃圾过滤", callback_data="submenu_spam"),
                     InlineKeyboardButton("🌐 联合封禁", callback_data="submenu_union")],
                    [InlineKeyboardButton("👥 用户管理", callback_data="submenu_users"),
                     InlineKeyboardButton("👋 欢迎消息", callback_data="submenu_welcome")],
                    [InlineKeyboardButton("🤖 自动回复", callback_data="submenu_autoreply"),
                     InlineKeyboardButton("💬 转发模式", callback_data="submenu_forward")],
                    [InlineKeyboardButton("📊 统计信息", callback_data="submenu_stats")],
                ]
            )
            await bot.edit_message_text(chat_id, msg_id, text, parse_mode="HTML", reply_markup=keyboard)
            await callback.answer()
            return

        await callback.answer()

    logger.info("callback_handlers_registered")
