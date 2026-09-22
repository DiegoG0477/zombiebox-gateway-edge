#!/usr/bin/env python3
"""Install an explicitly selected, checksum-verified optional Android module."""

import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

LIMIT = 256 << 20
MODULES = {"threadfin": "6b9c0ccf16164eb362af0a44660228267734c5aa"}


def download(version, module, arch, directory):
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9.-]+)?", version):
        raise ValueError("Select an explicit release version, never latest")
    name = f"zombiebox-{module}-android-{arch}.tar.gz"
    base = f"https://github.com/DiegoG0477/zombiebox-gateway-edge/releases/download/{version}/"
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
    return record


def install(package, module, arch, api, runtime, prefix):
    validate(package, module, arch, api)
    if not (runtime / "bin/zombied").is_file():
        raise ValueError("Install the Edge core first")
    binary = package / "bin" / module
    binary.chmod(0o700)
    subprocess.run(
        [str(binary), "-h"],
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
    (runtime / "threadfin").mkdir(exist_ok=True, mode=0o700)
    (service / "run").write_text(
        "#!/data/data/com.termux/files/usr/bin/sh\n"
        "export GOMEMLIMIT=128MiB GOMAXPROCS=1\n"
        'exec "$HOME/.zombie/bin/threadfin" -config "$HOME/.zombie/threadfin" -bind 127.0.0.1 -port 34400\n'
    )
    (service / "run").chmod(0o700)
    print(
        "Installed Threadfin stopped; configuration preserved. Start with zombiebox start zombie-threadfin."
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
