# Kids Computer Limiter

A lightweight parental control system for Raspberry Pi. It runs as a cron job every 5 minutes, fetches restrictions from this GitHub repository, and enforces them immediately — no restart required.

## Features

- **Domain blocking** — redirects blocked sites to `127.0.0.1` via a clean, removable block in `/etc/hosts`
- **Downtime enforcement** — shuts the computer down immediately if it is used outside allowed hours
- **Zero-touch updates** — edit `configs/devices.yaml` on GitHub and the Pi picks up changes on its next 5-minute cycle
- **Local + remote logging** — every action logged locally on the Pi; logs committed to this repo every 2 hours
- **Local website history** — records visited domains from Chromium, Chrome and Firefox history on each Pi
- **Graceful degradation** — if GitHub is unreachable the Pi keeps running with the last known config

## Quick start (on the Pi)

```bash
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/gerry421/kids-computer-limiter/main/install/setup.sh)"
```

The setup script will:
1. Prompt you for a **device ID** (e.g. `frankie-pi`)
2. Clone this repo to `/opt/kids-computer-limiter`
3. Install the cron job (runs every 5 minutes as root)
4. Run the limiter once immediately

## Managing restrictions

Edit [`configs/devices.yaml`](configs/devices.yaml) directly on GitHub. Changes are applied on the Pi within 5 minutes.

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for full reference.

## Monitoring

```bash
# Live log on the Pi
tail -f /var/log/limiter/limiter.log

# Remote logs (committed here every 2 hours)
cat logs/execution_log.txt

# Local website history on the Pi (UTC timestamp, domain, browser profile)
cd /opt/kids-computer-limiter
sudo python3 -m limiter.history
```

Website history is kept only on the Pi in `/var/log/limiter/website_visits.sqlite3`,
readable by root. It is not uploaded. The log includes existing saved browser
history on the first run, and checks all local users' standard browser profiles
every five minutes, even if the device is disabled or GitHub is unreachable.
It stores domains, not full URLs or search terms. Private browsing, unsupported
browsers and activity outside the browser are not captured. Visits deleted from
browser history before a check-in may be missed; deleting browser history later
does not delete previously collected entries from the local log.

## Removing the limiter

```bash
sudo bash /opt/kids-computer-limiter/install/uninstall.sh
```

## Documentation

| File | Contents |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | Full step-by-step install guide |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Config file reference & examples |
