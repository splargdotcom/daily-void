#!/usr/bin/env python3

import json
import socket
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path("/var/www/mywebsite/start/status.json")

SERVICES = [
    {
        "name": "splarg.com",
        "kind": "http",
        "check": "https://example.com/",
        "link": "https://example.com/",
    },
    {
        "name": "Maloja",
        "kind": "http",
        "check": "https://music.example.com/",
        "link": "https://music.example.com/",
    },
    {
        "name": "BugCam",
        "kind": "bugcam",
        "check": "https://camera.example.com/health",
        "link": "https://camera.example.com/",
    },
    {
        "name": "Server 2",
        "kind": "tcp",
        "host": "server2",
        "port": 22,
        "link": "",
    },
    {
        "name": "ComfyUI H3",
        "kind": "http",
        "check": "http://server2:8193/",
        "link": "https://comfy.example.com/",
    },
    {
        "name": "Qwen Chat",
        "kind": "http",
        "check": "http://server2:8090/",
        "link": "http://server2:8090/",
    },
    {
        "name": "SplargRater",
        "kind": "http",
        "check": "http://server2:8766/",
        "link": "http://server2:8766/",
    },
    {
        "name": "Terrarium",
        "kind": "http",
        "check": "http://127.0.0.1:8095/",
        "link": "http://server1:8095/",
    },
    {
        "name": "HemoLink",
        "kind": "http",
        "check": "http://127.0.0.1:8000/",
        "link": "http://server1:8000/",
    },
    {
        "name": "Server 1 Apache",
        "kind": "http",
        "check": "http://127.0.0.1/",
        "link": "/",
    },
]

HEADERS = {
    "User-Agent": "DailyVoid/2.0",
    "Accept": "application/json,text/html,*/*",
}


def http_check(url, want_json=False, timeout=4):
    started = time.perf_counter()

    request = urllib.request.Request(
        url,
        headers=HEADERS,
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            elapsed = round((time.perf_counter() - started) * 1000)
            code = response.getcode()

            if want_json:
                raw = response.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {}
                return code, elapsed, data

            return code, elapsed, None

    except urllib.error.HTTPError as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        return exc.code, elapsed, None

    except Exception as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        return None, elapsed, exc


def tcp_check(host, port, timeout=3):
    started = time.perf_counter()

    try:
        with socket.create_connection((host, port), timeout=timeout):
            elapsed = round((time.perf_counter() - started) * 1000)
            return True, elapsed, None

    except Exception as exc:
        elapsed = round((time.perf_counter() - started) * 1000)
        return False, elapsed, exc


def error_name(exc):
    if exc is None:
        return "error"

    name = type(exc).__name__

    reason = getattr(exc, "reason", None)
    if reason:
        reason_name = type(reason).__name__
        if reason_name and reason_name != name:
            return reason_name

    return name


def check_service(service):
    row = {
        "name": service["name"],
        "link": service["link"],
        "state": "bad",
        "label": "offline",
        "extra": "",
    }

    kind = service["kind"]

    if kind == "http":
        code, ms, result = http_check(service["check"])

        if code is not None and 200 <= code < 400:
            row.update(
                state="ok",
                label=str(code),
                extra=f"{ms} ms",
            )
        elif code is not None:
            row.update(
                state="warn",
                label=str(code),
                extra=f"{ms} ms",
            )
        else:
            row.update(
                state="bad",
                label="offline",
                extra=error_name(result),
            )

    elif kind == "tcp":
        ok, ms, result = tcp_check(
            service["host"],
            service["port"],
        )

        if ok:
            row.update(
                state="ok",
                label="online",
                extra=f"{ms} ms",
            )
        else:
            row.update(
                state="bad",
                label="offline",
                extra=error_name(result),
            )

    elif kind == "bugcam":
        code, ms, result = http_check(
            service["check"],
            want_json=True,
        )

        if code is None:
            row.update(
                state="bad",
                label="offline",
                extra=error_name(result),
            )

        elif isinstance(result, dict) and result.get("bugcam") == "ok":
            row.update(
                state="ok",
                label="online",
                extra=f"{ms} ms",
            )

        elif isinstance(result, dict):
            active = result.get("camera_active")
            fps = result.get("fps")
            temp = result.get("battery_temp")

            if active is True:
                row["state"] = "ok"
                row["label"] = "streaming"
            else:
                row["state"] = "warn"
                row["label"] = "reachable"

            details = []

            if fps is not None:
                details.append(f"{fps} FPS")

            if temp is not None:
                details.append(f"{temp}°C")

            if not details:
                details.append(f"{ms} ms")

            row["extra"] = " · ".join(details)

        else:
            row.update(
                state="warn",
                label="reachable",
                extra=f"{ms} ms",
            )

    return row


def main():
    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "services": [],
    }

    for service in SERVICES:
        row = check_service(service)
        output["services"].append(row)

        print(
            f"{row['name']:<22} "
            f"{row['state']:<5} "
            f"{row['label']:<10} "
            f"{row['extra']}"
        )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    temp = OUTPUT.with_suffix(".json.tmp")
    temp.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    temp.replace(OUTPUT)

    print()
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
