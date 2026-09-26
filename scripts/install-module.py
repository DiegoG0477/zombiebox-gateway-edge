#!/usr/bin/env python3
"""Install an explicitly selected, checksum-verified optional Android module."""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

LIMIT = 256 << 20
MODULES = {
    "threadfin": "6b9c0ccf16164eb362af0a44660228267734c5aa",
    "mediamtx": "048255986f7e04b859b4c4efe651448ec785ecd4",
    "airplay": "57ea83411d5f7e0b38c5841987439340543f025c",
    "spotify": "6a3e25019de8d2893b3fa26b0273d8cc376241c5",
}
SPOTIFY_PACKAGE_VERSIONS = {
    "libflac": "1.5.0-1",
    "libmpg123": "1.33.7",
    "libogg": "1.3.6-1",
}


def download(version, module, arch, directory):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9.-]+)?", version):
        raise ValueError("Select an explicit release version, never latest")
    name = f"zombiebox-{module}-android-{arch}.tar.gz"
    base = f"https://github.com/ZombieBox-tv/zombiebox-gateway-edge/releases/download/{version}/"
    for suffix, size in ((".sha256", 512), ("", LIMIT)):
        subprocess.run(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--location",
                "--proto",
                "=https",
                "--proto-redir",
                "=https",
                "--max-time",
                "300",
                "--max-filesize",
                str(size),
                "--output",
                str(directory / (name + suffix)),
                base + name + suffix,
            ],
            check=True,
            timeout=310,
        )
    fields = (directory / (name + ".sha256")).read_text().split()
    if len(fields) != 2 or fields[1] != name:
        raise ValueError("Release checksum does not identify the selected asset")
    return directory / name, fields[0]


def extract(archive, destination, checksum):
    if not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise ValueError("Supply the independently verified archive SHA256")
    if archive.stat().st_size > LIMIT:
        raise ValueError("Module archive is too large")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != checksum:
            raise ValueError("Module archive checksum mismatch")
    with tarfile.open(archive, "r:gz") as source:
        members, names, total = [], set(), 0
        for member in source:
            path = Path(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or ".." in path.parts
                or str(path) != member.name
                or member.name in names
            ):
                raise ValueError("Unsafe or duplicate module archive path")
            total += member.size
            if len(members) >= 1024 or total > LIMIT:
                raise ValueError("Module extraction limit exceeded")
            names.add(member.name)
            members.append(member)
        source.extractall(destination, members=members, filter="data")


