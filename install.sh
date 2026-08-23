#!/bin/bash
# ============================================================
#  Farnoud Bot — Professional Installer
#  Repo : https://github.com/FarnoudHosseini/FarnoudBot
#  Credit: Farnoud Hosseini
# ============================================================
set -euo pipefail

REPO_URL="https://github.com/FarnoudHosseini/FarnoudBot.git"
INSTALL_DIR="/opt/farnoudbot"
SERVICE_BOT="farnoud-bot"
SERVICE_PANEL="farnoud-panel"
APP_USER="farnoud"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# رنگ‌ها
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
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
  echo -e "                    ${GREEN}${BOLD}★ Farnoud Bot ★${NC}"
  echo -e "          ربات فروش سرویس + پنل مدیریت + مینی‌اپ"
  echo ""
}

log_ok()   { echo -e "${GREEN}✅ $*${NC}"; }
log_info() { echo -e "${YELLOW}▶  $*${NC}"; }
log_err()  { echo -e "${RED}❌ $*${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    log_err "لطفاً با دسترسی root اجرا کنید:"
    echo "   sudo bash install.sh"
    exit 1
  fi
}

random_str() {
  local len=${1:-32}
  tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$len"
}

random_pass() {
  # بدون کاراکترهایی که در شل/SQL مشکل‌ساز هستند
  tr -dc 'A-Za-z0-9@#%+=_' </dev/urandom | head -c 22
}

# ------------------------------------------------------------
# پیش‌نیازها
# ------------------------------------------------------------
install_prereqs() {
  log_info "به‌روزرسانی و نصب پیش‌نیازها..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    mysql-server mysql-client \
    nginx certbot python3-certbot-nginx \
    curl git ufw fail2ban rsync \
    build-essential libssl-dev libffi-dev pkg-config \
    > /dev/null

  systemctl enable --now mysql 2>/dev/null || service mysql start 2>/dev/null || true
  systemctl enable --now nginx 2>/dev/null || true
  log_ok "پیش‌نیازها نصب شد"
}

# ------------------------------------------------------------
# کاربر سیستمی
# ------------------------------------------------------------
ensure_app_user() {
  if ! id "$APP_USER" &>/dev/null; then
    useradd --system --home "$INSTALL_DIR" --shell /usr/sbin/nologin "$APP_USER"
    log_ok "کاربر سیستمی ${APP_USER} ساخته شد"
  fi
}

# ------------------------------------------------------------
# دریافت سورس
# ------------------------------------------------------------
is_local_source() {
  [ -f "$SCRIPT_DIR/main.py" ] && [ -f "$SCRIPT_DIR/requirements.txt" ] && [ -f "$SCRIPT_DIR/admin_app.py" ]
}

deploy_source() {
  ensure_app_user
  mkdir -p "$INSTALL_DIR"

  if is_local_source; then
    log_info "سورس لوکال شناسایی شد — کپی به ${INSTALL_DIR}..."
    # کپی محتویات پروژه (بدون venv و .git و فایل‌های حساس)
    rsync -a --delete \
      --exclude='.git' \
      --exclude='venv' \
      --exclude='__pycache__' \
      --exclude='*.pyc' \
      --exclude='.env' \
      --exclude='miniapp.py.bak' \
      --exclude='install.sh' \
      "$SCRIPT_DIR/" "$INSTALL_DIR/"
    # خود اسکریپت را هم کپی کن تا بعداً update/uninstall کار کند
    cp -f "$SCRIPT_DIR/install.sh" "$INSTALL_DIR/install.sh"
    chmod +x "$INSTALL_DIR/install.sh"
  else
    if [ -d "$INSTALL_DIR/.git" ]; then
      log_info "به‌روزرسانی مخزن گیت..."
      cd "$INSTALL_DIR"
      git fetch --all --prune
      git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null || true
    else
      log_info "کلون مخزن از گیت‌هاب..."
      rm -rf "$INSTALL_DIR"
      git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
    fi
  fi

  cd "$INSTALL_DIR"
  rm -f .env miniapp.py.bak 2>/dev/null || true
  chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"
  log_ok "سورس آماده است در ${INSTALL_DIR}"
}

