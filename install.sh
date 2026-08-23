#!/bin/bash
# ============================================================
#  FarnoudBot Installer
#  Repo: https://github.com/FarnoudHosseini/FarnoudBot
#  - English UI
#  - System-wide Python (NO venv)
#  - Database: farnoudbot / user: farnoud  (app never uses root)
#  - Safe with: curl ... | sudo bash   (reads from /dev/tty)
#  - Does not abort on single step failure (set +e)
# ============================================================

set +e
set -u

REPO_URL="https://github.com/FarnoudHosseini/FarnoudBot.git"
INSTALL_DIR="/opt/farnoudbot"
SERVICE_BOT="farnoud-bot"
SERVICE_PANEL="farnoud-panel"

DB_NAME="farnoudbot"
DB_USER="farnoud"
DB_HOST="localhost"
DB_PORT="3306"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log(){ echo -e "${CYAN}[INFO]${NC}  $*"; }
ok(){  echo -e "${GREEN}[OK]${NC}    $*"; }
warn(){ echo -e "${YELLOW}[WARN]${NC}  $*"; }
err(){ echo -e "${RED}[ERROR]${NC} $*"; }

require_root(){
  if [ "$(id -u)" -ne 0 ]; then err "Run as root: sudo bash install.sh"; exit 1; fi
}

# Interactive input works even when script is piped (curl | bash)
ask(){
  local p="$1" v="$2" x=""
  if [ -r /dev/tty ]; then
    printf "%s" "$p" >/dev/tty
    IFS= read -r x </dev/tty || true
  else
    read -r -p "$p" x || true
  fi
  printf -v "$v" '%s' "$x"
}

rand(){ tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c "${1:-20}" || echo "x$(date +%s)$RANDOM"; }

banner(){
  clear 2>/dev/null || true
  echo ""
  echo -e "${CYAN}============================================${NC}"
  echo -e "${CYAN}   FarnoudBot Installer (system-wide)${NC}"
  echo -e "${CYAN}============================================${NC}"
  echo -e "  Install dir : ${GREEN}${INSTALL_DIR}${NC}"
  echo -e "  Database    : ${GREEN}${DB_NAME}${NC}"
  echo -e "  DB user     : ${GREEN}${DB_USER}${NC}"
  echo -e "  Python      : system python3 (no venv)"
  echo -e "${CYAN}============================================${NC}"
  echo ""
}

# ---------- MySQL without password hang ----------
mysql_root(){
  # Prefer unix socket as local root; never wait for interactive password
  if command -v mysql >/dev/null 2>&1; then
    if mysql --protocol=socket -uroot --connect-timeout=3 -e "SELECT 1" >/dev/null 2>&1; then
      mysql --protocol=socket -uroot --connect-timeout=5 "$@"
      return $?
    fi
  fi
  if command -v mariadb >/dev/null 2>&1; then
    if mariadb --protocol=socket -uroot --connect-timeout=3 -e "SELECT 1" >/dev/null 2>&1; then
      mariadb --protocol=socket -uroot --connect-timeout=5 "$@"
      return $?
    fi
  fi
  # Some images only allow: sudo mysql
  if sudo mysql --protocol=socket -uroot --connect-timeout=3 -e "SELECT 1" >/dev/null 2>&1; then
    sudo mysql --protocol=socket -uroot --connect-timeout=5 "$@"
    return $?
  fi
  return 1
}

start_mysql(){
  log "Starting MySQL/MariaDB service..."
  systemctl start mysql 2>/dev/null || systemctl start mariadb 2>/dev/null \
    || service mysql start 2>/dev/null || service mariadb start 2>/dev/null || true
  systemctl enable mysql 2>/dev/null || systemctl enable mariadb 2>/dev/null || true
  local i
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    if mysql_root -e "SELECT 1" >/dev/null 2>&1; then
      ok "MySQL is ready"
      return 0
    fi
    sleep 2
  done
  err "Cannot talk to MySQL as root via socket."
  err "Try:  sudo mysql -e 'SELECT VERSION();'"
  return 1
}

