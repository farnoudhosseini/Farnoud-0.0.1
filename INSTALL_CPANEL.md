> راهنمای اصلی و ساده نصب روی هاست: **[README_HOSTING.md](README_HOSTING.md)** (شامل نصب‌کننده وب `/install` و Cron)

# نصب FarnoudBot روی cPanel

cPanel معمولاً **هاست اشتراکی** است و محدودیت دارد:
- نمی‌توانید systemd یا process دائمی آزادانه اجرا کنید
- بهترین راه: **Setup Python App (Passenger)** + حالت **Webhook**

> اگر هاست شما «Setup Python App» ندارد، این ربات برای آن مناسب نیست و VPS / aaPanel پیشنهاد می‌شود.

---

## پیش‌نیاز
- دامنه یا ساب‌دامین با SSL (AutoSSL یا Let's Encrypt)
- MySQL از داخل cPanel
- گزینه **Setup Python App** (CloudLinux / Passenger)

---

## مراحل نصب

### ۱. ساخت دیتابیس
cPanel → MySQL Databases:
- Database: `user_farnoudbot`
- User + Password بسازید و Full Privileges بدهید
- نام کامل معمولاً به شکل `cpaneluser_farnoudbot` است

### ۲. آپلود فایل‌ها
- File Manager یا FTP → پوشه مثلاً `farnoudbot` داخل `public_html` **نگذارید**؛ بهتر است خارج از public باشد، مثلاً:
  ```
  /home/USER/farnoudbot/
  ```
  و دامنه/ساب‌دامین را به آن اشاره دهید، یا از Application root در Python App استفاده کنید.

فایل زیپ را آپلود و Extract کنید.

### ۳. Setup Python App
cPanel → Setup Python App → Create:
- Python version: 3.10 یا 3.11
- Application root: مسیر پوشه پروژه (`/home/USER/farnoudbot`)
- Application URL: دامنه یا ساب‌دامین (مثلاً `bot.yourdomain.com`)
- Application startup file: **`passenger_wsgi.py`**
- Application Entry point: `application`

سپس **Run Pip Install** و در کادر packages این‌ها را وارد کنید (یا از requirements.txt):
```
python-telegram-bot[job-queue]>=22.7
aiomysql
python-dotenv
flask
pymysql
werkzeug
requests
qrcode[pil]
cryptography
```

### ۴. فایل `.env`
در ریشه پروژه:
```bash
cp .env.example .env
```
محتوا (نمونه):
```
BOT_TOKEN=123456:ABC...
ADMIN_ID=123456789
SECRET_KEY=یک_رشته_بلند_تصادفی_حداقل_۳۲_کاراکتر

DB_HOST=localhost
DB_PORT=3306
DB_USER=cpaneluser_farnoud
DB_PASSWORD=پسورد_دیتابیس
DB_NAME=cpaneluser_farnoudbot

BOT_USERNAME=YourBotUsername
PUBLIC_BASE_URL=https://bot.yourdomain.com
MINIAPP_URL=https://bot.yourdomain.com/miniapp/

USE_WEBHOOK=1
WEBHOOK_PATH=/telegram/webhook
WEBHOOK_SECRET=یک_رمز_تصادفی_قوی
```

### ۵. ساخت جداول
phpMyAdmin → دیتابیس را انتخاب → Import → فایل `models_schema.sql`

یا از Terminal (اگر SSH دارید):
```bash
mysql -u USER -p DBNAME < models_schema.sql
```

### ۶. Restart اپلیکیشن
در Setup Python App دکمه **Restart** را بزنید.

پنل باید روی آدرس دامنه باز شود:
```
https://bot.yourdomain.com/
```
ورود پیش‌فرض بعد از ساخت ادمین در دیتابیس / یا از طریق ربات.

### ۷. ست کردن Webhook تلگرام
جایگزین TOKEN و SECRET:
```bash
curl "https://api.telegram.org/botTOKEN/setWebhook?url=https://bot.yourdomain.com/telegram/webhook&secret_token=WEBHOOK_SECRET"
```

بررسی:
```bash
curl "https://api.telegram.org/botTOKEN/getWebhookInfo"
```

### ۸. ادمین پنل وب
اگر جدول admins خالی است، یک کاربر با هش werkzeug بسازید یا از `setup_admins.sql` بعد از تنظیم رمز استفاده کنید.  
از داخل ربات با `/admin` (اگر ADMIN_ID درست باشد) هم می‌توانید مدیریت کنید.

---

## محدودیت‌های cPanel / Webhook-only

| قابلیت | وضعیت |
|--------|--------|
| پنل وب + Mini App | ✅ |
| دریافت پیام و دکمه‌ها | ✅ (webhook) |
| خرید / کیف پول / تیکت | ✅ |
| Jobهای زمان‌بندی (بکاپ خودکار، تأیید کارت خودکار، بهینه‌سازی دوره‌ای) | ⚠️ محدود — روی Passenger پایدار نیست |
| Polling دائمی | ❌ معمولاً مجاز نیست |

برای Jobهای کامل، VPS یا aaPanel با Supervisor بهتر است.

---

## عیب‌یابی
- خطای 500: لاگ Passenger در `stderr.log` داخل پوشه اپ
- وب‌هوک کار نمی‌کند: SSL معتبر، مسیر `/telegram/webhook`، و `USE_WEBHOOK=1`
- اتصال دیتابیس: نام کامل کاربر و دیتابیس cPanel را چک کنید
- ماژول ناقص: دوباره Pip Install از requirements.txt

---

## توصیه نهایی
- ترافیک متوسط به بالا → **VPS + install.sh** یا **aaPanel**
- فقط تست / ترافیک کم → cPanel + Webhook قابل استفاده است

---

## Cron Job برای کارهای زمان‌بندی (جایگزین JobQueue)

روی cPanel به‌جای JobQueue داخلی ربات از **Cron Jobs** استفاده کنید.

### مسیرها
فرض کنید پروژه اینجا باشد:
```
/home/USER/farnoudbot
```
و Python اپلیکیشن (از Setup Python App) مثلاً:
```
/home/USER/virtualenv/farnoudbot/3.11/bin/python
```
مسیر دقیق Python را از صفحه Setup Python App کپی کنید.

### افزودن Cron (cPanel → Cron Jobs)

| زمان | دستور |
|------|--------|
| هر ۲ دقیقه | `cd /home/USER/farnoudbot && /home/USER/virtualenv/farnoudbot/3.11/bin/python cron_jobs.py auto_approve >> /home/USER/logs/farnoud_cron.log 2>&1` |
| دقیقه ۵ هر ساعت | `cd /home/USER/farnoudbot && .../python cron_jobs.py hourly >> /home/USER/logs/farnoud_cron.log 2>&1` |
| هر روز ساعت ۰۳:۱۵ | `cd /home/USER/farnoudbot && .../python cron_jobs.py backup >> /home/USER/logs/farnoud_cron.log 2>&1` |
| یکشنبه ساعت ۰۴:۳۰ | `cd /home/USER/farnoudbot && .../python cron_jobs.py optimize >> /home/USER/logs/farnoud_cron.log 2>&1` |

نماد cron:
```
*/2 * * * *   ... auto_approve
5 * * * *     ... hourly
15 3 * * *    ... backup
30 4 * * 0    ... optimize
```

### تست دستی (SSH یا Terminal)
```bash
cd /home/USER/farnoudbot
/path/to/python cron_jobs.py backup
/path/to/python cron_jobs.py auto_approve
/path/to/python cron_jobs.py all
```

### نکات
- پوشه لاگ را از قبل بسازید: `mkdir -p /home/USER/logs`
- `card_auto_approve_minutes` را در پنل وب تنظیم کنید (۰ = غیرفعال)
- فاصله بکاپ در پنل (`backup interval`) فقط برای JobQueue داخلی است؛ در حالت Cron خودتان زمان را در crontab تعیین می‌کنید
