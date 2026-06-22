#!/usr/bin/env python3
"""Verify all imports compile."""
import sys
sys.path.insert(0, '.')

modules = [
    ('config', 'from config import config'),
    ('core.bot', 'from core.bot import Bot'),
    ('core.database', 'from core.database import Database'),
    ('core.http', 'from core.http import HttpClient'),
    ('core.logger', 'from core.logger import get_logger'),
    ('core.models', 'from core.models import VerifiedUser, TopicMapping, ForwardMapping, ReplyMapping, BannedUser, WhitelistUser, RateLimit, VerifyLock, StatsMessage, StatsActiveUser, AppConfig, PendingQueue, ThreadMapping, EditNotice'),
    ('services.forward', 'from services.forward import ForwardService'),
    ('services.forward_topic', 'from services.forward_topic import MediaGroupCollector, TopicManager'),
    ('services.forward_edit', 'from services.forward_edit import EditSyncManager'),
    ('services.verify', 'from services.verify import VerifyService'),
    ('services.security', 'from services.security import SecurityService'),
    ('services.stats', 'from services.stats import StatsService'),
    ('services.menu', 'from services.menu import build_main_menu, build_spam_menu, build_union_menu, build_welcome_menu, build_autoreply_menu, build_forward_menu, build_users_menu, build_stats_menu'),
    ('utils.helpers', 'from utils.helpers import TTLCache, escape_html'),
    ('handlers.user', 'from handlers.user import register as user_register'),
    ('handlers.admin', 'from handlers.admin import register as admin_register'),
    ('handlers.callback', 'from handlers.callback import register as cb_register'),
]

all_ok = True
for name, imp in modules:
    try:
        exec(imp)
        print(f'  ✅ {name}')
    except Exception as e:
        print(f'  ❌ {name}: {e}')
        all_ok = False

if all_ok:
    print('\n✅ All imports OK')
else:
    print('\n❌ Some imports failed')
    sys.exit(1)
