#!/bin/bash
# ============================================================
#  Farnoud Bot — One-Line / Interactive Installer
#  Repo: https://github.com/FarnoudHosseini/FarnoudBot
#  Credit: Farnoud Hosseini
# ============================================================
set -euo pipefail

REPO_URL="https://github.com/FarnoudHosseini/FarnoudBot.git"
REPO_RAW="https://raw.githubusercontent.com/FarnoudHosseini/FarnoudBot/main"
INSTALL_DIR="/opt/farnoudbot"
SERVICE_BOT="farnoud-bot"
SERVICE_PANEL="farnoud-panel"

# رنگ‌ها
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_banner() {
  clear
  echo -e "${CYAN}"
  cat << 'BANNER'
 ███████╗ █████╗ ██████╗ ███╗   ██╗ ██████╗ ██╗   ██╗██████╗     ██╗  ██╗ ██████╗ ███████╗███████╗███████╗██╗███╗   ██╗██╗
 ██╔════╝██╔══██╗██╔══██╗████╗  ██║██╔═══██╗██║   ██║██╔══██╗    ██║  ██║██╔═══██╗██╔════╝██╔════╝██╔════╝██║████╗  ██║██║
 █████╗  ███████║██████╔╝██╔██╗ ██║██║   ██║██║   ██║██║  ██║    ███████║██║   ██║███████╗███████╗█████╗  ██║██╔██╗ ██║██║
 ██╔══╝  ██╔══██║██╔══██╗██║╚██╗██║██║   ██║██║   ██║██║  ██║    ██╔══██║██║   ██║╚════██║╚════██║██╔══╝  ██║██║╚██╗██║██║
 ██║     ██║  ██║██║  ██║██║ ╚████║╚██████╔╝╚██████╔╝██████╔╝    ██║  ██║╚██████╔╝███████║███████║███████╗██║██║ ╚████║██║
 ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ╚═════╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚══════╝╚══════╝╚═╝╚═╝  ╚═══╝╚═╝
BANNER
  echo -e "${NC}"
  echo -e "                    ${GREEN}★ Farnoud Bot ★${NC}"
  echo -e "          ربات فروش سرویس + پنل مدیریت + مینی‌اپ"
  echo ""
}

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo -e "${RED}❌ لطفاً با دسترسی root اجرا کنید: sudo bash install.sh${NC}"
    exit 1
  fi
}

random_str() {
  local len=${1:-24}
  tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$len"
}

random_pass() {
  tr -dc 'A-Za-z0-9!@#%+=_' </dev/urandom | head -c 20
}

install_prereqs() {
  echo -e "${YELLOW}📦 به‌روزرسانی و نصب پیش‌نیازها...${NC}"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    mysql-server mysql-client \
    nginx certbot python3-certbot-nginx \
    curl git ufw fail2ban \
    build-essential libssl-dev libffi-dev \
    > /dev/null
  systemctl enable --now mysql 2>/dev/null || service mysql start 2>/dev/null || true
  systemctl enable --now nginx 2>/dev/null || true
  echo -e "${GREEN}✅ پیش‌نیازها نصب شد${NC}"
}

clone_or_update_repo() {
  if [ -d "$INSTALL_DIR/.git" ]; then
    echo -e "${YELLOW}📥 به‌روزرسانی مخزن...${NC}"
    cd "$INSTALL_DIR"
    git fetch --all
    git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null || true
  else
    echo -e "${YELLOW}📥 کلون مخزن...${NC}"
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
  cd "$INSTALL_DIR"
  # حذف هرگونه .env حساس از مخزن در صورت وجود
  rm -f .env miniapp.py.bak 2>/dev/null || true
}

setup_venv() {
  echo -e "${YELLOW}🐍 محیط مجازی و وابستگی‌ها...${NC}"
  cd "$INSTALL_DIR"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  source venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  echo -e "${GREEN}✅ Python deps آماده${NC}"
}