def validate(package, module, arch, api):
    record = json.loads((package / "module.json").read_text())
    if (
        module not in MODULES
        or record.get("module") != module
        or record.get("upstreamCommit") != MODULES[module]
    ):
        raise ValueError("Unsupported optional module revision")
    if (
        record.get("schemaVersion") != 1
        or record.get("platform") != "android"
        or record.get("architecture") != arch
        or arch not in ("arm64", "armv7")
        or record.get("minApi") != 24
        or api < 24
    ):
        raise ValueError("Module does not support this Android userland")
    files = record.get("files", {})
    actual = {
        str(p.relative_to(package)) for p in package.rglob("*") if p.is_file()
    } - {"module.json"}
    required = {
        "bin/" + module,
        "licenses/upstream-LICENSE",
        "licenses/go-LICENSE",
        "licenses/ndk-NOTICE",
        "licenses/ndk-NOTICE.toolchain",
    }
    if module == "mediamtx":
        required.add("mediamtx.yml")
    if module == "airplay":
        required.update(
            {
                "bin/zombie-worker",
                "licenses/llhttp-LICENSE",
                "licenses/playfair-LICENSE",
            }
        )
    if module == "spotify":
        required.update(
            {
                "bin/zombie-worker",
                "licenses/libflac-Xiph",
                "licenses/libflac-LGPL",
                "licenses/libflac-GPL",
                "licenses/libogg-copyright",
                "licenses/libmpg123-LGPL",
            }
        )
        modules = {
            entry.get("module"): entry.get("version")
            for entry in record.get("dependencies", [])
        }
        if (
            record.get("vorbisPatch") != "licensed-vorbis.patch"
            or record.get("sourcePatches")
            != ["licensed-vorbis.patch", "stop-key-refusal-skip.patch"]
            or record.get("externalPackages") != list(SPOTIFY_PACKAGE_VERSIONS)
            or record.get("externalPackageVersions") != SPOTIFY_PACKAGE_VERSIONS
            or modules.get("github.com/jfreymuth/oggvorbis") != "v1.0.5"
            or modules.get("github.com/jfreymuth/vorbis") != "v1.0.2"
            or "github.com/xlab/vorbis-go" in modules
        ):
            raise ValueError(
                "Spotify package is not the reviewed source and decoder build"
            )
    if not required.issubset(files) or actual != set(files):
        raise ValueError("Incomplete or unexpected module files")
    for name, checksum in files.items():
        path = package / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != checksum
        ):
            raise ValueError("Invalid module file checksum/path")
    source = record.get("sourceArchive", {})
    if source.get(
        "name"
    ) != f"zombiebox-{module}-android-{arch}-sources.tar.gz" or not re.fullmatch(
        r"[a-f0-9]{64}", source.get("sha256", "")
    ):
        raise ValueError("Corresponding-source archive must be identified")
    spec = importlib.util.spec_from_file_location(
        "binary_installer", Path(__file__).with_name("install-binary.py")
    )
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    if not installer.android_elf((package / "bin" / module).read_bytes(), arch):
        raise ValueError("Expected an Android PIE executable for this ABI")
    if module in {"airplay", "spotify"} and not installer.android_elf(
        (package / "bin/zombie-worker").read_bytes(), arch
    ):
        raise ValueError("Expected an Android worker for this ABI")
    return record


