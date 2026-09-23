#!/usr/bin/env python3
"""Build source-closed Android UxPlay and its shared receiver worker."""

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
from pathlib import Path

from audit_android import audit

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "57ea83411d5f7e0b38c5841987439340543f025c"
LIBRARIES = (
    "libplist-2.0.so",
    "libcrypto.so.3",
    "libgstsdp-1.0.so",
    "libgstvideo-1.0.so",
    "libgstapp-1.0.so",
    "libgstbase-1.0.so",
    "libgstreamer-1.0.so",
    "libgobject-2.0.so.0",
    "libglib-2.0.so.0",
)


def archive(folder, output):
    with tarfile.open(output, "x:gz") as target:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                target.add(path, arcname=str(path.relative_to(folder)), recursive=False)
    output.with_name(output.name + ".sha256").write_text(
        hashlib.sha256(output.read_bytes()).hexdigest() + "  " + output.name + "\n"
    )


def run(*command, **kwargs):
    subprocess.run(command, check=True, **kwargs)


def export(checkout, destination):
    commit = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    exported = subprocess.check_output(["git", "-C", str(checkout), "archive", commit])
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(exported)) as source:
        source.extractall(destination, filter="data")
    return commit


def termux_sysroot(lock, arch, destination):
    destination.mkdir()
    prefix = destination / "data/data/com.termux/files/usr"
    for name, (version, path, expected) in lock[arch].items():
        if not path.startswith("pool/main/") or ".." in Path(path).parts:
            raise ValueError("Untrusted Termux package path")
        with urllib.request.urlopen(lock["repository"] + path, timeout=40) as response:
            data = response.read(12 << 20)
            if response.read(1):
                raise ValueError("Oversized Termux package")
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Termux build library changed: {name} {version}")
        archive_path = destination / (name + ".deb")
        archive_path.write_bytes(data)
        payload = subprocess.check_output(["ar", "p", str(archive_path), "data.tar.xz"])
        with tarfile.open(fileobj=io.BytesIO(payload), mode="r:xz") as source:
            source.extractall(destination, filter="data")
        archive_path.unlink()
    return prefix


def toolchain(ndk, prefix, arch, directory):
    clang_dir = ndk / "toolchains/llvm/prebuilt/linux-x86_64/bin"
    triple = "aarch64-linux-android" if arch == "arm64" else "armv7a-linux-androideabi"
    cpu = "aarch64" if arch == "arm64" else "armv7"
    wrapper = directory / "android-clang++"
    wrapper.write_text(
        "#!/bin/sh\nexec "
        + str(clang_dir / "clang")
        + f' --target={triple}24 -stdlib=libc++ "$@" -lc++_shared\n'
    )
    wrapper.chmod(0o700)
    cmake = directory / "android-toolchain.cmake"
    cmake.write_text(
        "set(CMAKE_SYSTEM_NAME Linux)\n"
        f"set(CMAKE_SYSTEM_PROCESSOR {cpu})\n"
        f"set(CMAKE_C_COMPILER {clang_dir / (triple + '24-clang')})\n"
        f"set(CMAKE_CXX_COMPILER {wrapper})\n"
        "set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)\n"
        f"set(CMAKE_FIND_ROOT_PATH {prefix})\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)\n"
        "set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)\n"
    )
    return cmake


def patch_uxplay(source):
    # Bionic exposes pthreads in libc; its NDK has no separate libpthread.
    file = source / "lib/CMakeLists.txt"
    original = file.read_text()
    old = "  target_link_libraries( airplay PUBLIC\n          pthread\n"
    if original.count(old) != 1:
        raise ValueError("Pinned UxPlay CMake patch no longer matches")
    file.write_text(original.replace(old, "  target_link_libraries( airplay PUBLIC\n"))


