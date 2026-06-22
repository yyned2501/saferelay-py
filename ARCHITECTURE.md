# SafeRelay-Py 架构文档

## 文件树

```
saferelay-py/
├── main.py                      # 入口：创建依赖、注册 handler、启动
├── config.py                    # 配置，从环境变量读取
├── .clinerules                  # 项目规则
├── ARCHITECTURE.md              # 架构文档（本文件）
├── requirements.txt             # 依赖清单
├── .env.example                 # 环境变量模板
├── verify_imports.sh            # 导入链验证脚本
│
├── core/                        # 第三方库封装层（唯一允许直接 import 第三方库的层）
│   ├── __init__.py
│   ├── bot.py                   # 封装 Pyrogram/Kurigram Client
│   ├── models.py                # SQLAlchemy ORM 模型定义
│   ├── database.py              # 封装 SQLAlchemy async，提供 Database 类
│   ├── http.py                  # 封装 httpx.AsyncClient
│   └── logger.py                # 封装 logging，结构化日志 + 脱敏
│
├── services/                    # 业务逻辑层（只从 core/ 导入）
│   ├── __init__.py
│   ├── forward.py               # ForwardService：消息转发核心
│   ├── forward_topic.py         # TopicManager + MediaGroupCollector：话题管理
│   ├── forward_edit.py          # EditSyncManager：编辑同步
│   ├── verify.py                # VerifyService：本地题库验证
│   ├── security.py              # SecurityService：封禁/白名单/欺诈/垃圾过滤
│   ├── stats.py                 # StatsService：消息/用户统计
│   └── menu.py                  # 管理面板菜单构建函数
│
├── handlers/                    # Telegram 事件处理层（只从 core/ + services/ 导入）
│   ├── __init__.py
│   ├── user.py                  # 用户私聊消息、/start、验证触发
│   ├── admin.py                 # 管理员命令（/menu, /ban, /trust 等）
│   └── callback.py              # CallbackQuery 处理（验证答案 + 菜单导航）
│
├── utils/                       # 纯工具函数（零第三方依赖）
│   ├── __init__.py
│   └── helpers.py               # TTLCache, escape_html 等
│
└── data/                        # 运行时数据
    └── saferelay.db             # SQLite 数据库文件
```

## 模块职责

### core/ 层
| 模块 | 职责 | 被谁导入 |
|---|---|---|
| `bot.py` | 封装 Pyrogram Client，导出 Bot、Message、filters 等 | services/*, handlers/* |
| `models.py` | ORM 模型（VerifiedUser, ForwardMapping 等 12 个表） | 仅 core/database.py |
| `database.py` | Database 类，封装所有持久化操作 | services/*, handlers/* |
| `http.py` | HttpClient 封装 httpx | services/security.py |
| `logger.py` | 结构化日志 + 敏感数据脱敏 | 所有模块 |

### services/ 层
| 模块 | 职责 | 被谁导入 |
|---|---|---|
| `forward.py` | ForwardService — 消息双向转发、转发模式、管理员回复、暂存队列 | handlers/* |
| `forward_topic.py` | TopicManager — 话题创建管理；MediaGroupCollector — 媒体组收集 | 仅 services/forward.py |
| `forward_edit.py` | EditSyncManager — 用户和管理员消息编辑同步 | 仅 services/forward.py |
| `verify.py` | VerifyService — 本地题库验证挑战 | handlers/user.py, handlers/callback.py |
| `security.py` | SecurityService — 封禁/白名单/联合封禁/欺诈检测/垃圾过滤 | handlers/* |
| `stats.py` | StatsService — 消息计数、活跃用户统计 | handlers/* |
| `menu.py` | 管理面板各子菜单文本和键盘构建 | handlers/callback.py |

### handlers/ 层
| 模块 | 路由 | 调用服务 |
|---|---|---|
| `user.py` | 私聊消息、/start、/help | forward, verify, security, stats |
| `admin.py` | /menu, /ban, /unban, /trust 等命令 | forward, security, stats |
| `callback.py` | CallbackQuery（验证答案、菜单导航） | forward, verify, security, stats, menu |

## 引用拓扑

```
main.py
  ├── config.py
  ├── core/bot.py ←── services/*  ──→ handlers/*
  ├── core/database.py ←── services/*  ──→ handlers/*
  │     └── core/models.py
  ├── core/http.py ←── services/security.py
  └── core/logger.py ←── 所有模块

services/forward.py
  ├── services/forward_topic.py (TopicManager, MediaGroupCollector)
  └── services/forward_edit.py (EditSyncManager)

导入方向（严格单向）：
  main.py → core/* → services/* → handlers/*
  services/forward.py → services/forward_topic.py
  services/forward.py → services/forward_edit.py
  handlers/callback.py → services/menu.py
  utils/* → 无依赖（纯 Python）
```

## 关键约束

1. **严格分层**：import 方向为 `core/` → `services/` → `handlers/`。同级模块（services/ 内部）允许引用，不可反向。
2. **模型定义唯一性**：所有 ORM 模型集中在 `core/models.py`，任何模块不得重复定义。
3. **菜单与 handler 分离**：菜单文本/键盘构建在 `services/menu.py`，handler 仅做路由。
4. **文件上限**：每个 .py 文件不超过 300 行，超出则按职责拆分。
