#!/usr/bin/env python3

import json
import os
import urllib.request

from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from icalendar import Calendar
import recurring_ical_events


TZ_NAME = os.environ.get("DAILY_VOID_TIMEZONE", "Europe/London")
TZ = ZoneInfo(TZ_NAME)

ENV_FILE = Path(
    os.environ.get(
        "DAILY_VOID_CALENDAR_ENV",
        str(Path.home() / ".config/daily-void/calendar.env"),
    )
)

WEB_ROOT = Path(
    os.environ.get(
        "DAILY_VOID_WEB_ROOT",
        "/var/www/daily-void",
    )
)

OUT = WEB_ROOT / "calendar.json"

DAYS_AHEAD = 21


def load_urls():
    urls = []

    for raw in ENV_FILE.read_text(
        encoding="utf-8"
    ).splitlines():

        raw = raw.strip()

        if (
            not raw
            or raw.startswith("#")
            or "=" not in raw
        ):
            continue

        key, value = raw.split("=", 1)

        if (
            (
                key.startswith("CALENDAR_ICS_URL")
                or key.startswith("CALENDAR_ICAL_URL")
            )
            and value.strip()
        ):
            urls.append(value.strip())

    if not urls:
        raise RuntimeError(
            "No CALENDAR_ICS_URL / CALENDAR_ICAL_URL found."
        )

    return urls


def fetch_calendar(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "DailyVoid-Private/1.0"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=30
    ) as response:
        return response.read()


def local_datetime(value):
    if isinstance(value, datetime):

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=TZ
            )

        return value.astimezone(TZ)

    if isinstance(value, date):
        return datetime.combine(
            value,
            time.min,
            tzinfo=TZ
        )

    raise TypeError(
        f"Unsupported calendar date: {value!r}"
    )


def event_end(event, start, all_day):
    if "DTEND" in event:
        return local_datetime(
            event.decoded("DTEND")
        )

    if "DURATION" in event:
        try:
            return start + event.decoded(
                "DURATION"
            )
        except Exception:
            pass

    if all_day:
        return start + timedelta(days=1)

    return start


def main():
    urls = load_urls()

    now = datetime.now(TZ)

    range_start = datetime.combine(
        now.date(),
        time.min,
        tzinfo=TZ
    )

    range_end = (
        range_start
        + timedelta(days=DAYS_AHEAD)
    )

    events = []
    seen = set()

    for index, url in enumerate(
        urls,
        start=1
    ):
        raw = fetch_calendar(url)

        calendar = Calendar.from_ical(
            raw
        )

        calendar_name = str(
            calendar.get(
                "X-WR-CALNAME",
                f"Calendar {index}"
            )
        )

        expanded = (
            recurring_ical_events
            .of(calendar)
            .between(
                range_start,
                range_end
            )
        )

        for event in expanded:

            if str(
                event.get(
                    "STATUS",
                    ""
                )
            ).upper() == "CANCELLED":
                continue

            if "DTSTART" not in event:
                continue

            raw_start = event.decoded(
                "DTSTART"
            )

            all_day = (
                isinstance(raw_start, date)
                and not isinstance(
                    raw_start,
                    datetime
                )
            )

            start = local_datetime(
                raw_start
            )

            end = event_end(
                event,
                start,
                all_day
            )

            # Hide events that have already ended.
            if end < now:
                continue

            title = str(
                event.get(
                    "SUMMARY",
                    "Untitled event"
                )
            ).strip()

            uid = str(
                event.get(
                    "UID",
                    ""
                )
            )

            unique = (
                uid,
                start.isoformat(),
                title
            )

            if unique in seen:
                continue

            seen.add(unique)

            events.append({
                "title": title,
                "start": (
                    start.date().isoformat()
                    if all_day
                    else start.isoformat()
                ),
                "end": (
                    end.date().isoformat()
                    if all_day
                    else end.isoformat()
                ),
                "all_day": all_day,
                "calendar": calendar_name,
            })

    events.sort(
        key=lambda event:
            (
                event["start"],
                event["title"].lower()
            )
    )

    payload = {
        "generated_at":
            now.isoformat(),
        "timezone":
            TZ_NAME,
        "range_days":
            DAYS_AHEAD,
        "events":
            events,
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    tmp = OUT.with_suffix(
        ".json.tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    tmp.replace(OUT)

    print(
        f"Wrote {OUT}"
    )

    print(
        f"Upcoming events: "
        f"{len(events)}"
    )


if __name__ == "__main__":
    main()
