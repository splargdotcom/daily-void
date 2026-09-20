# The Daily Void

A self-hosted start page for news, weather, services, personal admin,
music statistics and other temporary disturbances.

The Daily Void is a static HTML/CSS/JavaScript dashboard backed by small
Python updater scripts. The scripts write JSON into the web root and the
browser renders it.

## Features

- Technology and news feeds
- Reddit feed aggregation
- Weather
- Service health monitoring
- Local and remote machine telemetry
- AMD ROCm and NVIDIA GPU statistics
- Google Calendar agenda
- Gmail-derived Life Admin reminders
- Maloja weekly listening statistics and artwork
- Daily Brief
- Local read-state for feed items
- Configurable launchers
- Compact dark dashboard UI

## Layout

```text
web/          static dashboard
scripts/      JSON updater scripts
examples/     example environment/config files
```

The updaters generate files such as:

```text
feeds.json
weather.json
status.json
calendar.json
life_admin.json
machine_stats.json
maloja.json
```

## Quick start

Clone the repository, create a virtual environment, and install the optional
Python dependencies:

```bash
git clone https://github.com/splargdotcom/daily-void.git
cd daily-void

python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt

cp web/config.example.json web/config.json
```

Serve `web/` with Apache, nginx, Caddy, or any other static web server.

The scripts default to writing JSON to:

```text
/var/www/daily-void
```

Override that without editing source:

```bash
export DAILY_VOID_WEB_ROOT=/path/to/your/web/root
export DAILY_VOID_TIMEZONE=Europe/London
```

## Weather

Configure the weather updater with environment variables:

```bash
export WEATHER_LAT=51.5074
export WEATHER_LON=-0.1278
export WEATHER_PLACE="Your City"
export WEATHER_TIMEZONE=Europe/London
```

See `examples/weather.env.example`.

Weather data comes from Open-Meteo.

## Calendar

The calendar updater reads one or more private iCalendar feeds from an
environment file.

By default it looks for:

```text
~/.config/daily-void/calendar.env
```

You can override that location:

```bash
export DAILY_VOID_CALENDAR_ENV=/path/to/calendar.env
```

See `examples/calendar.env.example`.

Never commit a real private calendar URL.

## Gmail / Life Admin

Life Admin scans Gmail using read-only OAuth and extracts dated items such as
payments, renewals, expiries, refunds, and cancellations.

The default token location is:

```text
~/.config/daily-void/gmail-token.json
```

Override it with:

```bash
export GMAIL_TOKEN_FILE=/path/to/gmail-token.json
```

Private message evidence is stored outside the web root. You can change that
location with `DAILY_VOID_DATA_DIR`.

Do not expose OAuth credentials, tokens, or Gmail evidence through your web
server.

## Service monitoring

`update_status.py` includes a generic default service list, or you can point it
at your own JSON service definition:

```bash
export DAILY_VOID_STATUS_CONFIG=/path/to/status-services.json
```

See `examples/status-services.example.json`.

Supported checks include HTTP, TCP, and the optional BugCam health format.

## Machine telemetry

`update_machine_stats.py` collects CPU, load, RAM, disk, uptime, and optional
GPU telemetry.

The local machine is collected directly. A second machine can be queried over
SSH:

```bash
export REMOTE_STATS_HOST=server2
```

The SSH connection should already work non-interactively.

GPU support is optional:

- AMD: `rocm-smi`
- NVIDIA: `nvidia-smi`

Systems without one of those tools can still use the rest of the telemetry.

## Maloja

The optional Maloja updater reads weekly listening charts from a self-hosted
Maloja instance:

```bash
export MALOJA_URL=https://music.example.com
```

It produces weekly scrobble totals, top artist/track/album information, and
album artwork links.

## Scheduling

The updater scripts are designed to be run periodically using cron, systemd
timers, or another scheduler.

For example:

```cron
*/30 * * * * /path/to/.venv/bin/python /path/to/scripts/update_feeds.py
*/30 * * * * /path/to/.venv/bin/python /path/to/scripts/update_weather.py
*/2  * * * * /path/to/.venv/bin/python /path/to/scripts/update_status.py
```

Add the optional calendar, Life Admin, Maloja, and machine-stat scripts at the
cadence that makes sense for your setup.

## Privacy

Do not publish:

- OAuth credentials or tokens
- private calendar URLs
- generated Gmail evidence
- live personal calendar data
- private hostnames or addresses
- live private configuration

The included `.gitignore` excludes the common private/runtime files used by
the project.

If your dashboard contains personal information, protect it with appropriate
authentication rather than serving it publicly.

## License

MIT
