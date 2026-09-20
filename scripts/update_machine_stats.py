#!/usr/bin/env python3

import json
import os
import re
import shutil
import subprocess
import time

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


WEB_ROOT = Path(
    os.environ.get(
        "DAILY_VOID_WEB_ROOT",
        "/var/www/daily-void",
    )
)
OUTPUT = WEB_ROOT / "machine_stats.json"

TZ_NAME = os.environ.get(
    "DAILY_VOID_TIMEZONE",
    "Europe/London",
)
TZ = ZoneInfo(TZ_NAME)

REMOTE_STATS_HOST = os.environ.get(
    "REMOTE_STATS_HOST",
    "server2",
)


def cpu_snapshot():
    line = Path(
        "/proc/stat"
    ).read_text().splitlines()[0]

    values = list(
        map(
            int,
            line.split()[1:],
        )
    )

    idle = (
        values[3]
        + (
            values[4]
            if len(values) > 4
            else 0
        )
    )

    return sum(values), idle


def cpu_percent():
    total1, idle1 = cpu_snapshot()

    time.sleep(0.20)

    total2, idle2 = cpu_snapshot()

    total_delta = total2 - total1
    idle_delta = idle2 - idle1

    if total_delta <= 0:
        return None

    return round(
        (
            1
            - idle_delta
            / total_delta
        )
        * 100,
        1,
    )


def mem_stats():
    values = {}

    for line in Path(
        "/proc/meminfo"
    ).read_text().splitlines():

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1,
        )

        match = re.search(
            r"(\d+)",
            value,
        )

        if match:
            values[key] = (
                int(match.group(1))
                * 1024
            )

    total = values.get(
        "MemTotal",
        0,
    )

    available = values.get(
        "MemAvailable",
        0,
    )

    used = max(
        0,
        total - available,
    )

    percent = (
        round(
            used / total * 100,
            1,
        )
        if total
        else None
    )

    return {
        "total_bytes": total,
        "used_bytes": used,
        "percent": percent,
    }


def local_stats():
    disk = shutil.disk_usage(
        "/"
    )

    uptime = float(
        Path(
            "/proc/uptime"
        )
        .read_text()
        .split()[0]
    )

    load = os.getloadavg()

    return {
        "online": True,
        "uptime_seconds":
            round(uptime),

        "cpu_percent":
            cpu_percent(),

        "load_1":
            round(load[0], 2),

        "cores":
            os.cpu_count(),

        "memory":
            mem_stats(),

        "disk": {
            "total_bytes":
                disk.total,

            "used_bytes":
                disk.used,

            "percent":
                round(
                    disk.used
                    / disk.total
                    * 100,
                    1,
                ),
        },
    }


REMOTE_SCRIPT = r'''
python3 - <<'PYREMOTE'
import json
import os
import shutil
import time
from pathlib import Path

def snap():
    line = Path("/proc/stat").read_text().splitlines()[0]
    vals = list(map(int, line.split()[1:]))
    idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
    return sum(vals), idle

a_total, a_idle = snap()
time.sleep(0.20)
b_total, b_idle = snap()

delta = b_total - a_total
idle_delta = b_idle - a_idle

cpu = None
if delta > 0:
    cpu = round((1 - idle_delta / delta) * 100, 1)

mem = {}
for line in Path("/proc/meminfo").read_text().splitlines():
    if ":" not in line:
        continue
    k, v = line.split(":", 1)
    bits = v.strip().split()
    if bits and bits[0].isdigit():
        mem[k] = int(bits[0]) * 1024

total = mem.get("MemTotal", 0)
available = mem.get("MemAvailable", 0)
used = max(0, total - available)

disk = shutil.disk_usage("/")
uptime = float(Path("/proc/uptime").read_text().split()[0])
load = os.getloadavg()

print("__MACHINE_JSON__")
print(json.dumps({
    "online": True,
    "uptime_seconds": round(uptime),
    "cpu_percent": cpu,
    "load_1": round(load[0], 2),
    "cores": os.cpu_count(),
    "memory": {
        "total_bytes": total,
        "used_bytes": used,
        "percent": round(used / total * 100, 1) if total else None
    },
    "disk": {
        "total_bytes": disk.total,
        "used_bytes": disk.used,
        "percent": round(disk.used / disk.total * 100, 1)
    }
}))
PYREMOTE

echo "__GPU_BEGIN__"

rocm-smi \
  --showtemp \
  --showuse \
  --showmeminfo vram \
  --showpower \
  2>&1

echo "__GPU_END__"

echo "__NVIDIA_BEGIN__"

if command -v nvidia-smi >/dev/null 2>&1; then
    nvidia-smi \
      --query-gpu=index,name,utilization.gpu,temperature.gpu,memory.used,memory.total,power.draw,power.limit \
      --format=csv,noheader,nounits \
      2>&1
fi

echo "__NVIDIA_END__"

'''


