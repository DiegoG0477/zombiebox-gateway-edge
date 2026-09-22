"""Host-side ELF checks against the pinned NDK API24 stubs, not a runtime test."""

import importlib.util
import re
import subprocess
from pathlib import Path


def readelf(tool, path, option):
    return subprocess.check_output(
        [str(tool), "--wide", option, str(path)], text=True, timeout=30
    )


def symbols(output, undefined):
    result = set()
    for line in output.splitlines():
        columns = line.split()
        if len(columns) < 8 or not columns[0].rstrip(":").isdigit():
            continue
        # Optional weak imports may legitimately be absent on an older Android.
        if columns[4] not in ("GLOBAL", "WEAK"):
            continue
        if (columns[6] == "UND") != undefined:
            continue
        if undefined and columns[4] == "WEAK":
            continue
        result.add(columns[7].replace("@@", "@"))
    return result


def audit(binary, ndk, arch):
    spec = importlib.util.spec_from_file_location(
        "installer", Path(__file__).with_name("install-binary.py")
    )
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    if not installer.android_elf(binary.read_bytes(), arch):
        raise ValueError("Expected an Android PIE executable and matching ABI")
    toolchain = ndk / "toolchains/llvm/prebuilt/linux-x86_64"
    tool = toolchain / "bin/llvm-readelf"
    needed = set(re.findall(r"\(NEEDED\).*\[(.*?)\]", readelf(tool, binary, "-d")))
    allowed = {"libc.so", "libdl.so", "libm.so", "liblog.so"}
    if not needed or not needed.issubset(allowed):
        raise ValueError(f"Unexpected runtime libraries: {sorted(needed)}")
    triple = "aarch64-linux-android" if arch == "arm64" else "arm-linux-androideabi"
    stubs = toolchain / "sysroot/usr/lib" / triple / "24"
    exports = set()
    for library in needed:
        exports.update(symbols(readelf(tool, stubs / library, "--dyn-syms"), False))
    imports = symbols(readelf(tool, binary, "--dyn-syms"), True)
    missing = imports - exports
    if missing:
        raise ValueError(f"Imports absent from API24 libraries: {sorted(missing)}")
    loads = [
        line.split()
        for line in readelf(tool, binary, "-l").splitlines()
        if line.strip().startswith("LOAD ")
    ]
    minimum = 16384 if arch == "arm64" else 4096
    if not loads or any(int(row[-1], 16) < minimum for row in loads):
        raise ValueError(
            "ELF LOAD alignment does not meet the Android page-size contract"
        )
    return {
        "architecture": arch,
        "minApi": 24,
        "neededLibraries": sorted(needed),
        "requiredImports": len(imports),
        "api24ImportsSatisfied": True,
        "minimumLoadAlignment": min(int(row[-1], 16) for row in loads),
        "runtimeVerified": False,
    }
