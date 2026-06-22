"""工具函数 — 纯 Python，无第三方依赖。"""

import time
from typing import Any, Callable, Dict, Optional, Tuple


class TTLCache:
    """简单的 TTL 内存缓存。"""

    def __init__(self, default_ttl_ms: int = 1800000):
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._default_ttl_ms = default_ttl_ms
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值。"""
        item = self._cache.get(key)
        if item is None:
            self._misses += 1
            return None
        expires_at, value = item
        if time.time() * 1000 > expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl_ms: Optional[int] = None) -> None:
        """设置缓存值。"""
        ttl = ttl_ms if ttl_ms is not None else self._default_ttl_ms
        self._cache[key] = (time.time() * 1000 + ttl, value)
        # 限制缓存大小
        if len(self._cache) > 5000:
            self._evict(0.2)

    def delete(self, key: str) -> None:
        """删除缓存。"""
        self._cache.pop(key, None)

    def _evict(self, ratio: float) -> None:
        """淘汰最旧的部分条目。"""
        count = int(len(self._cache) * ratio)
        for key in list(self._cache.keys())[:count]:
            del self._cache[key]

    def clear(self) -> None:
        """清空缓存。"""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.2f}%",
            "size": len(self._cache),
        }


def escape_html(text: str) -> str:
    """转义 HTML 特殊字符。"""
    if not isinstance(text, str):
        return str(text)
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def secure_random_int(min_val: int, max_val: int) -> int:
    """生成安全的随机整数 [min, max)。"""
    import random
    return random.randrange(min_val, max_val)


def format_duration(seconds: int) -> str:
    """格式化秒数为可读字符串。"""
    if seconds < 60:
        return f"{seconds}秒"
    if seconds < 3600:
        return f"{seconds // 60}分钟"
    if seconds < 86400:
        return f"{seconds // 3600}小时"
    return f"{seconds // 86400}天"


cached_property = property
