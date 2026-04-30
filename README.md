# Kids Computer Limiter

A lightweight parental control system for Raspberry Pi. It runs as a cron job every 5 minutes, fetches restrictions from this GitHub repository, and enforces them immediately — no restart required.

## Features

- **Domain blocking** — redirects blocked sites to `127.0.0.1` via a clean, removable block in `/etc/hosts`
- **Downtime enforcement** — shuts the computer down immediately if it is used outside allowed hours
- **Zero-touch updates** — edit `configs/devices.yaml` on GitHub and the Pi picks up changes on its next 5-minute cycle
- **Local + remote logging** — every action logged locally on the Pi; logs committed to this repo every 2 hours
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
```

## Removing the limiter

```bash
sudo bash /opt/kids-computer-limiter/install/uninstall.sh
```

## Documentation

| File | Contents |
|---|---|
| [docs/SETUP.md](docs/SETUP.md) | Full step-by-step install guide |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Config file reference & examples |