# ------------------------------------------------------------
# محیط مجازی پایتون
# ------------------------------------------------------------
setup_venv() {
  log_info "ساخت محیط مجازی و نصب وابستگی‌ها..."
  cd "$INSTALL_DIR"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  source venv/bin/activate
  pip install --upgrade pip setuptools wheel -q
  pip install -r requirements.txt -q
  chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR/venv"
  log_ok "وابستگی‌های پایتون نصب شد"
}

# ------------------------------------------------------------
# دامنه و SSL
# ------------------------------------------------------------
prompt_domain() {
  echo ""
  echo -e "${CYAN}${BOLD}🌐 دامنه خود را وارد کنید${NC}"
  echo -e "   (باید A Record آن روی IP این سرور ست شده باشد)"
  echo -e "   مثال: panel.example.com"
  read -r -p "Domain: " DOMAIN
  DOMAIN=$(echo "$DOMAIN" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
  if [ -z "$DOMAIN" ]; then
    log_err "دامنه خالی است."
    exit 1
  fi

  SERVER_IP=$(curl -s4 --max-time 8 ifconfig.me 2>/dev/null || curl -s4 --max-time 8 icanhazip.com 2>/dev/null || hostname -I | awk '{print $1}')
  DOMAIN_IP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)

  echo -e "IP سرور : ${YELLOW}${SERVER_IP}${NC}"
  if [ -n "$DOMAIN_IP" ]; then
    echo -e "IP دامنه : ${YELLOW}${DOMAIN_IP}${NC}"
    if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
      log_warn "IP دامنه با سرور یکی نیست. SSL ممکن است شکست بخورد."
      read -r -p "ادامه می‌دهید؟ (y/N): " cont
      [[ "$cont" =~ ^[Yy]$ ]] || exit 1
    fi
  else
    log_warn "نتوانستیم IP دامنه را resolve کنیم. مطمئن شوید DNS ست شده."
  fi
}

write_nginx_http_only() {
  cat > /etc/nginx/sites-available/farnoudbot << NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 20M;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

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
}

write_nginx_ssl() {
  cat > /etc/nginx/sites-available/farnoudbot << NGINX
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

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
}

setup_ssl() {
  log_info "پیکربندی Nginx و دریافت SSL..."
  mkdir -p /var/www/html
  write_nginx_http_only
  ln -sf /etc/nginx/sites-available/farnoudbot /etc/nginx/sites-enabled/farnoudbot
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
  nginx -t && systemctl reload nginx

  USE_SSL=0
  if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
       --register-unsafely-without-email --redirect 2>/dev/null; then
    if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
      write_nginx_ssl
      nginx -t && systemctl reload nginx
      USE_SSL=1
      log_ok "SSL با موفقیت نصب شد"
    fi
  fi

  if [ "$USE_SSL" -eq 1 ]; then
    MINIAPP_URL="https://${DOMAIN}/miniapp/"
    PANEL_URL="https://${DOMAIN}"
  else
    log_warn "SSL ناموفق بود — ادامه با HTTP"
    write_nginx_http_only
    nginx -t && systemctl reload nginx
    MINIAPP_URL="http://${DOMAIN}/miniapp/"
    PANEL_URL="http://${DOMAIN}"
  fi
}

# ------------------------------------------------------------
# توکن و ادمین
# ------------------------------------------------------------
prompt_bot_token() {
  echo ""
  echo -e "${CYAN}${BOLD}🤖 توکن ربات تلگرام (از @BotFather)${NC}"
  read -r -p "BOT_TOKEN: " BOT_TOKEN
  BOT_TOKEN=$(echo "$BOT_TOKEN" | tr -d '[:space:]')
  if [ -z "$BOT_TOKEN" ]; then
    log_err "توکن خالی است."
    exit 1
  fi
}

