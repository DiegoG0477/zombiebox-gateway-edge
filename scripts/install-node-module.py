#!/usr/bin/env python3
"""Install a source-closed optional JS worker beside a matching Edge core."""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

MODULES = ("youtube", "youtube-receiver")
LIMIT = 256 << 20


def download(version, module, destination):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9.-]+)?", version):
        raise ValueError("Select an explicit release version")
    name = f"zombiebox-{module}-android-any.tar.gz"
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
                str(destination / (name + suffix)),
                base + name + suffix,
            ],
            check=True,
            timeout=310,
        )
    fields = (destination / (name + ".sha256")).read_text().split()
    if len(fields) != 2 or fields[1] != name:
        raise ValueError("Release checksum does not identify the selected asset")
    return destination / name, fields[0]


def extract(archive, destination, checksum):
    if not re.fullmatch(r"[a-f0-9]{64}", checksum) or archive.stat().st_size > LIMIT:
        raise ValueError("Invalid module archive identity or size")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != checksum:
            raise ValueError("Module archive checksum mismatch")
    with tarfile.open(archive, "r:gz") as source:
        seen, members, total = set(), [], 0
        for member in source:
            path = Path(member.name)
            if (
                not member.isfile()
                or path.is_absolute()
                or ".." in path.parts
                or str(path) != member.name
                or member.name in seen
            ):
                raise ValueError("Unsafe or duplicate module archive entry")
            seen.add(member.name)
            members.append(member)
            total += member.size
            if len(members) > 10000 or total > LIMIT:
                raise ValueError("Module extraction limit exceeded")
        source.extractall(destination, members=members, filter="data")


def node_compatible(version):
    match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", version)
    if not match:
        return False
    major, minor, patch = map(int, match.groups())
    return (major == 22 and (minor, patch) >= (22, 2)) or (
        major == 24 and (minor, patch) >= (18, 0)
    )


def validate(package, module, core_commit):
    record = json.loads((package / "module.json").read_text())
    if (
        module not in MODULES
        or record.get("module") != module
        or record.get("coreCommit") != core_commit
    ):
        raise ValueError("Module requires the exact installed Edge core release")
    if (
        record.get("schemaVersion") != 1
        or record.get("platform") != "android"
        or record.get("architecture") != "any"
        or record.get("minApi") != 24
    ):
        raise ValueError("Unsupported module manifest")
    expected_source = f"zombiebox-{module}-android-any-sources.tar.gz"
    source = record.get("sourceArchive", {})
    if source.get("name") != expected_source or not re.fullmatch(
        r"[a-f0-9]{64}", source.get("sha256", "")
    ):
        raise ValueError("Matching corresponding sources are required")
    files = record.get("files", {})
    actual = {
        str(path.relative_to(package)) for path in package.rglob("*") if path.is_file()
    } - {"module.json"}
    required = {
        "LICENSE",
        "NOTICE",
        f"{module}/package.json",
        f"{module}/package-lock.json",
        f"{module}/server.mjs",
    }
    if not required.issubset(files) or actual != set(files):
        raise ValueError("Incomplete or unexpected module payload")
    for name, digest in files.items():
        path = package / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or path.is_symlink()
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise ValueError("Invalid module file path/hash")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError("Module file checksum mismatch")
        if path.suffix in (".node", ".so"):
            raise ValueError("Unexpected native npm dependency")
    return record


def configure(module, runtime):
    config = runtime / "config"
    config.mkdir(exist_ok=True, mode=0o700)
    worker = config / (module + ".json")
    if not worker.exists():
        import secrets

        values = {"token": secrets.token_hex(32)}
        if module == "youtube":
            values.update(cookie="", visitorData="", poToken="")
        else:
            values.update(listen="127.0.0.1", port=8095, dialPort=8096)
        worker.write_text(json.dumps(values) + "\n")
        worker.chmod(0o600)
    providers_file = config / "providers.json"
    providers = json.loads(providers_file.read_text())
    key = "youtube" if module == "youtube" else "youtube_receiver"
    if key not in providers:
        port = 8091 if module == "youtube" else 8095
        providers[key] = {
            "enabled": False,
            "url": f"http://127.0.0.1:{port}",
            "token": json.loads(worker.read_text())["token"],
        }
        if module == "youtube":
            providers[key]["catalogId"] = ""
        replacement = providers_file.with_suffix(".next")
        replacement.write_text(json.dumps(providers, indent=2) + "\n")
        replacement.chmod(0o600)
        replacement.replace(providers_file)


def install(package, module, runtime, prefix):
    core_release = json.loads((runtime / "current/release.json").read_text())
    validate(package, module, core_release["coreCommit"])
    destination = runtime / module
    if destination.exists() and not destination.is_symlink():
        raise ValueError("Existing source installation must be migrated explicitly")
    node = shutil.which("node")
    if not node:
        subprocess.run(["pkg", "install", "-y", "nodejs-lts"], check=True, timeout=300)
        node = shutil.which("node")
    if not node or not node_compatible(
        subprocess.check_output([node, "--version"], text=True).strip()
    ):
        raise ValueError(
            "A supported native Termux Node 22.22.2+ or 24.18.0+ is required"
        )
    subprocess.run(
        [node, "--check", str(package / module / "server.mjs")], check=True, timeout=15
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
    configure(module, runtime)
    next_link = directory / "current.next"
    next_link.unlink(missing_ok=True)
    next_link.symlink_to(release)
    next_link.replace(directory / "current")
    replacement = runtime / (module + ".next")
    replacement.unlink(missing_ok=True)
    replacement.symlink_to(directory / "current" / module)
    replacement.replace(destination)
    if module == "youtube":
        command = 'export ZOMBIE_YOUTUBE_CONFIG="$HOME/.zombie/config/youtube.json"\nexec node --max-old-space-size=128 "$HOME/.zombie/youtube/server.mjs"\n'
    else:
        command = 'export ZOMBIE_YOUTUBE_RECEIVER_CONFIG="$HOME/.zombie/config/youtube-receiver.json"\nexec node --max-old-space-size=192 "$HOME/.zombie/youtube-receiver/server.mjs"\n'
    (service / "run").write_text(
        "#!/data/data/com.termux/files/usr/bin/sh\nset -eu\nexec 2>&1\n" + command
    )
    (service / "run").chmod(0o700)
    print(
        f"Installed {module} stopped; enable its provider and start zombie-{module} explicitly"
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
        parser.error("Local bundles require an independently verified SHA256")
    if os.environ.get("PREFIX") != "/data/data/com.termux/files/usr":
        raise SystemExit("Run inside the standard Termux application")
    api = int(
        subprocess.check_output(["getprop", "ro.build.version.sdk"], text=True).strip()
    )
    if api < 24:
        raise SystemExit("This module needs Android API24 or newer")
    runtime = Path.home() / ".zombie"
    if not (runtime / "current/release.json").is_file():
        raise SystemExit("Install the matching prebuilt Edge core first")
    os.umask(0o077)
    with (runtime / "install.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with tempfile.TemporaryDirectory(prefix="zombie-node-module-") as temporary:
            staging = Path(temporary)
            bundle, digest = (
                (args.bundle, args.sha256)
                if args.bundle
                else download(args.version, args.module, staging)
            )
            package = staging / "package"
            package.mkdir()
            extract(bundle, package, digest)
            install(package, args.module, runtime, Path(os.environ["PREFIX"]))


if __name__ == "__main__":
    main()
