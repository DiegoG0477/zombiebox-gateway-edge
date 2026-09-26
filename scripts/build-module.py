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
import urllib.request
import zipfile
from pathlib import Path

from audit_android import audit
from release_sources import linked_modules
from reviewed_notices import collect_reviewed

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "mediamtx": ("048255986f7e04b859b4c4efe651448ec785ecd4", "1.21.1"),
    "threadfin": ("6b9c0ccf16164eb362af0a44660228267734c5aa", "1.2.40"),
    "spotify": ("6a3e25019de8d2893b3fa26b0273d8cc376241c5", "0.10.2"),
}
SPOTIFY_PATCHES = ("licensed-vorbis.patch", "stop-key-refusal-skip.patch")


def archive(folder, output):
    with tarfile.open(output, "x:gz") as target:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                target.add(path, arcname=str(path.relative_to(folder)), recursive=False)
    output.with_name(output.name + ".sha256").write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n"
    )


def collect_dependencies(binary, source, sources, package, env, target="."):
    metadata = subprocess.check_output(
        ["go", "version", "-m", str(binary)], env=env, text=True
    )
    packages = {}
    inventory = subprocess.check_output(
        [
            "go",
            "list",
            "-mod=readonly",
            "-deps",
            "-f",
            "{{if .Module}}{{.Module.Path}} {{.ImportPath}}{{end}}",
            target,
        ],
        cwd=source,
        env=env,
        text=True,
    )
    for line in inventory.splitlines():
        if line.strip():
            module, imported = line.split()
            packages.setdefault(module, set()).add(imported)
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
        review = {}
        if notices:
            source_name = name + ".zip"
            shutil.copy2(record["Zip"], sources / source_name)
        else:
            source_name = name + "-reviewed-packages.zip"
            notice = f"licenses/{name}-inline.txt"
            review = collect_reviewed(
                module,
                version,
                packages.get(module, set()),
                record["Zip"],
                sources / source_name,
                package / notice,
            )
            notices.append(notice)
        entries.append(
            dict(
                module=module,
                version=version,
                goSum=checksum,
                source=source_name,
                sourceSha256=hashlib.sha256(
                    (sources / source_name).read_bytes()
                ).hexdigest(),
                notices=notices,
                **review,
            )
        )
    return entries


def termux_spotify_libraries(arch, directory):
    lock = json.loads((ROOT / "packaging/spotify-termux-libs.json").read_text())
    prefix = directory / "data/data/com.termux/files/usr"
    directory.mkdir()
    for name, (version, path, checksum) in lock[
        "aarch64" if arch == "arm64" else "arm"
    ].items():
        if not path.startswith("pool/main/") or ".." in Path(path).parts:
            raise ValueError("Untrusted Termux package path")
        with urllib.request.urlopen(lock["repository"] + path, timeout=40) as response:
            content = response.read(12 << 20)
            if response.read(1):
                raise ValueError("Oversized Termux build package")
        if hashlib.sha256(content).hexdigest() != checksum:
            raise ValueError(f"Termux package changed: {name} {version}")
        archive_path = directory / (name + ".deb")
        archive_path.write_bytes(content)
        payload = subprocess.check_output(["ar", "p", str(archive_path), "data.tar.xz"])
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:xz") as source_tar:
            source_tar.extractall(directory, filter="data")
        archive_path.unlink()
    return prefix


