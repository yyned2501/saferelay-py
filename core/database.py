"""数据库模块 — 封装 aiosqlite，提供所有持久化方法。"""

import json
import time
from typing import Any, Dict, List, Optional

import aiosqlite

from core.logger import get_logger

logger = get_logger("core.database")

DB_PATH = "data/saferelay.db"


class Database:
    """数据库单例，封装 aiosqlite。"""

    def __init__(self, db_path: str = DB_PATH):
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def init(self) -> None:
        """初始化数据库连接并建表。"""
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        logger.info("db_initialized", {"path": self._db_path})

    async def _create_tables(self) -> None:
        """创建所有表。"""
        await self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS verified_users (
                user_id INTEGER PRIMARY KEY,
                display_name TEXT NOT NULL DEFAULT '',
                verified_at INTEGER NOT NULL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS topic_mapping (
                user_id INTEGER PRIMARY KEY,
                thread_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS forward_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fwd_msg_id INTEGER NOT NULL,
                source_chat INTEGER NOT NULL,
                source_msg_id INTEGER NOT NULL,
                target_chat INTEGER,
                thread_id INTEGER,
                created_at INTEGER NOT NULL DEFAULT (unixepoch())
            );

            CREATE INDEX IF NOT EXISTS idx_fwd_msg_id ON forward_mapping(fwd_msg_id);
            CREATE INDEX IF NOT EXISTS idx_source_msg_id ON forward_mapping(source_msg_id);

            CREATE TABLE IF NOT EXISTS reply_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_msg_id INTEGER NOT NULL,
                guest_chat INTEGER NOT NULL,
                guest_msg_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (unixepoch())
            );

            CREATE INDEX IF NOT EXISTS idx_admin_msg_id ON reply_mapping(admin_msg_id);

            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT NOT NULL DEFAULT '',
                banned_at INTEGER NOT NULL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS whitelist (
                user_id INTEGER PRIMARY KEY,
                added_at INTEGER NOT NULL DEFAULT (unixepoch())
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                key TEXT PRIMARY KEY,
                timestamps TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS verify_locks (
                user_id INTEGER PRIMARY KEY,
                expires_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS stats_messages (
                date TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (date)
            );

            CREATE TABLE IF NOT EXISTS stats_active_users (
                date TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                PRIMARY KEY (date, user_id)
            );

            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_queue (
                user_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                msg_data TEXT,
                created_at INTEGER NOT NULL DEFAULT (unixepoch()),
                PRIMARY KEY (user_id, message_id)
            );

            CREATE TABLE IF NOT EXISTS thread_mapping (
                thread_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS edit_notices (
                user_id INTEGER NOT NULL,
                orig_msg_id INTEGER NOT NULL,
                notice_chat INTEGER NOT NULL,
                notice_msg_id INTEGER NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (unixepoch()),
                PRIMARY KEY (user_id, orig_msg_id)
            );
        """)
        await self._conn.commit()

    async def close(self) -> None:
        """关闭数据库连接。"""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        if not self._conn:
            raise RuntimeError("Database not initialized")
        return await self._conn.execute(sql, params)

    async def _fetchone(self, sql: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        cur = await self._execute(sql, params)
        return await cur.fetchone()

    async def _fetchall(self, sql: str, params: tuple = ()) -> List[aiosqlite.Row]:
        cur = await self._execute(sql, params)
        return await cur.fetchall()

    # ---- 用户验证 ----

    async def is_verified(self, user_id: int) -> bool:
        """检查用户是否已验证。"""
        row = await self._fetchone(
            "SELECT 1 FROM verified_users WHERE user_id = ?", (user_id,)
        )
        return row is not None

    async def mark_verified(self, user_id: int, display_name: str) -> None:
        """标记用户已验证。"""
        await self._execute(
            "INSERT OR REPLACE INTO verified_users (user_id, display_name, verified_at) VALUES (?, ?, unixepoch())",
            (user_id, display_name),
        )
        await self._conn.commit()

    async def remove_verified(self, user_id: int) -> None:
        """移除用户验证状态。"""
        await self._execute(
            "DELETE FROM verified_users WHERE user_id = ?", (user_id,)
        )
        await self._conn.commit()

    # ---- 用户资料缓存 ----

    async def upsert_user_profile(self, user_id: int, profile: Dict[str, Any]) -> None:
        """更新用户资料缓存。"""
        await self._execute(
            "INSERT OR REPLACE INTO verified_users (user_id, display_name, verified_at) VALUES (?, ?, unixepoch())",
            (user_id, profile.get("display_name", "")),
        )
        await self._conn.commit()

    # ---- 话题映射 ----

    async def get_user_topic(self, user_id: int) -> Optional[int]:
        """获取用户的话题 ID。"""
        row = await self._fetchone(
            "SELECT thread_id FROM topic_mapping WHERE user_id = ?", (user_id,)
        )
        return row["thread_id"] if row else None

    async def set_user_topic(self, user_id: int, thread_id: int) -> None:
        """设置用户的话题映射。"""
        await self._execute(
            "INSERT OR REPLACE INTO topic_mapping (user_id, thread_id) VALUES (?, ?)",
            (user_id, thread_id),
        )
        await self._conn.commit()

    async def remove_user_topic(self, user_id: int, thread_id: int) -> None:
        """移除用户的话题映射。"""
        await self._execute(
            "DELETE FROM topic_mapping WHERE user_id = ? AND thread_id = ?",
            (user_id, thread_id),
        )
        await self._conn.commit()

    async def get_user_by_thread(self, thread_id: int) -> Optional[int]:
        """通过话题 ID 获取用户 ID。"""
        row = await self._fetchone(
            "SELECT user_id FROM thread_mapping WHERE thread_id = ?", (thread_id,)
        )
        if row:
            return row["user_id"]
        # 回退查询 topic_mapping
        rows = await self._fetchall(
            "SELECT user_id FROM topic_mapping WHERE thread_id = ?", (thread_id,)
        )
        return rows[0]["user_id"] if rows else None

    async def set_thread_mapping(self, thread_id: int, user_id: int) -> None:
        """设置线程 → 用户映射。"""
        await self._execute(
            "INSERT OR REPLACE INTO thread_mapping (thread_id, user_id) VALUES (?, ?)",
            (thread_id, user_id),
        )
        await self._conn.commit()

    # ---- 消息映射 ----

    async def store_forward_mapping(
        self, fwd_msg_id: int, source_chat: int, source_msg_id: int,
        target_chat: int = None, thread_id: int = None,
    ) -> None:
        """存储转发消息映射。"""
        await self._execute(
            "INSERT INTO forward_mapping (fwd_msg_id, source_chat, source_msg_id, target_chat, thread_id) VALUES (?, ?, ?, ?, ?)",
            (fwd_msg_id, source_chat, source_msg_id, target_chat, thread_id),
        )
        await self._conn.commit()

    async def get_forward_mapping(self, fwd_msg_id: int) -> Optional[Dict[str, Any]]:
        """根据转发消息 ID 获取原始映射。"""
        row = await self._fetchone(
            "SELECT * FROM forward_mapping WHERE fwd_msg_id = ?", (fwd_msg_id,)
        )
        if row:
            return dict(row)
        return None

    async def get_original_mapping(self, orig_msg_id: int) -> Optional[int]:
        """根据原始消息 ID 获取转发后的消息 ID。"""
        row = await self._fetchone(
            "SELECT fwd_msg_id FROM forward_mapping WHERE source_msg_id = ?", (orig_msg_id,)
        )
        return row["fwd_msg_id"] if row else None

    # ---- 管理员回复映射 ----

    async def store_reply_mapping(self, admin_msg_id: int, guest_chat: int, guest_msg_id: int) -> None:
        """存储管理员回复映射。"""
        await self._execute(
            "INSERT INTO reply_mapping (admin_msg_id, guest_chat, guest_msg_id) VALUES (?, ?, ?)",
            (admin_msg_id, guest_chat, guest_msg_id),
        )
        await self._conn.commit()

    async def get_reply_mapping(self, admin_msg_id: int) -> Optional[Dict[str, Any]]:
        """获取管理员回复映射。"""
        row = await self._fetchone(
            "SELECT * FROM reply_mapping WHERE admin_msg_id = ?", (admin_msg_id,)
        )
        if row:
            return dict(row)
        return None

    # ---- 黑白名单 ----

    async def is_banned(self, user_id: int) -> bool:
        """检查用户是否被封禁。"""
        row = await self._fetchone(
            "SELECT 1 FROM banned_users WHERE user_id = ?", (user_id,)
        )
        return row is not None

    async def ban_user(self, user_id: int, reason: str = "") -> None:
        """封禁用户。"""
        await self._execute(
            "INSERT OR REPLACE INTO banned_users (user_id, reason) VALUES (?, ?)",
            (user_id, reason),
        )
        await self._conn.commit()

    async def unban_user(self, user_id: int) -> None:
        """解封用户。"""
        await self._execute(
            "DELETE FROM banned_users WHERE user_id = ?", (user_id,)
        )
        await self._conn.commit()

    async def is_whitelisted(self, user_id: int) -> bool:
        """检查用户是否在白名单中。"""
        row = await self._fetchone(
            "SELECT 1 FROM whitelist WHERE user_id = ?", (user_id,)
        )
        return row is not None

    async def add_whitelist(self, user_id: int) -> None:
        """添加白名单用户。"""
        await self._execute(
            "INSERT OR IGNORE INTO whitelist (user_id) VALUES (?)", (user_id,)
        )
        await self._conn.commit()

    async def remove_whitelist(self, user_id: int) -> None:
        """移除白名单用户。"""
        await self._execute(
            "DELETE FROM whitelist WHERE user_id = ?", (user_id,)
        )
        await self._conn.commit()

    # ---- 速率限制 ----

    async def check_rate_limit(self, key: str, window_ms: int, max_count: int) -> bool:
        """检查速率限制，返回是否允许通过。"""
        now = int(time.time() * 1000)
        row = await self._fetchone(
            "SELECT timestamps FROM rate_limits WHERE key = ?", (key,)
        )
        timestamps: list = json.loads(row["timestamps"]) if row else []
        # 过滤过期
        cutoff = now - window_ms
        timestamps = [ts for ts in timestamps if ts > cutoff]
        if len(timestamps) >= max_count:
            return False
        timestamps.append(now)
        await self._execute(
            "INSERT OR REPLACE INTO rate_limits (key, timestamps) VALUES (?, ?)",
            (key, json.dumps(timestamps)),
        )
        await self._conn.commit()
        return True

    # ---- 验证锁 ----

    async def acquire_verify_lock(self, user_id: int, ttl_seconds: int) -> bool:
        """尝试获取验证锁。"""
        expires = int(time.time()) + ttl_seconds
        try:
            await self._execute(
                "INSERT INTO verify_locks (user_id, expires_at) VALUES (?, ?)",
                (user_id, expires),
            )
            await self._conn.commit()
            return True
        except Exception:
            # 已存在锁，检查是否过期
            row = await self._fetchone(
                "SELECT expires_at FROM verify_locks WHERE user_id = ?", (user_id,)
            )
            if row and row["expires_at"] < int(time.time()):
                await self._execute(
                    "UPDATE verify_locks SET expires_at = ? WHERE user_id = ?",
                    (expires, user_id),
                )
                await self._conn.commit()
                return True
            return False

    async def release_verify_lock(self, user_id: int) -> None:
        """释放验证锁。"""
        await self._execute(
            "DELETE FROM verify_locks WHERE user_id = ?", (user_id,)
        )
        await self._conn.commit()

    # ---- 统计 ----

    async def increment_message_count(self) -> None:
        """递增消息计数。"""
        from datetime import date
        today = date.today().isoformat()
        await self._execute(
            "INSERT INTO stats_messages (date, count) VALUES (?, 1) "
            "ON CONFLICT(date) DO UPDATE SET count = count + 1",
            (today,),
        )
        await self._conn.commit()

    async def record_active_user(self, user_id: int) -> None:
        """记录活跃用户。"""
        from datetime import date
        today = date.today().isoformat()
        await self._execute(
            "INSERT OR IGNORE INTO stats_active_users (date, user_id) VALUES (?, ?)",
            (today, user_id),
        )
        await self._conn.commit()

    async def get_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取统计信息。"""
        from datetime import date, timedelta
        results = []
        for i in range(days):
            d = (date.today() - timedelta(days=i)).isoformat()
            row = await self._fetchone(
                "SELECT count FROM stats_messages WHERE date = ?", (d,)
            )
            count = row["count"] if row else 0
            active_row = await self._fetchone(
                "SELECT COUNT(*) as cnt FROM stats_active_users WHERE date = ?", (d,)
            )
            active = active_row["cnt"] if active_row else 0
            results.append({"date": d, "messages": count, "active_users": active})
        return results

    async def get_total_message_count(self) -> int:
        """获取总消息数。"""
        row = await self._fetchone("SELECT SUM(count) as total FROM stats_messages")
        return row["total"] if row and row["total"] else 0

    # ---- 已验证用户列表 ----

    async def get_verified_users(self) -> List[Dict[str, Any]]:
        """获取所有已验证用户。"""
        rows = await self._fetchall(
            "SELECT user_id, display_name, verified_at FROM verified_users ORDER BY verified_at DESC"
        )
        return [dict(r) for r in rows]

    async def get_verified_count(self) -> int:
        """获取已验证用户数量。"""
        row = await self._fetchone("SELECT COUNT(*) as cnt FROM verified_users")
        return row["cnt"] if row else 0

    # ---- 配置 ----

    async def get_config(self, key: str, default: str = "") -> str:
        """获取配置值。"""
        row = await self._fetchone(
            "SELECT value FROM config WHERE key = ?", (key,)
        )
        return row["value"] if row else default

    async def set_config(self, key: str, value: str) -> None:
        """设置配置值。"""
        await self._execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self._conn.commit()

    async def delete_config(self, key: str) -> None:
        """删除配置。"""
        await self._execute("DELETE FROM config WHERE key = ?", (key,))
        await self._conn.commit()

    # ---- 暂存队列 ----

    async def append_pending(self, user_id: int, message_id: int, msg_data: str = "") -> int:
        """添加消息到暂存队列。"""
        # 清理过期
        cutoff = int(time.time()) - 86400
        await self._execute(
            "DELETE FROM pending_queue WHERE user_id = ? AND created_at < ?",
            (user_id, cutoff),
        )
        await self._execute(
            "INSERT OR IGNORE INTO pending_queue (user_id, message_id, msg_data) VALUES (?, ?, ?)",
            (user_id, message_id, msg_data),
        )
        await self._conn.commit()
        row = await self._fetchone(
            "SELECT COUNT(*) as cnt FROM pending_queue WHERE user_id = ?", (user_id,)
        )
        return row["cnt"] if row else 0

    async def get_pending(self, user_id: int) -> List[Dict[str, Any]]:
        """获取暂存消息列表。"""
        rows = await self._fetchall(
            "SELECT message_id, msg_data FROM pending_queue WHERE user_id = ? ORDER BY created_at ASC",
            (user_id,),
        )
        return [dict(r) for r in rows]

    async def clear_pending(self, user_id: int) -> None:
        """清空暂存队列。"""
        await self._execute(
            "DELETE FROM pending_queue WHERE user_id = ?", (user_id,)
        )
        await self._conn.commit()

    async def delete_pending_item(self, user_id: int, message_id: int) -> None:
        """删除暂存队列中的一条消息。"""
        await self._execute(
            "DELETE FROM pending_queue WHERE user_id = ? AND message_id = ?",
            (user_id, message_id),
        )
        await self._conn.commit()

    # ---- 编辑通知 ----

    async def store_edit_notice(
        self, user_id: int, orig_msg_id: int, notice_chat: int, notice_msg_id: int
    ) -> None:
        """存储编辑通知映射。"""
        await self._execute(
            "INSERT OR REPLACE INTO edit_notices (user_id, orig_msg_id, notice_chat, notice_msg_id) VALUES (?, ?, ?, ?)",
            (user_id, orig_msg_id, notice_chat, notice_msg_id),
        )
        await self._conn.commit()

    async def get_edit_notice(self, user_id: int, orig_msg_id: int) -> Optional[Dict[str, Any]]:
        """获取编辑通知映射。"""
        row = await self._fetchone(
            "SELECT * FROM edit_notices WHERE user_id = ? AND orig_msg_id = ?",
            (user_id, orig_msg_id),
        )
        return dict(row) if row else None

    # ---- 清理 ----

    async def cleanup_topic_mapping(self, thread_id: int) -> None:
        """清理话题映射。"""
        await self._execute(
            "DELETE FROM topic_mapping WHERE thread_id = ?", (thread_id,)
        )
        await self._execute(
            "DELETE FROM thread_mapping WHERE thread_id = ?", (thread_id,)
        )
        await self._conn.commit()
