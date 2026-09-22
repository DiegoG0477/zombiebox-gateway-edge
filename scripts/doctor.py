#!/usr/bin/env python3
"""Read bounded native Edge resource/tool facts without opening private configuration."""

import json
import os
import platform
import re
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
        "modules": module_status(runtime, prefix),
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


def module_status(runtime, prefix):
    """Keep installation, process state and account readiness independent."""
    modules = {
        "core": ("zombied", ["bin/zombied"], []),
        "cast": ("zombie-mediamtx", ["bin/mediamtx"], []),
        "youtube": ("zombie-youtube", ["youtube/server.mjs"], ["node"]),
        "youtube_receiver": (
            "zombie-youtube-receiver",
            ["youtube-receiver/server.mjs", "youtube-receiver/completion.mjs"],
            ["node"],
        ),
        "spotify": ("zombie-spotify", ["bin/go-librespot", "bin/zombie-worker"], []),
        "airplay": ("zombie-airplay", ["bin/uxplay", "bin/zombie-worker"], []),
        "iptv_threadfin": ("zombie-threadfin", ["bin/threadfin"], []),
    }
    result = {}
    for name, (service, files, commands) in modules.items():
        directory = prefix / "var/service" / service
        missing = [item for item in files if not (runtime / item).is_file()]
        missing += [item for item in commands if shutil.which(item) is None]
        if not (directory / "run").is_file():
            state = "not_installed"
        elif (directory / "down").exists():
            state = "disabled"
        else:
            status = command(["sv", "status", str(directory)])
            state = (
                "running"
                if status.startswith("run:")
                else "stopped"
                if status.startswith("down:")
                else "unknown"
            )
        result[name] = {
            "installation": "missing_files" if missing else "present",
            "missing": missing,
            "serviceState": state,
            "accountReadiness": "not_probed",
            "mediaValidated": False,
        }
        if name.startswith("youtube") and shutil.which("node"):
            version = command(["node", "--version"])
            match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
            compatible = bool(
                match
                and tuple(map(int, match.groups())) >= (22, 22, 2)
                and int(match[1]) == 22
            )
            result[name]["runtimeVersionCompatible"] = compatible
    return result


def main():
    prefix = os.environ.get("PREFIX", "")
    if prefix != "/data/data/com.termux/files/usr":
        raise SystemExit("Run inside Termux on Android.")
    print(json.dumps(report(Path.home() / ".zombie", Path(prefix)), indent=2))


if __name__ == "__main__":
    main()
