# SafeRelay-Py 项目规则

## 1. Core 封装层
handlers/services 不能直接 import 第三方库（pyrogram/aiosqlite/httpx/sqlalchemy）。
所有第三方库调用必须经由 `core/` 模块中转。
✅ `from core.bot import Bot, Message`
✅ `from core.database import Database`
❌ `from pyrogram import Client`
❌ `from sqlalchemy import select`

## 2. 数据库规范
使用 SQLAlchemy async ORM，不写 raw SQL。
ORM 模型定义在 `core/models.py`，Database 封装类在 `core/database.py`。
所有查询通过 ORM 的 select/merge/delete 完成。

## 3. 全栈 async
所有 I/O 操作为异步。入口模式：
```python
async def amain():
    await bot.start()
    await idle()
    await bot.stop()
asyncio.run(amain())
```

## 4. 单文件 ≤ 300 行
任何 .py 文件不应超过 300 行。超限时需拆分：
- ORM 模型 → `core/models.py`
- 业务逻辑 → 按职责拆到 `services/*.py` 不同模块
- 菜单构建 → `services/menu.py`
- Handler 保持轻量

## 5. 类型注解 + 中文 docstring
所有函数/方法必须有类型注解。
公共函数必须有中文 docstring 说明功能。

## 6. logger 替代 print
使用 `core.logger.get_logger()` 获取结构化日志记录器。
日志包含 action 名称和结构化 data dict：
```python
logger.info("user_verified", {"user_id": user_id})
```

## 7. Git commit 中文
提交信息使用中文撰写，聚焦 "why" 而非 "what"。

## 8. 配置统一读取
所有配置通过 `config.py` 的 Config 类从环境变量读取。
`BOT_TOKEN` 和 `ADMIN_IDS` 为必需项，缺失则报错退出。

## 9. 包结构
每个包必须有 `__init__.py`。
导入使用绝对路径（`from services.forward import ForwardService`）。

## 10. 先读 ARCHITECTURE.md
修改代码前先阅读 `ARCHITECTURE.md` 了解模块职责和引用拓扑。
新增模块需在 ARCHITECTURE.md 中记录。
