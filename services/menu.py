"""管理菜单构建 — 提供管理面板各子菜单的文本和键盘构建函数。

仅供 handlers/callback.py 使用，将菜单构建逻辑从 handler 中剥离。
"""
from typing import Any, Dict, List, Optional, Tuple

from core.bot import InlineKeyboardButton, InlineKeyboardMarkup
from core.database import Database
from core.logger import get_logger

logger = get_logger("services.menu")

CONFIG_WELCOME_MSG = "welcome_msg"
CONFIG_UNION_BAN = "union_ban"


async def build_main_menu(
    db: Database, forward_svc: Any, security_svc: Any,
) -> Tuple[str, InlineKeyboardMarkup]:
    """构建管理面板主菜单。"""
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
    return text, keyboard


async def build_spam_menu(
    security_svc: Any,
) -> Tuple[str, InlineKeyboardMarkup]:
    """构建垃圾过滤设置菜单。"""
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
    return text, keyboard


async def build_union_menu(
    db: Database,
) -> Tuple[str, InlineKeyboardMarkup]:
    """构建联合封禁设置菜单。"""
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
    return text, keyboard


async def build_welcome_menu(
    db: Database,
) -> Tuple[str, InlineKeyboardMarkup]:
    """构建欢迎消息设置菜单。"""
    current = await db.get_config(CONFIG_WELCOME_MSG, "(未设置)")
    text = f"👋 <b>欢迎消息设置</b>\n\n📄 <b>当前内容:</b>\n<pre>{current}</pre>\n\n💡 使用 /welcome 消息内容 设置新消息"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
    ])
    return text, keyboard


async def build_autoreply_menu(
    db: Database,
) -> Tuple[str, InlineKeyboardMarkup]:
    """构建自动回复设置菜单。"""
    current = await db.get_config("auto_reply_msg", "(已关闭)")
    text = f"🤖 <b>自动回复设置</b>\n\n📄 <b>当前内容:</b>\n<pre>{current}</pre>\n\n💡 使用 /autoreply 消息内容 设置自动回复"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
    ])
    return text, keyboard


async def build_forward_menu(
    forward_svc: Any,
) -> Tuple[str, InlineKeyboardMarkup]:
    """构建转发模式设置菜单。"""
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
    return text, keyboard


async def build_users_menu(
    db: Database,
) -> Tuple[str, InlineKeyboardMarkup]:
    """构建用户管理菜单。"""
    total = await db.get_verified_count()
    text = f"👥 <b>用户管理</b>\n\n📊 已验证用户: {total}\n\n💡 使用 /ban、/trust 等命令管理用户"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🔄 刷新", callback_data="refresh_users")],
        [InlineKeyboardButton("◀️ 返回主菜单", callback_data="back_to_main")],
    ])
    return text, keyboard


async def build_stats_menu(
    stats_svc: Any, db: Database,
) -> Tuple[str, InlineKeyboardMarkup]:
    """构建统计信息菜单。"""
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
    return text, keyboard