prompt_domain() {
  echo ""
  echo -e "${CYAN}🌐 دامنه خود را وارد کنید (باید روی IP این سرور ست شده باشد)${NC}"
  echo -e "   مثال: panel.example.com"
  read -r -p "Domain: " DOMAIN
  DOMAIN=$(echo "$DOMAIN" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
  if [ -z "$DOMAIN" ]; then
    echo -e "${RED}دامنه خالی است.${NC}"
    exit 1
  fi
  # بررسی ساده DNS
  SERVER_IP=$(curl -s4 ifconfig.me || curl -s4 icanhazip.com || hostname -I | awk '{print $1}')
  DOMAIN_IP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)
  echo -e "IP سرور: ${YELLOW}${SERVER_IP}${NC}"
  if [ -n "$DOMAIN_IP" ]; then
    echo -e "IP دامنه: ${YELLOW}${DOMAIN_IP}${NC}"
    if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
      echo -e "${YELLOW}⚠️  IP دامنه با سرور یکی نیست. SSL ممکن است شکست بخورد. ادامه می‌دهید؟ (y/N)${NC}"
      read -r cont
      [[ "$cont" =~ ^[Yy]$ ]] || exit 1
    fi
  else
    echo -e "${YELLOW}⚠️  نتوانستیم IP دامنه را resolve کنیم. مطمئن شوید DNS ست شده.${NC}"
  fi
}

setup_ssl() {
  echo -e "${YELLOW}🔒 دریافت و نصب SSL با Certbot...${NC}"
  # کانفیگ موقت nginx برای challenge
  cat > /etc/nginx/sites-available/farnoudbot << NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
  ln -sf /etc/nginx/sites-available/farnoudbot /etc/nginx/sites-enabled/farnoudbot
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
  mkdir -p /var/www/html
  nginx -t && systemctl reload nginx

  if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --register-unsafely-without-email --redirect; then
    echo -e "${GREEN}✅ SSL نصب شد${NC}"
    MINIAPP_URL="https://${DOMAIN}/miniapp/"
    PANEL_URL="https://${DOMAIN}"
  else
    echo -e "${YELLOW}⚠️  SSL ناموفق بود. ادامه با HTTP...${NC}"
    MINIAPP_URL="http://${DOMAIN}/miniapp/"
    PANEL_URL="http://${DOMAIN}"
  fi

  # کانفیگ نهایی با پروکسی و هدرهای امنیتی
  cat > /etc/nginx/sites-available/farnoudbot << NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    # certbot مدیریت می‌کند؛ در صورت نبود fallback
    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Permissions-Policy "geolocation=(), microphone=(), camera=()" always;

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
NGINX
  # اگر SSL نبود، فقط HTTP
  if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
    cat > /etc/nginx/sites-available/farnoudbot << NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 20M;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX
  fi
  nginx -t && systemctl reload nginx
}

prompt_bot_token() {
  echo ""
  echo -e "${CYAN}🤖 توکن ربات تلگرام را وارد کنید (از @BotFather)${NC}"
  read -r -p "BOT_TOKEN: " BOT_TOKEN
  BOT_TOKEN=$(echo "$BOT_TOKEN" | tr -d '[:space:]')
  if [ -z "$BOT_TOKEN" ]; then
    echo -e "${RED}توکن خالی است.${NC}"
    exit 1
  fi
}

prompt_admin_id() {
  echo ""
  echo -e "${CYAN}👤 آیدی عددی ادمین تلگرام را وارد کنید${NC}"
  echo -e "   (از @userinfobot یا مشابه بگیرید)"
  read -r -p "ADMIN_ID: " ADMIN_ID
  ADMIN_ID=$(echo "$ADMIN_ID" | tr -d '[:space:]')
  if ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}آیدی باید عدد باشد.${NC}"
    exit 1
  fi
}

