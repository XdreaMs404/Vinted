#!/bin/bash

# Configuration
APP_DIR=$(pwd)
VENV_PYTHON="$APP_DIR/venv/bin/python"
DB_PATH="$APP_DIR/data/vinted-radar.db"

echo "=========================================="
echo "🚀 Vinted Radar - Systemd Installer"
echo "=========================================="
echo "Directory: $APP_DIR"
echo "Python: $VENV_PYTHON"
echo "Database: $DB_PATH"
echo ""

if [ "$EUID" -ne 0 ]; then
  echo "❌ Please run as root (or use sudo bash install_services.sh)"
  exit 1
fi

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ venv python not found at $VENV_PYTHON"
    echo "Make sure you run this script from inside the Vinted project directory."
    exit 1
fi

echo "1. Generating vinted-scraper.service..."
cat <<EOF > /etc/systemd/system/vinted-scraper.service
[Unit]
Description=Vinted Radar - 24/7 Batched Scraper
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
ExecStart=$VENV_PYTHON -m vinted_radar.cli batch --db $DB_PATH --page-limit 5
Restart=always
RestartSec=10

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
User=root
WorkingDirectory=$APP_DIR
ExecStart=$VENV_PYTHON -m vinted_radar.cli dashboard --db $DB_PATH --host 0.0.0.0 --port 8765
Restart=always
RestartSec=10

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

echo ""
echo "=========================================="
echo "✅ Installation Complete!"
echo "Both the Scraper and the Dashboard are now running silently in the background."
echo "=========================================="
echo "📊 Dashboard Access:"
echo "   http://<YOUR_VPS_IP>:8765"
echo ""
echo "⚠️  Firewall (If you cannot access the page):"
echo "   Run: ufw allow 8765/tcp"
echo ""
echo "💡 Useful Commands:"
echo " - View Scraper real-time logs: journalctl -u vinted-scraper.service -f"
echo " - View Dashboard logs:         journalctl -u vinted-dashboard.service -f"
echo " - Stop the scraper:            systemctl stop vinted-scraper.service"
echo "=========================================="
