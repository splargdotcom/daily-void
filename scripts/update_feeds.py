#!/usr/bin/env python3

import email.utils
import json
import os
import re
import time
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET

from datetime import datetime, timezone
from pathlib import Path


WEB_ROOT = Path(
    os.environ.get(
        "DAILY_VOID_WEB_ROOT",
        "/var/www/daily-void",
    )
)
OUT = WEB_ROOT / "feeds.json"

USER_AGENT = (
    "DailyVoid/2.1 "
    "(personal RSS dashboard; https://example.com/start/)"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept-Language": "en-GB,en;q=0.9",
    "Cache-Control": "no-cache",
}


FEEDS = {
    "technology": [
        ("Hacker News", "https://hnrss.org/frontpage"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ubuntu", "https://ubuntu.com/blog/feed"),
        ("Arch Linux", "https://archlinux.org/feeds/news/"),
    ],

    "news": [
        ("BBC", "https://feeds.bbci.co.uk/news/rss.xml"),
        ("Guardian", "https://www.theguardian.com/uk/rss"),
        ("Daily Mail", "https://www.dailymail.co.uk/news/index.rss"),
    ],
}


REDDIT_SUBS = [
    "LocalLLaMA",
    "selfhosted",
    "linux",
    "ComfyUI",
    "gamedev",
]

REDDIT_URL = (
    "https://www.reddit.com/r/"
    + "+".join(REDDIT_SUBS)
    + "/.rss?limit=50"
)


def fetch(url, accept="*/*", attempts=3):
    headers = dict(HEADERS)
    headers["Accept"] = accept

    last_error = None

    for attempt in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            headers=headers,
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=20,
            ) as response:
                return response.read()

        except Exception as exc:
            last_error = exc

            if attempt < attempts:
                wait = attempt * 2
                print(
                    f"     retry {attempt}/{attempts - 1} "
                    f"after {type(exc).__name__}"
                )
                time.sleep(wait)

    raise last_error


def text_of(node, *names):
    for name in names:
        element = node.find(name)

        if element is not None and element.text:
            return element.text.strip()

    return ""


def parse_date(value):
    if not value:
        return ""

    try:
        parsed = email.utils.parsedate_to_datetime(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        ).isoformat()

    except Exception:
        pass

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc
            )

        return parsed.astimezone(
            timezone.utc
        ).isoformat()

    except Exception:
        return ""


def parse_xml_feed(source, url):
    raw = fetch(
        url,
        accept=(
            "application/rss+xml,"
            "application/atom+xml,"
            "application/xml,"
            "text/xml,*/*"
        ),
    )

    root = ET.fromstring(raw)

    output = []

    # RSS
    for item in root.findall(".//item"):
        title = text_of(item, "title")
        link = text_of(item, "link")

        published = text_of(
            item,
            "pubDate",
            "published",
            "updated",
        )

        if title and link:
            output.append({
                "title": title,
                "url": link,
                "source": source,
                "published": parse_date(
                    published
                ),
            })

    # Atom
    atom = "{http://www.w3.org/2005/Atom}"

    for entry in root.findall(
        ".//" + atom + "entry"
    ):
        title = text_of(
            entry,
            atom + "title",
        )

        published = text_of(
            entry,
            atom + "published",
            atom + "updated",
        )

        link = ""

        for link_node in entry.findall(
            atom + "link"
        ):
            href = link_node.attrib.get(
                "href",
                "",
            )

            rel = link_node.attrib.get(
                "rel",
                "alternate",
            )

            if href and rel in (
                "alternate",
                "",
            ):
                link = href
                break

        if title and link:
            output.append({
                "title": title,
                "url": link,
                "source": source,
                "published": parse_date(
                    published
                ),
            })

    return output


def reddit_source_from_url(url):
    match = re.search(
        r"/r/([^/]+)/",
        url,
        flags=re.IGNORECASE,
    )

    if match:
        return "r/" + match.group(1)

    return "Reddit"


def fetch_reddit():
    raw = fetch(
        REDDIT_URL,
        accept=(
            "application/atom+xml,"
            "application/rss+xml,"
            "application/xml,"
            "text/xml,*/*"
        ),
    )

    root = ET.fromstring(raw)

    atom = "{http://www.w3.org/2005/Atom}"

    items = []

    for entry in root.findall(
        ".//" + atom + "entry"
    ):
        title = text_of(
            entry,
            atom + "title",
        )

        published = text_of(
            entry,
            atom + "published",
            atom + "updated",
        )

        link = ""

        for link_node in entry.findall(
            atom + "link"
        ):
            href = link_node.attrib.get(
                "href",
                "",
            )

            rel = link_node.attrib.get(
                "rel",
                "alternate",
            )

            if href and rel in (
                "alternate",
                "",
            ):
                link = href
                break

        if not title or not link:
            continue

        items.append({
            "title": title,
            "url": link,
            "source": reddit_source_from_url(
                link
            ),
            "published": parse_date(
                published
            ),
        })

    return items


