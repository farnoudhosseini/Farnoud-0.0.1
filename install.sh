#!/bin/bash
# ============================================================
#  Farnoud Bot Installer (system-wide, no venv)
#  https://github.com/FarnoudHosseini/FarnoudBot
# ============================================================
# Safe for:  curl -sSL .../install.sh | sudo bash
# All prompts read from /dev/tty so the menu works when piped.
# ============================================================

set +e   # never abort the whole script on a single failed command
set -u

REPO_URL="https://github.com/FarnoudHosseini/FarnoudBot.git"
INSTALL_DIR="/opt/farnoudbot"
SERVICE_BOT="farnoud-bot"
SERVICE_PANEL="farnoud-panel"

DB_NAME="farnoudbot"
DB_USER="farnoud"
DB_HOST="localhost"
DB_PORT="3306"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()   { echo -e "${GREEN}[OK]${NC}    $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

require_root() {
  if [ "$(id -u)" -ne 0 ]; then
    err "Run as root:  sudo bash install.sh"
    exit 1
  fi
}

ask() {
  local prompt="$1"
  local __var="$2"
  local __val=""
  if [ -r /dev/tty ]; then
    printf "%s" "$prompt" > /dev/tty
    IFS= read -r __val < /dev/tty || true
  else
    read -r -p "$prompt" __val || true
  fi
  printf -v "$__var" '%s' "$__val"
}

random_str() {
  tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c "${1:-24}" || echo "x$(date +%s)"
}

print_banner() {
  clear 2>/dev/null || true
  echo ""
  echo -e "${CYAN}========== Farnoud Bot Installer ==========${NC}"
  echo -e "  System-wide install (no virtualenv)"
  echo -e "  Database name: ${GREEN}${DB_NAME}${NC}"
  echo -e "  Install path:  ${GREEN}${INSTALL_DIR}${NC}"
  echo -e "${CYAN}===========================================${NC}"
  echo ""
}

mysql_exec() {
  local args=("$@")
  if command -v mysql >/dev/null 2>&1; then
    if mysql --protocol=socket -u root --connect-timeout=5 -e "SELECT 1" >/dev/null 2>&1; then
      mysql --protocol=socket -u root --connect-timeout=5 "${args[@]}"
      return $?
    fi
  fi
  if command -v mariadb >/dev/null 2>&1; then
    if mariadb --protocol=socket -u root --connect-timeout=5 -e "SELECT 1" >/dev/null 2>&1; then
      mariadb --protocol=socket -u root --connect-timeout=5 "${args[@]}"
      return $?
    fi
  fi
  mysql -u root --connect-timeout=5 "${args[@]}" 2>/dev/null
  return $?
}

wait_mysql() {
  log "Waiting for MySQL/MariaDB..."
  systemctl start mysql 2>/dev/null || systemctl start mariadb 2>/dev/null \
    || service mysql start 2>/dev/null || service mariadb start 2>/dev/null || true
  local i
  for i in $(seq 1 15); do
    if mysql_exec -e "SELECT 1" >/dev/null 2>&1; then
      ok "MySQL is up"
      return 0
    fi
    sleep 2
  done
  err "MySQL not reachable. Fix with:  systemctl status mysql"
  return 1
}

install_packages() {
  log "Installing system packages (this may take a few minutes)..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y -qq 2>/dev/null || apt-get update -y
  apt-get install -y \
    python3 python3-pip python3-dev \
    nginx curl git ufw \
    build-essential libssl-dev libffi-dev \
    certbot python3-certbot-nginx \
    2>&1 | tail -5

  if ! command -v mysql >/dev/null 2>&1 && ! command -v mariadb >/dev/null 2>&1; then
    apt-get install -y mysql-server mysql-client 2>&1 | tail -3 \
      || apt-get install -y default-mysql-server default-mysql-client 2>&1 | tail -3 \
      || apt-get install -y mariadb-server mariadb-client 2>&1 | tail -3
  fi

  systemctl enable nginx 2>/dev/null || true
  systemctl start nginx 2>/dev/null || true
  systemctl enable mysql 2>/dev/null || systemctl enable mariadb 2>/dev/null || true
  wait_mysql || true
  ok "System packages installed"
}

install_python_deps() {
  log "Installing Python packages system-wide (no venv)..."
  python3 -m pip install --upgrade pip setuptools wheel -q 2>/dev/null || true

  if [ -f "$INSTALL_DIR/requirements.txt" ]; then
    python3 -m pip install -r "$INSTALL_DIR/requirements.txt" --break-system-packages -q 2>/dev/null \
      || python3 -m pip install -r "$INSTALL_DIR/requirements.txt" -q 2>/dev/null \
      || python3 -m pip install -r "$INSTALL_DIR/requirements.txt"
  else
    warn "requirements.txt not found yet"
  fi

  python3 -c "import flask, telegram, pymysql, dotenv, werkzeug" 2>/dev/null || {
    log "Installing critical modules..."
    python3 -m pip install flask python-telegram-bot pymysql python-dotenv werkzeug \
      --break-system-packages -q 2>/dev/null \
      || python3 -m pip install flask python-telegram-bot pymysql python-dotenv werkzeug -q
  }
  ok "Python packages ready (system-wide)"
}

clone_repo() {
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating existing repo at $INSTALL_DIR ..."
    if [ -f "$INSTALL_DIR/.env" ]; then
      cp -a "$INSTALL_DIR/.env" "/tmp/farnoud.env.bak.$$"
    fi
    cd "$INSTALL_DIR" || exit 1
    git fetch --all 2>/dev/null || true
    git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null || true
    if [ -f "/tmp/farnoud.env.bak.$$" ]; then
      mv -f "/tmp/farnoud.env.bak.$$" "$INSTALL_DIR/.env"
    fi
  else
    log "Cloning repository..."
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR" || {
      err "git clone failed. Check network / GitHub access."
      exit 1
    }
  fi
  cd "$INSTALL_DIR" || exit 1
  rm -f miniapp.py.bak 2>/dev/null || true
  rm -rf "$INSTALL_DIR/venv" 2>/dev/null || true
  ok "Code is in $INSTALL_DIR"
}

