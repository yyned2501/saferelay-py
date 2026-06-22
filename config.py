"""SafeRelay 配置模块，从环境变量读取配置。"""

import os
from dotenv import load_dotenv
from typing import List, Optional

# 加载 .env 文件
load_dotenv()


class Config:
    """应用配置，从环境变量读取。"""

    def __init__(self):
        # 必需配置
        self.bot_token: str = os.getenv("BOT_TOKEN", "")
        raw_admin_ids: str = os.getenv("ADMIN_IDS", "")
        self.admin_ids: List[int] = self._parse_admin_ids(raw_admin_ids)
        self.admin_uid: Optional[int] = self.admin_ids[0] if self.admin_ids else None

        # 话题群组
        raw_group_id: str = os.getenv("GROUP_ID", "")
        self.group_id: Optional[int] = int(raw_group_id.strip()) if raw_group_id.strip() else None

        # MTProto API 凭证（Kurigram/Pyrogram 必需）
        self.api_id: int = int(os.getenv("API_ID", "0"))
        self.api_hash: str = os.getenv("API_HASH", "")

        # 代理配置
        raw_proxy_enabled: str = os.getenv("PROXY_ENABLED", "true")
        self.proxy_enabled: bool = raw_proxy_enabled.lower() in ("true", "1", "yes")
        self.proxy_scheme: str = os.getenv("PROXY_SCHEME", "socks5")
        self.proxy_host: str = os.getenv("PROXY_HOST", "192.168.31.10")
        self.proxy_port: int = int(os.getenv("PROXY_PORT", "7890"))

        # 可选配置
        self.welcome_msg: str = os.getenv("WELCOME_MSG", "")
        self.autoreply_msg: str = os.getenv("AUTOREPLY_MSG", "")

        # 欺诈数据库 URL
        self.fraud_db_url: str = os.getenv(
            "FRAUD_DB_URL",
            "https://raw.githubusercontent.com/qianqi32/SafeRelay/main/data/fraud.db",
        )

        # 联合封禁 API
        self.union_ban_api_url: str = os.getenv(
            "UNION_BAN_API_URL", "https://verify.wzxabc.eu.org"
        )

        # 验证有效期 (秒)，默认 7 天
        self.verification_ttl: int = int(os.getenv("VERIFICATION_TTL", str(60 * 60 * 24 * 7)))

        # 高级配置
        self.pending_max_messages: int = int(os.getenv("PENDING_MAX_MESSAGES", "10"))
        self.pending_queue_ttl: int = int(os.getenv("PENDING_QUEUE_TTL", "86400"))

        # 速率限制
        self.message_window_ms: int = 5000
        self.message_max_requests: int = 5
        self.verify_window_ms: int = 300000
        self.verify_max_requests: int = 3
        self.verify_attempt_window_ms: int = 60000
        self.verify_attempt_max_requests: int = 5
        self.broadcast_window_ms: int = 86400000
        self.broadcast_max_requests: int = 1

        # 验证锁超时 (秒)
        self.verify_lock_ttl: int = 60

        # 联合封禁缓存 (秒)
        self.union_ban_cache_ttl: int = 86400

        # 欺诈数据库缓存 (秒)
        self.fraud_cache_ttl: int = 3600

    @staticmethod
    def _parse_admin_ids(raw: str) -> List[int]:
        """解析逗号/分号/空格分隔的管理员 ID 列表。"""
        ids: List[int] = []
        if not raw:
            return ids
        for part in raw.replace(";", ",").split(","):
            part = part.strip()
            if part and part.lstrip("-").isdigit():
                ids.append(int(part))
        # 去重并保持顺序
        seen: set = set()
        unique: List[int] = []
        for uid in ids:
            if uid not in seen:
                seen.add(uid)
                unique.append(uid)
        return unique

    def validate(self) -> str:
        """验证配置是否有效，返回错误消息，空字符串表示有效。"""
        errors: List[str] = []
        if not self.bot_token:
            errors.append("BOT_TOKEN is required")
        if not self.admin_ids:
            errors.append("ADMIN_IDS is required")
        if self.bot_token and ":" not in self.bot_token:
            errors.append("BOT_TOKEN should be in format: 123456:ABC-DEF...")
        return "; ".join(errors)


config = Config()
