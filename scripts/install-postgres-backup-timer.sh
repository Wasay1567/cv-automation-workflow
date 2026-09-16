#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-$HOME/cv-automation-workflow}"
SERVICE_NAME="cv-postgres-backup"
SYSTEMD_DIR="/etc/systemd/system"

if [ "$(id -u)" -eq 0 ]; then
  SUDO=""
else
  SUDO="sudo"
fi

$SUDO install -m 0755 "$APP_DIR/scripts/postgres-backup.sh" "/usr/local/bin/${SERVICE_NAME}.sh"

service_file="$(mktemp)"
timer_file="$(mktemp)"
trap 'rm -f "$service_file" "$timer_file"' EXIT

cat > "$service_file" <<EOF
[Unit]
Description=Back up CV PostgreSQL database to S3
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
User=$(id -un)
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/${SERVICE_NAME}.sh
EOF

cat > "$timer_file" <<EOF
[Unit]
Description=Daily CV PostgreSQL S3 backup

[Timer]
OnCalendar=*-*-* 18:00:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF

$SUDO install -m 0644 "$service_file" "$SYSTEMD_DIR/${SERVICE_NAME}.service"
$SUDO install -m 0644 "$timer_file" "$SYSTEMD_DIR/${SERVICE_NAME}.timer"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now "${SERVICE_NAME}.timer"

echo "Installed daily PostgreSQL backup timer."