prompt_domain() {
  echo ""
  echo -e "${CYAN}Domain for panel + miniapp (A record must point to this server)${NC}"
  echo "  Example: robot.example.com"
  while true; do
    ask "Domain: " DOMAIN
    DOMAIN=$(echo "${DOMAIN:-}" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    if [ -n "$DOMAIN" ]; then
      break
    fi
    err "Domain cannot be empty."
  done
  SERVER_IP=$(curl -s4 --max-time 6 ifconfig.me 2>/dev/null || curl -s4 --max-time 6 icanhazip.com 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
  DOMAIN_IP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)
  log "Server IP: ${SERVER_IP:-unknown}"
  log "Domain IP: ${DOMAIN_IP:-unresolved}"
  if [ -n "${DOMAIN_IP:-}" ] && [ -n "${SERVER_IP:-}" ] && [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
    warn "DNS IP does not match this server. SSL may fail."
    ask "Continue anyway? (y/N): " cont
    case "${cont:-}" in y|Y|yes|YES) ;; *) err "Stopped by user."; exit 1 ;; esac
  fi
}

setup_nginx_ssl() {
  log "Configuring nginx..."
  cat > /etc/nginx/sites-available/farnoudbot << EOF
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
  ln -sf /etc/nginx/sites-available/farnoudbot /etc/nginx/sites-enabled/farnoudbot
  rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
  mkdir -p /var/www/html
  nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true

  log "Requesting SSL certificate (certbot)..."
  if certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
      --register-unsafely-without-email --redirect 2>&1 | tail -8; then
    ok "SSL OK"
    PANEL_URL="https://${DOMAIN}"
    MINIAPP_URL="https://${DOMAIN}/miniapp/"
  else
    warn "SSL failed — using HTTP"
    PANEL_URL="http://${DOMAIN}"
    MINIAPP_URL="http://${DOMAIN}/miniapp/"
  fi

  if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
    cat > /etc/nginx/sites-available/farnoudbot << EOF
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
EOF
    PANEL_URL="https://${DOMAIN}"
    MINIAPP_URL="https://${DOMAIN}/miniapp/"
  fi
  nginx -t 2>/dev/null && systemctl reload nginx 2>/dev/null || true
  ok "Nginx ready — panel will be ${PANEL_URL}"
}