install_os_packages(){
  log "apt update + install packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y >/tmp/farnoud_apt_update.log 2>&1 || true
  apt-get install -y \
    python3 python3-pip python3-dev python3-setuptools \
    nginx curl git ufw \
    build-essential libssl-dev libffi-dev pkg-config \
    default-libmysqlclient-dev \
    certbot python3-certbot-nginx \
    >/tmp/farnoud_apt_install.log 2>&1
  # MySQL server (package name varies)
  if ! command -v mysqld >/dev/null 2>&1 && ! command -v mariadbd >/dev/null 2>&1; then
    log "Installing MySQL/MariaDB server..."
    apt-get install -y mysql-server mysql-client >/tmp/farnoud_mysql_pkg.log 2>&1 \
      || apt-get install -y default-mysql-server default-mysql-client >/tmp/farnoud_mysql_pkg.log 2>&1 \
      || apt-get install -y mariadb-server mariadb-client >/tmp/farnoud_mysql_pkg.log 2>&1 \
      || warn "MySQL package install may have failed — see /tmp/farnoud_mysql_pkg.log"
  fi
  systemctl enable nginx >/dev/null 2>&1 || true
  systemctl start nginx >/dev/null 2>&1 || true
  start_mysql || warn "MySQL not up yet"
  ok "OS packages done"
}

clone_code(){
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating existing install at $INSTALL_DIR"
    [ -f "$INSTALL_DIR/.env" ] && cp -a "$INSTALL_DIR/.env" /tmp/farnoud.env.save
    cd "$INSTALL_DIR" || exit 1
    git fetch --all >/dev/null 2>&1 || true
    git reset --hard origin/main >/dev/null 2>&1 || git reset --hard origin/master >/dev/null 2>&1 || true
    [ -f /tmp/farnoud.env.save ] && mv -f /tmp/farnoud.env.save "$INSTALL_DIR/.env"
  else
    log "Cloning $REPO_URL -> $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
    if ! git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"; then
      err "git clone failed"
      exit 1
    fi
  fi
  cd "$INSTALL_DIR" || exit 1
  rm -rf "$INSTALL_DIR/venv" 2>/dev/null || true
  rm -f "$INSTALL_DIR/miniapp.py.bak" 2>/dev/null || true
  # Never keep a committed .env from the repo
  if [ -f "$INSTALL_DIR/.env" ] && grep -q 'YOUR_TELEGRAM\|CHANGE_ME' "$INSTALL_DIR/.env" 2>/dev/null; then
    rm -f "$INSTALL_DIR/.env"
  fi
  ok "Source ready"
}

install_pip(){
  log "Installing Python deps system-wide (no venv)..."
  python3 -m pip install --upgrade pip setuptools wheel >/tmp/farnoud_pip1.log 2>&1 || true
  if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    python3 -m pip install -r "$INSTALL_DIR/requirements.txt" --break-system-packages \
      >/tmp/farnoud_pip2.log 2>&1 \
      || python3 -m pip install -r "$INSTALL_DIR/requirements.txt" >/tmp/farnoud_pip2.log 2>&1 \
      || warn "pip install -r requirements.txt had errors (see /tmp/farnoud_pip2.log)"
  fi
  # Hard requirements used by main.py / admin_app.py
  python3 -m pip install \
    "python-telegram-bot[job-queue]>=22.7" \
    aiomysql python-dotenv flask pymysql werkzeug requests \
    "qrcode[pil]>=7.4" cryptography \
    --break-system-packages >/tmp/farnoud_pip3.log 2>&1 \
    || python3 -m pip install \
      "python-telegram-bot[job-queue]>=22.7" \
      aiomysql python-dotenv flask pymysql werkzeug requests \
      "qrcode[pil]>=7.4" cryptography \
      >/tmp/farnoud_pip3.log 2>&1

  if python3 -c "import flask, telegram, pymysql, dotenv, werkzeug, aiomysql" 2>/dev/null; then
    ok "Python modules OK"
  else
    err "Critical Python modules missing. Check /tmp/farnoud_pip3.log"
    return 1
  fi
}

ask_domain(){
  echo ""
  echo -e "${CYAN}Enter domain (DNS A record -> this server IP)${NC}"
  echo "  Example: robot.example.com"
  while true; do
    ask "Domain: " DOMAIN
    DOMAIN=$(echo "${DOMAIN:-}" | tr -d '[:space:]' | tr 'A-Z' 'a-z')
    [ -n "$DOMAIN" ] && break
    err "Domain is required"
  done
  SIP=$(curl -4 -s --max-time 5 ifconfig.me 2>/dev/null || curl -4 -s --max-time 5 icanhazip.com 2>/dev/null || true)
  DIP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)
  log "Server IP: ${SIP:-unknown}"
  log "Domain IP: ${DIP:-unresolved}"
  if [ -n "${SIP:-}" ] && [ -n "${DIP:-}" ] && [ "$SIP" != "$DIP" ]; then
    warn "DNS does not match this server"
    ask "Continue anyway? [y/N]: " c
    case "${c:-}" in y|Y|yes|YES) ;; *) exit 1 ;; esac
  fi
}