prompt_admin_id() {
  echo ""
  echo -e "${CYAN}${BOLD}👤 آیدی عددی ادمین تلگرام${NC}"
  echo -e "   (از @userinfobot بگیرید)"
  read -r -p "ADMIN_ID: " ADMIN_ID
  ADMIN_ID=$(echo "$ADMIN_ID" | tr -d '[:space:]')
  if ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
    log_err "آیدی باید عدد باشد."
    exit 1
  fi
}

prompt_bot_username() {
  echo ""
  echo -e "${CYAN}${BOLD}📛 یوزرنیم ربات (بدون @)${NC}"
  echo -e "   مثال: MyShopBot  — برای Mini App لازم است"
  read -r -p "BOT_USERNAME: " BOT_USERNAME
  BOT_USERNAME=$(echo "$BOT_USERNAME" | tr -d '[:space:]@')
}

# ------------------------------------------------------------
# دیتابیس
# ------------------------------------------------------------
mysql_root() {
  # تلاش برای دسترسی root بدون پسورد (auth_socket)
  if mysql -u root -e "SELECT 1" &>/dev/null; then
    mysql -u root "$@"
    return
  fi
  # در صورت نیاز از sudo
  if sudo mysql -u root -e "SELECT 1" &>/dev/null; then
    sudo mysql -u root "$@"
    return
  fi
  log_err "دسترسی به MySQL root برقرار نشد."
  exit 1
}

setup_database() {
  log_info "راه‌اندازی دیتابیس با پسورد تصادفی..."
  DB_NAME="farnoudbot"
  DB_USER="farnoud"
  DB_PASS=$(random_pass)
  SECRET_KEY=$(random_str 48)
  WEB_ADMIN_PASS=$(random_pass)

  cd "$INSTALL_DIR"
  # shellcheck disable=SC1091
  source venv/bin/activate
  WEB_ADMIN_HASH=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('${WEB_ADMIN_PASS}'))")

  mysql_root << SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL

  # اسکیمای پایه
  if [ -f setup_admins.sql ]; then
    mysql_root "${DB_NAME}" < setup_admins.sql 2>/dev/null || true
  fi
  if [ -f models_schema.sql ]; then
    mysql_root "${DB_NAME}" < models_schema.sql 2>/dev/null || true
  fi

  # ادمین وب
  mysql_root "${DB_NAME}" << SQL
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

BOT_USERNAME=${BOT_USERNAME:-}
TELEGRAM_INIT_DATA_MAX_AGE=86400
MIN_CHARGE=10000
MAX_CHARGE=50000000
MINIAPP_URL=${MINIAPP_URL}
ENV
  chmod 600 "$INSTALL_DIR/.env"
  chown "$APP_USER:$APP_USER" "$INSTALL_DIR/.env"

  # ذخیره رمز وب برای نمایش نهایی
  echo "${WEB_ADMIN_PASS}" > /root/.farnoud_web_pass
  chmod 600 /root/.farnoud_web_pass

  # اطمینان از ساخت جداول از طریق پایتون
  log_info "اجرای ensure tables..."
  set +e
  sudo -u "$APP_USER" bash -c "
    set -a
    source '$INSTALL_DIR/.env'
    set +a
    '$INSTALL_DIR/venv/bin/python' -c '
from database import ensure_tables_sync
from db_users import ensure_user_tables
from db_products import ensure_product_tables, ensure_service_mgmt_columns
from db_support import ensure_support_tables
from db_growth import ensure_growth_tables
from db_extras import ensure_extras_tables, ensure_bot_admins_table
from database import ensure_panel_max_sales
ensure_tables_sync()
ensure_user_tables()
ensure_product_tables()
ensure_support_tables()
ensure_growth_tables()
ensure_service_mgmt_columns()
ensure_extras_tables()
ensure_bot_admins_table()
ensure_panel_max_sales()
print(\"tables ok\")
'
  "
  set -e

  log_ok "دیتابیس و .env آماده شد"
}

