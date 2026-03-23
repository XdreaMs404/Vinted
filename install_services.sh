#!/bin/bash
set -euo pipefail

APP_DIR=$(pwd)
VENV_PYTHON="${APP_DIR}/venv/bin/python"
DB_PATH="${DB_PATH:-${APP_DIR}/data/vinted-radar.db}"
SCRAPER_PAGE_LIMIT="${SCRAPER_PAGE_LIMIT:-5}"
SCRAPER_STATE_REFRESH_LIMIT="${SCRAPER_STATE_REFRESH_LIMIT:-10}"
SCRAPER_INTERVAL_SECONDS="${SCRAPER_INTERVAL_SECONDS:-1800}"
DASHBOARD_HOST="${DASHBOARD_HOST:-127.0.0.1}"
DASHBOARD_PORT="${DASHBOARD_PORT:-8765}"
DASHBOARD_BASE_PATH="${DASHBOARD_BASE_PATH:-}"
DASHBOARD_PUBLIC_BASE_URL="${DASHBOARD_PUBLIC_BASE_URL:-}"
SERVICE_USER="${SERVICE_USER:-$(stat -c '%U' "$APP_DIR")}" 
SERVICE_GROUP="${SERVICE_GROUP:-$(id -gn "$SERVICE_USER")}" 

DASHBOARD_BASE_PATH_ARG=""
if [ -n "$DASHBOARD_BASE_PATH" ]; then
  DASHBOARD_BASE_PATH_ARG=" --base-path $DASHBOARD_BASE_PATH"
fi

DASHBOARD_PUBLIC_BASE_URL_ARG=""
if [ -n "$DASHBOARD_PUBLIC_BASE_URL" ]; then
  DASHBOARD_PUBLIC_BASE_URL_ARG=" --public-base-url $DASHBOARD_PUBLIC_BASE_URL"
fi

echo "=========================================="
echo "Vinted Radar - Systemd Installer"
echo "=========================================="
echo "Directory: $APP_DIR"
echo "Python: $VENV_PYTHON"
echo "Database: $DB_PATH"
echo "Service user: $SERVICE_USER:$SERVICE_GROUP"
echo "Scraper interval: ${SCRAPER_INTERVAL_SECONDS}s"
echo "Dashboard bind: ${DASHBOARD_HOST}:${DASHBOARD_PORT}"
if [ -n "$DASHBOARD_BASE_PATH" ]; then
  echo "Dashboard base path: $DASHBOARD_BASE_PATH"
fi
if [ -n "$DASHBOARD_PUBLIC_BASE_URL" ]; then
  echo "Dashboard public base URL: $DASHBOARD_PUBLIC_BASE_URL"
fi
echo

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (or use sudo bash install_services.sh)"
  exit 1
fi

if [ ! -f "$VENV_PYTHON" ]; then
  echo "venv python not found at $VENV_PYTHON"
  echo "Make sure you run this script from inside the Vinted project directory."
  exit 1
fi

if [ "$SERVICE_USER" = "root" ]; then
  echo "Warning: service user resolved to root."
  echo "Set SERVICE_USER=<unix-user> when possible to avoid running the app as root."
fi

echo "1. Generating vinted-scraper.service..."
cat <<EOF > /etc/systemd/system/vinted-scraper.service
[Unit]
Description=Vinted Radar - Continuous Scraper
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_PYTHON -m vinted_radar.cli continuous --db $DB_PATH --page-limit $SCRAPER_PAGE_LIMIT --state-refresh-limit $SCRAPER_STATE_REFRESH_LIMIT --interval-seconds $SCRAPER_INTERVAL_SECONDS
Restart=on-failure
RestartSec=15
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "2. Generating vinted-dashboard.service..."
cat <<EOF > /etc/systemd/system/vinted-dashboard.service
[Unit]
Description=Vinted Radar - Dashboard UI
After=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
WorkingDirectory=$APP_DIR
Environment=PYTHONUNBUFFERED=1
ExecStart=$VENV_PYTHON -m vinted_radar.cli dashboard --db $DB_PATH --host $DASHBOARD_HOST --port $DASHBOARD_PORT$DASHBOARD_BASE_PATH_ARG$DASHBOARD_PUBLIC_BASE_URL_ARG
Restart=on-failure
RestartSec=15
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "3. Reloading systemd daemon..."
systemctl daemon-reload

echo "4. Enabling services to auto-start on server reboot..."
systemctl enable vinted-scraper.service
systemctl enable vinted-dashboard.service

echo "5. Starting services..."
systemctl restart vinted-scraper.service
systemctl restart vinted-dashboard.service

echo
echo "=========================================="
echo "Installation complete"
echo "=========================================="
echo "Dashboard bind: http://${DASHBOARD_HOST}:${DASHBOARD_PORT}"
if [ -n "$DASHBOARD_PUBLIC_BASE_URL" ]; then
  echo "Advertised product URL: $DASHBOARD_PUBLIC_BASE_URL"
elif [ -n "$DASHBOARD_BASE_PATH" ]; then
  echo "Advertised product path prefix: $DASHBOARD_BASE_PATH"
fi
if [ "$DASHBOARD_HOST" = "127.0.0.1" ]; then
  echo "Dashboard is bound to localhost only. Use SSH tunneling or a reverse proxy for remote access."
else
  echo "Dashboard is exposed on a non-localhost interface. Add auth / reverse proxy controls before internet exposure."
fi
echo "Smoke check: python scripts/verify_vps_serving.py --base-url ${DASHBOARD_PUBLIC_BASE_URL:-http://${DASHBOARD_HOST}:${DASHBOARD_PORT}${DASHBOARD_BASE_PATH}} --listing-id <id>"
echo
echo "Useful commands:"
echo " - Scraper logs:   journalctl -u vinted-scraper.service -f"
echo " - Dashboard logs: journalctl -u vinted-dashboard.service -f"
echo " - Stop scraper:   systemctl stop vinted-scraper.service"
echo " - Stop dashboard: systemctl stop vinted-dashboard.service"
echo "=========================================="
