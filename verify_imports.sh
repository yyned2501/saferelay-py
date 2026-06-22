#!/bin/bash
set -e
cd /home/hermes/projects/saferelay-py
uv run python3 -c "
import sys; sys.path.insert(0, '.')
from config import Config; c = Config(); print('Config OK')
from core.logger import get_logger; log = get_logger('test')
from core.bot import Bot, Message, filters
from core.models import Base, VerifiedUser, ForwardMapping; print('core/models OK')
from core.database import Database
from core.http import HttpClient; print('core/ ALL OK')
from services.forward import ForwardService
from services.forward_topic import MediaGroupCollector, TopicManager; print('services/forward_topic OK')
from services.forward_edit import EditSyncManager; print('services/forward_edit OK')
from services.verify import VerifyService
from services.security import SecurityService
from services.stats import StatsService; print('services/ ALL OK')
from services.menu import build_main_menu, build_spam_menu; print('services/menu OK')
from handlers.user import register
from handlers.admin import register
from handlers.callback import register; print('handlers/ ALL OK')
print('===== ALL IMPORTS PASSED =====')
"