# ------------------------------------------------------------
# systemd
# ------------------------------------------------------------
setup_systemd() {
  log_info "ایجاد سرویس‌های systemd..."

  cat > /etc/systemd/system/${SERVICE_BOT}.service << SERV
[Unit]
Description=Farnoud Telegram Bot
After=network.target mysql.service
Wants=mysql.service

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${INSTALL_DIR}
Environment=PATH=${INSTALL_DIR}/venv/bin
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/python main.py
Restart=always
RestartSec=8
StandardOutput=journal
StandardError=journal
NoNewPrivileges=true
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
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${INSTALL_DIR}
Environment=PATH=${INSTALL_DIR}/venv/bin
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/venv/bin/python admin_app.py
Restart=always
RestartSec=8
StandardOutput=journal
StandardError=journal
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERV

  systemctl daemon-reload
  systemctl enable ${SERVICE_BOT} ${SERVICE_PANEL}
  systemctl restart ${SERVICE_BOT} ${SERVICE_PANEL} || systemctl start ${SERVICE_BOT} ${SERVICE_PANEL}

  sleep 2
  if systemctl is-active --quiet ${SERVICE_BOT}; then
    log_ok "سرویس ربات فعال است"
  else
    log_warn "سرویس ربات مشکل دارد — لاگ: journalctl -u ${SERVICE_BOT} -n 50"
  fi
  if systemctl is-active --quiet ${SERVICE_PANEL}; then
    log_ok "سرویس پنل فعال است"
  else
    log_warn "سرویس پنل مشکل دارد — لاگ: journalctl -u ${SERVICE_PANEL} -n 50"
  fi
}