def install(package, module, arch, api, runtime, prefix):
    record = validate(package, module, arch, api)
    if not (runtime / "bin/zombied").is_file():
        raise ValueError("Install the Edge core first")
    if module in {"airplay", "spotify"}:
        core = json.loads((runtime / "current/release.json").read_text())
        if record.get("coreCommit") != core.get("coreCommit"):
            raise ValueError(f"{module} worker requires its exact matching Edge core")
        alias = "uxplay" if module == "airplay" else "go-librespot"
        old = runtime / "bin" / alias
        if old.exists() and not old.is_symlink():
            raise ValueError(
                f"Migrate the existing source-built {alias} before installing a binary module"
            )
    if module == "mediamtx" and not (runtime / "config/runtime.env").is_file():
        raise ValueError("Install the core runtime configuration before MediaMTX")
    binary = package / "bin" / module
    binary.chmod(0o700)
    if module == "airplay":
        packages = record.get("externalPackages")
        if packages != [
            "openssl",
            "libplist",
            "gstreamer",
            "gst-plugins-base",
            "gst-plugins-good",
            "gst-plugins-bad",
            "glib",
            "libc++",
        ]:
            raise ValueError("Unexpected AirPlay runtime package set")
        subprocess.run(["pkg", "install", "-y", *packages], check=True, timeout=300)
        if not shutil.which("gst-inspect-1.0"):
            raise ValueError("Native GStreamer inspection tool is unavailable")
        for element in ("rtpL16pay", "rtph264pay", "multiudpsink", "udpsink"):
            subprocess.run(
                ["gst-inspect-1.0", element],
                check=True,
                timeout=15,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    if module == "spotify":
        subprocess.run(
            [
                "apt-get",
                "install",
                "-y",
                *(
                    f"{name}={version}"
                    for name, version in SPOTIFY_PACKAGE_VERSIONS.items()
                ),
            ],
            check=True,
            timeout=300,
        )
    subprocess.run(
        [str(binary), "--help" if module == "spotify" else "-h"],
        check=True,
        timeout=15,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if module in {"airplay", "spotify"}:
        worker = package / "bin/zombie-worker"
        worker.chmod(0o700)
        subprocess.run(
            [str(worker), "-h"],
            check=True,
            timeout=15,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    directory = runtime / "modules" / module
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    release = Path(tempfile.mkdtemp(prefix="release-", dir=directory))
    shutil.copytree(package, release, dirs_exist_ok=True)
    service = prefix / "var/service" / ("zombie-" + module)
    service.mkdir(parents=True, exist_ok=True)
    if (service / "run").exists():
        subprocess.run(["sv", "-w", "15", "down", str(service)], check=True, timeout=20)
    (service / "down").touch()
    temporary = directory / "current.next"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace(directory / "current")
    link = runtime / "bin" / (module + ".next")
    link.unlink(missing_ok=True)
    link.symlink_to(directory / "current/bin" / module)
    link.replace(runtime / "bin" / module)
    if module == "airplay":
        uxplay = runtime / "bin/uxplay.next"
        uxplay.unlink(missing_ok=True)
        uxplay.symlink_to(directory / "current/bin/airplay")
        uxplay.replace(runtime / "bin/uxplay")
    if module == "spotify":
        librespot = runtime / "bin/go-librespot.next"
        librespot.unlink(missing_ok=True)
        librespot.symlink_to(directory / "current/bin/spotify")
        librespot.replace(runtime / "bin/go-librespot")
    (service / "run").write_text(service_script(module, runtime, release))
    (service / "run").chmod(0o700)
    print(
        f"Installed {module} stopped; configuration preserved. Start with zombiebox start zombie-{module}."
    )
    if module == "mediamtx":
        print(
            "Restart zombied after starting MediaMTX to load the relay configuration."
        )


def service_script(module, runtime, release):
    header = "#!/data/data/com.termux/files/usr/bin/sh\nset -eu\nexec 2>&1\n"
    if module == "threadfin":
        (runtime / "threadfin").mkdir(exist_ok=True, mode=0o700)
        return (
            header
            + "export GOMEMLIMIT=128MiB GOMAXPROCS=1\n"
            + 'exec "$HOME/.zombie/bin/threadfin" -config "$HOME/.zombie/threadfin" -bind 127.0.0.1 -port 34400\n'
        )
    if module == "airplay":
        worker = runtime / "config/airplay-worker.json"
        (runtime / "airplay").mkdir(exist_ok=True, mode=0o700)
        if not worker.exists():
            worker.write_text(
                json.dumps(
                    {
                        "mode": "airplay",
                        "listen": "127.0.0.1:8093",
                        "token": secrets.token_hex(32),
                        "pin": f"{secrets.randbelow(10000):04}",
                        "stateDir": str(runtime / "airplay"),
                    }
                )
                + "\n"
            )
            worker.chmod(0o600)
        providers_file = runtime / "config/providers.json"
        providers = json.loads(providers_file.read_text())
        if "airplay" not in providers:
            providers["airplay"] = {
                "enabled": False,
                "url": "http://127.0.0.1:8093",
                "token": json.loads(worker.read_text())["token"],
            }
            replacement = providers_file.with_suffix(".next")
            replacement.write_text(json.dumps(providers, indent=2) + "\n")
            replacement.chmod(0o600)
            replacement.replace(providers_file)
        return (
            header
            + 'export PATH="$HOME/.zombie/bin:$PATH" GOMEMLIMIT=128MiB GOMAXPROCS=1\n'
            + 'export GST_REGISTRY="$HOME/.zombie/airplay/gstreamer-registry.bin"\n'
            + 'exec "$HOME/.zombie/modules/airplay/current/bin/zombie-worker" -config "$HOME/.zombie/config/airplay-worker.json"\n'
        )
    if module == "spotify":
        state = runtime / "spotify"
        state.mkdir(exist_ok=True, mode=0o700)
        worker = runtime / "config/spotify-worker.json"
        if not worker.exists():
            worker.write_text(
                json.dumps(
                    {
                        "mode": "spotify",
                        "listen": "127.0.0.1:8092",
                        "token": secrets.token_hex(32),
                        "stateDir": str(state),
                    }
                )
                + "\n"
            )
            worker.chmod(0o600)
        config = state / "config.yml"
        if not config.exists():
            config.write_text(
                "device_name: Zombie Box Edge\n"
                "credentials:\n  type: device_auth\n"
                "zeroconf_enabled: false\n"
                "audio_backend: pipe\n"
                f"audio_output_pipe: {state / 'audio.pcm'}\n"
                "audio_output_pipe_format: s16le\n"
                "audio_output_pipe_wait_for_reader: true\n"
                "volume_steps: 100\n"
                "server:\n  enabled: true\n  address: 127.0.0.1\n  port: 3678\n"
            )
            config.chmod(0o600)
        providers_file = runtime / "config/providers.json"
        providers = json.loads(providers_file.read_text())
        if "spotify" not in providers:
            providers["spotify"] = {
                "enabled": False,
                "url": "http://127.0.0.1:8092",
                "token": json.loads(worker.read_text())["token"],
            }
            replacement = providers_file.with_suffix(".next")
            replacement.write_text(json.dumps(providers, indent=2) + "\n")
            replacement.chmod(0o600)
            replacement.replace(providers_file)
        return (
            header
            + 'export PATH="$HOME/.zombie/bin:$PATH" GOMEMLIMIT=128MiB GOMAXPROCS=1\n'
            + 'exec "$HOME/.zombie/modules/spotify/current/bin/zombie-worker" -config "$HOME/.zombie/config/spotify-worker.json"\n'
        )
    config = runtime / "config/mediamtx.yml"
    if not config.exists():
        shutil.copy2(release / "mediamtx.yml", config)
        config.chmod(0o600)
    (runtime / "config/cast.enabled").touch(mode=0o600)
    return (
        header
        + 'set -a\n. "$HOME/.zombie/config/runtime.env"\nset +a\n'
        + ': "${ZOMBIE_RELAY_ADMIN_TOKEN:?Core relay key is missing}"\n'
        + "listen=${ZOMBIE_LISTEN:-0.0.0.0:8090}\n"
        + "export GOMEMLIMIT=96MiB GOMAXPROCS=1\n"
        + 'export MTX_AUTHHTTPADDRESS="http://127.0.0.1:${listen##*:}/internal/relay/auth?key=$ZOMBIE_RELAY_ADMIN_TOKEN"\n'
        + 'export MTX_RTSPADDRESS="${ZOMBIE_RTSP_LISTEN:-0.0.0.0:8554}"\n'
        + "export MTX_HLSADDRESS=127.0.0.1:8888 MTX_APIADDRESS=127.0.0.1:9997\n"
        + 'exec "$HOME/.zombie/bin/mediamtx" "$HOME/.zombie/config/mediamtx.yml"\n'
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=MODULES, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--bundle", type=Path)
    source.add_argument("--version")
    parser.add_argument("--sha256")
    args = parser.parse_args()
    if args.bundle and not args.sha256:
        parser.error(
            "Local bundles require --sha256 from an independently verified source"
        )
    if os.environ.get("PREFIX") != "/data/data/com.termux/files/usr":
        raise SystemExit("Run inside the standard Termux application")
    userland = subprocess.check_output(
        ["dpkg", "--print-architecture"], text=True
    ).strip()
    arch = {"aarch64": "arm64", "arm": "armv7"}.get(userland)
    if arch is None:
        raise SystemExit("Unsupported Termux userland")
    api = int(
        subprocess.check_output(["getprop", "ro.build.version.sdk"], text=True).strip()
    )
    runtime = Path.home() / ".zombie"
    if not runtime.is_dir():
        raise SystemExit("Install the Edge core first")
    os.umask(0o077)
    with (runtime / "install.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit("Another Edge installation is running") from None
        with tempfile.TemporaryDirectory(prefix="zombie-module-") as temporary:
            staging = Path(temporary)
            bundle, checksum = (
                (args.bundle, args.sha256)
                if args.bundle
                else download(args.version, args.module, arch, staging)
            )
            package = staging / "package"
            package.mkdir()
            extract(bundle, package, checksum)
            install(
                package, args.module, arch, api, runtime, Path(os.environ["PREFIX"])
            )


if __name__ == "__main__":
    main()