def build(args, core):
    lock = json.loads((ROOT / "packaging/airplay-termux-libs.json").read_text())
    upstream = core / "third_party/sources/uxplay"
    actual = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != UPSTREAM_COMMIT:
        raise ValueError("Restore the locked UxPlay reference first")
    ndk = args.ndk.resolve()
    if "Pkg.Revision = 28.2.13676358" not in (ndk / "source.properties").read_text():
        raise ValueError("Use pinned NDK 28.2.13676358")
    stem = f"zombiebox-airplay-android-{args.arch}"
    args.output.mkdir(parents=True, exist_ok=True)
    if any(
        (args.output / (stem + suffix)).exists()
        for suffix in (".tar.gz", "-sources.tar.gz")
    ):
        raise ValueError("Release assets are immutable")
    with tempfile.TemporaryDirectory(prefix="zombie-airplay-build-") as temporary:
        staging = Path(temporary)
        source, package, sources = (
            staging / "uxplay",
            staging / "package",
            staging / "sources",
        )
        export(upstream, source)
        patch_uxplay(source)
        (package / "bin").mkdir(parents=True)
        (package / "licenses").mkdir()
        sources.mkdir()
        sysroot = staging / "sysroot"
        prefix = termux_sysroot(
            lock, "aarch64" if args.arch == "arm64" else "arm", sysroot
        )
        cmake = toolchain(ndk, prefix, args.arch, staging)
        env = {
            **os.environ,
            "PKG_CONFIG_LIBDIR": str(prefix / "lib/pkgconfig"),
            "PKG_CONFIG_SYSROOT_DIR": str(sysroot),
        }
        build_dir = staging / "build"
        run(
            "cmake",
            "-S",
            str(source),
            "-B",
            str(build_dir),
            "-DCMAKE_TOOLCHAIN_FILE=" + str(cmake),
            "-DNO_X11_DEPS=ON",
            "-DUSE_MDNS=ON",
            "-DCMAKE_BUILD_TYPE=Release",
            "-DOPENSSL_ROOT_DIR=" + str(prefix),
            "-DOPENSSL_INCLUDE_DIR=" + str(prefix / "include"),
            "-DOPENSSL_CRYPTO_LIBRARY=" + str(prefix / "lib/libcrypto.so"),
            "-DCMAKE_EXE_LINKER_FLAGS=-lm",
            env=env,
        )
        run("cmake", "--build", str(build_dir), "-j2", env=env)
        shutil.copy2(build_dir / "uxplay", package / "bin/airplay")
        go_env = {
            **os.environ,
            "GOOS": "android",
            "GOARCH": "arm64" if args.arch == "arm64" else "arm",
            "GOARM": "7",
            "CGO_ENABLED": "0",
            "GOTOOLCHAIN": "go1.25.6",
            "GOMAXPROCS": "2",
        }
        run(
            "go",
            "build",
            "-p=2",
            "-trimpath",
            "-buildmode=pie",
            "-buildvcs=false",
            "-ldflags=-s -w",
            "-o",
            str(package / "bin/zombie-worker"),
            "./cmd/zombie-worker",
            cwd=core / "gateway",
            env=go_env,
        )
        worker_modules = subprocess.check_output(
            ["go", "version", "-m", str(package / "bin/zombie-worker")],
            env=go_env,
            text=True,
        )
        if any(line.split()[:1] == ["dep"] for line in worker_modules.splitlines()):
            raise ValueError(
                "Worker gained external Go modules; extend its source inventory"
            )
        ndk_lib = ndk / "toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib"
        ndk_lib /= (
            "aarch64-linux-android" if args.arch == "arm64" else "arm-linux-androideabi"
        )
        external = {name: prefix / "lib" / name for name in LIBRARIES}
        external["libc++_shared.so"] = ndk_lib / "libc++_shared.so"
        airplay_audit = audit(
            package / "bin/airplay",
            ndk,
            args.arch,
            external,
            verify_external_closure=False,
        )
        worker_audit = audit(
            package / "bin/zombie-worker", ndk, args.arch, allow_no_libraries=True
        )
        for name in ("LICENSE", "NOTICE"):
            shutil.copy2(ROOT / name, package / name)
            shutil.copy2(ROOT / name, sources / name)
        for name, origin in (
            ("upstream-LICENSE", source / "LICENSE"),
            ("llhttp-LICENSE", source / "lib/llhttp/LICENSE-MIT"),
            ("playfair-LICENSE", source / "lib/playfair/LICENSE.md"),
            ("ndk-NOTICE", ndk / "NOTICE"),
            ("ndk-NOTICE.toolchain", ndk / "NOTICE.toolchain"),
        ):
            shutil.copy2(origin, package / "licenses" / name)
        go_root = Path(
            subprocess.check_output(
                ["go", "env", "GOROOT"], env=go_env, text=True
            ).strip()
        )
        shutil.copy2(go_root / "LICENSE", package / "licenses/go-LICENSE")
        archive(source, sources / "uxplay-patched.tar.gz")
        with (sources / "gateway-core.tar").open("wb") as output:
            run("git", "-C", str(core), "archive", "HEAD", stdout=output)
        with tarfile.open(sources / "go-standard-library.tar.gz", "x:gz") as target:
            for name in ("src", "LICENSE", "PATENTS", "VERSION"):
                target.add(go_root / name, arcname="go/" + name)
        shutil.copy2(
            ROOT / "packaging/airplay-termux-libs.json",
            sources / "termux-build-libraries.json",
        )
        shutil.copy2(Path(__file__), sources / "build-airplay-module.py")
        shutil.copy2(ROOT / "scripts/audit_android.py", sources / "audit_android.py")
        shutil.copytree(package / "licenses", sources / "licenses")
        (sources / "BUILDING.md").write_text(
            "Rebuild with Go 1.25.6, NDK 28.2.13676358, CMake and the exact SHA256-checked "
            "Termux .deb headers/libraries in termux-build-libraries.json. Extract the patched UxPlay "
            "source and Core archive; invoke build-airplay-module.py from the matching Edge checkout. "
            "The dynamic Termux libraries are external packages, not included in the binary archive.\n"
        )
        source_asset = args.output / (stem + "-sources.tar.gz")
        archive(sources, source_asset)
        record = {
            "schemaVersion": 1,
            "module": "airplay",
            "moduleVersion": UPSTREAM_COMMIT,
            "upstreamCommit": UPSTREAM_COMMIT,
            "coreCommit": subprocess.check_output(
                ["git", "-C", str(core), "rev-parse", "HEAD"], text=True
            ).strip(),
            "edgeCommit": subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
            ).strip(),
            "platform": "android",
            "architecture": args.arch,
            "minApi": 24,
            "ndk": "28.2.13676358",
            "go": "1.25.6",
            "binaryAudit": {"airplay": airplay_audit, "worker": worker_audit},
            "externalPackages": lock["runtimePackages"],
            "externalRuntimeVerified": False,
            "runtimeVerified": False,
            "candidateOnly": args.allow_dirty,
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
        }
        (package / "module.json").write_text(json.dumps(record, indent=2) + "\n")
        archive(package, args.output / (stem + ".tar.gz"))
    print(f"Built {stem}; native runtime remains unverified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arch", choices=("arm64", "armv7"), required=True)
    parser.add_argument("--ndk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
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
                ["git", "-C", str(repository), "status", "--porcelain"]
            ).strip():
                raise ValueError(
                    "Commit sources first or explicitly build a local candidate"
                )
    build(args, core.resolve())


if __name__ == "__main__":
    main()
