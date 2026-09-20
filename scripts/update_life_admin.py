#!/usr/bin/env python3

import base64
import html
import json
import re

from datetime import datetime, timedelta
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil import parser as dateparser

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


# ============================================================
# CONFIG
# ============================================================

TZ = ZoneInfo("Europe/London")

TOKEN = (
    Path.home()
    / ".config/daily-void/gmail-token.json"
)

LOCAL_DIR = (
    Path.home()
    / ".local/share/daily-void"
)

EVIDENCE_OUT = (
    LOCAL_DIR
    / "gmail-evidence.json"
)

PUBLIC_OUT = Path(
    "/var/www/daily-void-private/life_admin.json"
)

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]

MAX_MESSAGES = 400


SEARCHES = [
    (
        "renewals",
        'newer_than:365d '
        '{'
        'subject:renewal '
        'subject:renews '
        'subject:renewing '
        'subject:expires '
        'subject:expiry '
        '"renews on" '
        '"will renew" '
        '"automatically renew" '
        '"auto-renew" '
        '"trial ends" '
        '"trial expires"'
        '}'
    ),
    (
        "payments",
        'newer_than:180d '
        '{'
        '"payment received" '
        '"payment successful" '
        '"payment confirmed" '
        '"thank you for your payment" '
        '"payment due" '
        '"amount due" '
        '"bill is due" '
        '"direct debit" '
        '"will be taken" '
        '"will be collected" '
        '"we will collect"'
        '}'
    ),
    (
        "refunds_cancellations",
        'newer_than:180d '
        '{'
        '"refund processed" '
        '"refund issued" '
        '"you have been refunded" '
        '"subscription cancelled" '
        '"subscription canceled" '
        '"cancellation confirmed" '
        '"membership cancelled" '
        '"membership canceled"'
        '}'
    ),
]


# ============================================================
# CLASSIFICATION RULES
# ============================================================

RULES = [
    (
        "REFUNDED",
        [
            r"\brefund (?:has been |was )?(?:processed|issued|completed)\b",
            r"\byou (?:have been|were) refunded\b",
            r"\bwe(?:'ve| have) refunded\b",
            r"\brefund confirmation\b",
        ],
    ),
    (
        "CANCELLED",
        [
            r"\bsubscription (?:has been |was )?cancel+ed\b",
            r"\bmembership (?:has been |was )?cancel+ed\b",
            r"\bcancellation (?:is |has been )?confirmed\b",
            r"\byour cancellation is complete\b",
        ],
    ),
    (
        "PAID",
        [
            r"\bpayment (?:has been |was )?received\b",
            r"\bpayment (?:was |is )?successful\b",
            r"\bpayment confirmed\b",
            r"\bthank you for your payment\b",
            r"\bwe(?:'ve| have) received your payment\b",
            r"\byour payment has been processed\b",
        ],
    ),
    (
        "RENEWS",
        [
            r"\bsubscription (?:will )?renew(?:s)?\b",
            r"\bmembership (?:will )?renew(?:s)?\b",
            r"\brenews? on\b",
            r"\brenewal date\b",
            r"\bwill automatically renew\b",
            r"\bautomatically renew(?:s)?\b",
            r"\bauto[- ]?renew(?:al|s)?\b",
        ],
    ),
    (
        "EXPIRES",
        [
            r"\bexpires? on\b",
            r"\bwill expire\b",
            r"\bexpiration date\b",
            r"\bexpiry date\b",
            r"\btrial ends? on\b",
            r"\btrial expires?\b",
        ],
    ),
    (
        "DUE",
        [
            r"\bpayment (?:is )?due\b",
            r"\bamount due\b",
            r"\bbill (?:is )?due\b",
            r"\bdue on\b",
            r"\bdirect debit (?:will be|is being) (?:taken|collected)\b",
            r"\bpayment will be (?:taken|collected)\b",
            r"\bwe(?:'ll| will) (?:take|collect) (?:your )?payment\b",
        ],
    ),
]


MONTHS = (
    "Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|"
    "May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    "Sep(?:t(?:ember)?)?|Oct(?:ober)?|"
    "Nov(?:ember)?|Dec(?:ember)?"
)

DATE_PATTERNS = [
    re.compile(
        rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})"
        rf"(?:\s+20\d{{2}})?\b",
        re.I,
    ),
    re.compile(
        rf"\b(?:{MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?"
        rf"(?:,\s*20\d{{2}})?\b",
        re.I,
    ),
    re.compile(
        r"\b\d{1,2}[/-]\d{1,2}[/-]20\d{2}\b"
    ),
]


