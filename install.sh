#!/bin/bash
# اسکریپت نصب سریع فرنود روی اوبونتو
# اجرا: sudo bash install.sh

set -e

echo "=========================================="
echo "  نصب پروژه فرنود (Farnoud)"
echo "=========================================="

# بررسی root
if [ "$EUID" -ne 0 ]; then
  echo "❌ لطفاً با sudo اجرا کنید: sudo bash install.sh"
  exit 1
fi

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "📦 [1/6] به‌روزرسانی سیستم و نصب پیش‌نیازها..."
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
  python3 python3-pip python3-venv \
  mysql-server mysql-client \
  curl git > /dev/null

echo "✅ پیش‌نیازها نصب شد"

echo ""
echo "🐍 [2/6] ساخت محیط مجازی پایتون..."
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "✅ کتابخانه‌های پایتون نصب شد"

echo ""
echo "🗄️  [3/6] راه‌اندازی MySQL..."
# اطمینان از اجرای MySQL
systemctl start mysql 2>/dev/null || service mysql start 2>/dev/null || true
systemctl enable mysql 2>/dev/null || true

# ساخت دیتابیس و جداول (بدون پسورد root در نصب پیش‌فرض اوبونتو با auth_socket)
mysql -u root << 'SQL' 2>/dev/null || mysql -u root -e "source setup_admins.sql" 2>/dev/null || true
CREATE DATABASE IF NOT EXISTS farnoudbot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE farnoudbot;
CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO admins (username, password) VALUES ('admin', 'admin123')
ON DUPLICATE KEY UPDATE password = 'admin123';
CREATE TABLE IF NOT EXISTS settings (
    `key` VARCHAR(100) PRIMARY KEY,
    `value` TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT IGNORE INTO settings (`key`, `value`)
VALUES ('welcome_message', 'سلام! به ربات فرنود خوش آمدید 👋');
SQL

echo "✅ دیتابیس آماده شد"

echo ""
echo "⚙️  [4/6] بررسی فایل .env..."
if [ ! -f ".env" ]; then
  cat > .env << 'ENV'
BOT_TOKEN=YOUR_BOT_TOKEN_HERE
ADMIN_ID=YOUR_TELEGRAM_ID

SECRET_KEY=CHANGE_ME_TO_A_RANDOM_SECRET

DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=farnoudbot
ENV
  echo "⚠️  فایل .env ساخته شد — لطفاً BOT_TOKEN و ADMIN_ID را تنظیم کنید"
else
  echo "✅ فایل .env موجود است"
fi

echo ""
echo "🔧 [5/6] ساخت سرویس systemd (اختیاری)..."
# سرویس ربات
cat > /etc/systemd/system/farnoud-bot.service << SERV
[Unit]
Description=Farnoud Telegram Bot
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERV

# سرویس پنل
cat > /etc/systemd/system/farnoud-panel.service << SERV
[Unit]
Description=Farnoud Admin Panel
After=network.target mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR
Environment=PATH=$PROJECT_DIR/venv/bin
ExecStart=$PROJECT_DIR/venv/bin/python admin_app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERV

systemctl daemon-reload
echo "✅ سرویس‌ها ساخته شدند"

echo ""
echo "🚀 [6/6] راهنمای اجرا..."
echo ""
echo "=========================================="
echo "  نصب کامل شد!"
echo "=========================================="
echo ""
echo "۱) فایل .env را ویرایش کنید:"
echo "   nano $PROJECT_DIR/.env"
echo ""
echo "۲) اجرای دستی برای تست:"
echo "   cd $PROJECT_DIR"
echo "   source venv/bin/activate"
echo "   python admin_app.py    # پنل → http://SERVER_IP:5000"
echo "   python main.py         # ربات"
echo ""
echo "۳) یا با systemd:"
echo "   systemctl start farnoud-panel"
echo "   systemctl start farnoud-bot"
echo "   systemctl enable farnoud-panel farnoud-bot"
echo ""
echo "ورود پنل: admin / admin123"
echo "دستورات ربات: /start  و  /admin"
echo "=========================================="
