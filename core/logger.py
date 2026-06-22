"""日志模块 — 封装 logging，提供结构化日志和脱敏功能。"""

import logging
import re
import sys
from typing import Any, Dict

# 敏感字段模式
SENSITIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'bot\d{6,}:[A-Za-z0-9_-]{20,}'), 'bot***:***'),
    (re.compile(r'\d{6,12}:[A-Za-z0-9_-]{30,}'), '***:***'),
    (re.compile(r'0x4[A-Za-z0-9]{20,}'), '0x***'),
    (re.compile(r'Bearer\s+[A-Za-z0-9._\-]+'), 'Bearer ***'),
    (re.compile(r'([?&](?:sig|signature|secret|token|key|secret_token)=)[^&\s"\']+'), '\\1***'),
]

SENSITIVE_KEYS: set[str] = {
    'token', 'secret', 'signature', 'sig', 'authorization',
    'bot_token', 'bot_secret', 'api_key', 'password',
}


def sanitize_sensitive(value: Any, depth: int = 0) -> Any:
    """递归脱敏敏感数据。"""
    if depth > 6:
        return '[Truncated]'
    if value is None:
        return None
    if isinstance(value, str):
        for pattern, replacement in SENSITIVE_PATTERNS:
            value = pattern.sub(replacement, value)
        return value
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list):
        return [sanitize_sensitive(v, depth + 1) for v in value]
    if isinstance(value, dict):
        return {
            k: '***' if k.lower() in SENSITIVE_KEYS else sanitize_sensitive(v, depth + 1)
            for k, v in value.items()
        }
    return value


class SafeRelayLogger:
    """结构化日志记录器，自动脱敏。"""

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, action: str, data: Dict[str, Any] = None) -> None:
        safe_data = sanitize_sensitive(data or {})
        msg = f"[{action}] {safe_data}" if safe_data else f"[{action}]"
        self._logger.log(level, msg)

    def info(self, action: str, data: Dict[str, Any] = None) -> None:
        self._log(logging.INFO, action, data)

    def warn(self, action: str, error_or_data: Any = None, data: Dict[str, Any] = None) -> None:
        payload: Dict[str, Any] = {}
        if isinstance(error_or_data, Exception):
            payload = {"error": str(error_or_data), ** (data or {})}
        elif error_or_data is not None:
            payload = {**error_or_data, **(data or {})}
        else:
            payload = data or {}
        self._log(logging.WARN, action, payload)

    def error(self, action: str, error: Exception = None, data: Dict[str, Any] = None) -> None:
        payload = {"error": str(error) if error else "unknown", **(data or {})}
        self._log(logging.ERROR, action, payload)

    def debug(self, action: str, data: Dict[str, Any] = None) -> None:
        self._log(logging.DEBUG, action, data)


_loggers: dict[str, SafeRelayLogger] = {}


def get_logger(name: str) -> SafeRelayLogger:
    """获取或创建 SafeRelayLogger。"""
    if name not in _loggers:
        _loggers[name] = SafeRelayLogger(name)
    return _loggers[name]


# 初始化根日志格式
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
