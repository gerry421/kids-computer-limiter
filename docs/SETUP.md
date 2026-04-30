# Setup Guide

Step-by-step instructions for installing the Kids Computer Limiter on a Raspberry Pi.

## Prerequisites

- Raspberry Pi running Raspberry Pi OS (or any Debian/Ubuntu-based Linux)
- Internet connection (Wi-Fi hotspot is fine)
- `git`, `python3`, and `pip` installed
- `sudo` access

Install prerequisites if needed:

```bash
sudo apt-get update
sudo apt-get install -y git python3 python3-pip
```

## Step 1 — Add the device to the config

Before running setup on the Pi, open [`configs/devices.yaml`](../configs/devices.yaml) in this repository and add an entry for the device.  Use any short, memorable ID (no spaces):

```yaml
- device_id: "frankie-pi"
  enabled: true
  downtime_hours:
    start: 22
    end: 6
  blocked_domains:
    - "youtube.com"
    - "tiktok.com"
  blocked_urls: []
  notes: "Frankie's Pi"
```

Commit and push the change to GitHub before continuing.

## Step 2 — Run the setup script on the Pi

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/gerry421/kids-computer-limiter/main/install/setup.sh)"
```

When prompted, enter the **exact same device ID** you added in Step 1 (e.g. `frankie-pi`).

The script will:

| Step | What happens |
|---|---|
| Install PyYAML | `pip install pyyaml` |
| Clone repo | `/opt/kids-computer-limiter` |
| Save device ID | `/etc/limiter/device_id.conf` |
| Back up hosts | `/etc/hosts.limiter.backup` |
| Install cron job | `*/5 * * * *` as root |
| First run | Limiter runs immediately to verify |

## Step 3 — Verify

```bash
tail -f /var/log/limiter/limiter.log
```

You should see lines like:

```
2026-04-30T22:05:01 | INFO     | limiter.action       | [frankie-pi] [CONFIG_FETCH] success=True
2026-04-30T22:05:01 | INFO     | limiter.action       | [frankie-pi] [HOSTS_UPDATE] 6 domain(s) success=True
```

## Step 4 — Test downtime

Temporarily set `downtime_hours.start` to the current hour in `devices.yaml`, push, wait up to 5 minutes, and the Pi should shut down.  Restore the value afterwards.

## Updating the device ID

Re-run setup:

```bash
sudo bash /opt/kids-computer-limiter/install/setup.sh
```

Or edit the file directly:

```bash
sudo nano /etc/limiter/device_id.conf
```

## Uninstalling

```bash
sudo bash /opt/kids-computer-limiter/install/uninstall.sh
```

The uninstall script will remove the cron job, clear the `/etc/hosts` limiter block, and optionally restore the original hosts file.
