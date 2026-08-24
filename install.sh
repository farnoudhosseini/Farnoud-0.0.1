#!/bin/bash
# ============================================================
#  FarnoudBot Installer
#  https://github.com/FarnoudHosseini/FarnoudBot
#  - English UI, system-wide Python (NO venv)
#  - DB: farnoudbot / user: farnoud
#  - Works with: curl ... | sudo bash
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

require_root(){ [ "$(id -u)" -eq 0 ] || { err "Run: sudo bash install.sh"; exit 1; }; }

ask(){
  local p="$1" v="$2" x=""
  if [ -r /dev/tty ]; then printf "%s" "$p" >/dev/tty; IFS= read -r x </dev/tty || true
  else read -r -p "$p" x || true; fi
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

mysql_root(){
  if command -v mysql >/dev/null 2>&1; then
    if mysql --protocol=socket -uroot --connect-timeout=3 -e "SELECT 1" >/dev/null 2>&1; then
      mysql --protocol=socket -uroot --connect-timeout=5 "$@"; return $?; fi
  fi
  if command -v mariadb >/dev/null 2>&1; then
    if mariadb --protocol=socket -uroot --connect-timeout=3 -e "SELECT 1" >/dev/null 2>&1; then
      mariadb --protocol=socket -uroot --connect-timeout=5 "$@"; return $?; fi
  fi
  if sudo mysql --protocol=socket -uroot --connect-timeout=3 -e "SELECT 1" >/dev/null 2>&1; then
    sudo mysql --protocol=socket -uroot --connect-timeout=5 "$@"; return $?; fi
  return 1
}

start_mysql(){
  log "Starting MySQL/MariaDB..."
  systemctl start mysql 2>/dev/null || systemctl start mariadb 2>/dev/null \
    || service mysql start 2>/dev/null || service mariadb start 2>/dev/null || true
  systemctl enable mysql 2>/dev/null || systemctl enable mariadb 2>/dev/null || true
  local i
  for i in $(seq 1 15); do
    mysql_root -e "SELECT 1" >/dev/null 2>&1 && { ok "MySQL ready"; return 0; }
    sleep 2
  done
  err "MySQL not reachable via socket. Try: sudo mysql -e 'SELECT VERSION();'"
  return 1
}

install_os_packages(){
  log "apt update + packages..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y >/tmp/farnoud_apt_update.log 2>&1 || true
  apt-get install -y \
    python3 python3-pip python3-dev python3-setuptools python3-wheel \
    python3-flask python3-pymysql python3-dotenv python3-requests \
    python3-pil python3-cryptography python3-werkzeug \
    nginx curl git ufw \
    build-essential libssl-dev libffi-dev pkg-config default-libmysqlclient-dev \
    certbot python3-certbot-nginx \
    >/tmp/farnoud_apt_install.log 2>&1 || true

  if ! command -v mysqld >/dev/null 2>&1 && ! command -v mariadbd >/dev/null 2>&1; then
    log "Installing MySQL server..."
    apt-get install -y mysql-server mysql-client >/tmp/farnoud_mysql_pkg.log 2>&1 \
      || apt-get install -y default-mysql-server default-mysql-client >/tmp/farnoud_mysql_pkg.log 2>&1 \
      || apt-get install -y mariadb-server mariadb-client >/tmp/farnoud_mysql_pkg.log 2>&1 || true
  fi
  systemctl enable nginx >/dev/null 2>&1; systemctl start nginx >/dev/null 2>&1 || true
  start_mysql || warn "MySQL not up yet"
  ok "OS packages done"
}

clone_code(){
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating $INSTALL_DIR"
    [ -f "$INSTALL_DIR/.env" ] && cp -a "$INSTALL_DIR/.env" /tmp/farnoud.env.save
    cd "$INSTALL_DIR" || exit 1
    git fetch --all >/dev/null 2>&1 || true
    git reset --hard origin/main >/dev/null 2>&1 || git reset --hard origin/master >/dev/null 2>&1 || true
    [ -f /tmp/farnoud.env.save ] && mv -f /tmp/farnoud.env.save "$INSTALL_DIR/.env"
  else
    log "Cloning $REPO_URL"
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" || { err "git clone failed"; exit 1; }
  fi
  cd "$INSTALL_DIR" || exit 1
  rm -rf "$INSTALL_DIR/venv" 2>/dev/null || true
  rm -f "$INSTALL_DIR/miniapp.py.bak" 2>/dev/null || true
  if [ -f "$INSTALL_DIR/.env" ] && grep -qE 'YOUR_TELEGRAM|CHANGE_ME' "$INSTALL_DIR/.env" 2>/dev/null; then
    rm -f "$INSTALL_DIR/.env"
  fi
  ok "Source ready"
}

pip_try(){
  # $*: packages
  python3 -m pip install "$@" --break-system-packages 2>>/tmp/farnoud_pip3.log && return 0
  python3 -m pip install "$@" 2>>/tmp/farnoud_pip3.log && return 0
  return 1
}

install_pip(){
  log "Installing Python packages (system-wide, no venv)..."
  : >/tmp/farnoud_pip3.log

  if ! python3 -m pip --version >/dev/null 2>&1; then
    log "Bootstrapping pip..."
    apt-get install -y python3-pip >/dev/null 2>&1 || true
    python3 -m ensurepip --upgrade >/dev/null 2>&1 || true
  fi

  python3 -m pip install --upgrade pip setuptools wheel --break-system-packages >>/tmp/farnoud_pip3.log 2>&1 \
    || python3 -m pip install --upgrade pip setuptools wheel >>/tmp/farnoud_pip3.log 2>&1 || true

  if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    log "pip install -r requirements.txt"
    pip_try -r "$INSTALL_DIR/requirements.txt" || warn "requirements.txt had errors (continuing)"
  fi

  log "pip install core: telegram flask aiomysql ..."
  pip_try "python-telegram-bot[job-queue]" aiomysql python-dotenv flask pymysql werkzeug requests "qrcode[pil]" cryptography Pillow \
    || warn "core pip batch had errors"

  # Force critical ones individually
  python3 -c "import telegram" 2>/dev/null || pip_try --force-reinstall "python-telegram-bot[job-queue]" || true
  python3 -c "import flask" 2>/dev/null || { pip_try --force-reinstall flask || apt-get install -y python3-flask >/dev/null 2>&1 || true; }
  python3 -c "import pymysql" 2>/dev/null || { pip_try pymysql || apt-get install -y python3-pymysql >/dev/null 2>&1 || true; }
  python3 -c "import dotenv" 2>/dev/null || { pip_try python-dotenv || apt-get install -y python3-dotenv >/dev/null 2>&1 || true; }
  python3 -c "import aiomysql" 2>/dev/null || pip_try aiomysql || true
  python3 -c "import werkzeug" 2>/dev/null || { pip_try werkzeug || apt-get install -y python3-werkzeug >/dev/null 2>&1 || true; }

  MISSING=""
  python3 -c "import flask" 2>/dev/null || MISSING="$MISSING flask"
  python3 -c "import telegram" 2>/dev/null || MISSING="$MISSING telegram"
  python3 -c "import pymysql" 2>/dev/null || MISSING="$MISSING pymysql"
  python3 -c "import dotenv" 2>/dev/null || MISSING="$MISSING dotenv"
  python3 -c "import aiomysql" 2>/dev/null || MISSING="$MISSING aiomysql"

  if [ -n "$MISSING" ]; then
    err "Missing modules:$MISSING"
    err "Log: tail -50 /tmp/farnoud_pip3.log"
    tail -40 /tmp/farnoud_pip3.log 2>/dev/null || true
    return 1
  fi
  ok "Python modules OK"
  python3 - <<'PY'
import telegram, flask
print("  telegram:", getattr(telegram, "__version__", "ok"))
print("  flask: ok")
PY
  return 0
}

ask_domain(){
  echo ""
  echo -e "${CYAN}Domain (DNS A -> this server)${NC}"
  while true; do
    ask "Domain: " DOMAIN
    DOMAIN=$(echo "${DOMAIN:-}" | tr -d '[:space:]' | tr 'A-Z' 'a-z')
    [ -n "$DOMAIN" ] && break
    err "Required"
  done
  SIP=$(curl -4 -s --max-time 5 ifconfig.me 2>/dev/null || true)
  DIP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)
  log "Server IP: ${SIP:-?}  Domain IP: ${DIP:-?}"
  if [ -n "${SIP:-}" ] && [ -n "${DIP:-}" ] && [ "$SIP" != "$DIP" ]; then
    warn "DNS mismatch"
    ask "Continue? [y/N]: " c
    case "${c:-}" in y|Y|yes|YES) ;; *) exit 1 ;; esac
  fi
}

