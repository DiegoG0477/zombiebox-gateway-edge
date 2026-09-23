#!/usr/bin/env python3
"""Read bounded native Edge resource/tool facts without opening private configuration."""

import argparse
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
                and (
                    (
                        int(match[1]) == 22
                        and tuple(map(int, match.groups())) >= (22, 22, 2)
                    )
                    or (
                        int(match[1]) == 24
                        and tuple(map(int, match.groups())) >= (24, 18, 0)
                    )
                )
            )
            result[name]["runtimeVersionCompatible"] = compatible
    return result


def network_report(runtime, address, http_port, discovery_port, rtsp_port):
    """Explicitly invoke the shared core; never print its stderr or private configuration."""
    args = [str(runtime / "bin/zombied"), "--diagnose-address", address]
    for name, value in (
        ("http", http_port),
        ("discovery", discovery_port),
        ("rtsp", rtsp_port),
    ):
        args += [f"--diagnose-{name}-port", str(value)]
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, timeout=4, check=False
        )
        if result.returncode != 0 or len(result.stdout) > 16384:
            return {"state": "unavailable_or_unsupported"}
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or value.get("reportVersion") != 1:
            return {"state": "unavailable_or_unsupported"}
        statuses = {
            "ok",
            "unavailable",
            "invalid_response",
            "authentication_required",
            "port_mismatch",
        }
        probes = {}
        for key in ("httpHealth", "discoveryUnicast", "rtspOptions"):
            probe = value[key]
            if (
                probe["state"] not in statuses
                or not isinstance(probe["elapsedMs"], int)
                or not 0 <= probe["elapsedMs"] <= 10000
            ):
                raise ValueError("invalid probe result")
            probes[key] = {"state": probe["state"], "elapsedMs": probe["elapsedMs"]}
        return {**probes, "mediaValidated": False, "accountValidated": False}
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return {"state": "unavailable_or_unsupported"}


def media_report(runtime):
    """The shared core owns bounded fixture generation and actual software decoding."""
    try:
        result = subprocess.run(
            [str(runtime / "bin/zombied"), "--diagnose-media"],
            capture_output=True,
            text=True,
            timeout=35,
            check=False,
        )
        if result.returncode != 0 or len(result.stdout) > 16384:
            return {"state": "unavailable_or_unsupported"}
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or value.get("reportVersion") != 1:
            raise ValueError("unknown report")
        stages = {}
        for key in ("fixture", "remux", "transcode"):
            stage = value[key]
            if stage["state"] not in {
                "pass",
                "failed",
                "unavailable",
                "cancelled",
                "not_run",
            }:
                raise ValueError("unknown state")
            counts = [stage["videoFrames"], stage["audioFrames"]]
            if any(
                type(count) is not int or not 0 <= count <= 1000 for count in counts
            ):
                raise ValueError("invalid frame evidence")
            if stage["state"] == "pass" and min(counts) < 5:
                raise ValueError("missing decoded frames")
            stages[key] = {
                "state": stage["state"],
                "videoFrames": counts[0],
                "audioFrames": counts[1],
            }
        return {
            **stages,
            "gatewayPipelineVerified": all(
                stage["state"] == "pass" for stage in stages.values()
            ),
            "receiverValidated": False,
            "networkValidated": False,
        }
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError):
        return {"state": "unavailable_or_unsupported"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--media",
        action="store_true",
        help="generate, convert and decode a small local software fixture",
    )
    parser.add_argument(
        "--network",
        action="store_true",
        help="probe one selected endpoint, without pairing or media",
    )
    parser.add_argument(
        "--address", default="127.0.0.1", help="literal local IPv4; loopback by default"
    )
    parser.add_argument("--http-port", type=int, default=8090)
    parser.add_argument("--discovery-port", type=int, default=8098)
    parser.add_argument("--rtsp-port", type=int, default=8554)
    args = parser.parse_args()
    prefix = os.environ.get("PREFIX", "")
    if prefix != "/data/data/com.termux/files/usr":
        raise SystemExit("Run inside Termux on Android.")
    runtime = Path.home() / ".zombie"
    value = report(runtime, Path(prefix))
    if args.network:
        value["network"] = network_report(
            runtime, args.address, args.http_port, args.discovery_port, args.rtsp_port
        )
        value["limitations"][1] = (
            "Selected-endpoint probes exclude credentials, media, pairing and broadcast/multicast qualification. Loopback is not evidence of access from another device."
        )
    if args.media:
        value["media"] = media_report(runtime)
    print(json.dumps(value, indent=2))


if __name__ == "__main__":
    main()
