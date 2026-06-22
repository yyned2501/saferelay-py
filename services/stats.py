"""统计服务 — 消息计数、活跃用户统计。"""

from typing import Any, Dict, List

from core.database import Database
from core.logger import get_logger

logger = get_logger("services.stats")


class StatsService:
    """统计服务。"""

    def __init__(self, db: Database):
        self.db = db
        # 内存缓冲（减少写入）
        self._buffer_daily = 0
        self._buffer_total = 0
        self._today = ""
        self._dirty = False

    async def increment_message_count(self) -> None:
        """递增消息计数。"""
        import datetime
        today = datetime.date.today().isoformat()
        if self._today != today:
            if self._dirty:
                await self._flush()
            self._today = today
            self._buffer_daily = 0
            self._buffer_total = 0
        self._buffer_daily += 1
        self._buffer_total += 1
        self._dirty = True

    async def _flush(self) -> None:
        """将缓冲数据刷入数据库。"""
        if not self._dirty:
            return
        self._dirty = False
        if self._buffer_daily > 0 or self._buffer_total > 0:
            await self.db.increment_message_count()

    async def record_active_user(self, user_id: int) -> None:
        """记录活跃用户。"""
        await self.db.record_active_user(user_id)

    async def get_stats(self, days: int = 7) -> Dict[str, Any]:
        """获取统计信息。"""
        await self._flush()
        daily_stats = await self.db.get_stats(days)
        total = await self.db.get_total_message_count()

        today = daily_stats[0] if daily_stats else {"messages": 0, "active_users": 0}

        return {
            "total_messages": total,
            "today_messages": today.get("messages", 0),
            "today_active_users": today.get("active_users", 0),
            "daily": daily_stats,
        }

    async def get_verified_count(self) -> int:
        """获取已验证用户数。"""
        return await self.db.get_verified_count()

    async def get_verified_users(self) -> List[Dict[str, Any]]:
        """获取已验证用户列表。"""
        return await self.db.get_verified_users()
