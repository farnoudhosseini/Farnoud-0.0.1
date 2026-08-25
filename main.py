# نقطه شروع اجرای ربات فرنود
# پشتیبانی از polling (VPS) و webhook (cPanel / aaPanel)

import os
import logging
from bot import create_bot
from config import USE_WEBHOOK, WEBHOOK_PATH, WEBHOOK_SECRET, PUBLIC_BASE_URL, BOT_TOKEN

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("farnoud")


def main():
    print("🚀 در حال راه‌اندازی ربات فرنود...")
    application = create_bot()

    if USE_WEBHOOK:
        if not PUBLIC_BASE_URL:
            raise SystemExit(
                "USE_WEBHOOK=1 است ولی PUBLIC_BASE_URL در .env تنظیم نشده.\n"
                "مثال: PUBLIC_BASE_URL=https://bot.yourdomain.com"
            )
        url_path = WEBHOOK_PATH.lstrip("/")
        webhook_url = f"{PUBLIC_BASE_URL.rstrip('/')}/{url_path}"
        listen = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")
        port = int(os.getenv("WEBHOOK_PORT", "8443"))
        print(f"🌐 حالت Webhook — URL: {webhook_url}")
        print(f"   Listen: {listen}:{port}")
        application.run_webhook(
            listen=listen,
            port=port,
            url_path=url_path,
            webhook_url=webhook_url,
            secret_token=WEBHOOK_SECRET or None,
            drop_pending_updates=True,
        )
    else:
        print("✅ ربات آماده است و در حال گوش دادن به پیام‌ها (Polling)...")
        application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
