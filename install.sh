#!/bin/bash
# ============================================================
#  Farnoud Bot — One-Line / Interactive Installer
#  Repo: https://github.com/FarnoudHosseini/FarnoudBot
#  Credit: Farnoud Hosseini
# ============================================================
set -uo pipefail

# Works with: curl ... | sudo bash  (reads input from /dev/tty)

REPO_URL="https://github.com/FarnoudHosseini/FarnoudBot.git"
INSTALL_DIR="/opt/farnoudbot"
SERVICE_BOT="farnoud-bot"
SERVICE_PANEL="farnoud-panel"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_banner() {
  clear 2>/dev/null || true
  echo -e "${CYAN}"
  cat << 'BANNER'
 ███████╗ █████╗ ██████╗ ███╗   ██╗ ██████╗ ██╗   ██╗██████╗     ██████╗  ██████╗ ████████╗
 ██╔════╝██╔══██╗██╔══██╗████╗  ██║██╔═══██╗██║   ██║██╔══██╗    ██╔══██╗██╔═══██╗╚══██╔══╝
 █████╗  ███████║██████╔╝██╔██╗ ██║██║   ██║██║   ██║██║  ██║    ██████╔╝██║   ██║   ██║
 ██╔══╝  ██╔══██║██╔══██╗██║╚██╗██║██║   ██║██║   ██║██║  ██║    ██╔══██╗██║   ██║   ██║
 ██║     ██║  ██║██║  ██║██║ ╚████║╚██████╔╝╚██████╔╝██████╔╝    ██████╔╝╚██████╔╝   ██║
 ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ╚═════╝     ╚═════╝  ╚═════╝    ╚═╝
BANNER
  echo -e "${NC}"
  echo -e "                    ${GREEN}* Farnoud Bot *${NC}"
  echo -e "          VPN sales bot + admin panel + mini app"
  echo ""
}

require_root() {
  if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo -e "${RED}[ERROR] Run as root: sudo bash install.sh${NC}"
    exit 1
  fi
}

random_str() {
  local len=${1:-24}
  tr -dc 'A-Za-z0-9' </dev/urandom | head -c "$len" || echo "Rnd$(date +%s)"
}

random_pass() {
  tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20 || echo "Pass$(date +%s)Xx"
}

# Read from real terminal even when script is piped (curl | bash)
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

log()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ---------- MySQL helper (no hang on password prompt) ----------
mysql_root() {
  # Prefer socket auth as root; never wait for interactive password
  if mysql --protocol=socket -u root -e "SELECT 1" &>/dev/null; then
    mysql --protocol=socket -u root "$@"
    return $?
  fi
  if sudo mysql -u root -e "SELECT 1" &>/dev/null; then
    sudo mysql -u root "$@"
    return $?
  fi
  if mysql -u root -e "SELECT 1" &>/dev/null; then
    mysql -u root "$@"
    return $?
  fi
  # Debian/Ubuntu sometimes needs sudo without password on fresh install
  if command -v mariadb >/dev/null 2>&1 && mariadb -u root -e "SELECT 1" &>/dev/null; then
    mariadb -u root "$@"
    return $?
  fi
  return 1
}

ensure_mysql_running() {
  log "Starting MySQL/MariaDB..."
  systemctl start mysql 2>/dev/null || systemctl start mariadb 2>/dev/null || service mysql start 2>/dev/null || service mariadb start 2>/dev/null || true
  systemctl enable mysql 2>/dev/null || systemctl enable mariadb 2>/dev/null || true
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    if mysql_root -e "SELECT 1" &>/dev/null; then
      ok "MySQL is ready"
      return 0
    fi
    sleep 2
  done
  err "Cannot connect to MySQL as root (socket auth)."
  err "Try manually: sudo mysql -e \"SELECT 1\""
  return 1
}

install_prereqs() {
  log "Updating packages and installing dependencies..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq \
    python3 python3-pip python3-venv python3-dev \
    mysql-server mysql-client \
    nginx certbot python3-certbot-nginx \
    curl git ufw fail2ban \
    build-essential libssl-dev libffi-dev \
    > /dev/null 2>&1 || apt-get install -y \
    python3 python3-pip python3-venv python3-dev \
    default-mysql-server default-mysql-client \
    nginx certbot python3-certbot-nginx \
    curl git ufw \
    build-essential libssl-dev libffi-dev
  ensure_mysql_running || exit 1
  systemctl enable --now nginx 2>/dev/null || true
  ok "Dependencies installed"
}

