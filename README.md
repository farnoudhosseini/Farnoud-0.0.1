# Farnoud Bot

<p align="center">
  <img src="https://uploadkon.ir/uploads/edcb23_26image-png-2K-202608231552.jpeg" alt="Farnoud Bot" width="480"/>
</p>

<p align="center">
  <b>ربات فروش سرویس VPN + پنل مدیریت وب + Telegram Mini App</b><br/>
  رایگان و متن‌باز — توسعه‌یافته توسط <a href="https://github.com/FarnoudHosseini">Farnoud Hosseini</a>
</p>

<p align="center">
  <a href="https://t.me/+6vJiX_pRVcVjNWE0">گروه تلگرام پشتیبانی</a> ·
  <a href="https://donofa.ir/farnoudhosseini">حمایت مالی (Donate)</a> ·
  <a href="https://github.com/FarnoudHosseini/FarnoudBot">GitHub</a>
</p>

---

## نصب یک‌خطی (One-Line Install)

روی سرور اوبونتو ۲۲.۰۴ / ۲۴.۰۴ با دسترسی root:

```bash
curl -sSL https://raw.githubusercontent.com/FarnoudHosseini/FarnoudBot/main/install.sh | sudo bash
```

یا دانلود و اجرا:

```bash
wget -O install.sh https://raw.githubusercontent.com/FarnoudHosseini/FarnoudBot/main/install.sh
sudo bash install.sh
```

منوی اسکریپت:

```
1) Install
2) Update
3) Full Uninstall
```

### مراحل نصب خودکار
1. به‌روزرسانی سیستم و نصب پیش‌نیازها (Python, MySQL, Nginx, Certbot, UFW, Fail2ban)
2. دریافت دامنه (باید روی IP سرور ست شده باشد)
3. صدور و نصب گواهی SSL رایگان (Let's Encrypt)
4. دریافت توکن ربات از BotFather
5. دریافت آیدی عددی ادمین
6. ساخت دیتابیس با **پسورد تصادفی**، تکمیل کامل فایل `.env`، هش امن رمز ورود پنل وب
7. تنظیمات امنیتی نهایی + راه‌اندازی سرویس‌های systemd

پس از نصب، آدرس پنل و رمز ورود وب در خروجی نمایش داده می‌شود.

---

## قابلیت‌های ربات

### برای کاربر نهایی
- **خرید سرویس** با کیف پول (تأیید قبل از کسر موجودی)
- **انتخاب لوکیشن / پنل** مقصد
- **تست رایگان** با امکان انتخاب پنل
- **کیف پول**: شارژ کارت‌به‌کارت، کد هدیه، تاریخچه تراکنش
- **سرویس‌های من**: مشاهده وضعیت، حجم، انقضا، لینک اتصال
- **رفرال**: لینک دعوت، پاداش ثبت‌نام و درصد از خرید زیرمجموعه
- **تیکت پشتیبانی** با دپارتمان‌های قابل تنظیم
- **درخواست نمایندگی (Reseller)**
- **Telegram Mini App** موبایل‌محور با احراز هویت `initData` و HMAC سمت سرور
- منوی شیشه‌ای (Inline) قابل شخصی‌سازی + ایموجی پریمیوم

### برای ادمین (داخل ربات — دستور `/admin`)
- آمار ربات و داشبورد
- تنظیم همه پیام‌ها و خوش‌آمدگویی (با متغیر و Premium Emoji)
- مدیریت پنل‌های VPN (PasarGuard / X-UI و …)
- سقف فروش هر پنل
- محصولات و دسته‌بندی (Drag & Drop ترتیب)
- سرویس‌های فروخته‌شده و مدیریت سفارش
- کاربران ربات: جستجو، موجودی، نقش، مسدودسازی
- ارسال همگانی (همه / دارای موجودی / بدون موجودی / دارای زیرمجموعه) + پین
- مدیریت کارت‌های پرداخت
- درخواست‌های شارژ (تأیید / رد خودکار اختیاری)
- ایموجی پریمیوم و منوی شیشه‌ای
- ادمین‌های ربات
- سرویس ساعتی (روشن/خاموش)
- بهینه‌سازی و آنتی‌اسپم
- فاصله بکاپ خودکار دیتابیس
- مدیریت اعتبار ورود وب‌پنل از داخل ربات
- **دکمه شیشه‌ای لینک گیت‌هاب پروژه**

### پنل وب مدیریت
- UI با استایل Liquid Glass / macOS
- داشبورد آماری و نمودار
- مدیریت پنل‌ها، محصولات، سفارش‌ها، کاربران
- رفرال، تخفیف، هدیه، وفاداری
- تیکت‌های پشتیبانی
- تنظیمات پیام‌ها و شخصی‌سازی
- Mini App در مسیر `/miniapp/`

### امنیت
- پسورد ورود پنل وب با **هش werkzeug** (مهاجرت نرم از plaintext قدیمی)
- `.env` با مجوز ۶۰۰ و تولید خودکار `SECRET_KEY` و پسورد دیتابیس تصادفی
- Nginx reverse proxy + هدرهای امنیتی
- پورت ۵۰۰۰ فقط لوکال؛ فایروال UFW و Fail2ban
- احراز هویت Mini App فقط از طریق Telegram `initData` تأییدشده سمت سرور
- Idempotency برای خرید کیف‌پولی و قفل ردیف کاربر

---

## ساختار پروژه (خلاصه)

```
FarnoudBot/
├── main.py / bot.py          # ورود ربات تلگرام
├── admin_app.py              # پنل وب Flask + Mini App
├── config.py                 # خواندن از .env
├── database.py + db_*.py     # لایه دیتابیس
├── handlers/                 # هندلرهای ربات
├── services/                 # کلاینت پنل‌ها و provision
├── static/ / templates/      # فرانت پنل و مینی‌اپ
├── models_schema.sql
├── install.sh                # نصب‌کننده تعاملی
└── requirements.txt
```

---

## اجرا دستی (توسعه)

```bash
cp .env.example .env
# مقادیر BOT_TOKEN و ADMIN_ID و DB را پر کنید
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# دیتابیس و جداول را بسازید
python admin_app.py   # پنل → http://127.0.0.1:5000
python main.py        # ربات
```

ورود پیش‌فرض پنل پس از نصب اسکریپت: `admin` + رمز تصادفی نمایش‌داده‌شده.

---

## لینک‌ها

| مورد | لینک |
|------|------|
| مخزن | https://github.com/FarnoudHosseini/FarnoudBot |
| گروه پشتیبانی | https://t.me/+6vJiX_pRVcVjNWE0 |
| حمایت مالی | https://donofa.ir/farnoudhosseini |

---

**Credit:** Farnoud Hosseini  
ربات رایگان است. در صورت مفید بودن از طریق لینک دونیت حمایت کنید.