setup_database() {
  echo -e "${YELLOW}🗄️  راه‌اندازی دیتابیس با پسورد تصادفی...${NC}"
  DB_NAME="farnoudbot"
  DB_USER="farnoud"
  DB_PASS=$(random_pass)
  SECRET_KEY=$(random_str 48)
  WEB_ADMIN_PASS=$(random_pass)
  # هش پسورد وب با پایتون
  cd "$INSTALL_DIR"
  # shellcheck disable=SC1091
  source venv/bin/activate
  WEB_ADMIN_HASH=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('${WEB_ADMIN_PASS}'))")

  # ساخت یوزر و دیتابیس
  mysql -u root << SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

  # جداول پایه
  mysql -u root "${DB_NAME}" < setup_admins.sql 2>/dev/null || true
  if [ -f models_schema.sql ]; then
    mysql -u root "${DB_NAME}" < models_schema.sql 2>/dev/null || true
  fi

  # ادمین وب با هش
  mysql -u root "${DB_NAME}" << SQL
INSERT INTO admins (username, password) VALUES ('admin', '${WEB_ADMIN_HASH}')
ON DUPLICATE KEY UPDATE password = '${WEB_ADMIN_HASH}';
SQL

  # فایل .env
  cat > "$INSTALL_DIR/.env" << ENV
BOT_TOKEN=${BOT_TOKEN}
ADMIN_ID=${ADMIN_ID}
SECRET_KEY=${SECRET_KEY}

DB_HOST=localhost
DB_PORT=3306
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASS}
DB_NAME=${DB_NAME}

BOT_USERNAME=
TELEGRAM_INIT_DATA_MAX_AGE=86400
MIN_CHARGE=10000
MAX_CHARGE=50000000
MINIAPP_URL=${MINIAPP_URL}
ENV
  chmod 600 "$INSTALL_DIR/.env"

  # ذخیره اعتبار وب برای نمایش نهایی
  echo "${WEB_ADMIN_PASS}" > /root/.farnoud_web_pass
  chmod 600 /root/.farnoud_web_pass

  echo -e "${GREEN}✅ دیتابیس و .env آماده شد${NC}"
}

setup_systemd() {
  echo -e "${YELLOW}🔧 سرویس‌های systemd...${NC}"
  cat > /etc/systemd/system/${SERVICE_BOT}.service << SERV
[Unit]
Description=Farnoud Telegram Bot
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
Environment=PATH=${INSTALL_DIR}/venv/bin
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/python main.py
Restart=always
RestartSec=8
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERV

  cat > /etc/systemd/system/${SERVICE_PANEL}.service << SERV
[Unit]
Description=Farnoud Admin Panel + MiniApp
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
Environment=PATH=${INSTALL_DIR}/venv/bin
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/python admin_app.py
Restart=always
RestartSec=8
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERV

  systemctl daemon-reload
  systemctl enable ${SERVICE_BOT} ${SERVICE_PANEL}
  systemctl restart ${SERVICE_BOT} ${SERVICE_PANEL} || systemctl start ${SERVICE_BOT} ${SERVICE_PANEL}
  echo -e "${GREEN}✅ سرویس‌ها فعال شدند${NC}"
}

harden_security() {
  echo -e "${YELLOW}🛡  تنظیمات امنیتی نهایی...${NC}"
  # فایروال پایه
  if command -v ufw >/dev/null 2>&1; then
    ufw allow OpenSSH >/dev/null 2>&1 || true
    ufw allow 80/tcp >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
  fi
  # fail2ban
  systemctl enable --now fail2ban 2>/dev/null || true
  # مجوزها
  chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true
  chown -R root:root "$INSTALL_DIR"
  find "$INSTALL_DIR" -type d -exec chmod 755 {} \;
  find "$INSTALL_DIR" -type f -name "*.py" -exec chmod 644 {} \;
  # بستن پورت 5000 از بیرون (فقط لوکال)
  if command -v ufw >/dev/null 2>&1; then
    ufw deny 5000/tcp >/dev/null 2>&1 || true
  fi
  echo -e "${GREEN}✅ سخت‌سازی انجام شد${NC}"
}

