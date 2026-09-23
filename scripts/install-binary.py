#!/usr/bin/env python3
"""Validate an Android bundle, stage it, then install the native runit service."""

import fcntl
import hashlib
import json
import os
import re
import secrets
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path


def android_elf(binary, arch):
    elf_class, machine, linker = (
        (2, 183, b"/system/bin/linker64\0")
        if arch == "arm64"
        else (1, 40, b"/system/bin/linker\0")
    )
    if (
        len(binary) < 64
        or binary[:6] != b"\x7fELF" + bytes([elf_class, 1])
        or struct.unpack_from("<HH", binary, 16) != (3, machine)
    ):
        return False
    offset = struct.unpack_from(
        "<Q" if elf_class == 2 else "<I", binary, 32 if elf_class == 2 else 28
    )[0]
    entry_size, count = struct.unpack_from("<HH", binary, 54 if elf_class == 2 else 42)
    if (
        count > 128
        or entry_size < (56 if elf_class == 2 else 32)
        or offset + count * entry_size > len(binary)
    ):
        return False
    for index in range(count):
        entry = offset + index * entry_size
        if struct.unpack_from("<I", binary, entry)[0] != 3:
            continue
        start = struct.unpack_from(
            "<Q" if elf_class == 2 else "<I",
            binary,
            entry + (8 if elf_class == 2 else 4),
        )[0]
        size = struct.unpack_from(
            "<Q" if elf_class == 2 else "<I",
            binary,
            entry + (32 if elf_class == 2 else 16),
        )[0]
        return size == len(linker) and binary[start : start + size] == linker
    return False


def validate(package, arch, api):
    manifest = json.loads((package / "release.json").read_text())
    if (
        arch not in ("arm64", "armv7")
        or manifest.get("platform") != "android"
        or manifest.get("architecture") != arch
    ):
        raise ValueError("Release is not built for this Android userland")
    if manifest.get("schemaVersion") != 1 or manifest.get("minApi") != 24 or api < 24:
        raise ValueError("Unsupported Android release contract")
    version = manifest.get("version", "")
    if not re.fullmatch(r"v[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9.-]+)?", version):
        raise ValueError("Invalid release version")
    if not re.fullmatch(r"[a-f0-9]{40}", manifest.get("coreCommit", "")):
        raise ValueError("Release must identify its exact core source")
    files = manifest.get("files", {})
    required = {
        "bin/zombied",
        "edge.sh",
        "install.sh",
        "scripts/doctor.py",
        "scripts/install-binary.py",
        "LICENSE",
        "NOTICE",
        "licenses/go-qrcode-LICENSE",
        "licenses/go-sqlite3-LICENSE",
        "licenses/go-LICENSE",
        "licenses/ndk-NOTICE",
        "licenses/ndk-NOTICE.toolchain",
        "runtime/zombied.sh",
        "runtime/zombiebox.sh",
    }
    required.update(
        "probes/" + name
        for name in (
            "baseline-360.mp4",
            "baseline-480.mp4",
            "main-720.mp4",
            "high-720.mp4",
            "high-1080.mp4",
            "aac.m4a",
            "baseline.ts",
            "fragmented.mp4",
        )
    )
    actual = {
        str(path.relative_to(package)) for path in package.rglob("*") if path.is_file()
    } - {"release.json"}
    if not required.issubset(files) or actual != set(files):
        raise ValueError("Incomplete or unexpected release files")
    for name, expected in files.items():
        path = package / name
        if Path(name).is_absolute() or ".." in Path(name).parts or path.is_symlink():
            raise ValueError("Unsafe release path")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Release checksum mismatch: {name}")
    binary = (package / "bin/zombied").read_bytes()
    if not android_elf(binary, arch):
        raise ValueError("Expected an Android PIE executable for the selected ABI")
    return manifest


def write_new(path, content, mode=0o600):
    if not path.exists():
        with path.open("x") as stream:
            stream.write(content)
        path.chmod(mode)


def install(package, arch, api, version, repository):
    prefix = Path(os.environ["PREFIX"])
    runtime = Path.home() / ".zombie"
    manifest = validate(package, arch, api)
    if version != "local" and version != manifest["version"]:
        raise ValueError("Downloaded version differs from the requested version")
    # Runs only after every checksum and target check, before stopping the old service.
    binary = package / "bin/zombied"
    binary.chmod(0o700)
    subprocess.run(
        [str(binary), "-h"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
        timeout=15,
    )
    for name in (
        "releases",
        "bin",
        "config",
        "state",
        "media",
        "cache",
        "logs",
        "probes",
    ):
        (runtime / name).mkdir(parents=True, exist_ok=True, mode=0o700)
    release = Path(
        tempfile.mkdtemp(prefix=manifest["version"] + "-", dir=runtime / "releases")
    )
    shutil.copytree(package, release, dirs_exist_ok=True)
    service = prefix / "var/service/zombied"
    service.mkdir(parents=True, exist_ok=True)
    if (service / "run").exists():
        subprocess.run(["sv", "-w", "15", "down", str(service)], check=True, timeout=20)
    (service / "down").touch()
    write_new(runtime / "config/providers.json", "{}\n")
    write_new(
        runtime / "config/runtime.env",
        "ZOMBIE_LISTEN=0.0.0.0:8090\nZOMBIE_RELAY_ADMIN_TOKEN="
        + secrets.token_hex(32)
        + "\n",
    )
    write_new(
        runtime / "config/operator.code",
        f"{secrets.randbelow(900000) + 100000:06d}\n",
    )
    current = runtime / "current"
    temporary = runtime / "current.next"
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(release)
    temporary.replace(current)
    # Keep the conventional path used by diagnostics and optional source modules.
    binary_link = runtime / "bin/zombied.next"
    binary_link.unlink(missing_ok=True)
    binary_link.symlink_to(current / "bin/zombied")
    binary_link.replace(runtime / "bin/zombied")
    shutil.copy2(release / "runtime/zombied.sh", service / "run")
    (service / "run").chmod(0o700)
    launcher = prefix / "bin/zombiebox"
    shutil.copy2(release / "runtime/zombiebox.sh", launcher)
    launcher.chmod(0o700)
    (runtime / "build-info.txt").write_text(
        f"Android/{arch} API24+ {manifest['version']}\nCore: {manifest['coreCommit']}\n"
    )
    (runtime / "config/release-source.json").write_text(
        json.dumps({"repository": repository, "version": manifest["version"]}) + "\n"
    )
    print(
        "Installed Android bundle. Credentials/data preserved. Run zombiebox to start; zombiebox boot-enable is optional."
    )


if __name__ == "__main__":
    if os.environ.get("PREFIX") != "/data/data/com.termux/files/usr":
        raise SystemExit("Run inside Termux on Android")
    os.umask(0o077)
    runtime = Path.home() / ".zombie"
    runtime.mkdir(exist_ok=True, mode=0o700)
    with (runtime / "install.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SystemExit("Another Edge installation is running") from None
        install(
            Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), sys.argv[4], sys.argv[5]
        )
