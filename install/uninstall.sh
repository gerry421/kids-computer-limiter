#!/usr/bin/env bash
# =============================================================================
# uninstall.sh — Remove the Kids Computer Limiter completely
#
# Usage:  sudo bash /opt/kids-computer-limiter/install/uninstall.sh
# =============================================================================

set -euo pipefail

INSTALL_DIR="/opt/kids-computer-limiter"
DEVICE_CONF_DIR="/etc/limiter"
HOSTS_BACKUP="/etc/hosts.limiter.backup"
LOG_DIR="/var/log/limiter"

info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }

if [[ $EUID -ne 0 ]]; then
    echo "[ERROR] Run as root: sudo bash uninstall.sh"
    exit 1
fi

# 1. Remove cron job
info "Removing cron job…"
tmpfile=$(mktemp)
crontab -l 2>/dev/null | grep -v "limiter_runner" > "$tmpfile" || true
crontab "$tmpfile"
rm "$tmpfile"

# 2. Clear limiter block from /etc/hosts
info "Removing limiter block from /etc/hosts…"
BLOCK_BEGIN="# === BEGIN LIMITER BLOCK ==="
BLOCK_END="# === END LIMITER BLOCK ==="
python3 - <<'PYEOF'
import re, shutil, sys
path = "/etc/hosts"
begin = "# === BEGIN LIMITER BLOCK ==="
end   = "# === END LIMITER BLOCK ==="
with open(path, "r") as f:
    content = f.read()
# Remove the block and any blank line immediately before it
cleaned = re.sub(
    r'\n?' + re.escape(begin) + r'.*?' + re.escape(end) + r'\n?',
    '',
    content,
    flags=re.DOTALL,
)
with open(path, "w") as f:
    f.write(cleaned)
print("[INFO]  Limiter block removed from /etc/hosts")
PYEOF

# 3. Flush DNS
if systemctl is-active --quiet systemd-resolved 2>/dev/null; then
    systemctl restart systemd-resolved && info "DNS cache flushed"
fi

# 4. Offer to restore hosts backup
if [[ -f "$HOSTS_BACKUP" ]]; then
    read -rp "Restore original /etc/hosts from backup? [y/N]: " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        cp "$HOSTS_BACKUP" /etc/hosts
        info "Hosts file restored from $HOSTS_BACKUP"
    fi
fi

# 5. Remove config directory
if [[ -d "$DEVICE_CONF_DIR" ]]; then
    rm -rf "$DEVICE_CONF_DIR"
    info "Removed $DEVICE_CONF_DIR"
fi

# 6. Remove log directory (optional)
if [[ -d "$LOG_DIR" ]]; then
    read -rp "Delete log directory $LOG_DIR? [y/N]: " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        rm -rf "$LOG_DIR"
        info "Removed $LOG_DIR"
    else
        info "Logs kept at $LOG_DIR"
    fi
fi

# 7. Remove temp files
rm -f /tmp/limiter_config_cache.yaml /tmp/limiter_last_commit.txt

# 8. Remove install directory (optional)
if [[ -d "$INSTALL_DIR" ]]; then
    read -rp "Delete installation directory $INSTALL_DIR? [y/N]: " answer
    if [[ "$answer" =~ ^[Yy]$ ]]; then
        rm -rf "$INSTALL_DIR"
        info "Removed $INSTALL_DIR"
    else
        info "Installation kept at $INSTALL_DIR"
    fi
fi

echo ""
echo "======================================================"
echo " Uninstall complete. Kids Computer Limiter removed."
echo "======================================================"