setup_nginx(){
  log "Nginx for $DOMAIN"
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
  nginx -t >/tmp/farnoud_nginx.log 2>&1 && systemctl reload nginx

  log "Let's Encrypt..."
  if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
      --register-unsafely-without-email --redirect >/tmp/farnoud_certbot.log 2>&1; then
    ok "SSL OK"
    PANEL_URL="https://${DOMAIN}"
    MINIAPP_URL="https://${DOMAIN}/miniapp/"
  else
    warn "SSL failed — HTTP only"
    PANEL_URL="http://${DOMAIN}"
    MINIAPP_URL="http://${DOMAIN}/miniapp/"
  fi
  ok "Nginx -> ${PANEL_URL}"
}

ask_bot(){
  echo ""
  echo -e "${CYAN}Bot token (@BotFather)${NC}"
  while true; do
    ask "BOT_TOKEN: " BOT_TOKEN
    BOT_TOKEN=$(echo "${BOT_TOKEN:-}" | tr -d '[:space:]')
    [ -n "$BOT_TOKEN" ] && break
  done
  echo -e "${CYAN}Admin Telegram ID (@userinfobot)${NC}"
  while true; do
    ask "ADMIN_ID: " ADMIN_ID
    ADMIN_ID=$(echo "${ADMIN_ID:-}" | tr -d '[:space:]')
    [[ "$ADMIN_ID" =~ ^[0-9]+$ ]] && break
    err "Digits only"
  done
}