AMOUNT_RE = re.compile(
    r"(?P<currency>£|\$|€)\s*"
    r"(?P<amount>\d{1,6}(?:,\d{3})*(?:\.\d{2})?)"
)


# ============================================================
# GMAIL
# ============================================================

def gmail():
    creds = Credentials.from_authorized_user_file(
        TOKEN,
        SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())

        TOKEN.write_text(
            creds.to_json(),
            encoding="utf-8",
        )

        TOKEN.chmod(0o600)

    return build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False,
    )


def search_ids(service, query):
    found = []
    page_token = None

    while len(found) < MAX_MESSAGES:
        result = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=min(
                    100,
                    MAX_MESSAGES - len(found)
                ),
                pageToken=page_token,
            )
            .execute()
        )

        found.extend(
            item["id"]
            for item in result.get(
                "messages",
                []
            )
        )

        page_token = result.get(
            "nextPageToken"
        )

        if not page_token:
            break

    return found[:MAX_MESSAGES]


def header(message, name):
    wanted = name.lower()

    for item in (
        message
        .get("payload", {})
        .get("headers", [])
    ):
        if item.get(
            "name",
            ""
        ).lower() == wanted:
            return item.get(
                "value",
                ""
            )

    return ""


def decode_data(value):
    if not value:
        return ""

    try:
        padding = (
            "=" * (-len(value) % 4)
        )

        raw = base64.urlsafe_b64decode(
            value + padding
        )

        return raw.decode(
            "utf-8",
            errors="replace",
        )

    except Exception:
        return ""


def body_parts(part):
    plain = []
    html_parts = []

    mime = part.get(
        "mimeType",
        ""
    ).lower()

    filename = part.get(
        "filename",
        ""
    )

    # Do not inspect attachment contents.
    if filename:
        return plain, html_parts

    data = (
        part
        .get("body", {})
        .get("data")
    )

    if data:
        text = decode_data(data)

        if mime == "text/plain":
            plain.append(text)

        elif mime == "text/html":
            html_parts.append(text)

    for child in part.get(
        "parts",
        []
    ):
        p, h = body_parts(child)

        plain.extend(p)
        html_parts.extend(h)

    return plain, html_parts


def html_to_text(value):
    value = re.sub(
        r"(?is)<(script|style).*?>.*?</\1>",
        " ",
        value,
    )

    value = re.sub(
        r"(?s)<[^>]+>",
        " ",
        value,
    )

    value = html.unescape(value)

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def message_text(message):
    payload = message.get(
        "payload",
        {}
    )

    plain, html_parts = body_parts(
        payload
    )

    if plain:
        result = "\n".join(plain)

    else:
        result = html_to_text(
            "\n".join(html_parts)
        )

    return result[:60000]


# ============================================================
# EXTRACTION
# ============================================================

def message_datetime(message):
    raw = header(
        message,
        "Date"
    )

    try:
        value = parsedate_to_datetime(raw)

        if value.tzinfo is None:
            value = value.replace(
                tzinfo=TZ
            )

        return value.astimezone(TZ)

    except Exception:
        millis = int(
            message.get(
                "internalDate",
                "0"
            )
        )

        return datetime.fromtimestamp(
            millis / 1000,
            tz=TZ,
        )


def merchant_from_sender(value):
    name, address = parseaddr(
        value
    )

    name = re.sub(
        r"\s+",
        " ",
        name,
    ).strip(
        ' "\''
    )

    if name:
        # Remove common noise.
        name = re.sub(
            r"\b(no[- ]?reply|support|billing|payments?)\b",
            "",
            name,
            flags=re.I,
        )

        name = re.sub(
            r"\s+",
            " ",
            name,
        ).strip(" -|")

        if name:
            return name[:60]

    if "@" in address:
        domain = address.split(
            "@",
            1
        )[1].lower()

        domain = domain.removeprefix(
            "mail."
        )

        pieces = domain.split(".")

        if len(pieces) >= 2:
            return pieces[-2].replace(
                "-",
                " "
            ).title()

    return "Unknown"



def clean_forward_subject(subject):
    value = subject.strip()

    while True:
        cleaned = re.sub(
            r"^\s*(?:fw|fwd|re)\s*:\s*",
            "",
            value,
            flags=re.I,
        )

        if cleaned == value:
            break

        value = cleaned

    return value.strip()


