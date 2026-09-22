#!/usr/bin/env python3
"""Build pinned optional Go modules as Android/Bionic PIEs, with matching sources."""

import argparse
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path

from audit_android import audit
from release_sources import linked_modules

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "mediamtx": ("048255986f7e04b859b4c4efe651448ec785ecd4", "1.21.1"),
    "threadfin": ("6b9c0ccf16164eb362af0a44660228267734c5aa", "1.2.40"),
}


def archive(folder, output):
    with tarfile.open(output, "x:gz") as target:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                target.add(path, arcname=str(path.relative_to(folder)), recursive=False)
    output.with_name(output.name + ".sha256").write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n"
    )


def collect_dependencies(binary, source, sources, package, env):
    metadata = subprocess.check_output(
        ["go", "version", "-m", str(binary)], env=env, text=True
    )
    entries = []
    for index, (module, version, checksum) in enumerate(linked_modules(metadata)):
        record = json.loads(
            subprocess.check_output(
                ["go", "mod", "download", "-json", module + "@" + version],
                cwd=source,
                env=env,
                text=True,
            )
        )
        if record.get("Error") or record.get("Sum") != checksum:
            raise ValueError("Linked dependency source checksum mismatch")
        name = f"module-{index:03d}"
        shutil.copy2(record["Zip"], sources / (name + ".zip"))
        notices = []
        with zipfile.ZipFile(record["Zip"]) as module_zip:
            for entry in module_zip.infolist():
                if Path(entry.filename).name.upper().split(".")[0] not in (
                    "LICENSE",
                    "LICENCE",
                    "COPYING",
                    "NOTICE",
                    "PATENTS",
                ):
                    continue
                if entry.file_size > 262144:
                    raise ValueError("Oversized dependency notice")
                notice = f"licenses/{name}-{len(notices)}.txt"
                (package / notice).write_bytes(module_zip.read(entry))
                notices.append(notice)
        if not notices:
            raise ValueError(
                "Linked dependency needs an explicit notice review: " + module
            )
        entries.append(
            dict(
                module=module,
                version=version,
                goSum=checksum,
                source=name + ".zip",
                notices=notices,
            )
        )
    return entries


