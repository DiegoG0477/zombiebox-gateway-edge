#!/usr/bin/env python3
"""Package a locked, architecture-neutral Edge Node worker with its npm sources."""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = ("youtube", "youtube-receiver")
SUPPLEMENTAL_NOTICES = {
    "node_modules/@bufbuild/protobuf": "bufbuild-protobuf-LICENSE",
    "node_modules/cookie-signature": "cookie-signature-LICENSE",
    "node_modules/filelist": "filelist-LICENSE",
    "node_modules/jake": "jake-LICENSE",
    "node_modules/yt-cast-receiver": "yt-cast-receiver-LICENSE",
}
RUNTIME_FILES = {
    "youtube": (
        "server.mjs",
        "worker.mjs",
        "interpreter.mjs",
        "formats.mjs",
        "browse.mjs",
    ),
    "youtube-receiver": (
        "server.mjs",
        "bridge.mjs",
        "completion.mjs",
        "receiver.mjs",
        "player.mjs",
    ),
}


def archive(directory, target):
    with tarfile.open(target, "w:gz") as bundle:
        for path in sorted(directory.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"Unexpected symlink in release: {path}")
            if path.is_file():
                bundle.add(
                    path, arcname=str(path.relative_to(directory)), recursive=False
                )
    target.with_name(target.name + ".sha256").write_text(
        hashlib.sha256(target.read_bytes()).hexdigest() + "  " + target.name + "\n"
    )


def npm_source(item):
    name, entry = item
    url = entry["resolved"]
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != "registry.npmjs.org":
        raise ValueError(f"Untrusted npm source URL for {name}")
    algorithm, expected = entry["integrity"].split("-", 1)
    if algorithm != "sha512":
        raise ValueError(f"Unsupported npm integrity for {name}")
    with urllib.request.urlopen(url, timeout=30) as response:
        data = response.read(32 << 20)
        if response.read(1):
            raise ValueError(f"Oversized npm source for {name}")
    if hashlib.sha512(data).digest() != base64.b64decode(expected, validate=True):
        raise ValueError(f"npm source integrity mismatch for {name}")
    return name, entry, data


def collect_notices(packages, worker, package, sources):
    """Require a preserved upstream or reviewed supplemental notice for every npm package."""
    notices = []
    for name, entry in packages:
        directory = worker / name
        metadata = json.loads((directory / "package.json").read_text())
        files = [
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.name.lower().startswith(
                ("license", "licence", "copying", "notice")
            )
        ]
        if files:
            references = [str(path.relative_to(package)) for path in sorted(files)]
        else:
            supplemental = SUPPLEMENTAL_NOTICES.get(name)
            if not supplemental:
                raise ValueError(f"Missing third-party notice: {name}")
            origin = ROOT / "notices/node" / supplemental
            target = package / "licenses" / supplemental
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(origin, target)
            source_notice = sources / "licenses" / supplemental
            source_notice.parent.mkdir(exist_ok=True)
            shutil.copy2(origin, source_notice)
            references = [str(target.relative_to(package))]
        notices.append(
            {
                "package": name,
                "version": entry["version"],
                "license": metadata.get("license", entry.get("license", "see notice")),
                "noticeFiles": references,
            }
        )
    (package / "THIRD_PARTY_NOTICES.json").write_text(
        json.dumps(notices, indent=2) + "\n"
    )
    (sources / "THIRD_PARTY_NOTICES.json").write_text(
        json.dumps(notices, indent=2) + "\n"
    )
    return notices