def original_forward_sender(body):
    # Normal plain-text forwarded-message header.
    match = re.search(
        r"(?im)^\s*From:\s*(.+?)\s*$",
        body,
    )

    if match:
        value = match.group(1).strip()

        if "@" in value:
            return value

    # Some HTML-derived forwards lose their line breaks.
    match = re.search(
        r"\bFrom:\s*"
        r"([^<\n]{1,100}<[^>\n]+>)",
        body,
        flags=re.I,
    )

    if match:
        return match.group(1).strip()

    return None


def merchant_from_message(
    subject,
    sender,
    body,
):
    clean_subject = clean_forward_subject(
        subject
    )

    # ------------------------------------------
    # Strong subject-derived identities.
    # ------------------------------------------

    match = re.search(
        r"\bpayment to\s+(.+?)"
        r"(?:[.!]|$)",
        clean_subject,
        flags=re.I,
    )

    if match:
        merchant = match.group(1).strip(
            " -|:."
        )

        if merchant:
            return merchant[:60]


    match = re.search(
        r"\byour\s+(.{2,50}?)\s+bill\b",
        clean_subject,
        flags=re.I,
    )

    if match:
        merchant = match.group(1).strip(
            " -|:."
        )

        # Don't accept generic phrases such as
        # "your latest bill".
        if merchant.lower() not in {
            "latest",
            "monthly",
            "new",
            "next",
        }:
            return merchant[:60]


    # A forwarded Love2shop voucher is obviously
    # about Love2shop, not the person forwarding it.
    if re.search(
        r"\blove2shop\b",
        clean_subject,
        flags=re.I,
    ):
        return "Love2shop"


    # ------------------------------------------
    # For forwarded messages, prefer the
    # original sender embedded in the body.
    # ------------------------------------------

    if re.match(
        r"^\s*(?:fw|fwd)\s*:",
        subject,
        flags=re.I,
    ):
        original = original_forward_sender(
            body
        )

        if original:
            merchant = merchant_from_sender(
                original
            )

            if merchant != "Unknown":
                return merchant


    # Otherwise the actual Gmail sender is best.
    return merchant_from_sender(
        sender
    )


def classify(text):
    lowered = text.lower()

    for status, patterns in RULES:
        for pattern in patterns:
            match = re.search(
                pattern,
                lowered,
                flags=re.I,
            )

            if match:
                return (
                    status,
                    match.group(0),
                )

    return None, None


def extract_amount(text):
    match = AMOUNT_RE.search(
        text
    )

    if not match:
        return None, None

    currency_symbol = match.group(
        "currency"
    )

    currency = {
        "£": "GBP",
        "$": "USD",
        "€": "EUR",
    }.get(
        currency_symbol
    )

    value = (
        match.group("amount")
        .replace(",", "")
    )

    try:
        return float(value), currency

    except ValueError:
        return None, None


def candidate_dates(text, reference):
    found = []

    for pattern in DATE_PATTERNS:
        for match in pattern.finditer(text):
            raw = match.group(0)

            raw = re.sub(
                r"(\d)(st|nd|rd|th)\b",
                r"\1",
                raw,
                flags=re.I,
            )

            try:
                parsed = dateparser.parse(
                    raw,
                    dayfirst=True,
                    fuzzy=False,
                    default=reference.replace(
                        month=1,
                        day=1,
                    ).replace(
                        tzinfo=None
                    ),
                )

            except Exception:
                continue

            candidate = parsed.date()

            # "4 January" in a December notice
            # almost certainly means next year.
            if (
                not re.search(
                    r"\b20\d{2}\b",
                    raw
                )
                and candidate
                < (
                    reference.date()
                    - timedelta(days=45)
                )
            ):
                try:
                    candidate = (
                        candidate.replace(
                            year=candidate.year + 1
                        )
                    )
                except ValueError:
                    pass

            found.append(
                candidate
            )

    return sorted(set(found))



def relevant_dates(
    subject,
    body,
    matched_phrase,
    reference,
):
    # An explicit date in the subject is extremely
    # strong evidence:
    #
    # "Voucher expires on 31 July 2026"
    #
    subject_dates = candidate_dates(
        subject,
        reference,
    )

    if subject_dates:
        return subject_dates


    combined = (
        subject
        + "\n"
        + body
    )


    # Next, prefer dates physically close to the
    # phrase which caused classification.
    #
    # e.g. "...we'll take your payment on 1 October..."
    #
    if matched_phrase:
        matches = list(
            re.finditer(
                re.escape(
                    matched_phrase
                ),
                combined,
                flags=re.I,
            )
        )

        for match in matches:
            start = max(
                0,
                match.start() - 180
            )

            end = min(
                len(combined),
                match.end() + 260
            )

            window = combined[
                start:end
            ]

            dates = candidate_dates(
                window,
                reference,
            )

            if dates:
                return dates


    # Last resort: consider every date in the email.
    return candidate_dates(
        combined,
        reference,
    )


