# The Daily Void

A self-hosted start page for news, weather, services, personal admin,
music statistics and other temporary disturbances.

The Daily Void uses a static HTML/CSS/JavaScript frontend backed by small
Python updater scripts which periodically generate JSON files.

## Features

- Technology and news feeds
- Reddit feed aggregation
- Weather
- Service health monitoring
- Machine telemetry
- AMD ROCm and NVIDIA GPU statistics
- Google Calendar agenda
- Gmail-derived Life Admin reminders
- Maloja weekly listening statistics and artwork
- Daily Brief
- Local read-state for feed items
- Configurable launchers
- Compact dark dashboard UI

## Architecture

The frontend lives in web/.

Updater scripts live in scripts/ and can generate files including:

- feeds.json
- weather.json
- status.json
- calendar.json
- life_admin.json
- machine_stats.json
- maloja.json

Serve web/ using Apache, nginx, Caddy, or another static web server.

## Basic setup

Copy:

    web/config.example.json

to:

    web/config.json

Then edit web/config.json for your own links, cards and services.

## Calendar

The optional calendar updater uses a private iCalendar URL.

Use examples/calendar.env.example as a template.

Never commit your real calendar URL.

## Gmail / Life Admin

The Life Admin integration uses read-only Gmail OAuth.

OAuth client credentials and tokens should live outside the web root.
Do not expose Gmail evidence files through your web server.

## Machine telemetry

Machine statistics can be collected locally and optionally from another
machine over SSH.

AMD GPU telemetry uses rocm-smi.

NVIDIA telemetry uses nvidia-smi.

## Maloja

The optional Maloja integration reads weekly chart information from a
self-hosted Maloja instance and creates a compact dashboard summary.

## Privacy

Do not publish:

- OAuth credentials or tokens
- private calendar URLs
- generated Gmail evidence
- live personal calendar data
- private hostnames or addresses
- live private configuration

The included .gitignore excludes common private/runtime files.

If a dashboard contains personal information, protect it with appropriate
authentication rather than serving it publicly.

## License

MIT

## Weather location

The weather updater accepts its location through environment variables:

    WEATHER_LAT
    WEATHER_LON
    WEATHER_TIMEZONE

See `examples/weather.env.example`.

The example values are generic and should be replaced with your own location.
