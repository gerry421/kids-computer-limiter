# Configuration Reference

The single master config file is [`configs/devices.yaml`](../configs/devices.yaml).  
Edit it directly on GitHub — the Pi applies changes on its next 5-minute cron run.

---

## File structure

```yaml
global:
  update_interval: 300

devices:
  - device_id: "frankie-pi"
    enabled: true
    downtime_hours:
      start: 22
      end: 6
    blocked_domains:
      - "youtube.com"
    blocked_urls: []
    notes: "Optional admin note"
```

---

## `global` section

| Key | Type | Default | Description |
|---|---|---|---|
| `update_interval` | integer | `300` | Cron interval in seconds (informational only — actual cron schedule is set during install) |
| `grace_period_before_shutdown` | integer | `0` | Reserved for future use |

---

## `devices` array — per-device keys

### `device_id` (string, required)

Must exactly match the value stored in `/etc/limiter/device_id.conf` on the Pi.  
Case-sensitive.  No spaces — use hyphens.

```yaml
device_id: "frankie-pi"
```

### `enabled` (boolean, default `true`)

Set to `false` to temporarily disable all restrictions for a device without deleting the entry.  The Pi will clear the hosts block and stop enforcing downtime.

```yaml
enabled: false
```

### `downtime_hours` (object)

Defines the hours during which the computer will **shut down immediately** if the cron job runs.

```yaml
downtime_hours:
  start: 22   # 10:00 p.m. (24-hour)
  end: 6      # 6:00 a.m.
```

- Supports crossing midnight (`start > end`)
- Omit or leave empty (`{}`) to disable downtime enforcement
- The shutdown is triggered on every cron run during the window — the computer cannot be used until the window ends

**Examples:**

| Goal | Config |
|---|---|
| 10 p.m. – 6 a.m. (crosses midnight) | `start: 22, end: 6` |
| 11 p.m. – 7 a.m. | `start: 23, end: 7` |
| No downtime | omit the key entirely |

### `blocked_domains` (list of strings)

Domains to redirect to `127.0.0.1` in `/etc/hosts`.  
The `www.` subdomain is **automatically added** for each entry.

```yaml
blocked_domains:
  - "youtube.com"       # also blocks www.youtube.com
  - "tiktok.com"
  - "discord.com"
  - "reddit.com"
  - "twitch.tv"
```

- Use bare domain names (no `http://`, no trailing slash)
- Domain matching is exact — to block a subdomain, list it explicitly
- Removing a domain from this list unblocks it on the next run

### `blocked_urls` (list of strings)

Reserved for future use. URL-path-level blocking requires a local proxy and is not yet implemented.  Leave as an empty list.

```yaml
blocked_urls: []
```

### `notes` (string, optional)

Free-text admin comment.  Not used by the limiter — just for your reference.

```yaml
notes: "Frankie's Pi — strict mode"
```

---

## Adding a new device

1. Add a new entry under `devices:` in `configs/devices.yaml`
2. Commit and push
3. Run `sudo bash install/setup.sh` on the new Pi and enter the matching `device_id`

## Disabling a device temporarily

Change `enabled: true` to `enabled: false` for that device and push.  The Pi will clear all restrictions on its next run.

## Emergency: removing all blocks manually

On the Pi:

```bash
sudo python3 -c "
import sys; sys.path.insert(0, '/opt/kids-computer-limiter')
from limiter.enforcer import clear_hosts_block
clear_hosts_block()
"
```

Or simply delete everything between (and including) the delimiters in `/etc/hosts`:

```
# === BEGIN LIMITER BLOCK ===
...
# === END LIMITER BLOCK ===
```
