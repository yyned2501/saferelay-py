"""ORM 模型定义 — SQLAlchemy async ORM 数据模型。

所有模型集中定义在此模块，core/database.py 导入使用。
handlers/services 禁止直接 import 本模块。
"""
from typing import Optional

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类。"""
    pass


class VerifiedUser(Base):
    """已验证用户表。"""
    __tablename__ = "verified_users"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    verified_at: Mapped[int] = mapped_column(Integer, default=0)


class TopicMapping(Base):
    """用户话题映射表。"""
    __tablename__ = "topic_mapping"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    thread_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, default=0)


class ForwardMapping(Base):
    """转发消息映射表。"""
    __tablename__ = "forward_mapping"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fwd_msg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_chat: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_msg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    target_chat: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    thread_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=0)


class ReplyMapping(Base):
    """管理员回复映射表。"""
    __tablename__ = "reply_mapping"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_msg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guest_chat: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guest_msg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, default=0)


class BannedUser(Base):
    """封禁用户表。"""
    __tablename__ = "banned_users"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    banned_at: Mapped[int] = mapped_column(Integer, default=0)


class WhitelistUser(Base):
    """白名单用户表。"""
    __tablename__ = "whitelist"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    added_at: Mapped[int] = mapped_column(Integer, default=0)


class RateLimit(Base):
    """速率限制表。"""
    __tablename__ = "rate_limits"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    timestamps: Mapped[str] = mapped_column(Text, default="[]")


class VerifyLock(Base):
    """验证锁表。"""
    __tablename__ = "verify_locks"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    expires_at: Mapped[int] = mapped_column(Integer, nullable=False)


class StatsMessage(Base):
    """消息统计表。"""
    __tablename__ = "stats_messages"
    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)


class StatsActiveUser(Base):
    """活跃用户统计表。"""
    __tablename__ = "stats_active_users"
    date: Mapped[str] = mapped_column(String(10), primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)


class AppConfig(Base):
    """配置表。"""
    __tablename__ = "config"
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class PendingQueue(Base):
    """验证暂存消息队列。"""
    __tablename__ = "pending_queue"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    msg_data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[int] = mapped_column(Integer, default=0)


class ThreadMapping(Base):
    """线程 → 用户映射表。"""
    __tablename__ = "thread_mapping"
    thread_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class EditNotice(Base):
    """编辑提示消息映射表。"""
    __tablename__ = "edit_notices"
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    orig_msg_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    notice_chat: Mapped[int] = mapped_column(BigInteger, nullable=False)
    notice_msg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[int] = mapped_column(Integer, default=0)