do_install() {
  require_root
  print_banner
  echo -e "${GREEN}شروع نصب کامل Farnoud Bot...${NC}"
  install_prereqs
  clone_or_update_repo
  setup_venv
  prompt_domain
  setup_ssl
  prompt_bot_token
  prompt_admin_id
  setup_database
  setup_systemd
  harden_security

  WEB_PASS=$(cat /root/.farnoud_web_pass 2>/dev/null || echo "(see /root/.farnoud_web_pass)")
  echo ""
  echo -e "${GREEN}==============================================${NC}"
  echo -e "${GREEN}  ✅ نصب با موفقیت انجام شد!${NC}"
  echo -e "${GREEN}==============================================${NC}"
  echo ""
  echo -e "🌐 پنل مدیریت:  ${CYAN}${PANEL_URL}${NC}"
  echo -e "📱 مینی‌اپ:     ${CYAN}${MINIAPP_URL}${NC}"
  echo -e "👤 ورود پنل:    ${YELLOW}admin / ${WEB_PASS}${NC}"
  echo -e "📂 مسیر نصب:    ${INSTALL_DIR}"
  echo -e "🤖 دستور ربات:  /start  و  /admin"
  echo ""
  echo -e "سرویس‌ها:"
  echo -e "  systemctl status ${SERVICE_BOT}"
  echo -e "  systemctl status ${SERVICE_PANEL}"
  echo ""
  echo -e "Repo: ${CYAN}https://github.com/FarnoudHosseini/FarnoudBot${NC}"
  echo -e "Credit: ${CYAN}Farnoud Hosseini${NC}"
  echo -e "Donate: ${CYAN}https://donofa.ir/farnoudhosseini${NC}"
  echo ""
}

do_update() {
  require_root
  print_banner
  if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}نصب قبلی یافت نشد. ابتدا Install را اجرا کنید.${NC}"
    exit 1
  fi
  echo -e "${YELLOW}در حال آپدیت...${NC}"
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  # بکاپ .env
  cp -a "$INSTALL_DIR/.env" "/root/farnoud_env_backup_$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
  clone_or_update_repo
  setup_venv
  # .env را حفظ کن
  systemctl start ${SERVICE_BOT} ${SERVICE_PANEL}
  echo -e "${GREEN}✅ آپدیت انجام شد. سرویس‌ها ری‌استارت شدند.${NC}"
}

do_uninstall() {
  require_root
  print_banner
  echo -e "${RED}⚠️  حذف کامل Farnoud Bot (دیتابیس، سرویس، nginx، فایل‌ها)${NC}"
  read -r -p "آیا مطمئن هستید؟ بنویسید YES: " conf
  if [ "$conf" != "YES" ]; then
    echo "لغو شد."
    exit 0
  fi
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  systemctl disable ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  rm -f /etc/systemd/system/${SERVICE_BOT}.service /etc/systemd/system/${SERVICE_PANEL}.service
  systemctl daemon-reload
  rm -f /etc/nginx/sites-enabled/farnoudbot /etc/nginx/sites-available/farnoudbot
  systemctl reload nginx 2>/dev/null || true
  # حذف دیتابیس (اختیاری امن)
  mysql -u root -e "DROP DATABASE IF EXISTS farnoudbot; DROP USER IF EXISTS 'farnoud'@'localhost';" 2>/dev/null || true
  rm -rf "$INSTALL_DIR"
  rm -f /root/.farnoud_web_pass
  echo -e "${GREEN}✅ حذف کامل انجام شد.${NC}"
}

show_menu() {
  print_banner
  echo -e "  ${CYAN}1)${NC} Install"
  echo -e "  ${CYAN}2)${NC} Update"
  echo -e "  ${CYAN}3)${NC} Full Uninstall"
  echo ""
  echo -e "  Repo:   https://github.com/FarnoudHosseini/FarnoudBot"
  echo -e "  Credit: Farnoud Hosseini"
  echo -e "  Donate: https://donofa.ir/farnoudhosseini"
  echo ""
  read -r -p "انتخاب (1/2/3): " choice
  case "$choice" in
    1) do_install ;;
    2) do_update ;;
    3) do_uninstall ;;
    *) echo -e "${RED}گزینه نامعتبر${NC}"; exit 1 ;;
  esac
}

# اگر آرگومان داده شد
case "${1:-}" in
  install|--install|-i) do_install ;;
  update|--update|-u) do_update ;;
  uninstall|--uninstall|-x) do_uninstall ;;
  *) show_menu ;;
esac
