#!/usr/bin/env python3

import html
import json
import re
import urllib.request

from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo


BASE = "https://music.example.com"
OUTPUT = Path(
    "/var/www/daily-void-private/maloja.json"
)

TZ = ZoneInfo("Europe/London")

HEADERS = {
    "User-Agent":
        "DailyVoid-Maloja/1.0",
    "Accept":
        "text/html,application/xhtml+xml",
}


def fetch(path):
    url = urljoin(
        BASE,
        path
    )

    request = urllib.request.Request(
        url,
        headers=HEADERS,
    )

    with urllib.request.urlopen(
        request,
        timeout=10,
    ) as response:
        return response.read().decode(
            "utf-8",
            errors="replace",
        )


def clean_text(value):
    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    value = html.unescape(
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def attrs_from_tag(value):
    attrs = {}

    for match in re.finditer(
        r'''([\w:-]+)\s*=\s*
            (["'])
            (.*?)
            \2
        ''',
        value,
        flags=re.X | re.S,
    ):
        attrs[
            match.group(1).lower()
        ] = html.unescape(
            match.group(3)
        )

    return attrs


def find_link(body, entity):
    match = re.search(
        rf'''href=
            (["'])
            (
                /{re.escape(entity)}
                \?
                .*?
            )
            \1
        ''',
        body,
        flags=re.X | re.S | re.I,
    )

    if not match:
        return BASE + "/"

    path = re.sub(
        r"\s+",
        "",
        html.unescape(
            match.group(2)
        ),
    )

    return urljoin(
        BASE,
        path,
    )


def parse_rows(page, entity):
    rows = []

    pattern = re.compile(
        r"<tr\b(?P<attrs>[^>]*)>"
        r"(?P<body>.*?)"
        r"</tr>",
        flags=re.I | re.S,
    )

    for match in pattern.finditer(
        page
    ):
        attrs = attrs_from_tag(
            match.group("attrs")
        )

        classes = (
            attrs.get(
                "class",
                "",
            )
            .lower()
            .split()
        )

        if "listrow" not in classes:
            continue

        if (
            attrs.get(
                "data-entity_type"
            )
            != entity
        ):
            continue

        body = match.group(
            "body"
        )

        name = html.unescape(
            attrs.get(
                "data-entity_name",
                "",
            )
        ).strip()

        amount_match = re.search(
            r'''<td\b
                [^>]*
                class=(["'])amount\1
                [^>]*
                >
                .*?
                <a\b[^>]*>
                \s*([\d,]+)\s*
                </a>
            ''',
            body,
            flags=re.I | re.S | re.X,
        )

        amount = 0

        if amount_match:
            amount = int(
                amount_match
                .group(2)
                .replace(",", "")
            )

        image_match = re.search(
            r'''data-bg=
                (["'])
                (.*?)
                \1
            ''',
            body,
            flags=re.I | re.S | re.X,
        )

        art = None

        if image_match:
            art = urljoin(
                BASE,
                html.unescape(
                    image_match.group(2)
                ),
            )

        artist = None

        if entity in {
            "track",
            "album",
        }:
            artist_match = re.search(
                rf'''<span\b
                    [^>]*
                    class=
                    (["'])
                    artist_in_{entity}column
                    \1
                    [^>]*
                    >
                    (.*?)
                    </span>
                ''',
                body,
                flags=re.I | re.S | re.X,
            )

            if artist_match:
                artist = clean_text(
                    artist_match.group(2)
                )

        rows.append({
            "id":
                attrs.get(
                    "data-entity_id"
                ),

            "name":
                name,

            "artist":
                artist,

            "count":
                amount,

            "art":
                art,

            "link":
                find_link(
                    body,
                    entity,
                ),
        })

    return rows


def scrobble_count(page):
    match = re.search(
        r'''<p\b
            [^>]*
            class=
            (["'])
            stats
            \1
            [^>]*
            >
            \s*
            ([\d,]+)
            \s+
            Scrobbles
        ''',
        page,
        flags=re.I | re.X,
    )

    if not match:
        return 0

    return int(
        match.group(2)
        .replace(",", "")
    )


def main():
    now = datetime.now(TZ)

    iso = now.date().isocalendar()

    period = (
        f"{iso.year}/W"
        f"{iso.week:02d}"
    )

    print(
        "Maloja period:",
        period,
    )

    scrobbles_html = fetch(
        f"/scrobbles?in={period}"
    )

    artists_html = fetch(
        f"/charts_artists?in={period}"
    )

    tracks_html = fetch(
        f"/charts_tracks?in={period}"
    )

    albums_html = fetch(
        f"/charts_albums?in={period}"
    )

    artists = parse_rows(
        artists_html,
        "artist",
    )

    tracks = parse_rows(
        tracks_html,
        "track",
    )

    albums = parse_rows(
        albums_html,
        "album",
    )

    total = scrobble_count(
        scrobbles_html
    )

    output = {
        "generated_at":
            now.isoformat(),

        "period":
            period,

        "week":
            iso.week,

        "year":
            iso.year,

        "scrobbles":
            total,

        "top_artist":
            artists[0]
            if artists
            else None,

        "top_track":
            tracks[0]
            if tracks
            else None,

        "top_album":
            albums[0]
            if albums
            else None,

        "albums":
            albums[:6],
    }

    temp = OUTPUT.with_suffix(
        ".json.tmp"
    )

    temp.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    temp.replace(
        OUTPUT
    )

    OUTPUT.chmod(
        0o644
    )

    print(
        "Scrobbles:",
        total,
    )

    if artists:
        print(
            "Top artist:",
            artists[0]["name"],
            artists[0]["count"],
        )

    if tracks:
        print(
            "Top track:",
            tracks[0]["name"],
            tracks[0]["count"],
        )

    if albums:
        print(
            "Top album:",
            albums[0]["name"],
            albums[0]["count"],
        )

    print(
        "Wrote:",
        OUTPUT,
    )


if __name__ == "__main__":
    main()
