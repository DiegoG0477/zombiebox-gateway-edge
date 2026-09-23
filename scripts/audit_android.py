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


def audit(
    binary,
    ndk,
    arch,
    external_libraries=None,
    verify_external_closure=True,
    allow_no_libraries=False,
):
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
    system = {"libc.so", "libdl.so", "libm.so", "liblog.so"}
    external_libraries = external_libraries or {}
    allowed = system | set(external_libraries)
    if (not needed and not allow_no_libraries) or not needed.issubset(allowed):
        raise ValueError(f"Unexpected runtime libraries: {sorted(needed)}")
    triple = "aarch64-linux-android" if arch == "arm64" else "arm-linux-androideabi"
    stubs = toolchain / "sysroot/usr/lib" / triple / "24"
    exports = set()
    system_needed = needed & system
    for library, path in external_libraries.items():
        if library not in needed or not path.is_file():
            raise ValueError(f"Missing reviewed Termux library: {library}")
        dependencies = set(
            re.findall(r"\(NEEDED\).*\[(.*?)\]", readelf(tool, path, "-d"))
        )
        if verify_external_closure and not dependencies.issubset(allowed):
            raise ValueError(
                f"Unexpected dependency of {library}: {dependencies - allowed}"
            )
        system_needed.update(dependencies & system)
        exports.update(symbols(readelf(tool, path, "--dyn-syms"), False))
    for library in system_needed:
        exports.update(symbols(readelf(tool, stubs / library, "--dyn-syms"), False))
    external_imports = (
        set().union(
            *(
                symbols(readelf(tool, path, "--dyn-syms"), True)
                for path in external_libraries.values()
            )
        )
        if verify_external_closure
        else set()
    )
    imports = symbols(readelf(tool, binary, "--dyn-syms"), True)
    missing = (imports | external_imports) - exports
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
        "externalRuntimeClosureVerified": verify_external_closure,
        "minimumLoadAlignment": min(int(row[-1], 16) for row in loads),
        "runtimeVerified": False,
    }