def event_date_for(
    status,
    dates,
    message_dt,
):
    if status in {
        "PAID",
        "REFUNDED",
        "CANCELLED",
    }:
        return message_dt.date()

    minimum = (
        message_dt.date()
        - timedelta(days=2)
    )

    maximum = (
        message_dt.date()
        + timedelta(days=400)
    )

    valid = [
        value
        for value in dates
        if minimum <= value <= maximum
    ]

    if valid:
        return valid[0]

    return None


# ============================================================
# NORMALIZATION / SELECTION
# ============================================================

def merchant_key(value):
    value = value.lower()

    value = re.sub(
        r"\b("
        r"limited|ltd|plc|inc|llc|group|"
        r"payments?|billing|support"
        r")\b",
        "",
        value,
    )

    return re.sub(
        r"[^a-z0-9]+",
        "",
        value,
    )



def same_money(left, right):
    left_amount = left.get("amount")
    right_amount = right.get("amount")

    if (
        left_amount is None
        or right_amount is None
    ):
        return False

    if (
        left.get("currency")
        != right.get("currency")
    ):
        return False

    return abs(
        float(left_amount)
        - float(right_amount)
    ) < 0.01


def item_message_dt(item):
    return datetime.fromisoformat(
        item["message_date"]
    )


def item_event_date(item):
    value = item.get("event_date")

    if not value:
        return None

    return datetime.fromisoformat(
        value
    ).date()


def correlate_evidence(items):
    """
    Conservative resolution rules:

    DUE:
      suppress only when a later PAID message exists
      for the same merchant AND amount.

    RENEWS / EXPIRES:
      suppress when a later CANCELLED message exists
      for the same merchant before/around the event.

    No fuzzy financial inference.
    """

    grouped = {}

    for item in items:
        key = merchant_key(
            item["merchant"]
        )

        grouped.setdefault(
            key,
            []
        ).append(item)

    active = []
    resolved = []

    for key, group in grouped.items():

        group.sort(
            key=lambda item:
                item["message_date"]
        )

        for item in group:

            status = item["status"]

            # ------------------------------------
            # DUE -> later matching PAID
            # ------------------------------------

            if status == "DUE":
                notice_dt = item_message_dt(
                    item
                )

                due_date = item_event_date(
                    item
                )

                matched = None

                for other in group:
                    if other["status"] != "PAID":
                        continue

                    paid_dt = item_message_dt(
                        other
                    )

                    if paid_dt <= notice_dt:
                        continue

                    if not same_money(
                        item,
                        other
                    ):
                        continue

                    # Don't associate wildly distant
                    # transactions.
                    if due_date:
                        latest = (
                            due_date
                            + timedelta(days=21)
                        )

                        if paid_dt.date() > latest:
                            continue

                    matched = other
                    break

                if matched:
                    resolved.append({
                        "reason": "paid",
                        "item": item,
                        "by": matched,
                    })

                    continue


            # ------------------------------------
            # Renewal/expiry -> later cancellation
            # ------------------------------------

            if status in {
                "RENEWS",
                "EXPIRES",
            }:
                notice_dt = item_message_dt(
                    item
                )

                event_date = item_event_date(
                    item
                )

                matched = None

                for other in group:
                    if (
                        other["status"]
                        != "CANCELLED"
                    ):
                        continue

                    cancel_dt = item_message_dt(
                        other
                    )

                    if cancel_dt <= notice_dt:
                        continue

                    if (
                        event_date
                        and cancel_dt.date()
                        > event_date
                        + timedelta(days=7)
                    ):
                        continue

                    matched = other
                    break

                if matched:
                    resolved.append({
                        "reason": "cancelled",
                        "item": item,
                        "by": matched,
                    })

                    continue


            active.append(item)

    return active, resolved


def public_worthy(item, today):
    status = item["status"]
    value = item.get(
        "event_date"
    )

    if not value:
        return False

    event_date = datetime.fromisoformat(
        value
    ).date()

    if status in {
        "DUE",
        "RENEWS",
        "EXPIRES",
    }:
        return (
            today - timedelta(days=7)
            <= event_date
            <= today + timedelta(days=120)
        )

    if status in {
        "PAID",
        "REFUNDED",
        "CANCELLED",
    }:
        return (
            today - timedelta(days=35)
            <= event_date
            <= today + timedelta(days=1)
        )

    return False