prompt_bot() {
  echo ""
  echo -e "${CYAN}Telegram bot token from @BotFather${NC}"
  while true; do
    ask "BOT_TOKEN: " BOT_TOKEN
    BOT_TOKEN=$(echo "${BOT_TOKEN:-}" | tr -d '[:space:]')
    [ -n "$BOT_TOKEN" ] && break
    err "Token cannot be empty."
  done
  echo ""
  echo -e "${CYAN}Your numeric Telegram admin ID (from @userinfobot)${NC}"
  while true; do
    ask "ADMIN_ID: " ADMIN_ID
    ADMIN_ID=$(echo "${ADMIN_ID:-}" | tr -d '[:space:]')
    if [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
      break
    fi
    err "ADMIN_ID must be digits only."
  done
}

setup_database() {
  log "Setting up database '${DB_NAME}' (app user: ${DB_USER}) — app never uses root"
  wait_mysql || {
    err "Cannot continue without MySQL"
    return 1
  }

  DB_PASS=$(random_str 20)
  SECRET_KEY=$(random_str 48)
  WEB_ADMIN_PASS=$(random_str 16)

  log "Creating database and app user..."
  SQLF=$(mktemp)
  cat > "$SQLF" << EOSQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
EOSQL

  if ! mysql_exec < "$SQLF" 2>/tmp/farnoud_mysql_err.txt; then
    warn "Modern CREATE USER failed, trying older syntax..."
    cat > "$SQLF" << EOSQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
FLUSH PRIVILEGES;
EOSQL
    if ! mysql_exec < "$SQLF" 2>>/tmp/farnoud_mysql_err.txt; then
      err "Database create failed. Last MySQL output:"
      cat /tmp/farnoud_mysql_err.txt 2>/dev/null || true
      rm -f "$SQLF"
      return 1
    fi
  fi
  rm -f "$SQLF"
  ok "Database ${DB_NAME} + user ${DB_USER} created"

  if [ -f "$INSTALL_DIR/setup_admins.sql" ]; then
    log "Importing setup_admins.sql..."
    mysql_exec "$DB_NAME" < "$INSTALL_DIR/setup_admins.sql" 2>/dev/null || true
  fi
  if [ -f "$INSTALL_DIR/models_schema.sql" ]; then
    log "Importing models_schema.sql..."
    mysql_exec "$DB_NAME" < "$INSTALL_DIR/models_schema.sql" 2>/dev/null || true
  fi

  log "Creating web admin login..."
  mysql_exec "$DB_NAME" -e "
CREATE TABLE IF NOT EXISTS admins (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(64) NOT NULL UNIQUE,
  password VARCHAR(255) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;" 2>/dev/null || true

  WEB_ADMIN_HASH=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('${WEB_ADMIN_PASS}'))" 2>/dev/null || echo "")
  if [ -n "$WEB_ADMIN_HASH" ]; then
    HASH_ESC=$(printf '%s' "$WEB_ADMIN_HASH" | sed "s/'/''/g")
    mysql_exec "$DB_NAME" -e "INSERT INTO admins (username, password) VALUES ('admin', '${HASH_ESC}') ON DUPLICATE KEY UPDATE password='${HASH_ESC}';" 2>/dev/null || true
  else
    warn "Could not hash web password (werkzeug missing)."
  fi

  PANEL_URL="${PANEL_URL:-http://${DOMAIN}}"
  MINIAPP_URL="${MINIAPP_URL:-http://${DOMAIN}/miniapp/}"

  log "Writing ${INSTALL_DIR}/.env ..."
  cat > "$INSTALL_DIR/.env" << EOF
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

  echo "$WEB_ADMIN_PASS" > /root/.farnoud_web_pass
  chmod 600 /root/.farnoud_web_pass

  log "Testing DB login as ${DB_USER}@${DB_NAME} ..."
  if mysql -u "$DB_USER" -p"$DB_PASS" -h "$DB_HOST" -P "$DB_PORT" "$DB_NAME" -e "SELECT 1" >/dev/null 2>&1; then
    ok "App DB user works"
  else
    warn "App DB user test failed — check credentials in .env"
  fi

  ok "Database setup done"
  return 0
}

setup_systemd() {
  log "Creating systemd services (system python3, no venv)..."
  PY=$(command -v python3)

  cat > /etc/systemd/system/${SERVICE_BOT}.service << EOF
[Unit]
Description=Farnoud Telegram Bot
After=network.target mysql.service mariadb.service
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${PY} ${INSTALL_DIR}/main.py
Restart=always
RestartSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

  cat > /etc/systemd/system/${SERVICE_PANEL}.service << EOF
[Unit]
Description=Farnoud Admin Panel + MiniApp
After=network.target mysql.service mariadb.service
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${PY} ${INSTALL_DIR}/admin_app.py
Restart=always
RestartSec=5
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable ${SERVICE_BOT} ${SERVICE_PANEL} >/dev/null 2>&1 || true
  systemctl restart ${SERVICE_BOT} 2>/dev/null || systemctl start ${SERVICE_BOT}
  systemctl restart ${SERVICE_PANEL} 2>/dev/null || systemctl start ${SERVICE_PANEL}
  sleep 2

  echo ""
  log "Service status:"
  systemctl is-active ${SERVICE_BOT} 2>/dev/null && ok "farnoud-bot is active" || err "farnoud-bot is NOT active"
  systemctl is-active ${SERVICE_PANEL} 2>/dev/null && ok "farnoud-panel is active" || err "farnoud-panel is NOT active"
  echo ""
  journalctl -u ${SERVICE_BOT} -n 15 --no-pager 2>/dev/null || true
  ok "systemd configured"
}

harden() {
  log "Firewall basics..."
  if command -v ufw >/dev/null 2>&1; then
    ufw allow OpenSSH >/dev/null 2>&1 || true
    ufw allow 80/tcp >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw deny 5000/tcp >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
  fi
  chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true
  ok "Done"
}

summary() {
  WEB_PASS=$(cat /root/.farnoud_web_pass 2>/dev/null || echo "(see /root/.farnoud_web_pass)")
  echo ""
  echo -e "${GREEN}========================================${NC}"
  echo -e "${GREEN}  INSTALL COMPLETE${NC}"
  echo -e "${GREEN}========================================${NC}"
  echo "  Panel:     ${PANEL_URL:-n/a}"
  echo "  Miniapp:   ${MINIAPP_URL:-n/a}"
  echo "  Web login: admin / ${WEB_PASS}"
  echo "  Path:      ${INSTALL_DIR}"
  echo "  Database:  ${DB_NAME} (user: ${DB_USER})"
  echo ""
  echo "  systemctl status farnoud-bot"
  echo "  systemctl status farnoud-panel"
  echo "  journalctl -u farnoud-bot -n 50 --no-pager"
  echo ""
}

do_install() {
  require_root
  print_banner
  log "Full install started"
  install_packages
  clone_repo
  install_python_deps
  prompt_domain
  setup_nginx_ssl
  prompt_bot
  setup_database || warn "DB step had issues — check logs above"
  setup_systemd
  harden
  summary
}

do_update() {
  require_root
  print_banner
  if [ ! -d "$INSTALL_DIR" ]; then
    err "Not installed yet."
    exit 1
  fi
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  clone_repo
  install_python_deps
  systemctl start ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  ok "Update finished"
}

do_uninstall() {
  require_root
  print_banner
  echo -e "${RED}This deletes services, nginx site, database ${DB_NAME}, and ${INSTALL_DIR}${NC}"
  ask "Type YES to confirm: " conf
  if [ "${conf:-}" != "YES" ]; then
    echo "Cancelled."
    exit 0
  fi
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  systemctl disable ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  rm -f /etc/systemd/system/${SERVICE_BOT}.service /etc/systemd/system/${SERVICE_PANEL}.service
  systemctl daemon-reload
  rm -f /etc/nginx/sites-enabled/farnoudbot /etc/nginx/sites-available/farnoudbot
  systemctl reload nginx 2>/dev/null || true
  mysql_exec -e "DROP DATABASE IF EXISTS \`${DB_NAME}\`; DROP USER IF EXISTS '${DB_USER}'@'localhost';" 2>/dev/null || true
  rm -rf "$INSTALL_DIR"
  rm -f /root/.farnoud_web_pass
  ok "Removed"
}

do_finish() {
  require_root
  print_banner
  log "Resume / finish install"
  if [ ! -d "$INSTALL_DIR" ]; then
    err "No $INSTALL_DIR — run full Install (option 1)"
    exit 1
  fi
  install_packages
  install_python_deps
  DOMAIN=$(grep -oP 'server_name \K[^; ]+' /etc/nginx/sites-available/farnoudbot 2>/dev/null | head -1 || true)
  if [ -z "${DOMAIN:-}" ]; then
    prompt_domain
    setup_nginx_ssl
  else
    log "Domain from nginx: $DOMAIN"
    if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
      PANEL_URL="https://${DOMAIN}"
      MINIAPP_URL="https://${DOMAIN}/miniapp/"
    else
      PANEL_URL="http://${DOMAIN}"
      MINIAPP_URL="http://${DOMAIN}/miniapp/"
    fi
  fi
  if [ -f "$INSTALL_DIR/.env" ]; then
    set -a; . "$INSTALL_DIR/.env"; set +a
  fi
  if [ -z "${BOT_TOKEN:-}" ] || [ -z "${ADMIN_ID:-}" ]; then
    prompt_bot
  else
    log "Using BOT_TOKEN / ADMIN_ID from existing .env"
  fi
  setup_database || warn "DB issues"
  setup_systemd
  harden
  summary
}

show_menu() {
  while true; do
    print_banner
    echo "  1) Install"
    echo "  2) Update"
    echo "  3) Uninstall"
    echo "  4) Finish / Resume (if stuck at database)"
    echo "  0) Exit"
    echo ""
    ask "Choose [0-4]: " choice
    case "${choice:-}" in
      1) do_install; break ;;
      2) do_update; break ;;
      3) do_uninstall; break ;;
      4) do_finish; break ;;
      0) echo "Bye."; exit 0 ;;
      *) err "Invalid option"; sleep 1 ;;
    esac
  done
}

case "${1:-}" in
  install|--install|-i)  do_install ;;
  update|--update|-u)    do_update ;;
  uninstall|--uninstall) do_uninstall ;;
  finish|--finish|resume) do_finish ;;
  ""|menu)               show_menu ;;
  *)
    echo "Usage: sudo bash install.sh [install|update|uninstall|finish]"
    exit 1
    ;;
esac