def build(args, core):
    commit, version = MODULES[args.module]
    upstream = core / "third_party/sources" / args.module
    actual = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != commit:
        raise ValueError("Restore the exact locked reference before building")
    ndk = args.ndk.resolve()
    if "Pkg.Revision = 28.2.13676358" not in (ndk / "source.properties").read_text():
        raise ValueError("Use the pinned NDK28.2.13676358")
    triple = (
        "aarch64-linux-android" if args.arch == "arm64" else "armv7a-linux-androideabi"
    )
    compiler = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin" / (triple + "24-clang")
    env = {
        **os.environ,
        "GOTOOLCHAIN": "go1.26.0",
        "GOOS": "android",
        "GOARCH": "arm64" if args.arch == "arm64" else "arm",
        "GOARM": "7",
        "CGO_ENABLED": "1",
        "CC": str(compiler),
        "GOMAXPROCS": "2",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    stem = f"zombiebox-{args.module}-android-{args.arch}"
    if any(
        (args.output / (stem + suffix)).exists()
        for suffix in (".tar.gz", "-sources.tar.gz")
    ):
        raise ValueError("Use a new output directory; release artifacts are immutable")
    with tempfile.TemporaryDirectory(prefix="zombie-edge-module-") as temporary:
        root = Path(temporary)
        source, package, sources = root / "upstream", root / "package", root / "sources"
        for path in (source, package / "bin", package / "licenses", sources):
            path.mkdir(parents=True)
        exported = subprocess.check_output(
            ["git", "-C", str(upstream), "archive", commit]
        )
        with tarfile.open(fileobj=io.BytesIO(exported)) as source_tar:
            source_tar.extractall(source, filter="data")
        if args.module == "mediamtx":
            subprocess.run(
                ["git", "apply", str(core / "wrappers/mediamtx/android.patch")],
                cwd=source,
                check=True,
            )
            (source / "internal/core/VERSION").write_text("v1.21.1\n")
            (source / "internal/servers/hls/hls.min.js").write_text(
                "/* Standalone web player is not included in Edge. */\n"
            )
            shutil.copy2(
                core / "wrappers/mediamtx/mediamtx.yml", package / "mediamtx.yml"
            )
        if args.module == "threadfin":
            entry = source / "threadfin.go"
            old = 'Repo: "Threadfin", Update: true'
            if entry.read_text().count(old) != 1:
                raise ValueError("Threadfin updater patch no longer matches")
            entry.write_text(
                entry.read_text().replace(old, 'Repo: "Threadfin", Update: false')
            )
        binary = package / "bin" / args.module
        subprocess.run(
            [
                "go",
                "build",
                "-p=2",
                "-mod=readonly",
                "-trimpath",
                "-buildvcs=false",
                "-buildmode=pie",
                "-ldflags=-s -w -checklinkname=0",
                "-o",
                str(binary),
                ".",
            ],
            cwd=source,
            env=env,
            check=True,
        )
        evidence = audit(binary, ndk, args.arch)
        shutil.copy2(source / "LICENSE", package / "licenses/upstream-LICENSE")
        shutil.copy2(ndk / "NOTICE", package / "licenses/ndk-NOTICE")
        shutil.copy2(
            ndk / "NOTICE.toolchain", package / "licenses/ndk-NOTICE.toolchain"
        )
        go_root = Path(
            subprocess.check_output(["go", "env", "GOROOT"], env=env, text=True).strip()
        )
        shutil.copy2(go_root / "LICENSE", package / "licenses/go-LICENSE")
        dependencies = collect_dependencies(binary, source, sources, package, env)
        archive(source, sources / "upstream-patched.tar.gz")
        with tarfile.open(sources / "go-standard-library.tar.gz", "x:gz") as target:
            for name in ("src", "LICENSE", "PATENTS", "VERSION"):
                target.add(go_root / name, arcname="go/" + name)
        record = dict(
            schemaVersion=1,
            module=args.module,
            moduleVersion=version,
            upstreamCommit=commit,
            platform="android",
            architecture=args.arch,
            minApi=24,
            go="1.26.0",
            ndk="28.2.13676358",
            binaryAudit=evidence,
            dependencies=dependencies,
            runtimeVerified=False,
        )
        (sources / "sources.json").write_text(json.dumps(record, indent=2) + "\n")
        shutil.copy2(Path(__file__), sources / "build-module.py")
        shutil.copy2(ROOT / "scripts/audit_android.py", sources / "audit_android.py")
        shutil.copy2(
            ROOT / "scripts/release_sources.py", sources / "release_sources.py"
        )
        shutil.copy2(ROOT / "scripts/install-binary.py", sources / "install-binary.py")
        for name in ("LICENSE", "NOTICE"):
            shutil.copy2(ROOT / name, sources / name)
        record["builderCommit"] = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip()
        record["coreCommit"] = subprocess.check_output(
            ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
        ).strip()
        record["candidateOnly"] = args.allow_dirty
        record["buildRecipeSha256"] = hashlib.sha256(
            Path(__file__).read_bytes()
        ).hexdigest()
        (sources / "sources.json").write_text(json.dumps(record, indent=2) + "\n")
        (sources / "BUILDING.md").write_text(
            "Extract upstream-patched.tar.gz; use Go1.26.0 with GOOS=android, CGO_ENABLED=1 and the NDK28.2.13676358 API24 compiler. Build with -buildmode=pie -trimpath -ldflags='-s -w -checklinkname=0'. Select GOARCH=arm64 or GOARCH=arm GOARM=7. Dependency ZIP sources and notices are included. No signing key is needed.\n"
        )
        source_asset = args.output / (stem + "-sources.tar.gz")
        archive(sources, source_asset)
        record["sourceArchive"] = dict(
            name=source_asset.name,
            sha256=hashlib.sha256(source_asset.read_bytes()).hexdigest(),
        )
        record["files"] = {
            str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(package.rglob("*"))
            if p.is_file()
        }
        (package / "module.json").write_text(json.dumps(record, indent=2) + "\n")
        archive(package, args.output / (stem + ".tar.gz"))
    print(f"Built {stem}; Android execution remains unverified.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", choices=MODULES, required=True)
    parser.add_argument("--arch", choices=("arm64", "armv7"), required=True)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Local candidate only; do not publish",
    )
    args = parser.parse_args()
    core = Path(
        subprocess.check_output(
            ["python3", str(ROOT / "scripts/dependencies.py"), "path", "gateway-core"],
            cwd=ROOT,
            text=True,
        ).strip()
    )
    if not args.allow_dirty:
        for repository in (ROOT, core):
            if subprocess.check_output(
                ["git", "-C", str(repository), "status", "--porcelain"], text=True
            ).strip():
                raise ValueError(
                    "Commit sources first or explicitly use --allow-dirty for a local candidate"
                )
    build(args, core.resolve())


if __name__ == "__main__":
    main()