# ------------------------------------------------------------
# سخت‌سازی
# ------------------------------------------------------------
harden_security() {
  log_info "تنظیمات امنیتی نهایی..."
  if command -v ufw >/dev/null 2>&1; then
    ufw allow OpenSSH >/dev/null 2>&1 || true
    ufw allow 80/tcp >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw deny 5000/tcp >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
  fi
  systemctl enable --now fail2ban 2>/dev/null || true

  chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true
  chown -R "$APP_USER:$APP_USER" "$INSTALL_DIR"
  find "$INSTALL_DIR" -type d -exec chmod 755 {} \;
  find "$INSTALL_DIR" -type f -name "*.py" -exec chmod 644 {} \;
  chmod 755 "$INSTALL_DIR/venv/bin"/* 2>/dev/null || true

  log_ok "سخت‌سازی انجام شد"
}

# ------------------------------------------------------------
# نصب کامل
# ------------------------------------------------------------
do_install() {
  require_root
  print_banner
  echo -e "${GREEN}${BOLD}شروع نصب کامل Farnoud Bot...${NC}"
  echo ""

  install_prereqs
  deploy_source
  setup_venv
  prompt_domain
  setup_ssl
  prompt_bot_token
  prompt_admin_id
  prompt_bot_username
  setup_database
  setup_systemd
  harden_security

  WEB_PASS=$(cat /root/.farnoud_web_pass 2>/dev/null || echo "(see /root/.farnoud_web_pass)")

  echo ""
  echo -e "${GREEN}==============================================${NC}"
  echo -e "${GREEN}${BOLD}  ✅ نصب با موفقیت انجام شد!${NC}"
  echo -e "${GREEN}==============================================${NC}"
  echo ""
  echo -e "🌐 پنل مدیریت :  ${CYAN}${PANEL_URL}${NC}"
  echo -e "📱 مینی‌اپ    :  ${CYAN}${MINIAPP_URL}${NC}"
  echo -e "👤 ورود پنل   :  ${YELLOW}admin / ${WEB_PASS}${NC}"
  echo -e "📂 مسیر نصب   :  ${INSTALL_DIR}"
  echo -e "🤖 دستورات    :  /start  و  /admin"
  echo ""
  echo -e "مدیریت سرویس‌ها:"
  echo -e "  systemctl status ${SERVICE_BOT}"
  echo -e "  systemctl status ${SERVICE_PANEL}"
  echo -e "  journalctl -u ${SERVICE_BOT} -f"
  echo -e "  journalctl -u ${SERVICE_PANEL} -f"
  echo ""
  echo -e "Repo   : ${CYAN}https://github.com/FarnoudHosseini/FarnoudBot${NC}"
  echo -e "Credit : ${CYAN}Farnoud Hosseini${NC}"
  echo -e "Donate : ${CYAN}https://donofa.ir/farnoudhosseini${NC}"
  echo ""
}

# ------------------------------------------------------------
# آپدیت
# ------------------------------------------------------------
do_update() {
  require_root
  print_banner
  if [ ! -d "$INSTALL_DIR" ]; then
    log_err "نصب قبلی یافت نشد. ابتدا Install را اجرا کنید."
    exit 1
  fi
  log_info "در حال آپدیت..."
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true

  BACKUP_ENV="/root/farnoud_env_backup_$(date +%Y%m%d%H%M%S)"
  cp -a "$INSTALL_DIR/.env" "$BACKUP_ENV" 2>/dev/null || true
  log_ok "بکاپ .env → ${BACKUP_ENV}"

  deploy_source
  # بازگردانی .env
  if [ -f "$BACKUP_ENV" ]; then
    cp -a "$BACKUP_ENV" "$INSTALL_DIR/.env"
    chown "$APP_USER:$APP_USER" "$INSTALL_DIR/.env"
    chmod 600 "$INSTALL_DIR/.env"
  fi

  setup_venv
  systemctl start ${SERVICE_BOT} ${SERVICE_PANEL}
  sleep 2
  log_ok "آپدیت انجام شد. سرویس‌ها ری‌استارت شدند."
  systemctl status ${SERVICE_BOT} --no-pager -l || true
  systemctl status ${SERVICE_PANEL} --no-pager -l || true
}

# ------------------------------------------------------------
# حذف کامل
# ------------------------------------------------------------
do_uninstall() {
  require_root
  print_banner
  echo -e "${RED}${BOLD}⚠️  حذف کامل Farnoud Bot${NC}"
  echo -e "   (دیتابیس، سرویس، nginx، فایل‌ها)"
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

  mysql_root -e "DROP DATABASE IF EXISTS farnoudbot; DROP USER IF EXISTS 'farnoud'@'localhost';" 2>/dev/null || true

  rm -rf "$INSTALL_DIR"
  rm -f /root/.farnoud_web_pass

  log_ok "حذف کامل انجام شد."
}

# ------------------------------------------------------------
# منو
# ------------------------------------------------------------
show_menu() {
  print_banner
  echo -e "  ${CYAN}1)${NC} Install"
  echo -e "  ${CYAN}2)${NC} Update"
  echo -e "  ${CYAN}3)${NC} Full Uninstall"
  echo ""
  echo -e "  Repo   : https://github.com/FarnoudHosseini/FarnoudBot"
  echo -e "  Credit : Farnoud Hosseini"
  echo -e "  Donate : https://donofa.ir/farnoudhosseini"
  echo ""
  read -r -p "انتخاب (1/2/3): " choice
  case "$choice" in
    1) do_install ;;
    2) do_update ;;
    3) do_uninstall ;;
    *) log_err "گزینه نامعتبر"; exit 1 ;;
  esac
}

# آرگومان خط فرمان
case "${1:-}" in
  install|--install|-i)   do_install ;;
  update|--update|-u)     do_update ;;
  uninstall|--uninstall|-x) do_uninstall ;;
  *) show_menu ;;
esac
