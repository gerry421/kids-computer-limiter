#!/usr/bin/env bash
# =============================================================================
# setup.sh — One-time installation of the Kids Computer Limiter on a Pi
#
# Usage:  sudo bash setup.sh
#
# What this does:
#   1. Verifies root access
#   2. Prompts for this device's unique ID
#   3. Installs Python dependencies
#   4. Clones / updates the repo to INSTALL_DIR
#   5. Configures git identity for log commits
#   6. Creates /etc/limiter/device_id.conf
#   7. Creates log directory
#   8. Backs up /etc/hosts
#   9. Installs the cron job
#  10. Runs the limiter once to verify everything works
# =============================================================================

set -euo pipefail

REPO_URL="https://github.com/gerry421/kids-computer-limiter.git"
INSTALL_DIR="/opt/kids-computer-limiter"
RUNNER_SCRIPT="$INSTALL_DIR/install/limiter_runner.sh"
CRON_COMMENT="# Kids Computer Limiter"
CRON_LINE="*/5 * * * * $RUNNER_SCRIPT $CRON_COMMENT"
DEVICE_CONF_DIR="/etc/limiter"
DEVICE_CONF_FILE="$DEVICE_CONF_DIR/device_id.conf"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo "[INFO]  $*"; }
warn()  { echo "[WARN]  $*"; }
error() { echo "[ERROR] $*" >&2; }

require_root() {
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root (use: sudo bash setup.sh)"
        exit 1
    fi
}

prompt_device_id() {
    while true; do
        read -rp "Enter a unique device ID for this Pi (e.g. frankie-pi): " DEVICE_ID
        DEVICE_ID="${DEVICE_ID// /-}"   # replace spaces with hyphens
        if [[ -n "$DEVICE_ID" ]]; then
            break
        fi
        warn "Device ID cannot be empty."
    done
}

install_dependencies() {
    info "Checking Python dependencies…"
    if ! command -v python3 &>/dev/null; then
        error "python3 is not installed. Run: sudo apt-get install -y python3"
        exit 1
    fi
    python3 -m pip install --quiet --break-system-packages pyyaml 2>/dev/null \
        || python3 -m pip install --quiet pyyaml
    info "Dependencies OK"
}

clone_or_update_repo() {
    if [[ -d "$INSTALL_DIR/.git" ]]; then
        info "Updating existing repo at $INSTALL_DIR…"
        git -C "$INSTALL_DIR" pull --quiet --rebase
    else
        info "Cloning repo to $INSTALL_DIR…"
        git clone --quiet "$REPO_URL" "$INSTALL_DIR"
    fi
}

configure_git_identity() {
    # Needed so git commit (for log uploads) doesn't fail
    local name email
    name=$(git -C "$INSTALL_DIR" config user.name 2>/dev/null || true)
    email=$(git -C "$INSTALL_DIR" config user.email 2>/dev/null || true)

    if [[ -z "$name" ]]; then
        git -C "$INSTALL_DIR" config user.name "limiter-$DEVICE_ID"
    fi
    if [[ -z "$email" ]]; then
        git -C "$INSTALL_DIR" config user.email "limiter@${DEVICE_ID}.local"
    fi
    info "Git identity configured"
}

write_device_id() {
    mkdir -p "$DEVICE_CONF_DIR"
    printf 'DEVICE_ID="%s"\n' "$DEVICE_ID" > "$DEVICE_CONF_FILE"
    chmod 600 "$DEVICE_CONF_FILE"
    info "Device ID saved to $DEVICE_CONF_FILE"
}

create_log_dir() {
    local log_dir="/var/log/limiter"
    mkdir -p "$log_dir"
    chmod 755 "$log_dir"
    info "Log directory: $log_dir"
}

backup_hosts() {
    local backup="/etc/hosts.limiter.backup"
    if [[ ! -f "$backup" ]]; then
        cp /etc/hosts "$backup"
        info "Hosts file backed up to $backup"
    else
        info "Hosts backup already exists — skipping"
    fi
}

install_cron() {
    # Remove any existing limiter cron lines then add a fresh one
    local tmpfile
    tmpfile=$(mktemp)
    crontab -l 2>/dev/null | grep -v "limiter_runner" > "$tmpfile" || true
    echo "$CRON_LINE" >> "$tmpfile"
    crontab "$tmpfile"
    rm "$tmpfile"
    info "Cron job installed: $CRON_LINE"
}

make_runner_executable() {
    chmod +x "$RUNNER_SCRIPT"
    info "Runner script is executable: $RUNNER_SCRIPT"
}

run_once() {
    info "Running limiter once to verify setup…"
    cd "$INSTALL_DIR"
    python3 -m limiter.main && info "First run succeeded" \
        || warn "First run exited with errors — check /var/log/limiter/limiter.log"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
require_root
prompt_device_id

info "Installing Kids Computer Limiter for device: $DEVICE_ID"

install_dependencies
clone_or_update_repo
configure_git_identity
write_device_id
create_log_dir
backup_hosts
make_runner_executable
install_cron
run_once

echo ""
echo "======================================================"
echo " Installation complete!"
echo " Device ID : $DEVICE_ID"
echo " Log file  : /var/log/limiter/limiter.log"
echo " Config    : $DEVICE_CONF_FILE"
echo " Cron job  : every 5 minutes (auto-active)"
echo "======================================================"
echo ""
echo "To monitor: tail -f /var/log/limiter/limiter.log"
echo "To remove:  sudo bash $INSTALL_DIR/install/uninstall.sh"
