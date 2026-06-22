"""验证服务 — 本地题库验证。

只保留本地题库，移除 Turnstile。
"""

import json
import random
from typing import Any, Dict, List, Optional, Tuple

from core.bot import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message
from core.database import Database
from core.logger import get_logger

logger = get_logger("services.verify")

# 15 道题目（与原始 JS 一致）
LOCAL_QUIZ_QUESTIONS: List[Dict[str, Any]] = [
    {"q": "冰融化后会变成什么？", "opts": ["水", "石头", "木头", "火"], "a": 0},
    {"q": "正常人有几只眼睛？", "opts": ["1", "2", "3", "4"], "a": 1},
    {"q": "以下哪个属于水果？", "opts": ["白菜", "香蕉", "猪肉", "大米"], "a": 1},
    {"q": "1 加 2 等于几？", "opts": ["2", "3", "4", "5"], "a": 1},
    {"q": "5 减 2 等于几？", "opts": ["1", "2", "3", "4"], "a": 2},
    {"q": "2 乘以 3 等于几？", "opts": ["4", "5", "6", "7"], "a": 2},
    {"q": "10 加 5 等于几？", "opts": ["10", "12", "15", "20"], "a": 2},
    {"q": "8 减 4 等于几？", "opts": ["2", "3", "4", "5"], "a": 2},
    {"q": "在天上飞的交通工具是什么？", "opts": ["汽车", "轮船", "飞机", "自行车"], "a": 2},
    {"q": "星期一的后面是星期几？", "opts": ["星期日", "星期五", "星期二", "星期三"], "a": 2},
    {"q": "鱼通常生活在哪里？", "opts": ["树上", "土里", "水里", "火里"], "a": 2},
    {"q": "我们用什么器官来听声音？", "opts": ["眼睛", "鼻子", "耳朵", "嘴巴"], "a": 2},
    {"q": "晴朗的天空通常是什么颜色的？", "opts": ["绿色", "红色", "蓝色", "紫色"], "a": 2},
    {"q": "太阳从哪个方向升起？", "opts": ["西方", "南方", "东方", "北方"], "a": 2},
    {"q": "小狗发出的叫声通常是？", "opts": ["喵喵", "咩咩", "汪汪", "呱呱"], "a": 2},
]

# 验证配置
CHALLENGE_TTL = 60       # 单题有效期 60 秒
TRIGGER_WINDOW = 300     # 5 分钟窗口
TRIGGER_LIMIT = 3        # 5 分钟最多触发 3 次
MAX_ATTEMPTS = 3         # 每题最多尝试 3 次
VERIFICATION_TTL = 604800  # 验证有效期 7 天


class VerifyService:
    """验证服务 — 本地题库验证。"""

    def __init__(self, db: Database, bot: Bot):
        self.db = db
        self.bot = bot
        # 内存中存储活跃验证挑战
        self._challenges: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def generate_keyboard(question: Dict[str, Any]) -> InlineKeyboardMarkup:
        """生成题目 Inline 键盘。"""
        buttons = [
            InlineKeyboardButton(text=opt, callback_data=f"quiz_answer:{idx}")
            for idx, opt in enumerate(question["opts"])
        ]
        # 每行 2 个
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        return InlineKeyboardMarkup(inline_keyboard=rows)

    def create_challenge(self, user_id: int) -> Tuple[str, Dict[str, Any]]:
        """创建新的验证挑战，返回 (challenge_id, question)。"""
        question = random.choice(LOCAL_QUIZ_QUESTIONS)
        challenge = {
            "question": question,
            "correct_answer": question["a"],
            "attempts": 0,
            "created_at": __import__("time").time(),
        }
        challenge_id = f"quiz_{user_id}_{int(__import__('time').time())}"
        self._challenges[f"quiz:{user_id}"] = challenge
        return challenge_id, question

    def get_challenge(self, user_id: int) -> Optional[Dict[str, Any]]:
        """获取当前验证挑战。"""
        return self._challenges.get(f"quiz:{user_id}")

    def delete_challenge(self, user_id: int) -> None:
        """删除验证挑战。"""
        self._challenges.pop(f"quiz:{user_id}", None)

    def verify_answer(self, user_id: int, answer_index: int) -> Dict[str, Any]:
        """验证答案。

        Returns:
            dict: {"success": bool, "reason": str, "message": str}
        """
        challenge = self.get_challenge(user_id)
        if not challenge:
            return {"success": False, "reason": "expired", "message": "验证已过期，请重新获取题目"}

        if challenge["attempts"] >= MAX_ATTEMPTS:
            self.delete_challenge(user_id)
            return {"success": False, "reason": "max_attempts", "message": "尝试次数过多，请重新获取题目"}

        challenge["attempts"] += 1

        if answer_index == challenge["correct_answer"]:
            self.delete_challenge(user_id)
            return {"success": True}

        remaining = MAX_ATTEMPTS - challenge["attempts"]
        return {
            "success": False,
            "reason": "wrong_answer",
            "message": f"答案错误，还剩 {remaining} 次机会",
            "remaining": remaining,
        }

    async def check_trigger_limit(self, user_id: int) -> bool:
        """检查触发频率限制，返回是否允许。"""
        key = f"quiz_trigger:{user_id}"
        return await self.db.check_rate_limit(key, TRIGGER_WINDOW * 1000, TRIGGER_LIMIT)