setup_nginx(){
  log "Writing nginx site for $DOMAIN"
  mkdir -p /var/www/html
  cat >/etc/nginx/sites-available/farnoudbot <<EOF
server {
    listen 80;
    server_name ${DOMAIN};
    client_max_body_size 20M;
    location /.well-known/acme-challenge/ { root /var/www/html; }
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }
}
EOF
  ln -sfn /etc/nginx/sites-available/farnoudbot /etc/nginx/sites-enabled/farnoudbot
  rm -f /etc/nginx/sites-enabled/default
  nginx -t >/tmp/farnoud_nginx_test.log 2>&1 && systemctl reload nginx
  log "Requesting Let's Encrypt certificate..."
  if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
      --register-unsafely-without-email --redirect >/tmp/farnoud_certbot.log 2>&1; then
    ok "SSL enabled"
    PANEL_URL="https://${DOMAIN}"
    MINIAPP_URL="https://${DOMAIN}/miniapp/"
  else
    warn "SSL failed (see /tmp/farnoud_certbot.log) — using HTTP"
    PANEL_URL="http://${DOMAIN}"
    MINIAPP_URL="http://${DOMAIN}/miniapp/"
  fi
  ok "Nginx configured -> ${PANEL_URL}"
}

ask_bot(){
  echo ""
  echo -e "${CYAN}Bot token from @BotFather${NC}"
  while true; do
    ask "BOT_TOKEN: " BOT_TOKEN
    BOT_TOKEN=$(echo "${BOT_TOKEN:-}" | tr -d '[:space:]')
    [ -n "$BOT_TOKEN" ] && break
    err "Token required"
  done
  echo ""
  echo -e "${CYAN}Admin numeric Telegram ID (@userinfobot)${NC}"
  while true; do
    ask "ADMIN_ID: " ADMIN_ID
    ADMIN_ID=$(echo "${ADMIN_ID:-}" | tr -d '[:space:]')
    [[ "$ADMIN_ID" =~ ^[0-9]+$ ]] && break
    err "ADMIN_ID must be digits"
  done
}