def build(args, core):
    commit, version = MODULES[args.module]
    upstream_name = "go-librespot" if args.module == "spotify" else args.module
    upstream = core / "third_party/sources" / upstream_name
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
        "GOTOOLCHAIN": "go1.25.6" if args.module == "spotify" else "go1.26.0",
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
        for path in (package / "bin", package / "licenses", sources):
            path.mkdir(parents=True)
        if args.module == "spotify":
            subprocess.run(
                [
                    "python3",
                    str(core / "scripts/prepare-spotify-source.py"),
                    "--source",
                    str(upstream),
                    "--output",
                    str(source),
                ],
                check=True,
            )
            applied_patches = (source / "ZOMBIE_PATCHES").read_text().splitlines()
            if applied_patches != list(SPOTIFY_PATCHES):
                raise ValueError("Spotify source does not have the reviewed patch set")
            sysroot = root / "sysroot"
            prefix = termux_spotify_libraries(args.arch, sysroot)
            env.update(
                PKG_CONFIG_LIBDIR=str(prefix / "lib/pkgconfig"),
                PKG_CONFIG_SYSROOT_DIR=str(sysroot),
                GOCACHE=str(root / "go-cache"),
            )
        else:
            source.mkdir()
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
        target = "./cmd/daemon" if args.module == "spotify" else "."
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
                target,
            ],
            cwd=source,
            env=env,
            check=True,
        )
        external = None
        if args.module == "spotify":
            external = {
                name: prefix / "lib" / name
                for name in ("libFLAC.so", "libmpg123.so", "libogg.so")
            }
        evidence = audit(binary, ndk, args.arch, external)
        if args.module == "spotify":
            linked = subprocess.check_output(
                ["go", "version", "-m", str(binary)], env=env, text=True
            )
            if "github.com/xlab/vorbis-go" in linked or not all(
                name in linked
                for name in (
                    "github.com/jfreymuth/oggvorbis",
                    "github.com/jfreymuth/vorbis",
                )
            ):
                raise ValueError(
                    "Spotify binary does not link the reviewed Vorbis modules"
                )
            worker_env = {
                **env,
                "CGO_ENABLED": "0" if args.arch == "arm64" else "1",
            }
            worker = package / "bin/zombie-worker"
            subprocess.run(
                [
                    "go",
                    "build",
                    "-p=2",
                    "-trimpath",
                    "-buildvcs=false",
                    "-buildmode=pie",
                    "-ldflags=-s -w",
                    "-o",
                    str(worker),
                    "./cmd/zombie-worker",
                ],
                cwd=core / "gateway",
                env=worker_env,
                check=True,
            )
            worker_audit = audit(worker, ndk, args.arch, allow_no_libraries=True)
            worker_modules = subprocess.check_output(
                ["go", "version", "-m", str(worker)], env=worker_env, text=True
            )
            if any(line.split()[:1] == ["dep"] for line in worker_modules.splitlines()):
                raise ValueError("Spotify worker gained uncatalogued Go dependencies")
        shutil.copy2(source / "LICENSE", package / "licenses/upstream-LICENSE")
        shutil.copy2(ndk / "NOTICE", package / "licenses/ndk-NOTICE")
        shutil.copy2(
            ndk / "NOTICE.toolchain", package / "licenses/ndk-NOTICE.toolchain"
        )
        go_root = Path(
            subprocess.check_output(["go", "env", "GOROOT"], env=env, text=True).strip()
        )
        shutil.copy2(go_root / "LICENSE", package / "licenses/go-LICENSE")
        if args.module == "spotify":
            for name, origin in (
                ("libflac-Xiph", prefix / "share/doc/libflac/COPYING.Xiph"),
                ("libflac-LGPL", prefix / "share/doc/libflac/COPYING.LGPL"),
                ("libflac-GPL", prefix / "share/doc/libflac/COPYING.GPL"),
                ("libogg-copyright", prefix / "share/doc/libogg/copyright"),
                ("libmpg123-LGPL", prefix / "share/doc/libflac/COPYING.LGPL"),
            ):
                shutil.copy2(origin, package / "licenses" / name)
        dependencies = collect_dependencies(
            binary, source, sources, package, env, target
        )
        archive(source, sources / "upstream-patched.tar.gz")
        if args.module == "spotify":
            with (sources / "gateway-core.tar").open("wb") as output:
                subprocess.run(
                    ["git", "-C", str(core), "archive", "HEAD"],
                    stdout=output,
                    check=True,
                )
            for patch_name in SPOTIFY_PATCHES:
                shutil.copy2(
                    core / "wrappers/spotify/patches" / patch_name,
                    sources / patch_name,
                )
            shutil.copy2(
                core / "scripts/prepare-spotify-source.py",
                sources / "prepare-spotify-source.py",
            )
            shutil.copy2(
                ROOT / "packaging/spotify-termux-libs.json",
                sources / "spotify-termux-libs.json",
            )
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
            go="1.25.6" if args.module == "spotify" else "1.26.0",
            ndk="28.2.13676358",
            binaryAudit=evidence,
            dependencies=dependencies,
            runtimeVerified=False,
        )
        if args.module == "spotify":
            spotify_lock = json.loads(
                (ROOT / "packaging/spotify-termux-libs.json").read_text()
            )
            package_arch = "aarch64" if args.arch == "arm64" else "arm"
            record.update(
                workerAudit=worker_audit,
                externalPackages=["libflac", "libmpg123", "libogg"],
                externalPackageVersions={
                    name: entry[0] for name, entry in spotify_lock[package_arch].items()
                },
                vorbisPatch="licensed-vorbis.patch",
                sourcePatches=list(SPOTIFY_PATCHES),
            )
        (sources / "sources.json").write_text(json.dumps(record, indent=2) + "\n")
        shutil.copy2(Path(__file__), sources / "build-module.py")
        shutil.copy2(ROOT / "scripts/audit_android.py", sources / "audit_android.py")
        shutil.copy2(
            ROOT / "scripts/release_sources.py", sources / "release_sources.py"
        )
        shutil.copy2(
            ROOT / "scripts/reviewed_notices.py", sources / "reviewed_notices.py"
        )
        shutil.copytree(package / "licenses", sources / "licenses")
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
        if args.module == "spotify":
            (sources / "BUILDING.md").write_text(
                "Extract upstream-patched.tar.gz. With Go1.25.6, NDK28.2.13676358 API24 Clang and the exact SHA-locked Termux libflac/libmpg123/libogg headers and libraries in spotify-termux-libs.json, build ./cmd/daemon with GOOS=android, GOARCH=arm64 or arm GOARM=7, CGO_ENABLED=1, -buildmode=pie, -trimpath and -ldflags='-s -w -checklinkname=0'. Set PKG_CONFIG_LIBDIR to the extracted package lib/pkgconfig directory and PKG_CONFIG_SYSROOT_DIR to its extraction root. Build ./cmd/zombie-worker from gateway-core.tar with the same Go/NDK target. The matching module ZIPs, notices, both source patches and Go standard-library source are included. Do not substitute xlab/vorbis-go. No signing key is needed.\n"
            )
        else:
            (sources / "BUILDING.md").write_text(
                "Extract upstream-patched.tar.gz; use Go1.26.0 with GOOS=android, CGO_ENABLED=1 and the NDK28.2.13676358 API24 compiler. Build with -buildmode=pie -trimpath -ldflags='-s -w -checklinkname=0'. Select GOARCH=arm64 or GOARCH=arm GOARM=7. Dependency ZIP sources and notices are included. No signing key is needed.\n\n"
                "The reviewed-packages ZIP is a source subset, not a Go proxy ZIP: goSum identifies the verified original module while sourceSha256 identifies this subset. Only aes/keywrap from benburkert/openpgp is compiled. Its exact source, tests and inline BSD notice are supplied; unrelated OpenPGP packages are excluded. A normal rebuild downloads the original module using upstream go.sum. For an offline rebuild, populate a local module directory with the supplied keywrap sources and map it using a local go.mod replacement; record that local replacement separately from the original binary provenance.\n"
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
