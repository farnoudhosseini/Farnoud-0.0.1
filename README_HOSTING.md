# راهنمای نصب روی هاست، cPanel و aaPanel

این راهنما برای کسانی است که می‌خواهند **FarnoudBot** را روی هاست یا پنل کنترل نصب کنند.  
نصب روی **سرور اوبونتو (VPS)** همچنان با همان `install.sh` قبلی انجام می‌شود و تغییری در آن لازم نیست.

---

## کدام روش را انتخاب کنم؟

| محیط | روش پیشنهادی | فایل راهنما |
|------|----------------|-------------|
| سرور اوبونتو / VPS | `sudo bash install.sh` | README اصلی |
| **aaPanel** | آپلود + نصب‌کننده وب `/install` + Supervisor | همین فایل |
| **cPanel** | Python App + نصب‌کننده وب `/install` + Cron | همین فایل |

---

## نصب با نصب‌کننده وب (ساده‌ترین راه)

بعد از اینکه فایل‌ها روی هاست قرار گرفت و دامنه به پروژه وصل شد:

1. در مرورگر بروید به:
   ```
   https://دامنه-شما/install
   ```
2. فرم را پر کنید:
   - اطلاعات دیتابیس MySQL
   - توکن ربات و آیدی عددی ادمین
   - آدرس HTTPS دامنه
   - انتخاب Webhook (برای cPanel) یا Polling (برای aaPanel با Supervisor)
   - رمز ورود پنل وب
3. روی **شروع نصب** بزنید.
4. در پایان، نام کاربری پنل `admin` و رمزی که وارد کردید نمایش داده می‌شود.

پس از نصب موفق، مسیر `/install` قفل می‌شود.

---

## مراحل قبل از باز کردن /install

### ۱) ساخت دیتابیس
- در cPanel یا aaPanel یک دیتابیس MySQL و یک کاربر بسازید و دسترسی کامل بدهید.
- نام‌ها را یادداشت کنید (در cPanel اغلب با پیشوند نام کاربری شروع می‌شوند).

### ۲) آپلود پروژه
فایل زیپ را آپلود و Extract کنید. پوشه نهایی باید شامل این فایل‌ها باشد:
- `admin_app.py` ، `main.py` ، `passenger_wsgi.py` ، `wsgi.py` ، `cron_jobs.py` ، `requirements.txt`

