"""SafeRelay-Py 主入口。

创建数据库、Bot 实例，注册所有 handler，启动 bot。
"""
import asyncio
import sys

from pyrogram import idle

import config as cfg
from core.bot import Bot
from core.database import Database
from core.http import HttpClient
from core.logger import get_logger

logger = get_logger("main")


async def amain() -> None:
    """异步主函数：初始化依赖，注册 handler，启动 bot。"""
    # 验证配置
    err = cfg.config.validate()
    if err:
        logger.error("config_invalid", {"error": err})
        print(f"[ERROR] 配置错误: {err}")
        sys.exit(1)

    logger.info("starting_saferelay", {"admin_count": len(cfg.config.admin_ids)})

    # 初始化数据库
    db = Database()
    await db.init()
    logger.info("db_initialized")

    # 初始化 HTTP 客户端
    http = HttpClient()

    # 初始化 Bot
    proxy_cfg = None
    if cfg.config.proxy_enabled:
        proxy_cfg = {
            "scheme": cfg.config.proxy_scheme,
            "hostname": cfg.config.proxy_host,
            "port": cfg.config.proxy_port,
        }
    bot = Bot(
        bot_token=cfg.config.bot_token,
        api_id=cfg.config.api_id,
        api_hash=cfg.config.api_hash,
        proxy=proxy_cfg,
    )

    # 导入并注册 handler（延迟导入避免循环依赖）
    from services.forward import ForwardService
    from services.security import SecurityService
    from services.stats import StatsService
    from services.verify import VerifyService

    forward_svc = ForwardService(
        db=db, bot=bot, admin_ids=cfg.config.admin_ids, group_id=cfg.config.group_id,
    )
    verify_svc = VerifyService(db=db, bot=bot)
    security_svc = SecurityService(
        db=db, bot=bot, http=http,
        admin_ids=cfg.config.admin_ids, admin_uid=cfg.config.admin_uid,
    )
    stats_svc = StatsService(db=db)

    # 注册 handler
    from handlers import user, admin, callback
    user.register(bot, db, forward_svc, verify_svc, security_svc, stats_svc)
    admin.register(bot, db, forward_svc, security_svc, stats_svc)
    callback.register(bot, db, forward_svc, verify_svc, security_svc, stats_svc)

    logger.info("all_handlers_registered")
    print("[INFO] SafeRelay-Py 启动完成，等待消息...")

    # 启动 bot 并保持运行
    await bot.start()
    await idle()
    await bot.stop()
    await db.close()
    await http.close()


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("[INFO] 收到退出信号")
    except Exception as e:
        print(f"[ERROR] 启动失败: {e}")
        logger.error("startup_failed", {"error": str(e)})
        sys.exit(1)
