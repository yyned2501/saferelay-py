# SafeRelay-Py — Python 转换项目

## 目标

将 SafeRelay (JS/Cloudflare Workers) 转换为 Python 项目，使用 **Kurigram (Pyrogram 兼容分支)**。

**原始项目**: https://github.com/qianqi32/SafeRelay
**主文件**: https://raw.githubusercontent.com/qianqi32/SafeRelay/main/worker.js

## 核心架构：Core 封装层

所有第三方库只能直接在 `core/` 中使用，services/ 和 handlers/ **只能从 core/ 导入**，绝不能直接 import pyrogram/aiosqlite/httpx。

```
saferelay-py/
├── main.py                    # 入口: 创建 db, bot, 注册 handlers, run()
├── config.py                  # 配置，从环境变量读取
├── core/                      # ← 所有第三方库中转层
│   ├── __init__.py
│   ├── bot.py                 # 封装 Pyrogram/Kurigram Client
│   ├── database.py            # 封装 aiosqlite
│   ├── http.py                # 封装 httpx
│   └── logger.py              # 封装 logging
├── services/                  # 业务逻辑
│   ├── __init__.py
│   ├── forward.py             # 消息转发（调用 core.bot）
│   ├── verify.py              # 验证（调用 core.bot + core.database）
│   ├── security.py            # 安全（调用 core.database + core.http）
│   └── stats.py               # 统计
├── handlers/                  # TG 事件处理 (调用 services/)
│   ├── __init__.py
│   ├── user.py                # 用户私聊消息
│   ├── admin.py               # 管理员命令
│   └── callback.py            # Callback query
├── utils/                     # 纯工具，无第三方依赖
│   ├── __init__.py
│   └── helpers.py
├── data/
│   └── fraud.db
├── CLAUDE.md
├── requirements.txt
├── .env.example
└── README.md
```

## Core 层接口设计

### core/bot.py — 封装 Kurigram (Pyrogram)

```python
# 对外暴露的类型（间接引用，防止 handlers 直接 import pyrogram）
# Message, CallbackQuery, filters 等从 core.bot 导出

class Bot:
    def __init__(self, bot_token: str)
    def on_message(self, filter=None, group=0) -> decorator
    def on_callback_query(self, filter=None, group=0) -> decorator
    async def send_message(chat_id, text, **kwargs) -> Message
    async def forward_messages(chat_id, from_chat_id, message_ids, **kwargs) -> list[Message]
    async def copy_message(chat_id, from_chat_id, message_id, **kwargs) -> Message
    async def edit_message_text(chat_id, message_id, text, **kwargs) -> Message
    async def delete_messages(chat_id, message_ids) -> bool
    async def answer_callback_query(callback_query_id, text=None, **kwargs)
    async def get_chat(chat_id) -> Chat
    async def get_users(user_ids) -> User
    async def create_forum_topic(chat_id, title) -> ForumTopic
    async def close_forum_topic(chat_id, topic_id)
    async def reopen_forum_topic(chat_id, topic_id)
    async def edit_forum_topic(chat_id, topic_id, title)
    async def get_forum_topic(chat_id, topic_id) -> ForumTopic
    async def send_chat_action(chat_id, action)
    async def get_me() -> User
    def run(self)  # blocking, starts the bot
```

### core/database.py — 封装 aiosqlite

```python
class Database:
    async def init()
    async def close()
    # 用户验证
    async def is_verified(user_id: int) -> bool
    async def mark_verified(user_id: int, display_name: str)
    async def remove_verified(user_id: int)
    # 话题映射
    async def get_user_topic(user_id: int) -> int | None
    async def set_user_topic(user_id: int, thread_id: int)
    async def remove_user_topic(user_id: int, thread_id: int)
    # 消息映射
    async def store_forward_mapping(fwd_msg_id, source_chat, source_msg_id, target_chat, thread_id)
    async def get_forward_mapping(fwd_msg_id: int) -> dict | None
    async def get_original_mapping(orig_msg_id: int) -> int | None
    # 管理员回复映射
    async def store_reply_mapping(admin_msg_id, guest_chat, guest_msg_id)
    async def get_reply_mapping(admin_msg_id: int) -> dict | None
    # 黑白名单
    async def is_banned(user_id: int) -> bool
    async def ban_user(user_id: int, reason: str = "")
    async def unban_user(user_id: int)
    async def is_whitelisted(user_id: int) -> bool
    async def add_whitelist(user_id: int)
    async def remove_whitelist(user_id: int)
    # 速率限制
    async def check_rate_limit(key: str, window_ms: int, max_count: int) -> bool
    # 验证锁
    async def acquire_verify_lock(user_id: int, ttl_seconds: int) -> bool
    async def release_verify_lock(user_id: int)
    # 统计
    async def increment_message_count()
    async def record_active_user(user_id: int)
    async def get_stats(days: int = 7) -> list[dict]
    # 已验证用户列表
    async def get_verified_users() -> list[dict]
    async def get_verified_count() -> int
```

### core/http.py — 封装 httpx

```python
class HttpClient:
    async def get(url, **kwargs) -> dict
    async def post(url, json=None, **kwargs) -> dict
    async def close()
```

### core/logger.py — 封装 logging

```python
def get_logger(name: str) -> Logger
# 结构化日志，带脱敏
```

## 功能对照

| 原始 (JS/CF) | 新 (Python) | 说明 |
|---|---|---|
| Cloudflare KV | core/database.py | SQLite |
| fetch → Telegram API | core/bot.py | Pyrogram 原生 |
| Turnstile 验证 | ❌ 移除 | MTProto 不支持 |
| 本地题库验证 | services/verify.py | InlineKeyboard |
| 消息转发 | services/forward.py | 调用 core.bot |
| 管理员命令 | handlers/admin.py | 调用 services |
| Callback 处理 | handlers/callback.py | 调用 services |
| 用户消息 | handlers/user.py | 调用 services |
| 速率限制 | core/database.py | SQLite |
| 联合封禁 | core/http.py + services/security.py | httpx |
| 欺诈检测 | services/security.py | 读 data/fraud.db |
| 内存缓存 | Python dict/lru_cache | utils/helpers.py |

## 环境变量

必须在 main.py 启动前通过 config.py 校验。缺失 BOT_TOKEN 或 ADMIN_IDS 则报错退出。

## 依赖 (requirements.txt)
```
kurigram>=2.2.22
aiosqlite>=0.20.0
httpx>=0.27.0
```

## 关键规则

1. **handlers/ 和 services/ 不能直接 import pyrogram / aiosqlite / httpx**
   - ✅ `from core.bot import Bot, Message, filters`
   - ✅ `from core.database import Database`
   - ✅ `from core.http import HttpClient`
   - ❌ `from pyrogram import Client`
2. **uv 管理 Python** — `uv run python3 ...`, `uv pip install ...`
3. **类型注解** + **中文 docstring**
4. **异步 everywhere**
5. **移除 Turnstile**，只保留本地题库