def parse_gpu(text):
    def number(pattern):
        match = re.search(
            pattern,
            text,
            flags=re.I,
        )

        if not match:
            return None

        return float(
            match.group(1)
        )

    total = number(
        r"VRAM Total Memory \(B\):\s*([\d.]+)"
    )

    used = number(
        r"VRAM Total Used Memory \(B\):\s*([\d.]+)"
    )

    gpu = {
        "util_percent":
            number(
                r"GPU use \(%\):\s*([\d.]+)"
            ),

        "edge_c":
            number(
                r"Sensor edge\) \(C\):\s*([\d.]+)"
            ),

        "hotspot_c":
            number(
                r"Sensor junction\) \(C\):\s*([\d.]+)"
            ),

        "memory_c":
            number(
                r"Sensor memory\) \(C\):\s*([\d.]+)"
            ),

        "power_w":
            number(
                r"Package Power \(W\):\s*([\d.]+)"
            ),

        "vram_total_bytes":
            total,

        "vram_used_bytes":
            used,
    }

    if total and used:
        gpu["vram_percent"] = round(
            used / total * 100,
            1,
        )
    else:
        gpu["vram_percent"] = None

    return gpu



def parse_nvidia(text):
    gpus = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        parts = [
            part.strip()
            for part in line.split(",")
        ]

        if len(parts) < 8:
            continue

        try:
            index = int(parts[0])
        except Exception:
            continue

        def number(value):
            try:
                return float(value)
            except Exception:
                return None

        used_mb = number(
            parts[4]
        )

        total_mb = number(
            parts[5]
        )

        used_bytes = (
            int(
                used_mb
                * 1024
                * 1024
            )
            if used_mb is not None
            else None
        )

        total_bytes = (
            int(
                total_mb
                * 1024
                * 1024
            )
            if total_mb is not None
            else None
        )

        percent = None

        if (
            used_bytes is not None
            and total_bytes
        ):
            percent = round(
                used_bytes
                / total_bytes
                * 100,
                1,
            )

        gpus.append({
            "index":
                index,

            "name":
                parts[1],

            "util_percent":
                number(parts[2]),

            "temperature_c":
                number(parts[3]),

            "vram_used_bytes":
                used_bytes,

            "vram_total_bytes":
                total_bytes,

            "vram_percent":
                percent,

            "power_w":
                number(parts[6]),

            "power_limit_w":
                number(parts[7]),
        })

    return gpus


def server2_stats():
    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=5",
                REMOTE_STATS_HOST,
                REMOTE_SCRIPT,
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip()
                or
                f"ssh exit {result.returncode}"
            )

        output = result.stdout

        match = re.search(
            r"__MACHINE_JSON__\s*\n"
            r"(\{.*?\})\s*\n"
            r"__GPU_BEGIN__",
            output,
            flags=re.S,
        )

        if not match:
            raise RuntimeError(
                "machine JSON not found"
            )

        machine = json.loads(
            match.group(1)
        )

        gpu_match = re.search(
            r"__GPU_BEGIN__"
            r"(.*?)"
            r"__GPU_END__",
            output,
            flags=re.S,
        )

        if gpu_match:
            machine["gpu"] = parse_gpu(
                gpu_match.group(1)
            )

        nvidia_match = re.search(
            r"__NVIDIA_BEGIN__"
            r"(.*?)"
            r"__NVIDIA_END__",
            output,
            flags=re.S,
        )

        if nvidia_match:
            machine["nvidia"] = parse_nvidia(
                nvidia_match.group(1)
            )

        return machine

    except Exception as exc:
        return {
            "online": False,
            "error":
                type(exc).__name__,
        }


def main():
    data = {
        "generated_at":
            datetime.now(TZ)
            .isoformat(),

        "server1":
            local_stats(),

        "server2":
            server2_stats(),
    }

    temp = OUTPUT.with_suffix(
        ".json.tmp"
    )

    temp.write_text(
        json.dumps(
            data,
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
        json.dumps(
            data,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
