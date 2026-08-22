# نقطه شروع اجرای ربات فرنود

from bot import create_bot

def main():
    print("🚀 در حال راه‌اندازی ربات فرنود...")
    application = create_bot()
    print("✅ ربات آماده است و در حال گوش دادن به پیام‌ها...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