setup_db(){
  log "DB ${DB_NAME} / user ${DB_USER}"
  start_mysql || return 1
  DB_PASS=$(rand 22)
  SECRET_KEY=$(rand 48)
  WEB_PASS=$(rand 14)
  SQL=$(mktemp)
  cat >"$SQL" <<EOS
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
EOS
  if ! mysql_root <"$SQL" 2>/tmp/farnoud_db_err.log; then
    cat >"$SQL" <<EOS
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
FLUSH PRIVILEGES;
EOS
    mysql_root <"$SQL" 2>>/tmp/farnoud_db_err.log || { err "DB create failed"; cat /tmp/farnoud_db_err.log; rm -f "$SQL"; return 1; }
  fi
  rm -f "$SQL"
  ok "Database ready"

  [ -f "$INSTALL_DIR/setup_admins.sql" ] && mysql_root <"$INSTALL_DIR/setup_admins.sql" 2>/dev/null || true
  [ -f "$INSTALL_DIR/models_schema.sql" ] && mysql_root "$DB_NAME" <"$INSTALL_DIR/models_schema.sql" 2>/dev/null || true

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;" 2>/dev/null || true

  HASH=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('${WEB_PASS}'))" 2>/dev/null || true)
  if [ -n "${HASH:-}" ]; then
    HESC=$(printf "%s" "$HASH" | sed "s/'/''/g")
    mysql_root "$DB_NAME" -e "INSERT INTO admins (username,password) VALUES ('admin','${HESC}') ON DUPLICATE KEY UPDATE password='${HESC}';" 2>/dev/null || true
  fi

  PANEL_URL="${PANEL_URL:-http://${DOMAIN}}"
  MINIAPP_URL="${MINIAPP_URL:-http://${DOMAIN}/miniapp/}"

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

  mysql -u"$DB_USER" -p"$DB_PASS" -h"$DB_HOST" "$DB_NAME" --connect-timeout=5 -e "SELECT 1" >/dev/null 2>&1 \
    && ok "DB login test OK" || warn "DB login test failed"
  ok "Database step done"
}

setup_services(){
  log "systemd units"
  PYBIN=$(command -v python3)
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

  if systemctl is-active --quiet ${SERVICE_BOT}; then ok "farnoud-bot ACTIVE"
  else err "farnoud-bot FAILED"; journalctl -u ${SERVICE_BOT} -n 25 --no-pager; fi

  if systemctl is-active --quiet ${SERVICE_PANEL}; then ok "farnoud-panel ACTIVE"
  else err "farnoud-panel FAILED"; journalctl -u ${SERVICE_PANEL} -n 25 --no-pager; fi

  # Port 5000 check
  sleep 1
  if ss -lntp 2>/dev/null | grep -q ':5000'; then
    ok "Port 5000 is LISTENING"
  elif netstat -lntp 2>/dev/null | grep -q ':5000'; then
    ok "Port 5000 is LISTENING"
  else
    warn "Port 5000 not listening yet (panel may still be crashing)"
  fi
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
  echo "  ss -lntp | grep 5000"
  echo "  systemctl status farnoud-bot farnoud-panel"
  echo "  journalctl -u farnoud-bot -n 50 --no-pager"
  echo -e "${GREEN}==============================================${NC}"
}

do_install(){
  require_root; banner
  install_os_packages
  clone_code
  if ! install_pip; then
    err "STOP: Python packages missing. Fix then run: sudo bash install.sh finish"
    exit 1
  fi
  ask_domain
  setup_nginx
  ask_bot
  setup_db || warn "DB step errors"
  setup_services
  firewall_bits
  print_done
}

do_update(){
  require_root; banner
  [ -d "$INSTALL_DIR" ] || { err "Not installed"; exit 1; }
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  clone_code
  install_pip || exit 1
  systemctl start ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  ok "Updated"
}