### ۳) اتصال دامنه + SSL
- دامنه یا ساب‌دامین را به این پوشه وصل کنید.
- SSL حتماً فعال باشد (Let's Encrypt / AutoSSL).

### ۴) اجرای Python

**cPanel**
- Setup Python App → نسخه ۳.۱۰ یا ۳.۱۱
- Application root = پوشه پروژه
- Startup file = `passenger_wsgi.py`
- Entry point = `application`
- پکیج‌ها را از `requirements.txt` نصب کنید
- Restart

**aaPanel**
- Website بسازید + SSL
- Python پروژه / venv:
  ```bash
  cd /www/wwwroot/farnoudbot
  python3 -m venv venv
  source venv/bin/activate
  pip install -r requirements.txt
  pip install gunicorn
  ```
- موقتاً برای دیدن نصب‌کننده:
  ```bash
  source venv/bin/activate
  gunicorn -w 1 -b 0.0.0.0:5000 wsgi:application
  ```
  و در Nginx روی دامنه پروکسی به پورت ۵۰۰۰ بگذارید؛ بعداً با Supervisor دائمی می‌کنید.

سپس `https://دامنه/install` را باز کنید.

---

## بعد از نصب — کارهایی که باید انجام دهید

### الف) تنظیم Mini App در BotFather

1. در تلگرام به `@BotFather` بروید.
2. دستور `/mybots` → ربات خود را انتخاب کنید.
3. **Bot Settings** → **Menu Button** (یا Configure Mini App).
4. آدرس مینی‌اپ را وارد کنید:
   ```
   https://دامنه-شما/miniapp/
   ```
   (همان آدرسی که در پنل و `.env` به‌عنوان `MINIAPP_URL` ذخیره شده است.)
5. در پنل وب ربات هم از بخش مربوط به Mini App می‌توانید URL را بررسی/ذخیره کنید.

### ب) تنظیم گروه گزارش با `/setgroup`

1. یک **سوپرگروه** بسازید و در صورت امکان Topics / Forum را روشن کنید.
2. ربات را **ادمین** گروه کنید.
3. با اکانت ادمین اصلی ربات (همان `ADMIN_ID`) داخل گروه دستور زیر را بزنید:
   ```
   /setgroup
   ```
4. ربات گروه را ذخیره می‌کند و اگر گروه تاپیک‌دار باشد، تاپیک‌های گزارش (بکاپ، خطا و …) را می‌سازد.
5. برای تست بکاپ دستی:
   ```
   /backup
   ```

### ج) Cron Jobها (خیلی مهم روی هاست)

روی cPanel و حالت Webhook، کارهای زمان‌بندی با فایل `cron_jobs.py` انجام می‌شود.

**دستورهای آماده:**

```bash
python cron_jobs.py auto_approve   # تأیید خودکار رسید کارت
python cron_jobs.py hourly         # کسر سرویس ساعتی
python cron_jobs.py backup         # بکاپ دیتابیس
python cron_jobs.py optimize       # پاکسازی داده قدیمی
python cron_jobs.py all            # همه با هم
```

**نمونه زمان‌بندی پیشنهادی:**

| زمان | دستور |
|------|--------|
| هر ۲ دقیقه | `... python cron_jobs.py auto_approve` |
| دقیقه ۵ هر ساعت | `... python cron_jobs.py hourly` |
| هر روز ۰۳:۱۵ | `... python cron_jobs.py backup` |
| یکشنبه‌ها ۰۴:۳۰ | `... python cron_jobs.py optimize` |

**cPanel → Cron Jobs**  
مسیر کامل `python` را از صفحه Setup Python App کپی کنید:

```bash
cd /home/USER/farnoudbot && /home/USER/virtualenv/.../bin/python cron_jobs.py auto_approve >> /home/USER/logs/farnoud_cron.log 2>&1
```

**aaPanel → Cron**  
همان دستورها با مسیر venv خودتان، مثلاً:

```bash
cd /www/wwwroot/farnoudbot && /www/wwwroot/farnoudbot/venv/bin/python cron_jobs.py auto_approve >> /tmp/farnoud_cron.log 2>&1
```

> اگر روی aaPanel ربات را با **Polling + Supervisor** اجرا می‌کنید، Job داخلی ربات هم فعال است. در آن حالت Cron را برای همان کار روشن نکنید تا دوبار اجرا نشود.

---

## aaPanel — اجرای دائمی (Supervisor)

بعد از نصب وب:

**پنل (و وب‌هوک اگر Webhook انتخاب کرده‌اید):**
```bash
/www/wwwroot/farnoudbot/venv/bin/gunicorn -w 2 -b 127.0.0.1:5000 wsgi:application
```

**ربات Polling (فقط اگر USE_WEBHOOK=0):**
```bash
/www/wwwroot/farnoudbot/venv/bin/python main.py
```

هر دو را در Supervisor با Restart=always ثبت کنید و Nginx را به `127.0.0.1:5000` پروکسی کنید.

---

## cPanel — حالت پیشنهادی

- `USE_WEBHOOK=1` (نصب‌کننده وب به‌صورت پیش‌فرض همین را پیشنهاد می‌دهد)
- فقط Python App (Passenger) کافی است؛ process جدا برای ربات لازم نیست
- حتماً Cron را طبق جدول بالا تنظیم کنید

بررسی وب‌هوک:
```bash
curl "https://api.telegram.org/botTOKEN/getWebhookInfo"
```

---

## عیب‌یابی سریع

| مشکل | راه‌حل |
|------|--------|
| `/install` باز نمی‌شود | Python App / gunicorn روشن است؟ دامنه به پوشه درست اشاره می‌کند؟ |
| خطای دیتابیس در نصب | نام کاربر/دیتابیس کامل cPanel را وارد کنید؛ دسترسی Full باشد |
| ربات جواب نمی‌دهد | وب‌هوک ست شده؟ SSL معتبر است؟ `USE_WEBHOOK=1`؟ |
| مینی‌اپ باز نمی‌شود | URL در BotFather با `/miniapp/` درست است؟ |
| بکاپ نمی‌آید | `/setgroup` زده‌اید؟ Cron بکاپ فعال است؟ |
| نصب دوباره | فایل‌های `.installed` و در صورت نیاز `.env` را حذف کنید و دوباره `/install` را باز کنید |

---

## یادآوری مهم درباره VPS اوبونتو

روی سرور اوبونتو همچنان فقط از این روش استفاده کنید:

```bash
sudo bash install.sh
```

این مسیر با systemd، Nginx و SSL خودکار کار می‌کند و **نیازی به نصب‌کننده وب ندارد**.  
فایل‌های مربوط به هاست (`passenger_wsgi.py`، `cron_jobs.py`، `/install`) روی VPS مزاحم نیستند و رفتار نصب اوبونتو را عوض نمی‌کنند.

---

**پشتیبانی:** گروه تلگرام پروژه در README اصلی لینک شده است.