clone_or_update_repo() {
  if [ -d "$INSTALL_DIR/.git" ]; then
    log "Updating repo in $INSTALL_DIR ..."
    cd "$INSTALL_DIR"
    # keep .env
    git fetch --all 2>/dev/null || true
    git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null || true
  else
    log "Cloning repo into $INSTALL_DIR ..."
    rm -rf "$INSTALL_DIR"
    git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
  fi
  cd "$INSTALL_DIR"
  rm -f miniapp.py.bak 2>/dev/null || true
  ok "Repo ready"
}

setup_venv() {
  log "Python venv + pip packages..."
  cd "$INSTALL_DIR"
  if [ ! -d "venv" ]; then
    python3 -m venv venv
  fi
  # shellcheck disable=SC1091
  source venv/bin/activate
  pip install --upgrade pip -q
  pip install -r requirements.txt -q
  ok "Python deps ready"
}

prompt_domain() {
  echo ""
  echo -e "${CYAN}Enter your domain (DNS A record must point to this server)${NC}"
  echo -e "  Example: panel.example.com"
  ask "Domain: " DOMAIN
  DOMAIN=$(echo "$DOMAIN" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
  if [ -z "$DOMAIN" ]; then
    err "Domain is empty."
    exit 1
  fi
  SERVER_IP=$(curl -s4 --max-time 8 ifconfig.me || curl -s4 --max-time 8 icanhazip.com || hostname -I | awk '{print $1}')
  DOMAIN_IP=$(getent ahostsv4 "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -1 || true)
  log "Server IP: ${SERVER_IP}"
  if [ -n "$DOMAIN_IP" ]; then
    log "Domain IP: ${DOMAIN_IP}"
    if [ "$DOMAIN_IP" != "$SERVER_IP" ]; then
      warn "Domain IP does not match server IP. SSL may fail."
      ask "Continue anyway? (y/N): " cont
      [[ "$cont" =~ ^[Yy]$ ]] || exit 1
    fi
  else
    warn "Could not resolve domain. Make sure DNS is set."
  fi
}

setup_ssl() {
  log "Configuring nginx + SSL (certbot)..."
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
    ok "SSL installed"
    MINIAPP_URL="https://${DOMAIN}/miniapp/"
    PANEL_URL="https://${DOMAIN}"
  else
    warn "SSL failed. Continuing with HTTP..."
    MINIAPP_URL="http://${DOMAIN}/miniapp/"
    PANEL_URL="http://${DOMAIN}"
  fi

  if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
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
  else
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
  ok "Nginx configured"
}

prompt_bot_token() {
  echo ""
  echo -e "${CYAN}Enter Telegram bot token (from @BotFather)${NC}"
  ask "BOT_TOKEN: " BOT_TOKEN
  BOT_TOKEN=$(echo "$BOT_TOKEN" | tr -d '[:space:]')
  if [ -z "$BOT_TOKEN" ]; then
    err "Token is empty."
    exit 1
  fi
}

prompt_admin_id() {
  echo ""
  echo -e "${CYAN}Enter admin numeric Telegram ID${NC}"
  echo -e "  (get it from @userinfobot)"
  ask "ADMIN_ID: " ADMIN_ID
  ADMIN_ID=$(echo "$ADMIN_ID" | tr -d '[:space:]')
  if ! [[ "$ADMIN_ID" =~ ^[0-9]+$ ]]; then
    err "ADMIN_ID must be numbers only."
    exit 1
  fi
}

setup_database() {
  log "Setting up database + .env ..."
  ensure_mysql_running || exit 1

  DB_NAME="farnoudbot"
  DB_USER="farnoud"
  DB_PASS=$(random_pass)
  SECRET_KEY=$(random_str 48)
  WEB_ADMIN_PASS=$(random_pass)

  cd "$INSTALL_DIR"
  # shellcheck disable=SC1091
  source venv/bin/activate

  log "Generating web admin password hash..."
  WEB_ADMIN_HASH=$(python3 -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('${WEB_ADMIN_PASS}'))" 2>/dev/null) || {
    err "werkzeug hash failed. Is requirements.txt installed?"
    exit 1
  }

  log "Creating database and user..."
  # Write SQL to temp file to avoid heredoc / quoting issues
  local sqlfile
  sqlfile=$(mktemp)
  cat > "$sqlfile" << SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
ALTER USER '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost';
FLUSH PRIVILEGES;
SQL
  if ! mysql_root < "$sqlfile"; then
    # Older MySQL without CREATE USER IF NOT EXISTS
    cat > "$sqlfile" << SQL
CREATE DATABASE IF NOT EXISTS \`${DB_NAME}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON \`${DB_NAME}\`.* TO '${DB_USER}'@'localhost' IDENTIFIED BY '${DB_PASS}';
FLUSH PRIVILEGES;
SQL
    if ! mysql_root < "$sqlfile"; then
      rm -f "$sqlfile"
      err "MySQL CREATE DATABASE failed."
      err "Run: sudo mysql -e \"SELECT VERSION();\""
      exit 1
    fi
  fi
  rm -f "$sqlfile"
  ok "Database created"

  log "Importing schema (if present)..."
  if [ -f "$INSTALL_DIR/setup_admins.sql" ]; then
    mysql_root "$DB_NAME" < "$INSTALL_DIR/setup_admins.sql" 2>/dev/null || true
  fi
  if [ -f "$INSTALL_DIR/models_schema.sql" ]; then
    mysql_root "$DB_NAME" < "$INSTALL_DIR/models_schema.sql" 2>/dev/null || true
  fi

  log "Creating web admin user..."
  mysql_root "$DB_NAME" -e \
    "CREATE TABLE IF NOT EXISTS admins (
       id INT AUTO_INCREMENT PRIMARY KEY,
       username VARCHAR(64) NOT NULL UNIQUE,
       password VARCHAR(255) NOT NULL
     ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;" 2>/dev/null || true

  # Escape single quotes in hash for SQL
  local hash_esc
  hash_esc=$(printf "%s" "$WEB_ADMIN_HASH" | sed "s/'/\\\\'/g")
  mysql_root "$DB_NAME" -e \
    "INSERT INTO admins (username, password) VALUES ('admin', '${hash_esc}')
     ON DUPLICATE KEY UPDATE password='${hash_esc}';" 2>/dev/null || \
  mysql_root "$DB_NAME" -e \
    "UPDATE admins SET password='${hash_esc}' WHERE username='admin';
     INSERT IGNORE INTO admins (username, password) VALUES ('admin', '${hash_esc}');" 2>/dev/null || true

  # Keep existing .env values if re-running and user wants? We rewrite with new DB pass.
  MINIAPP_URL="${MINIAPP_URL:-https://${DOMAIN}/miniapp/}"

  log "Writing .env ..."
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

  echo "${WEB_ADMIN_PASS}" > /root/.farnoud_web_pass
  chmod 600 /root/.farnoud_web_pass

  ok "Database and .env ready"
}

setup_systemd() {
  log "Creating systemd services..."
  cat > /etc/systemd/system/${SERVICE_BOT}.service << SERV
[Unit]
Description=Farnoud Telegram Bot
After=network.target mysql.service mariadb.service
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
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERV

  cat > /etc/systemd/system/${SERVICE_PANEL}.service << SERV
[Unit]
Description=Farnoud Admin Panel + MiniApp
After=network.target mysql.service mariadb.service
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
PrivateTmp=true

[Install]
WantedBy=multi-user.target
SERV

  systemctl daemon-reload
  systemctl enable ${SERVICE_BOT} ${SERVICE_PANEL} >/dev/null 2>&1 || true
  systemctl restart ${SERVICE_BOT} ${SERVICE_PANEL} || systemctl start ${SERVICE_BOT} ${SERVICE_PANEL}
  sleep 2
  systemctl --no-pager --full status ${SERVICE_BOT} | head -15 || true
  systemctl --no-pager --full status ${SERVICE_PANEL} | head -15 || true
  ok "Services started"
}

harden_security() {
  log "Basic firewall / permissions..."
  if command -v ufw >/dev/null 2>&1; then
    ufw allow OpenSSH >/dev/null 2>&1 || true
    ufw allow 80/tcp >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw deny 5000/tcp >/dev/null 2>&1 || true
    ufw --force enable >/dev/null 2>&1 || true
  fi
  systemctl enable --now fail2ban 2>/dev/null || true
  chmod 600 "$INSTALL_DIR/.env" 2>/dev/null || true
  ok "Hardening done"
}

print_summary() {
  WEB_PASS=$(cat /root/.farnoud_web_pass 2>/dev/null || echo "(see /root/.farnoud_web_pass)")
  PANEL_URL="${PANEL_URL:-https://${DOMAIN}}"
  MINIAPP_URL="${MINIAPP_URL:-https://${DOMAIN}/miniapp/}"
  echo ""
  echo -e "${GREEN}==============================================${NC}"
  echo -e "${GREEN}  Install finished successfully${NC}"
  echo -e "${GREEN}==============================================${NC}"
  echo ""
  echo -e "Admin panel:  ${CYAN}${PANEL_URL}${NC}"
  echo -e "Mini app:     ${CYAN}${MINIAPP_URL}${NC}"
  echo -e "Web login:    ${YELLOW}admin / ${WEB_PASS}${NC}"
  echo -e "Install path: ${INSTALL_DIR}"
  echo -e "Bot commands: /start   /admin"
  echo ""
  echo -e "Check services:"
  echo -e "  systemctl status ${SERVICE_BOT}"
  echo -e "  systemctl status ${SERVICE_PANEL}"
  echo -e "  journalctl -u ${SERVICE_BOT} -n 50 --no-pager"
  echo ""
  echo -e "Repo: https://github.com/FarnoudHosseini/FarnoudBot"
  echo ""
}

do_install() {
  require_root
  print_banner
  log "Starting full install..."
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
  print_summary
}

do_update() {
  require_root
  print_banner
  if [ ! -d "$INSTALL_DIR" ]; then
    err "No previous install found. Run Install first."
    exit 1
  fi
  log "Updating..."
  systemctl stop ${SERVICE_BOT} ${SERVICE_PANEL} 2>/dev/null || true
  cp -a "$INSTALL_DIR/.env" "/root/farnoud_env_backup_$(date +%Y%m%d%H%M%S)" 2>/dev/null || true
  clone_or_update_repo
  # restore .env if git wiped it
  if [ ! -f "$INSTALL_DIR/.env" ]; then
    latest=$(ls -1t /root/farnoud_env_backup_* 2>/dev/null | head -1 || true)
    [ -n "$latest" ] && cp -a "$latest" "$INSTALL_DIR/.env"
  fi
  setup_venv
  systemctl start ${SERVICE_BOT} ${SERVICE_PANEL}
  ok "Update done. Services restarted."
}

do_uninstall() {
  require_root
  print_banner
  echo -e "${RED}WARNING: Full remove (DB, services, nginx site, files)${NC}"
  ask "Type YES to confirm: " conf
  if [ "$conf" != "YES" ]; then
    echo "Cancelled."
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
  ok "Uninstall complete."
}

# Finish install if previous run stopped after SSL/token (recovery)
do_finish() {
  require_root
  print_banner
  if [ ! -d "$INSTALL_DIR" ]; then
    err "No /opt/farnoudbot — run full Install."
    exit 1
  fi
  log "Resume / finish install (DB + services)..."
  # reuse domain from nginx if possible
  if [ -z "${DOMAIN:-}" ]; then
    DOMAIN=$(grep -oP 'server_name \K[^;]+' /etc/nginx/sites-available/farnoudbot 2>/dev/null | head -1 | tr -d ' ' || true)
  fi
  if [ -z "${DOMAIN:-}" ]; then
    prompt_domain
  else
    log "Using domain: $DOMAIN"
    MINIAPP_URL="https://${DOMAIN}/miniapp/"
    PANEL_URL="https://${DOMAIN}"
    if [ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
      MINIAPP_URL="http://${DOMAIN}/miniapp/"
      PANEL_URL="http://${DOMAIN}"
    fi
  fi
  if [ -z "${BOT_TOKEN:-}" ] || [ -z "${ADMIN_ID:-}" ]; then
    if [ -f "$INSTALL_DIR/.env" ]; then
      # shellcheck disable=SC1091
      set -a; source "$INSTALL_DIR/.env"; set +a
    fi
  fi
  if [ -z "${BOT_TOKEN:-}" ]; then
    prompt_bot_token
  fi
  if [ -z "${ADMIN_ID:-}" ]; then
    prompt_admin_id
  fi
  setup_venv
  setup_database
  setup_systemd
  harden_security
  print_summary
}

show_menu() {
  while true; do
    print_banner
    echo -e "  ${CYAN}1)${NC} Full Install"
    echo -e "  ${CYAN}2)${NC} Update"
    echo -e "  ${CYAN}3)${NC} Full Uninstall"
    echo -e "  ${CYAN}4)${NC} Finish / Resume (if install stopped at database)"
    echo -e "  ${CYAN}0)${NC} Exit"
    echo ""
    echo -e "  Repo: https://github.com/FarnoudHosseini/FarnoudBot"
    echo ""
    ask "Choose [0-4]: " choice
    case "$choice" in
      1|install|Install) do_install; break ;;
      2|update|Update) do_update; break ;;
      3|uninstall|Uninstall) do_uninstall; break ;;
      4|finish|resume|Finish) do_finish; break ;;
      0|q|Q|exit) echo "Bye."; exit 0 ;;
      *)
        err "Invalid option."
        sleep 1
        ;;
    esac
  done
}

case "${1:-}" in
  install|--install|-i) do_install ;;
  update|--update|-u) do_update ;;
  uninstall|--uninstall|-x) do_uninstall ;;
  finish|--finish|resume|--resume) do_finish ;;
  menu|--menu|"") show_menu ;;
  *)
    echo "Usage:"
    echo "  sudo bash install.sh              # interactive menu"
    echo "  sudo bash install.sh install      # full install"
    echo "  sudo bash install.sh finish       # resume after failed DB step"
    echo "  sudo bash install.sh update"
    echo "  sudo bash install.sh uninstall"
    exit 1
    ;;
esac