def load_previous():
    try:
        return json.loads(
            OUT.read_text(
                encoding="utf-8"
            )
        )

    except Exception:
        return {}



def previous_source_items(previous, group, source):
    items = previous.get(group, [])

    return [
        item
        for item in items
        if item.get("source") == source
    ]




SPORT_TITLE_RE = re.compile(
    r"""
    \b(
        football|
        soccer|
        premier\ league|
        champions\ league|
        europa\ league|
        conference\ league|
        fa\ cup|
        carabao\ cup|
        world\ cup|
        fifa|
        uefa|
        rugby|
        cricket|
        tennis|
        wimbledon|
        golf|
        formula\ ?1|
        f1|
        grand\ prix|
        motogp|
        boxing|
        ufc|
        mma|
        athletics|
        olympic(?:s)?|
        paralympic(?:s)?|
        nba|
        nfl|
        mlb|
        nhl
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)

SPORT_URL_PARTS = (
    "/sport/",
    "/sports/",
    "/football/",
    "/soccer/",
    "/rugby/",
    "/cricket/",
    "/tennis/",
    "/golf/",
    "/formula-1/",
    "/formula1/",
    "/f1/",
    "/boxing/",
    "/ufc/",
    "/mma/",
    "/athletics/",
    "/olympics/",
)


def is_sport_story(item):
    title = str(
        item.get("title", "")
    )

    url = str(
        item.get("url", "")
    ).lower()

    if SPORT_TITLE_RE.search(title):
        return True

    return any(
        part in url
        for part in SPORT_URL_PARTS
    )


def main():
    previous = load_previous()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    data = {
        "generated_at": now,
        "technology": [],
        "news": [],
        "reddit": [],
        "errors": {},
    }


    # -------------------------
    # TECHNOLOGY + NEWS
    # -------------------------

    for group, sources in FEEDS.items():
        print()
        print(
            "===",
            group.upper(),
            "===",
        )

        failures = []

        for source, url in sources:
            try:
                items = parse_xml_feed(
                    source,
                    url,
                )

                data[group].extend(
                    items
                )

                print(
                    f"OK   "
                    f"{source:<18} "
                    f"{len(items)} items"
                )

            except Exception as exc:
                message = (
                    f"{source}: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                )

                failures.append(
                    message
                )

                old_items = previous_source_items(
                    previous,
                    group,
                    source,
                )

                if old_items:
                    data[group].extend(
                        old_items
                    )

                    print(
                        f"STALE {source:<16} "
                        f"keeping {len(old_items)} "
                        f"previous items"
                    )

                else:
                    print(
                        "FAIL",
                        message,
                    )

            time.sleep(0.25)

        if group == "news":
            before = len(data[group])

            data[group] = [
                item
                for item in data[group]
                if not is_sport_story(item)
            ]

            removed = before - len(data[group])

            print(
                f"FILTER Sport stories removed: {removed}"
            )

        data[group].sort(
            key=lambda item:
                item.get("published")
                or "",
            reverse=True,
        )

        data[group] = (
            data[group][:40]
        )

        if failures:
            data["errors"][group] = (
                failures
            )


    # -------------------------
    # REDDIT
    # -------------------------

    print()
    print("=== REDDIT ===")

    try:
        reddit_items = fetch_reddit()

        reddit_items.sort(
            key=lambda item:
                item.get("published")
                or "",
            reverse=True,
        )

        data["reddit"] = (
            reddit_items[:40]
        )

        print(
            "OK   Combined Reddit RSS "
            f"({len(reddit_items)} items)"
        )

        counts = {}

        for item in reddit_items:
            source = item["source"]

            counts[source] = (
                counts.get(source, 0)
                + 1
            )

        for source in sorted(counts):
            print(
                f"     {source:<18} "
                f"{counts[source]} items"
            )

    except Exception as exc:
        message = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print(
            "FAIL Combined Reddit RSS:",
            message,
        )

        # Do not destroy a working Reddit
        # card just because one refresh fails.
        old_items = previous.get(
            "reddit",
            [],
        )

        if old_items:
            data["reddit"] = old_items

            print(
                "KEEP Previous Reddit data:",
                len(old_items),
                "items",
            )

        data["errors"]["reddit"] = [
            message
        ]


    # -------------------------
    # WRITE ATOMICALLY
    # -------------------------

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    tmp = OUT.with_suffix(
        ".json.tmp"
    )

    tmp.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    tmp.replace(OUT)

    print()
    print("=== RESULT ===")

    print(
        "Technology:",
        len(data["technology"]),
    )

    print(
        "News:      ",
        len(data["news"]),
    )

    print(
        "Reddit:    ",
        len(data["reddit"]),
    )

    print()
    print(
        "Wrote",
        OUT,
    )


if __name__ == "__main__":
    main()