def build(module, version, output, node_dir, core):
    if module not in MODULES:
        raise ValueError("Unsupported Node module")
    node = node_dir / "node"
    npm = node_dir / "npm"
    detected = subprocess.check_output([str(node), "--version"], text=True).strip()
    if detected != "v24.18.0":
        raise ValueError("Build with the reviewed Node 24.18.0 toolchain")
    if not npm.is_file():
        raise ValueError("Matching npm toolchain is missing")
    source = core / "wrappers" / module
    lock = json.loads((source / "package-lock.json").read_text())
    packages = [(name, item) for name, item in lock["packages"].items() if name]
    if not packages or any(
        "resolved" not in item or "integrity" not in item for _, item in packages
    ):
        raise ValueError("npm lock lacks complete source identities")
    stem = f"zombiebox-{module}-android-any"
    output.mkdir(parents=True, exist_ok=True)
    if any(
        (output / (stem + suffix)).exists() for suffix in (".tar.gz", "-sources.tar.gz")
    ):
        raise ValueError("Release assets are immutable; use a new output directory")
    with tempfile.TemporaryDirectory(prefix="zombie-edge-node-") as temporary:
        root = Path(temporary)
        package, sources = root / "package", root / "sources"
        worker = package / module
        worker.mkdir(parents=True)
        sources.mkdir()
        for name in (*RUNTIME_FILES[module], "package.json", "package-lock.json"):
            shutil.copy2(source / name, worker / name)
        env = {**os.environ, "PATH": str(node_dir) + os.pathsep + os.environ["PATH"]}
        subprocess.run(
            [
                str(npm),
                "ci",
                "--ignore-scripts",
                "--omit=dev",
                "--no-bin-links",
                "--no-audit",
                "--no-fund",
            ],
            cwd=worker,
            env=env,
            check=True,
        )
        for path in worker.rglob("*"):
            if path.is_symlink() or (
                path.is_file()
                and (
                    path.suffix in (".node", ".so")
                    or path.read_bytes()[:4] == b"\x7fELF"
                )
            ):
                raise ValueError(
                    f"Native or linked npm payload is not portable: {path}"
                )
        shutil.copy2(ROOT / "LICENSE", package / "LICENSE")
        shutil.copy2(ROOT / "NOTICE", package / "NOTICE")
        for path in source.glob("*.test.mjs"):
            shutil.copy2(path, sources / path.name)
        for name in (*RUNTIME_FILES[module], "package.json", "package-lock.json"):
            shutil.copy2(source / name, sources / name)
        notice_inventory = collect_notices(packages, worker, package, sources)
        receipts = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for index, (name, entry, data) in enumerate(pool.map(npm_source, packages)):
                filename = f"npm-{index:03d}.tgz"
                (sources / filename).write_bytes(data)
                receipts.append(
                    {
                        "path": name,
                        "version": entry["version"],
                        "archive": filename,
                        "sha512": entry["integrity"],
                    }
                )
        source_record = {
            "schemaVersion": 1,
            "module": module,
            "version": version,
            "coreCommit": subprocess.check_output(
                ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
            ).strip(),
            "edgeCommit": subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
            ).strip(),
            "npmPackages": receipts,
            "thirdPartyNotices": len(notice_inventory),
            "runtimeSource": "https://nodejs.org/dist/v24.18.0/node-v24.18.0.tar.xz",
            "runtimeProvidedBy": "Termux nodejs-lts (not bundled)",
        }
        (sources / "sources.json").write_text(
            json.dumps(source_record, indent=2) + "\n"
        )
        shutil.copy2(Path(__file__), sources / "build-node-module.py")
        (sources / "BUILDING.md").write_text(
            "Install Node 24.18.0 and npm. Place the worker files beside package-lock.json, "
            "then run npm ci --ignore-scripts --omit=dev --no-bin-links --no-audit --no-fund. "
            "The verified npm tarballs in this archive are the complete dependency source set. "
            "A native Termux Node runtime is installed separately.\n"
        )
        shutil.copy2(ROOT / "LICENSE", sources / "LICENSE")
        shutil.copy2(ROOT / "NOTICE", sources / "NOTICE")
        source_asset = output / (stem + "-sources.tar.gz")
        archive(sources, source_asset)
        record = {
            **{
                key: source_record[key]
                for key in (
                    "schemaVersion",
                    "module",
                    "version",
                    "coreCommit",
                    "edgeCommit",
                )
            },
            "platform": "android",
            "architecture": "any",
            "minApi": 24,
            "nodeRange": ">=22.22.2 <23 || >=24.18.0 <25",
            "sourceArchive": {
                "name": source_asset.name,
                "sha256": hashlib.sha256(source_asset.read_bytes()).hexdigest(),
            },
            "files": {
                str(path.relative_to(package)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(package.rglob("*"))
                if path.is_file()
            },
            "runtimeVerified": False,
        }
        (package / "module.json").write_text(json.dumps(record, indent=2) + "\n")
        archive(package, output / (stem + ".tar.gz"))
    print(f"Built source-closed {stem}; Android execution remains unverified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=MODULES, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--node-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(
        r"v[0-9]+\.[0-9]+\.[0-9]+(?:[.-][A-Za-z0-9.-]+)?", args.version
    ):
        parser.error("Use an explicit release version")
    core = Path(
        subprocess.check_output(
            ["python3", str(ROOT / "scripts/dependencies.py"), "check", "gateway-core"],
            text=True,
        ).strip()
    )
    for repository in (ROOT, core):
        if subprocess.check_output(
            [
                "git",
                "-C",
                str(repository),
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
            text=True,
        ).strip():
            raise ValueError("Commit both sources before building release assets")
    build(
        args.module,
        args.version,
        args.output.resolve(),
        args.node_dir.resolve(),
        core.resolve(),
    )


if __name__ == "__main__":
    main()
