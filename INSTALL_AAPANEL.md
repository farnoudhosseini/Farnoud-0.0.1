> راهنمای اصلی و ساده نصب روی هاست: **[README_HOSTING.md](README_HOSTING.md)** (شامل نصب‌کننده وب `/install` و Cron)

# نصب FarnoudBot روی aaPanel (宝塔)

aaPanel معمولاً روی VPS نصب می‌شود و دسترسی root دارید — نصب نسبتاً ساده است.

## پیش‌نیاز
- دامنه با DNS روی IP سرور
- SSL (Let's Encrypt از داخل aaPanel)
- Python 3.10+ و MySQL/MariaDB

---

## روش پیشنهادی ۱: Supervisor + Polling (ساده‌ترین و پایدارترین)

### ۱. آپلود پروژه
```bash
cd /www/wwwroot
# زیپ را آپلود و استخراج کنید
unzip FarnoudBot-host-ready.zip -d farnoudbot
cd farnoudbot
```

### ۲. ساخت دیتابیس از پنل aaPanel
- Database → Add database  
  نام: `farnoudbot`  
  کاربر: `farnoud`  
  پسورد قوی بسازید و یادداشت کنید

### ۳. فایل `.env`
```bash
cp .env.example .env
nano .env
```
مقادیر را پر کنید:
```
BOT_TOKEN=...
ADMIN_ID=...
SECRET_KEY=یک_رشته_بلند_تصادفی
DB_HOST=localhost
DB_USER=farnoud
DB_PASSWORD=پسورد_دیتابیس
DB_NAME=farnoudbot
PUBLIC_BASE_URL=https://bot.yourdomain.com
MINIAPP_URL=https://bot.yourdomain.com/miniapp/
USE_WEBHOOK=0
```

### ۴. وابستگی‌های Python
```bash
# در aaPanel: App Store → Python Project یا:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

### ۵. جداول دیتابیس
```bash
# با mysql کلاینت یا phpMyAdmin فایل models_schema.sql را import کنید
mysql -u farnoud -p farnoudbot < models_schema.sql
```

### ۶. سایت در aaPanel
- Website → Add site → دامنه را اضافه کنید
- SSL → Let's Encrypt
- Reverse proxy به `http://127.0.0.1:5000` (برای پنل)

یا مستقیماً با gunicorn روی پورت ۵۰۰۰ و پروکسی Nginx.

### ۷. Supervisor (برای ربات و پنل)
در aaPanel → Supervisor → Add daemon:

**ربات:**
```
Name: farnoud-bot
Run user: root (یا www)
Run directory: /www/wwwroot/farnoudbot
Start command: /www/wwwroot/farnoudbot/venv/bin/python main.py
Process num: 1
```

**پنل:**
```
Name: farnoud-panel
Run directory: /www/wwwroot/farnoudbot
Start command: /www/wwwroot/farnoudbot/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 wsgi:application
Process num: 1
```

Nginx را به `127.0.0.1:5000` پروکسی کنید.

### ۸. تنظیم وب‌هوک تلگرام (اختیاری)
اگر ترجیح می‌دهید webhook باشد:
```
USE_WEBHOOK=1
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=یک_رمز_تصادفی
```
سپس فقط **یک** پروسه gunicorn کافی است (پنل + وب‌هوک). ربات جداگانه لازم نیست؛ ولی JobQueue (بکاپ خودکار و ...) محدود می‌شود مگر Supervisor جدا برای worker داشته باشید.

---

## روش ۲: فقط Webhook داخل Flask (یک پروسه)

```
USE_WEBHOOK=1
PUBLIC_BASE_URL=https://bot.yourdomain.com
```
فقط gunicorn را با Supervisor اجرا کنید. تلگرام را به آدرس زیر ست کنید:

```
https://bot.yourdomain.com/telegram/webhook
```

ست کردن وب‌هوک:
```bash
curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://bot.yourdomain.com/telegram/webhook&secret_token=WEBHOOK_SECRET"
```

---

## نکات
- پورت ۵۰۰۰ را از فایروال عمومی ببندید؛ فقط Nginx به آن دسترسی داشته باشد.
- بعد از تغییر `.env` سرویس‌ها را Restart کنید.
- لاگ: Supervisor logs در aaPanel.

---

## Cron Job (جایگزین یا مکمل JobQueue)

اگر از حالت Webhook استفاده می‌کنید یا می‌خواهید Jobها مستقل از process ربات باشند:

### aaPanel → Cron
نوع: Shell script

```bash
#!/bin/bash
cd /www/wwwroot/farnoudbot
# اگر venv دارید:
source venv/bin/activate
python cron_jobs.py auto_approve
```

یا مستقیم در crontab سرور:

```cron
*/2 * * * * cd /www/wwwroot/farnoudbot && /www/wwwroot/farnoudbot/venv/bin/python cron_jobs.py auto_approve >> /tmp/farnoud_cron.log 2>&1
5 * * * *   cd /www/wwwroot/farnoudbot && /www/wwwroot/farnoudbot/venv/bin/python cron_jobs.py hourly >> /tmp/farnoud_cron.log 2>&1
15 3 * * *  cd /www/wwwroot/farnoudbot && /www/wwwroot/farnoudbot/venv/bin/python cron_jobs.py backup >> /tmp/farnoud_cron.log 2>&1
30 4 * * 0  cd /www/wwwroot/farnoudbot && /www/wwwroot/farnoudbot/venv/bin/python cron_jobs.py optimize >> /tmp/farnoud_cron.log 2>&1
```

### Jobهای موجود در cron_jobs.py
| نام | کار |
|-----|-----|
| `auto_approve` | تأیید خودکار رسید کارت‌به‌کارت |
| `hourly` | کسر هزینه سرویس‌های ساعتی + اعلان |
| `backup` | بکاپ دیتابیس و ارسال به گروه گزارش |
| `optimize` | پاکسازی سفارش/لاگ قدیمی + گزارش به ادمین |
| `all` | اجرای همه به‌ترتیب |

اگر ربات را با **Polling + Supervisor** اجرا می‌کنید، JobQueue داخلی هم کار می‌کند و Cron اختیاری است (برای اطمینان می‌توانید فقط یکی را فعال نگه دارید تا دوبار اجرا نشود).
