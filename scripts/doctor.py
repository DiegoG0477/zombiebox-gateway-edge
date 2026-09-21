#!/usr/bin/env python3
"""Read bounded native Edge resource/tool facts without opening private configuration."""

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path


def command(args):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=3, check=False
        )
        return (
            result.stdout.splitlines()[0][:240]
            if result.returncode == 0 and result.stdout
            else "UNKNOWN"
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNAVAILABLE"


def report(runtime, prefix):
    installed = {
        name: (prefix / "var/service" / name / "run").is_file()
        for name in [
            "zombied",
            "zombie-mediamtx",
            "zombie-youtube",
            "zombie-youtube-receiver",
            "zombie-spotify",
            "zombie-airplay",
            "zombie-threadfin",
        ]
    }
    tools = {}
    for name, flag in [
        ("go", "version"),
        ("ffmpeg", "-version"),
        ("ffprobe", "-version"),
        ("node", "--version"),
        ("clang", "--version"),
    ]:
        binary = shutil.which(name)
        tools[name] = command([binary, flag]) if binary else "UNAVAILABLE"
    storage = shutil.disk_usage(runtime if runtime.exists() else runtime.parent)
    return {
        "reportVersion": 1,
        "androidApi": command(["getprop", "ro.build.version.sdk"]),
        "architecture": platform.machine(),
        "cpuCount": os.cpu_count(),
        "storageFreeMb": storage.free // (1024 * 1024),
        "tools": tools,
        "installedServices": installed,
        "gatewayInstalled": (runtime / "bin/zombied").is_file(),
        "support": {
            "core": "android-prebuilt"
            if (runtime / "current/release.json").is_file()
            else "native-build-required",
            "airplay": "experimental-native-build",
            "rebrowser": "remote-full-only",
        },
        "limitations": [
            "Installed tools/services do not prove account, Bionic media, LAN discovery or physical compatibility.",
            "No credentials, configuration contents or network probes are included.",
        ],
    }


def main():
    prefix = os.environ.get("PREFIX", "")
    if prefix != "/data/data/com.termux/files/usr":
        raise SystemExit("Run inside Termux on Android.")
    print(json.dumps(report(Path.home() / ".zombie", Path(prefix)), indent=2))


if __name__ == "__main__":
    main()
