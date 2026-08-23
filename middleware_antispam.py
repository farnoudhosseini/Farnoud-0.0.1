# محدودیت نرخ: حداکثر 5 پیام در 3 ثانیه برای هر کاربر

from __future__ import annotations
import time
from collections import defaultdict, deque
from typing import Deque, Dict

from telegram import Update
from telegram.ext import ContextTypes, TypeHandler, ApplicationHandlerStop

# user_id -> timestamps of recent updates
_buckets: Dict[int, Deque[float]] = defaultdict(deque)
WINDOW = 3.0
MAX_HITS = 5


def _is_spam(user_id: int) -> bool:
    now = time.monotonic()
    q = _buckets[user_id]
    while q and now - q[0] > WINDOW:
        q.popleft()
    if len(q) >= MAX_HITS:
        return True
    q.append(now)
    return False


async def antispam_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    # ادمین‌ها محدود نشوند (اختیاری — محدود می‌کنیم همه را برای سادگی،
    # ولی callbackهای زیاد ادمین را شل‌تر نگه می‌داریم با همان قانون)
    if _is_spam(user.id):
        # فقط برای پیام متنی جواب بده؛ برای کال‌بک فقط نادیده بگیر
        if update.message:
            try:
                await update.message.reply_text(
                    "⏳ کمی صبر کنید — پیام‌ها خیلی سریع ارسال شدند."
                )
            except Exception:
                pass
        raise ApplicationHandlerStop()


def install_antispam(application):
    # group=-1 تا قبل از بقیه handlerها اجرا شود
    application.add_handler(TypeHandler(Update, antispam_handler), group=-1)
