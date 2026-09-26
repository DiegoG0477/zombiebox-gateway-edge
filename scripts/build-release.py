#!/usr/bin/env python3
"""Cross-build Android/Bionic PIE assets on Linux with a pinned NDK; never publish."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from audit_android import audit
from release_sources import collect

ROOT = Path(__file__).resolve().parents[1]
NDK_VERSION = "28.2.13676358"


def build(core, ndk, output, version, arch):
    triple, goarch = (
        ("aarch64-linux-android", "arm64")
        if arch == "arm64"
        else ("armv7a-linux-androideabi", "arm")
    )
    compiler = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin" / (triple + "24-clang")
    if not compiler.is_file():
        raise ValueError(f"Missing Linux NDK compiler: {compiler}")
    with tempfile.TemporaryDirectory(prefix="zombie-edge-") as temporary:
        package = Path(temporary)
        (package / "bin").mkdir()
        env = {
            **os.environ,
            "GOOS": "android",
            "GOARCH": goarch,
            "GOARM": "7",
            "CGO_ENABLED": "1",
            "CC": str(compiler),
            "GOMAXPROCS": "2",
            "GOTOOLCHAIN": "go1.25.6",
        }
        subprocess.run(
            [
                "go",
                "build",
                "-p=2",
                "-trimpath",
                "-buildmode=pie",
                "-o",
                str(package / "bin/zombied"),
                "./cmd/zombied",
            ],
            cwd=core / "gateway",
            env=env,
            check=True,
        )
        binary_audit = audit(package / "bin/zombied", ndk, arch)
        for name in (
            "edge.sh",
            "install.sh",
            "scripts/doctor.py",
            "scripts/install-module.py",
            "scripts/install-node-module.py",
            "scripts/install-binary.py",
            "LICENSE",
            "NOTICE",
            "runtime/zombied.sh",
            "runtime/zombiebox.sh",
        ):
            target = package / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        (package / "licenses").mkdir()
        shutil.copy2(
            core / "docs/licenses/go-qrcode-LICENSE",
            package / "licenses/go-qrcode-LICENSE",
        )
        shutil.copy2(
            core / "docs/licenses/DIAL-LICENSE", package / "licenses/DIAL-LICENSE"
        )
        for name in (
            "miekg-dns-LICENSE",
            "golang-x-net-LICENSE",
            "golang-x-sys-LICENSE",
        ):
            shutil.copy2(core / "docs/licenses" / name, package / "licenses" / name)
        shutil.copy2(
            core / "third_party/THIRD_PARTY_NOTICES.md",
            package / "THIRD_PARTY_NOTICES.md",
        )
        # The bundled SQLite driver is compiled into this executable.
        go_cache = Path(
            subprocess.check_output(
                ["go", "env", "GOMODCACHE"], env=env, text=True
            ).strip()
        )
        shutil.copy2(
            go_cache / "github.com/mattn/go-sqlite3@v1.14.32/LICENSE",
            package / "licenses/go-sqlite3-LICENSE",
        )
        go_root = Path(
            subprocess.check_output(["go", "env", "GOROOT"], env=env, text=True).strip()
        )
        shutil.copy2(go_root / "LICENSE", package / "licenses/go-LICENSE")
        shutil.copy2(ndk / "NOTICE", package / "licenses/ndk-NOTICE")
        shutil.copy2(
            ndk / "NOTICE.toolchain", package / "licenses/ndk-NOTICE.toolchain"
        )
        subprocess.run(
            [
                "python3",
                str(core / "scripts/generate-probes.py"),
                "--output",
                str(package / "probes"),
            ],
            check=True,
        )
        subprocess.run(
            [
                "python3",
                str(core / "scripts/generate-extended-probes.py"),
                "--output",
                str(package / "probes"),
            ],
            check=True,
        )
        source_archive = collect(
            package / "bin/zombied",
            core,
            ROOT,
            env,
            output / f"zombiebox-gateway-android-{arch}-sources.tar.gz",
        )
        manifest = {
            "schemaVersion": 1,
            "version": version,
            "platform": "android",
            "architecture": arch,
            "minApi": 24,
            "ndk": NDK_VERSION,
            "go": "1.25.6",
            "coreCommit": subprocess.check_output(
                ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
            ).strip(),
            "edgeCommit": subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
            ).strip(),
            "edgeDirty": bool(
                subprocess.check_output(
                    ["git", "-C", str(ROOT), "status", "--porcelain"], text=True
                ).strip()
            ),
            "publicationReady": False,
            "sourceArchive": source_archive,
            "distributionScope": "core_and_probes_only",
            "binaryAudit": binary_audit,
            "files": {
                str(path.relative_to(package)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(package.rglob("*"))
                if path.is_file()
            },
        }
        (package / "release.json").write_text(json.dumps(manifest, indent=2) + "\n")
        asset = output / f"zombiebox-gateway-android-{arch}.tar.gz"
        with tarfile.open(asset, "w:gz") as archive:
            for path in sorted(package.rglob("*")):
                if path.is_file():
                    archive.add(
                        path, arcname=str(path.relative_to(package)), recursive=False
                    )
        asset.with_name(asset.name + ".sha256").write_text(
            hashlib.sha256(asset.read_bytes()).hexdigest() + "  " + asset.name + "\n"
        )
        print(f"Built {asset}; Android execution is not verified by cross-compilation.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--arch", choices=("armv7", "arm64"), required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    if not re.fullmatch(
        r"v[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9.-]+)?", args.version
    ):
        raise SystemExit("Use an explicit version, never latest")
    ndk = args.ndk.resolve()
    if f"Pkg.Revision = {NDK_VERSION}" not in (ndk / "source.properties").read_text():
        raise SystemExit(f"Use Android NDK {NDK_VERSION}")
    core = Path(
        subprocess.check_output(
            ["python3", "scripts/dependencies.py", "check", "gateway-core"],
            cwd=ROOT,
            text=True,
        ).strip()
    )
    args.output.mkdir(parents=True, exist_ok=True)
    asset = args.output / f"zombiebox-gateway-android-{args.arch}.tar.gz"
    if asset.exists():
        raise SystemExit("Output already exists; use a fresh version directory")
    build(core, ndk, args.output.resolve(), args.version, args.arch)


if __name__ == "__main__":
    main()
