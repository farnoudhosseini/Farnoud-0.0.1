# نقطه شروع اجرای ربات
# فقط ربات را اجرا می‌کند و هیچ منطق دیگری ندارد

from bot import create_bot

def main():
    """
    تابع اصلی اجرای ربات
    """
    print("🚀 در حال راه‌اندازی ربات فروش VPN...")
    
    # ساخت ربات
    application = create_bot()
    
    # شروع polling
    print("✅ ربات آماده است و در حال گوش دادن به پیام‌ها...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()