def dedupe(items):
    result = {}

    for item in items:
        key = (
            merchant_key(
                item["merchant"]
            ),
            item["status"],
            item.get(
                "event_date"
            ),
            item.get(
                "amount"
            ),
            item.get(
                "currency"
            ),
        )

        existing = result.get(
            key
        )

        if (
            existing is None
            or item["message_date"]
            > existing["message_date"]
        ):
            result[key] = item

    return list(
        result.values()
    )


# ============================================================
# MAIN
# ============================================================

def main():
    LOCAL_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    service = gmail()

    ids = []
    search_sources = {}

    for label, query in SEARCHES:
        matches = search_ids(
            service,
            query,
        )

        print(
            f"{label:<24} "
            f"{len(matches)} candidate messages"
        )

        for message_id in matches:
            search_sources.setdefault(
                message_id,
                []
            ).append(label)

            if message_id not in ids:
                ids.append(message_id)

    ids = ids[:MAX_MESSAGES]

    print()
    print(
        "Unique messages to inspect:",
        len(ids)
    )

    evidence = []

    for index, message_id in enumerate(
        ids,
        start=1,
    ):
        message = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="full",
            )
            .execute()
        )

        subject = header(
            message,
            "Subject"
        )

        sender = header(
            message,
            "From"
        )

        dt = message_datetime(
            message
        )

        body = message_text(
            message
        )

        combined = (
            subject
            + "\n"
            + body
        )

        status, matched = classify(
            combined
        )

        if not status:
            continue

        dates = relevant_dates(
            subject,
            body,
            matched,
            dt,
        )

        event_date = event_date_for(
            status,
            dates,
            dt,
        )

        amount, currency = extract_amount(
            combined
        )

        # Upcoming categories without an actual date
        # are too ambiguous for the dashboard.
        if (
            status in {
                "DUE",
                "RENEWS",
                "EXPIRES",
            }
            and event_date is None
        ):
            continue

        item = {
            "message_id": message_id,
            "message_date": dt.isoformat(),
            "merchant": merchant_from_message(
                subject,
                sender,
                body,
            ),
            "status": status,
            "event_date": (
                event_date.isoformat()
                if event_date
                else None
            ),
            "amount": amount,
            "currency": currency,
            "matched_phrase": matched,
            "subject": subject[:200],
            "search_source":
                search_sources.get(
                    message_id,
                    []
                ),
        }

        evidence.append(
            item
        )

        if index % 25 == 0:
            print(
                f"Inspected {index}/"
                f"{len(ids)}"
            )

    evidence = dedupe(
        evidence
    )

    evidence.sort(
        key=lambda item: (
            item.get(
                "event_date"
            ) or "9999-12-31",
            item["merchant"].lower(),
        )
    )

    EVIDENCE_OUT.write_text(
        json.dumps(
            {
                "generated_at":
                    datetime.now(
                        TZ
                    ).isoformat(),
                "items":
                    evidence,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    EVIDENCE_OUT.chmod(
        0o600
    )

    today = datetime.now(
        TZ
    ).date()

    active_evidence, resolutions = (
        correlate_evidence(
            evidence
        )
    )

    public_items = [
        {
            "merchant":
                item["merchant"],
            "status":
                item["status"],
            "date":
                item["event_date"],
            "amount":
                item["amount"],
            "currency":
                item["currency"],
        }
        for item in active_evidence
        if public_worthy(
            item,
            today,
        )
    ]

    public_items.sort(
        key=lambda item:
            item["date"]
    )

    payload = {
        "generated_at":
            datetime.now(
                TZ
            ).isoformat(),
        "timezone":
            "Europe/London",
        "items":
            public_items,
        "counts": {
            status: sum(
                1
                for item
                in public_items
                if item["status"]
                == status
            )
            for status in [
                "PAID",
                "DUE",
                "RENEWS",
                "EXPIRES",
                "REFUNDED",
                "CANCELLED",
            ]
        },
    }

    tmp = PUBLIC_OUT.with_suffix(
        ".json.tmp"
    )

    tmp.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    tmp.replace(
        PUBLIC_OUT
    )

    PUBLIC_OUT.chmod(
        0o644
    )

    print()
    print("=== RESULT ===")
    print(
        "Classified evidence:",
        len(evidence)
    )
    print(
        "Dashboard items:    ",
        len(public_items)
    )

    print(
        "Resolved items:     ",
        len(resolutions)
    )
    print(
        "Counts:             ",
        payload["counts"]
    )

    print()
    print(
        "Private evidence:",
        EVIDENCE_OUT
    )
    print(
        "Dashboard JSON:  ",
        PUBLIC_OUT
    )


if __name__ == "__main__":
    main()