setup_db(){
  log "Creating database '${DB_NAME}' and user '${DB_USER}' (not root)"
  if ! start_mysql; then
    err "MySQL not available — cannot create database"
    return 1
  fi

  DB_PASS=$(rand 22)
  SECRET_KEY=$(rand 48)
  WEB_PASS=$(rand 14)

  # Write SQL to file — avoids interactive mysql and quoting bugs
  SQL=$(mktemp)
  cat >"$SQL" <<EOS
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
EOS
  if ! mysql_root <"$SQL" 2>/tmp/farnoud_db_err.log; then
    warn "CREATE USER IF NOT EXISTS failed — trying legacy GRANT syntax"
    cat >"$SQL" <<EOS
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
FLUSH PRIVILEGES;
EOS
    if ! mysql_root <"$SQL" 2>>/tmp/farnoud_db_err.log; then
      err "Failed to create database. Log:"
      cat /tmp/farnoud_db_err.log 2>/dev/null || true
      rm -f "$SQL"
      return 1
    fi
  fi
  rm -f "$SQL"
  ok "Database ${DB_NAME} ready, user ${DB_USER}"

  # Base tables from repo
  if [ -f "$INSTALL_DIR/setup_admins.sql" ]; then
    log "Import setup_admins.sql"
    # File contains CREATE DATABASE + USE — run against root without selecting DB first is fine
    mysql_root <"$INSTALL_DIR/setup_admins.sql" 2>/tmp/farnoud_schema.log || true
  fi
  if [ -f "$INSTALL_DIR/models_schema.sql" ]; then
    log "Import models_schema.sql"
    mysql_root "$DB_NAME" <"$INSTALL_DIR/models_schema.sql" 2>>/tmp/farnoud_schema.log || true
  fi

  # Ensure admins table exists even if SQL import failed
  mysql_root "$DB_NAME" -e "
CREATE TABLE IF NOT EXISTS admins (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS settings (
  \`key\` VARCHAR(100) PRIMARY KEY,
  \`value\` TEXT,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
" 2>/dev/null || true

  log "Creating web panel user 'admin'..."
  HASH=$(python3 - <<PY
from werkzeug.security import generate_password_hash
print(generate_password_hash("${WEB_PASS}"))
PY
)
  if [ -n "$HASH" ]; then
    HESC=$(printf "%s" "$HASH" | sed "s/'/''/g")
    mysql_root "$DB_NAME" -e "INSERT INTO admins (username,password) VALUES ('admin','${HESC}') ON DUPLICATE KEY UPDATE password='${HESC}';" 2>/dev/null || true
  else
    warn "werkzeug hash failed"
  fi

  PANEL_URL="${PANEL_URL:-http://${DOMAIN}}"
  MINIAPP_URL="${MINIAPP_URL:-http://${DOMAIN}/miniapp/}"

  log "Writing $INSTALL_DIR/.env"
  cat >"$INSTALL_DIR/.env" <<EOF
BOT_TOKEN=${BOT_TOKEN}
ADMIN_ID=${ADMIN_ID}
SECRET_KEY=${SECRET_KEY}

DB_HOST=${DB_HOST}
DB_PORT=${DB_PORT}
DB_USER=${DB_USER}
DB_PASSWORD=${DB_PASS}
DB_NAME=${DB_NAME}

BOT_USERNAME=
TELEGRAM_INIT_DATA_MAX_AGE=86400
MIN_CHARGE=10000
MAX_CHARGE=50000000
MINIAPP_URL=${MINIAPP_URL}
EOF
  chmod 600 "$INSTALL_DIR/.env"
  echo "$WEB_PASS" >/root/.farnoud_web_pass
  chmod 600 /root/.farnoud_web_pass

  # Verify app user (must NOT be root)
  if mysql -u"$DB_USER" -p"$DB_PASS" -h"$DB_HOST" -P"$DB_PORT" "$DB_NAME" --connect-timeout=5 -e "SELECT DATABASE();" >/dev/null 2>&1; then
    ok "Login test OK: ${DB_USER} -> ${DB_NAME}"
  else
    warn "Login test as ${DB_USER} failed — check .env / MySQL grants"
  fi
  ok "Database step finished"
}

setup_services(){
  log "Installing systemd units (system python3, no venv)"
  PYBIN=$(command -v python3)
  if [ -z "$PYBIN" ]; then err "python3 not found"; return 1; fi

  cat >/etc/systemd/system/${SERVICE_BOT}.service <<EOF
[Unit]
Description=FarnoudBot Telegram Bot
After=network-online.target mysql.service mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${PYBIN} ${INSTALL_DIR}/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  cat >/etc/systemd/system/${SERVICE_PANEL}.service <<EOF
[Unit]
Description=FarnoudBot Admin Panel + MiniApp
After=network-online.target mysql.service mariadb.service
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${PYBIN} ${INSTALL_DIR}/admin_app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable ${SERVICE_BOT} ${SERVICE_PANEL} >/dev/null 2>&1 || true
  systemctl restart ${SERVICE_BOT} || systemctl start ${SERVICE_BOT}
  systemctl restart ${SERVICE_PANEL} || systemctl start ${SERVICE_PANEL}
  sleep 3
  echo ""
  if systemctl is-active --quiet ${SERVICE_BOT}; then ok "farnoud-bot ACTIVE"; else err "farnoud-bot NOT active"; journalctl -u ${SERVICE_BOT} -n 20 --no-pager; fi
  if systemctl is-active --quiet ${SERVICE_PANEL}; then ok "farnoud-panel ACTIVE"; else err "farnoud-panel NOT active"; journalctl -u ${SERVICE_PANEL} -n 20 --no-pager; fi
}

firewall_bits(){
  if command -v ufw >/dev/null 2>&1; then
    ufw allow OpenSSH >/dev/null 2>&1 || true
    ufw allow 80/tcp >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw deny 5000/tcp >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
  fi
  chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true
}

print_done(){
  WP=$(cat /root/.farnoud_web_pass 2>/dev/null || echo "see /root/.farnoud_web_pass")
  echo ""
  echo -e "${GREEN}============== INSTALL COMPLETE ==============${NC}"
  echo "  Panel URL : ${PANEL_URL:-n/a}"
  echo "  Mini App  : ${MINIAPP_URL:-n/a}"
  echo "  Web login : admin / ${WP}"
  echo "  Path      : ${INSTALL_DIR}"
  echo "  Database  : ${DB_NAME}  user=${DB_USER}"
  echo ""
  echo "  systemctl status farnoud-bot"
  echo "  systemctl status farnoud-panel"
  echo "  journalctl -u farnoud-bot -n 50 --no-pager"
  echo -e "${GREEN}==============================================${NC}"
  echo ""
}

do_install(){
  require_root
  banner
  log "Full install"
  install_os_packages
  clone_code
  install_pip
  ask_domain
  setup_nginx
  ask_bot
  setup_db || warn "Database step reported errors — continue anyway"
  setup_services
  firewall_bits
  print_done
}

do_update(){
  require_root
  banner
  [ -d "$INSTALL_DIR" ] || { err "Not installed"; exit 1; }
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  clone_code
  install_pip
  systemctl start ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  ok "Update done"
}

do_uninstall(){
  require_root
  banner
  echo -e "${RED}Deletes services, nginx site, DB ${DB_NAME}, user ${DB_USER}, ${INSTALL_DIR}${NC}"
  ask "Type YES: " conf
  [ "${conf:-}" = "YES" ] || { echo "Cancelled"; exit 0; }
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  systemctl disable ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  rm -f /etc/systemd/system/${SERVICE_BOT}.service /etc/systemd/system/${SERVICE_PANEL}.service
  systemctl daemon-reload
  rm -f /etc/nginx/sites-enabled/farnoudbot /etc/nginx/sites-available/farnoudbot
  systemctl reload nginx 2>/dev/null || true
  mysql_root -e "DROP DATABASE IF EXISTS \`${DB_NAME}\`; DROP USER IF EXISTS '${DB_USER}'@'localhost'; FLUSH PRIVILEGES;" 2>/dev/null || true
  rm -rf "$INSTALL_DIR"
  rm -f /root/.farnoud_web_pass
  ok "Uninstalled"
}

do_finish(){
  require_root
  banner
  log "Resume install (packages + DB + services)"
  [ -d "$INSTALL_DIR" ] || { err "Missing $INSTALL_DIR — use option 1"; exit 1; }
  install_os_packages
  install_pip
  DOMAIN=$(grep -oP 'server_name \K[^; ]+' /etc/nginx/sites-available/farnoudbot 2>/dev/null | head -1 || true)
  if [ -z "${DOMAIN:-}" ]; then
    ask_domain
    setup_nginx
  else
    log "Domain: $DOMAIN"
    if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
      PANEL_URL="https://${DOMAIN}"; MINIAPP_URL="https://${DOMAIN}/miniapp/"
    else
      PANEL_URL="http://${DOMAIN}"; MINIAPP_URL="http://${DOMAIN}/miniapp/"
    fi
  fi
  if [ -f "$INSTALL_DIR/.env" ]; then
    set -a; # shellcheck disable=SC1091
    . "$INSTALL_DIR/.env"; set +a
  fi
  if [ -z "${BOT_TOKEN:-}" ] || [ -z "${ADMIN_ID:-}" ]; then
    ask_bot
  else
    log "Reusing BOT_TOKEN / ADMIN_ID from .env"
  fi
  setup_db || warn "DB errors"
  setup_services
  firewall_bits
  print_done
}

menu(){
  while true; do
    banner
    echo "  1) Full Install"
    echo "  2) Update"
    echo "  3) Uninstall"
    echo "  4) Finish / Resume (stuck after SSL or at database)"
    echo "  0) Exit"
    echo ""
    ask "Choose [0-4]: " ch
    case "${ch:-}" in
      1) do_install; break ;;
      2) do_update; break ;;
      3) do_uninstall; break ;;
      4) do_finish; break ;;
      0) echo "Bye"; exit 0 ;;
      *) err "Invalid"; sleep 1 ;;
    esac
  done
}

case "${1:-}" in
  install|--install|-i) do_install ;;
  update|--update|-u) do_update ;;
  uninstall|--uninstall|-x) do_uninstall ;;
  finish|--finish|resume) do_finish ;;
  ""|menu|--menu) menu ;;
  *) echo "Usage: sudo bash install.sh [install|update|uninstall|finish]"; exit 1 ;;
esac
