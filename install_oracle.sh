#!/usr/bin/env bash
# Oracle Cloud (Ubuntu / Oracle Linux) par install: systemd timer + resource limits.
# Run:  bash install_oracle.sh      (normal user se, sudo password maang sakta hai)
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
USER_NAME="$(whoami)"

read -rp "Telegram Bot Token: " TOKEN
read -rp "Telegram Chat ID: " CHAT

echo "[1/4] Python install..."
if command -v apt-get >/dev/null; then
  sudo apt-get update -y && sudo apt-get install -y python3 python3-venv python3-pip
else
  sudo dnf install -y python3 python3-pip
fi

echo "[2/4] Virtualenv + packages..."
python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q requests beautifulsoup4 pypdf

echo "[3/4] Secrets file..."
sudo tee /etc/govt-job-alert.env >/dev/null <<ENV
TELEGRAM_BOT_TOKEN=$TOKEN
TELEGRAM_CHAT_ID=$CHAT
SOURCES_FILE=sources_india.json
SEEN_FILE=seen_india.json
ENV
sudo chmod 600 /etc/govt-job-alert.env

echo "[4/4] systemd service + timer..."
sudo tee /etc/systemd/system/govt-job-alert.service >/dev/null <<UNIT
[Unit]
Description=Govt Job Alert Monitor (blocked sites)

[Service]
Type=oneshot
User=$USER_NAME
WorkingDirectory=$DIR
EnvironmentFile=/etc/govt-job-alert.env
ExecStart=$DIR/venv/bin/python monitor.py
TimeoutStartSec=300
# Website (nginx) ko bachane ke liye limits:
Nice=19
IOSchedulingClass=idle
CPUQuota=25%
MemoryMax=250M
UNIT

sudo tee /etc/systemd/system/govt-job-alert.timer >/dev/null <<UNIT
[Unit]
Description=Run Govt Job Alert every 10 minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now govt-job-alert.timer
echo
echo "Done. Pehli run ek-do minute mein hogi. Log dekhne ke liye:"
echo "  journalctl -u govt-job-alert.service -n 50 --no-pager"
echo "Turant chalane ke liye:  sudo systemctl start govt-job-alert.service"