do_uninstall(){
  require_root; banner
  echo -e "${RED}Deletes services, nginx, DB ${DB_NAME}, ${INSTALL_DIR}${NC}"
  ask "Type YES: " conf
  [ "${conf:-}" = "YES" ] || { echo "Cancelled"; exit 0; }
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  systemctl disable ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  rm -f /etc/systemd/system/${SERVICE_BOT}.service /etc/systemd/system/${SERVICE_PANEL}.service
  systemctl daemon-reload
  rm -f /etc/nginx/sites-enabled/farnoudbot /etc/nginx/sites-available/farnoudbot
  systemctl reload nginx 2>/dev/null || true
  mysql_root -e "DROP DATABASE IF EXISTS \`${DB_NAME}\`; DROP USER IF EXISTS '${DB_USER}'@'localhost'; FLUSH PRIVILEGES;" 2>/dev/null || true
  rm -rf "$INSTALL_DIR" /root/.farnoud_web_pass
  ok "Removed"
}

do_finish(){
  require_root; banner
  log "Resume / fix deps + restart services"
  [ -d "$INSTALL_DIR" ] || { err "No $INSTALL_DIR"; exit 1; }
  install_os_packages
  if ! install_pip; then
    err "Python still broken"
    exit 1
  fi
  DOMAIN=$(grep -oP 'server_name \K[^; ]+' /etc/nginx/sites-available/farnoudbot 2>/dev/null | head -1 || true)
  if [ -z "${DOMAIN:-}" ]; then ask_domain; setup_nginx
  else
    log "Domain: $DOMAIN"
    if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
      PANEL_URL="https://${DOMAIN}"; MINIAPP_URL="https://${DOMAIN}/miniapp/"
    else
      PANEL_URL="http://${DOMAIN}"; MINIAPP_URL="http://${DOMAIN}/miniapp/"
    fi
  fi
  if [ -f "$INSTALL_DIR/.env" ]; then set -a; . "$INSTALL_DIR/.env"; set +a; fi
  if [ -z "${BOT_TOKEN:-}" ] || [ -z "${ADMIN_ID:-}" ]; then ask_bot; fi
  # Only recreate DB if .env missing DB_PASSWORD
  if [ ! -f "$INSTALL_DIR/.env" ] || [ -z "${DB_PASSWORD:-}" ]; then
    setup_db || warn "DB errors"
  else
    ok "Keeping existing .env / database"
  fi
  setup_services
  firewall_bits
  print_done
}

do_restart(){
  banner
  log "Restarting FarnoudBot services (when stuck / hung)..."
  systemctl daemon-reload 2>/dev/null || true
  systemctl restart ${SERVICE_BOT} 2>/dev/null || systemctl start ${SERVICE_BOT} 2>/dev/null || true
  systemctl restart ${SERVICE_PANEL} 2>/dev/null || systemctl start ${SERVICE_PANEL} 2>/dev/null || true
  sleep 2
  if systemctl is-active --quiet ${SERVICE_BOT} 2>/dev/null; then
    ok "farnoud-bot is ACTIVE"
  else
    warn "farnoud-bot not active — check: systemctl status ${SERVICE_BOT}"
    systemctl status ${SERVICE_BOT} --no-pager -l 2>/dev/null | head -25 || true
  fi
  if systemctl is-active --quiet ${SERVICE_PANEL} 2>/dev/null; then
    ok "farnoud-panel is ACTIVE"
  else
    warn "farnoud-panel not active — check: systemctl status ${SERVICE_PANEL}"
  fi
  echo ""
  log "Recent bot logs (last 15 lines):"
  journalctl -u ${SERVICE_BOT} -n 15 --no-pager 2>/dev/null || true
  echo ""
  ok "Restart done. If still stuck: sudo journalctl -u ${SERVICE_BOT} -f"
}

menu(){
  while true; do
    banner
    echo "  1) Full Install"
    echo "  2) Update"
    echo "  3) Uninstall"
    echo "  4) Finish / Resume / Fix packages"
    echo "  5) Restart Bot (when stuck)"
    echo "  0) Exit"
    echo ""
    ask "Choose [0-5]: " ch
    case "${ch:-}" in
      1) do_install; break ;;
      2) do_update; break ;;
      3) do_uninstall; break ;;
      4) do_finish; break ;;
      5) do_restart; break ;;
      0) exit 0 ;;
      *) err "Invalid"; sleep 1 ;;
    esac
  done
}

case "${1:-}" in
  install|--install|-i) do_install ;;
  update|--update|-u) do_update ;;
  uninstall|--uninstall|-x) do_uninstall ;;
  finish|--finish|resume|fix) do_finish ;;
  restart|--restart|-r) do_restart ;;
  ""|menu) menu ;;
  *) echo "Usage: sudo bash install.sh [install|update|uninstall|finish|restart]"; exit 1 ;;
esac
